import os
import re
import json
import time
import hashlib
import html
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai
from google.genai import types


# ============================================================
# CONFIGURATION
# ============================================================

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

DATA_DIR = "data"
MASTER_FILE = "data.json"

INITIAL_ARTICLES = 15
ARTICLES_PER_UPDATE = 10
MAX_ARTICLES_PER_DAY = 100

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY GitHub Secret is missing.")

client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================
# HTTP SETTINGS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# NEWS SOURCES
# ============================================================

RSS_FEEDS = [
    (
        "Indian Express - India",
        "https://indianexpress.com/section/india/feed/"
    ),
    (
        "Indian Express - World",
        "https://indianexpress.com/section/world/feed/"
    ),
    (
        "Hindustan Times",
        "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"
    ),
    (
        "Times of India",
        "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"
    ),
    (
        "NDTV",
        "https://feeds.feedburner.com/ndtvnews-top-stories"
    ),
    (
        "BBC World",
        "https://feeds.bbci.co.uk/news/world/rss.xml"
    ),
    (
        "BBC India",
        "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"
    ),
    (
        "PIB",
        "https://pib.gov.in/RssMain.aspx"
    ),
    (
        "Google News - India",
        "https://news.google.com/rss/search?q=India&hl=en-IN&gl=IN&ceid=IN:en"
    ),
    (
        "Google News - World",
        "https://news.google.com/rss/search?q=world&hl=en-IN&gl=IN&ceid=IN:en"
    ),
    (
        "Google News - Science Technology",
        "https://news.google.com/rss/search?q=science+technology&hl=en-IN&gl=IN&ceid=IN:en"
    ),
]


# ============================================================
# FALLBACK IMAGES
# ============================================================

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1504711434969-e33886168f5c",
    "https://images.unsplash.com/photo-1495020689067-958852a7765e",
    "https://images.unsplash.com/photo-1505373877841-8d25f7d46678",
    "https://images.unsplash.com/photo-1521295121783-8a321d551ad2",
]


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_title(title):
    title = clean_text(title).lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def article_hash(title, url):
    raw = normalize_title(title) + "|" + str(url).strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def valid_title(title):
    if not title:
        return False

    bad_titles = [
        "actual current-affairs headline",
        "current affairs headline",
        "breaking news headline",
        "news headline",
        "sample headline",
        "test headline",
    ]

    lower = title.lower().strip()

    if lower in bad_titles:
        return False

    if len(title) < 20:
        return False

    return True


def safe_url(url):
    if not url:
        return ""

    url = str(url).strip()

    if url.startswith("http://") or url.startswith("https://"):
        return url

    return ""


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def extract_rss_image(entry):
    try:
        if hasattr(entry, "media_content"):
            media = entry.media_content

            if media:
                for item in media:
                    if isinstance(item, dict):
                        url = item.get("url")
                        if url:
                            return safe_url(url)

        if hasattr(entry, "media_thumbnail"):
            media = entry.media_thumbnail

            if media:
                for item in media:
                    if isinstance(item, dict):
                        url = item.get("url")
                        if url:
                            return safe_url(url)

        description = entry.get("description", "")

        match = re.search(
            r'<img[^>]+src=["\']([^"\']+)["\']',
            description,
            re.IGNORECASE,
        )

        if match:
            return safe_url(match.group(1))

    except Exception:
        pass

    return ""


def extract_page_image(url):
    if not url:
        return ""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=12,
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        meta = soup.find(
            "meta",
            attrs={"property": "og:image"}
        )

        if meta and meta.get("content"):
            return safe_url(meta["content"])

        meta = soup.find(
            "meta",
            attrs={"name": "twitter:image"}
        )

        if meta and meta.get("content"):
            return safe_url(meta["content"])

    except Exception:
        pass

    return ""


def get_image(entry, url, index):
    image = extract_rss_image(entry)

    if image:
        return image

    image = extract_page_image(url)

    if image:
        return image

    return FALLBACK_IMAGES[index % len(FALLBACK_IMAGES)]


# ============================================================
# ARTICLE PAGE EXTRACTION
# ============================================================

def extract_article_text(url):
    if not url:
        return ""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15,
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        for element in soup([
            "script",
            "style",
            "noscript",
            "nav",
            "footer",
            "header",
            "aside",
            "form",
        ]):
            element.decompose()

        paragraphs = []

        for p in soup.find_all("p"):
            text = clean_text(p.get_text(" ", strip=True))

            if len(text) >= 60:
                paragraphs.append(text)

        if not paragraphs:
            return ""

        paragraphs = paragraphs[:12]

        return "\n\n".join(paragraphs)

    except Exception:
        return ""


