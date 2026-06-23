import uuid
from django.db import models
from django.contrib.auth.models import User, Group

class ParticipantSession(models.Model):
    session_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    
    participant_tag = models.CharField(max_length=64, blank=True)
    consent_given = models.BooleanField(default=False)
    consented_at = models.DateTimeField(null=True, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    profession = models.CharField(max_length=255, blank=True)
    education_level = models.CharField(max_length=64, blank=True)
    gender = models.CharField(max_length=64, blank=True)
    reads_words_daily = models.CharField(max_length=64, blank=True)
    reads_news_daily = models.BooleanField(null=True, blank=True)
    movies_per_week = models.CharField(max_length=64, blank=True)
    picture_statement_agreement = models.CharField(max_length=32, blank=True)
    demographics_completed_at = models.DateTimeField(null=True, blank=True)
    reading_habits_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expertise_sentiment = models.PositiveSmallIntegerField(null=True, blank=True)
    expertise_fakenews = models.PositiveSmallIntegerField(null=True, blank=True)
    expertise_visualisation = models.PositiveSmallIntegerField(null=True, blank=True)
    expertise_completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user.username if self.user else 'Anon'} - {self.session_uuid}"

class Movie(models.Model):
    imdb_id = models.CharField(max_length=16, unique=True)
    target_groups = models.ManyToManyField(Group, related_name='targeted_movies', blank=True)
    title = models.CharField(max_length=200)
    year = models.PositiveIntegerField()
    genre = models.CharField(max_length=120)
    poster_url = models.URLField(blank=True)
    description = models.TextField()

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return f"{self.title} ({self.year})"


class Review(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="reviews")
    source = models.CharField(max_length=50, default="SST")
    sentiment = models.CharField(max_length=12, default="neutral")
    text = models.TextField()


class MovieSelection(models.Model):
    participant = models.ForeignKey(
        ParticipantSession,
        on_delete=models.CASCADE,
        related_name="selections",
    )
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    selected_at = models.DateTimeField(auto_now_add=True)


class WebcamClip(models.Model):
    participant = models.ForeignKey(
        ParticipantSession,
        on_delete=models.CASCADE,
        related_name="webcam_clips",
    )
    clip = models.FileField(upload_to="webcam_clips/")
    created_at = models.DateTimeField(auto_now_add=True)


class ScreenClip(models.Model):
    participant = models.ForeignKey(
        ParticipantSession,
        on_delete=models.CASCADE,
        related_name="screen_clips",
    )
    clip = models.FileField(upload_to="screen_clips/")
    created_at = models.DateTimeField(auto_now_add=True)


class MovieReviewResponse(models.Model):
    participant = models.ForeignKey(
        ParticipantSession,
        on_delete=models.CASCADE,
        related_name="movie_review_responses",
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    review_text = models.TextField(blank=True)
    sentiment_choice = models.CharField(max_length=12)
    rating_choice = models.DecimalField(max_digits=2, decimal_places=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "movie"],
                name="unique_movie_response_per_participant",
            )
        ]


class NewsArticle(models.Model):
    slug = models.SlugField(unique=True)
    target_groups = models.ManyToManyField(Group, related_name='targeted_news', blank=True)
    headline = models.CharField(max_length=255)
    source = models.CharField(max_length=120)
    summary = models.TextField()
    body = models.TextField()
    is_fake = models.BooleanField(default=False)

    class Meta:
        ordering = ["headline"]

    def __str__(self) -> str:
        return self.headline


class NewsArticleResponse(models.Model):
    participant = models.ForeignKey(
        ParticipantSession,
        on_delete=models.CASCADE,
        related_name="news_article_responses",
    )
    article = models.ForeignKey(
        NewsArticle,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    classification_choice = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "article"],
                name="unique_news_response_per_participant",
            )
        ]


class NetworkDiagram(models.Model):
    slug = models.SlugField(unique=True)
    type = models.CharField(max_length=20)
    target_groups = models.ManyToManyField(Group, related_name='targeted_diagrams', blank=True)
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=255)
    context = models.TextField()
    image_url = models.URLField(blank=True)
    image_alt = models.CharField(max_length=255, blank=True)
    image_source_label = models.CharField(max_length=255, blank=True)
    image_source_url = models.URLField(blank=True)
    nodes = models.JSONField(default=list)
    edges = models.JSONField(default=list)
    question_one = models.CharField(max_length=255)
    question_one_options = models.JSONField(default=list)
    question_two = models.CharField(max_length=255)
    question_two_options = models.JSONField(default=list)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self) -> str:
        return self.title


class NetworkDiagramResponse(models.Model):
    participant = models.ForeignKey(
        ParticipantSession,
        on_delete=models.CASCADE,
        related_name="network_diagram_responses",
    )
    diagram = models.ForeignKey(
        NetworkDiagram,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    answer_one = models.CharField(max_length=255)
    answer_two = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "diagram"],
                name="unique_network_response_per_participant",
            )
        ]

class PaasResponse(models.Model):
    participant = models.ForeignKey(
        ParticipantSession, 
        on_delete=models.CASCADE, 
        related_name="paas_responses"
    )
    task_number = models.PositiveSmallIntegerField() # 1=Movies, 2=News, 3=Networks
    rating = models.PositiveSmallIntegerField()
    # Per-item relative difficulty ratings for this task, e.g.
    # {"movie:14": 2, "movie:9": 1, "movie:22": 3}
    # Keys are "<item_type>:<item_id>", values are 1 (Easy), 2 (Moderate), or 3 (Difficult).
    item_difficulty_ratings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "task_number"],
                name="unique_paas_per_task_participant",
            )
        ]