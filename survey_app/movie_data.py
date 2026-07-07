import csv
import random
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REVIEWS_CSV_PATH = BASE_DIR / "data" / "jumr_reviews.csv"

MAX_REVIEW_WORDS = 150

# Map raw "Overall Sentiment" CSV values to our sentiment labels.
SENTIMENT_CODE_MAP = {
    "1": "positive",
    "0": "neutral",
    "-1": "negative",
}

# Matches emoji and other pictographic symbols so they can be stripped
# from review text before it's shown to participants.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols & pictographs, supplemental symbols
    "\U00002600-\U000027BF"  # misc symbols, dingbats
    "\U0001F1E6-\U0001F1FF"  # flags
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\U00002B00-\U00002BFF"
    "\U0001FA70-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)


def strip_emojis(text: str) -> str:
    cleaned = _EMOJI_PATTERN.sub("", text)
    # Collapse any double spaces left behind after removing emojis.
    return re.sub(r"\s{2,}", " ", cleaned).strip()


# Some IMDb-style reviews append a trailing "Guide: ..." parental content
# note (profanity/violence/sex-and-nudity call-outs) after the reviewer's
# actual opinion — not part of the review itself, and not something we
# want participants reading mid-study. e.g.:
#   "...Needed to be shorter.Guide: F-word. No sex or nudity."
#   "...Guide: No sex or nudity. 2 F-bombs for the kids. Thank you..."
_CONTENT_GUIDE_PATTERN = re.compile(r"\s*Guide:.*$", flags=re.IGNORECASE)


def strip_content_guide_note(text: str) -> str:
    cleaned = _CONTENT_GUIDE_PATTERN.sub("", text)
    return re.sub(r"\s{2,}", " ", cleaned).strip()

