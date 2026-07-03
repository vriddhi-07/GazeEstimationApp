import json
from pathlib import Path
import subprocess
import threading
import time
import logging
import datetime

from django.contrib.auth import authenticate, login
from django.contrib.auth.models import Group
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import ConsentForm, DemographicForm
from .models import (
    Movie,
    MovieReviewResponse,
    MovieSelection,
    NewsArticle,
    NewsArticleResponse,
    NetworkDiagram,
    NetworkDiagramResponse,
    ParticipantSession,
    Review,
    ScreenClip,
    WebcamClip,
    PaasResponse
)
from .movie_data import MOVIES
from .news_data import NEWS_ARTICLES

# This VM has limited CPU. Running multiple ffmpeg encodes at once causes
# them to starve each other (each libx264 encode wants ~100-200% CPU), so
# conversions that would normally take seconds end up taking many minutes
# or hitting the timeout. Serialize them instead: only one ffmpeg process
# runs at a time, others queue up and run once it's free.
_FFMPEG_SEMAPHORE = threading.Semaphore(1)
from .network_data import NETWORK_DIAGRAMS

CONSENT_RUN_KEY = "consent_for_current_run"
MINIMUM_REQUIRED_REVIEWS = 3
MINIMUM_REQUIRED_NEWS_ARTICLES = 3
MINIMUM_REQUIRED_NETWORK_DIAGRAMS = 3
ACTIVE_REVIEW_SESSION_KEY = "active_movie_review"
ACTIVE_ARTICLE_SESSION_KEY = "active_news_article"


def get_or_create_participant(request: HttpRequest) -> ParticipantSession:
    participant, created = ParticipantSession.objects.get_or_create(user=request.user)
    return participant


def get_recording_participant(request: HttpRequest) -> ParticipantSession:
    participant_id = request.POST.get("participant_id")
    if participant_id:
        participant = ParticipantSession.objects.filter(id=participant_id).first()
        if participant:
            return participant
    return get_or_create_participant(request)


def get_onboarding_redirect(participant: ParticipantSession, request: HttpRequest) -> str | None:
    # if not request.session.get("participant_id"):
    #     return "survey_app:welcome"
    if not participant.consent_given:
        return "survey_app:consent"
    if not participant.demographics_completed_at:
        return "survey_app:demographics"
    if not participant.expertise_completed_at:          # ← ADD THIS BLOCK
        return "survey_app:expertise_rating"
    return None


def get_review_progress(participant: ParticipantSession) -> dict[str, int | bool]:
    reviewed_count = participant.movie_review_responses.count()
    remaining_required = max(MINIMUM_REQUIRED_REVIEWS - reviewed_count, 0)
    return {
        "reviewed_count": reviewed_count,
        "remaining_required": remaining_required,
        "minimum_met": reviewed_count >= MINIMUM_REQUIRED_REVIEWS,
    }


def get_news_progress(participant: ParticipantSession) -> dict[str, int | bool]:
    reviewed_count = participant.news_article_responses.count()
    remaining_required = max(MINIMUM_REQUIRED_NEWS_ARTICLES - reviewed_count, 0)
    return {
        "reviewed_count": reviewed_count,
        "remaining_required": remaining_required,
        "minimum_met": reviewed_count >= MINIMUM_REQUIRED_NEWS_ARTICLES,
    }


def get_network_progress(participant: ParticipantSession) -> dict[str, int | bool]:
    reviewed_count = participant.network_diagram_responses.count()
    remaining_required = max(MINIMUM_REQUIRED_NETWORK_DIAGRAMS - reviewed_count, 0)
    return {
        "reviewed_count": reviewed_count,
        "remaining_required": remaining_required,
        "minimum_met": reviewed_count >= MINIMUM_REQUIRED_NETWORK_DIAGRAMS,
    }


def get_active_review_text(request: HttpRequest, movie: Movie) -> str:
    active_review = request.session.get(ACTIVE_REVIEW_SESSION_KEY, {})
    if active_review.get("movie_id") == movie.id and active_review.get("review_text"):
        return str(active_review["review_text"])

    review = movie.reviews.first()
    review_text = review.text if review else ""
    request.session[ACTIVE_REVIEW_SESSION_KEY] = {
        "movie_id": movie.id,
        "review_text": review_text,
    }
    return review_text


def get_active_article_body(request: HttpRequest, article: NewsArticle) -> str:
    active_article = request.session.get(ACTIVE_ARTICLE_SESSION_KEY, {})
    if active_article.get("article_id") == article.id and active_article.get("body"):
        return str(active_article["body"])

    request.session[ACTIVE_ARTICLE_SESSION_KEY] = {
        "article_id": article.id,
        "body": article.body,
    }
    return article.body


def append_chunk_to_media_file(uploaded_clip, relative_path: str) -> None:
    abs_path = Path(settings.MEDIA_ROOT) / relative_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    with abs_path.open("ab") as destination:
        for chunk in uploaded_clip.chunks():
            destination.write(chunk)


