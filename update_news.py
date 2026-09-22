import os
import json
import time
import re
import hashlib
from datetime import datetime

import feedparser
import requests
from bs4 import BeautifulSoup
from google import genai


# ============================================================
# AURA EXAM AI
# Incremental Current Affairs Updater
# ============================================================

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

DATA_DIR = "data"
MASTER_FILE = "data.json"

INITIAL_ARTICLES = 15
ARTICLES_PER_UPDATE = 10
MAX_ARTICLES_PER_DAY = 100

os.makedirs(DATA_DIR, exist_ok=True)


# ============================================================
# GEMINI
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )

client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================
# LARGE NEWS SOURCES
# ============================================================

RSS_FEEDS = [
    {
        "name": "Reuters India",
        "url": "https://feeds.reuters.com/reuters/INtopNews",
    },
    {
        "name": "Reuters World",
        "url": "https://feeds.reuters.com/Reuters/worldNews",
    },
    {
        "name": "Indian Express India",
        "url": "https://indianexpress.com/section/india/feed/",
    },
    {
        "name": "Indian Express World",
        "url": "https://indianexpress.com/section/world/feed/",
    },
    {
        "name": "Hindustan Times India",
        "url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
    },
    {
        "name": "Times of India",
        "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    },
    {
        "name": "NDTV",
        "url": "https://feeds.feedburner.com/ndtvnews-top-stories",
    },
    {
        "name": "BBC World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
    },
    {
        "name": "BBC India",
        "url": "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml",
    },
]


# ============================================================
# FALLBACK IMAGES
# ============================================================

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1495020689067-958852a7765e",
    "https://images.unsplash.com/photo-1504711434969-e33886168f5c",
    "https://images.unsplash.com/photo-1521295121783-8a321d551ad2",
    "https://images.unsplash.com/photo-1585829365295-ab7cd400c167",
]


# ============================================================
# TEXT HELPERS
# ============================================================

JUNK_PATTERNS = [
    "subscribe",
    "sign in",
    "login",
    "advertisement",
    "advertising",
    "cookie policy",
    "privacy policy",
    "terms of use",
    "newsletter",
    "follow us",
    "read more",
    "click here",
    "download app",
]


def clean_text(text):
    if not text:
        return ""

    text = BeautifulSoup(
        str(text),
        "html.parser"
    ).get_text(" ", strip=True)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def is_junk(text):
    if not text:
        return True

    text = clean_text(text)

    if len(text) < 35:
        return True

    lower = text.lower()

    return any(
        pattern in lower
        for pattern in JUNK_PATTERNS
    )


def normalize_title(title):
    title = clean_text(title).lower()

    title = re.sub(
        r"[^a-z0-9]+",
        " ",
        title
    )

    return re.sub(
        r"\s+",
        " ",
        title
    ).strip()


def make_article_key(title, url):
    raw = (
        normalize_title(title)
        + "|"
        + str(url).strip().lower()
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def get_rss_image(entry):

    try:
        for item in entry.get("media_content", []):
            url = item.get("url")

            if url and url.startswith("http"):
                return url
    except Exception:
        pass

    try:
        for item in entry.get("media_thumbnail", []):
            url = item.get("url")

            if url and url.startswith("http"):
                return url
    except Exception:
        pass

    try:
        for item in entry.get("enclosures", []):
            url = (
                item.get("href")
                or item.get("url")
            )

            if url and url.startswith("http"):
                return url
    except Exception:
        pass

    try:
        html = (
            entry.get("summary", "")
            or entry.get("description", "")
        )

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        image = soup.find("img")

        if image:
            src = image.get("src")

            if src and src.startswith("http"):
                return src

    except Exception:
        pass

    return ""


def get_og_image(url):

    try:

        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/120 Safari/537.36"
            },
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        meta = soup.find(
            "meta",
            attrs={"property": "og:image"}
        )

        if meta:
            image = meta.get("content")

            if image and image.startswith("http"):
                return image

    except Exception:
        pass

    return ""


# ============================================================
# ARTICLE EXTRACTION
# ============================================================

def extract_article_text(url):

    try:

        response = requests.get(
            url,
            timeout=12,
            headers={
                "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/120 Safari/537.36"
            },
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for tag in soup.find_all(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "aside",
                "form",
                "noscript",
                "iframe",
                "svg",
            ]
        ):
            tag.decompose()

        article = soup.find("article")

        if article:
            paragraphs = article.find_all("p")
        else:
            paragraphs = soup.find_all("p")

        result = []

        for paragraph in paragraphs:

            text = clean_text(
                paragraph.get_text(
                    " ",
                    strip=True
                )
            )

            if not is_junk(text):
                result.append(text)

        # Remove duplicate paragraphs
        unique = []

        for paragraph in result:
            if paragraph not in unique:
                unique.append(paragraph)

        return " ".join(unique[:20])[:7000]

    except Exception as error:

        print(
            f"Article extraction error: {error}"
        )

        return ""


# ============================================================
# FETCH NEWS
# ============================================================

