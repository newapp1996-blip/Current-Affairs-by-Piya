import os
import re
import json
import time
import hashlib
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai
from google.genai import types


# ============================================================
# AURA EXAM AI - CURRENT AFFAIRS UPDATER
# ============================================================

DATA_DIR = "data"
MASTER_FILE = "data.json"

FIRST_RUN_COUNT = 30
UPDATE_COUNT = 10
MAX_DAILY_COUNT = 30

IST = ZoneInfo("Asia/Kolkata")

TODAY = datetime.now(IST).strftime("%Y-%m-%d")
CURRENT_TIME = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured.")

gemini = genai.Client(api_key=API_KEY)


# ============================================================
# HTTP SETTINGS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}


# ============================================================
# NEWS SOURCES
# ============================================================

RSS_SOURCES = [
    {
        "id": "ht_india",
        "name": "Hindustan Times",
        "category": "India",
        "url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"
    },
    {
        "id": "toi_top",
        "name": "Times of India",
        "category": "India",
        "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"
    },
    {
        "id": "ndtv_top",
        "name": "NDTV",
        "category": "India",
        "url": "https://feeds.feedburner.com/ndtvnews-top-stories"
    },
    {
        "id": "bbc_world",
        "name": "BBC",
        "category": "World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml"
    },
    {
        "id": "bbc_india",
        "name": "BBC",
        "category": "India",
        "url": "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"
    },
    {
        "id": "google_india",
        "name": "Google News",
        "category": "India",
        "url": "https://news.google.com/rss/search?q=India&hl=en-IN&gl=IN&ceid=IN:en"
    },
    {
        "id": "google_world",
        "name": "Google News",
        "category": "World",
        "url": "https://news.google.com/rss/search?q=world&hl=en-IN&gl=IN&ceid=IN:en"
    },
    {
        "id": "google_sports",
        "name": "Google News",
        "category": "Sports",
        "url": "https://news.google.com/rss/search?q=sports&hl=en-IN&gl=IN&ceid=IN:en"
    },
    {
        "id": "google_science",
        "name": "Google News",
        "category": "Science & Technology",
        "url": "https://news.google.com/rss/search?q=science+technology&hl=en-IN&gl=IN&ceid=IN:en"
    },
    {
        "id": "google_economy",
        "name": "Google News",
        "category": "Economy",
        "url": "https://news.google.com/rss/search?q=economy+India&hl=en-IN&gl=IN&ceid=IN:en"
    },
    {
        "id": "google_environment",
        "name": "Google News",
        "category": "Environment",
        "url": "https://news.google.com/rss/search?q=environment+India&hl=en-IN&gl=IN&ceid=IN:en"
    },
    {
        "id": "google_health",
        "name": "Google News",
        "category": "Health",
        "url": "https://news.google.com/rss/search?q=health+India&hl=en-IN&gl=IN&ceid=IN:en"
    }
]


# ============================================================
# CATEGORY NORMALIZATION
# ============================================================

VALID_CATEGORIES = [
    "India",
    "World",
    "Sports",
    "Science & Technology",
    "Economy",
    "Environment",
    "Health"
]


def normalize_category(category):
    if not category:
        return "India"

    value = str(category).strip().lower()

    if "sport" in value or "cricket" in value:
        return "Sports"

    if "science" in value or "technology" in value or "tech" in value:
        return "Science & Technology"

    if "econom" in value or "business" in value or "market" in value:
        return "Economy"

    if "environment" in value or "climate" in value:
        return "Environment"

    if "health" in value or "medical" in value:
        return "Health"

    if "world" in value or "international" in value:
        return "World"

    return "India"


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = html.unescape(str(value))
    value = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def clean_url(url):
    if not url:
        return ""

    return str(url).strip()


def make_id(url, title):
    base = clean_url(url) or clean_text(title)

    digest = hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()[:12]

    return int(digest, 16) % 900000000 + 100000000


def safe_list(value):
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def safe_vocabulary(value):
    result = []

    if not isinstance(value, list):
        return result

    for item in value:
        if isinstance(item, dict):
            word = clean_text(item.get("word", ""))
            meaning = clean_text(
                item.get("meaning_hindi", "")
                or item.get("meaning", "")
            )

            if word:
                result.append({
                    "word": word,
                    "meaning_hindi": meaning
                })

    return result


