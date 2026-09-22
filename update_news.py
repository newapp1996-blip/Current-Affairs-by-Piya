import os
import json
import re
import time
import html
import urllib.request
import urllib.error
import feedparser
from datetime import datetime, timezone


# ============================================================
# AURA EXAM AI - CONFIGURATION
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

# Current Gemini models confirmed in Google's API documentation.
# We try the primary model first and fall back if necessary.
GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

OUTPUT_FILE = "data.json"


# ============================================================
# GOOGLE NEWS RSS FEEDS
# ============================================================

GOOGLE_NEWS_FEEDS = {

    "National": (
        "https://news.google.com/rss/search?"
        "q=India+government+OR+India+national+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen"
    ),

    "Defence": (
        "https://news.google.com/rss/search?"
        "q=India+defence+military+DRDO+Army+Navy+Air+Force+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen"
    ),

    "Economy": (
        "https://news.google.com/rss/search?"
        "q=India+economy+RBI+budget+banking+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen"
    ),

    "International": (
        "https://news.google.com/rss/search?"
        "q=international+world+India+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen"
    ),

    "Science & Tech": (
        "https://news.google.com/rss/search?"
        "q=India+science+technology+space+ISRO+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen"
    ),

    "Schemes": (
        "https://news.google.com/rss/search?"
        "q=India+government+scheme+mission+yojana+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen"
    ),
}


# ============================================================
# PLACEHOLDER DETECTION
# ============================================================

FORBIDDEN_PHRASES = [
    "actual current-affairs headline",
    "actual current affairs headline",
    "a concise summary",
    "what happened",
    "where it happened",
    "who or which institution is involved",
    "why it matters",
    "relevant exam concepts",
    "relevant exam concept",
    "sample question",
    "sample answer",
    "title here",
    "headline here",
    "summary here",
    "insert headline",
    "insert summary",
    "your headline",
    "your summary",
    "national#1 of 1",
    "national #1 of 1",
]


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


# ============================================================
# FETCH NEWS
# ============================================================

def fetch_news():
    all_items = []
    seen_titles = set()

    for category, url in GOOGLE_NEWS_FEEDS.items():

        print(f"Fetching {category} news...")

        try:
            feed = feedparser.parse(url)

            count = 0

            for entry in feed.entries[:10]:

                title = clean_text(
                    getattr(entry, "title", "")
                )

                summary = clean_text(
                    getattr(entry, "summary", "")
                )

                link = getattr(entry, "link", "")

                published = clean_text(
                    getattr(entry, "published", "")
                )

                if not title:
                    continue

                title_key = re.sub(
                    r"[^a-z0-9]+",
                    "",
                    title.lower()
                )

                if title_key in seen_titles:
                    continue

                seen_titles.add(title_key)

                all_items.append({
                    "category": category,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published": published,
                })

                count += 1

            print(f"  {count} articles collected.")

        except Exception as e:
            print(
                f"  ERROR fetching {category}: {e}"
            )

    print()
    print(
        f"TOTAL RSS ARTICLES COLLECTED: {len(all_items)}"
    )

    if len(all_items) < 12:
        raise RuntimeError(
            "Not enough real news articles were collected."
        )

    return all_items


# ============================================================
# GEMINI PROMPT
# ============================================================

