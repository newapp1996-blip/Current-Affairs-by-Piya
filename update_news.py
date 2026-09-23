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

FIRST_RUN_COUNT = 30
UPDATE_COUNT = 10
MAX_DAILY_COUNT = 30

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured.")

gemini = genai.Client(api_key=API_KEY)


# ============================================================
# HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}


# ============================================================
# RSS SOURCES
# ============================================================

FEEDS = [
    {
        "name": "Hindustan Times - India",
        "url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
        "category": "India"
    },

    {
        "name": "Times of India",
        "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        "category": "India"
    },

    {
        "name": "NDTV",
        "url": "https://feeds.feedburner.com/ndtvnews-top-stories",
        "category": "India"
    },

    {
        "name": "BBC World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "category": "World"
    },

    {
        "name": "BBC India",
        "url": "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml",
        "category": "India"
    },

    {
        "name": "Google News - India",
        "url": "https://news.google.com/rss/search?q=India&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "India"
    },

    {
        "name": "Google News - World",
        "url": "https://news.google.com/rss/search?q=world&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "World"
    },

    {
        "name": "Google News - Science Technology",
        "url": "https://news.google.com/rss/search?q=science+technology&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "Science & Technology"
    },

    # ========================================================
    # SPORTS SOURCES
    # ========================================================

    {
        "name": "Google News - Sports India",
        "url": "https://news.google.com/rss/search?q=India+sports&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "Sports"
    },

    {
        "name": "Google News - Cricket",
        "url": "https://news.google.com/rss/search?q=cricket&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "Sports"
    },

    {
        "name": "Google News - Sports World",
        "url": "https://news.google.com/rss/search?q=world+sports&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "Sports"
    },

    {
        "name": "Google News - Football",
        "url": "https://news.google.com/rss/search?q=football&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "Sports"
    }
]


# ============================================================
# FALLBACK IMAGES
# ============================================================

FALLBACK_IMAGES = {
    "India": "https://images.unsplash.com/photo-1524492412937-b28074a5d7da",
    "World": "https://images.unsplash.com/photo-1521295121783-8a321d551ad2",
    "Science & Technology": "https://images.unsplash.com/photo-1518770660439-4636190af475",
    "Sports": "https://images.unsplash.com/photo-1461896836934-ffe607ba8211",
    "Economy": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44",
    "Environment": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e",
    "Health": "https://images.unsplash.com/photo-1505751172876-fa1923c5c528",
    "Government & Polity": "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620",
    "International Relations": "https://images.unsplash.com/photo-1451187580459-43490279c0fa",
    "Other": "https://images.unsplash.com/photo-1495020689067-958852a7765e"
}


# ============================================================
# TEXT CLEANING
# ============================================================

def clean(value):
    if value is None:
        return ""

    value = html.unescape(str(value))

    value = BeautifulSoup(
        value,
        "html.parser"
    ).get_text(" ", strip=True)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def valid_title(title):
    title = clean(title)

    if len(title) < 20:
        return False

    blocked = [
        "actual current-affairs headline",
        "current affairs headline",
        "sample headline",
        "test headline",
        "dummy headline",
        "placeholder headline"
    ]

    lower = title.lower()

    for item in blocked:
        if item in lower:
            return False

    return True


# ============================================================
# HASH
# ============================================================

