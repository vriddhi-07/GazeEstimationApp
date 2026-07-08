from .models import ParticipantSession


def participant_progress(request):
    """
    Adds study_progress_completed / study_progress_total to every template's
    context, for the header progress bar. Runs on every request (that's how
    Django context processors work), so it has to degrade to {} quietly for
    anonymous users, admin/staff pages, or any request where the logged-in
    user doesn't have a ParticipantSession yet (nothing to show yet).

    Total is the same 3+3+3=9 minimum used elsewhere (MINIMUM_REQUIRED_*),
    not a hardcoded "9" — if those thresholds ever change, this follows.
    Completed count per task type is capped at that type's minimum, so a
    participant who somehow submits more than 3 in one category (e.g. a
    retry) doesn't show as more than 9/9.
    """
    if not request.user.is_authenticated:
        return {}

    participant = ParticipantSession.objects.filter(user=request.user).first()
    if not participant:
        return {}

    # Local import to avoid a circular import between views.py and here.
    from .views import (
        MINIMUM_REQUIRED_REVIEWS,
        MINIMUM_REQUIRED_NEWS_ARTICLES,
        MINIMUM_REQUIRED_NETWORK_DIAGRAMS,
    )

    movie_done = min(participant.movie_review_responses.count(), MINIMUM_REQUIRED_REVIEWS)
    news_done = min(participant.news_article_responses.count(), MINIMUM_REQUIRED_NEWS_ARTICLES)
    network_done = min(participant.network_diagram_responses.count(), MINIMUM_REQUIRED_NETWORK_DIAGRAMS)

    total = (
        MINIMUM_REQUIRED_REVIEWS
        + MINIMUM_REQUIRED_NEWS_ARTICLES
        + MINIMUM_REQUIRED_NETWORK_DIAGRAMS
    )
    completed = movie_done + news_done + network_done
    percent = round((completed / total) * 100) if total else 0

    return {
        "study_progress_completed": completed,
        "study_progress_total": total,
        "study_progress_percent": percent,
    }