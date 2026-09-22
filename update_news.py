import os
import json
import time
import random
import re
from datetime import datetime, timedelta

import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai


# ============================================================
# AURA EXAM AI
# DAILY CURRENT AFFAIRS GENERATOR
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

TARGET_NEWS_COUNT = 15


# ============================================================
# GEMINI
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable is not set."
    )

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9"
})


# ============================================================
# RSS SOURCES
# ============================================================

RSS_FEEDS = {

    "PIB": [
        "https://www.pib.gov.in/RssMain.aspx"
    ],

    "Indian Express": [
        "https://indianexpress.com/section/india/feed/",
        "https://indianexpress.com/section/world/feed/",
        "https://indianexpress.com/section/sports/feed/",
        "https://indianexpress.com/section/business/feed/"
    ],

    "BBC India": [
        "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"
    ],

    "The Hindu": [
        "https://www.thehindu.com/news/national/feeder/default.rss",
        "https://www.thehindu.com/news/international/feeder/default.rss",
        "https://www.thehindu.com/sport/feeder/default.rss",
        "https://www.thehindu.com/business/feeder/default.rss"
    ],

    "Dainik Jagran": [
        "https://www.jagran.com/rss/news-national.xml",
        "https://www.jagran.com/rss/news-international.xml"
    ],

    "Punjab Kesari": [
        "https://www.punjabkesari.in/rss/news.xml"
    ]
}


# ============================================================
# FALLBACK IMAGES
# ============================================================

FALLBACK_IMAGES = [

    "https://images.unsplash.com/photo-1504711434969-e33886168f5c"
    "?auto=format&fit=crop&w=1200&q=80",

    "https://images.unsplash.com/photo-1495020689067-958852a7765e"
    "?auto=format&fit=crop&w=1200&q=80",

    "https://images.unsplash.com/photo-1521295121783-8a321d551ad2"
    "?auto=format&fit=crop&w=1200&q=80",

    "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee"
    "?auto=format&fit=crop&w=1200&q=80"
]


# ============================================================
# JUNK TEXT FILTER
# ============================================================

JUNK_PATTERNS = [

    r"subscribe",
    r"sign in",
    r"log in",
    r"advertisement",
    r"advertising",
    r"cookie",
    r"newsletter",
    r"follow us",
    r"read more",
    r"share this",
    r"related stories",
    r"recommended",
    r"trending",
    r"comments?",
    r"download app",
    r"whatsapp",
    r"instagram",
    r"facebook",
    r"twitter",
    r"youtube",
    r"all rights reserved",
    r"copyright",
    r"terms of use",
    r"privacy policy"
]


# ============================================================
# TEXT CLEANER
# ============================================================

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
    ).strip()

    return text


def is_junk(text):

    if not text:
        return True

    text_lower = text.lower()

    for pattern in JUNK_PATTERNS:

        if re.search(
            pattern,
            text_lower
        ):
            return True

    if len(text) < 80:
        return True

    return False


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def extract_image_from_entry(entry):

    # media_content
    media_content = entry.get(
        "media_content",
        []
    )

    for media in media_content:

        url = media.get("url")

        if url:
            return url


    # media_thumbnail
    thumbnails = entry.get(
        "media_thumbnail",
        []
    )

    for thumb in thumbnails:

        url = thumb.get("url")

        if url:
            return url


    # enclosure
    enclosures = entry.get(
        "enclosures",
        []
    )

    for enclosure in enclosures:

        url = enclosure.get("href")

        if url:
            return url


    return None


# ============================================================
# OG IMAGE
# ============================================================

def extract_og_image(url):

    if not url:
        return None

    try:

        response = session.get(
            url,
            timeout=12
        )

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        meta = soup.find(
            "meta",
            property="og:image"
        )

        if meta:

            image = meta.get("content")

            if image:
                return image

    except Exception:
        pass

    return None


# ============================================================
# ARTICLE TEXT EXTRACTION
# ============================================================