MOVIE_METADATA = [
    # --- SET 1 (Users 1, 2, 3, 4) ---
    {
        "csv_name": "Interstellar",
        "target_sentiment": "positive",
        "imdb_id": "tt0816692",
        "set_group": 1,
        "title": "Interstellar",
        "year": 2014,
        "genre": "Adventure, Drama, Sci-Fi",
        "poster_url": "/static/survey_app/posters/interstellar.svg",
        "description": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
    },
    {
        "csv_name": "Avengers: Endgame",
        "target_sentiment": "neutral",
        "imdb_id": "tt4154796",
        "set_group": 1,
        "title": "Avengers: Endgame",
        "year": 2019,
        "genre": "Action, Adventure, Drama",
        "poster_url": "/static/survey_app/posters/avengers_endgame.svg",
        "description": "After the devastating events of Infinity War, the remaining Avengers assemble once more to undo Thanos's actions and restore order to the universe.",
    },
    {
        "csv_name": "Die Hard",
        "target_sentiment": "neutral",
        "imdb_id": "tt0095016",
        "set_group": 1,
        "title": "Die Hard",
        "year": 1988,
        "genre": "Action, Thriller",
        "poster_url": "/static/survey_app/posters/die_hard.svg",
        "description": "An NYPD officer tries to save his wife and several others taken hostage by terrorists during a Christmas party at the Nakatomi Plaza in Los Angeles.",
    },
    {
        "csv_name": "Star Wars",
        "target_sentiment": "positive",
        "imdb_id": "tt0076759",
        "set_group": 1,
        "title": "Star Wars",
        "year": 1977,
        "genre": "Action, Adventure, Fantasy",
        "poster_url": "/static/survey_app/posters/star_wars.svg",
        "description": "Luke Skywalker joins forces with a Jedi Knight, a cocky pilot, a Wookiee and two droids to save the galaxy from the Empire's world-destroying battle station.",
    },
    {
        "csv_name": "Wonder Woman 1984",
        "target_sentiment": "neutral",
        "imdb_id": "tt7126948",
        "set_group": 1,
        "title": "Wonder Woman 1984",
        "year": 2020,
        "genre": "Action, Adventure, Fantasy",
        "poster_url": "/static/survey_app/posters/wonder_woman.svg",
        "description": "Diana must contend with a work colleague and businessman, whose desire for unlimited power leads him on a global rampage, and a mysterious villain.",
    },

    # --- SET 2 (Users 5, 6, 7, 8) ---
    {
        "csv_name": "Tenet",
        "target_sentiment": "neutral",
        "imdb_id": "tt6723592",
        "set_group": 2,
        "title": "Tenet",
        "year": 2020,
        "genre": "Action, Sci-Fi, Thriller",
        "poster_url": "/static/survey_app/posters/tenet.svg",
        "description": "A secret agent embarks on a dangerous, time-bending mission to prevent a global catastrophe by manipulating the flow of time itself.",
    },
    {
        "csv_name": "Ma Rainey's Black Bottom",
        "target_sentiment": "neutral",
        "imdb_id": "tt10545296",
        "set_group": 2,
        "title": "Ma Rainey's Black Bottom",
        "year": 2020,
        "genre": "Drama, Music",
        "poster_url": "/static/survey_app/posters/ma_raineys_black_bottom.svg",
        "description": "Tensions and temperatures rise during a 1920s recording session in Chicago as a band waits for their iconic singer to arrive.",
    },
    {
        "csv_name": "It's a Wonderful Life",
        "target_sentiment": "neutral",
        "imdb_id": "tt0038650",
        "set_group": 2,
        "title": "It's a Wonderful Life",
        "year": 1946,
        "genre": "Drama, Family, Fantasy",
        "poster_url": "/static/survey_app/posters/its_a_wonderful_life.svg",
        "description": "An angel is sent from heaven to help a desperately frustrated businessman by showing him what life would have been like if he had never existed.",
    },
    {
        "csv_name": "The Sound of Music",
        "target_sentiment": "negative",
        "imdb_id": "tt0059742",
        "set_group": 2,
        "title": "The Sound of Music",
        "year": 1965,
        "genre": "Biography, Drama, Family",
        "poster_url": "/static/survey_app/posters/the_sound_of_music.svg",
        "description": "A young woman who has trained to be a governess in 1930s Austria comes to the von Trapp family, a widower and his seven children.",
    },
    {
        "csv_name": "Promising Young Woman",
        "target_sentiment": "neutral",
        "imdb_id": "tt9620292",
        "set_group": 2,
        "title": "Promising Young Woman",
        "year": 2020,
        "genre": "Crime, Drama, Mystery",
        "poster_url": "/static/survey_app/posters/promising_young_woman.svg",
        "description": "A woman, haunted by a tragic event in her past, takes revenge against the men who cross her path.",
    },

    # --- SET 3 (Users 9, 10, 11, 12) ---
    {
        "csv_name": "Soul",
        "target_sentiment": "neutral",
        "imdb_id": "tt2948372",
        "set_group": 3,
        "title": "Soul",
        "year": 2020,
        "genre": "Animation, Adventure, Comedy",
        "poster_url": "/static/survey_app/posters/soul.svg",
        "description": "After landing the gig of a lifetime, a jazz pianist suddenly finds himself trapped in a strange land between Earth and the afterlife.",
    },
    {
        "csv_name": "Palm Springs",
        "target_sentiment": "positive",
        "imdb_id": "tt8016756",
        "set_group": 3,
        "title": "Palm Springs",
        "year": 2020,
        "genre": "Comedy, Fantasy, Romance",
        "poster_url": "/static/survey_app/posters/palm_springs.svg",
        "description": "Two wedding guests get stuck in a time loop together, repeating the same day over and over, and forming an unexpected bond.",
    },
    {
        "csv_name": "Sylvie's Love",
        "target_sentiment": "negative",
        "imdb_id": "tt9559338",
        "set_group": 3,
        "title": "Sylvie's Love",
        "year": 2020,
        "genre": "Drama, Music, Romance",
        "poster_url": "/static/survey_app/posters/sylvies_love.svg",
        "description": "In 1950s New York, a savvy and ambitious woman falls in love with a saxophonist, igniting a passion that lasts through marriages, career aspirations, and parenthood.",
    },
    {
        "csv_name": "Home Alone",
        "target_sentiment": "negative",
        "imdb_id": "tt0099785",
        "set_group": 3,
        "title": "Home Alone",
        "year": 1990,
        "genre": "Comedy, Family",
        "poster_url": "/static/survey_app/posters/home_alone.svg",
        "description": "An eight-year-old troublemaker, mistakenly left home alone, must defend his house against a pair of burglars on Christmas Eve.",
    },
    {
        "csv_name": "Elf",
        "target_sentiment": "positive",
        "imdb_id": "tt0319343",
        "set_group": 3,
        "title": "Elf",
        "year": 2003,
        "genre": "Comedy, Family, Fantasy",
        "poster_url": "/static/survey_app/posters/elf.svg",
        "description": "Raised as an elf at the North Pole, a human travels to New York City to meet his biological father and discover his true identity.",
    },
]