def make_hash(title, url):
    raw = (
        clean(title).lower()
        + "|"
        + clean(url).lower()
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


# ============================================================
# RSS IMAGE
# ============================================================

def get_rss_image(entry):

    media_content = entry.get("media_content")

    if media_content:
        for item in media_content:
            if isinstance(item, dict):
                url = item.get("url")

                if url:
                    return url

    media_thumbnail = entry.get("media_thumbnail")

    if media_thumbnail:
        for item in media_thumbnail:
            if isinstance(item, dict):
                url = item.get("url")

                if url:
                    return url

    image = entry.get("image")

    if isinstance(image, dict):
        url = image.get("href")

        if url:
            return url

    return ""


# ============================================================
# WEBPAGE IMAGE
# ============================================================

def get_page_image(url):

    if not url:
        return ""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=12
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        og_image = soup.find(
            "meta",
            property="og:image"
        )

        if og_image:
            image_url = og_image.get("content")

            if image_url:
                return image_url

    except Exception:
        pass

    return ""


# ============================================================
# IMAGE
# ============================================================

def get_image(entry, url, category):

    image = get_rss_image(entry)

    if image:
        return image

    image = get_page_image(url)

    if image:
        return image

    return FALLBACK_IMAGES.get(
        category,
        FALLBACK_IMAGES["Other"]
    )


# ============================================================
# COLLECT RSS NEWS
# ============================================================

def collect_news():

    print("Collecting RSS news...")

    candidates = []
    seen = set()

    for feed in FEEDS:

        print(
            "SOURCE:",
            feed["name"]
        )

        try:

            response = requests.get(
                feed["url"],
                headers=HEADERS,
                timeout=20
            )

            if response.status_code != 200:

                print(
                    "RSS failed:",
                    response.status_code
                )

                continue

            parsed = feedparser.parse(
                response.content
            )

            count = 0

            for entry in parsed.entries[:30]:

                title = clean(
                    entry.get("title", "")
                )

                url = clean(
                    entry.get("link", "")
                )

                summary = clean(
                    entry.get(
                        "summary",
                        entry.get(
                            "description",
                            ""
                        )
                    )
                )

                if not valid_title(title):
                    continue

                if not url:
                    continue

                article_hash = make_hash(
                    title,
                    url
                )

                if article_hash in seen:
                    continue

                seen.add(article_hash)

                category = feed["category"]

                candidates.append(
                    {
                        "source_id": article_hash,
                        "source_name": feed["name"],
                        "source_category": category,
                        "title": title,
                        "url": url,
                        "summary": summary[:4000],
                        "image_url": get_image(
                            entry,
                            url,
                            category
                        )
                    }
                )

                count += 1

            print(
                "Articles collected:",
                count
            )

        except Exception as error:

            print(
                "RSS failed:",
                error
            )

    print(
        "TOTAL CANDIDATES:",
        len(candidates)
    )

    return candidates


# ============================================================
# JSON HELPERS
# ============================================================

def load_json(path):

    if not os.path.exists(path):
        return None

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            "Could not read JSON:",
            path,
            error
        )

        return None