def extract_article_text(url):

    if not url:
        return ""

    try:

        response = session.get(
            url,
            timeout=15
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        # Remove obvious junk sections

        for tag in soup([
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "form",
            "noscript"
        ]):

            tag.decompose()


        # Prefer article tag

        article = soup.find("article")

        if article:

            paragraphs = article.find_all("p")

        else:

            paragraphs = soup.find_all("p")


        cleaned = []

        for p in paragraphs:

            text = clean_text(
                p.get_text(" ", strip=True)
            )

            if is_junk(text):
                continue

            if len(text) < 80:
                continue

            cleaned.append(text)


        # Remove duplicates

        unique = []

        seen = set()

        for text in cleaned:

            key = re.sub(
                r"\W+",
                "",
                text.lower()
            )

            if key in seen:
                continue

            seen.add(key)

            unique.append(text)


        # Limit scraped material.
        # Gemini will use it only as source context,
        # NOT as the final article.

        return "\n".join(
            unique[:25]
        )


    except Exception as error:

        print(
            f"Article extraction failed: {error}"
        )

        return ""


# ============================================================
# RSS FETCH
# ============================================================

def fetch_rss_feeds():

    collected = []

    seen_urls = set()

    seen_titles = set()


    for source_name, feeds in RSS_FEEDS.items():

        for feed_url in feeds:

            print(
                f"Fetching RSS: {source_name} -> {feed_url}"
            )

            try:

                response = session.get(
                    feed_url,
                    timeout=20
                )

                if response.status_code != 200:

                    print(
                        f"RSS HTTP {response.status_code}"
                    )

                    continue


                feed = feedparser.parse(
                    response.content
                )


                for entry in feed.entries[:10]:

                    title = clean_text(
                        entry.get(
                            "title",
                            ""
                        )
                    )

                    link = (
                        entry.get(
                            "link",
                            ""
                        )
                        or ""
                    ).strip()


                    if not title or not link:
                        continue


                    title_key = re.sub(
                        r"\W+",
                        "",
                        title.lower()
                    )


                    if title_key in seen_titles:
                        continue


                    if link in seen_urls:
                        continue


                    seen_titles.add(
                        title_key
                    )

                    seen_urls.add(
                        link
                    )


                    summary = clean_text(
                        entry.get(
                            "summary",
                            ""
                        )
                    )


                    image_url = (
                        extract_image_from_entry(
                            entry
                        )
                    )


                    # Try article page only for useful
                    # supporting context.

                    article_text = ""

                    if len(summary) < 250:

                        article_text = (
                            extract_article_text(
                                link
                            )
                        )


                    if not image_url:

                        image_url = (
                            extract_og_image(
                                link
                            )
                        )


                    if not image_url:

                        image_url = random.choice(
                            FALLBACK_IMAGES
                        )


                    collected.append({

                        "source_name":
                            source_name,

                        "title":
                            title,

                        "url":
                            link,

                        "summary":
                            summary,

                        "article_context":
                            article_text,

                        "image_url":
                            image_url

                    })


                    print(
                        f"  + {title}"
                    )


            except Exception as error:

                print(
                    f"RSS error: {error}"
                )


    print(
        f"\nTotal unique source stories: "
        f"{len(collected)}"
    )


    return collected


# ============================================================
# SOURCE MATERIAL PREPARATION
# ============================================================

def prepare_source_material(items):

    material = []

    for index, item in enumerate(items):

        context = (
            item.get("article_context")
            or item.get("summary")
            or ""
        )


        # Keep context reasonably sized.

        context = context[:5000]


        material.append({

            "source_id":
                index + 1,

            "source":
                item["source_name"],

            "headline":
                item["title"],

            "url":
                item["url"],

            "context":
                context,

            "image_url":
                item["image_url"]

        })


    return material


# ============================================================
# GEMINI JSON CLEANER
# ============================================================

def clean_json_response(text):

    if not text:
        return ""

    text = text.strip()


    # Remove markdown code fences.

    text = re.sub(
        r"^```(?:json)?",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```$",
        "",
        text
    )


    # Find JSON object.

    start = text.find("{")

    end = text.rfind("}")

    if start >= 0 and end >= 0:

        text = text[
            start:end + 1
        ]


    return text.strip()


# ============================================================
# VALIDATE NEWS
# ============================================================

def validate_news_item(item):

    if not isinstance(
        item,
        dict
    ):
        return False


    required = [
        "headline",
        "story_lead",
        "bullet_points",
        "full_article_text",
        "exam_relevance",
        "source_url"
    ]


    for key in required:

        if key not in item:
            return False


        if item[key] is None:
            return False


    headline = str(
        item["headline"]
    ).strip()


    article = str(
        item["full_article_text"]
    ).strip()


    if len(headline) < 15:
        return False


    if len(article) < 250:
        return False


    if not isinstance(
        item["bullet_points"],
        list
    ):
        return False


    if len(item["bullet_points"]) < 2:
        return False


    return True


# ============================================================
# VALIDATE COMPLETE PAYLOAD
# ============================================================

def validate_generated_payload(data):

    if not isinstance(
        data,
        dict
    ):
        return False


    news = data.get(
        "news"
    )


    if not isinstance(
        news,
        list
    ):
        return False


    # CRITICAL:
    # We require all 15.

    if len(news) < TARGET_NEWS_COUNT:

        print(
            f"Gemini returned only "
            f"{len(news)} news items. "
            f"Need {TARGET_NEWS_COUNT}."
        )

        return False


    valid_news = []

    seen = set()


    for item in news:

        if not validate_news_item(
            item
        ):
            continue


        headline_key = re.sub(
            r"\W+",
            "",
            item["headline"].lower()
        )


        if headline_key in seen:
            continue


        seen.add(
            headline_key
        )

        valid_news.append(
            item
        )


    if len(valid_news) < TARGET_NEWS_COUNT:

        print(
            f"Only {len(valid_news)} "
            f"unique valid articles."
        )

        return False


    data["news"] = (
        valid_news[
            :TARGET_NEWS_COUNT
        ]
    )


    return True


# ============================================================
# GEMINI GENERATION
# ============================================================

def generate_daily_content(
    source_items
):

    if len(source_items) < 20:

        print(
            "WARNING: fewer than 20 source "
            "stories available."
        )


    source_material =
        prepare_source_material(
            source_items
        )


    source_json =
        json.dumps(
            source_material,
            ensure_ascii=False,
            indent=2
        )


    prompt = f"""
You are the senior current-affairs editor
for AURA EXAM AI.

Today is {TODAY_DATE}.

Create EXACTLY 15 high-quality current-affairs
articles for Indian competitive-exam students.

IMPORTANT:
You MUST return exactly 15 articles.

Do NOT return 8.
Do NOT return 10.
Do NOT return 12.
Return EXACTLY 15.

Use the supplied source material as factual
reference material.

Each article MUST correspond to one real
source story supplied below.

Do NOT invent a news event.

Do NOT combine unrelated stories.

Do NOT mix paragraphs from different stories.

Do NOT copy website navigation,
advertisements, cookie notices,
recommendation text, comments, or unrelated
paragraphs.

The "full_article_text" must be newly written
for THIS EXACT NEWS ITEM and must discuss
only this news event.

Each full article should be approximately
300-500 words.

The article should explain:

1. What happened
2. Who/which institution is involved
3. Where it happened
4. Important dates
5. Important facts
6. Why the development matters
7. Relevant background where useful
8. Exam relevance

Use factual and neutral language.

Prioritize:
- India
- Government and governance
- Economy/business
- International relations
- Science and technology
- Environment
- Defence
- Sports
- Important legal/judicial developments
- Important social developments
- Important reports/indexes
- Major international developments

Avoid:
- celebrity gossip
- entertainment unless nationally important
- trivial viral content
- opinion pieces
- duplicate stories
- rumours
- unverified claims

CATEGORY DISTRIBUTION:

Try to provide approximately:

National/Governance: 4
International: 3
Economy/Business: 2
Science/Environment/Defence: 2
Sports: 2
Other important current affairs: 2

This distribution is flexible if today's
important news requires adjustment.

SOURCE RULE:

Every article must use the correct source URL
from the supplied material.

Never assign the URL of one story to another story.

IMAGE RULE:

Use the image_url belonging to the selected
source story.

OUTPUT ONLY VALID JSON.

Use this exact structure:

{{
  "date": "{TODAY_DATE}",

  "news": [
    {{
      "id": 1,
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

      "key_locations": "...",

      "important_dates": "...",

      "key_facts": "...",

      "exam_relevance": "...",

      "takeaway": "...",

      "entities": [
        {{
          "name": "...",
          "role": "...",
          "party_and_state": "...",
          "bio_details": "..."
        }}
      ],

      "source_name": "...",

      "source_url": "...",

      "image_url": "..."
    }}
  ],

  "quizzes": [
    {{
      "question": "...",
      "options": [
        "...",
        "...",
        "..."
      ],
      "answer": 0
    }}
  ]
}}

IMPORTANT:
The "answer" value must be the zero-based
index of the correct option.

Create at least 15 quiz questions.

SOURCE MATERIAL:

{source_json}
"""


    models = [

        "gemini-2.5-flash",

        "gemini-2.0-flash",

        "gemini-1.5-flash"

    ]


    for attempt in range(3):

        model =
            models[
                min(
                    attempt,
                    len(models) - 1
                )
            ]


        print(
            f"\nGemini attempt "
            f"{attempt + 1}/3 "
            f"using {model}"
        )


        try:

            response =
                client.models.generate_content(
                    model=model,
                    contents=prompt
                )


            raw =
                getattr(
                    response