def convert_webm_to_mp4(relative_webm_path: str, relative_mp4_path: str | None = None) -> str | None:
    src_path = Path(settings.MEDIA_ROOT) / relative_webm_path
    if relative_mp4_path is None:
        relative_mp4_path = str(Path(relative_webm_path).with_suffix(".mp4"))
    dst_path = Path(settings.MEDIA_ROOT) / relative_mp4_path
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dst_path = dst_path.with_suffix(".part.mp4")
    if temp_dst_path.exists():
        temp_dst_path.unlink()

    previous_size = -1
    stable_checks = 0
    for _ in range(10):
        if src_path.exists():
            current_size = src_path.stat().st_size
            if current_size > 0 and current_size == previous_size:
                stable_checks += 1
                if stable_checks >= 2:
                    break
            else:
                stable_checks = 0
            previous_size = current_size
        time.sleep(0.5)

    if not src_path.exists():
        error_log_path = dst_path.with_suffix(".ffmpeg.log")
        error_log_path.write_text(f"source recording not found: {src_path}")
        return None

    last_error = ""
    for _ in range(3):
        try:
            with _FFMPEG_SEMAPHORE:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-loglevel",
                        "error",
                        "-i",
                        str(src_path),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "ultrafast",
                        "-vf",
                        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        "-pix_fmt",
                        "yuv420p",
                        "-movflags",
                        "+faststart",
                        str(temp_dst_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL,
                    timeout=420,
                )
            temp_dst_path.replace(dst_path)
            return relative_mp4_path
        except FileNotFoundError:
            last_error = "ffmpeg executable not found"
            break
        except subprocess.TimeoutExpired:
            last_error = "ffmpeg conversion timed out after 420s"
            if temp_dst_path.exists():
                temp_dst_path.unlink()
            break
        except subprocess.CalledProcessError as exc:
            last_error = exc.stderr or exc.stdout or "ffmpeg conversion failed"
            if temp_dst_path.exists():
                temp_dst_path.unlink()
            time.sleep(1)

    error_log_path = dst_path.with_suffix(".ffmpeg.log")
    error_log_path.write_text(last_error or "ffmpeg conversion failed")
    return None


def remove_stale_partial_file(relative_mp4_path: str) -> None:
    dst_path = Path(settings.MEDIA_ROOT) / relative_mp4_path
    temp_dst_path = dst_path.with_suffix(".part.mp4")
    if temp_dst_path.exists():
        temp_dst_path.unlink()


RECORDING_LOG_DIR = Path(settings.BASE_DIR) / "recording_logs"


def log_recording_event(
    participant_id: int,
    session_stamp: str,
    kind: str,
    started_at_ms: str | None,
    ended_at_ms: str | None,
) -> None:
    """
    Append one JSON line per finished clip to a per-participant log file, so
    webcam/screen recording start & end times can be matched up against
    RealEye's own timestamps during post-processing.

    started_at_ms / ended_at_ms are epoch-millisecond timestamps captured in
    the browser (Date.now()) at the moment MediaRecorder actually started
    and stopped — these are the times that matter for sync, not when the
    upload/finalize HTTP requests happened to arrive at the server.
    """
    try:
        started_ms = int(started_at_ms) if started_at_ms else None
        ended_ms = int(ended_at_ms) if ended_at_ms else None
    except (TypeError, ValueError):
        started_ms = None
        ended_ms = None

    def _iso(ms: int | None) -> str | None:
        if ms is None:
            return None
        utc_dt = datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)
        local_dt = timezone.localtime(utc_dt)
        return local_dt.isoformat()

    entry = {
        "event": f"{kind}_recording",
        "participant_id": participant_id,
        "session_stamp": session_stamp,
        "started_at_ms": started_ms,
        "started_at_iso": _iso(started_ms),
        "ended_at_ms": ended_ms,
        "ended_at_iso": _iso(ended_ms),
        "duration_ms": (ended_ms - started_ms) if (started_ms and ended_ms) else None,
        "server_finalize_received_at_iso": timezone.localtime(timezone.now()).isoformat(),
    }

    RECORDING_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RECORDING_LOG_DIR / f"participant_{participant_id}.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def seed_movie_data() -> None:
    for item in MOVIES:
        movie, _ = Movie.objects.update_or_create(
            imdb_id=item["imdb_id"],
            defaults={
                "title": item["title"],
                "year": item["year"],
                "genre": item["genre"],
                "poster_url": item["poster_url"],
                "description": item["description"],
            },
        )

        group_name = f"Set {item.get('set_group', 1)}"
        group, _ = Group.objects.get_or_create(name=group_name)
        movie.target_groups.set([group])

        review = item["review"]
        movie.reviews.all().delete()
        Review.objects.create(
            movie=movie,
            source=review.get("source", "JUMR"),
            sentiment=review["sentiment"],
            text=review["text"],
        )


def seed_news_data() -> None:
    active_slugs = {item["slug"] for item in NEWS_ARTICLES}
    NewsArticle.objects.exclude(slug__in=active_slugs).exclude(
        slug__startswith="demo-"
    ).delete()

    for item in NEWS_ARTICLES:
        article, _ = NewsArticle.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "headline": item["headline"],
                "source": item["source"],
                "summary": item["summary"],
                "body": item["body"],
                "is_fake": item.get("is_fake", False),
            },
        )
        
        # Link the article to the correct Cohort Group
        group_name = f"Set {item.get('set_group', 1)}"
        group, _ = Group.objects.get_or_create(name=group_name)
        article.target_groups.add(group)



