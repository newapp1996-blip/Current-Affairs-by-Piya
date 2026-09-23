import os
import re
import json
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

# FIRST RUN = 30 ARTICLES
FIRST_RUN_COUNT = 30

# EACH 3-HOUR UPDATE = 10 NEW ARTICLES
UPDATE_COUNT = 10

# MAXIMUM ARTICLES STORED PER DAY
MAX_DAILY_COUNT = 100

API_KEY = os.environ.get(
    "GEMINI_API_KEY"
)

if not API_KEY:

    raise RuntimeError(
        "GEMINI_API_KEY is missing."
    )


client = genai.Client(
    api_key=API_KEY
)


# ============================================================
# HTTP
# ============================================================

HEADERS = {

    "User-Agent":
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
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
# CLEAN
# ============================================================

def clean(value):

    if value is None:

        return ""

    value = html.unescape(
        str(value)
    )

    soup = BeautifulSoup(
        value,
        "html.parser"
    )

    value = soup.get_text(
        " ",
        strip=True
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# VALID TITLE
# ============================================================

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


# ============================================================
# HASH
# ============================================================

def make_hash(
    title,
    url
):

    text = (

        clean(title).lower()

        + "|"

        + clean(url).lower()

    )

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


# ============================================================
# JSON
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

    except Exception:

        return None


def save_json(
    path,
    data
):

    folder = os.path.dirname(
        path
    )

    if folder:

        os.makedirs(
            folder,
            exist_ok=True
        )

    temp = path + ".tmp"

    with open(
        temp,
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
        temp,
        path
    )


# ============================================================
# IMAGE
# ============================================================

def get_rss_image(entry):

    try:

        if hasattr(
            entry,
            "media_content"
        ):

            media = (
                entry.media_content
            )

            if media:

                for item in media:

                    url = item.get(
                        "url",
                        ""
                    )

                    if url:

                        return url


        if hasattr(
            entry,
            "media_thumbnail"
        ):

            media = (
                entry.media_thumbnail
            )

            if media:

                for item in media:

                    url = item.get(
                        "url",
                        ""
                    )

                    if url:

                        return url


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


        names = [

            "og:image",

            "twitter:image",

            "twitter:image:src"

        ]


        for name in names:

            tag = soup.find(

                "meta",

                attrs={
                    "property": name
                }

            )

            if (
                tag
                and
                tag.get("content")
            ):

                return tag.get(
                    "content"
                )


            tag = soup.find(

                "meta",

                attrs={
                    "name": name
                }

            )

            if (
                tag
                and
                tag.get("content")
            ):

                return tag.get(
                    "content"
                )


    except Exception:

        pass

    return ""


def choose_fallback_image(
    category,
    index
):

    if category in FALLBACK_IMAGES:

        return FALLBACK_IMAGES[
            category
        ]

    keys = list(
        FALLBACK_IMAGES.keys()
    )

    return FALLBACK_IMAGES[
        keys[
            index % len(keys)
        ]
    ]


def get_image(
    entry,
    url,
    category,
    index
):

    image = get_rss_image(
        entry
    )

    if image:

        return image


    image = get_page_image(
        url
    )

    if image:

        return image


    return choose_fallback_image(
        category,
        index
    )


# ============================================================
# CATEGORY
# ============================================================

def guess_category(
    title,
    summary
):

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

    print(
        "Collecting RSS news..."
    )

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
                    "HTTP:",
                    response.status_code
                )

                continue


            parsed = feedparser.parse(
                response.content
            )


            count = 0


            for entry in parsed.entries[:40]:

                title = clean(
                    entry.get(
                        "title",
                        ""
                    )
                )


                url = clean(
                    entry.get(
                        "link",
                        ""
                    )
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


                if not valid_title(
                    title
                ):

                    continue


                if not url:

                    continue


                article_hash =
                    make_hash(
                        title,
                        url
                    )


                if article_hash in seen:

                    continue


                seen.add(
                    article_hash
                )


                category =
                    guess_category(
                        title,
                        summary
                    )


                image =
                    get_image(

                        entry,

                        url,

                        category,

                        len(all_items)

                    )


                all_items.append(

                    {

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
        len(all_items)
    )


    return all_items


# ============================================================
# TODAY
# ============================================================

def today_file():

    return os.path.join(

        DATA_DIR,

        TODAY + ".json"

    )


def load_today():

    data = load_json(
        today_file()
    )


    if not isinstance(
        data,
        dict
    ):

        return []


    news = data.get(
        "news",
        []
    )


    if not isinstance(
        news,
        list
    ):

        return []


    return news


# ============================================================
# GEMINI PROMPT
# ============================================================

def build_prompt(
    items,
    number
):

    source_blocks = []


    for index, item in enumerate(
        items
    ):

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

        source_blocks.append(
            block
        )


    prompt = (

        "You are a senior UPSC current-affairs "
        "editor and civil-services educator.\n\n"

        "Prepare exactly "
        + str(number)
        + " distinct current-affairs study notes "
        "from the supplied real news sources.\n\n"


        "CRITICAL FACTUAL RULES:\n"

        "1. Use ONLY information supported by the supplied source material.\n"

        "2. Never invent statistics, dates, names, schemes, quotations or events.\n"

        "3. Do not mix unrelated news stories.\n"

        "4. Each article must remain specifically about its selected source story.\n"

        "5. Do not produce generic filler analysis.\n"

        "6. Preserve the actual source URL.\n"

        "7. If the supplied material does not support a claim, do not make the claim.\n\n"


        "STYLE:\n"

        "Write the result like high-quality UPSC classroom notes.\n"

        "The student should be able to directly revise the article "
        "and use the analytical points while writing a UPSC Mains answer.\n\n"


        "DEPTH:\n"

        "Give substantial UPSC-level analysis.\n"

        "Explain the issue, its background, causes, implications, "
        "stakeholders, challenges and possible way forward wherever "
        "the supplied material supports them.\n\n"


        "RETURN ONLY VALID JSON.\n\n"


        "Each object MUST contain exactly these fields:\n\n"

        "source_number\n"

        "category\n"

        "headline\n"

        "story_lead\n"

        "why_in_news\n"

        "background\n"

        "detailed_analysis\n"

        "key_facts\n"

        "causes\n"

        "impact\n"

        "challenges\n"

        "government_response\n"

        "way_forward\n"

        "key_locations\n"

        "important_dates\n"

        "upsc_relevance\n"

        "prelims_facts\n"

        "mains_answer\n"

        "takeaway\n"

        "vocabulary\n\n"


        "FIELD INSTRUCTIONS:\n\n"

        "story_lead: Give a concise factual introduction.\n"

        "why_in_news: Explain why this issue is currently in the news.\n"

        "background: Give relevant background and context.\n"

        "detailed_analysis: Provide deep UPSC-level analysis "
        "of the issue and its significance.\n"

        "key_facts: Important factual points as an array.\n"

        "causes: Major causes/drivers as an analytical paragraph.\n"

        "impact: Explain political, economic, social, environmental, "
        "strategic or institutional impacts wherever relevant.\n"

        "challenges: Explain major challenges and concerns.\n"

        "government_response: Mention only responses supported by the source.\n"

        "way_forward: Give balanced, practical analytical suggestions "
        "based on the issue and supplied material. Do not invent government policies.\n"

        "key_locations: Important places as an array.\n"

        "important_dates: Important dates as an array.\n"

        "upsc_relevance: Connect the topic with UPSC GS papers, "
        "governance, economy, environment, science-tech, IR, society "
        "or other relevant syllabus areas.\n"

        "prelims_facts: Facts useful for Prelims revision as an array.\n"

        "mains_answer: Write a concise Mains-ready answer framework "
        "with introduction, body points and conclusion. It must be "
        "directly usable by a student as notes.\n"

        "takeaway: Give the central lesson/fact of the issue.\n"

        "vocabulary: Return an array of objects. Each object must contain "
        "word and hindi_meaning. Select 5 to 10 important English words "
        "actually used or naturally relevant to the article and give "
        "their accurate Hindi meanings.\n\n"


        "SOURCE MATERIAL:\n\n"

        + "\n\n".join(
            source_blocks
        )

    )


    return prompt


# ============================================================
# GEMINI
# ============================================================

def generate_articles(
    items,
    number
):

    if not items:

        return []


    prompt =
        build_prompt(
            items[:80],
            number
        )


    models = [

        "gemini-3.8-flash",

        "gemini-3.7-flash",

        "gemini-3.6-flash"

    ]


    for model in models:

        print(
            "Trying Gemini:",
            model
        )


        try:

            response =
                client.models.generate_content(

                    model=model,

                    contents=prompt

                )


            text =
                response.text


            if not text:

                continue


            text =
                text.strip()


            if text.startswith(
                "```"
            ):

                text =
                    re.sub(

                        r"^```(?:json)?",

                        "",

                        text

                    )


                text =
                    re.sub(

                        r"```$",

                        "",

                        text

                    ).strip()


            parsed =
                json.loads(text)


            if isinstance(
                parsed,
                dict
            ):

                parsed =
                    parsed.get(
                        "articles",
                        []
                    )


            if not isinstance(
                parsed,
                list
            ):

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
# LIST CLEAN
# ============================================================

def clean_list(value):

    if not isinstance(
        value,
        list
    ):

        return []


    result = []


    for item in value:

        cleaned =
            clean(item)


        if cleaned:

            result.append(
                cleaned
            )


    return result


# ============================================================
# VOCABULARY
# ============================================================

def clean_vocabulary(value):

    if not isinstance(
        value,
        list
    ):

        return []


    result = []


    for item in value:

        if not isinstance(
            item,
            dict
        ):

            continue


        word =
            clean(
                item.get(
                    "word",
                    ""
                )
            )


        meaning =
            clean(

                item.get(

                    "hindi_meaning",

                    item.get(
                        "meaning_hindi",
                        ""
                    )

                )

            )


        if word and meaning:

            result.append(

                {
                    "word":
                        word,

                    "hindi_meaning":
                        meaning
                }

            )


    return result


# ============================================================
# CONVERT
# ============================================================

def convert_articles(
    generated,
    candidates
):

    output = []

    used = set()


    for article in generated:

        if not isinstance(
            article,
            dict
        ):

            continue


        try:

            source_number =
                int(

                    article.get(
                        "source_number",
                        -1
                    )

                )

        except Exception:

            continue


        if (

            source_number < 0

            or

            source_number >=
            len(candidates)

        ):

            continue


        source =
            candidates[
                source_number
            ]


        title =
            clean(

                article.get(
                    "headline",
                    ""
                )

            )


        if not valid_title(
            title
        ):

            continue


        article_hash =
            make_hash(
                title,
                source["url"]
            )


        if article_hash in used:

            continue


        used.add(
            article_hash
        )


        category =
            clean(

                article.get(
                    "category",
                    source["category"]
                )

            )


        if not category:

            category =
                source["category"]


        item = {

            "id": 0,

            "category":
                category,

            "headline":
                title,

            "story_lead":
                clean(
                    article.get(
                        "story_lead",
                        source["summary"]
                    )
                ),

            "why_in_news":
                clean(
                    article.get(
                        "why_in_news",
                        ""
                    )
                ),

            "background":
                clean(
                    article.get(
                        "background",
                        ""
                    )
                ),

            "detailed_analysis":
                clean(
                    article.get(
                        "detailed_analysis",
                        ""
                    )
                ),

            "key_facts":
                clean_list(
                    article.get(
                        "key_facts",
                        []
                    )
                ),

            "causes":
                clean(
                    article.get(
                        "causes",
                        ""
                    )
                ),

            "impact":
                clean(
                    article.get(
                        "impact",
                        ""
                    )
                ),

            "challenges":
                clean(
                    article.get(
                        "challenges",
                        ""
                    )
                ),

            "government_response":
                clean(
                    article.get(
                        "government_response",
                        ""
                    )
                ),

            "way_forward":
                clean(
                    article.get(
                        "way_forward",
                        ""
                    )
                ),

            "key_locations":
                clean_list(
                    article.get(
                        "key_locations",
                        []
                    )
                ),

            "important_dates":
                clean_list(
                    article.get(
                        "important_dates",
                        []
                    )
                ),

            "upsc_relevance":
                clean(
                    article.get(
                        "upsc_relevance",
                        ""
                    )
                ),

            "prelims_facts":
                clean_list(
                    article.get(
                        "prelims_facts",
                        []
                    )
                ),

            "mains_answer":
                clean(
                    article.get(
                        "mains_answer",
                        ""
                    )
                ),

            "takeaway":
                clean(
                    article.get(
                        "takeaway",
                        ""
                    )
                ),

            "vocabulary":
                clean_vocabulary(
                    article.get(
                        "vocabulary",
                        []
                    )
                ),

            "source_name":
                source["source_name"],

            "source_url":
                source["url"],

            "image_url":
                source["image_url"],

            "published_date":
                TODAY

        }


        output.append(
            item
        )


    return output


# ============================================================
# RSS FALLBACK
# ============================================================

def fallback_articles(
    candidates,
    number
):

    output = []


    for index, source in enumerate(
        candidates[:number]
    ):

        summary =
            source["summary"]


        if not summary:

            summary =
                "This current-affairs story "
                "is based on the latest report "
                "published by the listed source."


        item = {

            "id": 0,

            "category":
                source["category"],

            "headline":
                source["title"],

            "story_lead":
                summary,

            "why_in_news":
                summary,

            "background":
                "",

            "detailed_analysis":
                summary,

            "key_facts":
                [summary],

            "causes":
                "",

            "impact":
                "",

            "challenges":
                "",

            "government_response":
                "",

            "way_forward":
                "",

            "key_locations":
                [],

            "important_dates":
                [],

            "upsc_relevance":
                "Read the main facts and developments "
                "for current-affairs revision.",

            "prelims_facts":
                [summary],

            "mains_answer":
                summary,

            "takeaway":
                summary,

            "vocabulary":
                [],

            "source_name":
                source["source_name"],

            "source_url":
                source["url"],

            "image_url":
                source["image_url"]
                or
                choose_fallback_image(
                    source["category"],
                    index
                ),

            "published_date":
                TODAY

        }


        output.append(
            item
        )


    return output


# ============================================================
# MERGE
# ============================================================

def merge_news(
    old_news,
    new_news
):

    combined = []

    seen = set()


    for item in (
        old_news + new_news
    ):

        title =
            clean(

                item.get(
                    "headline",
                    ""
                )

            )


        url =
            clean(

                item.get(
                    "source_url",
                    ""
                )

            )


        if not title:

            continue


        article_hash =
            make_hash(
                title,
                url
            )


        if article_hash in seen:

            continue


        seen.add(
            article_hash
        )


        item["id"] =
            len(combined)


        combined.append(
            item
        )


        if (
            len(combined)
            >=
            MAX_DAILY_COUNT
        ):

            break


    return combined


# ============================================================
# DUPLICATE IMAGES
# ============================================================

def fix_duplicate_images(
    news
):

    used = set()


    for index, item in enumerate(
        news
    ):

        image =
            clean(

                item.get(
                    "image_url",
                    ""
                )

            )


        if (
            not image
            or
            image in used
        ):

            category =
                clean(

                    item.get(
                        "category",
                        "World"
                    )

                )


            image =
                choose_fallback_image(
                    category,
                    index
                )


        used.add(
            image
        )


        item["image_url"] =
            image


    return news


# ============================================================
# UPDATE TODAY
# ============================================================

def update_today():

    old_news =
        load_today()


    print(
        "Existing articles:",
        len(old_news)
    )


    if (
        len(old_news)
        >=
        MAX_DAILY_COUNT
    ):

        return old_news[
            :MAX_DAILY_COUNT
        ]


    candidates =
        collect_news()


    if not candidates:

        return old_news


    old_hashes =
        set()


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


    fresh = []


    for item in candidates:

        article_hash =
            make_hash(

                item["title"],

                item["url"]

            )


        if article_hash in old_hashes:

            continue


        fresh.append(
            item
        )


    print(
        "New candidates:",
        len(fresh)
    )


    if not fresh:

        return old_news


    if old_news:

        needed =
            min(

                UPDATE_COUNT,

                MAX_DAILY_COUNT
                - len(old_news)

            )

    else:

        needed =
            min(

                FIRST_RUN_COUNT,

                MAX_DAILY_COUNT

            )


    generated =
        generate_articles(
            fresh,
            needed
        )


    new_articles =
        convert_articles(
            generated,
            fresh
        )


    if not new_articles:

        print(
            "Gemini failed."
        )

        print(
            "Using RSS fallback."
        )


        new_articles =
            fallback_articles(
                fresh,
                needed
            )


    final_news =
        merge_news(

            old_news,

            new_articles

        )


    final_news =
        fix_duplicate_images(
            final_news
        )


    for index, item in enumerate(
        final_news
    ):

        item["id"] =
            index


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


    if os.path.exists(
        DATA_DIR
    ):

        for filename in os.listdir(
            DATA_DIR
        ):

            if not filename.endswith(
                ".json"
            ):

                continue


            name =
                filename[:-5]


            if re.fullmatch(
                r"\d{4}-\d{2}-\d{2}",
                name
            ):

                dates.append(
                    name
                )


    if TODAY not in dates:

        dates.append(
            TODAY
        )


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

        datetime.now()
        .timetuple()
        .tm_yday

        %

        len(quotes)

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


    news =
        update_today()


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


    dates =
        available_dates()


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
