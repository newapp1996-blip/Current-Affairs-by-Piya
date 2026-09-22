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
# SETTINGS
# ============================================================

TODAY = datetime.now().strftime("%Y-%m-%d")

DATA_DIR = "data"
MASTER_FILE = "data.json"

FIRST_RUN_COUNT = 15
UPDATE_COUNT = 10
MAX_DAILY_COUNT = 100

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing.")

gemini = genai.Client(api_key=API_KEY)


# ============================================================
# HTTP
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}


# ============================================================
# RSS FEEDS
# ============================================================

FEEDS = [
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
        "Google News India",
        "https://news.google.com/rss/search?q=India&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Google News World",
        "https://news.google.com/rss/search?q=world&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Google News Science Technology",
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
# TEXT CLEANING
# ============================================================

def clean(value):
    if value is None:
        return ""

    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def valid_title(title):
    title = clean(title)

    if len(title) < 20:
        return False

    blocked = [
        "actual current-affairs headline",
        "current affairs headline",
        "sample headline",
        "test headline",
    ]

    if title.lower() in blocked:
        return False

    return True


def make_hash(title, url):
    value = (
        clean(title).lower()
        + "|"
        + clean(url)
    )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


# ============================================================
# IMAGE
# ============================================================

def get_rss_image(entry):

    try:
        media = entry.get("media_content")

        if media:
            for item in media:
                if isinstance(item, dict):
                    url = item.get("url")

                    if url:
                        return url

        media = entry.get("media_thumbnail")

        if media:
            for item in media:
                if isinstance(item, dict):
                    url = item.get("url")

                    if url:
                        return url

    except Exception:
        pass

    return ""


def get_page_image(url):

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10,
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        tag = soup.find(
            "meta",
            attrs={"property": "og:image"},
        )

        if tag:
            value = tag.get("content")

            if value:
                return value

    except Exception:
        pass

    return ""


def get_image(entry, url, number):

    image = get_rss_image(entry)

    if image:
        return image

    image = get_page_image(url)

    if image:
        return image

    return FALLBACK_IMAGES[
        number % len(FALLBACK_IMAGES)
    ]


# ============================================================
# RSS COLLECTION
# ============================================================

def collect_news():

    results = []
    seen = set()

    print("Collecting RSS news...")

    for source_name, feed_url in FEEDS:

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

                title = clean(
                    entry.get(
                        "title",
                        "",
                    )
                )

                url = clean(
                    entry.get(
                        "link",
                        "",
                    )
                )

                if not valid_title(title):
                    continue

                if not url:
                    continue

                key = make_hash(
                    title,
                    url,
                )

                if key in seen:
                    continue

                seen.add(key)

                summary = clean(
                    entry.get(
                        "summary",
                        "",
                    )
                )

                image = get_image(
                    entry,
                    url,
                    len(results),
                )

                article = {
                    "source_id": len(results),
                    "source_name": source_name,
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "image_url": image,
                }

                results.append(article)

                source_count += 1

            print(
                "  Articles collected:",
                source_count,
            )

        except Exception as error:

            print(
                "  RSS ERROR:",
                str(error),
            )

    print(
        "TOTAL CANDIDATES:",
        len(results),
    )

    return results


# ============================================================
# JSON
# ============================================================

def load_json(path):

    if not os.path.exists(path):
        return {}

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            "JSON ERROR:",
            str(error),
        )

        return {}


def save_json(path, data):

    folder = os.path.dirname(path)

    if folder:
        os.makedirs(
            folder,
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
# TODAY'S EXISTING NEWS
# ============================================================

def load_today():

    path = os.path.join(
        DATA_DIR,
        TODAY + ".json",
    )

    data = load_json(path)

    if not isinstance(data, dict):
        return []

    news = data.get("news")

    if not isinstance(news, list):
        return []

    return news


# ============================================================
# GEMINI PROMPT
# ============================================================

def make_prompt(
    sources,
    number,
):

    lines = []

    for source in sources:

        line = (
            "SOURCE_ID="
            + str(source["source_id"])
            + "\nSOURCE="
            + source["source_name"]
            + "\nHEADLINE="
            + source["title"]
            + "\nURL="
            + source["url"]
            + "\nSUMMARY="
            + source["summary"]
        )

        lines.append(line)

    source_text = "\n\n---\n\n".join(lines)

    prompt = (
        "You are a professional current affairs "
        "editor.\n\n"
        "Today's date is "
        + TODAY
        + ".\n\n"
        "Select exactly "
        + str(number)
        + " important current-affairs events "
        "from the supplied sources.\n\n"

        "IMPORTANT RULES:\n"
        "- Use only supplied source information.\n"
        "- Never invent an event.\n"
        "- Never invent names, dates or statistics.\n"
        "- Do not use placeholder headlines.\n"
        "- Every article must be a different event.\n"
        "- Prefer important Indian and world news.\n"
        "- Make the articles useful for students.\n"
        "- Keep the writing factual and neutral.\n"
        "- source_id must match the supplied source.\n"
        "- Return JSON only.\n\n"

        "JSON FORMAT:\n"
        "[\n"
        "{\n"
        '  "source_id": 0,\n'
        '  "category": "National",\n'
        '  "headline": "Real headline",\n'
        '  "story_lead": "Short factual summary",\n'
        '  "bullet_points": ["Fact 1", "Fact 2", "Fact 3", "Fact 4"],\n'
        '  "full_article_text": "Detailed explanation",\n'
        '  "key_locations": "Location",\n'
        '  "important_dates": "Date",\n'
        '  "key_facts": "Important facts",\n'
        '  "exam_relevance": "Exam relevance",\n'
        '  "takeaway": "Revision takeaway"\n'
        "}\n"
        "]\n\n"

        "SOURCE MATERIAL:\n"
        + source_text
    )

    return prompt


# ============================================================
# GEMINI
# ============================================================

def generate_news(
    sources,
    number,
):

    if not sources:
        return []

    sources = sources[:40]

    prompt = make_prompt(
        sources,
        number,
    )

    # Current model first, then fallbacks
    models = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    ]

    for model in models:

        print(
            "Trying Gemini model:",
            model,
        )

        try:

            response = gemini.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            text = response.text

            if not text:
                print("Empty Gemini response.")
                continue

            text = text.strip()

            if text.startswith("```"):

                text = re.sub(
                    r"^```json",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )

                text = re.sub(
                    r"^```",
                    "",
                    text,
                )

                text = re.sub(
                    r"```$",
                    "",
                    text,
                )

                text = text.strip()

            result = json.loads(text)

            if not isinstance(
                result,
                list,
            ):
                print(
                    "Gemini returned non-list JSON."
                )
                continue

            print(
                "Gemini generated:",
                len(result),
                "articles",
            )

            return result

        except Exception as error:

            print(
                "Gemini ERROR:",
                str(error),
            )

            time.sleep(2)

    return []