def seed_network_data() -> None:
    active_slugs = {item["slug"] for item in NETWORK_DIAGRAMS}
    NetworkDiagram.objects.exclude(slug__in=active_slugs).exclude(
        slug__startswith="demo-"
    ).delete()

    for item in NETWORK_DIAGRAMS:
        diagram, _ = NetworkDiagram.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "order": item.get("order", 0),
                "title": item["title"],
                "type": item["type"],
                "context": item["context"],
                "image_url": item.get("image_url", ""),
                "image_alt": item.get("image_alt", ""),
                "image_source_label": item.get("image_source_label", ""),
                "image_source_url": item.get("image_source_url", ""),
                "nodes": item["nodes"],
                "edges": item["edges"],
                "question_one": item["question_one"],
                "question_one_options": item["question_one_options"],
                "question_two": item["question_two"],
                "question_two_options": item["question_two_options"],
            },
        )

        # Link the diagram to exactly the correct Cohort Group,
        # clearing any stale group links from previous seed runs.
        group_name = f"Set {item.get('set_group', 1)}"
        group, _ = Group.objects.get_or_create(name=group_name)
        diagram.target_groups.set([group])
        
def get_network_display_hints(slug: str) -> dict[str, str]:
    item = next((entry for entry in NETWORK_DIAGRAMS if entry["slug"] == slug), None)
    if not item:
        return {
            "image_fit": "contain",
            "image_position": "center center",
            "image_aspect_ratio": "4 / 3",
            "image_scale": "100%",
        }
    return {
        "image_fit": item.get("image_fit", "contain"),
        "image_position": item.get("image_position", "center center"),
        "image_aspect_ratio": item.get("image_aspect_ratio", "4 / 3"),
        "image_scale": item.get("image_scale", "100%"),
    }


def build_network_edges(diagram: NetworkDiagram) -> list[dict[str, int | str]]:
    if not diagram.nodes or not diagram.edges:
        return []
    node_lookup = {node["id"]: node for node in diagram.nodes}
    rendered_edges: list[dict[str, int | str]] = []
    for edge in diagram.edges:
        source = node_lookup[edge["source"]]
        target = node_lookup[edge["target"]]
        rendered_edges.append(
            {
                "x1": source["x"],
                "y1": source["y"],
                "x2": target["x"],
                "y2": target["y"],
                "mid_x": int((source["x"] + target["x"]) / 2),
                "mid_y": int((source["y"] + target["y"]) / 2) - 10,
                "width": edge.get("width", 4),
                "label": edge.get("label", ""),
            }
        )
    return rendered_edges


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Fetch the participant AND save the ID to the session
            participant = get_or_create_participant(request)
            request.session["participant_id"] = participant.id

            request.session[CONSENT_RUN_KEY] = False
            return redirect("survey_app:consent")
    else:
        form = AuthenticationForm()

    return render(
        request,
        "survey_app/login.html", 
        {
            "form": form,
            "record_webcam": False,
            "reset_capture_session": True,
            "load_survey_js": False,
        },
    )


@require_http_methods(["GET", "POST"])
def consent_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    if request.method == "POST":
        form = ConsentForm(request.POST)
        if form.is_valid():
            participant.consent_given = True
            participant.consented_at = timezone.now()
            participant.participant_tag = form.cleaned_data.get("participant_tag", "")
            participant.save(update_fields=["consent_given", "consented_at", "participant_tag"])
            request.session[CONSENT_RUN_KEY] = False
            return redirect("/demographics/?start_capture=1")
    else:
        onboarding_redirect = get_onboarding_redirect(participant, request)
        if onboarding_redirect and onboarding_redirect != "survey_app:consent":
            return redirect(onboarding_redirect)
        form = ConsentForm()
    return render(
        request,
        "survey_app/consent.html",
        {
            "form": form,
            "record_webcam": False,
            "reset_capture_session": True,
            "load_survey_js": False,
        },
    )


@require_http_methods(["GET", "POST"])
def demographics_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    if not participant.consent_given:
        return redirect("survey_app:consent")
    if participant.demographics_completed_at:
        return redirect("survey_app:expertise_rating")

    if request.method == "POST":
        form = DemographicForm(request.POST)
        if form.is_valid():
            participant.age = form.cleaned_data["age"]
            participant.profession = form.cleaned_data["profession"]
            participant.education_level = form.cleaned_data["education_level"]
            participant.gender = form.cleaned_data["gender"]
            participant.demographics_completed_at = timezone.now()
            participant.save(
                update_fields=[
                    "age",
                    "profession",
                    "education_level",
                    "gender",
                    "demographics_completed_at",
                ]
            )
            return redirect("survey_app:expertise_rating")
    else:
        form = DemographicForm(
            initial={
                "age": participant.age,
                "profession": participant.profession,
                "education_level": participant.education_level,
                "gender": participant.gender,
            }
        )

    return render(
        request,
        "survey_app/demographics.html",
        {
            "form": form,
            "record_webcam": False,
            # After consent we redirect here with ?start_capture=1 so the
            # frontend can open the capture popup automatically.
            "load_survey_js": request.GET.get("start_capture") == "1",
        },
    )


