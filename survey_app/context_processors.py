from .models import ParticipantSession


# Pages before task 1 (the movie carousel) never show the progress bar,
# even for a returning/authenticated participant who already has responses
# recorded (e.g. revisits login after their session was reset, or a retry).
# This is enforced here rather than relying only on each pre-task template
# overriding {% block header_progress %} empty, since that's easy to miss
# and was the source of a real bug (bar showing on the login page with a
# stale, non-zero count). Keeping both is belt-and-suspenders, but this is
# the one that actually guarantees it regardless of the template state.
PRE_TASK_URL_NAMES = {
    "welcome",  # login page - url name is "welcome", see urls.py
    "consent",
    "demographics",
    "expertise_rating",
    "capture_session",
}


def participant_progress(request):
    """
    Adds study_progress_completed / study_progress_total to every template's
    context, for the header progress bar. Runs on every request (that's how
    Django context processors work), so it has to degrade to {} quietly for
    anonymous users, admin/staff pages, pre-task pages (login through
    capture-session — the bar only starts from the movie carousel onward),
    or any request where the logged-in user doesn't have a ParticipantSession
    yet (nothing to show yet).

    Total is the same 3+3+3=9 minimum used elsewhere (MINIMUM_REQUIRED_*),
    not a hardcoded "9" — if those thresholds ever change, this follows.
    Completed count per task type is capped at that type's minimum, so a
    participant who somehow submits more than 3 in one category (e.g. a
    retry) doesn't show as more than 9/9.
    """
    if not request.user.is_authenticated:
        return {}

    url_name = getattr(request.resolver_match, "url_name", None)
    if url_name in PRE_TASK_URL_NAMES:
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