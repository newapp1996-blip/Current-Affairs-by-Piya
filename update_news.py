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

# Initial run
FIRST_RUN_COUNT = 30

# Every later 3-hour update
UPDATE_COUNT = 10

IST = ZoneInfo("Asia/Kolkata")

TODAY = datetime.now(IST).strftime("%Y-%m-%d")
CURRENT_TIME = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured.")

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
# RSS SOURCES
# Existing sources preserved
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

    # --------------------------------------------------------
    # NEW INTERNATIONAL SOURCES
    # --------------------------------------------------------

    {
        "id": "cnn_world",
        "name": "CNN",
        "category": "World",
        "url": "http://rss.cnn.com/rss/edition_world.rss"
    },
    {
        "id": "aljazeera_world",
        "name": "Al Jazeera",
        "category": "World",
        "url": "https://www.aljazeera.com/xml/rss/all.xml"
    },
    {
        "id": "dw_world",
        "name": "DW",
        "category": "World",
        "url": "https://rss.dw.com/rdf/rss-en-world"
    },
    {
        "id": "france24_world",
        "name": "France 24",
        "category": "World",
        "url": "https://www.france24.com/en/rss"
    },

    # --------------------------------------------------------
    # EXISTING GOOGLE NEWS SOURCES
    # --------------------------------------------------------

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
# INDIAN LANGUAGE SUPPORT
# ============================================================

INDIAN_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "te": "Telugu",
    "mr": "Marathi",
    "ta": "Tamil",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "as": "Assamese",
    "or": "Odia",
    "ur": "Urdu",
    "sa": "Sanskrit",
    "ne": "Nepali",
    "kok": "Konkani",
    "mai": "Maithili",
    "doi": "Dogri",
    "mni": "Manipuri",
    "ks": "Kashmiri",
    "sd": "Sindhi",
    "sat": "Santali",
    "brx": "Bodo"
}


# ============================================================
# CATEGORY
# ============================================================

def normalize_category(category):
    value = str(category or "").lower()

    if "sport" in value or "cricket" in value:
        return "Sports"

    if (
        "science" in value
        or "technology" in value
        or "tech" in value
    ):
        return "Science & Technology"

    if (
        "econom" in value
        or "business" in value
        or "market" in value
    ):
        return "Economy"

    if (
        "environment" in value
        or "climate" in value
    ):
        return "Environment"

    if (
        "health" in value
        or "medical" in value
    ):
        return "Health"

    if (
        "world" in value
        or "international" in value
    ):
        return "World"

    return "India"


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = html.unescape(str(value))

    value = BeautifulSoup(
        value,
        "html.parser"
    ).get_text(" ", strip=True)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def safe_list(value):
    if isinstance(value, list):
        return [
            str(x).strip()
            for x in value
            if str(x).strip()
        ]

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def safe_vocabulary(value):
    result = []

    if not isinstance(value, list):
        return result

    for item in value:
        if not isinstance(item, dict):
            continue

        word = clean_text(
            item.get("word", "")
        )

        meaning = clean_text(
            item.get("meaning_hindi", "")
        )

        if word:
            result.append({
                "word": word,
                "meaning_hindi": meaning
            })

    return result


# ============================================================
# SAFE ENTITIES
# ============================================================

def safe_entities(value):
    result = {
        "people": [],
        "countries": [],
        "states": [],
        "places": []
    }

    if not isinstance(value, dict):
        return result

    for entity_type in result.keys():

        items = value.get(
            entity_type,
            []
        )

        if not isinstance(items, list):
            continue

        for item in items:

            if not isinstance(item, dict):
                continue

            name = clean_text(
                item.get("name", "")
            )

            wikipedia_url = clean_text(
                item.get("wikipedia_url", "")
            )

            if not name:
                continue

            result[entity_type].append({
                "name": name,
                "wikipedia_url": wikipedia_url
            })

    return result


# ============================================================
# SAFE TRANSLATIONS
# ============================================================