from .forms import ExpertiseRatingForm  # add to your existing forms import line
 
@login_required
def expertise_rating_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
 
    if not participant.demographics_completed_at:
        return redirect("survey_app:demographics")
    if participant.expertise_completed_at:
        return redirect("survey_app:carousel")
 
    if request.method == "POST":
        form = ExpertiseRatingForm(request.POST)
        if form.is_valid():
            participant.expertise_sentiment = form.cleaned_data["expertise_sentiment"]
            participant.expertise_fakenews = form.cleaned_data["expertise_fakenews"]
            participant.expertise_visualisation = form.cleaned_data["expertise_visualisation"]
            participant.expertise_completed_at = timezone.now()
            participant.save(update_fields=[
                "expertise_sentiment",
                "expertise_fakenews",
                "expertise_visualisation",
                "expertise_completed_at",
            ])
            return redirect("survey_app:carousel")
    else:
        form = ExpertiseRatingForm()
 
    return render(request, "survey_app/expertise_rating.html", {
        "form": form,
        "record_webcam": False,
    })
 

@login_required
@require_GET
def carousel_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    seed_movie_data()
    reviewed_movie_ids = participant.movie_review_responses.values_list("movie_id", flat=True)
    
    # Filter by the user's groups
    user_groups = request.user.groups.all()
    movies = Movie.objects.prefetch_related("reviews").filter(
        target_groups__in=user_groups
    ).exclude(id__in=reviewed_movie_ids).distinct()
    
    progress = get_review_progress(participant)
    return render(
        request,
        "survey_app/carousel.html",
        {
            "movies": movies,
            "progress": progress,
            "record_webcam": True,
        },
    )

@login_required
@require_GET
def news_carousel_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    seed_news_data()
    responded_article_ids = participant.news_article_responses.values_list("article_id", flat=True)

    user_groups = request.user.groups.all()
    next_article = NewsArticle.objects.filter(
        target_groups__in=user_groups
    ).exclude(id__in=responded_article_ids).distinct().first()

    if next_article:
        return redirect("survey_app:news_detail", article_id=next_article.id)

    progress = get_news_progress(participant)
    if progress["minimum_met"]:
        return redirect("survey_app:paas_evaluation", task_number=2)
    # No articles available for this user's groups and minimum not yet met.
    # Redirecting to next_task here would cause an infinite loop, so fall
    # through to the PAAS screen to avoid getting stuck.
    return redirect("survey_app:paas_evaluation", task_number=2)

@login_required
@require_GET
def network_carousel_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)
    if not get_news_progress(participant)["minimum_met"]:
        return redirect("survey_app:news_carousel")

    seed_network_data()
    responded_diagram_ids = participant.network_diagram_responses.values_list("diagram_id", flat=True)

    user_groups = request.user.groups.all()
    next_diagram = NetworkDiagram.objects.filter(
        target_groups__in=user_groups
    ).exclude(id__in=responded_diagram_ids).distinct().first()

    if next_diagram:
        return redirect("survey_app:network_questions", diagram_id=next_diagram.id)

    progress = get_network_progress(participant)
    if progress["minimum_met"]:
        return redirect("survey_app:paas_evaluation", task_number=3)
    return redirect("survey_app:next_task")


@require_GET
def movie_detail_view(request: HttpRequest, movie_id: int) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    movie = get_object_or_404(Movie.objects.prefetch_related("reviews"), id=movie_id)
    if participant.movie_review_responses.filter(movie=movie).exists():
        return redirect("survey_app:carousel")
    MovieSelection.objects.create(participant=participant, movie=movie)
    review_text = get_active_review_text(request, movie)
    return render(
        request,
        "survey_app/movie_detail.html",
        {
            "movie": movie,
            "review_text": review_text,
            "record_webcam": True,
        },
    )


@require_http_methods(["GET", "POST"])
def movie_questions_view(request: HttpRequest, movie_id: int) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    movie = get_object_or_404(Movie.objects.prefetch_related("reviews"), id=movie_id)
    if participant.movie_review_responses.filter(movie=movie).exists():
        return redirect("survey_app:carousel")

    review_text = get_active_review_text(request, movie)
    if request.method == "POST":
        sentiment_choice = str(request.POST.get("sentiment_choice", "")).lower().strip()
        if sentiment_choice not in {"positive", "neutral", "negative"}:
            return render(
                request,
                "survey_app/movie_questions.html",
                {
                    "movie": movie,
                    "review_text": review_text,
                    "error_message": "Select a sentiment option.",
                    "selected_sentiment": sentiment_choice,
                    "selected_rating": request.POST.get("rating_choice", ""),
                    "record_webcam": True,
                },
            )

        try:
            rating_choice = float(request.POST.get("rating_choice"))
        except (TypeError, ValueError):
            rating_choice = 0

        if rating_choice < 0.5 or rating_choice > 5.0 or (rating_choice * 2) % 1 != 0:
            return render(
                request,
                "survey_app/movie_questions.html",
                {
                    "movie": movie,
                    "review_text": review_text,
                    "error_message": "Select a rating in 0.5 star increments.",
                    "selected_sentiment": sentiment_choice,
                    "selected_rating": request.POST.get("rating_choice", ""),
                    "record_webcam": True,
                },
            )

        MovieReviewResponse.objects.create(
            participant=participant,
            movie=movie,
            review_text=review_text,
            sentiment_choice=sentiment_choice,
            rating_choice=rating_choice,
        )
        request.session.pop(ACTIVE_REVIEW_SESSION_KEY, None)
        progress = get_review_progress(participant)
        if progress["minimum_met"]:
            return redirect("survey_app:paas_evaluation", task_number=1)
        return redirect("survey_app:carousel")

    return render(
        request,
        "survey_app/movie_questions.html",
        {
            "movie": movie,
            "review_text": review_text,
            "record_webcam": True,
        },
    )


