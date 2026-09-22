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
# CONFIG
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
# NEWS SOURCES
# ============================================================

RSS_FEEDS = [
    {
        "name": "Indian Express India",
        "url": "https://indianexpress.com/section/india/feed/",
    },
    {
        "name": "Indian Express World",
        "url": "https://indianexpress.com/section/world/feed/",
    },
    {
        "name": "Hindustan Times",
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
    {
        "name": "PIB",
        "url": "https://pib.gov.in/RssMain.aspx",
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
# TEXT FUNCTIONS
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

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def is_junk(text):
    if not text:
        return True

    text = clean_text(text)

    if len(text) < 35:
        return True

    lower = text.lower()

    for pattern in JUNK_PATTERNS:
        if pattern in lower:
            return True

    return False


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
    value = (
        normalize_title(title)
        + "|"
        + str(url).strip().lower()
    )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def get_rss_image(entry):

    try:
        for media in entry.get(
            "media_content",
            []
        ):
            url = media.get("url")

            if url and url.startswith("http"):
                return url
    except Exception:
        pass

    try:
        for media in entry.get(
            "media_thumbnail",
            []
        ):
            url = media.get("url")

            if url and url.startswith("http"):
                return url
    except Exception:
        pass

    try:
        for enclosure in entry.get(
            "enclosures",
            []
        ):
            url = (
                enclosure.get("href")
                or enclosure.get("url")
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
            url = image.get("src")

            if url and url.startswith("http"):
                return url

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
                    "(Windows NT 10
