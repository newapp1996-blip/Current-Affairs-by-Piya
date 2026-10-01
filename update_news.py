import os
import re
import json
import time
import hashlib
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote, urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from google import genai


# ============================================================
# AURA EXAM AI - CURRENT AFFAIRS UPDATER
# ============================================================
# PURPOSE
# ------------------------------------------------------------
# 1. Fetch fresh RSS news
# 2. Read the actual article
# 3. Classify the article correctly
# 4. Keep India / World / Sports / Science / Economy /
#    Environment / Health categories separate
# 5. Exam Corner contains ONLY high-value Indian exam news
# 6. Generate exam-oriented study material using Gemini
# 7. Preserve existing articles
# 8. Repair missing quiz / Hindi / entities
# 9. Automatically update every workflow run
# ============================================================


IST = ZoneInfo("Asia/Kolkata")
NOW = datetime.now(IST)
TODAY = NOW.strftime("%Y-%m-%d")
NOW_ISO = NOW.isoformat()

DATA_FILE = "data.json"
DATA_DIR = "data"

FIRST_RUN_COUNT = 30
UPDATE_COUNT = 9999

MAX_CANDIDATES_PER_SOURCE = 25
REQUEST_TIMEOUT = 15

# Version used to rebuild older articles when the content
# extraction/summary format changes.
CONTENT_VERSION = 3


# ============================================================
# EXAM CORNER KEYWORDS
# ------------------------------------------------------------
# IMPORTANT:
# These are NOT enough by themselves.
# Exam Corner also requires the article to be India-focused
# and to cross the exam relevance threshold.
# ============================================================

EXAM_HIGH_VALUE = (
    "upsc",
    "civil services",
    "ssc",
    "ibps",
    "rbi",
    "sebi",
    "niti aayog",
    "supreme court",
    "parliament",
    "cabinet",
    "union cabinet",
    "ministry",
    "government scheme",
    "yojana",
    "policy",
    "act",
    "bill",
    "constitution",
    "constitutional",
    "amendment",
    "committee",
    "commission",
    "report",
    "economic survey",
    "union budget",
    "budget 202",
    "census",
    "election commission",
    "finance commission",
    "gst council",
    "monetary policy",
    "fiscal policy",
    "foreign policy",
    "international relations",
    "defence",
    "defense",
    "military exercise",
    "armed forces",
    "missile",
    "border",
    "summit",
    "treaty",
    "agreement",
    "index",
    "ranking",
    "g20",
    "brics",
    "sco",
    "asean",
    "united nations",
    "world bank",
    "imf",
    "unesco",
    "wto",
    "cop30",
    "environment agreement",
)

EXAM_MEDIUM = (
    "appointment",
    "ordinance",
    "judiciary",
    "high court",
    "supreme court",
    "lok sabha",
    "rajya sabha",
    "rajya sabha",
    "ministry of finance",
    "ministry of defence",
    "ministry of external affairs",
    "ministry of home affairs",
    "ministry of education",
    "ministry of environment",
    "ministry of health",
    "central government",
    "state government",
    "regulator",
    "regulatory",
    "commission",
    "authority",
    "national mission",
    "national programme",
    "national program",
    "scheme",
    "initiative",
    "portal",
    "infrastructure project",
    "defence deal",
    "defense deal",
    "trade agreement",
    "free trade agreement",
    "fta",
)


# ============================================================
# TOPIC CLASSIFICATION KEYWORDS
# ============================================================

SPORTS = (
    "cricket",
    "football",
    "tennis",
    "olympics",
    "athlete",
    "match",
    "tournament",
    "fifa",
    "ipl",
    "hockey",
    "badminton",
    "wimbledon",
    "championship",
    "medal",
    "world cup",
    "paralympics",
)

HEALTH = (
    "hospital",
    "disease",
    "virus",
    "vaccine",
    "vaccination",
    "health",
    "medical",
    "doctor",
    "cancer",
    "medicine",
    "outbreak",
    "public health",
    "mental health",
    "healthcare",
    "epidemic",
    "pandemic",
    "drug trial",
    "clinical trial",
)

SCIENCE = (
    "space",
    "isro",
    "nasa",
    "artificial intelligence",
    "technology",
    "tech",
    "quantum",
    "semiconductor",
    "robot",
    "robotics",
    "research",
    "science",
    "satellite",
    "astronomy",
    "innovation",
    "rocket",
    "launch vehicle",
    "mission",
    "genome",
    "biotechnology",
    "nuclear",
)

ECONOMY = (
    "stock market",
    "sensex",
    "nifty",
    "inflation",
    "gdp",
    "economy",
    "rupee",
    "trade",
    "market",
    "finance",
    "rbi",
    "banking",
    "interest rate",
    "fiscal",
    "monetary policy",
    "repo rate",
    "forex",
    "investment",
    "tax",
    "gst",
    "unemployment",
    "employment data",
)

ENVIRONMENT = (
    "climate",
    "pollution",
    "forest",
    "wildlife",
    "biodiversity",
    "carbon",
    "emission",
    "flood",
    "drought",
    "environment",
    "greenhouse",
    "conservation",
    "wetland",
    "national park",
    "tiger reserve",
    "elephant reserve",
    "renewable energy",
    "solar energy",
    "climate change",
)

WORLD = (
    "united states",
    "us president",
    "ukraine",
    "russia",
    "china",
    "europe",
    "middle east",
    "israel",
    "palestine",
    "iran",
    "pakistan",
    "bangladesh",
    "sri lanka",
    "nepal",
    "afghanistan",
    "foreign",
    "global",
    "world",
    "un summit",
    "nato",
    "european union",
    "european commission",
    "white house",
    "beijing",
    "moscow",
    "washington",
)


# ============================================================
# GEMINI MODELS
# ============================================================

GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]


# ============================================================
# RSS SOURCES
# ============================================================