def safe_translations(value):
    result = {}

    if not isinstance(value, dict):
        return result

    for language_code in INDIAN_LANGUAGES.keys():

        if language_code == "en":
            continue

        translation = value.get(
            language_code
        )

        if not isinstance(
            translation,
            dict
        ):
            continue

        cleaned = {}

        for field in [
            "headline",
            "story_lead",
            "full_article_text",
            "background_context",
            "bullet_points",
            "key_facts",
            "key_locations",
            "important_dates"
        ]:

            field_value = translation.get(
                field
            )

            if isinstance(
                field_value,
                list
            ):
                cleaned[field] = [
                    clean_text(x)
                    for x in field_value
                    if clean_text(x)
                ]

            elif isinstance(
                field_value,
                str
            ):
                cleaned[field] = clean_text(
                    field_value
                )

        if cleaned:
            result[language_code] = cleaned

    return result


def make_id(url, title):

    base = str(url or title)

    digest = hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()[:12]

    return int(digest, 16) % 900000000 + 100000000


# ============================================================
# UNIQUE CANDIDATE ID
# ============================================================

def make_candidate_id(url, title):

    base = (
        str(url or "").strip()
        + "|"
        + str(title or "").strip()
    )

    return hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()[:20]


# ============================================================
# RSS
# ============================================================

def collect_news():

    candidates = []

    for source in RSS_SOURCES:

        print(
            "Reading:",
            source["name"]
        )

        try:

            response = requests.get(
                source["url"],
                headers=HEADERS,
                timeout=20
            )

            response.raise_for_status()

            feed = feedparser.parse(
                response.content
            )

            for item in feed.entries[:50]:

                title = clean_text(
                    item.get(
                        "title",
                        ""
                    )
                )

                summary = clean_text(
                    item.get(
                        "summary",
                        ""
                    )
                    or item.get(
                        "description",
                        ""
                    )
                )

                url = str(
                    item.get(
                        "link",
                        ""
                    )
                ).strip()

                if not title or not url:
                    continue

                candidate_id = make_candidate_id(
                    url,
                    title
                )

                candidates.append({

                    "source_id": source["id"],

                    "candidate_id": candidate_id,

                    "source": source["name"],
                    "category": source["category"],
                    "title": title,
                    "summary": summary,
                    "url": url
                })

        except Exception as exc:

            print(
                "Source failed:",
                source["name"],
                str(exc)
            )

    return deduplicate(
        candidates
    )


def deduplicate(items):

    result = []

    seen_urls = set()
    seen_titles = set()

    for item in items:

        url = (
            item["url"]
            .lower()
            .strip()
        )

        title_key = re.sub(
            r"[^a-z0-9]+",
            "",
            item["title"].lower()
        )

        if url in seen_urls:
            continue

        if title_key in seen_titles:
            continue

        seen_urls.add(url)
        seen_titles.add(title_key)

        result.append(item)

    return result


# ============================================================
# JSON
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

    except Exception:

        return default


def save_json(path, data):

    directory = os.path.dirname(path)

    if directory:

        os.makedirs(
            directory,
            exist_ok=True
        )

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


def load_today():

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

    if not isinstance(
        data,
        dict
    ):

        data = {
            "date": TODAY,
            "news": []
        }

    if not isinstance(
        data.get("news"),
        list
    ):

        data["news"] = []

    data["date"] = TODAY

    return data


# ============================================================
# SOURCE ARTICLE
# ============================================================

def fetch_article_text(url):

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
                paragraph.get_text(
                    " ",
                    strip=True
                )
            )

            if len(text_value) >= 40:

                paragraphs.append(
                    text_value
                )

        return "\n\n".join(
            paragraphs[:35]
        )[:12000]

    except Exception as exc:

        print(
            "Article fetch failed:",
            str(exc)
        )

        return ""


# ============================================================
# WIKIPEDIA
# ============================================================

def wikipedia_search(entity_name):

    try:

        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": entity_name,
                "format": "json",
                "utf8": 1,
                "srlimit": 1
            },
            headers=HEADERS,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        results = (
            data
            .get("query", {})
            .get("search", [])
        )

        if not results:
            return ""

        title = results[0].get(
            "title",
            ""
        )

        if not title:
            return ""

        return (
            "https://en.wikipedia.org/wiki/"
            + requests.utils.quote(
                title.replace(" ", "_"),
                safe="_()"
            )
        )

    except Exception as exc:

        print(
            "Wikipedia lookup failed:",
            entity_name,
            str(exc)
        )

        return ""