def load_reviews_by_movie() -> dict[str, list[dict]]:
    """
    Load the JUMR CSV and bucket reviews by movie name.
    Strips emojis and trailing "Guide: ..." content-rating notes from review
    text, then keeps only reviews that are MAX_REVIEW_WORDS words or fewer
    (measured after cleaning). Each entry is
    {"text": ..., "sentiment": ..., "word_count": ...}.
    """
    buckets: dict[str, list[dict]] = {}

    with open(REVIEWS_CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Name") or "").strip()
            review_text = (row.get("Review") or "").strip()
            sentiment_code = (row.get("Overall Sentiment") or "").strip()

            if not name or not review_text or sentiment_code not in SENTIMENT_CODE_MAP:
                continue

            review_text = strip_emojis(review_text)
            review_text = strip_content_guide_note(review_text)
            if not review_text:
                continue

            word_count = len(review_text.split())
            if word_count > MAX_REVIEW_WORDS:
                continue

            sentiment = SENTIMENT_CODE_MAP[sentiment_code]
            buckets.setdefault(name, [])
            buckets[name].append(
                {"text": review_text, "sentiment": sentiment, "word_count": word_count}
            )

    return buckets


def _validate_reviews(reviews_by_movie: dict[str, list[dict]]) -> None:
    """
    Confirm every movie in MOVIE_METADATA has at least one review matching
    its target_sentiment, at or under MAX_REVIEW_WORDS words. Raises a
    clear error immediately if not.
    """
    missing = []
    for metadata in MOVIE_METADATA:
        csv_name = metadata["csv_name"]
        target_sentiment = metadata["target_sentiment"]
        candidates = [
            c for c in reviews_by_movie.get(csv_name, [])
            if c["sentiment"] == target_sentiment
        ]
        if len(candidates) < 1:
            missing.append(
                f"{csv_name}: no '{target_sentiment}' review found at or under "
                f"{MAX_REVIEW_WORDS} words"
            )

    if missing:
        raise ValueError(
            "movie_data.py: cannot build MOVIES, missing review data:\n  "
            + "\n  ".join(missing)
        )


def build_movies(seed: int = 42) -> list[dict]:
    reviews_by_movie = load_reviews_by_movie()
    _validate_reviews(reviews_by_movie)

    rng = random.Random(seed)
    movies = []

    for metadata in MOVIE_METADATA:
        csv_name = metadata["csv_name"]
        target_sentiment = metadata["target_sentiment"]
        candidates = [
            c for c in reviews_by_movie[csv_name]
            if c["sentiment"] == target_sentiment
        ]

        # Pick the longest available review of the target sentiment at or
        # under MAX_REVIEW_WORDS, so each movie gets as full a review as
        # possible within the cap. Ties are broken deterministically using
        # the seeded RNG.
        max_word_count = max(c["word_count"] for c in candidates)
        longest_candidates = [c for c in candidates if c["word_count"] == max_word_count]
        chosen = rng.choice(longest_candidates)

        movie = {
            "imdb_id": metadata.get("imdb_id", ""),
            "set_group": metadata["set_group"],
            "title": metadata["title"],
            "year": metadata["year"],
            "genre": metadata["genre"],
            "poster_url": metadata["poster_url"],
            "description": metadata["description"],
            "review": {"sentiment": chosen["sentiment"], "text": chosen["text"]},
        }
        movies.append(movie)

    return movies


MOVIES = build_movies()