@require_GET
def news_detail_view(request: HttpRequest, article_id: int) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    article = get_object_or_404(NewsArticle, id=article_id)
    if participant.news_article_responses.filter(article=article).exists():
        return redirect("survey_app:news_carousel")

    article_body = get_active_article_body(request, article)
    return render(
        request,
        "survey_app/news_detail.html",
        {
            "article": article,
            "article_body": article_body,
            "record_webcam": True,
        },
    )


@require_http_methods(["GET", "POST"])
def news_questions_view(request: HttpRequest, article_id: int) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    article = get_object_or_404(NewsArticle, id=article_id)
    if participant.news_article_responses.filter(article=article).exists():
        return redirect("survey_app:news_carousel")

    article_body = get_active_article_body(request, article)
    if request.method == "POST":
        classification_choice = str(request.POST.get("classification_choice", "")).lower().strip()
        if classification_choice not in {"agree", "disagree", "discuss", "unrelated"}:
            return render(
                request,
                "survey_app/news_questions.html",
                {
                    "article": article,
                    "article_body": article_body,
                    "error_message": "Choose how the article text relates to the headline.",
                    "selected_classification": classification_choice,
                    "record_webcam": True,
                },
            )

        NewsArticleResponse.objects.create(
            participant=participant,
            article=article,
            classification_choice=classification_choice,
        )
        request.session.pop(ACTIVE_ARTICLE_SESSION_KEY, None)
        progress = get_news_progress(participant)
        if progress["minimum_met"]:
            return redirect("survey_app:paas_evaluation", task_number=2)
        # Auto-pick next article for the user
        user_groups = request.user.groups.all()
        next_article = NewsArticle.objects.filter(
            target_groups__in=user_groups
        ).exclude(
            id__in=participant.news_article_responses.values_list("article_id", flat=True)
        ).distinct().first()
        if next_article:
            return redirect("survey_app:news_detail", article_id=next_article.id)
        return redirect("survey_app:paas_evaluation", task_number=2)

    return render(
        request,
        "survey_app/news_questions.html",
        {
            "article": article,
            "article_body": article_body,
            "record_webcam": True,
        },
    )


@require_GET
def network_detail_view(request: HttpRequest, diagram_id: int) -> HttpResponse:
    return redirect("survey_app:network_questions", diagram_id=diagram_id)


@require_http_methods(["GET", "POST"])
def network_questions_view(request: HttpRequest, diagram_id: int) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)
    if not get_news_progress(participant)["minimum_met"]:
        return redirect("survey_app:news_carousel")

    diagram = get_object_or_404(NetworkDiagram, id=diagram_id)
    if participant.network_diagram_responses.filter(diagram=diagram).exists():
        return redirect("survey_app:network_carousel")

    edges = build_network_edges(diagram)
    display_hints = get_network_display_hints(diagram.slug)

    if request.method == "POST":
        answer_one = str(request.POST.get("answer_one", "")).strip()
        answer_two = str(request.POST.get("answer_two", "")).strip()

        if answer_one not in diagram.question_one_options or answer_two not in diagram.question_two_options:
            return render(
                request,
                "survey_app/network_questions.html",
                {
                    "diagram": diagram,
                    "edges": edges,
                    **display_hints,
                    "error_message": "Choose one answer for each question before continuing.",
                    "selected_answer_one": answer_one,
                    "selected_answer_two": answer_two,
                    "record_webcam": True,
                },
            )

        NetworkDiagramResponse.objects.create(
            participant=participant,
            diagram=diagram,
            answer_one=answer_one,
            answer_two=answer_two,
        )
        progress = get_network_progress(participant)
        if progress["minimum_met"]:
            return redirect("survey_app:paas_evaluation", task_number=3)
        # Auto-pick next diagram for the user
        user_groups = request.user.groups.all()
        next_diagram = NetworkDiagram.objects.filter(
            target_groups__in=user_groups
        ).exclude(
            id__in=participant.network_diagram_responses.values_list("diagram_id", flat=True)
        ).distinct().first()
        if next_diagram:
            return redirect("survey_app:network_questions", diagram_id=next_diagram.id)
        return redirect("survey_app:paas_evaluation", task_number=3)

    return render(
        request,
        "survey_app/network_questions.html",
        {
            "diagram": diagram,
            "edges": edges,
            **display_hints,
            "record_webcam": True,
        },
    )