def enrich_entities_with_wikipedia(
    entities
):

    if not isinstance(
        entities,
        dict
    ):

        return safe_entities({})

    result = safe_entities(
        entities
    )

    for entity_type in result:

        for entity in result[
            entity_type
        ]:

            if not entity.get(
                "wikipedia_url"
            ):

                entity[
                    "wikipedia_url"
                ] = wikipedia_search(
                    entity["name"]
                )

                time.sleep(0.1)

    return result


# ============================================================
# GEMINI
# ============================================================

def call_gemini(prompt):

    models = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite"
    ]

    last_error = None

    for model_name in models:

        for attempt in range(3):

            try:

                response = gemini.models.generate_content(

                    model=model_name,

                    contents=prompt,

                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json"
                    )
                )

                text_value = (
                    response.text.strip()
                )

                if text_value.startswith(
                    "```"
                ):

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

                return json.loads(
                    text_value
                )

            except Exception as exc:

                last_error = exc

                print(
                    "Gemini error:",
                    str(exc)
                )

                time.sleep(2)

    raise RuntimeError(
        "Gemini failed: "
        + str(last_error)
    )


# ============================================================
# GENERATE ARTICLES + QUIZ + EXAM CLASSIFICATION
# ============================================================

def generate_articles(candidates):

    prepared = []

    for candidate in candidates:

        source_text = fetch_article_text(
            candidate["url"]
        )

        prepared.append({

            "candidate_id": candidate[
                "candidate_id"
            ],

            "source_id": candidate[
                "source_id"
            ],

            "source": candidate[
                "source"
            ],

            "category": candidate[
                "category"
            ],

            "title": candidate[
                "title"
            ],

            "summary": candidate[
                "summary"
            ],

            "url": candidate[
                "url"
            ],

            "source_text": source_text
        })

    material = json.dumps(
        prepared,
        ensure_ascii=False
    )

    language_instruction = """

For every article also create translations for the following
Indian languages:

hi = Hindi
bn = Bengali
te = Telugu
mr = Marathi
ta = Tamil
gu = Gujarati
kn = Kannada
ml = Malayalam
pa = Punjabi
as = Assamese
or = Odia
ur = Urdu
sa = Sanskrit
ne = Nepali
kok = Konkani
mai = Maithili
doi = Dogri
mni = Manipuri
ks = Kashmiri
sd = Sindhi
sat = Santali
brx = Bodo

English is the original language and must remain available.

Translations are required ONLY for the main news reading
content:

headline
story_lead
full_article_text
background_context
bullet_points
key_facts
key_locations
important_dates

Do not translate the quiz, vocabulary, URLs, source name,
Wikipedia URLs, or the clock.

Do not invent information while translating.
Preserve names, numbers, dates and factual meaning.
"""

    prompt = (

        "You are the editorial engine for AURA EXAM AI. "
        "Create factual current-affairs articles for Indian "
        "competitive-exam students.\n\n"

        "Use only the supplied source material. "
        "Do not invent facts. "
        "Do not copy long source passages. "
        "Create original educational notes.\n\n"

        "Political and government stories must remain neutral "
        "and factual. Do not endorse or oppose political parties, "
        "candidates or governments. Do not predict election results.\n\n"

        "For EVERY news item create EXACTLY ONE quiz question "
        "based specifically on that news item.\n\n"

        "The quiz must contain:\n"
        "question\n"
        "options: exactly 4 options\n"
        "correct_answer: the exact correct option text\n"
        "explanation\n\n"

        "For EVERY news item determine whether it is directly "
        "useful for Indian competitive examinations.\n\n"

        "Set exam_specific to TRUE when the news has meaningful "
        "relevance to exams such as UPSC/Civil Services, SSC, "
        "Banking/RBI, Railways, Defence examinations, State PSC, "
        "government examinations or similar Indian competitive "
        "examinations.\n\n"

        "Examples include:\n"
        "Indian government schemes and policies, constitutional "
        "issues, Parliament, legislation, Supreme Court, "
        "appointments, awards, reports, indices, economy, RBI, "
        "budget, international relations involving India, "
        "important organisations, defence, science and technology, "
        "environment, geography, census/demography, important "
        "days, summits, books/authors, sports achievements with "
        "exam relevance and major national developments.\n\n"

        "Do NOT mark every India news story as exam_specific. "
        "Routine crime, celebrity gossip, trivial local incidents "
        "and ordinary entertainment news should normally be FALSE.\n\n"

        "Identify important entities appearing in the article.\n"

        "Return:\n"
        "people\n"
        "countries\n"
        "states\n"
        "places\n\n"

        "Each entity must contain only:\n"
        "name\n"
        "wikipedia_url\n\n"

        "If you are not confident about the exact Wikipedia "
        "URL, return an empty wikipedia_url. Do not invent URLs.\n\n"

        "Return these article fields:\n"

        "candidate_id\n"
        "source_id\n"
        "source\n"
        "category\n"
        "exam_specific\n"
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
        "vocabulary\n"
        "entities\n"
        "translations\n"
        "quiz\n\n"

        "Vocabulary must contain objects with "
        "word and meaning_hindi.\n\n"

        + language_instruction

        +

        "\nReturn ONLY valid JSON:\n"

        "{"
        "\"articles\":["
        "{"
        "\"candidate_id\":\"\","
        "\"source_id\":\"\","
        "\"source\":\"\","
        "\"category\":\"\","
        "\"exam_specific\":false,"
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
        "],"

        "\"entities\":{"
        "\"people\":[],"
        "\"countries\":[],"
        "\"states\":[],"
        "\"places\":[]"
        "},"

        "\"translations\":{"
        "\"hi\":{"
        "\"headline\":\"\","
        "\"story_lead\":\"\","
        "\"full_article_text\":\"\","
        "\"background_context\":\"\","
        "\"bullet_points\":[],"
        "\"key_facts\":[],"
        "\"key_locations\":[],"
        "\"important_dates\":[]"
        "}"
        "},"

        "\"quiz\":{"
        "\"question\":\"\","
        "\"options\":[],"
        "\"correct_answer\":\"\","
        "\"explanation\":\"\""
        "}"
        "}"
        "]"
        "}\n\n"

        "SUPPLIED NEWS:\n"
        + material
    )

    result = call_gemini(
        prompt
    )

    if not isinstance(
        result,
        dict
    ):
        return []

    articles = result.get(
        "articles",
        []
    )

    if not isinstance(
        articles,
        list
    ):
        return []

    return articles


