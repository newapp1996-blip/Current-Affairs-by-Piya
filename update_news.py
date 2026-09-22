import os
import json
import time
import random
import re
from datetime import datetime

import feedparser
import requests
from bs4 import BeautifulSoup
from google import genai


# ============================================================
# CONFIGURATION
# ============================================================

TARGET_NEWS_COUNT = 15

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

DATA_DIR = "data"
MASTER_FILE = "data.json"

os.makedirs(DATA_DIR, exist_ok=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================
# RSS SOURCES
# ============================================================

RSS_FEEDS = [
    {
        "name": "PIB",
        "url": "https://pib.gov.in/RssMain.aspx",
    },
    {
        "name": "Indian Express",
        "url": "https://indianexpress.com/section/india/feed/",
    },
    {
        "name": "BBC News India",
        "url": "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml",
    },
    {
        "name": "The Hindu",
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
    },
    {
        "name": "Dainik Jagran",
        "url": "https://rss.jagran.com/rss/news-national.xml",
    },
    {
        "name": "Punjab Kesari",
        "url": "https://www.punjabkesari.in/rss/national.xml",
    },
]


# ============================================================
# FALLBACK IMAGES
# ============================================================

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1495020689067-958852a7765e",
    "https://images.unsplash.com/photo-1504711434969-e33886168f5c",
    "https://images.unsplash.com/photo-1500534623283-312aade485b7",
    "https://images.unsplash.com/photo-1521295121783-8a321d551ad2",
    "https://images.unsplash.com/photo-1585829365295-ab7cd400c167",
]


# ============================================================
# JUNK TEXT FILTER
# ============================================================

JUNK_PATTERNS = [
    "subscribe",
    "sign in",
    "login",
    "advertisement",
    "advertising",
    "cookie",
    "newsletter",
    "follow us",
    "share this",
    "read more",
    "click here",
    "download app",
    "terms of use",
    "privacy policy",
    "all rights reserved",
]


def is_junk_text(text):
    if not text:
        return True

    clean = re.sub(r"\s+", " ", text).strip()
    lower = clean.lower()

    if len(clean) < 40:
        return True

    for pattern in JUNK_PATTERNS:
        if pattern in lower:
            return True

    return False


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = BeautifulSoup(str(text), "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================================================
# EXTRACT IMAGE FROM RSS ENTRY
# ============================================================

def get_rss_image(entry):
    # media_content
    try:
        media_content = entry.get("media_content", [])

        for media in media_content:
            url = media.get("url")
            if url and url.startswith("http"):
                return url
    except Exception:
        pass

    # media_thumbnail
    try:
        thumbnails = entry.get("media_thumbnail", [])

        for thumb in thumbnails:
            url = thumb.get("url")
            if url and url.startswith("http"):
                return url
    except Exception:
        pass

    # enclosure
    try:
        enclosures = entry.get("enclosures", [])

        for enclosure in enclosures:
            url = enclosure.get("href") or enclosure.get("url")

            if url and url.startswith("http"):
                return url
    except Exception:
        pass

    # HTML inside description/summary
    try:
        html = entry.get("summary", "") or entry.get("description", "")

        soup = BeautifulSoup(html, "html.parser")
        image = soup.find("img")

        if image:
            src = image.get("src")

            if src and src.startswith("http"):
                return src
    except Exception:
        pass

    return ""


# ============================================================
# EXTRACT OG IMAGE FROM ARTICLE PAGE
# ============================================================

def get_og_image(url):
    try:
        response = requests.get(
            url,
            timeout=12,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                )
            },
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        meta = soup.find(
            "meta",
            attrs={"property": "og:image"}
        )

        if meta and meta.get("content"):
            image = meta["content"].strip()

            if image.startswith("http"):
                return image

    except Exception:
        pass

    return ""


# ============================================================
# EXTRACT ARTICLE TEXT
# ============================================================

def extract_article_text(url):
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                )
            },
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove irrelevant page sections
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

        paragraphs = []

        article = soup.find("article")

        if article:
            candidates = article.find_all("p")
        else:
            candidates = soup.find_all("p")

        for paragraph in candidates:
            text = clean_text(paragraph.get_text(" ", strip=True))

            if not is_junk_text(text):
                paragraphs.append(text)

        # Remove duplicates while preserving order
        unique_paragraphs = []

        for paragraph in paragraphs:
            if paragraph not in unique_paragraphs:
                unique_paragraphs.append(paragraph)

        return " ".join(unique_paragraphs[:20])

    except Exception as error:
        print(f"Article extraction failed: {error}")
        return ""


# ============================================================
# FETCH RSS FEEDS
# ============================================================

