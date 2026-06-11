from django.urls import path

from . import views

app_name = "survey_app"

urlpatterns = [
    path("", views.login_view, name="welcome"),
    path("consent/", views.consent_view, name="consent"),
    path("demographics/", views.demographics_view, name="demographics"),
    path("reading-habits/", views.reading_habits_view, name="habits"),
    path("media-preferences/", views.media_preferences_view, name="media_preferences"),
    path("expertise/", views.expertise_rating_view, name="expertise_rating"),
    path("capture-session/", views.capture_session_view, name="capture_session"),
    path("movies/", views.carousel_view, name="carousel"),
    path("movies/<int:movie_id>/", views.movie_detail_view, name="movie_detail"),
    path("movies/<int:movie_id>/questions/", views.movie_questions_view, name="movie_questions"),
    path("news/", views.news_carousel_view, name="news_carousel"),
    path("news/<int:article_id>/", views.news_detail_view, name="news_detail"),
    path("news/<int:article_id>/questions/", views.news_questions_view, name="news_questions"),
    path("networks/", views.network_carousel_view, name="network_carousel"),
    path("networks/<int:diagram_id>/", views.network_detail_view, name="network_detail"),
    path("networks/<int:diagram_id>/questions/", views.network_questions_view, name="network_questions"),
    path("next-task/", views.next_task_view, name="next_task"),
    path("thank-you/", views.thank_you_view, name="thank_you"),
    path("api/movies/<int:movie_id>/select/", views.select_movie, name="select_movie"),
    path("api/movies/<int:movie_id>/reviews/", views.movie_reviews_api, name="movie_reviews_api"),
    path("api/movies/<int:movie_id>/response/", views.submit_movie_response, name="submit_movie_response"),
    path("api/webcam/upload/", views.upload_webcam_clip, name="upload_webcam_clip"),
    path("api/webcam/finalize/", views.finalize_webcam_clip, name="finalize_webcam_clip"),
    path("api/screen/upload/", views.upload_screen_clip, name="upload_screen_clip"),
    path("api/screen/finalize/", views.finalize_screen_clip, name="finalize_screen_clip"),
    path("paas/<int:task_number>/", views.paas_evaluation_view, name="paas_evaluation"),
]
