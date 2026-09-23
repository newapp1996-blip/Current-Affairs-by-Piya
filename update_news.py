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


client = genai.Client(api_key=API_KEY)


# ============================================================
# HTTP
# ============================================================

HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
}


# ============================================================
# RSS SOURCES
# ============================================================

FEEDS = [

    {
        "id": "ht_india",
        "name": "Hindustan Times",
        "url":
            "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"
    },

    {
        "id": "toi",
        "name": "Times of India",
        "url":
            "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"
    },

    {
        "id": "ndtv",
        "name": "NDTV",
        "url":
            "https://feeds.feedburner.com/ndtvnews-top-stories"
    },

    {
        "id": "bbc_world",
        "name": "BBC World",
        "url":
            "https://feeds.bbci.co.uk/news/world/rss.xml"
    },

    {
        "id": "bbc_india",
        "name": "BBC India",
        "url":
            "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"
    },

    {
        "id": "google_india",
        "name": "Google News India",
        "url":
            "https://news.google.com/rss/search?q=India&hl=en-IN&gl=IN&ceid=IN:en"
    },

    {
        "id": "google_world",
        "name": "Google News World",
        "url":
            "https://news.google.com/rss/search?q=world&hl=en-IN&gl=IN&ceid=IN:en"
    },

    {
        "id": "google_science",
        "name": "Google News Science & Technology",
        "url":
            "https://news.google.com/rss/search?q=science+technology&hl=en-IN&gl=IN&ceid=IN:en"
    }
]


# ============================================================
# FALLBACK IMAGES
# ============================================================

FALLBACK_IMAGES = {

    "India":
        "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?auto=format&fit=crop&w=1200&q=80",

    "World":
        "https://images.unsplash.com/photo-1521295121783-8a321d551ad2?auto=format&fit=crop&w=1200&q=80",

    "Science":
        "https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=1200&q=80",

    "Technology":
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",

    "Business":
        "https://images.unsplash.com/photo-1556761175-b413da4baf72?auto=format&fit=crop&w=1200&q=80",

    "Sports":
        "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=1200&q=80",

    "Environment":
        "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1200&q=80"
}


# ============================================================
# HELPERS
# ============================================================

def clean(value):

    if value is None:
        return ""

    value = html.unescape(str(value))

    soup = BeautifulSoup(value, "html.parser")

    value = soup.get_text(" ", strip=True)

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
        "placeholder headline"
    ]

    low = title.lower()

    for item in blocked:

        if item in low:
            return False

    return True


def make_hash(title, url):

    text = (
        clean(title).lower()
        + "|"
        + clean(url).lower()
    )

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


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

    except Exception:

        return None