def fetch_rss_feeds():
    print("Fetching RSS feeds...")

    source_items = []
    seen_urls = set()
    seen_titles = set()

    for feed_info in RSS_FEEDS:

        print(f"Reading: {feed_info['name']}")

        try:
            feed = feedparser.parse(feed_info["url"])

            entries = feed.entries[:10]

            for entry in entries:

                title = clean_text(entry.get("title", ""))
                url = entry.get("link", "")

                if not title or not url:
                    continue

                normalized_title = re.sub(
                    r"[^a-z0-9]+",
                    " ",
                    title.lower()
                ).strip()

                if url in seen_urls:
                    continue

                if normalized_title in seen_titles:
                    continue

                seen_urls.add(url)
                seen_titles.add(normalized_title)

                summary = clean_text(
                    entry.get("summary", "")
                    or entry.get("description", "")
                )

                image_url = get_rss_image(entry)

                article_text = extract_article_text(url)

                if not article_text:
                    article_text = summary

                if not article_text:
                    article_text = title

                if not image_url:
                    image_url = get_og_image(url)

                if not image_url:
                    image_url = random.choice(FALLBACK_IMAGES)

                source_items.append(
                    {
                        "source_id": len(source_items) + 1,
                        "source_name": feed_info["name"],
                        "title": title,
                        "url": url,
                        "summary": summary[:1500],
                        "article_context": article_text[:7000],
                        "image_url": image_url,
                    }
                )

                # We only need enough material for Gemini
                if len(source_items) >= 60:
                    break

        except Exception as error:
            print(
                f"Could not read {feed_info['name']}: {error}"
            )

        if len(source_items) >= 60:
            break

    print(
        f"Collected {len(source_items)} unique source articles."
    )

    return source_items


# ============================================================
# PREPARE SOURCE MATERIAL FOR GEMINI
# ============================================================

def prepare_source_material(source_items):
    blocks = []

    for item in source_items:
        block = f"""
SOURCE_ID: {item['source_id']}
SOURCE_NAME: {item['source_name']}
TITLE: {item['title']}
URL: {item['url']}

SUMMARY:
{item['summary']}

ARTICLE_CONTEXT:
{item['article_context']}

------------------------------------------------------------
"""

        blocks.append(block)

    return "\n".join(blocks)


# ============================================================
# GEMINI PROMPT
# ============================================================

def build_prompt(source_material):
    return f"""
You are preparing a high-quality Daily Current Affairs section
for Indian students preparing for CBSE, UPSC, SSC, Banking,
Railway, CUET, JEE and other competitive examinations.

Today's date is {TODAY_DATE}.

Using ONLY the source material supplied below, select exactly
{TARGET_NEWS_COUNT} distinct and important current-affairs stories.

IMPORTANT RULES:

1. Return EXACTLY 15 news articles.
2. Every article must be based on ONE specific SOURCE_ID.
3. Do NOT mix unrelated source stories.
4. Do NOT invent facts.
5. Do NOT invent URLs.
6. Do NOT invent source names.
7. Do NOT invent image URLs.
8. The Python program will attach the original source URL,
   source name and image after your response.
9. The full_article_text must discuss ONLY the selected story.
10. Do not copy large portions of the source article verbatim.
11. Rewrite the information in clear original language.
12. Avoid duplicate stories.
13. Prefer nationally important developments.
14. Prefer developments useful for examinations.
15. Include dates, places, organisations, people and numbers
    only when supported by the source material.
16. Do not combine two unrelated events into one article.
17. Do not create generic filler stories.
18. Each article should be approximately 300–500 words.
19. The headline must accurately represent the selected story.
20. The story_lead must directly explain the same story.
21. All bullet points must relate to that same story.
22. key_facts must relate only to that story.
23. exam_relevance must explain why that particular story
    could matter for students.
24. takeaway must summarise that same story.

RETURN ONLY VALID JSON.

Required structure:

{{
  "date": "{TODAY_DATE}",
  "news": [
    {{
      "id": 1,
      "source_id": 123,
      "headline": "Specific headline",
      "story_lead": "Specific summary of this story",
      "bullet_points": [
        "Fact related to this story",
        "Fact related to this story",
        "Fact related to this story"
      ],
      "full_article_text": "Detailed article specifically about this story.",
      "key_locations": ["Location"],
      "important_dates": ["Date"],
      "key_facts": [
        "Fact 1",
        "Fact 2",
        "Fact 3"
      ],
      "exam_relevance": "Why this particular story is relevant for examinations.",
      "takeaway": "One concise takeaway from this story.",
      "entities": [
        "Organisation or person"
      ]
    }}
  ]
}}

SOURCE MATERIAL:

{source_material}
"""


# ============================================================
# CALL GEMINI
# ============================================================

def generate_with_gemini(source_material):
    prompt = build_prompt(source_material)

    models = [
        "gemini-2.5-flash",
        "gemini-1.5-flash",
    ]

    for model_name in models:

        for attempt in range(3):

            try:
                print(
                    f"Generating with {model_name} "
                    f"(attempt {attempt + 1}/3)..."
                )

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "temperature": 0.2,
                        "response_mime_type": "application/json",
                    },
                )

                text = response.text.strip()

                # Remove accidental markdown fences
                text = re.sub(
                    r"^```json\s*",
                    "",
                    text,
                    flags=re.IGNORECASE
                )

                text = re.sub(
                    r"\s*```$",
                    "",
                    text
                )

                data = json.loads(text)

                if validate_gemini_output(data):
                    print(
                        "Gemini returned 15 valid news articles."
                    )
                    return data

                print(
                    "Gemini output did not contain 15 valid articles."
                )

            except Exception as error:
                print(
                    f"Gemini generation error: {error}"
                )

                time.sleep(2)

    return None


