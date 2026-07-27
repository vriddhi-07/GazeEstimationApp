"""
Management command to export all participant responses to a single CSV
file for analysis.

Run:
    python3 manage.py export_responses
    python3 manage.py export_responses --output /path/to/file.csv

--- Column mapping / assumptions ---

sr-1/2/3   : Self-rating expertise scores (ParticipantSession fields,
             single value 1-5 each, filled in on the expertise-rating
             screen before the study starts):
               sr-1 = expertise_sentiment
               sr-2 = expertise_fakenews
               sr-3 = expertise_visualisation

sa-1/2/3   : Movies task RAW responses, as a "(sentiment, rating)" tuple.
             sentiment is position-encoded (positive=1, neutral=2,
             negative=3 -- the order shown on the question page).
             rating is exported as-is (already numeric, 0.5-5.0).

fn-1/2/3   : News task raw classification_choice, position-encoded
             (agree=1, disagree=2, discuss=3, unrelated=4 -- the order
             shown on the question page).

viz-1/2/3  : Network diagram task RAW responses, as a "(answer_one_pos,
             answer_two_pos)" tuple. Each value is the 1-based position
             of the participant's chosen answer within that specific
             diagram's own question_one_options / question_two_options
             list (there's no stored "correct answer" to grade against,
             so this is positional, not correctness).

*_paas     : Task-level PAAS rating (PaasResponse.rating) for that task
             (sa=task 1/Movies, fn=task 2/News, viz=task 3/Networks --
             matching the PaasResponse.task_number comment in models.py).

*N_diff    : Per-item relative-difficulty rating (1=Easy, 2=Moderate,
             3=Difficult) for the Nth item *in that same sa/fn/viz slot*
             -- matched by the item's actual id (via the "movie:<id>" /
             "article:<id>" / "diagram:<id>" keys PaasResponse stores),
             not by dict order, so it's guaranteed to line up with the
             correct item even if ratings were submitted out of order.

education / occupation / gender : position-encoded against the live
             EDUCATION_LEVEL_CHOICES / PROFESSION_CHOICES / GENDER_CHOICES
             in forms.py (imported directly, so if those choice lists
             change later this still stays correct without editing this
             file).

prescription_glasses / vision_issues / remarks : not currently collected
             anywhere in the app -- exported as blank placeholder columns
             for manual fill-in, per explicit instruction.

Participants with fewer than 3 responses for a task get blank cells for
the missing slots rather than an error.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from survey_app.forms import EDUCATION_LEVEL_CHOICES, GENDER_CHOICES, PROFESSION_CHOICES
from survey_app.models import (
    MovieReviewResponse,
    NetworkDiagramResponse,
    NewsArticleResponse,
    ParticipantSession,
    PaasResponse,
)


def _position_map(choices, skip_blank=True):
    """1-based position of each choice value, in the order given."""
    result = {}
    pos = 1
    for value, _label in choices:
        if skip_blank and value == "":
            continue
        result[value] = pos
        pos += 1
    return result


EDUCATION_MAP = _position_map(EDUCATION_LEVEL_CHOICES)
GENDER_MAP = _position_map(GENDER_CHOICES)
PROFESSION_MAP = _position_map(PROFESSION_CHOICES)

# Order exactly as shown to participants (movie_questions.html / news_questions.html)
SENTIMENT_MAP = {"positive": 1, "neutral": 2, "negative": 3}
CLASSIFICATION_MAP = {"agree": 1, "disagree": 2, "discuss": 3, "unrelated": 4}

TASK_PREFIX = {1: "sa", 2: "fn", 3: "viz"}  # PaasResponse.task_number -> column prefix

HEADER = [
    "participant_id", "age", "education", "occupation", "gender",
    "sr-1", "sr-2", "sr-3",
    "sa-1", "sa-2", "sa-3",
    "fn-1", "fn-2", "fn-3",
    "viz-1", "viz-2", "viz-3",
    "sa_paas", "sa1_diff", "sa2_diff", "sa3_diff",
    "fn_paas", "fn1_diff", "fn2_diff", "fn3_diff",
    "viz_paas", "viz1_diff", "viz2_diff", "viz3_diff",
    "prescription_glasses", "vision_issues", "remarks",
]


class Command(BaseCommand):
    help = "Export all participant responses to a single CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Output CSV path (default: exports/participant_responses_<timestamp>.csv)",
        )

    def handle(self, *args, **options):
        output_path = options["output"]
        if not output_path:
            stamp = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M%S")
            export_dir = Path(settings.BASE_DIR) / "exports"
            export_dir.mkdir(exist_ok=True)
            output_path = str(export_dir / f"participant_responses_{stamp}.csv")

        rows = []
        participants = (
            ParticipantSession.objects.filter(user__isnull=False)
            .select_related("user")
            .order_by("user__username")
        )

        for p in participants:
            username = p.user.username if p.user else f"anon_{p.id}"
            row = {
                "participant_id": username,
                "age": p.age if p.age is not None else "",
                "education": EDUCATION_MAP.get(p.education_level, ""),
                "occupation": PROFESSION_MAP.get(p.profession, ""),
                "gender": GENDER_MAP.get(p.gender, ""),
                "prescription_glasses": "",
                "vision_issues": "",
                "remarks": "",
            }

            # --- sr: expertise self-ratings (single values, filled in pre-study) ---
            row["sr-1"] = p.expertise_sentiment if p.expertise_sentiment is not None else ""
            row["sr-2"] = p.expertise_fakenews if p.expertise_fakenews is not None else ""
            row["sr-3"] = p.expertise_visualisation if p.expertise_visualisation is not None else ""

            # --- Movies: sa (raw tuple) ---
            movie_responses = list(
                MovieReviewResponse.objects.filter(participant=p)
                .select_related("movie")
                .order_by("created_at")
            )
            for i in range(3):
                slot = i + 1
                if i < len(movie_responses):
                    mr = movie_responses[i]
                    sentiment_code = SENTIMENT_MAP.get(mr.sentiment_choice, mr.sentiment_choice)
                    row[f"sa-{slot}"] = f"({sentiment_code}, {mr.rating_choice})"
                else:
                    row[f"sa-{slot}"] = ""

            # --- News: fn (raw single value, position-encoded) ---
            news_responses = list(
                NewsArticleResponse.objects.filter(participant=p).order_by("created_at")
            )
            for i in range(3):
                slot = i + 1
                if i < len(news_responses):
                    nr = news_responses[i]
                    row[f"fn-{slot}"] = CLASSIFICATION_MAP.get(
                        nr.classification_choice, nr.classification_choice
                    )
                else:
                    row[f"fn-{slot}"] = ""

            # --- Networks: viz (raw tuple, positional against that diagram's own options) ---
            network_responses = list(
                NetworkDiagramResponse.objects.filter(participant=p)
                .select_related("diagram")
                .order_by("created_at")
            )
            for i in range(3):
                slot = i + 1
                if i < len(network_responses):
                    vr = network_responses[i]
                    opts1 = vr.diagram.question_one_options or []
                    opts2 = vr.diagram.question_two_options or []
                    pos1 = (opts1.index(vr.answer_one) + 1) if vr.answer_one in opts1 else vr.answer_one
                    pos2 = (opts2.index(vr.answer_two) + 1) if vr.answer_two in opts2 else vr.answer_two
                    row[f"viz-{slot}"] = f"({pos1}, {pos2})"
                else:
                    row[f"viz-{slot}"] = ""

            # --- PAAS rating + per-item difficulty, matched by actual item id ---
            paas_by_task = {
                pr.task_number: pr for pr in PaasResponse.objects.filter(participant=p)
            }

            # task 1 (Movies) diffs keyed by "movie:<id>", matched to movie_responses order
            pr1 = paas_by_task.get(1)
            row["sa_paas"] = pr1.rating if pr1 else ""
            for i in range(3):
                if pr1 and i < len(movie_responses):
                    key = f"movie:{movie_responses[i].movie_id}"
                    row[f"sa{i+1}_diff"] = pr1.item_difficulty_ratings.get(key, "")
                else:
                    row[f"sa{i+1}_diff"] = ""

            # task 2 (News) diffs keyed by "article:<id>"
            pr2 = paas_by_task.get(2)
            row["fn_paas"] = pr2.rating if pr2 else ""
            for i in range(3):
                if pr2 and i < len(news_responses):
                    key = f"article:{news_responses[i].article_id}"
                    row[f"fn{i+1}_diff"] = pr2.item_difficulty_ratings.get(key, "")
                else:
                    row[f"fn{i+1}_diff"] = ""

            # task 3 (Networks) diffs keyed by "diagram:<id>"
            pr3 = paas_by_task.get(3)
            row["viz_paas"] = pr3.rating if pr3 else ""
            for i in range(3):
                if pr3 and i < len(network_responses):
                    key = f"diagram:{network_responses[i].diagram_id}"
                    row[f"viz{i+1}_diff"] = pr3.item_difficulty_ratings.get(key, "")
                else:
                    row[f"viz{i+1}_diff"] = ""

            rows.append(row)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADER)
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(
            self.style.SUCCESS(f"Exported {len(rows)} participant(s) to {output_path}")
        )