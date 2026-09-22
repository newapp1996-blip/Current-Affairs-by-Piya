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
from google.genai import types

# ============================================================
# GEMINI
# ============================================================

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

# ============================================================
# FALLBACK IMAGES
# ============================================================

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=800&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&auto=format&fit=crop",
]

# ============================================================
# DAILY MOTIVATIONAL QUOTES
# These rotate automatically according to the date.
# ============================================================

MOTIVATIONAL_QUOTES = [
    {
        "quote": "Success is the sum of small efforts, repeated day in and day out.",
        "author": "Robert Collier",
        "image_url": "https://images.unsplash.com/photo-1499750310107-5fef28a66643?w=900&auto=format&fit=crop"
    },
    {
        "quote": "The secret of getting ahead is getting started.",
        "author": "Mark Twain",
        "image_url": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=900&auto=format&fit=crop"
    },
    {
        "quote": "Success is not final; keep learning, keep improving, and keep moving forward.",
        "author": "AURA EXAM AI",
        "image_url": "https://images.unsplash.com/photo-1484417894907-623942c8ee29?w=900&auto=format&fit=crop"
    },
    {
        "quote": "Great things are done by a series of small things brought together.",
        "author": "Vincent van Gogh",
        "image_url": "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=900&auto=format&fit=crop"
    },
    {
        "quote": "Discipline is choosing between what you want now and what you want most.",
        "author": "Abraham Lincoln",
        "image_url": "https://images.unsplash.com/photo-1531482615713-2afd69097998?w=900&auto=format&fit=crop"
    },
    {
        "quote": "Do something today that your future self will thank you for.",
        "author": "AURA EXAM AI",
        "image_url": "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=900&auto=format&fit=crop"
    },
    {
        "quote": "Your future depends on what you do today.",
        "author": "Mahatma Gandhi",
        "image_url": "https://images.unsplash.com/photo-1532012197267-da84d127e765?w=900&auto=format&fit=crop"
    },
    {
        "quote": "Focus on progress, not perfection.",
        "author": "AURA EXAM AI",
        "image_url": "https://images.unsplash.com/photo-1499750310107-5fef28a66643?w=900&auto=format&fit=crop"
    },
    {
        "quote": "The harder you work for something, the greater you will feel when you achieve it.",
        "author": "AURA EXAM AI",
        "image_url": "https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=900&auto=format&fit=crop"
    },
    {
        "quote": "Believe you can and you're halfway there.",
        "author": "Theodore Roosevelt",
        "image_url": "https://images.unsplash.com/photo-1531297484001-80022131f5a1?w=900&auto=format&fit=crop"
    }
]

HINDI_MOTIVATIONAL_QUOTES = [
    {
        "quote": "सफलता छोटे-छोटे प्रयासों को लगातार दोहराने से मिलती है।",
        "author": "AURA EXAM AI",
        "image_url": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=900&auto=format&fit=crop"
    },
    {
        "quote": "आज की मेहनत ही आने वाले कल की सफलता की नींव है।",
        "author": "AURA EXAM AI",
        "image_url": "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=900&auto=format&fit=crop"
    },
    {
        "quote": "जो विद्यार्थी लगातार सीखता रहता है, वही आगे बढ़ता है।",
        "author": "AURA EXAM AI",
        "image_url": "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=900&auto=format&fit=crop"
    },
    {
        "quote": "अनुशासन वह रास्ता है जो सपनों को वास्तविकता में बदलता है।",
        "author": "AURA EXAM AI",
        "image_url": "https://images.unsplash.com/photo-1531482615713-2afd69097998?w=900&auto=format&fit=crop"
    },
    {
        "quote": "हार केवल तब होती है जब हम प्रयास करना छोड़ देते हैं।",
        "author": "AURA EXAM AI",
        "image_url": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=900&auto=format&fit=crop"
    }
]


def get_daily_motivation():
    """
    Selects motivational content based on the date.
    The quote automatically changes each day.
    """

    try:
        day_number = datetime.now().timetuple().tm_yday

        english_quote = MOTIVATIONAL_QUOTES[
            day_number % len(MOTIVATIONAL_QUOTES)
        ]

        hindi_quote = HINDI_MOTIVATIONAL_QUOTES[
            day_number % len(HINDI_MOTIVATIONAL_QUOTES)
        ]

        return {
            "english": english_quote,
            "hindi": hindi_quote
        }

    except Exception:
        return {
            "english": MOTIVATIONAL_QUOTES[0],
            "hindi": HINDI_MOTIVATIONAL_QUOTES[0]
        }


# ============================================================
# JUNK FILTER
# ============================================================

JUNK_PATTERNS = [
    r"subscribed with another email",
    r"logout and login",
    r"subscription benefits",
    r"premium stories",
    r"editorials, opinions",
    r"unlock these with subscription",
    r"the view from india",
    r"first day first show",
    r"today's cache",
    r"science for all",
    r"data point decoding",
    r"theedge at the cutting edge",
    r"health matters ramya kannan",
    r"the hindu on books",
    r"published - \w+ \d+, \d{4}",
    r"photo credit:.*$",
    r"download the app",
    r"terms of use",
    r"privacy policy",
    r"copyright",
    r"all rights reserved"
]