def save_json(path, data):

    folder = os.path.dirname(path)

    if folder:
        os.makedirs(folder, exist_ok=True)

    temporary = path + ".tmp"

    with open(
        temporary,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    os.replace(temporary, path)


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def get_rss_image(entry):

    try:

        if hasattr(entry, "media_content"):

            media = entry.media_content

            if media:

                for item in media:

                    url = item.get("url", "")

                    if url:
                        return url

        if hasattr(entry, "media_thumbnail"):

            media = entry.media_thumbnail

            if media:

                for item in media:

                    url = item.get("url", "")

                    if url:
                        return url

        for link in entry.get("links", []):

            link_type = link.get("type", "")

            href = link.get("href", "")

            if (
                "image" in link_type.lower()
                and href
            ):

                return href

    except Exception:
        pass

    return ""


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

        meta_names = [
            "og:image",
            "twitter:image",
            "twitter:image:src"
        ]

        for name in meta_names:

            tag = soup.find(
                "meta",
                attrs={"property": name}
            )

            if tag and tag.get("content"):
                return tag.get("content")

            tag = soup.find(
                "meta",
                attrs={"name": name}
            )

            if tag and tag.get("content"):
                return tag.get("content")

    except Exception:
        pass

    return ""


def choose_fallback_image(category, index):

    if category in FALLBACK_IMAGES:
        return FALLBACK_IMAGES[category]

    keys = list(FALLBACK_IMAGES.keys())

    return FALLBACK_IMAGES[
        keys[index % len(keys)]
    ]


def get_image(entry, url, category, index):

    image = get_rss_image(entry)

    if image:
        return image

    image = get_page_image(url)

    if image:
        return image

    return choose_fallback_image(
        category,
        index
    )


# ============================================================
# CATEGORY
# ============================================================

def guess_category(title, summary):

    text = (
        clean(title)
        + " "
        + clean(summary)
    ).lower()

    if any(
        word in text
        for word in [
            "india",
            "delhi",
            "mumbai",
            "government",
            "minister",
            "parliament",
            "supreme court",
            "isro"
        ]
    ):
        return "India"

    if any(
        word in text
        for word in [
            "ai ",
            "artificial intelligence",
            "technology",
            "software",
            "chip",
            "semiconductor",
            "google",
            "microsoft",
            "apple"
        ]
    ):
        return "Technology"

    if any(
        word in text
        for word in [
            "science",
            "space",
            "nasa",
            "research",
            "health",
            "climate"
        ]
    ):
        return "Science"

    if any(
        word in text
        for word in [
            "business",
            "economy",
            "market",
            "bank",
            "rupee",
            "trade",
            "company"
        ]
    ):
        return "Business"

    if any(
        word in text
        for word in [
            "sport",
            "cricket",
            "football",
            "tennis",
            "olympic"
        ]
    ):
        return "Sports"

    if any(
        word in text
        for word in [
            "environment",
            "forest",
            "wildlife",
            "pollution"
        ]
    ):
        return "Environment"

    return "World"


# ============================================================
# COLLECT RSS
# ============================================================

def collect_news():

    print("Collecting RSS news...")

    all_items = []

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
                    "  HTTP:",
                    response.status_code
                )

                continue

            parsed = feedparser.parse(
                response.content
            )

            count = 0

            for entry in parsed.entries[:40]:

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

                category = guess_category(
                    title,
                    summary
                )

                image = get_image(
                    entry,
                    url,
                    category,
                    len(all_items)
                )

                item = {
                    "source_id":
                        feed["id"],

                    "source_name":
                        feed["name"],

                    "title":
                        title,

                    "url":
                        url,

                    "summary":
                        summary,

                    "image_url":
                        image,

                    "category":
                        category
                }

                all_items.append(item)

                count += 1

            print(
                "  Articles collected:",
                count
            )

        except Exception as error:

            print(
                "  RSS failed:",
                error
            )

    print(
        "TOTAL CANDIDATES:",
        len(all_items)
    )

    return all_items


# ============================================================
# TODAY FILE
# ============================================================

def today_file():

    return os.path.join(
        DATA_DIR,
        TODAY + ".json"
    )


def load_today():

    path = today_file()

    data = load_json(path)

    if not isinstance(data, dict):
        return []

    news = data.get("news", [])

    if not isinstance(news, list):
        return []

    return news


# ============================================================
# GEMINI ENRICHMENT
# ============================================================

def build_prompt(items, number):

    source_text = []

    for index, item in enumerate(items):

        block = (
            "SOURCE NUMBER: "
            + str(index)
            + "\n"
            + "SOURCE ID: "
            + item["source_id"]
            + "\n"
            + "SOURCE: "
            + item["source_name"]
            + "\n"
            + "HEADLINE: "
            + item["title"]
            + "\n"
            + "SUMMARY: "
            + item["summary"]
            + "\n"
            + "URL: "
            + item["url"]
            + "\n"
        )

        source_text.append(block)

    prompt = (
        "You are the editor of a factual current-affairs website "
        "for Indian students preparing for competitive and school examinations.\n\n"

        "Select exactly "
        + str(number)
        + " important and distinct current-affairs stories from "
        "the supplied source material.\n\n"

        "IMPORTANT RULES:\n"
        "1. Use ONLY information supported by the supplied source material.\n"
        "2. Do NOT invent facts, names, numbers, dates or quotations.\n"
        "3. Do NOT create fictional stories.\n"
        "4. Keep each story specific to its selected source.\n"
        "5. Preserve the real source URL.\n"
        "6. Write a coherent article for that particular story.\n"
        "7. Do not mix facts from unrelated stories.\n"
        "8. Return valid JSON only.\n\n"

        "Return a JSON array with exactly these fields:\n"
        "source_number\n"
        "category\n"
        "headline\n"
        "story_lead\n"
        "bullet_points\n"
        "full_article_text\n"
        "key_locations\n"
        "important_dates\n"
        "key_facts\n"
        "exam_relevance\n"
        "takeaway\n\n"

        "headline must be a real headline based on the source.\n"
        "full_article_text should contain several coherent paragraphs.\n"
        "bullet_points, key_locations, important_dates and key_facts "
        "must be arrays of strings.\n\n"

        "SOURCE MATERIAL:\n\n"
        + "\n\n".join(source_text)
    )

    return prompt


