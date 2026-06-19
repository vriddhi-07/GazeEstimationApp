from pathlib import Path
import re

import pytreebank


BASE_DIR = Path(__file__).resolve().parent.parent
SST_PATH = BASE_DIR / "data" / "stanford_sentiment_treebank"
MAX_WORDS = 150

MOVIE_METADATA = [
    # --- SET 1 (Users 1, 2, 3, 4) ---
    {
        "imdb_id": "tt0111161",
        "set_group": 1,
        "title": "The Shawshank Redemption",
        "year": 1994,
        "genre": "Drama",
        "poster_url": "/static/survey_app/posters/the_shawshank_redemption.svg",
        "description": "Two imprisoned men forge a friendship over years, finding hope and redemption through small acts of resistance.",
    },
    {
        "imdb_id": "tt0068646",
        "set_group": 1,
        "title": "The Godfather",
        "year": 1972,
        "genre": "Crime, Drama",
        "poster_url": "/static/survey_app/posters/the_godfather.svg",
        "description": "The aging patriarch of a crime family transfers control of his empire to his reluctant son.",
    },
    {
        "imdb_id": "tt0468569",
        "set_group": 1,
        "title": "The Dark Knight",
        "year": 2008,
        "genre": "Action, Crime, Drama",
        "poster_url": "/static/survey_app/posters/the_dark_knight.svg",
        "description": "Batman faces a chaotic adversary who pushes Gotham to the edge and tests the limits of justice.",
    },
    {
        "imdb_id": "tt0109830",
        "set_group": 1,
        "title": "Forrest Gump",
        "year": 1994,
        "genre": "Drama, Romance",
        "poster_url": "/static/survey_app/posters/forrest_gump.svg",
        "description": "A kind-hearted man experiences major moments of U.S. history while holding onto unwavering love and optimism.",
    },
    {
        "imdb_id": "tt0133093",
        "set_group": 1,
        "title": "The Matrix",
        "year": 1999,
        "genre": "Action, Sci-Fi",
        "poster_url": "/static/survey_app/posters/the_matrix.svg",
        "description": "A hacker discovers reality is a simulation and joins a rebellion against machine control.",
    },

    # --- SET 2 (Users 5, 6, 7, 8) ---
    {
        "imdb_id": "tt1285016",
        "set_group": 2,
        "title": "The Social Network",
        "year": 2010,
        "genre": "Biography, Drama",
        "poster_url": "/static/survey_app/posters/the_social_network.svg",
        "description": "Harvard student Mark Zuckerberg creates a social networking website that grows into a global phenomenon, but the friendships and lawsuits that follow change everything.",
    },
    {
        "imdb_id": "tt1375666",
        "set_group": 2,
        "title": "Inception",
        "year": 2010,
        "genre": "Action, Adventure, Sci-Fi",
        "poster_url": "/static/survey_app/posters/inception.svg",
        "description": "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea.",
    },
    {
        "imdb_id": "tt0110912",
        "set_group": 2,
        "title": "Pulp Fiction",
        "year": 1994,
        "genre": "Crime, Drama",
        "poster_url": "/static/survey_app/posters/pulp_fiction.svg",
        "description": "The lives of two mob hitmen, a boxer, a gangster, and his wife intertwine in four tales of violence and redemption.",
    },
    {
        "imdb_id": "tt0137523",
        "set_group": 2,
        "title": "Fight Club",
        "year": 1999,
        "genre": "Drama",
        "poster_url": "/static/survey_app/posters/fight_club.svg",
        "description": "An insomniac office worker and a devil-may-care soap maker form an underground fight club that evolves into much more.",
    },
    {
        "imdb_id": "tt0816692",
        "set_group": 2,
        "title": "Interstellar",
        "year": 2014,
        "genre": "Adventure, Drama, Sci-Fi",
        "poster_url": "/static/survey_app/posters/interstellar.svg",
        "description": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
    },

    # --- SET 3 (Users 9, 10, 11, 12) ---
    {
        "imdb_id": "tt0099685",
        "set_group": 3,
        "title": "Goodfellas",
        "year": 1990,
        "genre": "Biography, Crime, Drama",
        "poster_url": "/static/survey_app/posters/goodfellas.svg",
        "description": "The story of Henry Hill and his life in the mob, covering his relationship with his wife Karen Hill and his mob partners.",
    },
    {
        "imdb_id": "tt6751668",
        "set_group": 3,
        "title": "Parasite",
        "year": 2019,
        "genre": "Drama, Thriller",
        "poster_url": "/static/survey_app/posters/parasite.svg",
        "description": "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.",
    },
    {
        "imdb_id": "tt0172495",
        "set_group": 3,
        "title": "Gladiator",
        "year": 2000,
        "genre": "Action, Adventure, Drama",
        "poster_url": "/static/survey_app/posters/gladiator.svg",
        "description": "A former Roman General sets out to exact vengeance against the corrupt emperor who murdered his family and sent him into slavery.",
    },
    {
        "imdb_id": "tt0102926",
        "set_group": 3,
        "title": "The Silence of the Lambs",
        "year": 1991,
        "genre": "Crime, Drama, Thriller",
        "poster_url": "/static/survey_app/posters/the_silence_of_the_lambs.svg",
        "description": "A young F.B.I. cadet must receive the help of an incarcerated and manipulative cannibal killer to help catch another serial killer.",
    },
    {
        "imdb_id": "tt0482571",
        "set_group": 3,
        "title": "The Prestige",
        "year": 2006,
        "genre": "Drama, Mystery, Sci-Fi",
        "poster_url": "/static/survey_app/posters/the_prestige.svg",
        "description": "After a tragic accident, two stage magicians in 1890s London engage in a battle to create the ultimate illusion.",
    }
]


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        " n't": "n't",
        " 's": "'s",
        " 're": "'re",
        " 've": "'ve",
        " 'm": "'m",
        " 'd": "'d",
        " 'll": "'ll",
        " ,": ",",
        " .": ".",
        " !": "!",
        " ?": "?",
        " ;": ";",
        " :": ":",
        "( ": "(",
        " )": ")",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def truncate_words(text: str, limit: int = MAX_WORDS) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(" ,;:") + "..."


