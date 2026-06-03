import json
from pathlib import Path
import subprocess
import time

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import ConsentForm, DemographicForm, MediaPreferencesForm, ReadingHabitsForm
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
from .network_data import NETWORK_DIAGRAMS

CONSENT_RUN_KEY = "consent_for_current_run"
MINIMUM_REQUIRED_REVIEWS = 3
MINIMUM_REQUIRED_NEWS_ARTICLES = 3
MINIMUM_REQUIRED_NETWORK_DIAGRAMS = 3
ACTIVE_REVIEW_SESSION_KEY = "active_movie_review"
ACTIVE_ARTICLE_SESSION_KEY = "active_news_article"


def get_or_create_participant(request: HttpRequest) -> ParticipantSession:
    participant_id = request.session.get("participant_id")
    if participant_id:
        participant = ParticipantSession.objects.filter(id=participant_id).first()
        if participant:
            return participant

    participant = ParticipantSession.objects.create()
    request.session["participant_id"] = participant.id
    return participant


def get_recording_participant(request: HttpRequest) -> ParticipantSession:
    participant_id = request.POST.get("participant_id")
    if participant_id:
        participant = ParticipantSession.objects.filter(id=participant_id).first()
        if participant:
            return participant
    return get_or_create_participant(request)


def get_onboarding_redirect(participant: ParticipantSession, request: HttpRequest) -> str | None:
    if not request.session.get("participant_id"):
        return "survey_app:welcome"
    if not participant.consent_given:
        return "survey_app:consent"
    if not participant.demographics_completed_at:
        return "survey_app:demographics"
    if not participant.reads_words_daily or participant.reads_news_daily is None:
        return "survey_app:habits"
    if not participant.reading_habits_completed_at or not request.session.get(CONSENT_RUN_KEY, False):
        return "survey_app:media_preferences"
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
            )
            temp_dst_path.replace(dst_path)
            return relative_mp4_path
        except FileNotFoundError:
            last_error = "ffmpeg executable not found"
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
        reviews = item["reviews"]
        movie.reviews.all().delete()
        Review.objects.bulk_create(
            [
                Review(
                    movie=movie,
                    source=review.get("source", "SST"),
                    sentiment=review["sentiment"],
                    text=review["text"],
                )
                for review in reviews
            ]
        )


def seed_news_data() -> None:
    active_slugs = {item["slug"] for item in NEWS_ARTICLES}
    NewsArticle.objects.exclude(slug__in=active_slugs).delete()

    for item in NEWS_ARTICLES:
        NewsArticle.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "headline": item["headline"],
                "source": item["source"],
                "summary": item["summary"],
                "body": item["body"],
                "is_fake": item.get("is_fake", False),
            },
        )


def seed_network_data() -> None:
    active_slugs = {item["slug"] for item in NETWORK_DIAGRAMS}
    NetworkDiagram.objects.exclude(slug__in=active_slugs).delete()

    for item in NETWORK_DIAGRAMS:
        NetworkDiagram.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "title": item["title"],
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