def save_json(path, data):

    folder = os.path.dirname(path)

    if folder:
        os.makedirs(
            folder,
            exist_ok=True
        )

    temp_path = path + ".tmp"

    with open(
        temp_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    os.replace(
        temp_path,
        path
    )


# ============================================================
# TODAY'S EXISTING DATA
# ============================================================

def load_today():

    path = os.path.join(
        DATA_DIR,
        TODAY + ".json"
    )

    data = load_json(path)

    if not isinstance(data, dict):
        return []

    news = data.get(
        "news",
        []
    )

    if not isinstance(news, list):
        return []

    return news


# ============================================================
# GEMINI PROMPT
# ============================================================

def make_prompt(candidates, number_to_generate):

    source_text = []

    for item in candidates:

        source_text.append(
            "SOURCE_ID: "
            + item["source_id"]
            + "\nSOURCE: "
            + item["source_name"]
            + "\nCATEGORY: "
            + item["source_category"]
            + "\nTITLE: "
            + item["title"]
            + "\nURL: "
            + item["url"]
            + "\nSUMMARY: "
            + item["summary"]
            + "\n"
        )

    joined_sources = "\n".join(
        source_text
    )

    prompt = (
        "You are an expert current-affairs editor preparing "
        "high-quality study material for Indian UPSC Civil Services "
        "Examination aspirants.\n\n"

        "Today is "
        + TODAY
        + ".\n\n"

        "Select exactly "
        + str(number_to_generate)
        + " genuinely important current-affairs stories "
        "from the supplied sources.\n\n"

        "IMPORTANT SPORTS REQUIREMENT:\n"
        "Include approximately 4 to 6 important SPORTS stories "
        "in the final selection whenever sufficient credible "
        "sports stories are available. Sports may include cricket, "
        "football, athletics, badminton, hockey, tennis, chess, "
        "Olympics/Asian Games/Commonwealth Games, major international "
        "sporting events, Indian athletes, sports governance, "
        "records, awards and major sporting policies.\n\n"

        "Do not fill the sports quota with trivial match results. "
        "Prefer stories having national, international, governance, "
        "economic, social, scientific or examination relevance.\n\n"

        "GENERAL SELECTION:\n"
        "Prefer significant India, World, Economy, Government, "
        "Polity, International Relations, Environment, Science & "
        "Technology, Health and Sports developments.\n\n"

        "Use only the information supported by the supplied source "
        "material. Do not invent statistics, dates, statements, "
        "official decisions or quotations.\n\n"

        "For political, electoral or government-related stories, "
        "use neutral factual language. Distinguish documented facts "
        "from claims made by political actors or other sources. "
        "Do not endorse, oppose, rank or persuade regarding any "
        "political party, candidate or policy choice.\n\n"

        "For every selected story produce detailed study notes "
        "appropriate for UPSC preparation.\n\n"

        "The full article must be coherent and specific to that "
        "particular news story. Do not write generic current-affairs "
        "content.\n\n"

        "UPSC analysis should cover relevant background, causes, "
        "impacts, challenges, government/institutional measures, "
        "constitutional or policy connections where applicable, "
        "and a practical way forward where appropriate.\n\n"

        "Mains notes must be written so that a student can directly "
        "convert the material into a UPSC Mains answer.\n\n"

        "Return ONLY valid JSON.\n\n"

        "Return an array containing exactly "
        + str(number_to_generate)
        + " objects.\n\n"

        "Each object MUST contain these fields:\n"

        "source_id\n"
        "category\n"
        "headline\n"
        "story_lead\n"
        "bullet_points\n"
        "full_article_text\n"
        "background_context\n"
        "upsc_analysis\n"
        "mains_notes\n"
        "causes\n"
        "impacts\n"
        "challenges\n"
        "government_steps\n"
        "way_forward\n"
        "constitutional_or_policy_link\n"
        "prelims_facts\n"
        "mains_questions\n"
        "key_locations\n"
        "important_dates\n"
        "key_facts\n"
        "exam_relevance\n"
        "takeaway\n"
        "vocabulary\n\n"

        "bullet_points must be an array of strings.\n"
        "causes must be an array of strings.\n"
        "impacts must be an array of strings.\n"
        "challenges must be an array of strings.\n"
        "government_steps must be an array of strings.\n"
        "way_forward must be an array of strings.\n"
        "constitutional_or_policy_link must be an array of strings.\n"
        "prelims_facts must be an array of strings.\n"
        "mains_questions must be an array of strings.\n"
        "key_locations must be an array of strings.\n"
        "important_dates must be an array of strings.\n"
        "key_facts must be an array of strings.\n"
        "exam_relevance must be an array of strings.\n"
        "vocabulary must be an array of objects.\n\n"

        "Each vocabulary object must contain:\n"
        "{ \"word\": \"English word\", "
        "\"meaning_hindi\": \"Hindi meaning\" }\n\n"

        "Use 5 to 10 useful vocabulary words per article.\n\n"

        "The full_article_text should read like a concise "
        "newspaper-style explanation followed by useful study "
        "content, not as unrelated scraped paragraphs.\n\n"

        "UPSC analysis should be detailed but factually restrained.\n\n"

        "SOURCE MATERIAL:\n\n"
        + joined_sources
    )

    return prompt


# ============================================================
# GEMINI GENERATION
# ============================================================

def generate_news(candidates, number_to_generate):

    if not candidates:
        return []

    prompt = make_prompt(
        candidates,
        number_to_generate
    )

    print(
        "Articles requested from Gemini:",
        number_to_generate
    )

    models = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite"
    ]

    for model in models:

        print(
            "Trying Gemini model:",
            model
        )

        try:

            response = gemini.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            text = response.text or ""

            text = text.strip()

            if text.startswith("```"):
                text = re.sub(
                    r"^```(?:json)?",
                    "",
                    text
                )

                text = re.sub(
                    r"```$",
                    "",
                    text
                )

                text = text.strip()

            data = json.loads(text)

            if isinstance(data, dict):

                if "articles" in data:
                    data = data["articles"]

                elif "news" in data:
                    data = data["news"]

            if not isinstance(data, list):
                continue

            if len(data) == 0:
                continue

            print(
                "Gemini generated:",
                len(data),
                "articles"
            )

            return data

        except Exception as error:

            print(
                "Gemini ERROR:",
                error
            )

            time.sleep(2)

    return []