# ============================================================
# CONVERT
# ============================================================

def convert_articles(
    generated,
    candidates
):

    converted = []

    candidate_lookup = {}

    for candidate in candidates:

        candidate_lookup[
            candidate["candidate_id"]
        ] = candidate

    for item in generated:

        if not isinstance(
            item,
            dict
        ):
            continue

        candidate_id = clean_text(
            item.get(
                "candidate_id",
                ""
            )
        )

        candidate = candidate_lookup.get(
            candidate_id
        )

        if candidate is None:

            source_id = clean_text(
                item.get(
                    "source_id",
                    ""
                )
            )

            headline_temp = clean_text(
                item.get(
                    "headline",
                    ""
                )
            )

            for current in candidates:

                if (
                    current["source_id"]
                    == source_id
                    and (
                        current["title"].lower()
                        in headline_temp.lower()
                        or headline_temp.lower()
                        in current["title"].lower()
                    )
                ):

                    candidate = current
                    break

        if candidate is None:
            continue

        source_id = clean_text(
            item.get(
                "source_id",
                candidate["source_id"]
            )
        )

        headline = clean_text(
            item.get(
                "headline",
                ""
            )
        )

        if not headline:
            continue

        quiz = item.get(
            "quiz",
            {}
        )

        if not isinstance(
            quiz,
            dict
        ):
            quiz = {}

        options = safe_list(
            quiz.get(
                "options"
            )
        )

        correct_answer = clean_text(
            quiz.get(
                "correct_answer",
                ""
            )
        )

        if len(options) != 4:
            continue

        if correct_answer not in options:
            continue

        entities = enrich_entities_with_wikipedia(
            item.get(
                "entities",
                {}
            )
        )

        translations = safe_translations(
            item.get(
                "translations",
                {}
            )
        )

        article = {

            "id": make_id(
                candidate["url"],
                headline
            ),

            "candidate_id": candidate[
                "candidate_id"
            ],

            "source_id": source_id,

            "source": clean_text(
                item.get(
                    "source",
                    candidate["source"]
                )
            ),

            "category": normalize_category(
                item.get(
                    "category",
                    candidate["category"]
                )
            ),

            "exam_specific": bool(
                item.get(
                    "exam_specific",
                    False
                )
            ),

            "headline": headline,

            "story_lead": clean_text(
                item.get(
                    "story_lead",
                    ""
                )
            ),

            "full_article_text": clean_text(
                item.get(
                    "full_article_text",
                    ""
                )
            ),

            "background_context": clean_text(
                item.get(
                    "background_context",
                    ""
                )
            ),

            "bullet_points": safe_list(
                item.get(
                    "bullet_points"
                )
            ),

            "key_facts": safe_list(
                item.get(
                    "key_facts"
                )
            ),

            "key_locations": safe_list(
                item.get(
                    "key_locations"
                )
            ),

            "important_dates": safe_list(
                item.get(
                    "important_dates"
                )
            ),

            "exam_relevance": clean_text(
                item.get(
                    "exam_relevance",
                    ""
                )
            ),

            "upsc_analysis": clean_text(
                item.get(
                    "upsc_analysis",
                    ""
                )
            ),

            "causes": safe_list(
                item.get(
                    "causes"
                )
            ),

            "impacts": safe_list(
                item.get(
                    "impacts"
                )
            ),

            "challenges": safe_list(
                item.get(
                    "challenges"
                )
            ),

            "government_steps": safe_list(
                item.get(
                    "government_steps"
                )
            ),

            "constitutional_or_policy_link":
                clean_text(
                    item.get(
                        "constitutional_or_policy_link",
                        ""
                    )
                ),

            "way_forward": clean_text(
                item.get(
                    "way_forward",
                    ""
                )
            ),

            "mains_notes": clean_text(
                item.get(
                    "mains_notes",
                    ""
                )
            ),

            "mains_questions": safe_list(
                item.get(
                    "mains_questions"
                )
            ),

            "takeaway": clean_text(
                item.get(
                    "takeaway",
                    ""
                )
            ),

            "prelims_facts": safe_list(
                item.get(
                    "prelims_facts"
                )
            ),

            "vocabulary": safe_vocabulary(
                item.get(
                    "vocabulary"
                )
            ),

            "entities": entities,

            "translations": translations,

            "quiz": {

                "question": clean_text(
                    quiz.get(
                        "question",
                        ""
                    )
                ),

                "options": options,

                "correct_answer":
                    correct_answer,

                "explanation": clean_text(
                    quiz.get(
                        "explanation",
                        ""
                    )
                )
            },

            "url": candidate[
                "url"
            ],

            "image_url": "",

            "published": TODAY
        }

        converted.append(
            article
        )

    return converted