# ============================================================
# RSS COLLECTION
# ============================================================

def collect_news():
    candidates = []

    for source in RSS_SOURCES:
        print("Reading:", source["name"], source["url"])

        try:
            response = requests.get(
                source["url"],
                headers=HEADERS,
                timeout=20
            )

            response.raise_for_status()

            feed = feedparser.parse(response.content)

            for item in feed.entries[:40]:
                title = clean_text(
                    item.get("title", "")
                )

                summary = clean_text(
                    item.get("summary", "")
                    or item.get("description", "")
                )

                link = clean_url(
                    item.get("link", "")
                )

                if not title or not link:
                    continue

                candidates.append({
                    "source_id": source["id"],
                    "source": source["name"],
                    "category": source["category"],
                    "title": title,
                    "summary": summary,
                    "url": link
                })

        except Exception as exc:
            print(
                "Source failed:",
                source["name"],
                str(exc)
            )

    return deduplicate_candidates(candidates)


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_candidates(items):
    unique = []
    seen_urls = set()
    seen_titles = set()

    for item in items:
        url = item["url"].lower().strip()

        title_key = re.sub(
            r"[^a-z0-9]+",
            "",
            item["title"].lower()
        )

        if url in seen_urls:
            continue

        if title_key and title_key in seen_titles:
            continue

        seen_urls.add(url)
        seen_titles.add(title_key)

        unique.append(item)

    return unique


# ============================================================
# LOAD EXISTING DATA
# ============================================================

def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except Exception as exc:
        print(
            "Could not read:",
            path,
            str(exc)
        )

        return default


def save_json(path, data):
    directory = os.path.dirname(path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


def load_today_data():
    path = os.path.join(
        DATA_DIR,
        TODAY + ".json"
    )

    data = load_json(
        path,
        {
            "date": TODAY,
            "news": []
        }
    )

    if not isinstance(data, dict):
        data = {
            "date": TODAY,
            "news": []
        }

    if not isinstance(data.get("news"), list):
        data["news"] = []

    data["date"] = TODAY

    return data


# ============================================================
# EXISTING ARTICLE URLS
# ============================================================

def existing_urls(news):
    urls = set()

    for article in news:
        url = clean_url(
            article.get("url", "")
        ).lower()

        if url:
            urls.add(url)

    return urls


# ============================================================
# SOURCE PAGE FETCH
# ============================================================

def fetch_source_text(url):
    if not url:
        return ""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for element in soup([
            "script",
            "style",
            "noscript",
            "svg",
            "nav",
            "footer",
            "header",
            "form"
        ]):
            element.decompose()

        paragraphs = []

        for paragraph in soup.find_all("p"):
            text_value = clean_text(
                paragraph.get_text(" ", strip=True)
            )

            if len(text_value) >= 40:
                paragraphs.append(text_value)

        text_value = "\n\n".join(
            paragraphs[:35]
        )

        return text_value[:12000]

    except Exception as exc:
        print(
            "Could not fetch article page:",
            url,
            str(exc)
        )

        return ""


# ============================================================
# GEMINI JSON CALL
# ============================================================

def call_gemini(prompt, retries=3):
    models = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite"
    ]

    last_error = None

    for model_name in models:

        for attempt in range(retries):

            try:
                print(
                    "Calling Gemini:",
                    model_name,
                    "attempt",
                    attempt + 1
                )

                response = gemini.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json"
                    )
                )

                text_value = response.text.strip()

                if text_value.startswith("```"):
                    text_value = re.sub(
                        r"^```json\s*",
                        "",
                        text_value,
                        flags=re.IGNORECASE
                    )

                    text_value = re.sub(
                        r"\s*```$",
                        "",
                        text_value
                    )

                return json.loads(text_value)

            except Exception as exc:
                last_error = exc

                print(
                    "Gemini error:",
                    str(exc)
                )

                time.sleep(2)

    raise RuntimeError(
        "Gemini failed: " + str(last_error)
    )


# ============================================================
# GEMINI ARTICLE GENERATION
# ============================================================