def build_prompt(news_items):

    news_text = []

    for i, item in enumerate(news_items[:50], start=1):

        news_text.append(
            f"""
ARTICLE {i}
CATEGORY: {item["category"]}
TITLE: {item["title"]}
SUMMARY: {item["summary"]}
PUBLISHED: {item["published"]}
LINK: {item["link"]}
""".strip()
        )

    joined_news = "\n\n".join(news_text)

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    prompt = f"""
You are the Current Affairs Editor for AURA EXAM AI.

Today: {today}

You are given REAL recent news articles collected from Google News RSS.

Your job is to create a high-quality current-affairs package for Indian competitive-exam students.

TARGET EXAMS:
- NDA
- CDS
- UPSC
- SSC
- Banking
- Railways
- State government exams
- Defence examinations

IMPORTANT:
Use ONLY facts supported by the supplied news articles.

DO NOT invent events.
DO NOT create fictional headlines.
DO NOT create placeholder content.
DO NOT write generic examples.
DO NOT use phrases such as:
"Actual current-affairs headline"
"Sample question"
"Headline here"
"Summary here"

Select the most important REAL current affairs.

Create EXACTLY 12 news items.

Each news item must contain:

id
category
title
image_url
date
place
persons_ministers
officers
countries_states
mission
reason
conclusion

For image_url:
Use an empty string if no reliable image URL is available.
DO NOT invent image URLs.

For date:
Use the actual date from the supplied article when possible.

For place:
Mention the relevant city/state/country if supported.

For persons_ministers:
Mention important people actually involved.

For officers:
Mention relevant officers only if actually supported.

For countries_states:
Mention relevant countries/states.

For mission:
Mention the relevant mission, operation, scheme, programme, project or initiative if applicable.

For reason:
Explain why the event matters for exam preparation.

For conclusion:
Give a concise exam-oriented takeaway.

Also create EXACTLY 4 multiple-choice questions.

Each quiz object must contain:

id
question
options
answer
explanation

"options" must contain exactly 4 choices.

"answer" must be the exact text of the correct option.

Questions must be based on the generated current affairs.

Also create one short motivational sentence.

RETURN ONLY VALID JSON.

Do not use Markdown.
Do not use ```json.
Do not add commentary outside JSON.

Required JSON structure:

{{
  "news": [],
  "quizzes": [],
  "motivational": ""
}}

REAL NEWS ARTICLES:
{joined_news}
"""

    return prompt


# ============================================================
# GEMINI REQUEST
# ============================================================

def request_gemini(model, prompt):

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "max_output_tokens": 20000
        }
    }

    body = json.dumps(
        payload
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": API_KEY
        },
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=120
    ) as response:

        response_body = response.read().decode(
            "utf-8"
        )

        return json.loads(
            response_body
        )


# ============================================================
# EXTRACT GEMINI TEXT
# ============================================================

def extract_gemini_text(response):

    try:
        candidates = response.get(
            "candidates",
            []
        )

        if not candidates:
            raise RuntimeError(
                "Gemini returned no candidates."
            )

        parts = candidates[0].get(
            "content",
            {}
        ).get(
            "parts",
            []
        )

        text_parts = []

        for part in parts:

            if "text" in part:
                text_parts.append(
                    part["text"]
                )

        text = "".join(
            text_parts
        ).strip()

        if not text:
            raise RuntimeError(
                "Gemini returned empty text."
            )

        return text

    except Exception as e:
        raise RuntimeError(
            f"Unable to extract Gemini response: {e}"
        )


# ============================================================
# CLEAN JSON RESPONSE
# ============================================================

def parse_json_response(text):

    text = text.strip()

    # Remove accidental Markdown fences.
    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            raise RuntimeError(
                "Gemini did not return valid JSON."
            )

        try:
            return json.loads(
                text[start:end + 1]
            )
        except Exception as e:
            raise RuntimeError(
                f"Invalid Gemini JSON: {e}"
            )


# ============================================================
# CALL GEMINI WITH FALLBACKS
# ============================================================

def call_gemini(news_items):

    if not API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing."
        )

    prompt = build_prompt(
        news_items
    )

    last_error = None

    for model in GEMINI_MODELS:

        print()
        print(
            f"Trying Gemini model: {model}"
        )

        for attempt in range(1, 4):

            try:

                print(
                    f"Attempt {attempt}/3..."
                )

                response = request_gemini(
                    model,
                    prompt
                )

                text = extract_gemini_text(
                    response
                )

                data = parse_json_response(
                    text
                )

                print(
                    f"Gemini generation successful using {model}"
                )

                return data

            except urllib.error.HTTPError as e:

                error_body = e.read().decode(
                    "utf-8",
                    errors="replace"
                )

                print(
                    f"Gemini HTTP {e.code}: {error_body}"
                )

                last_error = (
                    f"HTTP {e.code}: {error_body}"
                )

                if e.code in {
                    429,
                    500,
                    502,
                    503,
                    504
                }:

                    if attempt < 3:
                        wait_time = 15 * attempt

                        print(
                            f"Retrying in {wait_time} seconds..."
                        )

                        time.sleep(
                            wait_time
                        )

                        continue

                break

            except Exception as e:

                print(
                    f"Gemini error: {e}"
                )

                last_error = str(e)

                if attempt < 3:

                    wait_time = 10 * attempt

                    print(
                        f"Retrying in {wait_time} seconds..."
                    )

                    time.sleep(
                        wait_time
                    )

                    continue

                break

        print(
            f"Model {model} failed. Trying next model..."
        )

    raise RuntimeError(
        "All Gemini models failed.\n"
        f"Last error: {last_error}"
    )