@require_POST
def select_movie(request: HttpRequest, movie_id: int) -> JsonResponse:
    participant = get_or_create_participant(request)
    if get_onboarding_redirect(participant, request):
        return JsonResponse({"error": "Consent required"}, status=403)

    movie = get_object_or_404(Movie, id=movie_id)
    if participant.movie_review_responses.filter(movie=movie).exists():
        return JsonResponse({"error": "Movie already reviewed"}, status=409)
    MovieSelection.objects.create(participant=participant, movie=movie)
    return JsonResponse(
        {
            "ok": True,
            "movie_id": movie.id,
            "detail_url": f"/movies/{movie.id}/",
        }
    )


@require_GET
def movie_reviews_api(request: HttpRequest, movie_id: int) -> JsonResponse:
    participant = get_or_create_participant(request)
    if get_onboarding_redirect(participant, request):
        return JsonResponse({"error": "Consent required"}, status=403)

    movie = get_object_or_404(Movie.objects.prefetch_related("reviews"), id=movie_id)
    if participant.movie_review_responses.filter(movie=movie).exists():
        return JsonResponse({"error": "Movie already reviewed"}, status=409)
    reviews = [
        {"sentiment": review.sentiment, "text": review.text}
        for review in movie.reviews.all()
    ]
    return JsonResponse({"ok": True, "movie_id": movie.id, "reviews": reviews})


