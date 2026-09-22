import os
import re
import json
import time
import hashlib
import html
from datetime import datetime

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
# HTTP HEADERS
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
# RSS SOURCES
# ============================================================

RSS_FEEDS = [
    (
        "Indian Express - India",
        "https://indianexpress.com/section/india/feed/",
    ),
    (
        "Indian Express - World",
        "https://indianexpress.com/section/world/feed/",
    ),
    (
        "Hindustan Times",
        "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
    ),
    (
        "Times of India",
        "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    ),
    (
        "NDTV",
        "https://feeds.feedburner.com/ndtvnews-top-stories",
    ),
    (
        "BBC World",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ),
    (
        "BBC India",
        "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml",
    ),
    (
        "PIB",
        "https://pib.gov.in/RssMain.aspx",
    ),
    (
        "Google News - India",
        "https://news.google.com/rss/search?q=India&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Google News - World",
        "https://news.google.com/rss/search?q=world&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Google News - Science Technology",
        "https://news.google.com/rss/search?q=science+technology&hl=en-IN&gl=IN&ceid=IN:en",
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
# TEXT FUNCTIONS
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

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def valid_title(title):
    if not title:
        return False

    if len(title) < 20:
        return False

    bad_titles = [
        "actual current-affairs headline",
        "current affairs headline",
        "breaking news headline",
        "news headline",
        "sample headline",
        "test headline",
    ]

    if title.lower().strip() in bad_titles:
        return False

    return True


def safe_url(url):
    if not url:
        return ""

    url = str(url).strip()

    if url.startswith("http://"):
        return url

    if url.startswith("https://"):
        return url

    return ""


# ============================================================
# IMAGE FUNCTIONS
# ============================================================

def extract_rss_image(entry):
    try:
        media_content = entry.get("media_content")

        if media_content:
            for item in media_content:
                if isinstance(item, dict):
                    image_url = item.get("url")

                    if image_url:
                        return safe_url(image_url)

        media_thumbnail = entry.get("media_thumbnail")

        if media_thumbnail:
            for item in media_thumbnail:
                if isinstance(item, dict):
                    image_url = item.get("url")

                    if image_url:
                        return safe_url(image_url)

        description = entry.get(
            "description",
            "",
        )

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

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        meta = soup.find(
            "meta",
            attrs={"property": "og:image"},
        )

        if meta:
            image_url = meta.get("content")

            if image_url:
                return safe_url(image_url)

        meta = soup.find(
            "meta",
            attrs={"name": "twitter:image"},
        )

        if meta:
            image_url = meta.get("content")

            if image_url:
                return safe_url(image_url)

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

    return FALLBACK_IMAGES[
        index % len(FALLBACK_IMAGES)
    ]


# ============================================================
# ARTICLE PAGE TEXT
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

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        for element in soup(
            [
                "script",
                "style",
                "noscript",
                "nav",
                "footer",
                "header",
                "aside",
                "form",
            ]
        ):
            element.decompose()

        paragraphs = []

        for paragraph in soup.find_all("p"):
            text = clean_text(
                paragraph.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(text) >= 60:
                paragraphs.append(text)

        if not paragraphs:
            return ""

        return "\n\n".join(
            paragraphs[:12]
        )

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
                    response.status_code,
                )
                continue

            feed = feedparser.parse(
                response.content
            )

            source_count = 0

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

                unique_key = article_hash(
                    title,
                    url,
                )

                if unique_key in seen:
                    continue

                seen.add(unique_key)

                summary = clean_text(
                    entry.get(
                        "summary",
                        "",
                    )
                )

                image_url = get_image(
                    entry,
                    url,
                    len(candidates),
                )

                candidates.append(
                    {
                        "source_id": len(candidates),
                        "source_name": source_name,
                        "title": title,
                        "url": url,
                        "summary": summary,
                        "image_url": image_url,
                    }
                )

                source_count += 1

            print(
                "  Articles collected:",
                source_count,
            )

        except Exception as exc:
            print(
                "  RSS ERROR:",
                str(exc),
            )

    print(
        "TOTAL CANDIDATES:",
        len(candidates),
    )

    return candidates


# ============================================================
# JSON FUNCTIONS
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


def save_json(path, data):
    directory = os.path.dirname(path)

    if directory:
        os.makedirs(
            directory,
            exist_ok=True,
        )

    temporary_path = path + ".tmp"

    with open(
        temporary_path,
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
        temporary_path,
        path,
    )


def load_today():
    path = os.path.join(
        DATA_DIR,
        TODAY_DATE + ".json",
    )

    data = load_json(
        path,
        {},
    )

    if not isinstance(data, dict):
        return {
            "date": TODAY_DATE,
            "news": [],
        }

    news = data.get(
        "news",
        [],
    )

    if not isinstance(news, list):
        news = []

    return {
        "date": TODAY_DATE,
        "news": news,
    }


# ============================================================
# GEMINI PROMPT
# ============================================================

def build_prompt(
    candidates,
    required_count,
):
    source_parts = []

    for index, item in enumerate(candidates):

        source_text = (
            "SOURCE_ID: "
            + str(index)
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
        )

        source_parts.append(
            source_text
        )

    source_material = "\n\n---\n\n".join(
        source_parts
    )

    prompt = (
        "You are an expert current-affairs "
        "editor for an Indian examination "
        "website.\n\n"

        "Today's date: "
        + TODAY_DATE
        + "\n\n"

        "Select exactly "
        + str(required_count)
        + " important current-affairs "
        "events from the supplied sources.\n\n"

        "STRICT RULES:\n"
        "1. Use only information present in "
        "the supplied sources.\n"
        "2. Never invent a news event.\n"
        "3. Never invent statistics, dates, "
        "names or quotations.\n"
        "4. Do not create placeholder headlines.\n"
        "5. Each article must describe a "
        "different event.\n"
        "6. Prefer important India and world "
        "developments.\n"
        "7. Make the content useful for "
        "CBSE, UPSC, SSC, Banking, "
        "NEET and JEE-level revision.\n"
        "8. Keep the writing factual and neutral.\n"
        "9. source_id must exactly match one "
        "of the supplied source IDs.\n"
        "10. Return JSON only.\n\n"

        "Return this structure:\n"

        "[\n"
        "  {\n"
        '    "source_id": 0,\n'
        '    "category": "National",\n'
        '    "headline": "Real specific headline",\n'
        '    "story_lead": "Concise factual summary",\n'
        '    "bullet_points": [\n'
        '      "Fact 1",\n'
        '      "Fact 2",\n'
        '      "Fact 3",\n'
        '      "Fact 4"\n'
        "    ],\n"
        '    "full_article_text": "Detailed factual '
        'explanation of this exact event",\n'
        '    "key_locations": "Relevant location",\n'
        '    "important_dates": "Relevant date",\n'
        '    "key_facts": "Important facts",\n'
        '    "exam_relevance": "Exam relevance",\n'
        '    "takeaway": "Revision takeaway"\n'
        "  }\n"
        "]\n\n"

        "SOURCE MATERIAL:\n"
        + source_material
    )

    return prompt


# ============================================================
# GEMINI GENERATION
# ============================================================

def generate_articles(
    candidates,
    required_count,
):
    if not candidates:
        print("No candidates available.")
        return []

    candidates = candidates[:40]

    prompt = build_prompt(
        candidates,
        required_count,
    )

    models = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    ]

    for model_name in models:

        print(
            "Trying Gemini model:",
            model_name,
        )

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            response_text = response.text

            if not response_text:
                print(
                    "Gemini returned empty response."
                )
                continue

            response_text = response_text.strip()

            if response_text.startswith("```"):
                response_text = re.sub(
                    r"^```(?:json)?",
                    "",
                    response_text,
                    flags=re.IGNORECASE,
                )

                response_text = re.sub(
                    r"```$",
                    "",
                    response_text,
                )

                response_text = response_text.strip()

            generated = json.loads(
                response_text
            )

            if not isinstance(
                generated,
                list,
            ):
                print(
                    "Gemini response is not a list."
                )
                continue

            print(
                "Gemini generated:",
                len(generated),
                "articles",
            )

            return generated

        except Exception as exc:
            print(
                "Gemini ERROR:",
                str(exc),
            )

            time.sleep(2)

    return []


# ============================================================
# CONVERT GENERATED ARTICLES
# ============================================================

def convert_articles(
    generated,
    candidates,
    existing_hashes,
):
    converted = []

    for item in generated:

        if not isinstance(
            item,
            dict,
        ):
            continue

        # ----------------------------------------------------
        # SOURCE ID
        # ----------------------------------------------------

        source_id_value = item.get(
            "source_id"
        )

        try:
            source_id = int(
                source_id_value
            )
        except Exception:
            continue

        if source_id < 0:
            continue

        if source_id >= len(candidates):
            continue

        source = candidates[
            source_id
        ]

        # ----------------------------------------------------
        # HEADLINE
        # ----------------------------------------------------

        headline = clean_text(
            item.get(
                "headline",
                "",
            )
        )

        if not valid_title(headline):
            continue

        if (
            "actual current-affairs headline"
            in headline.lower()
        ):
            continue

        # ----------------------------------------------------
        # DUPLICATE CHECK
        # ----------------------------------------------------

        unique_key = article_hash(
            headline,
            source["url"],
        )

        if unique_key in existing_hashes:
            continue

        # ----------------------------------------------------
        # STORY LEAD
        # ----------------------------------------------------

        story_lead = clean_text(
            item.get(
                "story_lead",
                "",
            )
        )

        if not story_lead:
            story_lead = source[
                "summary"
            ]

        # ----------------------------------------------------
        # BULLET POINTS
        # ----------------------------------------------------

        raw_bullets = item.get(
            "bullet_points",
            [],
        )

        if not isinstance(
            raw_bullets,
            list,
        ):
            raw_bullets = []

        bullet_points = []

        for bullet in raw_bullets:
            cleaned_bullet = clean_text(
                bullet
            )

            if cleaned_bullet:
                bullet_points.append(
                    cleaned_bullet
                )

        # ----------------------------------------------------
        # FULL ARTICLE
        # ----------------------------------------------------

        full_article_text = clean_text(
            item.get(
                "full_article_text",
                "",
            )
        )

        if not full_article_text:

            full_article_text = (
                extract_article_text(
                    source["url"]
                )
            )

        if not full_article_text:
            full_article_text = story_lead

        # ----------------------------------------------------
        # OTHER FIELDS
        # ----------------------------------------------------

        category = clean_text(
            item.get(
