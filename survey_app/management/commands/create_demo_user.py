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

import re
from pathlib import Path

import pytreebank
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


# ── PYTREEBANK-SOURCED DEMO REVIEW EXCERPTS ───────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
SST_PATH = BASE_DIR / "data" / "stanford_sentiment_treebank"
MAX_DEMO_REVIEW_WORDS = 150
MIN_DEMO_REVIEW_WORDS = 12
DEMO_MIN_SENTENCES = 2
DEMO_MAX_SENTENCES = 3
DEMO_TARGET_MIN_WORDS = 100


def _normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        " n't": "n't", " 's": "'s", " 're": "'re", " 've": "'ve",
        " 'm": "'m", " 'd": "'d", " 'll": "'ll", " ,": ",", " .": ".",
        " !": "!", " ?": "?", " ;": ";", " :": ":", "( ": "(", " )": ")",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _is_complete_sentence(text: str) -> bool:
    return text.endswith((".", "!", "?", ".'", "!'", "?'", "''"))


def load_demo_review_pool() -> dict[str, list[str]]:
    """
    Load single, complete SST sentences (not stitched excerpts), bucketed
    by sentiment, each at most MAX_DEMO_REVIEW_WORDS words long.
    """
    dataset = pytreebank.load_sst(path=str(SST_PATH))
    pools = {"positive": [], "neutral": [], "negative": []}

    for split_name in ("train", "dev", "test"):
        for tree in dataset[split_name]:
            text = _normalize_text(tree.to_lines()[0])
            word_count = len(text.split())

            if word_count < MIN_DEMO_REVIEW_WORDS or word_count > MAX_DEMO_REVIEW_WORDS:
                continue
            if text.startswith("..."):
                continue
            if not _is_complete_sentence(text):
                continue

            if tree.label >= 3:
                sentiment = "positive"
            elif tree.label == 2:
                sentiment = "neutral"
            else:
                sentiment = "negative"

            if text not in pools[sentiment]:
                pools[sentiment].append(text)

            if all(len(pools[s]) >= 25 for s in pools):
                return pools

    return pools


def build_demo_paragraph(sentences: list[str]) -> str:
    """Join consecutive same-sentiment sentences into one flowing paragraph."""
    return " ".join(sentences)


def pick_demo_review(
    pool: dict[str, list[str]], sentiment: str, start_index: int
) -> tuple[dict, int]:
    """
    Build a single review paragraph by concatenating 2-3 sentences of the
    given sentiment, so the demo review reads as one excerpt with enough
    length to fill the review box, while staying under MAX_DEMO_REVIEW_WORDS.
    Returns (review_dict, next_start_index) so repeated calls advance
    through the pool without reusing the same sentences twice.
    """
    candidates = sorted(pool[sentiment], key=len, reverse=True)
    if not candidates:
        raise ValueError(
            f"create_demo_user: no '{sentiment}' excerpts available. "
            f"Widen MIN_DEMO_REVIEW_WORDS or check the SST dataset path."
        )

    idx = start_index
    chosen: list[str] = []
    word_total = 0

    while idx < start_index + len(candidates) and len(chosen) < DEMO_MAX_SENTENCES:
        candidate = candidates[idx % len(candidates)]
        idx += 1
        candidate_words = len(candidate.split())

        if (
            len(chosen) >= DEMO_MIN_SENTENCES
            and word_total + candidate_words > MAX_DEMO_REVIEW_WORDS
        ):
            break

        if candidate in chosen:
            continue

        chosen.append(candidate)
        word_total += candidate_words

        if len(chosen) >= DEMO_MIN_SENTENCES and word_total >= DEMO_TARGET_MIN_WORDS:
            break

    if len(chosen) < DEMO_MIN_SENTENCES:
        raise ValueError(
            f"create_demo_user: could not gather {DEMO_MIN_SENTENCES} distinct "
            f"'{sentiment}' sentences (only found {len(chosen)}). "
            f"Widen MIN_DEMO_REVIEW_WORDS or lower DEMO_MIN_SENTENCES."
        )

    text = build_demo_paragraph(chosen)
    return {"sentiment": sentiment, "text": text}, idx