# ============================================================
# RSS COLLECTION
# ============================================================

def collect_candidates():
    candidates = []
    seen = set()

    print("Collecting RSS news...")

    for source_name, feed_url in RSS_FEEDS:

        print("SOURCE:", source_name)

        try:
            response = requests.get(
                feed_url,
                headers=HEADERS,
                timeout=20,
            )

            if response.status_code != 200:
                print(
                    "  RSS failed:",
                    response.status_code
                )
                continue

            feed = feedparser.parse(response.content)

            count = 0

            for entry in feed.entries[:30]:

                title = clean_text(
                    entry.get("title", "")
                )

                url = safe_url(
                    entry.get("link", "")
                )

                if not valid_title(title):
                    continue

                if not url:
                    continue

                key = article_hash(title, url)

                if key in seen:
                    continue

                seen.add(key)

                summary = clean_text(
                    entry.get("summary", "")
                )

                candidates.append({
                    "source_id": len(candidates),
                    "source_name": source_name,
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "image_url": get_image(
                        entry,
                        url,
                        len(candidates),
                    ),
                })

                count += 1

            print(
                "  Articles collected:",
                count
            )

        except Exception as exc:
            print(
                "  RSS ERROR:",
                str(exc)
            )

    print(
        "TOTAL CANDIDATES:",
        len(candidates)
    )

    return candidates


# ============================================================
# LOAD DATA
# ============================================================

def load_json(path, default=None):

    if default is None:
        default = {}

    if not os.path.exists(path):
        return default

    try:
        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except Exception as exc:
        print(
            "JSON LOAD ERROR:",
            path,
            str(exc),
        )

        return default


def load_today():

    path = os.path.join(
        DATA_DIR,
        TODAY_DATE + ".json"
    )

    data = load_json(path, {})

    if not isinstance(data, dict):
        return {
            "date": TODAY_DATE,
            "news": [],
        }

    news = data.get("news", [])

    if not isinstance(news, list):
        news = []

    return {
        "date": TODAY_DATE,
        "news": news,
    }


# ============================================================
# BUILD GEMINI PROMPT
# ============================================================

def build_prompt(candidates, required_count):

    source_material_parts = []

    for i, item in enumerate(candidates):

        source_material_parts.append(
            "SOURCE_ID: "
            + str(i)
            + "\n"
            + "SOURCE: "
            + item["source_name"]
            + "\n"
            + "HEADLINE: "
            + item["title"]
            + "\n"
            + "URL: "
            + item["url"]
            + "\n"
            + "SUMMARY: "
            + item["summary"]
            + "\n"
        )

    source_material = "\n---\n".join(
        source_material_parts
    )

    prompt = (
        "You are an expert current-affairs editor for an "
        "Indian competitive-exam website.\n\n"

        "Today's date is "
        + TODAY_DATE
        + ".\n\n"

        "Using ONLY the supplied source material, select exactly "
        + str(required_count)
        + " genuinely important current-affairs events.\n\n"

        "Rules:\n"
        "1. Do not invent events.\n"
        "2. Do not invent facts, numbers, dates or quotations.\n"
        "3. Do not use placeholder text.\n"
        "4. Each article must describe a different event.\n"
        "5. Prefer important India and world news.\n"
        "6. Include government, economy, science, technology, "
        "international affairs, environment, defence, sports, "
        "awards and important social developments when supported "
        "by the sources.\n"
        "7. The article must be useful for students preparing "
        "for competitive and board examinations.\n"
        "8. Keep factual wording neutral.\n"
        "9. source_id MUST be one of the supplied SOURCE_ID values.\n"
        "10. Return valid JSON only.\n\n"

        "Required JSON structure:\n"
        "[\n"
        "  {\n"
        '    "source_id": 0,\n'
        '    "category": "National",\n'
        '    "headline": "Specific real headline",\n'
        '    "story_lead": "2-3 sentence factual summary",\n'
        '    "bullet_points": [\n'
        '      "Important fact 1",\n'
        '      "Important fact 2",\n'
        '      "Important fact 3",\n'
        '      "Important fact 4"\n'
        "    ],\n"
        '    "full_article_text": "Detailed factual explanation of '
        'this exact event.",\n'
        '    "key_locations": "Relevant location",\n'
        '    "important_dates": "Relevant date",\n'
        '    "key_facts": "Important factual details",\n'
        '    "exam_relevance": "Why this event is relevant for exams",\n'
        '    "takeaway": "One concise revision takeaway"\n'
        "  }\n"
        "]\n\n"

        "SOURCE MATERIAL:\n"
        + source_material
    )

    return prompt