@require_GET
def welcome_view(request: HttpRequest) -> HttpResponse:
    participant = ParticipantSession.objects.create()
    request.session["participant_id"] = participant.id
    request.session[CONSENT_RUN_KEY] = False
    request.session.pop(ACTIVE_REVIEW_SESSION_KEY, None)
    request.session.pop(ACTIVE_ARTICLE_SESSION_KEY, None)
    return render(
        request,
        "survey_app/welcome.html",
        {
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
        return redirect("survey_app:habits")

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
            return redirect("survey_app:habits")
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


@require_http_methods(["GET", "POST"])
def reading_habits_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    if not participant.consent_given:
        return redirect("survey_app:consent")
    if not participant.demographics_completed_at:
        return redirect("survey_app:demographics")
    if participant.reads_words_daily and participant.reads_news_daily is not None:
        return redirect("survey_app:media_preferences")

    if request.method == "POST":
        form = ReadingHabitsForm(request.POST)
        if form.is_valid():
            participant.reads_words_daily = form.cleaned_data["reads_words_daily"]
            participant.reads_news_daily = form.cleaned_data["reads_news_daily"] == "yes"
            participant.save(
                update_fields=[
                    "reads_words_daily",
                    "reads_news_daily",
                ]
            )
            return redirect("survey_app:media_preferences")
    else:
        form = ReadingHabitsForm(
            initial={
                "reads_words_daily": participant.reads_words_daily,
                "reads_news_daily": "yes" if participant.reads_news_daily else "no" if participant.reads_news_daily is False else "",
            }
        )

    return render(
        request,
        "survey_app/reading_habits.html",
        {
            "form": form,
            "record_webcam": False,
            "load_survey_js": True,
        },
    )


@require_http_methods(["GET", "POST"])
def media_preferences_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    if not participant.consent_given:
        return redirect("survey_app:consent")
    if not participant.demographics_completed_at:
        return redirect("survey_app:demographics")
    if not participant.reads_words_daily or participant.reads_news_daily is None:
        return redirect("survey_app:habits")
    if participant.reading_habits_completed_at and request.session.get(CONSENT_RUN_KEY, False):
        return redirect("/movies/")

    if request.method == "POST":
        form = MediaPreferencesForm(request.POST)
        if form.is_valid():
            participant.movies_per_week = form.cleaned_data["movies_per_week"]
            participant.picture_statement_agreement = form.cleaned_data["picture_statement_agreement"]
            participant.reading_habits_completed_at = timezone.now()
            participant.save(
                update_fields=[
                    "movies_per_week",
                    "picture_statement_agreement",
                    "reading_habits_completed_at",
                ]
            )
            request.session[CONSENT_RUN_KEY] = True
            return redirect("/movies/")
    else:
        form = MediaPreferencesForm(
            initial={
                "movies_per_week": participant.movies_per_week,
                "picture_statement_agreement": participant.picture_statement_agreement,
            }
        )

    return render(
        request,
        "survey_app/media_preferences.html",
        {
            "form": form,
            "record_webcam": False,
            "load_survey_js": True,
        },
    )


@require_GET
def carousel_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    seed_movie_data()
    reviewed_movie_ids = participant.movie_review_responses.values_list("movie_id", flat=True)
    movies = Movie.objects.prefetch_related("reviews").exclude(id__in=reviewed_movie_ids)
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


@require_GET
def news_carousel_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    seed_news_data()
    responded_article_ids = participant.news_article_responses.values_list("article_id", flat=True)
    articles = NewsArticle.objects.exclude(id__in=responded_article_ids)
    progress = get_news_progress(participant)
    return render(
        request,
        "survey_app/news_carousel.html",
        {
            "articles": articles,
            "progress": progress,
            "record_webcam": True,
        },
    )


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
        return render(
            request,
            "survey_app/review_submitted.html",
            {
                "minimum_met": progress["minimum_met"],
                "record_webcam": True,
            },
        )

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
        remaining_articles = NewsArticle.objects.exclude(
            id__in=participant.news_article_responses.values_list("article_id", flat=True)
        ).exists()
        return render(
            request,
            "survey_app/news_submitted.html",
            {
                "has_more_articles": remaining_articles,
                "minimum_met": progress["minimum_met"],
                "record_webcam": True,
            },
        )

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
def network_carousel_view(request: HttpRequest) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)
    if not get_news_progress(participant)["minimum_met"]:
        return redirect("survey_app:news_carousel")

    seed_network_data()
    responded_diagram_ids = participant.network_diagram_responses.values_list("diagram_id", flat=True)
    diagrams = NetworkDiagram.objects.exclude(id__in=responded_diagram_ids)
    progress = get_network_progress(participant)
    return render(
        request,
        "survey_app/network_carousel.html",
        {
            "diagrams": diagrams,
            "progress": progress,
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
        remaining_diagrams = NetworkDiagram.objects.exclude(
            id__in=participant.network_diagram_responses.values_list("diagram_id", flat=True)
        ).exists()
        return render(
            request,
            "survey_app/network_submitted.html",
            {
                "has_more_diagrams": remaining_diagrams,
                "minimum_met": progress["minimum_met"],
                "record_webcam": True,
            },
        )

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

    # Check Task 2 (News)
    if not get_news_progress(participant)["minimum_met"]:
        return redirect("survey_app:news_carousel")
    if not participant.paas_responses.filter(task_number=2).exists():
        return redirect("survey_app:paas_evaluation", task_number=2)

    # Check Task 3 (Networks)
    if not get_network_progress(participant)["minimum_met"]:
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

    webm_relative_path = f"tmp_recordings/webcam-{participant.id}-{session_stamp}.webm"
    mp4_relative_path = f"webcam_clips/webcam-{participant.id}-{session_stamp}.mp4"
    converted_path = convert_webm_to_mp4(webm_relative_path, mp4_relative_path)
    if not converted_path:
        return JsonResponse({"ok": False, "error": "Conversion failed"}, status=500)

    remove_stale_partial_file(mp4_relative_path)
    WebcamClip.objects.get_or_create(participant=participant, clip=converted_path)

    webm_path = Path(settings.MEDIA_ROOT) / webm_relative_path
    if webm_path.exists():
        webm_path.unlink()

    return JsonResponse({"ok": True, "file": converted_path})


@require_POST
def finalize_screen_clip(request: HttpRequest) -> HttpResponse:
    participant = get_recording_participant(request)
    if not participant.consent_given:
        return HttpResponseForbidden("Consent required")

    session_stamp = request.POST.get("session_stamp")
    if not session_stamp:
        return JsonResponse({"ok": False, "error": "Missing session_stamp"}, status=400)

    webm_relative_path = f"tmp_recordings/screen-{participant.id}-{session_stamp}.webm"
    mp4_relative_path = f"screen_clips/screen-{participant.id}-{session_stamp}.mp4"
    converted_path = convert_webm_to_mp4(webm_relative_path, mp4_relative_path)
    if not converted_path:
        return JsonResponse({"ok": False, "error": "Conversion failed"}, status=500)

    remove_stale_partial_file(mp4_relative_path)
    ScreenClip.objects.get_or_create(participant=participant, clip=converted_path)

    webm_path = Path(settings.MEDIA_ROOT) / webm_relative_path
    if webm_path.exists():
        webm_path.unlink()

    return JsonResponse({"ok": True, "file": converted_path})


@require_http_methods(["GET", "POST"])
def paas_evaluation_view(request: HttpRequest, task_number: int) -> HttpResponse:
    participant = get_or_create_participant(request)
    onboarding_redirect = get_onboarding_redirect(participant, request)
    if onboarding_redirect:
        return redirect(onboarding_redirect)

    if PaasResponse.objects.filter(participant=participant, task_number=task_number).exists():
        return redirect("survey_app:next_task")

    if request.method == "POST":
        rating = request.POST.get("paas_rating")
        if rating and rating.isdigit() and 1 <= int(rating) <= 9:
            PaasResponse.objects.update_or_create(
                participant=participant,
                task_number=task_number,
                defaults={"rating": int(rating)}
            )
            
            return redirect("survey_app:next_task")
            
        else:
            return render(
                request, 
                "survey_app/paas_evaluation.html", 
                {
                    "task_number": task_number,
                    "error_message": "Please select a mental effort rating from 1 to 9.",
                    "record_webcam": True,
                }
            )

    return render(
        request, 
        "survey_app/paas_evaluation.html", 
        {
            "task_number": task_number,
            "record_webcam": True,
        }
    )