# ============================================================
# CONVERT GEMINI RESULT
# ============================================================

def convert_articles(
    generated,
    sources,
    existing_hashes,
):

    articles = []

    for item in generated:

        if not isinstance(
            item,
            dict,
        ):
            continue

        source_id = item.get(
            "source_id"
        )

        try:
            source_id = int(
                source_id
            )
        except Exception:
            continue

        if source_id < 0:
            continue

        if source_id >= len(sources):
            continue

        source = sources[source_id]

        headline = clean(
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

        key = make_hash(
            headline,
            source["url"],
        )

        if key in existing_hashes:
            continue

        category = clean(
            item.get(
                "category",
                "National",
            )
        )

        story_lead = clean(
            item.get(
                "story_lead",
                "",
            )
        )

        if not story_lead:
            story_lead = source["summary"]

        bullets_raw = item.get(
            "bullet_points",
            [],
        )

        if not isinstance(
            bullets_raw,
            list,
        ):
            bullets_raw = []

        bullets = []

        for bullet in bullets_raw:

            value = clean(bullet)

            if value:
                bullets.append(value)

        full_text = clean(
            item.get(
                "full_article_text",
                "",
            )
        )

        if not full_text:

            full_text = extract_article(
                source["url"]
            )

        if not full_text:
            full_text = story_lead

        location = clean(
            item.get(
                "key_locations",
                "",
            )
        )

        important_date = clean(
            item.get(
                "important_dates",
                "",
            )
        )

        key_facts = clean(
            item.get(
                "key_facts",
                "",
            )
        )

        exam_relevance = clean(
            item.get(
                "exam_relevance",
                "",
            )
        )

        takeaway = clean(
            item.get(
                "takeaway",
                "",
            )
        )

        article = {
            "id": 0,
            "category": category or "National",
            "headline": headline,
            "story_lead": story_lead,
            "bullet_points": bullets,
            "full_article_text": full_text,
            "key_locations": location,
            "important_dates": important_date,
            "key_facts": key_facts,
            "exam_relevance": exam_relevance,
            "takeaway": takeaway,
            "source_name": source["source_name"],
            "source_url": source["url"],
            "image_url": source["image_url"],
            "published_date": TODAY,
        }

        articles.append(article)

        existing_hashes.add(key)

    return articles


# ============================================================
# ARTICLE TEXT EXTRACTION
# ============================================================

def extract_article(url):

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

        for tag in soup(
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
            tag.decompose()

        paragraphs = []

        for paragraph in soup.find_all("p"):

            text = clean(
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
            paragraphs[:10]
        )

    except Exception:
        return ""


# ============================================================
# UPDATE TODAY
# ============================================================

def update_today():

    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )

    old_news = load_today()

    print(
        "Existing articles:",
        len(old_news),
    )

    existing_hashes = set()

    for article in old_news:

        if not isinstance(
            article,
            dict,
        ):
            continue

        old_title = article.get(
            "headline",
            "",
        )

        old_url = article.get(
            "source_url",
            "",
        )

        existing_hashes.add(
            make_hash(
                old_title,
                old_url,
            )
        )

    if len(old_news) >= MAX_DAILY_COUNT:

        print(
            "Daily maximum reached."
        )

        return old_news[
            :MAX_DAILY_COUNT
        ]

    sources = collect_news()

    if not sources:

        if old_news:
            return old_news

        raise RuntimeError(
            "No RSS news was collected."
        )

    if len(old_news) == 0:

        number = FIRST_RUN_COUNT

    else:

        remaining = (
            MAX_DAILY_COUNT
            - len(old_news)
        )

        number = min(
            UPDATE_COUNT,
            remaining,
        )

    print(
        "Articles requested from Gemini:",
        number,
    )

    generated = generate_news(
        sources,
        number,
    )

    if not generated:

        if old_news:

            print(
                "Gemini failed. "
                "Keeping previous news."
            )

            return old_news

        raise RuntimeError(
            "Gemini generated no articles."
        )

    new_articles = convert_articles(
        generated,
        sources,
        existing_hashes,
    )

    print(
        "Valid new articles:",
        len(new_articles),
    )

    all_news = old_news + new_articles

    all_news = all_news[
        :MAX_DAILY_COUNT
    ]

    for index, article in enumerate(
        all_news,
        start=1,
    ):
        article["id"] = index

    if not all_news:

        raise RuntimeError(
            "Final article count is zero."
        )

    return all_news


# ==============================================