def fetch_news():

    print("\nFetching current news...")

    articles = []
    seen_urls = set()
    seen_titles = set()

    for feed_info in RSS_FEEDS:

        print(
            f"Checking {feed_info['name']}..."
        )

        try:

            feed = feedparser.parse(
                feed_info["url"]
            )

            for entry in feed.entries[:15]:

                title = clean_text(
                    entry.get("title", "")
                )

                url = entry.get("link", "")

                if not title or not url:
                    continue

                title_key = normalize_title(title)

                if url in seen_urls:
                    continue

                if title_key in seen_titles:
                    continue

                # Reject placeholder content
                if (
                    "actual current-affairs headline"
                    in title.lower()
                ):
                    continue

                seen_urls.add(url)
                seen_titles.add(title_key)

                summary = clean_text(
                    entry.get("summary", "")
                    or entry.get("description", "")
                )

                image_url = get_rss_image(entry)

                article_text = extract_article_text(
                    url
                )

                if not article_text:
                    article_text = summary

                if not article_text:
                    continue

                if not image_url:
                    image_url = get_og_image(url)

                if not image_url:
                    image_url = FALLBACK_IMAGES[
                        len(articles)
                        % len(FALLBACK_IMAGES)
                    ]

                articles.append(
                    {
                        "source_name":
                            feed_info["name"],

                        "title":
                            title,

                        "url":
                            url,

                        "summary":
                            summary[:1500],

                        "article_context":
                            article_text[:7000],

                        "image_url":
                            image_url,

                        "article_key":
                            make_article_key(
                                title,
                                url
                            ),
                    }
                )

                if len(articles) >= 80:
                    break

        except Exception as error:

            print(
                f"Could not read "
                f"{feed_info['name']}: {error}"
            )

        if len(articles) >= 80:
            break

    print(
        f"Collected {len(articles)} source stories."
    )

    return articles


# ============================================================
# LOAD TODAY'S EXISTING DATA
# ============================================================

def get_today_file():

    return os.path.join(
        DATA_DIR,
        f"{TODAY_DATE}.json"
    )


def load_today_data():

    path = get_today_file()

    if not os.path.exists(path):
        return {
            "date": TODAY_DATE,
            "news": [],
            "motivation": get_motivation(),
        }

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(
                "Today's JSON is not an object."
            )

        if not isinstance(
            data.get("news"),
            list
        ):
            data["news"] = []

        return data

    except Exception as error:

        print(
            f"Could not read today's file: {error}"
        )

        return {
            "date": TODAY_DATE,
            "news": [],
            "motivation": get_motivation(),
        }


# ============================================================
# FIND ALREADY USED STORIES
# ============================================================

def get_existing_keys(today_data):

    keys = set()

    for item in today_data.get("news", []):

        url = item.get(
            "source_url",
            ""
        )

        title = item.get(
            "headline",
            ""
        )

        if url:
            keys.add(
                make_article_key(
                    title,
                    url
                )
            )

    return keys


# ============================================================
# PREPARE GEMINI SOURCE MATERIAL
# ============================================================

def prepare_source_material(
    candidates
):

    blocks = []

    for index, item in enumerate(
        candidates,
        start=1
    ):

        blocks.append(
            f"""
SOURCE_ID: {index}
SOURCE_NAME: {item['source_name']}
TITLE: {item['title']}
URL: {item['url']}

SUMMARY:
{item['summary']}

ARTICLE_CONTEXT:
{item['article_context']}

IMAGE_URL:
{item['image_url']}

--------------------------------------------------
"""
        )

    return "\n".join(blocks)


# ============================================================
# GEMINI
# ============================================================

def generate_articles(
    candidates,
    number_required
):

    source_material = prepare_source_material(
        candidates
    )

    prompt = f"""
You are the editor of AURA EXAM AI,
a daily current-affairs platform for Indian
students preparing for CBSE and competitive
examinations.

Today's date:
{TODAY_DATE}

Generate EXACTLY {number_required} NEW current-affairs
articles from the supplied source material.

IMPORTANT:

- Use only the supplied sources.
- Do not invent news.
- Do not invent facts.
- Do not invent URLs.
- Do not invent source names.
- Do not mix unrelated stories.
- Each article must come from ONE SOURCE_ID.
- Do not repeat the same event.
- Do not use old news when a newer relevant story exists.
- Avoid entertainment/gossip unless it has significant
  national or international public relevance.
- Prefer India, world affairs, science, technology,
  economy, environment, defence, international relations,
  government, education, important appointments,
  major reports, sports events of national significance,
  and important institutional developments.
- Write in clear student-friendly language.
- The full article must be specifically about its headline.
- Do not copy the source article word-for-word.

Each article should contain:

headline
story_lead
bullet_points
full_article_text
key_locations
important_dates
key_facts
exam_relevance
takeaway
category
entities
source_id

Return ONLY valid JSON.

Required structure:

{{
  "news": [
    {{
      "source_id": 1,
      "category": "National",
      "headline": "...",
      "story_lead": "...",
      "bullet_points": [
        "...",
        "...",
        "...",
        "..."
      ],
      "full_article_text": "...",
      "key_locations": [
        "..."
      ],
      "important_dates": [
        "..."
      ],
      "key_facts": [
        "...",
        "...",
        "..."
     