def clean_extracted_text(text):
    """Filters webpage junk and HTML artifacts."""

    if not text:
        return ""

    # Remove HTML
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)

    for pattern in JUNK_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def extract_image_from_entry(entry, article_html=None):
    """
    Attempts to extract an actual article image.
    Falls back to a stable image if unavailable.
    """

    # 1. media_content
    try:
        media_content = entry.get("media_content", [])
        if media_content:
            for media in media_content:
                url = media.get("url")
                if url and url.startswith("http"):
                    return url
    except Exception:
        pass

    # 2. media_thumbnail
    try:
        media_thumbnail = entry.get("media_thumbnail", [])
        if media_thumbnail:
            url = media_thumbnail[0].get("url")
            if url and url.startswith("http"):
                return url
    except Exception:
        pass

    # 3. enclosure
    try:
        enclosures = entry.get("enclosures", [])
        for enclosure in enclosures:
            url = enclosure.get("href") or enclosure.get("url")
            if url and url.startswith("http"):
                return url
    except Exception:
        pass

    # 4. Article og:image
    if article_html:
        try:
            soup = BeautifulSoup(article_html, "html.parser")

            og_image = soup.find(
                "meta",
                property="og:image"
            )

            if og_image and og_image.get("content"):
                url = og_image["content"]

                if url.startswith("http"):
                    return url

        except Exception:
            pass

    return None


# ============================================================
# RSS FETCHING
# ============================================================

def fetch_rss_feeds():
    """Fetches articles across multiple news sources."""

    rss_sources = [
        {
            "name": "PIB India",
            "url": "https://pib.gov.in/RssMain.aspx?ModId=6"
        },
        {
            "name": "Indian Express",
            "url": "https://indianexpress.com/section/india/feed/"
        },
        {
            "name": "BBC News",
            "url": "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"
        },
        {
            "name": "The Hindu",
            "url": "https://www.thehindu.com/news/national/feeder/default.rss"
        },
        {
            "name": "Dainik Jagran",
            "url": "https://www.jagran.com/rss/news/national.xml"
        },
        {
            "name": "Punjab Kesari",
            "url": "https://punjabkesari.in/rss/national.xml"
        }
    ]

    raw_articles = []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        }
    }

    for source in rss_sources:

        try:
            print(f"Fetching RSS: {source['name']}")

            feed = feedparser.parse(source["url"])

            if not feed.entries:
                print(f"No RSS entries found: {source['name']}")
                continue

            for entry in feed.entries[:7]:

                title = clean_extracted_text(
                    entry.get("title", "")
                )

                link = entry.get("link", "")

                summary = clean_extracted_text(
                    entry.get("summary", "")
                )

                clean_paragraphs = []
                article_html = None

                if link:

                    try:

                        res = requests.get(
                            link,
                            headers=headers,
                            timeout=10
                        )

                        if res.status_code == 200:

                            article_html = res.text

                            soup = BeautifulSoup(
                                res.text,
                                "html.parser"
                            )

                            for p in soup.find_all("p"):

                                p_text = clean_extracted_text(
                                    p.get_text(" ", strip=True)
                                )

                                if len(p_text.split()) > 10:

                                    clean_paragraphs.append(
                                        p_text
                                    )

                    except Exception as article_error:

                        print(
                            f"Article fetch failed "
                            f"{source['name']}: {article_error}"
                        )

                full_body = (
                    " ".join(clean_paragraphs[:7])
                    if clean_paragraphs
                    else summary
                )

                image_url = extract_image_from_entry(
                    entry,
                    article_html
                )

                if not image_url:

                    image_url = (
                        FALLBACK_IMAGES[
                            len(raw_articles)
                            % len(FALLBACK_IMAGES)
                        ]
                    )

                if title and (summary or full_body):

                    raw_articles.append({
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "full_body": full_body,
                        "source_name": source["name"],
                        "image_url": image_url
                    })

        except Exception as e:

            print(
                f"Error reading source "
                f"{source['name']}: {e}"
            )

    # Remove duplicate headlines
    unique_articles = []
    seen_titles = set()

    for article in raw_articles:

        normalized_title = re.sub(
            r"\s+",
            " ",
            article["title"].lower()
        ).strip()

        if normalized_title in seen_titles:
            continue

        seen_titles.add(normalized_title)
        unique_articles.append(article)

    # Shuffle while retaining variety
    random.shuffle(unique_articles)

    final_articles = unique_articles[:20]

    print(
        f"Total usable news articles: "
        f"{len(final_articles)}"
    )

    return final_articles


# ============================================================
# GEMINI CONTENT GENERATION
# ============================================================