@require_POST
def submit_movie_response(request: HttpRequest, movie_id: int) -> JsonResponse:
    participant = get_or_create_participant(request)
    if get_onboarding_redirect(participant, request):
        return JsonResponse({"error": "Consent required"}, status=403)

    movie = get_object_or_404(Movie, id=movie_id)
    if participant.movie_review_responses.filter(movie=movie).exists():
        return JsonResponse({"ok": False, "error": "Movie already reviewed"}, status=409)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid payload"}, status=400)

    sentiment_choice = str(payload.get("sentiment_choice", "")).lower().strip()
    if sentiment_choice not in {"positive", "neutral", "negative"}:
        return JsonResponse({"ok": False, "error": "Invalid sentiment choice"}, status=400)

    try:
        rating_choice = float(payload.get("rating_choice"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid rating value"}, status=400)

    if rating_choice < 0.5 or rating_choice > 5.0 or (rating_choice * 2) % 1 != 0:
        return JsonResponse({"ok": False, "error": "Rating must be in 0.5 increments"}, status=400)

    MovieReviewResponse.objects.create(
        participant=participant,
        movie=movie,
        review_text=str(payload.get("review_text", "")),
        sentiment_choice=sentiment_choice,
        rating_choice=rating_choice,
    )
    progress = get_review_progress(participant)
    return JsonResponse(
        {
            "ok": True,
            "reviewed_count": progress["reviewed_count"],
            "remaining_required": progress["remaining_required"],
            "minimum_met": progress["minimum_met"],
            "carousel_url": "/movies/",
            "next_task_url": "/next-task/",
        }
    )


@require_GET
def next_task_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    # Check Task 1 (Movies)
    if not get_review_progress(participant)["minimum_met"]:
        return redirect("survey_app:carousel")
    if not participant.paas_responses.filter(task_number=1).exists():
        return redirect("survey_app:paas_evaluation", task_number=1)

    # After PAAS 1: auto-start Task 2 (News) — pick first article directly
    if not get_news_progress(participant)["minimum_met"]:
        seed_news_data()
        responded_article_ids = participant.news_article_responses.values_list("article_id", flat=True)
        user_groups = request.user.groups.all()
        next_article = NewsArticle.objects.filter(
            target_groups__in=user_groups
        ).exclude(id__in=responded_article_ids).distinct().first()
        if next_article:
            return redirect("survey_app:news_detail", article_id=next_article.id)
        return redirect("survey_app:news_carousel")
    # if not participant.paas_responses.filter(task_number=2).exists():
    #     return redirect("survey_app:paas_evaluation", task_number=2)
    if not get_news_progress(participant)["minimum_met"]:
        seed_news_data()
        responded_article_ids = participant.news_article_responses.values_list("article_id", flat=True)
        user_groups = request.user.groups.all()
        next_article = NewsArticle.objects.filter(
            target_groups__in=user_groups
        ).exclude(id__in=responded_article_ids).distinct().first()
        if next_article:
            return redirect("survey_app:news_detail", article_id=next_article.id)
        return redirect("survey_app:paas_evaluation", task_number=2)
    if not participant.paas_responses.filter(task_number=2).exists():
        return redirect("survey_app:paas_evaluation", task_number=2)

    # After PAAS 2: auto-start Task 3 (Networks/Word Cloud) — pick first diagram directly

    # After PAAS 2: auto-start Task 3 (Networks/Word Cloud) — pick first diagram directly
    if not get_network_progress(participant)["minimum_met"]:
        seed_network_data()
        responded_diagram_ids = participant.network_diagram_responses.values_list("diagram_id", flat=True)
        user_groups = request.user.groups.all()
        next_diagram = NetworkDiagram.objects.filter(
            target_groups__in=user_groups
        ).exclude(id__in=responded_diagram_ids).distinct().first()
        if next_diagram:
            return redirect("survey_app:network_questions", diagram_id=next_diagram.id)
        return redirect("survey_app:network_carousel")
    if not participant.paas_responses.filter(task_number=3).exists():
        return redirect("survey_app:paas_evaluation", task_number=3)

    return redirect("survey_app:thank_you")


@require_GET
def thank_you_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)
    if not get_network_progress(participant)["minimum_met"]:
        return redirect("survey_app:next_task")
    return render(request, "survey_app/thank_you.html", {"record_webcam": True})


@require_GET
@ensure_csrf_cookie
def capture_session_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    if not participant.consent_given:
        return redirect("survey_app:consent")

    return render(
        request,
        "survey_app/capture_session.html",
        {
            "record_webcam": False,
            "participant_id": participant.id,
        },
    )


@require_POST
def upload_webcam_clip(request: HttpRequest) -> HttpResponse:
    participant = get_recording_participant(request)
    if not participant.consent_given:
        return HttpResponseForbidden("Consent required")

    clip = request.FILES.get("clip")
    session_stamp = request.POST.get("session_stamp")
    if clip is None or not session_stamp:
        return JsonResponse({"ok": False, "error": "Missing clip"}, status=400)

    temp_relative_path = f"tmp_recordings/webcam-{participant.id}-{session_stamp}.webm"
    append_chunk_to_media_file(clip, temp_relative_path)
    return JsonResponse({"ok": True})


@require_POST
def upload_screen_clip(request: HttpRequest) -> HttpResponse:
    participant = get_recording_participant(request)
    if not participant.consent_given:
        return HttpResponseForbidden("Consent required")

    clip = request.FILES.get("clip")
    session_stamp = request.POST.get("session_stamp")
    if clip is None or not session_stamp:
        return JsonResponse({"ok": False, "error": "Missing clip"}, status=400)

    temp_relative_path = f"tmp_recordings/screen-{participant.id}-{session_stamp}.webm"
    append_chunk_to_media_file(clip, temp_relative_path)
    return JsonResponse({"ok": True})


@require_POST
def finalize_webcam_clip(request: HttpRequest) -> HttpResponse:
    participant = get_recording_participant(request)
    if not participant.consent_given:
        return HttpResponseForbidden("Consent required")

    session_stamp = request.POST.get("session_stamp")
    if not session_stamp:
        return JsonResponse({"ok": False, "error": "Missing session_stamp"}, status=400)

    started_at = request.POST.get("started_at")
    ended_at = request.POST.get("ended_at")

    webm_relative_path = f"tmp_recordings/webcam-{participant.id}-{session_stamp}.webm"
    mp4_relative_path = f"webcam_clips/webcam-{participant.id}-{session_stamp}.mp4"
    webm_fallback_path = f"webcam_clips/webcam-{participant.id}-{session_stamp}.webm"
    participant_id = participant.id

    log_recording_event(participant_id, session_stamp, "webcam", started_at, ended_at)

    logger = logging.getLogger(__name__)

    def _convert():
        logger.info("========== Webcam finalize started ==========")
        logger.info("Participant ID: %s", participant_id)
        logger.info("Source: %s", webm_relative_path)
        logger.info("Destination MP4: %s", mp4_relative_path)

        try:
            # Attempt MP4 conversion
            converted_path = convert_webm_to_mp4(
                webm_relative_path,
                mp4_relative_path,
            )

            logger.info("convert_webm_to_mp4() returned: %s", converted_path)

            if converted_path:
                logger.info("MP4 conversion succeeded.")
                remove_stale_partial_file(mp4_relative_path)

            else:
                logger.warning("MP4 conversion failed. Falling back to WEBM.")

                src = Path(settings.MEDIA_ROOT) / webm_relative_path
                dst = Path(settings.MEDIA_ROOT) / webm_fallback_path

                logger.info("Moving %s -> %s", src, dst)

                dst.parent.mkdir(parents=True, exist_ok=True)

                src.rename(dst)

                converted_path = webm_fallback_path

                logger.info("Fallback WEBM move succeeded.")

            from .models import ParticipantSession, WebcamClip

            logger.info("Looking up ParticipantSession id=%s", participant_id)

            participant_session = ParticipantSession.objects.get(id=participant_id)

            logger.info("ParticipantSession found: %s", participant_session)

            clip, created = WebcamClip.objects.get_or_create(
                participant=participant_session,
                clip=converted_path,
            )

            logger.info(
                "WebcamClip %s (created=%s)",
                clip.pk,
                created,
            )

            webm_path = Path(settings.MEDIA_ROOT) / webm_relative_path

            if webm_path.exists():
                logger.info("Deleting temp file %s", webm_path)
                webm_path.unlink()

            logger.info("========== Webcam finalize completed ==========")

        except Exception:
            logger.exception("ERROR while finalizing webcam recording")

    threading.Thread(target=_convert, daemon=True).start()
    return JsonResponse({"ok": True, "queued": True})


@require_POST
def finalize_screen_clip(request: HttpRequest) -> HttpResponse:
    participant = get_recording_participant(request)
    if not participant.consent_given:
        return HttpResponseForbidden("Consent required")

    session_stamp = request.POST.get("session_stamp")
    if not session_stamp:
        return JsonResponse({"ok": False, "error": "Missing session_stamp"}, status=400)

    started_at = request.POST.get("started_at")
    ended_at = request.POST.get("ended_at")

    webm_relative_path = f"tmp_recordings/screen-{participant.id}-{session_stamp}.webm"
    mp4_relative_path = f"screen_clips/screen-{participant.id}-{session_stamp}.mp4"
    webm_fallback_path = f"screen_clips/screen-{participant.id}-{session_stamp}.webm"
    participant_id = participant.id

    log_recording_event(participant_id, session_stamp, "screen", started_at, ended_at)

    logger = logging.getLogger(__name__)

    def _convert():
        try:
            converted_path = convert_webm_to_mp4(webm_relative_path, mp4_relative_path)
            if converted_path:
                remove_stale_partial_file(mp4_relative_path)
            else:
                src = Path(settings.MEDIA_ROOT) / webm_relative_path
                dst = Path(settings.MEDIA_ROOT) / webm_fallback_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    src.rename(dst)
                    converted_path = webm_fallback_path
                except OSError:
                    logger.error(
                        "Could not move webm to fallback path: %s -> %s", src, dst
                    )
                    return

            from .models import ParticipantSession as _PS, ScreenClip as _SC
            p = _PS.objects.filter(id=participant_id).first()
            if p:
                clip, created = _SC.objects.get_or_create(participant=p, clip=converted_path)
                logger.info("ScreenClip %s (created=%s)", clip.pk, created)
            else:
                logger.error("ParticipantSession id=%s not found for screen clip", participant_id)

            webm_path = Path(settings.MEDIA_ROOT) / webm_relative_path
            if webm_path.exists():
                try:
                    webm_path.unlink()
                except OSError:
                    pass
        except Exception:
            logger.exception("ERROR while finalizing screen recording")

    threading.Thread(target=_convert, daemon=True).start()
    return JsonResponse({"ok": True, "queued": True})


def get_paas_difficulty_items(participant: ParticipantSession, task_number: int) -> list[dict]:
    """
    Build the list of items the participant actually saw for this task,
    each as {"key": "<type>:<id>", "label": <display name>}, so the
    relative-difficulty question can show real item names.
    """
    items: list[dict] = []

    if task_number == 1:
        responses = (
            participant.movie_review_responses
            .select_related("movie")
            .order_by("created_at")
        )
        seen_ids = set()
        for response in responses:
            if response.movie_id in seen_ids:
                continue
            seen_ids.add(response.movie_id)
            items.append({
                "key": f"movie:{response.movie_id}",
                "label": response.movie.title,
            })

    elif task_number == 2:
        responses = (
            participant.news_article_responses
            .select_related("article")
            .order_by("created_at")
        )
        seen_ids = set()
        for response in responses:
            if response.article_id in seen_ids:
                continue
            seen_ids.add(response.article_id)
            items.append({
                "key": f"article:{response.article_id}",
                "label": response.article.headline,
            })

    elif task_number == 3:
        type_labels = {
            "wordcloud": "Word Cloud",
            "network": "Network Diagram",
            "metromap": "Metro Map",
        }
        responses = (
            participant.network_diagram_responses
            .select_related("diagram")
            .order_by("created_at")
        )
        seen_ids = set()
        for response in responses:
            if response.diagram_id in seen_ids:
                continue
            seen_ids.add(response.diagram_id)
            label = type_labels.get(response.diagram.type, response.diagram.title)
            items.append({
                "key": f"diagram:{response.diagram_id}",
                "label": label,
            })

    return items

@require_http_methods(["GET", "POST"])
def paas_evaluation_view(request: HttpRequest, task_number: int) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    if PaasResponse.objects.filter(participant=participant, task_number=task_number).exists():
        return redirect("survey_app:next_task")

    difficulty_items = get_paas_difficulty_items(participant, task_number)

    if request.method == "POST":
        rating = request.POST.get("paas_rating")
        difficulty_ratings: dict[str, int] = {}
        difficulty_valid = True

        for item in difficulty_items:
            field_name = f"difficulty_{item['key']}"
            value = request.POST.get(field_name)
            if value and value.isdigit() and 1 <= int(value) <= 3:
                difficulty_ratings[item["key"]] = int(value)
            else:
                difficulty_valid = False

        if rating and rating.isdigit() and 1 <= int(rating) <= 9 and difficulty_valid:
            PaasResponse.objects.update_or_create(
                participant=participant,
                task_number=task_number,
                defaults={
                    "rating": int(rating),
                    "item_difficulty_ratings": difficulty_ratings,
                }
            )
            
            return redirect("survey_app:next_task")
            
        else:
            return render(
                request, 
                "survey_app/paas_evaluation.html", 
                {
                    "task_number": task_number,
                    "difficulty_items": difficulty_items,
                    "error_message": "Please select a mental effort rating from 1 to 9, and a difficulty rating for every item listed below.",
                    "record_webcam": True,
                }
            )

    return render(
        request, 
        "survey_app/paas_evaluation.html", 
        {
            "task_number": task_number,
            "difficulty_items": difficulty_items,
            "record_webcam": True,
        }
    )