def generate_articles(items, number):

    if not items:
        return []

    selected_items = items[:80]

    prompt = build_prompt(
        selected_items,
        number
    )

    models = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash"
    ]

    for model in models:

        print(
            "Trying Gemini model:",
            model
        )

        try:

            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            text = response.text

            if not text:
                continue

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

            parsed = json.loads(text)

            if isinstance(parsed, dict):

                parsed = parsed.get(
                    "articles",
                    []
                )

            if not isinstance(parsed, list):
                continue

            print(
                "Gemini generated:",
                len(parsed)
            )

            return parsed

        except Exception as error:

            print(
                "Gemini ERROR:",
                error
            )

    return []


# ============================================================
# CONVERT GEMINI ARTICLES
# ============================================================

def convert_articles(generated, candidates):

    output = []

    used = set()

    for article in generated:

        if not isinstance(article, dict):
            continue

        try:

            source_number = int(
                article.get(
                    "source_number",
                    -1
                )
            )

        except Exception:

            continue

        if (
            source_number < 0
            or source_number >= len(candidates)
        ):
            continue

        source = candidates[
            source_number
        ]

        title = clean(
            article.get(
                "headline",
                ""
            )
        )

        if not valid_title(title):
            continue

        source_hash = make_hash(
            title,
            source["url"]
        )

        if source_hash in used:
            continue

        used.add(source_hash)

        category = clean(
            article.get(
                "category",
                source["category"]
            )
        )

        if not category:
            category = source["category"]

        lead = clean(
            article.get(
                "story_lead",
                source["summary"]
            )
        )

        full_text = clean(
            article.get(
                "full_article_text",
                ""
            )
        )

        if not full_text:
            full_text = lead

        bullet_points = article.get(
            "bullet_points",
            []
        )

        if not isinstance(
            bullet_points,
            list
        ):
            bullet_points = []

        bullet_points = [
            clean(x)
            for x in bullet_points
            if clean(x)
        ]

        key_locations = article.get(
            "key_locations",
            []
        )

        if not isinstance(
            key_locations,
            list
        ):
            key_locations = []

        key_locations = [
            clean(x)
            for x in key_locations
            if clean(x)
        ]

        important_dates = article.get(
            "important_dates",
            []
        )

        if not isinstance(
            important_dates,
            list
        ):
            important_dates = []

        important_dates = [
            clean(x)
            for x in important_dates
            if clean(x)
        ]

        key_facts = article.get(
            "key_facts",
            []
        )

        if not isinstance(
            key_facts,
            list
        ):
            key_facts = []

        key_facts = [
            clean(x)
            for x in key_facts
            if clean(x)
        ]

        exam_relevance = clean(
            article.get(
                "exam_relevance",
                ""
            )
        )

        takeaway = clean(
            article.get(
                "takeaway",
                ""
            )
        )

        item = {
            "id": 0,

            "category": category,

            "headline": title,

            "story_lead": lead,

            "bullet_points": bullet_points,

            "full_article_text": full_text,

            "key_locations": key_locations,

            "important_dates": important_dates,

            "key_facts": key_facts,

            "exam_relevance": exam_relevance,

            "takeaway": takeaway,

            "source_name":
                source["source_name"],

            "source_url":
                source["url"],

            "image_url":
                source["image_url"],

            "published_date":
                TODAY
        }

        output.append(item)

    return output


# ============================================================
# FALLBACK ARTICLES
#
# If Gemini is temporarily unavailable, we still publish
# genuine RSS stories instead of leaving the page empty.
# ============================================================

def fallback_articles(candidates, number):

    output = []

    for index, source in enumerate(
        candidates[:number]
    ):

        title = source["title"]

        summary = source["summary"]

        if not summary:
            summary = (
                "This current-affairs story "
                "is based on the latest report "
                "published by the listed source."
            )

        item = {

            "id": 0,

            "category":
                source["category"],

            "headline":
                title,

            "story_lead":
                summary,

            "bullet_points":
                [
                    summary
                ],

            "full_article_text":
                summary,

            "key_locations":
                [],

            "important_dates":
                [],

            "key_facts":
                [],

            "exam_relevance":
                "Revise the main facts, "
                "institutions, locations and "
                "developments mentioned in this news story.",

            "takeaway":
                summary,

            "source_name":
                source["source_name"],

            "source_url":
                source["url"],

            "image_url":
                source["image_url"] or
                choose_fallback_image(
                    source["category"],
                    index
                ),

            "published_date":
                TODAY
        }

        output.append(item)

    return output


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def merge_news(old_news, new_news):

    combined = []

    seen = set()

    for item in old_news + new_news:

        title = clean(
            item.get(
                "headline",
                ""
            )
        )

        url = clean(
            item.get(
                "source_url",
                ""
            )
        )

        if not title:
            continue

        article_hash = make_hash(
            title,
            url
        )

        if article_hash in seen:
            continue

        seen.add(article_hash)

        item["id"] = len(combined)

        combined.append(item)

        if len(combined) >= MAX_DAILY_COUNT:
            break

    return combined


