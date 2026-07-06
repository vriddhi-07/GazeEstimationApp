"""
Management command to re-process orphaned raw .webm recordings in
media/tmp_recordings/ that were never finalized (moved + remuxed) into
media/webcam_clips/ or media/screen_clips/.

Run after deploying the recording fix:
    python manage.py reprocess_recordings

What it does:
  1. Scans media/tmp_recordings/ for webcam-<label>-<stamp>.webm files.
  2. Checks whether a corresponding webm already exists in
     media/webcam_clips/ or media/screen_clips/.
  3. If not, remuxes with ffmpeg (fixes MediaRecorder's missing duration/
     seek metadata); falls back to moving the .webm as-is if ffmpeg fails.
  4. Creates the WebcamClip / ScreenClip database record.

Use --dry-run to see what would be processed without actually doing it.
"""

import logging
import threading
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-process orphaned raw .webm recordings in tmp_recordings/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be processed without making changes.",
        )

    def handle(self, *args, **options):
        from survey_app.models import ParticipantSession, WebcamClip, ScreenClip
        from survey_app.views import finalize_webm_recording

        dry_run = options["dry_run"]
        tmp_dir = Path(settings.MEDIA_ROOT) / "tmp_recordings"

        if not tmp_dir.exists():
            self.stdout.write("tmp_recordings/ directory does not exist — nothing to do.")
            return

        webm_files = list(tmp_dir.glob("*.webm"))
        if not webm_files:
            self.stdout.write("No orphaned .webm files found.")
            return

        self.stdout.write(f"Found {len(webm_files)} orphaned file(s).")

        for webm_path in sorted(webm_files):
            name = webm_path.stem          # e.g. "webcam-5_293-1776899842434" (new)
                                            # or "webcam-293-1776899842434" (legacy, pre-username-labels)
            parts = name.split("-")        # ["webcam", "5_293", "1776899842434"]

            if len(parts) != 3 or parts[0] not in ("webcam", "screen"):
                self.stdout.write(self.style.WARNING(f"  Skipping unrecognised file: {webm_path.name}"))
                continue

            kind, label, session_stamp = parts

            # New-style label is "<username>_<db_id>"; legacy label is just
            # "<db_id>" with no username prefix. Support both so orphaned
            # files from before this naming change still reprocess cleanly.
            label_parts = label.rsplit("_", 1)
            if len(label_parts) == 2 and label_parts[1].isdigit():
                participant_id_str = label_parts[1]
            elif label.isdigit():
                participant_id_str = label
            else:
                self.stdout.write(self.style.WARNING(f"  Skipping bad participant id: {webm_path.name}"))
                continue

            try:
                participant_id = int(participant_id_str)
            except ValueError:
                self.stdout.write(self.style.WARNING(f"  Skipping bad participant id: {webm_path.name}"))
                continue

            participant = ParticipantSession.objects.filter(id=participant_id).first()
            if not participant:
                self.stdout.write(self.style.WARNING(
                    f"  Participant {participant_id} not found — skipping {webm_path.name}"
                ))
                continue

            clip_dir = "webcam_clips" if kind == "webcam" else "screen_clips"
            ClipModel = WebcamClip if kind == "webcam" else ScreenClip
            webm_rel = f"{clip_dir}/{name}.webm"
            webm_tmp_rel = f"tmp_recordings/{webm_path.name}"

            # Check if already processed
            webm_out_abs = Path(settings.MEDIA_ROOT) / webm_rel
            if webm_out_abs.exists():
                self.stdout.write(f"  Already processed: {webm_path.name} -> {webm_rel}")
                if not dry_run:
                    ClipModel.objects.get_or_create(participant=participant, clip=webm_rel)
                continue

            self.stdout.write(f"  Processing: {webm_path.name} (participant {participant_id})")
            if dry_run:
                continue

            # Try remuxing (fixes MediaRecorder's missing duration/seek index)
            converted = finalize_webm_recording(webm_tmp_rel, webm_rel)
            if converted:
                self.stdout.write(self.style.SUCCESS(f"    -> Remuxed to {webm_rel}"))
                ClipModel.objects.get_or_create(participant=participant, clip=converted)
                if webm_path.exists():
                    webm_path.unlink()
            else:
                # ffmpeg not available — move webm as-is (duration/seeking
                # will still be broken for this one, but the recording isn't lost)
                dst = Path(settings.MEDIA_ROOT) / webm_rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    webm_path.rename(dst)
                    self.stdout.write(self.style.WARNING(
                        f"    -> ffmpeg unavailable; stored as-is (seek/duration may be broken): {webm_rel}"
                    ))
                    ClipModel.objects.get_or_create(participant=participant, clip=webm_rel)
                except OSError as e:
                    self.stdout.write(self.style.ERROR(f"    -> Failed to move file: {e}"))

        self.stdout.write("Done.")