def generate_articles(candidates):
    if not candidates:
        return []

    prepared = []

    for index, candidate in enumerate(candidates):
        print(
            "Preparing source",
            index + 1,
            "of",
            len(candidates)
        )

        source_text = fetch_source_text(
            candidate["url"]
        )

        prepared.append({
            "index": index,
            "source_id": candidate["source_id"],
            "source": candidate["source"],
            "category": candidate["category"],
            "title": candidate["title"],
            "summary": candidate["summary"],
            "url": candidate["url"],
            "source_text": source_text
        })

        time.sleep(0.3)

    material = json.dumps(
        prepared,
        ensure_ascii=False
    )

    prompt = (
        "You are the editorial engine for AURA EXAM AI, "
        "an Indian competitive-exam current affairs platform. "
        "Create original, factual, exam-oriented notes from the "
        "supplied news sources.\n\n"

        "IMPORTANT RULES:\n"
        "1. Use only facts supported by the supplied title, summary "
        "and source text.\n"
        "2. Do not invent statistics, quotations, dates, schemes, "
        "organizations, events or statements.\n"
        "3. Do not copy long passages from the source.\n"
        "4. Write original summaries and analysis.\n"
        "5. If the supplied material does not establish a fact, "
        "do not manufacture it.\n"
        "6. Political, governmental and policy stories must use "
        "neutral factual language.\n"
        "7. Attribute claims to the relevant person, organization "
        "or source when necessary.\n"
        "8. Do not endorse or oppose any political party, candidate, "
        "government or policy.\n"
        "9. Do not rank political actors or predict election outcomes.\n"
        "10. Keep the article specifically connected to its supplied source.\n"
        "11. Do not create placeholder articles.\n"
        "12. Category must be one of: India, World, Sports, "
        "Science & Technology, Economy, Environment, Health.\n\n"

        "For every supplied news item return an object with these fields:\n"
        "source_id\n"
        "source\n"
        "category\n"
        "headline\n"
        "story_lead\n"
        "full_article_text\n"
        "background_context\n"
        "bullet_points\n"
        "key_facts\n"
        "key_locations\n"
        "important_dates\n"
        "exam_relevance\n"
        "upsc_analysis\n"
        "causes\n"
        "impacts\n"
        "challenges\n"
        "government_steps\n"
        "constitutional_or_policy_link\n"
        "way_forward\n"
        "mains_notes\n"
        "mains_questions\n"
        "takeaway\n"
        "prelims_facts\n"
        "vocabulary\n\n"

        "Field requirements:\n"
        "- headline: accurate and concise.\n"
        "- story_lead: 2-3 sentences.\n"
        "- full_article_text: 4-7 original paragraphs.\n"
        "- background_context: useful context for understanding the story.\n"
        "- bullet_points: 4-7 important points.\n"
        "- key_facts: 4-8 factual points.\n"
        "- key_locations: relevant places only.\n"
        "- important_dates: dates explicitly supported by the material.\n"
        "- exam_relevance: UPSC/competitive-exam relevance.\n"
        "- upsc_analysis: structured analytical discussion.\n"
        "- causes: relevant causes or drivers; use an empty array if not applicable.\n"
        "- impacts: important consequences.\n"
        "- challenges: important implementation or policy challenges.\n"
        "- government_steps: documented steps mentioned or clearly supported.\n"
        "- constitutional_or_policy_link: relevant constitutional article, law, "
        "policy, institution or framework only when supported or clearly relevant. "
        "Do not invent connections.\n"
        "- way_forward: balanced, evidence-based suggestions.\n"
        "- mains_notes: concise notes suitable for Mains answer preparation.\n"
        "- mains_questions: 2-3 probable descriptive questions.\n"
        "- takeaway: 2-4 sentence revision takeaway.\n"
        "- prelims_facts: 5-8 concise factual points.\n"
        "- vocabulary: 4-8 useful English words from the article with Hindi meanings. "
        "Return objects containing word and meaning_hindi.\n\n"

        "Return ONLY valid JSON in this structure:\n"
        "{"
        "\"articles\":["
        "{"
        "\"source_id\":\"\","
        "\"source\":\"\","
        "\"category\":\"\","
        "\"headline\":\"\","
        "\"story_lead\":\"\","
        "\"full_article_text\":\"\","
        "\"background_context\":\"\","
        "\"bullet_points\":[],"
        "\"key_facts\":[],"
        "\"key_locations\":[],"
        "\"important_dates\":[],"
        "\"exam_relevance\":\"\","
        "\"upsc_analysis\":\"\","
        "\"causes\":[],"
        "\"impacts\":[],"
        "\"challenges\":[],"
        "\"government_steps\":[],"
        "\"constitutional_or_policy_link\":\"\","
        "\"way_forward\":\"\","
        "\"mains_notes\":\"\","
        "\"mains_questions\":[],"
        "\"takeaway\":\"\","
        "\"prelims_facts\":[],"
        "\"vocabulary\":["
        "{"
        "\"word\":\"\","
        "\"meaning_hindi\":\"\""
        "}"
        "]"
        "}"
        "]"
        "}\n\n"

        "SUPPLIED NEWS MATERIAL:\n"
        + material
    )

    result = call_gemini(prompt)

    if not isinstance(result, dict):
        return []

    articles = result.get("articles", [])

    if not isinstance(articles, list):
        return []

    return articles