def is_complete_review_excerpt(text: str) -> bool:
    return text.endswith((".", "!", "?", ".'", "!'","?'","''"))


def load_review_pool() -> dict[str, list[str]]:
    dataset = pytreebank.load_sst(path=str(SST_PATH))
    pools = {"positive": [], "neutral": [], "negative": []}

    for split_name in ("train", "dev", "test"):
        for tree in dataset[split_name]:
            text = truncate_words(normalize_text(tree.to_lines()[0]))
            word_count = len(text.split())
            if word_count < 40 or word_count > 120:
                continue
            if text.startswith("..."):
                continue
            if not is_complete_review_excerpt(text):
                continue

            if tree.label >= 3:
                sentiment = "positive"
            elif tree.label == 2:
                sentiment = "neutral"
            else:
                sentiment = "negative"

            if text not in pools[sentiment]:
                pools[sentiment].append(text)

            # INCREASED DATA REQUIREMENTS: We now need a lot more reviews for 15 movies.
            # Raised from 8 to 50 minimum reviews per sentiment type.
            if len(pools["positive"]) >= 80 and len(pools["negative"]) >= 80 and len(pools["neutral"]) >= 40:
                return pools

    return pools


def build_movies() -> list[dict]:
    review_pool = load_review_pool()
    
    # Expanded to exactly 15 plans to match the 15 movies
    sentiment_plan = [
        ("positive", "positive"),
        ("positive", "neutral"),
        ("positive", "negative"),
        ("neutral", "positive"),
        ("negative", "positive"),
    ] * 3 
    
    indices = {"positive": 0, "neutral": 0, "negative": 0}

    movies = []
    for metadata, sentiments in zip(MOVIE_METADATA, sentiment_plan, strict=True):
        reviews = []
        for sentiment in sentiments:
            excerpts = review_pool[sentiment][indices[sentiment]:indices[sentiment] + 2]
            if len(excerpts) < 2:
                excerpts = review_pool[sentiment][indices[sentiment]:]
            indices[sentiment] += 2
            if len(excerpts) == 1:
                text = excerpts[0]
            else:
                text = f'Review excerpt 1: "{excerpts[0]}" Review excerpt 2: "{excerpts[1]}"'
            text = truncate_words(text, limit=135)
            reviews.append({"sentiment": sentiment, "text": text})
        movies.append({**metadata, "reviews": reviews})
    return movies


MOVIES = build_movies()