# ============================================================
# LIST CLEANING
# ============================================================

def clean_list(value):

    if not isinstance(value, list):
        return []

    result = []

    for item in value:

        if isinstance(item, dict):
            result.append(
                clean(
                    json.dumps(
                        item,
                        ensure_ascii=False
                    )
                )
            )

        else:
            value_text = clean(item)

            if value_text:
                result.append(
                    value_text
                )

    return result


# ============================================================
# VOCABULARY CLEANING
# ============================================================

def clean_vocabulary(value):

    if not isinstance(value, list):
        return []

    result = []

    for item in value:

        if not isinstance(item, dict):
            continue

        word = clean(
            item.get("word", "")
        )

        meaning = clean(
            item.get("meaning_hindi", "")
        )

        if not word or not meaning:
            continue

        result.append(
            {
                "word": word,
                "meaning_hindi": meaning
            }
        )

    return result


# ============================================================
# CONVERT GEMINI ARTICLES
# ============================================================

def convert_articles(generated, candidates):

    source_map = {}

    for source in candidates:
        source_map[
            source["source_id"]
        ] = source

    results = []

    seen = set()

    for item in generated:

        if not isinstance(item, dict):
            continue

        source_id = clean(
            item.get(
                "source_id",
                ""
            )
        )

        source = source_map.get(
            source_id
        )

        if not source:
            continue

        headline = clean(
            item.get(
                "headline",
                ""
            )
        )

        if not valid_title(headline):
            continue

        article_hash = make_hash(
            headline,
            source["url"]
        )

        if article_hash in seen:
            continue

        seen.add(article_hash)

        category = clean(
            item.get(
                "category",
                source["source_category"]
            )
        )

        if not category:
            category = source["source_category"]

        article = {
            "id": 0,

            "category": category,

            "headline": headline,

            "story_lead": clean(
                item.get(
                    "story_lead",
                    source["summary"]
                )
            ),

            "bullet_points": clean_list(
                item.get(
                    "bullet_points",
                    []
                )
            ),

            "full_article_text": clean(
                item.get(
                    "full_article_text",
                    ""
                )
            ),

            "background_context": clean(
                item.get(
                    "background_context",
                    ""
                )
            ),

            "upsc_analysis": clean(
                item.get(
                    "upsc_analysis",
                    ""
                )
            ),

            "mains_notes": clean(
                item.get(
                    "mains_notes",
                    ""
                )
            ),

            "causes": clean_list(
                item.get(
                    "causes",
                    []
                )
            ),

            "impacts": clean_list(
                item.get(
                    "impacts",
                    []
                )
            ),

            "challenges": clean_list(
                item.get(
                    "challenges",
                    []
                )
            ),

            "government_steps": clean_list(
                item.get(
                    "government_steps",
                    []
                )
            ),

            "way_forward": clean_list(
                item.get(
                    "way_forward",
                    []
                )
            ),

            "constitutional_or_policy_link": clean_list(
                item.get(
                    "constitutional_or_policy_link",
                    []
                )
            ),

            "prelims_facts": clean_list(
                item.get(
                    "prelims_facts",
                    []
                )
            ),

            "mains_questions": clean_list(
                item.get(
                    "mains_questions",
                    []
                )
            ),

            "key_locations": clean_list(
                item.get(
                    "key_locations",
                    []
                )
            ),

            "important_dates": clean_list(
                item.get(
                    "important_dates",
                    []
                )
            ),

            "key_facts": clean_list(
                item.get(
                    "key_facts",
                    []
                )
            ),

            "exam_relevance": clean_list(
                item.get(
                    "exam_relevance",
                    []
                )
            ),

            "takeaway": clean(
                item.get(
                    "takeaway",
                    ""
                )
            ),

            "vocabulary": clean_vocabulary(
                item.get(
                    "vocabulary",
                    []
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

            "published_date": TODAY
        }

        if not article[
            "full_article_text"
        ]:

            article[
                "full_article_text"
            ] = article[
                "story_lead"
            ]

        results.append(
            article
        )

    return results


# ============================================================
# FALLBACK ARTICLE EXTRACTION
# ============================================================

def extract_article(url):

    if not url:
        return ""

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        paragraphs = []

        for paragraph in soup.find_all("p"):

            text = clean(
                paragraph.get_text(
                    " ",
                    strip=True
                )
            )

            if len(text) < 80:
                continue

            paragraphs.append(
                text
            )

            if len(paragraphs) >= 8:
                break

        return "\n\n".join(
            paragraphs
        )

    except Exception:
        return ""


# ============================================================
# UPDATE TODAY
# ============================================================

def update_today():

    existing = load_today()

    print(
        "Existing articles:",
        len(existing)
    )

    if len(existing) >= MAX_DAILY_COUNT:

        print(
            "Daily limit reached:",
            MAX_DAILY_COUNT
        )

        existing = existing[
            :MAX_DAILY_COUNT
        ]

        for index, article in enumerate(
            existing,
            start=1
        ):
            article["id"] = index

        return existing

    candidates = collect_news()

    if not candidates:

        if existing:
            return existing

        raise RuntimeError(
            "No RSS news was collected."
        )

    existing_hashes = set()

    for article in existing:

        title = article.get(
            "headline",
            ""
        )

        url = article.get(
            "source_url",
            ""
        )

        existing_hashes.add(
            make_hash(
                title,
                url
            )
        )

    fresh_candidates = []

    for item in candidates:

        candidate_hash = make_hash(
            item["title"],
            item["url"]
        )

        if candidate_hash in existing_hashes:
            continue

        fresh_candidates.append(
            item
        )

    remaining = (
        MAX_DAILY_COUNT
        - len(existing)
    )

    if len(existing) == 0:

        requested = min(
            FIRST_RUN_COUNT,
            remaining
        )

    else:

        requested = min(
            UPDATE_COUNT,
            remaining
        )

    if requested <= 0:
        return existing

    generated = generate_news(
        fresh_candidates,
        requested
    )

    new_articles = convert_articles(
        generated,
        fresh_candidates
    )

    # ========================================================
    # SPORTS PRIORITY CHECK
    # ========================================================

    sports_existing = 0

    for article in existing:

        category = article.get(
            "category",
            ""
        ).lower()

        if "sport" in category:
            sports_existing += 1

    sports_new = 0

    for article in new_articles:

        category = article.get(
            "category",
            ""
        ).lower()

        if "sport" in category:
            sports_new += 1

    total_sports = (
        sports_existing
        + sports_new
    )

    print(
        "Sports articles currently:",
        total_sports
    )

    # --------------------------------------------------------
    # If sports are missing, make one additional sports request
    # --------------------------------------------------------

    if total_sports < 4 and len(existing) + len(new_articles) < MAX_DAILY_COUNT:

        sports_candidates = []

        for item in fresh_candidates:

            category = item.get(
                "source_category",
                ""
            ).lower()

            source_name = item.get(
                "source_name",
                ""
            ).lower()

            title = item.get(
                "title",
                ""
            ).lower()

            if (
                "sport" in category
                or "sport" in source_name
                or "cricket" in title
                or "football" in title
                or "tennis" in title
                or "athlete" in title
                or "olympic" in title
            ):
                sports_candidates.append(
                    item
                )

        if sports_candidates:

            needed = min(
                4 - total_sports,
                MAX_DAILY_COUNT
                - len(existing)
                - len(new_articles)
            )

            if needed > 0:

                print(
                    "Requesting additional sports articles:",
                    needed
                )

                sports_generated = generate_news(
                    sports_candidates,
                    needed
                )

                sports_articles = convert_articles(
                    sports_generated,
                    sports_candidates
                )

                existing_new_hashes = set()

                for article in new_articles:

                    existing_new_hashes.add(
                        make_hash(
                            article.get(
                                "headline",
                                ""
                            ),
                            article.get(
                                "source_url",
                                ""
                            )
                        )
                    )

                for article in sports_articles:

                    article_hash = make_hash(
                        article.get(
                            "headline",
                            ""
                        ),
                        article.get(
                            "source_url",
                            ""
                        )
                    )

                    if article_hash in existing_new_hashes:
                        continue

                    new_articles.append(
                        article
                    )

                    existing_new_hashes.add(
                        article_hash
                    )

    # ========================================================
    # FALLBACK IF GEMINI FAILED
    # ========================================================

    if not new_articles:

        if existing:

            print(
                "Gemini generated no usable new articles."
            )

            return existing

        raise RuntimeError(
            "Gemini generated no articles. "
            "No empty data file will be created."
        )

    combined = (
        existing
        + new_articles
    )

    # Remove duplicates one more time
    unique = []

    seen = set()

    for article in combined:

        article_hash = make_hash(
            article.get(
                "headline",
                ""
            ),
            article.get(
                "source_url",
                ""
            )
        )

        if article_hash in seen:
            continue

        seen.add(
            article_hash
        )

        unique.append(
            article
        )

    unique = unique[
        :MAX_DAILY_COUNT
    ]

    for index, article in enumerate(
        unique,
        start=1
    ):
        article["id"] = index

    print(
        "FINAL DAILY ARTICLE COUNT:",
        len(unique)
    )

    sports_count = 0

    for article in unique:

        category = article.get(
            "category",
            ""
        ).lower()

        if "sport" in category:
            sports_count += 1

    print(
        "FINAL SPORTS COUNT:",
        sports_count
    )

    return unique


# ============================================================
# AVAILABLE DATES
# ============================================================

def available_dates():

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    dates = []

    for filename in os.listdir(
        DATA_DIR
    ):

        if not filename.endswith(
            ".json"
        ):
            continue

        date_text = filename[
            :-5
        ]

        if re.match(
            r"^\d{4}-\d{2}-\d{2}$",
            date_text
        ):

            dates.append(
                date_text
            )

    if TODAY not in dates:
        dates.append(
            TODAY
        )

    dates = sorted(
        set(dates),
        reverse=True
    )

    return dates


# ============================================================
# MOTIVATION
# ============================================================

def motivation():

    quotes = [
        "Consistency compounds into excellence.",
        "Study with purpose. Revise with discipline.",
        "Small improvements every day create extraordinary results.",
        "Understand today. Remember tomorrow. Apply in the exam.",
        "Focused preparation turns information into knowledge.",
        "Discipline is the bridge between preparation and performance."
    ]

    day_number = datetime.now().timetuple().tm_yday

    return quotes[
        day_number % len(quotes)
    ]


# ============================================================
# MAIN
# ============================================================

def main():

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    news = update_today()

    daily_file = os.path.join(
        DATA_DIR,
        TODAY + ".json"
    )

    daily_payload = {
        "date": TODAY,
        "news": news
    }

    save_json(
        daily_file,
        daily_payload
    )

    dates = available_dates()

    master_payload = {
        "current_date": TODAY,

        "available_dates": dates,

        "today": {
            "date": TODAY,
            "news": news
        },

        "motivation": {
            "quote": motivation(),
            "date": TODAY
        }
    }

    save_json(
        MASTER_FILE,
        master_payload
    )

    print(
        "========================================"
    )

    print(
        "AURA EXAM AI UPDATE COMPLETE"
    )

    print(
        "DATE:",
        TODAY
    )

    print(
        "ARTICLES:",
        len(news)
    )

    print(
        "AVAILABLE DATES:",
        len(dates)
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