def generate_daily_content(raw_articles):

    if not raw_articles:

        print("No raw news articles available.")

        return {
            "date": TODAY_DATE,
            "news": [],
            "quizzes": []
        }

    prompt = f"""
You are an expert Current Affairs Faculty for UPSC, SSC,
State PCS and other Indian competitive examinations.

Synthesize the following raw news feeds into original,
fact-focused study material.

RAW NEWS:
{json.dumps(raw_articles, ensure_ascii=False)}

CRITICAL RULES:

1. FACTUAL ACCURACY:
   Use only information supported by the supplied news.
   Do not invent facts, people, dates, locations or events.

2. NO N/A:
   Do not output "N/A" where meaningful information can be
   extracted from the supplied article.

3. ORIGINAL WRITING:
   Rewrite and synthesize the information into original
   study notes. Do not copy article wording.

4. HTML HIGHLIGHTING:
   In headline, full_article_text, important_locations,
   important_facts and relevant fields, important people,
   locations, ministries, government agencies and statutory
   bodies may be highlighted using:
   <b><u>ENTITY</u></b>

5. FULL ARTICLE:
   Write approximately 350-500 words when enough source
   information is available.

6. EXAM RELEVANCE:
   Clearly identify UPSC/SSC/State PCS relevance where
   applicable.

7. SOURCE:
   Preserve the original source URL and source name.

8. IMAGE:
   Use the supplied article image_url whenever possible.

9. QUIZ:
   Generate useful exam-oriented MCQs directly based on
   the generated news.
   Each question must have exactly four options.
   "answer" must be the zero-based option index.

10. DO NOT GENERATE FAKE NEWS.

JSON OUTPUT:

{{
  "date": "{TODAY_DATE}",

  "news": [
    {{
      "id": 1,
      "category": "NATIONAL",

      "headline":
        "Headline with <b><u>Important Entity</u></b>",

      "story_lead":
        "Concise key summary sentence.",

      "bullet_points": [
        "Important point 1",
        "Important point 2",
        "Important point 3"
      ],

      "full_article_text":
        "Original 350-500 word study article.",

      "exam_relevance":
        "UPSC GS Paper II / State PCS",

      "takeaway":
        "Core exam takeaway.",

      "important_locations":
        "<b><u>New Delhi</u></b>, India",

      "important_dates":
        "Relevant date or deadline from the source",

      "source_url":
        "Original source URL",

      "source_name":
        "Source Name",

      "important_facts": [
        "Important factual point",
        "Important factual point"
      ],

      "vocabulary_words": [
        {{
          "word": "Statutory",
          "meaning":
            "Authorized or defined by legislation."
        }}
      ],

      "image_url":
        "Original supplied image URL"
    }}
  ],

  "quizzes": [
    {{
      "question": "Question?",
      "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
      ],
      "answer": 0
    }}
  ]
}}
"""

    for model_name in [
        "gemini-2.5-flash",
        "gemini-1.5-flash"
    ]:

        for attempt in range(1, 4):

            try:

                print(
                    f"Generating content via "
                    f"{model_name} "
                    f"(Attempt {attempt})..."
                )

                response = client.models.generate_content(

                    model=model_name,

                    contents=prompt,

                    config=types.GenerateContentConfig(

                        response_mime_type="application/json",

                        temperature=0.3
                    )
                )

                generated = json.loads(response.text)

                # Basic validation
                if not isinstance(generated, dict):
                    raise ValueError(
                        "Gemini returned invalid JSON structure."
                    )

                if "news" not in generated:
                    raise ValueError(
                        "Generated data has no news field."
                    )

                if "quizzes" not in generated:
                    generated["quizzes"] = []

                generated["date"] = TODAY_DATE

                return generated

            except Exception as e:

                print(
                    f"Attempt {attempt} failed: {e}"
                )

                time.sleep(5)

    print("All Gemini attempts failed.")

    return {
        "date": TODAY_DATE,
        "news": [],
        "quizzes": []
    }


# ============================================================
# ARCHIVE DATE MANAGEMENT
# ============================================================

def get_available_dates():

    dates = set()

    data_directory = "data"

    if os.path.exists(data_directory):

        for filename in os.listdir(data_directory):

            if filename.endswith(".json"):

                date_part = filename[:-5]

                if re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}",
                    date_part
                ):
                    dates.add(date_part)

    dates.add(TODAY_DATE)

    return sorted(
        dates,
        reverse=True
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print(
        f"AURA EXAM AI DAILY UPDATE - {TODAY_DATE}"
    )
    print("=" * 60)

    os.makedirs("data", exist_ok=True)

    # --------------------------------------------------------
    # FETCH NEWS
    # --------------------------------------------------------

    raw_news = fetch_rss_feeds()

    # --------------------------------------------------------
    # GENERATE AI CONTENT
    # --------------------------------------------------------

    data = generate_daily_content(raw_news)

    # --------------------------------------------------------
    # SAFETY CHECK
    # Do not destroy a previously working daily file if
    # Gemini/RSS temporarily fails.
    # --------------------------------------------------------

    today_file = f"data/{TODAY_DATE}.json"

    if not data.get("news"):

        if os.path.exists(today_file):

            print(
                "New generation returned no news. "
                "Keeping existing today's file."
            )

            with open(
                today_file,
                "r",
                encoding="utf-8"
            ) as f:
                data = json.load(f)

        else:

            print(
                "WARNING: No news generated today."
         