# ── DUMMY MOVIES ──────────────────────────────────────────────────────────────
# Each movie gets ONE pytreebank-sourced review excerpt (<=150 words).
# "review_sentiment" picks which sentiment bucket that excerpt comes from.

DEMO_MOVIES = [
    {
        "imdb_id": "demo_tt0001",
        "title": "Stellar Voyage",
        "year": 2021,
        "genre": "Sci-Fi, Adventure",
        "poster_url": "/static/survey_app/posters/stellar_voyage.svg",
        "description": "A crew of astronauts embark on a daring journey beyond the known solar system.",
        "review_sentiment": "positive",
    },
    {
        "imdb_id": "demo_tt0002",
        "title": "The Quiet Shore",
        "year": 2019,
        "genre": "Drama, Romance",
        "poster_url": "/static/survey_app/posters/the_quiet_shore.svg",
        "description": "Two strangers meet at a coastal village and uncover a shared past.",
        "review_sentiment": "neutral",
    },
    {
        "imdb_id": "demo_tt0003",
        "title": "Iron Verdict",
        "year": 2022,
        "genre": "Thriller, Crime",
        "poster_url": "/static/survey_app/posters/iron_verdict.svg",
        "description": "A defence attorney discovers her client may be hiding a dark secret.",
        "review_sentiment": "negative",
    },
    {
        "imdb_id": "demo_tt0004",
        "title": "Echoes of Tomorrow",
        "year": 2020,
        "genre": "Mystery, Drama",
        "poster_url": "/static/survey_app/posters/echoes_of_tomorrow.svg",
        "description": "A grieving musician begins receiving voice messages from a version of herself one year in the future.",
        "review_sentiment": "neutral",
    },
    {
        "imdb_id": "demo_tt0005",
        "title": "Burnout Boulevard",
        "year": 2023,
        "genre": "Comedy, Drama",
        "poster_url": "/static/survey_app/posters/burnout_boulevard.svg",
        "description": "A burnt-out city planner quits her job and accidentally becomes the spokesperson for a neighbourhood rebellion.",
        "review_sentiment": "positive",
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
        "order": "1",
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
        "order": "2",
        "title": "Demo Task B: Social Network",
        "type": "network",
        "context": "Answer the questions using the diagram",
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
        "order": "3",
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

        # ── 4. Seed demo movies (one pytreebank excerpt each, <=150 words) ───
        review_pool = load_demo_review_pool()
        sentiment_counters = {"positive": 0, "neutral": 0, "negative": 0}

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
            movie.target_groups.set([demo_group])

            sentiment = item["review_sentiment"]
            review, sentiment_counters[sentiment] = pick_demo_review(
                review_pool, sentiment, sentiment_counters[sentiment]
            )

            movie.reviews.all().delete()
            Review.objects.create(
                movie=movie,
                source="SST",
                sentiment=review["sentiment"],
                text=review["text"],
            )
            word_count = len(review["text"].split())
            self.stdout.write(
                f"  Seeded movie: {item['title']} [{sentiment}, {word_count} words]"
            )

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
            article.target_groups.set([demo_group])
            self.stdout.write(f"  Seeded article: {item['headline'][:50]}")

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
            diagram.target_groups.set([demo_group])
            self.stdout.write(f"  Seeded diagram: {item['title']}")

        self.stdout.write(self.style.SUCCESS(
            "\n✓ Demo setup complete!\n"
            "  Username: demo\n"
            "  Password: demo1234\n"
            "  Onboarding: pre-completed, goes straight to Task 1\n"
            "  Content: 5 movies, 3 articles, 3 diagrams (all Demo group only)\n"
        ))