# ============================================================
# VALIDATE GEMINI OUTPUT
# ============================================================

def validate_gemini_output(data):

    if not isinstance(data, dict):
        return False

    news = data.get("news")

    if not isinstance(news, list):
        return False

    if len(news) != TARGET_NEWS_COUNT:
        return False

    source_ids = set()

    for item in news:

        if not isinstance(item, dict):
            return False

        required_fields = [
            "source_id",
            "headline",
            "story_lead",
            "bullet_points",
            "full_article_text",
            "key_facts",
            "exam_relevance",
            "takeaway",
        ]

        for field in required_fields:
            if field not in item:
                return False

        try:
            source_id = int(item["source_id"])
        except Exception:
            return False

        if source_id in source_ids:
            return False

        source_ids.add(source_id)

        if not item["headline"]:
            return False

        if not item["full_article_text"]:
            return False

        if not isinstance(item["bullet_points"], list):
            return False

        if not isinstance(item["key_facts"], list):
            return False

    return True


# ============================================================
# ATTACH ORIGINAL SOURCE DATA
# ============================================================

def attach_source_metadata(data, source_items):

    source_map = {
        int(item["source_id"]): item
        for item in source_items
    }

    valid_news = []

    for index, news_item in enumerate(data["news"], start=1):

        try:
            source_id = int(news_item["source_id"])
        except Exception:
            continue

        source = source_map.get(source_id)

        if not source:
            continue

        news_item["id"] = index

        # Python, not Gemini, decides these values.
        news_item["source_name"] = source["source_name"]
        news_item["source_url"] = source["url"]
        news_item["image_url"] = source["image_url"]

        valid_news.append(news_item)

    if len(valid_news) != TARGET_NEWS_COUNT:
        raise ValueError(
            f"Only {len(valid_news)} articles could be mapped "
            f"to valid sources."
        )

    data["news"] = valid_news

    return data


# ============================================================
# MOTIVATIONAL QUOTES
# ============================================================

MOTIVATIONAL_QUOTES = [
    {
        "english": "Success is the sum of small efforts, repeated day in and day out.",
        "hindi": "सफलता छोटे-छोटे प्रयासों का परिणाम है, जिन्हें लगातार दोहराया जाता है।",
        "author": "Robert Collier",
        "image_url": (
            "https://images.unsplash.com/"
            "photo-1499750310107-5fef28a66643"
        ),
    },
    {
        "english": "The secret of getting ahead is getting started.",
        "hindi": "आगे बढ़ने का रहस्य शुरुआत करने में है।",
        "author": "Mark Twain",
        "image_url": (
            "https://images.unsplash.com/"
            "photo-1500530855697-b586d89ba3ee"
        ),
    },
    {
        "english": "Great things are done by a series of small things brought together.",
        "hindi": "बड़े काम छोटे-छोटे प्रयासों को जोड़कर पूरे होते हैं।",
        "author": "Vincent van Gogh",
        "image_url": (
            "https://images.unsplash.com/"
            "photo-1500534314209-a25ddb2bd429"
        ),
    },
    {
        "english": "It always seems impossible until it's done.",
        "hindi": "जब तक काम पूरा नहीं होता, वह असंभव ही लगता है।",
        "author": "Nelson Mandela",
        "image_url": (
            "https://images.unsplash.com/"
            "photo-1497366754035-f200968a6e72"
        ),
    },
    {
        "english": "Do something today that your future self will thank you for.",
        "hindi": "आज ऐसा काम करो जिसके लिए तुम्हारा भविष्य स्वयं तुम्हें धन्यवाद दे।",
        "author": "Unknown",
        "image_url": (
            "https://images.unsplash.com/"
            "photo-1499209974431-9dddcece7f88"
        ),
    },
]


def get_daily_motivation():
    day_number = datetime.now().timetuple().tm_yday

    return MOTIVATIONAL_QUOTES[
        day_number % len(MOTIVATIONAL_QUOTES)
    ]


# ============================================================
# AVAILABLE DATES
# ============================================================

def get_available_dates():

    dates = []

    if not os.path.isdir(DATA_DIR):
        return dates

    for filename in os.listdir(DATA_DIR):

        if not filename.endswith(".json"):
            continue

        date_string = filename[:-5]

        try:
            datetime.strptime(
                date_string,
                "%Y-%m-%d"
            )

            dates.append(date_string)

        except ValueError:
            continue

    dates.sort(reverse=True)

    return dates


# ============================================================
# LOAD EXISTING TODAY DATA
# =============================================