# ============================================================
# ENSURE UNIQUE IMAGE ASSIGNMENT
# ============================================================

def fix_duplicate_images(news):

    used_images = set()

    for index, item in enumerate(news):

        image = clean(
            item.get(
                "image_url",
                ""
            )
        )

        if (
            not image
            or image in used_images
        ):

            category = clean(
                item.get(
                    "category",
                    "World"
                )
            )

            image = choose_fallback_image(
                category,
                index
            )

        used_images.add(image)

        item["image_url"] = image

    return news


# ============================================================
# UPDATE TODAY
# ============================================================

def update_today():

    old_news = load_today()

    print(
        "Existing articles:",
        len(old_news)
    )

    if len(old_news) >= MAX_DAILY_COUNT:

        print(
            "Daily limit reached:",
            MAX_DAILY_COUNT
        )

        return old_news[:MAX_DAILY_COUNT]

    candidates = collect_news()

    if not candidates:

        print(
            "No RSS candidates found."
        )

        return old_news

    old_hashes = set()

    for item in old_news:

        old_hashes.add(
            make_hash(
                item.get(
                    "headline",
                    ""
                ),
                item.get(
                    "source_url",
                    ""
                )
            )
        )

    fresh_candidates = []

    for item in candidates:

        item_hash = make_hash(
            item["title"],
            item["url"]
        )

        if item_hash in old_hashes:
            continue

        fresh_candidates.append(item)

    print(
        "New candidates:",
        len(fresh_candidates)
    )

    if not fresh_candidates:

        print(
            "No new stories found."
        )

        return old_news

    if old_news:

        needed = min(
            UPDATE_COUNT,
            MAX_DAILY_COUNT - len(old_news)
        )

    else:

        needed = min(
            FIRST_RUN_COUNT,
            MAX_DAILY_COUNT
        )

    fresh_candidates = fresh_candidates[:40]

    generated = generate_articles(
        fresh_candidates,
        needed
    )

    new_articles = convert_articles(
        generated,
        fresh_candidates
    )

    # If Gemini fails, use the genuine RSS stories.
    if not new_articles:

        print(
            "Gemini did not produce valid articles."
        )

        print(
            "Using RSS fallback."
        )

        new_articles = fallback_articles(
            fresh_candidates,
            needed
        )

    final_news = merge_news(
        old_news,
        new_articles
    )

    final_news = fix_duplicate_images(
        final_news
    )

    for index, item in enumerate(final_news):
        item["id"] = index

    print(
        "FINAL DAILY COUNT:",
        len(final_news)
    )

    return final_news


# ============================================================
# AVAILABLE DATES
# ============================================================

def available_dates():

    dates = []

    if os.path.exists(DATA_DIR):

        for filename in os.listdir(DATA_DIR):

            if not filename.endswith(".json"):
                continue

            name = filename[:-5]

            if re.fullmatch(
                r"\d{4}-\d{2}-\d{2}",
                name
            ):

                dates.append(name)

    if TODAY not in dates:
        dates.append(TODAY)

    dates.sort(
        reverse=True
    )

    return dates


# ============================================================
# MOTIVATION
# ============================================================

def get_motivation():

    quotes = [

        "Consistency turns ordinary effort into extraordinary results.",

        "Study today so tomorrow becomes easier.",

        "Small progress every day creates a strong foundation.",

        "Focus on understanding, not just memorising.",

        "Discipline is built one productive session at a time.",

        "Your preparation today becomes your confidence tomorrow."
    ]

    index = (
        datetime.now().timetuple().tm_yday
        % len(quotes)
    )

    return quotes[index]


# ============================================================
# MAIN
# ============================================================

def main():

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    news = update_today()

    if not news:

        raise RuntimeError(
            "No current-affairs stories available."
        )

    daily_data = {

        "date":
            TODAY,

        "news":
            news
    }

    save_json(
        today_file(),
        daily_data
    )

    dates = available_dates()

    master = {

        "current_date":
            TODAY,

        "available_dates":
            dates,

        "today":
            daily_data,

        "motivation":
            {
                "quote":
                    get_motivation(),

                "date":
                    TODAY
            },

        "last_updated":
            datetime.now().isoformat()
    }

    save_json(
        MASTER_FILE,
        master
    )

    print("")
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
        "ARCHIVE DATES:",
        len(dates)
    )
    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
