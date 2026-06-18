"""
Management command to create a demo participant account with dummy content
for walkthrough video purposes.

Usage:
    python manage.py create_demo_user

This creates:
- A Django user with username "demo" and password "demo1234"
- A "Demo" group with 3 dummy movies, 3 dummy news articles, 3 dummy diagrams
- A ParticipantSession with all onboarding already completed
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.utils import timezone
from survey_app.models import (
    ParticipantSession,
    Movie,
    Review,
    NewsArticle,
    NetworkDiagram,
)


# ── DUMMY MOVIES ──────────────────────────────────────────────────────────────

DEMO_MOVIES = [
    {
        "imdb_id": "demo_tt0001",
        "title": "Stellar Voyage",
        "year": 2021,
        "genre": "Sci-Fi, Adventure",
        "poster_url": "/static/survey_app/posters/fallback.svg",
        "description": "A crew of astronauts embark on a daring journey beyond the known solar system.",
        "reviews": [
            {
                "sentiment": "positive",
                "text": (
                    'Review excerpt 1: "A breathtaking ride through the cosmos that leaves you '
                    'speechless and inspired." '
                    'Review excerpt 2: "The visual effects are nothing short of spectacular, '
                    'anchored by a deeply human story about courage and sacrifice."'
                ),
            },
            {
                "sentiment": "negative",
                "text": (
                    'Review excerpt 1: "Despite its ambitions, the film stumbles with a '
                    'predictable plot and underdeveloped characters." '
                    'Review excerpt 2: "The third act falls apart under the weight of its own '
                    'sci-fi jargon, leaving audiences more confused than moved."'
                ),
            },
        ],
    },
    {
        "imdb_id": "demo_tt0002",
        "title": "The Quiet Shore",
        "year": 2019,
        "genre": "Drama, Romance",
        "poster_url": "/static/survey_app/posters/fallback.svg",
        "description": "Two strangers meet at a coastal village and uncover a shared past.",
        "reviews": [
            {
                "sentiment": "positive",
                "text": (
                    'Review excerpt 1: "A tender and quietly devastating film that lingers '
                    'long after the credits roll." '
                    'Review excerpt 2: "The performances are understated yet powerful, '
                    'making every small moment feel profound and real."'
                ),
            },
            {
                "sentiment": "neutral",
                "text": (
                    'Review excerpt 1: "A pleasant watch that neither surprises nor '
                    'disappoints, offering solid performances and gentle pacing." '
                    'Review excerpt 2: "The story is familiar but told with enough warmth '
                    'to keep you engaged through its modest runtime."'
                ),
            },
        ],
    },
    {
        "imdb_id": "demo_tt0003",
        "title": "Iron Verdict",
        "year": 2022,
        "genre": "Thriller, Crime",
        "poster_url": "/static/survey_app/posters/fallback.svg",
        "description": "A defence attorney discovers her client may be hiding a dark secret.",
        "reviews": [
            {
                "sentiment": "positive",
                "text": (
                    'Review excerpt 1: "A gripping courtroom thriller that keeps you '
                    'guessing right up to the final scene." '
                    'Review excerpt 2: "Sharp writing and a powerhouse lead performance '
                    'make this one of the best legal dramas in recent memory."'
                ),
            },
            {
                "sentiment": "negative",
                "text": (
                    'Review excerpt 1: "The twists feel manufactured rather than earned, '
                    'and the villain is telegraphed far too early." '
                    'Review excerpt 2: "A disappointingly hollow thriller that mistakes '
                    'frantic pacing for genuine tension."'
                ),
            },
        ],
    },
    {
        "imdb_id": "demo_tt0004",
        "title": "Echoes of Tomorrow",
        "year": 2020,
        "genre": "Mystery, Drama",
        "poster_url": "/static/survey_app/posters/fallback.svg",
        "description": "A grieving musician begins receiving voice messages from a version of herself one year in the future.",
        "reviews": [
            {
                "sentiment": "positive",
                "text": (
                    'Review excerpt 1: "A haunting and emotionally rich mystery that rewards '
                    'patient viewers with a deeply satisfying resolution." '
                    'Review excerpt 2: "The lead performance is extraordinary, carrying the '
                    'film through its more demanding emotional stretches with quiet authority."'
                ),
            },
            {
                "sentiment": "neutral",
                "text": (
                    'Review excerpt 1: "An intriguing premise that is only partially realised, '
                    'though the central performance keeps it compelling throughout." '
                    'Review excerpt 2: "The pacing drags in the second act but the film '
                    'recovers well enough to leave a lasting impression."'
                ),
            },
        ],
    },
    {
        "imdb_id": "demo_tt0005",
        "title": "Burnout Boulevard",
        "year": 2023,
        "genre": "Comedy, Drama",
        "poster_url": "/static/survey_app/posters/fallback.svg",
        "description": "A burnt-out city planner quits her job and accidentally becomes the spokesperson for a neighbourhood rebellion.",
        "reviews": [
            {
                "sentiment": "positive",
                "text": (
                    'Review excerpt 1: "A sharp and surprisingly warm comedy that finds '
                    'real heart beneath its satirical surface." '
                    'Review excerpt 2: "Witty, well-paced, and anchored by a magnetic '
                    'lead performance that makes even the broadest jokes land."'
                ),
            },
            {
                "sentiment": "negative",
                "text": (
                    'Review excerpt 1: "The film mistakes busyness for energy, cramming '
                    'in too many subplots at the expense of its most interesting characters." '
                    'Review excerpt 2: "A promising setup that loses its nerve by the third '
                    'act, settling for easy resolutions where genuine conflict was needed."'
                ),
            },
        ],
    },
]


# ── DUMMY NEWS ARTICLES ───────────────────────────────────────────────────────

DEMO_ARTICLES = [
    {
        "slug": "demo-article-local-park-renovation",
        "headline": "City Council Approves Renovation of Central Park Facilities",
        "source": "Demo News",
        "summary": "The city council voted unanimously to approve a budget for renovating park facilities.",
        "body": (
            "The city council voted unanimously on Tuesday to approve a $2.4 million budget "
            "for the renovation of Central Park's aging facilities. The project, which is "
            "expected to begin next spring, will include new playground equipment, upgraded "
            "restrooms, and improved walking trails. Mayor Linda Howell called the decision "
            "a long overdue investment in the community. Residents who attended the public "
            "hearing expressed overwhelming support for the initiative, citing safety concerns "
            "about the current infrastructure. The renovation is expected to be completed "
            "within 18 months, with minimal disruption to daily park activities. Local "
            "contractors will be given priority in the bidding process, according to a "
            "statement released by the council."
        ),
        "is_fake": False,
    },
    {
        "slug": "demo-article-scientists-coffee-discovery",
        "headline": "Scientists Discover That Coffee Consumption Triples Athletic Performance",
        "source": "Demo Health Wire",
        "summary": "A new study claims coffee triples athletic performance in all sports.",
        "body": (
            "A new study published this week in the Journal of Nutritional Enhancement claims "
            "that drinking three cups of coffee per day can triple an athlete's performance "
            "across all sports including swimming, weightlifting, and long-distance running. "
            "The researchers, based at an unnamed university, reportedly tested 12 volunteers "
            "over a single weekend. Critics have already questioned the methodology, noting "
            "that the sample size is far too small and the timeframe too short to draw any "
            "meaningful conclusions. Dr. Patricia Yuen, a sports nutritionist not affiliated "
            "with the study, called the claims 'wildly overstated and potentially misleading.' "
            "Nevertheless, the article has been widely shared on social media, with many "
            "users accepting the findings at face value without reading beyond the headline."
        ),
        "is_fake": True,
    },
    {
        "slug": "demo-article-renewable-energy-milestone",
        "headline": "India Reaches 100 GW Solar Energy Milestone Ahead of Schedule",
        "source": "Demo Energy Times",
        "summary": "India has achieved its 100 GW solar capacity target two years ahead of schedule.",
        "body": (
            "India has officially crossed the 100 gigawatt mark in installed solar energy "
            "capacity, reaching the milestone nearly two years ahead of its original target. "
            "The Ministry of New and Renewable Energy announced the achievement on Wednesday, "
            "calling it a testament to the country's accelerating clean energy transition. "
            "The milestone was reached following the commissioning of a large solar park in "
            "Rajasthan, which added 2.8 GW to the national grid. India is now among the top "
            "five countries globally in terms of solar installed capacity. The government has "
            "set an ambitious new target of 500 GW of renewable energy by 2030, which would "
            "require significant investment in grid infrastructure and storage technology. "
            "Industry analysts say the pace of growth has exceeded even the most optimistic "
            "projections from five years ago."
        ),
        "is_fake": False,
    },
]


# ── DUMMY NETWORK DIAGRAMS ────────────────────────────────────────────────────

DEMO_DIAGRAMS = [
    {
        "slug": "demo-task-a-wordcloud",
        "title": "Demo Task A: Finance Word Cloud",
        "type": "wordcloud",
        "context": "Answer the questions using the word cloud",
        "image_url": "/static/survey_app/images/demowordcloud.jpg",
        "image_alt": "Finance Word Cloud",
        "image_source_label": "",
        "image_source_url": "",
        "image_fit": "contain",
        "image_position": "center center",
        "image_scale": "100%",
        "nodes": [],
        "edges": [],
        "question_one": "What is the dominant theme of this word cloud?",
        "question_one_options": ["Sports", "Finance", "Health", "Technology"],
        "question_two": "Which currency is explicitly mentioned in the word cloud?",
        "question_two_options": ["Dollar", "Pound", "Yen", "Rupee"],
    },
    {
        "slug": "demo-task-b-network",
        "title": "Demo Task B: Social Network",
        "type": "network",
        "context": "YOUR CONTEXT INSTRUCTION HERE",
        "image_url": "/static/survey_app/images/demonwdiagram.png",
        "image_alt": "Social Network Diagram",
        "image_source_label": "",
        "image_source_url": "",
        "image_fit": "contain",
        "image_position": "center center",
        "image_scale": "100%",
        "nodes": [],
        "edges": [],
        "question_one": "Who is connected to the most number of people in the network?",
        "question_one_options": ["Anne", "Bob", "Elisa", "Carl"],
        "question_two": "Which 2 people have no direct connection between each other?",
        "question_two_options": ["Anne and Bob", "Elisa and Carl", "Bob and Diana", "Anne and Elisa"],
    },
    {
        "slug": "demo-task-c-metromap",
        "title": "Demo Task C: Metro Map",
        "type": "metromap",
        "context": "Answer the questions using the map",
        "image_url": "/static/survey_app/images/demometromap.png",
        "image_alt": "Tashkent Metro Map",
        "image_source_label": "",
        "image_source_url": "",
        "image_fit": "contain",
        "image_position": "center center",
        "image_scale": "100%",
        "nodes": [],
        "edges": [],
        "question_one": "From Sobir Rhimov to Habib Abdullayev, what is the minimum number of interchanges to be made?",
        "question_one_options": ["One", "Two", "Three", "Four"],
        "question_two": "How many interchange stations are there?",
        "question_two_options": ["One", "Two", "Three", "Four"],
    },
]


class Command(BaseCommand):
    help = "Create a demo user and seed dummy content for walkthrough video"

    def handle(self, *args, **options):
        # ── 1. Create Demo group ──────────────────────────────────────────────
        demo_group, created = Group.objects.get_or_create(name="Demo")
        self.stdout.write(f"{'Created' if created else 'Found'} group: Demo")

        # ── 2. Create demo user ───────────────────────────────────────────────
        user, created = User.objects.get_or_create(username="demo")
        if created:
            user.set_password("demo1234")
            user.save()
            self.stdout.write("Created user: demo / demo1234")
        else:
            self.stdout.write("Found existing user: demo")
        user.groups.add(demo_group)

        # ── 3. Create or reset ParticipantSession with onboarding complete ───
        ParticipantSession.objects.filter(user=user).delete()
        old_sessions = ParticipantSession.objects.filter(user=user)
        for old in old_sessions:
            old.movie_review_responses.all().delete()
            old.news_article_responses.all().delete()
            old.network_diagram_responses.all().delete()
            old.paas_responses.all().delete()
        old_sessions.delete()
        participant = ParticipantSession.objects.create(
            user=user,
        )
        self.stdout.write("Created demo user")

        # ── 4. Seed demo movies ───────────────────────────────────────────────
        for item in DEMO_MOVIES:
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
            movie.target_groups.add(demo_group)
            movie.reviews.all().delete()
            Review.objects.bulk_create([
                Review(
                    movie=movie,
                    source="DEMO",
                    sentiment=r["sentiment"],
                    text=r["text"],
                )
                for r in item["reviews"]
            ])
            self.stdout.write(f"  Seeded movie: {item['title']}")

        # ── 5. Seed demo news articles ────────────────────────────────────────
        for item in DEMO_ARTICLES:
            article, _ = NewsArticle.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "headline": item["headline"],
                    "source": item["source"],
                    "summary": item["summary"],
                    "body": item["body"],
                    "is_fake": item["is_fake"],
                },
            )
            article.target_groups.add(demo_group)
            self.stdout.write(f"  Seeded article: {item['headline'][:50]}")

        # ── 6. Seed demo network diagrams ─────────────────────────────────────
        # ── 6. Seed demo network diagrams ─────────────────────────────────────
        # Remove any old demo diagrams whose slugs have changed
        current_slugs = {item["slug"] for item in DEMO_DIAGRAMS}
        NetworkDiagram.objects.filter(slug__startswith="demo-").exclude(
            slug__in=current_slugs
        ).delete()
        for item in DEMO_DIAGRAMS:
            diagram, _ = NetworkDiagram.objects.update_or_create(
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
            diagram.target_groups.add(demo_group)
            self.stdout.write(f"  Seeded diagram: {item['title']}")

        self.stdout.write(self.style.SUCCESS(
            "\n✓ Demo setup complete!\n"
            "  Username: demo\n"
            "  Password: demo1234\n"
            "  Onboarding: pre-completed, goes straight to Task 1\n"
            "  Content: 3 movies, 3 articles, 3 diagrams (all Demo group only)\n"
        ))