# ============================================================
# VALIDATE GENERATED DATA
# ============================================================

def validate_data(data):

    if not isinstance(data, dict):
        raise RuntimeError(
            "Generated data is not a JSON object."
        )

    news = data.get(
        "news"
    )

    quizzes = data.get(
        "quizzes"
    )

    motivational = data.get(
        "motivational"
    )

    if not isinstance(news, list):
        raise RuntimeError(
            "news is not a list."
        )

    if not isinstance(quizzes, list):
        raise RuntimeError(
            "quizzes is not a list."
        )

    if len(news) < 12:
        raise RuntimeError(
            f"Only {len(news)} news items generated. "
            "At least 12 are required."
        )

    if len(quizzes) < 4:
        raise RuntimeError(
            f"Only {len(quizzes)} quizzes generated. "
            "At least 4 are required."
        )

    if not isinstance(
        motivational,
        str
    ):
        raise RuntimeError(
            "Motivational message is invalid."
        )

    required_news_fields = [
        "id",
        "category",
        "title",
        "image_url",
        "date",
        "place",
        "persons_ministers",
        "officers",
        "countries_states",
        "mission",
        "reason",
        "conclusion",
    ]

    for index, item in enumerate(
        news[:12],
        start=1
    ):

        if not isinstance(item, dict):
            raise RuntimeError(
                f"News item {index} is invalid."
            )

        for field in required_news_fields:

            if field not in item:
                raise RuntimeError(
                    f"News item {index} missing field: {field}"
                )

        title = str(
            item.get("title", "")
        ).lower()

        for forbidden in FORBIDDEN_PHRASES:

            if forbidden.lower() in title:

                raise RuntimeError(
                    "Placeholder headline detected: "
                    f"{item.get('title')}"
                )

    required_quiz_fields = [
        "id",
        "question",
        "options",
        "answer",
        "explanation",
    ]

    for index, quiz in enumerate(
        quizzes[:4],
        start=1
    ):

        if not isinstance(
            quiz,
            dict
        ):
            raise RuntimeError(
                f"Quiz {index} is invalid."
            )

        for field in required_quiz_fields:

            if field not in quiz:
                raise RuntimeError(
                    f"Quiz {index} missing field: {field}"
                )

        options = quiz.get(
            "options"
        )

        if not isinstance(
            options,
            list
        ) or len(options) != 4:

            raise RuntimeError(
                f"Quiz {index} must have exactly 4 options."
            )

        if quiz["answer"] not in options:

            raise RuntimeError(
                f"Quiz {index} answer does not match an option."
            )

    print(
        f"Validation successful: "
        f"{len(news[:12])} news + "
        f"{len(quizzes[:4])} quizzes"
    )


# ============================================================
# WRITE DATA.JSON
# ============================================================

def write_data_json(data):

    output = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "news": data["news"][:12],

        "quizzes": data["quizzes"][:4],

        "motivational": data.get(
            "motivational",
            "Stay consistent. Every question solved today strengthens tomorrow's performance."
        )
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        "data.json updated successfully."
    )

    print(
        f"News saved: {len(output['news'])}"
    )

    print(
        f"Quizzes saved: {len(output['quizzes'])}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("AURA EXAM AI - CURRENT AFFAIRS UPDATE")
    print("=" * 70)

    print()
    print("1. Fetching real news...")
    news_items = fetch_news()

    print()
    print("2. Generating current affairs with Gemini...")
    data = call_gemini(
        news_items
    )

    print()
    print("3. Validating generated data...")
    validate_data(
        data
    )

    print()
    print("4. Writing data.json...")
    write_data_json(
        data
    )

    print()
    print("=" * 70)
    print("AURA EXAM AI UPDATE COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    main()