# ============================================================
# GEMINI GENERATION
# ============================================================

def generate_articles(candidates, required_count):

    if not candidates:
        print("No candidates available.")
        return []

    candidates = candidates[:40]

    prompt = build_prompt(
        candidates,
        required_count,
    )

    models = [
        "gemini-2.5-flash",
        "gemini-1.5-flash",
    ]

    for model_name in models:

        print(
            "Trying Gemini model:",
            model_name
        )

        try:

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.15,
                    response_mime_type="application/json",
                ),
            )

            text = response.text.strip()

            if text.startswith("```"):
                text = re.sub(
                    r"^```(?:json)?",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )

                text = re.sub(
                    r"```$",
                    "",
                    text,
                )

                text = text.strip()

            data = json.loads(text)

            if not isinstance(data, list):
                print("Gemini did not return a list.")
                continue

            print(
                "Gemini generated:",
                len(data),
                "articles"
            )

            return data

        except Exception as exc:

            print(
                "Gemini ERROR:",
                str(exc)
            )

            time.sleep(2)

    return []


# ============================================================
# CONVERT GEMINI ARTICLES
# ============================================================

def convert_articles(
    generated,
    candidates,
    existing_hashes,
):

    converted = []

    for item in generated:

        if not isinstance(item, dict):
            continue

        source_id = item.get("source_id")

        try:
            source_id = int(source_id)
        except Exception:
            continue

        if source_id < 0 or source_id >= len(candidates):
            continue

        source = candidates[source_id]

        headline = clean_text(
            item.get("headline", "")
        )

        if not valid_title(headline):
            continue

        lower_headline = headline.lower()

        if (
            "actual current-affairs headline"
            in lower_headline
        ):
            continue

        source_hash = article_hash(
            headline,
            source["url"],
        )

        if source_hash in existing_hashes:
            continue

        story_lead = clean_text(
            item.get("story_lead", "")
        )

        full_article_text = clean_text(
            item.get("full_article_text", "")
        )

        bullet_points = item.get(
            "bullet_points",
            [],
        )

        if not isinstance(
            bullet_points,
            list,
        ):
            bullet_points = []

        bullet_points = [
            clean_text(x)
            for x in bullet_points
            if clean_text(x)
        ]

        if not story_lead:
            story_lead = source["summary"]

        if not full_article_text:
            full_article_text = extract_article_text(
                source["url"]
            )

        if not full_article_text:
            full_article_text = story_lead

        article = {
            "id": 0,
            "category": clean_text(
                item.get(
                    "category",
                    "National",
                )
            ) or "National",

            "headline": headline,

            "story_lead": story_lead,

            "bullet_points": bullet_points,

            "full_article_text": full_article_text,

            "key_locations": clean_text(
                item.get(
                    "key_locations",
                    "",
                )
            ),

            "important_dates": clean_text(
                item.get(
                    "important_dates",
                    "",
                )
            ),

            "key_facts": clean_text(
                item.get(
                    "key_facts",
                    "",
                )
            ),

            "exam_relevance": clean_text(
                item.get(
                    "exam_relevance",
                    "",
                )
            ),

            "takeaway": clean_text(
                item.get(
                    "takeaway",
                    "",
                )
            ),

            "source_name": source[
                "source_name"
            ],

            "source_url": source[
                "url"
            ],

            "image_url": source[
                "image_url"
            ],

            "published_date": TODAY_DATE,
        }

        converted.append(article)

        existing_hashes.add(
            source_hash
        )

    return converted


# ============================================================
# UPDATE TODAY
# ============================================================