# ============================================================
# CONVERT GEMINI ARTICLES
# ============================================================

def convert_articles(generated, candidates):
    candidate_map = {}

    for candidate in candidates:
        candidate_map[
            candidate["source_id"] + "|" + candidate["url"]
        ] = candidate

    converted = []

    for item in generated:

        if not isinstance(item, dict):
            continue

        source_id = clean_text(
            item.get("source_id", "")
        )

        headline = clean_text(
            item.get("headline", "")
        )

        if not headline:
            continue

        source = clean_text(
            item.get("source", "")
        )

        category = normalize_category(
            item.get("category", "")
        )

        matching_candidate = None

        for candidate in candidates:
            if candidate["source_id"] == source_id:
                matching_candidate = candidate
                break

        if not matching_candidate:
            for candidate in candidates:
                if candidate["title"].lower() in headline.lower():
                    matching_candidate = candidate
                    break

        if not matching_candidate:
            continue

        url = matching_candidate["url"]

        article_id = make_id(
            url,
            headline
        )

        article = {
            "id": article_id,
            "source_id": source_id or matching_candidate["source_id"],
            "source": source or matching_candidate["source"],
            "category": category,
            "headline": headline,
            "story_lead": clean_text(
                item.get("story_lead", "")
            ),
            "full_article_text": clean_text(
                item.get("full_article_text", "")
            ),
            "background_context": clean_text(
                item.get("background_context", "")
            ),
            "bullet_points": safe_list(
                item.get("bullet_points")
            ),
            "key_facts": safe_list(
                item.get("key_facts")
            ),
            "key_locations": safe_list(
                item.get("key_locations")
            ),
            "important_dates": safe_list(
                item.get("important_dates")
            ),
            "exam_relevance": clean_text(
                item.get("exam_relevance", "")
            ),
            "upsc_analysis": clean_text(
                item.get("upsc_analysis", "")
            ),
            "causes": safe_list(
                item.get("causes")
            ),
            "impacts": safe_list(
                item.get("impacts")
            ),
            "challenges": safe_list(
                item.get("challenges")
            ),
            "government_steps": safe_list(
                item.get("government_steps")
            ),
            "constitutional_or_policy_link": clean_text(
                item.get(
                    "constitutional_or_policy_link",
                    ""
                )
            ),
            "way_forward": clean_text(
                item.get("way_forward", "")
            ),
            "mains_notes": clean_text(
                item.get("mains_notes", "")
            ),
            "mains_questions": safe_list(
                item.get("mains_questions")
            ),
            "takeaway": clean_text(
                item.get("takeaway", "")
            ),
            "prelims_facts": safe_list(
                item.get("prelims_facts")
            ),
            "vocabulary": safe_vocabulary(
                item.get("vocabulary")
            ),
            "image_url": "",
            "url": url,
            "published": TODAY
        }

        converted.append(article)

    return converted


# ============================================================
# MOTIVATION
# ============================================================

def generate_motivation():
    quotes = [
        "Small improvements every day create extraordinary results.",
        "Consistency turns preparation into performance.",
        "Read today. Revise tomorrow. Remember on exam day.",
        "Strong preparation is built one focused session at a time.",
        "Knowledge becomes power when it is revised and applied.",
        "Every current affair can become a better answer in the exam."
    ]

    index = (
        datetime.now(IST).timetuple().tm_yday
        % len(quotes)
    )

    return {
        "quote": quotes[index],
        "date": TODAY
    }