RSS_SOURCES = [
    (
        "HT India",
        "India",
        "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
    ),
    (
        "Times of India",
        "India",
        "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    ),
    (
        "NDTV",
        "India",
        "https://feeds.feedburner.com/ndtvnews-top-stories",
    ),
    (
        "BBC World",
        "World",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ),
    (
        "BBC India",
        "India",
        "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml",
    ),
    (
        "Google News India",
        "India",
        "https://news.google.com/rss/search?q=India%20when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    ),
    (
        "Google News World",
        "World",
        "https://news.google.com/rss/search?q=world%20news%20when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    ),
    (
        "Google News Sports",
        "Sports",
        "https://news.google.com/rss/search?q=sports%20when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    ),
    (
        "Google News Science Technology",
        "Science & Technology",
        "https://news.google.com/rss/search?q=science%20technology%20when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    ),
    (
        "Google News Economy India",
        "Economy",
        "https://news.google.com/rss/search?q=India%20economy%20when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    ),
    (
        "Google News Environment India",
        "Environment",
        "https://news.google.com/rss/search?q=India%20environment%20when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    ),
    (
        "Google News Health India",
        "Health",
        "https://news.google.com/rss/search?q=India%20health%20when%3A1d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    ),
]


# ============================================================
# MOTIVATION
# ============================================================

MOTIVATION_QUOTES = [
    "Consistency turns ordinary study into extraordinary results.",
    "Read with purpose. Revise with discipline. Perform with confidence.",
    "One focused hour today can remove many doubts tomorrow.",
    "Small daily progress compounds into strong preparation.",
    "Understand the issue, connect the facts, write the answer.",
    "Discipline is choosing your preparation even when motivation is low.",
    "Study deeply today so that revision becomes easier tomorrow.",
    "Current affairs become powerful when facts are connected with concepts.",
]

# Stable public Unsplash images used only when a publisher image is unavailable.
# The URL changes automatically with each update/date, so the motivation panel
# never remains blank.
MOTIVATION_IMAGES = [
    "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?auto=format&fit=crop&w=1600&q=85",
    "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=1600&q=85",
    "https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1600&q=85",
    "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1600&q=85",
    "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?auto=format&fit=crop&w=1600&q=85",
    "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?auto=format&fit=crop&w=1600&q=85",
    "https://images.unsplash.com/photo-1516979187457-637abb4f9353?auto=format&fit=crop&w=1600&q=85",
    "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=1600&q=85",
]


NEWS_FALLBACK_IMAGES = {
    "India": [
        "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1532375810709-75b1da00537c?auto=format&fit=crop&w=1200&q=80",
    ],
    "World": [
        "https://images.unsplash.com/photo-1521295121783-8a321d551ad2?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?auto=format&fit=crop&w=1200&q=80",
    ],
    "Sports": [
        "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?auto=format&fit=crop&w=1200&q=80",
    ],
    "Science & Technology": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80",
    ],
    "Economy": [
        "https://images.unsplash.com/photo-1559526324-593bc073d938?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=1200&q=80",
    ],
    "Environment": [
        "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1473448912268-2022ce9509d8?auto=format&fit=crop&w=1200&q=80",
    ],
    "Health": [
        "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1200&q=80",
    ],
    "default": [
        "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1495020689067-958852a7765e?auto=format&fit=crop&w=1200&q=80",
    ],
}


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AURA-EXAM-AI/1.0; +https://github.com/)"
}


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = BeautifulSoup(
        str(value),
        "html.parser"
    ).get_text(" ", strip=True)

    return re.sub(r"\s+", " ", value).strip()


def normalize_title(value):
    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def safe_json_load(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as exc:
        print(f"Could not read {path}: {exc}")
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    tmp = path + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    os.replace(tmp, path)


def article_key(article):
    url = clean_text(article.get("source_url", ""))
    title = normalize_title(article.get("headline", ""))

    return hashlib.sha1(
        (url + "|" + title).encode("utf-8")
    ).hexdigest()


# ============================================================
# WEB FETCHING
# ============================================================

def fetch_page(url):
    if not url:
        return ""

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        r.raise_for_status()
        return r.text

    except Exception as exc:
        print(f"Page fetch failed: {url} -> {exc}")
        return ""


def extract_image_from_html(html, base_url):
    if not html:
        return ""

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    candidates = []

    for attrs in [
        {"property": "og:image"},
        {"name": "twitter:image"},
        {"property": "og:image:url"},
    ]:
        tag = soup.find("meta", attrs=attrs)

        if tag and tag.get("content"):
            candidates.append(tag.get("content"))

    for link in soup.find_all("link"):
        rel = " ".join(
            link.get("rel", [])
        ).lower()

        href = link.get("href", "")

        if href and "image" in rel:
            candidates.append(href)

    for value in candidates:
        value = clean_text(value)

        if value.startswith("//"):
            value = "https:" + value

        value = urljoin(
            base_url,
            value
        )

        if value.startswith(("http://", "https://")):
            return value

    return ""


def extract_page_text(html):
    """
    Extract article information without copying the publisher's
    page into AURA.  The extracted text is source material for
    an original AI summary.

    Important: include semantic list/table content because many
    current-affairs stories put their most important facts there.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove page chrome, scripts and common non-editorial blocks.
    unwanted = [
        "script", "style", "noscript", "svg", "header", "footer",
        "nav", "aside", "form", "button", "iframe",
    ]
    for tag in soup(unwanted):
        tag.decompose()

    for tag in soup.find_all(True):
        classes = " ".join(tag.get("class", [])).lower()
        ident = str(tag.get("id", "")).lower()
        marker = f"{classes} {ident}"
        if any(word in marker for word in (
            "advert", "advertisement", "sponsor", "newsletter",
            "subscribe", "social-share", "related-story",
            "recommended", "comments", "comment-section",
            "cookie", "popup", "paywall",
        )):
            tag.decompose()

    main = (
        soup.find("article")
        or soup.find("main")
        or soup.body
        or soup
    )

    blocks = []
    semantic_tags = {
        "h1", "h2", "h3", "h4", "h5",
        "p", "li", "blockquote", "dt", "dd", "tr"
    }

    # Process document order. A list item/table row is treated as a
    # complete semantic block so nested cells/paragraphs are not duplicated.
    for node in main.find_all(list(semantic_tags)):
        # Skip a node if it is nested inside another semantic block
        # that already represents the same content.
        parent = node.parent
        nested = False
        while parent is not None and parent is not main:
            if getattr(parent, "name", None) in {"li", "tr"} and node.name in {"p", "li", "td", "th"}:
                nested = True
                break
            parent = parent.parent
        if nested:
            continue

        if node.name == "tr":
            cells = [clean_text(c.get_text(" ", strip=True)) for c in node.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            text = " | ".join(cells)
        else:
            text = clean_text(node.get_text(" ", strip=True))

        if not text:
            continue

        # Keep list semantics visible to Gemini.
        if node.name == "li":
            text = "- " + text
        elif node.name == "tr":
            text = "TABLE: " + text

        # Headings can be short; ordinary paragraphs should contain
        # enough text to avoid navigation fragments.
        if node.name not in {"h1", "h2", "h3", "h4", "h5", "dt", "dd"} and len(text.lstrip("- ")) < 20:
            continue

        if blocks and text == blocks[-1]:
            continue

        blocks.append(text)

    # Remove consecutive duplicates while preserving order.
    result = []
    seen = set()
    for block in blocks:
        key = re.sub(r"\s+", " ", block).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(block)

    # More room for fact-heavy articles; Gemini input is capped later.
    return "\n\n".join(result[:180])


def parse_published_date(value):
    """Return YYYY-MM-DD when an RSS date can be parsed."""
    value = clean_text(value)
    if not value:
        return TODAY
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt.astimezone(IST).strftime("%Y-%m-%d")
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%d %b %Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST)
            return dt.astimezone(IST).strftime("%Y-%m-%d")
        except Exception:
            continue
    return TODAY


# ============================================================
# RSS
# ============================================================

def rss_candidates():
    candidates = []
    seen = set()

    for source_name, source_category, rss_url in RSS_SOURCES:

        try:
            feed = feedparser.parse(rss_url)

            print(
                f"{source_name}: "
                f"{len(feed.entries)} RSS entries"
            )

        except Exception as exc:
            print(
                f"RSS failed: "
                f"{source_name} -> {exc}"
            )
            continue

        for entry in feed.entries[
            :MAX_CANDIDATES_PER_SOURCE
        ]:

            title = clean_text(
                entry.get("title", "")
            )

            url = clean_text(
                entry.get("link", "")
            )

            if not title or not url:
                continue

            key = (
                normalize_title(title),
                url.split("?")[0].rstrip("/")
            )

            if key in seen:
                continue

            seen.add(key)

            image = ""

            for field in (
                "media_content",
                "media_thumbnail",
                "enclosures",
            ):

                values = entry.get(
                    field,
                    []
                ) or []

                if isinstance(values, dict):
                    values = [values]

                for item in values:

                    if not isinstance(
                        item,
                        dict
                    ):
                        continue

                    image = (
                        item.get("url")
                        or item.get("href")
                        or ""
                    )

                    if image:
                        break

                if image:
                    break

            published = (
                entry.get("published")
                or entry.get("updated")
                or ""
            )

            candidates.append({
                "source_name": source_name,
                "source_category": source_category,
                "category": source_category,
                "headline": title,
                "source_url": url,
                "rss_image": image,
                "published_raw": clean_text(
                    published
                ),
                "published_date": parse_published_date(published),
            })

    return candidates


# ============================================================
# IMAGE HANDLING
# ============================================================

def valid_image_url(url):
    if not url:
        return False

    return url.lower().startswith(
        ("http://", "https://")
    )


def choose_unique_image(
    candidate,
    article,
    used_images,
    index
):

    image = candidate.get(
        "rss_image",
        ""
    )

    if not valid_image_url(image):
        image = ""

    if not image:
        image = extract_image_from_html(
            candidate.get("page_html", ""),
            candidate.get("source_url", "")
        )

    if image and image not in used_images:
        used_images.add(image)
        return image

    category = article.get(
        "category",
        "default"
    )

    pool = NEWS_FALLBACK_IMAGES.get(
        category,
        NEWS_FALLBACK_IMAGES["default"]
    )

    for offset in range(len(pool)):

        fallback = pool[
            (index + offset) % len(pool)
        ]

        if fallback not in used_images:
            used_images.add(fallback)
            return fallback

    fallback = NEWS_FALLBACK_IMAGES[
        "default"
    ][
        index % len(
            NEWS_FALLBACK_IMAGES["default"]
        )
    ]

    used_images.add(fallback)

    return fallback


# ============================================================
# GEMINI JSON
# ============================================================

def parse_json_response(text):

    text = (text or "").strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    try:
        return json.loads(text)

    except Exception:

        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:
            return json.loads(
                text[start:end + 1]
            )

        raise


def call_gemini(client, prompt):

    last_error = None

    for model in GEMINI_MODELS:

        try:

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2,
                },
            )

            text = getattr(
                response,
                "text",
                None
            )

            if text:
                return parse_json_response(text)

        except Exception as exc:

            last_error = exc

            print(
                f"Gemini {model} failed: {exc}"
            )

            time.sleep(1)

    raise RuntimeError(
        f"All Gemini models failed: {last_error}"
    )


# ============================================================
# CATEGORY HELPERS
# ============================================================

def contains_any(text, keywords):
    return any(
        keyword in text
        for keyword in keywords
    )


def count_matches(text, keywords):
    return sum(
        1 for keyword in keywords
        if keyword in text
    )


def is_india_focused(text):
    india_markers = (
        "india",
        "indian",
        "new delhi",
        "delhi",
        "mumbai",
        "kolkata",
        "chennai",
        "bengaluru",
        "bangalore",
        "hyderabad",
        "chandigarh",
        "jaipur",
        "lucknow",
        "patna",
        "government of india",
        "union government",
        "central government",
        "lok sabha",
        "rajya sabha",
        "ministry of",
        "supreme court of india",
        "reserve bank of india",
        "rbi",
        "isro",
    )

    return contains_any(
        text,
        india_markers
    )


def exam_corner_score(title, text, category):

    # --------------------------------------------------------
    # Exam Corner covers exam-relevant current affairs
    # across ALL major categories.
    # --------------------------------------------------------

    allowed_categories = {
        "India",
        "World",
        "Economy",
        "Science & Technology",
        "Environment",
        "Health",
        "Sports",
    }

    if category not in allowed_categories:
        return 0

    combined = (
        title.lower()
        + " "
        + title.lower()
        + " "
        + text[:8000].lower()
    )

    if not is_india_focused(combined):
        return 0

    high = count_matches(
        combined,
        EXAM_HIGH_VALUE
    )

    medium = count_matches(
        combined,
        EXAM_MEDIUM
    )

    # Headline gets extra weight.
    title_high = count_matches(
        title.lower(),
        EXAM_HIGH_VALUE
    )

    title_medium = count_matches(
        title.lower(),
        EXAM_MEDIUM
    )

    score = (
        high * 3
        + medium
        + title_high * 3
        + title_medium * 2
    )

    return score


def classify_candidate(candidate, page_text=""):

    title = clean_text(
        candidate.get(
            "headline",
            ""
        )
    )

    text = clean_text(
        page_text
    )

    title_blob = title.lower()

    body_blob = text[:8000].lower()

    # Headline gets strong priority.
    blob = (
        title_blob
        + " "
        + title_blob
        + " "
        + body_blob
    )

    source_category = candidate.get(
        "source_category",
        candidate.get(
            "category",
            "India"
        )
    )

    # --------------------------------------------------------
    # STEP 1: Strong topic classification
    # --------------------------------------------------------

    sports_score = count_matches(
        title_blob,
        SPORTS
    )

    health_score = count_matches(
        title_blob,
        HEALTH
    )

    science_score = count_matches(
    title_blob,
    SCIENCE
)

# Strong Science & Technology indicators
# These should be recognised even when the headline
# does not contain the existing SCIENCE keyword list.
science_strong = (
    "drdo",
    "isro",
    "csir",
    "technology",
    "technolog",
    "artificial intelligence",
    "ai ",
    "machine learning",
    "semiconductor",
    "quantum",
    "robot",
    "robotics",
    "space",
    "satellite",
    "launch vehicle",
    "missile",
    "defence technology",
    "defense technology",
    "biotechnology",
    "biotech",
    "genome",
    "genomics",
    "gene",
    "vaccine",
    "nanotechnology",
    "nanocrystal",
    "research",
    "innovation",
    "laboratory",
    "laboratories",
    "scientific",
    "scientist",
    "indigenous technology",
    "5g",
    "6g",
    "cybersecurity",
    "cyber security",
    "digital technology",
    "supercomputer",
    "astronomy",
)

science_strong_score = count_matches(
    title_blob,
    science_strong
)

if science_strong_score >= 1:
    science_score += 3
    )

    economy_score = count_matches(
        title_blob,
        ECONOMY
    )

    environment_score = count_matches(
        title_blob,
        ENVIRONMENT
    )

    world_score = count_matches(
        title_blob,
        WORLD
    )

    title_scores = {
        "Sports": sports_score,
        "Health": health_score,
        "Science & Technology": science_score,
        "Economy": economy_score,
        "Environment": environment_score,
        "World": world_score,
    }

    strongest_title_category = max(
        title_scores,
        key=title_scores.get
    )

    strongest_title_score = title_scores[
        strongest_title_category
    ]

    # --------------------------------------------------------
    # Strong headline topic wins immediately.
    # --------------------------------------------------------

    if strongest_title_score >= 1:
        category = strongest_title_category

    else:

        # Body scores are used only when headline is unclear.

        body_scores = {
            "Sports": count_matches(
                body_blob,
                SPORTS
            ),
            "Health": count_matches(
                body_blob,
                HEALTH
            ),
            "Science & Technology": count_matches(
                body_blob,
                SCIENCE
            ),
            "Economy": count_matches(
                body_blob,
                ECONOMY
            ),
            "Environment": count_matches(
                body_blob,
                ENVIRONMENT
            ),
            "World": count_matches(
                body_blob,
                WORLD
            ),
        }

        strongest_body_category = max(
            body_scores,
            key=body_scores.get
        )

        strongest_body_score = body_scores[
            strongest_body_category
        ]

        if strongest_body_score >= 2:
            category = strongest_body_category

        elif source_category == "World":
            category = "World"

        elif source_category in {
            "Sports",
            "Science & Technology",
            "Economy",
            "Environment",
            "Health",
        }:
            category = source_category

        else:
            category = "India"

    # --------------------------------------------------------
    # STEP 2: Prevent false India classification
    # --------------------------------------------------------

    # If a story is clearly international, do not classify it
    # as India simply because the article mentions India.

    if contains_any(
        title_blob,
        WORLD
    ) and not is_india_focused(title_blob):

        category = "World"

    # --------------------------------------------------------
    # STEP 3: Exam Corner
    # --------------------------------------------------------
    # VERY IMPORTANT:
    # Exam Corner is NOT a normal category.
    # It is a filter/subset of India news.
    #
    # Therefore:
    #
    # Sports              -> NEVER Exam Corner
    # Health              -> NEVER Exam Corner
    # Science             -> NEVER Exam Corner
    # Economy             -> NEVER Exam Corner automatically
    # Environment         -> NEVER Exam Corner automatically
    # World               -> NEVER Exam Corner
    #
    # Only India + strong exam relevance can enter.
    # --------------------------------------------------------

    exam_score = exam_corner_score(
        title,
        text,
        category
    )

    exam_corner = (
        category == "India"
        and exam_score >= 7
    )

    candidate["category"] = category
    candidate["exam_corner"] = bool(
        exam_corner
    )
    candidate["exam_score"] = exam_score

    print(
        f"CLASSIFY | {title[:90]} | "
        f"{category} | "
        f"ExamCorner={exam_corner} | "
        f"score={exam_score}"
    )

    return candidate


# ============================================================
# GEMINI ARTICLE PROMPT
# ============================================================

def article_prompt(candidate, page_text):

    return f"""
You are the content engine for AURA EXAM AI, an Indian competitive-exam current-affairs website.

Create a COMPREHENSIVE, SOURCE-FAITHFUL CURRENT-AFFAIRS BRIEF from the supplied source material.
The goal is to help a student understand the complete important information in the news, not merely its headline.

COPYRIGHT / ORIGINAL-WORDING RULES — VERY IMPORTANT:
- Do NOT reproduce the source article verbatim.
- Do NOT copy long sentences or distinctive wording from the publisher.
- Write the visible article in your own original wording.
- Use the source only to identify and preserve facts.
- Facts such as dates, names, numbers, places, events and public records are to be retained accurately.
- Do not omit important facts merely to make the summary short.
- Do not invent information from your general knowledge.

COMPLETENESS RULES — VERY IMPORTANT:
- Preserve all material facts needed to understand the event.
- Pay special attention to lists, numbered items, tables, dates, statistics, amounts, names, places, exceptions, deadlines and comparisons.
- If the source contains a list of dates/locations, retain the individual important entries rather than collapsing them into a vague sentence.
- If the source contains a table, preserve its important rows/columns in readable wording.
- The full_article_text should normally be several informative paragraphs for a substantial story, not a 2-3 sentence generic summary.
- For a short/simple story, keep it appropriately shorter; never add filler just to increase length.

CONTEXT / ANALYSIS RULES:
- background_context: use ONLY context explicitly supplied by the source; otherwise return an empty string.
- causes, impacts, challenges, government_steps and constitutional_or_policy_link: include only when directly supported by the source and materially relevant. Otherwise return an empty array.
- exam_relevance, mains_notes and prelims_facts may interpret the supplied facts for exam preparation, but must not introduce unsupported factual claims.
- Keep political coverage neutral and descriptive.

IMPORTANT CATEGORY RULES:
1. Exam Corner is NOT a general category.
2. Exam Corner is ONLY for Indian current affairs having clear competitive-exam relevance.
3. A normal India news story remains India.
4. International news is World.
5. Health news is Health.
6. Science/technology news is Science & Technology.
7. Economy/finance news is Economy.
8. Environment/climate/wildlife news is Environment.
9. Sports news is Sports.
10. Do not change the supplied classifier category merely because the article mentions India.

The supplied classifier category is authoritative.

Return ONLY valid JSON.

SOURCE:
Publisher: {candidate['source_name']}
Category: {candidate['category']}
Exam Corner: {candidate.get('exam_corner', False)}
Headline: {candidate['headline']}
Publication date: {candidate.get('published_date', TODAY)}
URL: {candidate['source_url']}

SOURCE MATERIAL:
{page_text[:18000]}

Required JSON object:
{{
  "category": "{candidate['category']}",
  "exam_corner": {str(bool(candidate.get('exam_corner', False))).lower()},
  "headline": "clear factual headline in original wording",
  "story_lead": "2-4 sentence original lead covering what happened and why it matters when supported",
  "full_article_text": "comprehensive original current-affairs brief preserving the important facts, details, lists, dates, numbers, names, places, exceptions and comparisons from the source",
  "background_context": "source-supported background only, or empty string",
  "bullet_points": ["6-10 important source-supported points when the story has enough material"],
  "key_facts": ["important factual details that a student should remember"],
  "key_locations": ["important places explicitly mentioned"],
  "important_dates": ["important dates explicitly mentioned, with the associated event when useful"],
  "exam_relevance": ["specific Prelims/Mains relevance based on the supplied facts"],
  "upsc_analysis": "balanced analysis only when the source provides enough material; otherwise concise factual significance",
  "causes": ["source-supported causes/drivers only"],
  "impacts": ["source-supported impacts only"],
  "challenges": ["source-supported challenges only"],
  "government_steps": ["government/institutional steps explicitly supported by the source"],
  "constitutional_or_policy_link": ["links only when clearly justified by the supplied material"],
  "way_forward": ["only if supported or directly framed as an exam-analysis inference from the supplied facts"],
  "mains_notes": "compact but information-rich Mains-ready notes",
  "mains_questions": ["2-3 original questions based specifically on this news"],
  "takeaway": "one concise factual takeaway",
  "prelims_facts": ["high-value factual points from the source"],
  "vocabulary": [
    {{"word": "important English word", "meaning_hindi": "Hindi meaning"}}
  ],
  "related_entities": [
    {{"name": "person/place/organisation", "type": "person/place/organisation", "wikipedia_url": ""}}
  ],
  "hindi_translation": {{
    "headline": "Hindi headline",
    "story_lead": "Hindi translation of lead",
    "full_article_text": "Hindi translation of the complete original brief",
    "background_context": "Hindi background or empty",
    "bullet_points": ["Hindi bullet points"],
    "key_facts": ["Hindi facts"],
    "key_locations": ["Hindi locations"],
    "important_dates": ["Hindi date/event entries"]
  }},
  "quiz": {{
    "question": "one article-specific MCQ based on an important fact",
    "options": ["A", "B", "C", "D"],
    "correct_answer": "exactly one option string",
    "explanation": "short factual explanation"
  }}
}}
"""


# ============================================================
# NORMALIZE GENERATED ARTICLE
# ============================================================

def normalize_generated(article, candidate):

    article = (
        article
        if isinstance(article, dict)
        else {}
    )

    article["source_name"] = candidate[
        "source_name"
    ]

    article["source_url"] = candidate[
        "source_url"
    ]

    # IMPORTANT:
    # Never let Gemini override our classifier.
    article["category"] = candidate[
        "category"
    ]

    article["exam_corner"] = bool(
        candidate.get(
            "exam_corner",
            False
        )
    )

    # Extra safety:
    # Exam Corner can ONLY be attached to India.
    if article["category"] != "India":
        article["exam_corner"] = False

    article["published_date"] = candidate.get(
        "published_date", TODAY
    )
    article["content_version"] = CONTENT_VERSION

    for key in [
        "bullet_points",
        "key_facts",
        "key_locations",
        "important_dates",
        "exam_relevance",
        "causes",
        "impacts",
        "challenges",
        "government_steps",
        "constitutional_or_policy_link",
        "way_forward",
        "mains_questions",
        "prelims_facts",
        "vocabulary",
        "related_entities",
    ]:

        if not isinstance(
            article.get(key),
            list
        ):
            article[key] = []

    if not isinstance(
        article.get("hindi_translation"),
        dict
    ):
        article["hindi_translation"] = None

    quiz = article.get("quiz")

    if not isinstance(
        quiz,
        dict
    ):
        article["quiz"] = None

    else:

        if (
            not isinstance(
                quiz.get("options"),
                list
            )
            or len(quiz["options"]) != 4
        ):
            article["quiz"] = None

    return article


# ============================================================
# FALLBACK QUIZ
# ============================================================

def fallback_quiz(article):

    headline = (
        article.get("headline")
        or "this current-affairs article"
    )

    return {
        "question": (
            "Which topic is directly discussed "
            "in the current-affairs article titled: "
            f"{headline}?"
        ),

        "options": [
            headline,
            "A topic not discussed in the article",
            "An unrelated historical event",
            "An unrelated scientific formula",
        ],

        "correct_answer": headline,

        "explanation": (
            "The correct option is the topic "
            "explicitly identified by the article headline."
        ),
    }


# ============================================================
# ENTITY URLS
# ============================================================

def ensure_entity_urls(article):

    entities = (
        article.get("related_entities")
        or []
    )

    clean_entities = []
    seen = set()

    for item in entities:

        if not isinstance(
            item,
            dict
        ):
            continue

        name = clean_text(
            item.get("name", "")
        )

        if not name:
            continue

        key = name.lower()

        if key in seen:
            continue

        seen.add(key)

        entity_type = (
            "person"
            if str(
                item.get("type", "")
            ).lower() == "person"
            else "place"
        )

        url = (
            item.get("wikipedia_url")
            or
            "https://en.wikipedia.org/wiki/"
            "Special:Search?search="
            + quote(name)
        )

        clean_entities.append({
            "name": name,
            "type": entity_type,
            "wikipedia_url": url,
        })

    article[
        "related_entities"
    ] = clean_entities


# ============================================================
# REPAIR CHECK
# ============================================================

def needs_repair(article):

    hindi = article.get(
        "hindi_translation"
    )

    quiz = article.get(
        "quiz"
    )

    vocab = article.get(
        "vocabulary"
    )

    entities = article.get(
        "related_entities"
    )

    return (
        article.get("content_version", 0) < CONTENT_VERSION
        or not article.get("full_article_text")
        or not isinstance(
            hindi,
            dict
        )
        or not hindi.get("headline")
        or not isinstance(
            quiz,
            dict
        )
        or not isinstance(
            quiz.get("options"),
            list
        )
        or len(
            quiz.get("options", [])
        ) != 4
        or not isinstance(
            vocab,
            list
        )
        or not isinstance(
            entities,
            list
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    api_key = os.environ.get(
        "GEMINI_API_KEY",
        ""
    ).strip()

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured"
        )

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    client = genai.Client(
        api_key=api_key
    )

    # --------------------------------------------------------
    # ROOT DATA
    # --------------------------------------------------------

    root = safe_json_load(
        DATA_FILE,
        {}
    )

    if not isinstance(
        root,
        dict
    ):
        root = {}

    # --------------------------------------------------------
    # TODAY DATA
    # --------------------------------------------------------

    today_file = os.path.join(
        DATA_DIR,
        f"{TODAY}.json"
    )

    today_data = safe_json_load(
        today_file,
        {
            "date": TODAY,
            "news": [],
        }
    )

    if not isinstance(
        today_data,
        dict
    ):
        today_data = {
            "date": TODAY,
            "news": [],
        }

    if not isinstance(
        today_data.get("news"),
        list
    ):
        today_data["news"] = []

    existing_news = today_data[
        "news"
    ]

    existing_keys = {
        article_key(a)
        for a in existing_news
        if isinstance(a, dict)
    }

    used_images = {
        a.get("image_url")
        for a in existing_news
        if isinstance(a, dict)
        and a.get("image_url")
    }

    # ========================================================
    # REPAIR EXISTING ARTICLES
    # ========================================================

    repair_targets = [
        a
        for a in existing_news
        if isinstance(a, dict)
        and needs_repair(a)
    ]

    print(
        f"Existing articles: "
        f"{len(existing_news)} | "
        f"repair targets: "
        f"{len(repair_targets)}"
    )

    for article in repair_targets:

        source_url = article.get(
            "source_url",
            ""
        )

        html = (
            fetch_page(source_url)
            if source_url
            else ""
        )

        source_text = extract_page_text(
            html
        )

        if not source_text:
            source_text = article.get(
                "full_article_text",
                ""
            )

        candidate = {
            "source_name": article.get(
                "source_name",
                "News Source"
            ),
            "source_category": article.get(
                "category",
                "India"
            ),
            "category": article.get(
                "category",
                "India"
            ),
            "headline": article.get(
                "headline",
                "Current Affairs"
            ),
            "source_url": source_url,
            "published_date": article.get("published_date") or TODAY,
        }

        # Reclassify repaired article.
        candidate = classify_candidate(
            candidate,
            source_text
        )

        try:

            generated = call_gemini(
                client,
                article_prompt(
                    candidate,
                    source_text
                )
            )

            generated = normalize_generated(
                generated,
                candidate
            )

            generated["id"] = article.get(
                "id"
            )

            generated["image_url"] = (
                article.get("image_url")
                or extract_image_from_html(
                    html,
                    source_url
                )
            )

            # Preserve existing rich fields.
            for key, value in generated.items():

                if key in {
                    "source_name",
                    "source_url",
                    "category",
                    "published_date",
                    "id",
                    "image_url",
                    "exam_corner",
                }:
                    continue

                # A content-version rebuild is intentionally allowed to replace
                # old AI summaries with the improved, more complete format.
                if article.get("content_version", 0) < CONTENT_VERSION:
                    article[key] = value
                elif not article.get(key):
                    article[key] = value

            article["category"] = candidate[
                "category"
            ]

            article["exam_corner"] = bool(
                candidate.get(
                    "exam_corner",
                    False
                )
            )

            if not isinstance(
                article.get(
                    "hindi_translation"
                ),
                dict
            ):
                article[
                    "hindi_translation"
                ] = generated.get(
                    "hindi_translation"
                )

            if not isinstance(
                article.get("quiz"),
                dict
            ):
                article["quiz"] = (
                    generated.get("quiz")
                    or fallback_quiz(article)
                )

            if not isinstance(
                article.get("vocabulary"),
                list
            ):
                article[
                    "vocabulary"
                ] = generated.get(
                    "vocabulary",
                    []
                )

            if not isinstance(
                article.get(
                    "related_entities"
                ),
                list
            ):
                article[
                    "related_entities"
                ] = generated.get(
                    "related_entities",
                    []
                )

            ensure_entity_urls(
                article
            )

            if article.get(
                "image_url"
            ):
                used_images.add(
                    article[
                        "image_url"
                    ]
                )

        except Exception as exc:

            print(
                f"Repair failed for "
                f"{article.get('headline')}: "
                f"{exc}"
            )

            if not isinstance(
                article.get("quiz"),
                dict
            ):
                article["quiz"] = (
                    fallback_quiz(article)
                )

            if not isinstance(
                article.get(
                    "hindi_translation"
                ),
                dict
            ):

                article[
                    "hindi_translation"
                ] = {
                    "headline": article.get(
                        "headline",
                        ""
                    ),
                    "story_lead": article.get(
                        "story_lead",
                        ""
                    ),
                    "full_article_text": article.get(
                        "full_article_text",
                        ""
                    ),
                    "background_context": article.get(
                        "background_context",
                        ""
                    ),
                    "bullet_points": article.get(
                        "bullet_points",
                        []
                    ),
                    "key_facts": article.get(
                        "key_facts",
                        []
                    ),
                    "key_locations": article.get(
                        "key_locations",
                        []
                    ),
                    "important_dates": article.get(
                        "important_dates",
                        []
                    ),
                }

            if not isinstance(
                article.get(
                    "related_entities"
                ),
                list
            ):
                article[
                    "related_entities"
                ] = []

            ensure_entity_urls(
                article
            )

    # ========================================================
    # COLLECT RSS CANDIDATES
    # ========================================================

    candidates = rss_candidates()

    target = (
        FIRST_RUN_COUNT
        if len(existing_news) == 0
        else UPDATE_COUNT
    )

    print(
        f"Candidate pool: "
        f"{len(candidates)} | "
        f"target new articles: "
        f"{target}"
    )

    # ========================================================
    # SELECT NEW ARTICLES
    # ========================================================

    selected = []
    seen_titles = set()

    for candidate in candidates:

        title_key = normalize_title(
            candidate["headline"]
        )

        url_key = (
            candidate["source_url"]
            .split("?")[0]
            .rstrip("/")
        )

        if not title_key:
            continue

        candidate_key = article_key({
            "headline": candidate[
                "headline"
            ],
            "source_url": candidate[
                "source_url"
            ],
        })

        if candidate_key in existing_keys:
            continue

        if any(
            a.get(
                "source_url",
                ""
            ).split("?")[0].rstrip("/")
            == url_key
            for a in existing_news
        ):
            continue

        if title_key in seen_titles:
            continue

        seen_titles.add(
            title_key
        )

        selected.append(
            candidate
        )

        if len(selected) >= target:
            break

    # ========================================================
    # PROCESS NEW ARTICLES
    # ========================================================

    added = 0

    numeric_ids = [
        int(a.get("id", 0))
        for a in existing_news
        if isinstance(a, dict)
        and str(
            a.get("id", "")
        ).isdigit()
    ]

    next_id = (
        max(
            numeric_ids + [0]
        )
        + 1
    )

    for index, candidate in enumerate(
        selected
    ):

        html = fetch_page(
            candidate[
                "source_url"
            ]
        )

        candidate[
            "page_html"
        ] = html

        page_text = extract_page_text(
            html
        )

        if len(page_text) < 250:
            page_text = candidate[
                "headline"
            ]

        # ----------------------------------------------------
        # ACTUAL ARTICLE CLASSIFICATION
        # ----------------------------------------------------

        candidate = classify_candidate(
            candidate,
            page_text
        )

        try:

            generated = call_gemini(
                client,
                article_prompt(
                    candidate,
                    page_text
                )
            )

            article = normalize_generated(
                generated,
                candidate
            )

        except Exception as exc:

            print(
                f"Generation failed: "
                f"{candidate['headline']} "
                f"-> {exc}"
            )

            continue

        article["id"] = next_id
        next_id += 1

        article["published_date"] = candidate.get(
            "published_date", TODAY
        )
        article["content_version"] = CONTENT_VERSION

        article["source_url"] = candidate[
            "source_url"
        ]

        article["source_name"] = candidate[
            "source_name"
        ]

        article["category"] = candidate[
            "category"
        ]

        # FINAL SAFETY RULE:
        # Exam Corner can never contain
        # non-India categories.
        article["exam_corner"] = (
            bool(
                candidate.get(
                    "exam_corner",
                    False
                )
            )
            and article[
                "category"
            ] == "India"
        )

        article["image_url"] = (
            choose_unique_image(
                candidate,
                article,
                used_images,
                index
            )
        )

        article["added_at"] = NOW_ISO

        ensure_entity_urls(
            article
        )

        if not isinstance(
            article.get("quiz"),
            dict
        ):
            article["quiz"] = (
                fallback_quiz(article)
            )

        if not isinstance(
            article.get(
                "hindi_translation"
            ),
            dict
        ):

            article[
                "hindi_translation"
            ] = {
                "headline": article.get(
                    "headline",
                    ""
                ),
                "story_lead": article.get(
                    "story_lead",
                    ""
                ),
                "full_article_text": article.get(
                    "full_article_text",
                    ""
                ),
                "background_context": article.get(
                    "background_context",
                    ""
                ),
                "bullet_points": article.get(
                    "bullet_points",
                    []
                ),
                "key_facts": article.get(
                    "key_facts",
                    []
                ),
                "key_locations": article.get(
                    "key_locations",
                    []
                ),
                "important_dates": article.get(
                    "important_dates",
                    []
                ),
            }

        existing_news.append(
            article
        )

        existing_keys.add(
            article_key(article)
        )

        added += 1

        print(
            f"Added #{article['id']}: "
            f"{article['headline']} | "
            f"Category={article['category']} | "
            f"ExamCorner={article['exam_corner']}"
        )

    # ========================================================
    # RECLASSIFY ALL EXISTING ARTICLES
    # ========================================================
    # This fixes older incorrectly categorised articles too.
    # ========================================================

    print(
        "Reclassifying existing articles..."
    )

    for article in existing_news:

        if not isinstance(
            article,
            dict
        ):
            continue

        article_text = (
            article.get(
                "full_article_text",
                ""
            )
            or article.get(
                "story_lead",
                ""
            )
        )

        repaired = classify_candidate(
            {
                "source_category": article.get(
                    "category",
                    "India"
                ),
                "category": article.get(
                    "category",
                    "India"
                ),
                "headline": article.get(
                    "headline",
                    ""
                ),
                "source_url": article.get(
                    "source_url",
                    ""
                ),
                "source_name": article.get(
                    "source_name",
                    "News Source"
                ),
            },
            article_text
        )

        article[
            "category"
        ] = repaired[
            "category"
        ]

        article[
            "exam_corner"
        ] = (
            bool(
                repaired.get(
                    "exam_corner",
                    False
                )
            )
            and article[
                "category"
            ] == "India"
        )

    # ========================================================
    # FINAL DATA SANITIZATION
    # ========================================================

    for index, article in enumerate(
        existing_news
    ):

        if not article.get(
            "image_url"
        ):

            article[
                "image_url"
            ] = choose_unique_image(
                {},
                article,
                used_images,
                index
            )

        ensure_entity_urls(
            article
        )

        if not isinstance(
            article.get("quiz"),
            dict
        ):
            article["quiz"] = (
                fallback_quiz(article)
            )

        # Absolute final Exam Corner protection.
        if article.get(
            "category"
        ) != "India":
            article[
                "exam_corner"
            ] = False

    # Mark every successfully processed article with the current content version.
    for article in existing_news:
        if isinstance(article, dict):
            article["content_version"] = CONTENT_VERSION

    # ========================================================
    # NEWEST FIRST
    # ========================================================

    existing_news.sort(
        key=lambda a: (
            int(
                a.get("id", 0)
            )
            if str(
                a.get("id", "")
            ).isdigit()
            else 0
        ),
        reverse=True
    )

    # ========================================================
    # SAVE TODAY
    # ========================================================

    today_data["date"] = TODAY

    today_data[
        "updated_at"
    ] = NOW_ISO

    today_data[
        "news"
    ] = existing_news

    today_data[
        "count"
    ] = len(existing_news)

    save_json(
        today_file,
        today_data
    )

    # ========================================================
    # REBUILD ROOT INDEX
    # ========================================================

    available_dates = set(
        root.get(
            "available_dates",
            []
        )
        if isinstance(
            root.get(
                "available_dates"
            ),
            list
        )
        else []
    )

    if os.path.isdir(
        DATA_DIR
    ):

        for name in os.listdir(
            DATA_DIR
        ):

            if re.fullmatch(
                r"\d{4}-\d{2}-\d{2}\.json",
                name
            ):

                available_dates.add(
                    name[:-5]
                )

    available_dates.add(
        TODAY
    )

    available_dates = sorted(
        available_dates,
        reverse=True
    )

    # ========================================================
    # MOTIVATION ROTATION
    # ========================================================

    motivation_index = (
        len(available_dates)
        + NOW.hour // 3
    ) % len(
        MOTIVATION_IMAGES
    )

    quote_index = (
        NOW.hour // 3
        + NOW.timetuple().tm_yday
    ) % len(
        MOTIVATION_QUOTES
    )

    # ========================================================
    # ROOT UPDATE
    # ========================================================

    root.update({

        "project": "AURA EXAM AI",

        "current_date": TODAY,

        "last_updated": NOW_ISO,

        "available_dates": available_dates,

        "today": today_data,

        "motivation": {
            "quote": MOTIVATION_QUOTES[
                quote_index
            ],

            "image_url": MOTIVATION_IMAGES[
                motivation_index
            ],

            "updated_at": NOW_ISO,
        },
    })

    save_json(
        DATA_FILE,
        root
    )

    # ========================================================
    # FINAL STATISTICS
    # ========================================================

    india_count = sum(
        1
        for a in existing_news
        if a.get("category")
        == "India"
    )

    world_count = sum(
        1
        for a in existing_news
        if a.get("category")
        == "World"
    )

    sports_count = sum(
        1
        for a in existing_news
        if a.get("category")
        == "Sports"
    )

    science_count = sum(
        1
        for a in existing_news
        if a.get("category")
        == "Science & Technology"
    )

    economy_count = sum(
        1
        for a in existing_news
        if a.get("category")
        == "Economy"
    )

    environment_count = sum(
        1
        for a in existing_news
        if a.get("category")
        == "Environment"
    )

    health_count = sum(
        1
        for a in existing_news
        if a.get("category")
        == "Health"
    )

    exam_count = sum(
        1
        for a in existing_news
        if a.get("exam_corner")
        is True
    )

    quiz_count = sum(
        1
        for a in existing_news
        if isinstance(
            a.get("quiz"),
            dict
        )
    )

    # ========================================================
    # FINAL VALIDATION
    # ========================================================

    invalid_exam_articles = [
        a.get(
            "headline",
            "Unknown"
        )
        for a in existing_news
        if a.get("exam_corner")
        and a.get("category")
        != "India"
    ]

    if invalid_exam_articles:

        print(
            "WARNING: Invalid Exam Corner "
            "articles detected:"
        )

        for headline in (
            invalid_exam_articles
        ):
            print(
                f" - {headline}"
            )

    else:

        print(
            "Exam Corner validation: PASSED"
        )

    print("----------------------------------------")
    print(f"Today: {TODAY}")
    print(
        f"Existing articles before update: "
        f"{len(existing_news) - added}"
    )
    print(
        f"New articles added: {added}"
    )
    print(
        f"Total articles today: "
        f"{len(existing_news)}"
    )
    print("----------------------------------------")
    print("CATEGORY COUNTS")
    print(f"India: {india_count}")
    print(f"World: {world_count}")
    print(f"Sports: {sports_count}")
    print(
        f"Science & Technology: "
        f"{science_count}"
    )
    print(f"Economy: {economy_count}")
    print(f"Environment: {environment_count}")
    print(f"Health: {health_count}")
    print(f"Exam Corner: {exam_count}")
    print(f"Quiz count: {quiz_count}")
    print("----------------------------------------")
    print(
        "AURA EXAM AI UPDATE COMPLETED"
    )
    print("----------------------------------------")


if __name__ == "__main__":
    main()