# ============================================================
# AUTOMATIC DAILY MOTIVATIONAL IMAGE
# ============================================================

def escape_svg_text(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def create_daily_motivation_image():

    motivation_dir = "motivation"

    os.makedirs(
        motivation_dir,
        exist_ok=True
    )

    image_path = os.path.join(
        motivation_dir,
        f"motivation_{TODAY}.svg"
    )

    quotes = [
        "CONSISTENCY BUILDS RESULTS",
        "STUDY TODAY. SUCCEED TOMORROW.",
        "YOUR PREPARATION DEFINES YOUR PERFORMANCE.",
        "ONE FOCUSED SESSION AT A TIME.",
        "REVISION TURNS KNOWLEDGE INTO MARKS.",
        "DISCIPLINE BEATS LAST-MINUTE PREPARATION.",
        "KEEP LEARNING. KEEP IMPROVING."
    ]

    day_number = (
        datetime.now(IST)
        .timetuple()
        .tm_yday
    )

    quote = quotes[
        day_number % len(quotes)
    ]

    # Different visual pattern every day
    pattern = day_number % 5

    if pattern == 0:
        accent = "#2563eb"
        accent2 = "#1e3a8a"
    elif pattern == 1:
        accent = "#16a34a"
        accent2 = "#166534"
    elif pattern == 2:
        accent = "#7c3aed"
        accent2 = "#4c1d95"
    elif pattern == 3:
        accent = "#ea580c"
        accent2 = "#9a3412"
    else:
        accent = "#0891b2"
        accent2 = "#164e63"

    quote_safe = escape_svg_text(
        quote
    )

    date_safe = escape_svg_text(
        datetime.now(IST).strftime(
            "%d %B %Y"
        )
    )

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg
    xmlns="http://www.w3.org/2000/svg"
    width="1600"
    height="900"
    viewBox="0 0 1600 900">

    <defs>
        <linearGradient
            id="background"
            x1="0"
            y1="0"
            x2="1"
            y2="1">

            <stop
                offset="0%"
                stop-color="{accent2}"/>

            <stop
                offset="100%"
                stop-color="{accent}"/>
        </linearGradient>

        <filter
            id="shadow"
            x="-20%"
            y="-20%"
            width="140%"
            height="140%">

            <feDropShadow
                dx="0"
                dy="12"
                stdDeviation="15"
                flood-opacity="0.25"/>
        </filter>
    </defs>

    <rect
        width="1600"
        height="900"
        fill="url(#background)"/>

    <circle
        cx="1320"
        cy="170"
        r="260"
        fill="#ffffff"
        opacity="0.08"/>

    <circle
        cx="1450"
        cy="700"
        r="360"
        fill="#ffffff"
        opacity="0.06"/>

    <circle
        cx="160"
        cy="760"
        r="260"
        fill="#ffffff"
        opacity="0.05"/>

    <rect
        x="170"
        y="150"
        width="1260"
        height="600"
        rx="45"
        fill="#ffffff"
        opacity="0.96"
        filter="url(#shadow)"/>

    <text
        x="800"
        y="270"
        text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif"
        font-size="38"
        font-weight="700"
        fill="{accent2}">
        AURA EXAM AI
    </text>

    <text
        x="800"
        y="390"
        text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif"
        font-size="68"
        font-weight="800"
        fill="#111827">
        {quote_safe}
    </text>

    <line
        x1="520"
        y1="455"
        x2="1080"
        y2="455"
        stroke="{accent}"
        stroke-width="8"
        stroke-linecap="round"/>

    <text
        x="800"
        y="545"
        text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif"
        font-size="34"
        font-weight="600"
        fill="#374151">
        CURRENT AFFAIRS • EXAM PREPARATION • SUCCESS
    </text>

    <text
        x="800"
        y="635"
        text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif"
        font-size="27"
        fill="#6b7280">
        {date_safe}
    </text>

    <text
        x="800"
        y="700"
        text-anchor="middle"
        font-family="Arial, Helvetica, sans-serif"
        font-size="25"
        fill="{accent2}">
        Stay focused. Keep learning. Keep moving forward.
    </text>

</svg>
'''

    with open(
        image_path,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(svg)

    print(
        "Daily motivational image created:",
        image_path
    )

    return image_path.replace(
        os.sep,
        "/"
    )


# ============================================================
# MOTIVATION
# ============================================================

def motivation():

    quotes = [
        "Consistency turns preparation into performance.",
        "Read today. Revise tomorrow. Remember on exam day.",
        "Knowledge becomes power when it is revised and applied.",
        "Every current affair can become a better answer in the exam.",
        "Strong preparation is built one focused session at a time."
    ]

    index = (
        datetime.now(
            IST
        ).timetuple().tm_yday
        % len(quotes)
    )

    image_path = create_daily_motivation_image()

    return {

        "quote": quotes[index],

        "date": TODAY,

        "image": image_path,

        "image_alt": (
            "Daily motivational image for students "
            "focused on examination preparation, "
            "study and academic success"
        )
    }


# ============================================================
# AVAILABLE DATES
# ============================================================

def available_dates():

    if not os.path.exists(
        DATA_DIR
    ):
        return []

    result = []

    for filename in os.listdir(
        DATA_DIR
    ):

        if not filename.endswith(
            ".json"
        ):
            continue

        date_value = filename[
            :-5
        ]

        if re.fullmatch(
            r"\d{4}-\d{2}-\d{2}",
            date_value
        ):

            result.append(
                date_value
            )

    return sorted(
        set(result),
        reverse=True
    )


# ============================================================
# MASTER FILE
# ============================================================

def update_master(
    today_data
):

    dates = available_dates()

    if TODAY not in dates:
        dates.append(TODAY)

    dates = sorted(
        set(dates),
        reverse=True
    )

    master = {

        "current_date": TODAY,

        "available_dates": dates,

        "today": today_data,

        "motivation": motivation(),

        "last_updated_ist":
            CURRENT_TIME
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
    print(
        "AURA EXAM AI CURRENT AFFAIRS"
    )
    print("=" * 60)

    print(
        "IST:",
        CURRENT_TIME
    )

    print(
        "DATE:",
        TODAY
    )

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    today_data = load_today()

    existing = today_data.get(
        "news",
        []
    )

    print(
        "Existing news:",
        len(existing)
    )

    # --------------------------------------------------------
    # First run = 30
    # Every later run = +10
    # NO 30 ARTICLE CAP
    # --------------------------------------------------------

    target = (
        FIRST_RUN_COUNT
        if len(existing) == 0
        else UPDATE_COUNT
    )

    print(
        "New articles requested:",
        target
    )

    candidates = collect_news()

    old_urls = set()

    for article in existing:

        url = str(
            article.get(
                "url",
                ""
            )
        ).lower().strip()

        if url:
            old_urls.add(
                url
            )

    fresh = []

    for candidate in candidates:

        if (
            candidate["url"]
            .lower()
            in old_urls
        ):
            continue

        fresh.append(
            candidate
        )

    # --------------------------------------------------------
    # Add only the required number.
    # Existing articles are NEVER deleted.
    # --------------------------------------------------------

    fresh = fresh[:target]

    print(
        "Fresh candidates:",
        len(fresh)
    )

    if not fresh:

        print(
            "No new articles available right now."
        )

        today_data[
            "last_updated_ist"
        ] = CURRENT_TIME

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

    generated = []

    batch_size = 10

    for start in range(
        0,
        len(fresh),
        batch_size
    ):

        batch = fresh[
            start:start + batch_size
        ]

        try:

            result = generate_articles(
                batch
            )

            generated.extend(
                result
            )

        except Exception as exc:

            print(
                "Generation failed:",
                str(exc)
            )

        time.sleep(1)

    new_articles = convert_articles(
        generated,
        fresh
    )

    existing_ids = set()

    for article in existing:

        existing_ids.add(
            str(
                article.get(
                    "id",
                    ""
                )
            )
        )

    added = 0

    for article in new_articles:

        article_id = str(
            article["id"]
        )

        if article_id in existing_ids:
            continue

        existing.append(
            article
        )

        existing_ids.add(
            article_id
        )

        added += 1

    today_data[
        "news"
    ] = existing

    today_data[
        "last_updated_ist"
    ] = CURRENT_TIME

    daily_file = os.path.join(
        DATA_DIR,
        TODAY + ".json"
    )

    save_json(
        daily_file,
        today_data
    )

    update_master(
        today_data
    )

    print("=" * 60)
    print(
        "UPDATE COMPLETE"
    )
    print(
        "Date:",
        TODAY
    )
    print(
        "Added:",
        added
    )
    print(
        "Total news:",
        len(existing)
    )
    print(
        "Total quizzes:",
        len(existing)
    )
    print(
        "Motivational image:",
        f"motivation/motivation_{TODAY}.svg"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