# ============================================================
# UPDATE MASTER DATA
# ============================================================

def get_available_dates():
    if not os.path.exists(DATA_DIR):
        return []

    dates = []

    for filename in os.listdir(DATA_DIR):

        if not filename.endswith(".json"):
            continue

        date_part = filename[:-5]

        if re.fullmatch(
            r"\d{4}-\d{2}-\d{2}",
            date_part
        ):
            dates.append(date_part)

    return sorted(
        dates,
        reverse=True
    )


def update_master(today_data):
    available_dates = get_available_dates()

    if TODAY not in available_dates:
        available_dates.insert(
            0,
            TODAY
        )

    available_dates = sorted(
        set(available_dates),
        reverse=True
    )

    master = {
        "current_date": TODAY,
        "available_dates": available_dates,
        "today": today_data,
        "motivation": generate_motivation(),
        "last_updated_ist": CURRENT_TIME
    }

    save_json(
        MASTER_FILE,
        master
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("AURA EXAM AI - CURRENT AFFAIRS UPDATE")
    print("=" * 60)

    print("IST time:", CURRENT_TIME)
    print("IST date:", TODAY)

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    today_data = load_today_data()

    old_news = today_data.get(
        "news",
        []
    )

    print(
        "Existing articles today:",
        len(old_news)
    )

    if len(old_news) >= MAX_DAILY_COUNT:
        print(
            "Daily limit reached:",
            MAX_DAILY_COUNT
        )

        update_master(today_data)

        print(
            "Master data refreshed."
        )

        return

    target_count = (
        FIRST_RUN_COUNT
        if len(old_news) == 0
        else min(
            UPDATE_COUNT,
            MAX_DAILY_COUNT - len(old_news)
        )
    )

    print(
        "Target new articles:",
        target_count
    )

    candidates = collect_news()

    print(
        "RSS candidates found:",
        len(candidates)
    )

    old_urls = existing_urls(
        old_news
    )

    fresh_candidates = []

    for candidate in candidates:
        url = candidate["url"].lower()

        if url in old_urls:
            continue

        fresh_candidates.append(
            candidate
        )

    print(
        "Fresh candidates:",
        len(fresh_candidates)
    )

    if not fresh_candidates:
        print(
            "No new RSS articles found."
        )

        save_json(
            os.path.join(
                DATA_DIR,
                TODAY + ".json"
            ),
            today_data
        )

        update_master(
            today_data
        )

        return

    fresh_candidates = fresh_candidates[
        :target_count
    ]

    generated = []

    batch_size = 10

    for start in range(
        0,
        len(fresh_candidates),
        batch_size
    ):
        batch = fresh_candidates[
            start:start + batch_size
        ]

        print(
            "Generating batch:",
            start + 1,
            "to",
            start + len(batch)
        )

        try:
            batch_generated = generate_articles(
                batch
            )

            generated.extend(
                batch_generated
            )

        except Exception as exc:
            print(
                "Generation batch failed:",
                str(exc)
            )

        time.sleep(1)

    new_articles = convert_articles(
        generated,
        fresh_candidates
    )

    print(
        "Generated valid articles:",
        len(new_articles)
    )

    # Final duplicate protection
    old_ids = set()

    for article in old_news:
        old_ids.add(
            str(article.get("id", ""))
        )

    added = 0

    for article in new_articles:

        if str(article["id"]) in old_ids:
            continue

        old_news.append(
            article
        )

        old_ids.add(
            str(article["id"])
        )

        added += 1

        if len(old_news) >= MAX_DAILY_COUNT:
            break

    # Keep newest additions first
    today_data["news"] = old_news

    today_data["date"] = TODAY

    today_data["last_updated_ist"] = CURRENT_TIME

    daily_path = os.path.join(
        DATA_DIR,
        TODAY + ".json"
    )

    save_json(
        daily_path,
        today_data
    )

    update_master(
        today_data
    )

    print("=" * 60)
    print("UPDATE COMPLETE")
    print("=" * 60)
    print("Date:", TODAY)
    print("New articles added:", added)
    print("Total articles today:", len(old_news))
    print("Daily file:", daily_path)
    print("Master file:", MASTER_FILE)
    print("=" * 60)


if __name__ == "__main__":
    main()