def update_today():

    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )

    existing = load_today()

    old_news = existing.get(
        "news",
        [],
    )

    if not isinstance(
        old_news,
        list,
    ):
        old_news = []

    print(
        "Existing articles:",
        len(old_news)
    )

    existing_hashes = set()

    for article in old_news:

        if not isinstance(
            article,
            dict,
        ):
            continue

        existing_hashes.add(
            article_hash(
                article.get(
                    "headline",
                    "",
                ),
                article.get(
                    "source_url",
                    "",
                ),
            )
        )

    if len(old_news) >= MAX_ARTICLES_PER_DAY:

        print(
            "Daily article limit reached."
        )

        return {
            "date": TODAY_DATE,
            "news": old_news[
                :MAX_ARTICLES_PER_DAY
            ],
        }

    candidates = collect_candidates()

    if not candidates:
        print(
            "No RSS candidates found."
        )

        if old_news:
            return {
                "date": TODAY_DATE,
                "news": old_news,
            }

        raise RuntimeError(
            "No news candidates were collected."
        )

    if len(old_news) == 0:
        required_count = INITIAL_ARTICLES
    else:
        required_count = min(
            ARTICLES_PER_UPDATE,
            MAX_ARTICLES_PER_DAY - len(old_news),
        )

    print(
        "Articles requested from Gemini:",
        required_count
    )

    generated = generate_articles(
        candidates,
        required_count,
    )

    if not generated:

        if old_news:
            print(
                "Generation failed. "
                "Keeping existing articles."
            )

            return {
                "date": TODAY_DATE,
                "news": old_news,
            }

        raise RuntimeError(
            "Gemini generated no articles. "
            "No empty data file will be created."
        )

    new_articles = convert_articles(
        generated,
        candidates,
        existing_hashes,
    )

    print(
        "Valid new articles:",
        len(new_articles)
    )

    combined = old_news + new_articles

    combined = combined[
        :MAX_ARTICLES_PER_DAY
    ]

    for index, article in enumerate(
        combined,
        start=1,
    ):
        article["id"] = index

    if not combined:
        raise RuntimeError(
            "Final article count is zero. "
            "Existing data was not overwritten."
        )

    return {
        "date": TODAY_DATE,
        "news": combined,
    }


# ============================================================
# AVAILABLE DATES
# ============================================================

def get_available_dates():

    if not os.path.exists(
        DATA_DIR
    ):
        return []

    dates = []

    for filename in os.listdir(
        DATA_DIR
    ):

        if not filename.endswith(
            ".json"
        ):
            continue

        date_part = filename[:-5]

        if re.fullmatch(
            r"\d{4}-\d{2}-\d{2}",
            date_part,
        ):
            dates.append(
                date_part
            )

    dates.sort(
        reverse=True
    )

    return dates


# ============================================================
# SAVE JSON SAFELY
# ============================================================

def save_json(path, data):

    directory = os.path.dirname(path)

    if directory:
        os.makedirs(
            directory,
            exist_ok=True,
        )

    temporary = path + ".tmp"

    with open(
        temporary,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(
        temporary,
        path,
    )


# ============================================================
# MOTIVATION
# ============================================================

MOTIVATIONAL_QUOTES = [
    (
        "Success is the sum of small efforts, "
        "repeated day in and day out."
    ),
    (
        "Consistency turns ordinary preparation "
        "into extraordinary results."
    ),
    (
        "Study with focus today so that tomorrow "
        "becomes easier."
    ),
    (
        "Every difficult chapter becomes easier "
        "when you understand it step by step."
    ),
    (
        "Discipline is doing the work even when "
        "motivation is low."
    ),
    (
        "Learn the concept, practise the question, "
        "master the subject."
    ),
]


def get_motivation():

    day_number = datetime.now().timetuple().tm_yday

    quote = MOTIVATIONAL_QUOTES[
        day_number
        % len(MOTIVATIONAL_QUOTES)
    ]

    return {
        "quote": quote,
        "date": TODAY_DATE,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("AURA EXAM AI NEWS UPDATER")
    print("DATE:", TODAY_DATE)
    print("=" * 60)

    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )

    today_data = update_today()

    today_path = os.path.join(
        DATA_DIR,
        TODAY_DATE + ".json",
    )

    save_json(
        today_path,
        today_data,
    )

    available_dates = get_available_dates()

    master = {
        "current_date": TODAY_DATE,
        "available_dates": available_dates,
        "today": today_data,
        "motivation": get_motivation(),
    }

    save_json(
        MASTER_FILE,
        master,
    )

    print("=" * 60)
    print(
        "FINAL ARTICLE COUNT:",
        len(
            today_data.get(
                "news",
                [],
            )
        ),
    )

    print(
        "AVAILABLE DATES:",
        len(available_dates),
    )

    print(
        "TODAY FILE:",
        today_path,
    )

    print(
        "MASTER FILE:",
        MASTER_FILE,
    )

    print("=" * 60)
    print("UPDATE COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
