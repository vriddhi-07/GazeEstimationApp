import csv
from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent.parent
FNC_DIR = BASE_DIR / "data" / "fnc-1"
MAX_WORDS = 150

def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:60] or "headline"

def truncate_words(text: str, limit: int = MAX_WORDS) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(" ,;:") + "..."

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def build_summary(text: str, limit: int = 24) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(" ,;:") + "..."

def load_bodies() -> dict[str, str]:
    with (FNC_DIR / "train_bodies.csv").open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {
            row["Body ID"]: truncate_words(normalize_text(row["articleBody"]))
            for row in reader
        }

# (headline, body_id) pairs to skip even though they pass the word-count
# filter — e.g. articles that are technically >=60 words but still read as
# visual outliers next to the other stimuli. Keeping this as an explicit
# exclusion (rather than raising MIN_WORDS) avoids reshuffling every other
# article's selection.
EXCLUDED_PAIRS = {
    ("ISIL Beheads American Photojournalist in Iraq", "608"),
    ("Report: Christian Bale Just Bailed on the Steve Jobs Movie", "1157"),
}

def build_news_articles() -> list[dict]:
    bodies = load_bodies()
    
    # We need 9 articles total (3 groups * 3 articles each)
    # Using a mix of stances for each group
    desired_stances = ["agree", "discuss", "unrelated"] * 3
    
    collected: list[dict] = []
    used_pairs: set[tuple[str, str]] = set()

    with (FNC_DIR / "train_stances.csv").open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    search_start = 0
    for desired_stance in desired_stances:
        for idx in range(search_start, len(rows)):
            row = rows[idx]
            if row["Stance"] != desired_stance:
                continue
            body_id = row["Body ID"]
            headline = normalize_text(row["Headline"])
            body = bodies.get(body_id, "")
            
            if not body or len(body.split()) < 60:
                continue
            
            pair = (headline, body_id)
            if pair in used_pairs or pair in EXCLUDED_PAIRS:
                continue

            used_pairs.add(pair)
            
            # Dynamically assign to group 1, 2, or 3 based on current count
            group_num = (len(collected) // 3) + 1
            
            collected.append(
                {
                    "slug": f"{slugify(headline)}-{body_id}",
                    "set_group": group_num,
                    "headline": headline,
                    "source": "FNC-1",
                    "summary": build_summary(body),
                    "body": body,
                    "stance": desired_stance,
                    "is_fake": False,
                }
            )
            search_start = idx + 1
            break

    return collected

NEWS_ARTICLES = build_news_articles()