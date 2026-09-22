import os
import json
import re
import urllib.request
import urllib.error
import feedparser
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

GEMINI_MODEL = "gemini-2.5-flash"

GOOGLE_NEWS_FEEDS = {
    "National": "https://news.google.com/rss/search?q=India+government+OR+India+national+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "Defence": "https://news.google.com/rss/search?q=India+defence+military+DRDO+Army+Navy+Air+Force+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "Economy": "https://news.google.com/rss/search?q=India+economy+RBI+budget+banking+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "International": "https://news.google.com/rss/search?q=international+world+India+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "Science & Tech": "https://news.google.com/rss/search?q=India+science+technology+space+ISRO+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "Schemes": "https://news.google.com/rss/search?q=India+government+scheme+mission+yojana+when%3A2d&hl=en-IN&gl=IN&ceid=IN%3Aen"
}


# ============================================================
# RSS NEWS FETCHING
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_rss_headlines():

    all_news = []

    print("Fetching current news from RSS feeds...")

    for category, url in GOOGLE_NEWS_FEEDS.items():

        try:
            parsed = feedparser.parse(url)

            print(
                f"{category}: "
                f"{len(parsed.entries)} RSS entries found"
            )

            for entry in parsed.entries[:8]:

                title = clean_text(
                    getattr(entry, "title", "")
                )

                summary = clean_text(
                    getattr(entry, "summary", "")
                )

                published = clean_text(
                    getattr(entry, "published", "")
                )

                if not title:
                    continue

                all_news.append({
                    "category": category,
                    "title": title,
                    "summary": summary[:1000],
                    "published": published
                })

        except Exception as e:
            print(
                f"WARNING: Could not fetch {category}: {e}"
            )

    if len(all_news) < 5:

        raise RuntimeError(
            "RSS fetching returned too few news articles. "
            "Aborting update so existing website data is not destroyed."
        )

    # Remove duplicate headlines
    unique = []
    seen = set()

    for item in all_news:

        key = re.sub(
            r"[^a-z0-9]",
            "",
            item["title"].lower()
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    print(
        f"Total unique news articles collected: {len(unique)}"
    )

    return unique


# ============================================================
# GEMINI
# ============================================================

def call_gemini(news_items):

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from GitHub Actions Secrets."
        )

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
        f"?key={api_key}"
    )

    news_text = ""

    for i, item in enumerate(news_items[:40], start=1):

        news_text += f"""
NEWS {i}
Category: {item['category']}
Headline: {item['title']}
Published: {item['published']}
Summary: {item['summary']}
-------------------------
"""

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    prompt = f"""
You are generating DAILY CURRENT AFFAIRS for Indian competitive
exams such as UPSC, SSC, Banking, CDS, NDA, CAPF and State PCS.

TODAY'S DATE:
{today}

IMPORTANT:
The supplied news below contains REAL RSS news headlines.

You MUST use REAL news events from the supplied material.

DO NOT invent events.

DO NOT create generic sample news.

DO NOT use placeholders.

DO NOT write phrases such as:
- "Actual current-affairs headline"
- "A concise summary"
- "Relevant exam concepts"
- "What happened"
- "Where it happened"
- "Who or which institution is involved"
- "Why it matters"
- "National#1 of 1"
- "Sample Question"
- "Title here"
- "N/A" when factual information is available

Do not return Markdown.

Do not return links.

Do not return explanations outside JSON.

============================================================
SOURCE NEWS
============================================================

{news_text}

============================================================
TASK
============================================================

Select exactly 12 DISTINCT and genuinely useful current-affairs
events from the supplied news.

Use a balanced mixture of:

Defence
National
International
Economy
Government Schemes
Science & Technology

For each item provide:

id
category
title
image_url
date
place
persons_ministers
officers
countries_states
reason
mission
conclusion

IMPORTANT:
"title" must be the REAL headline/event.

"reason" must explain why the event matters for competitive exams.

"conclusion" must contain the actual key takeaway.

If a field genuinely does not apply, use "Not applicable".
Do NOT invent names, officers or dates.

For image_url:
Use a relevant stable Unsplash image URL.
It does not need to represent the exact news event.
If you cannot provide one, use an empty string.

============================================================
QUIZ
============================================================

Create exactly 4 MCQs from the 12 current-affairs entries.

Each question must have:

question
options: exactly 4 options
answer: integer 0, 1, 2 or 3

Questions must test factual knowledge from the generated news.

============================================================
MOTIVATION
============================================================

Create ONE short motivational line specifically for competitive
exam aspirants.

Maximum 20 words.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Required structure:

{{
  "news": [
    {{
      "id": 1,
      "category": "Defence",
      "title": "REAL NEWS HEADLINE",
      "image_url": "",
      "date": "2026-09-22",
      "place": "Actual location",
      "persons_ministers": "Actual person or Not applicable",
      "officers": "Actual officer/designation or Not applicable",
      "countries_states": "Actual countries/states",
      "reason": "Why this matters for competitive exams",
      "mission": "Mission/Scheme/Project or Not applicable",
      "conclusion": "Actual key takeaway"
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
  ],
  "motivational": "Short motivational line"
}}

Again:

EXACTLY 12 news items.
EXACTLY 4 quiz questions.
ONE motivational line.
REAL NEWS ONLY.
NO PLACEHOLDER TEXT.
VALID JSON ONLY.
"""

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
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(request, timeout=90) as response:

            raw = response.read().decode("utf-8")

            result = json.loads(raw)

    except urllib.error.HTTPError as e:

        error_body = e.read().decode("utf-8", errors="ignore")

        print("GEMINI HTTP ERROR:")
        print(error_body)

        raise RuntimeError(
            f"Gemini API HTTP {e.code}"
        )

    except Exception as e:

        raise RuntimeError(
            f"Gemini API request failed: {e}"
        )

    try:

        text_content = (
            result["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

    except Exception:

        print("Unexpected Gemini response:")
        print(json.dumps(result, indent=2))

        raise RuntimeError(
            "Could not extract generated JSON from Gemini."
        )

    # Remove accidental Markdown fences
    text_content = re.sub(
        r"^```json\s*",
        "",
        text_content.strip(),
        flags=re.IGNORECASE
    )

    text_content = re.sub(
        r"\s*```$",
        "",
        text_content.strip()
    )

    try:

        data = json.loads(text_content)

    except json.JSONDecodeError as e:

        print("INVALID GEMINI JSON:")
        print(text_content)

        raise RuntimeError(
            f"Gemini returned invalid JSON: {e}"
        )

    return data


# ============================================================
# VALIDATION
# ============================================================

PLACEHOLDER_PHRASES = [
    "actual current-affairs headline",
    "a concise summary",
    "relevant exam concepts",
    "what happened",
    "where it happened",
    "who or which institution is involved",
    "why it matters",
    "national#1 of 1",
    "sample question",
    "title here"
]


def contains_placeholder(value):

    if not isinstance(value, str):
        return False

    lower = value.lower()

    return any(
        phrase in lower
        for phrase in PLACEHOLDER_PHRASES
    )


def validate_data(data):

    if not isinstance(data, dict):
        raise RuntimeError(
            "Generated data is not a JSON object."
        )

    news = data.get("news")
    quizzes = data.get("quizzes")
    motivational = data.get("motivational")

    if not isinstance(news, list):
        raise RuntimeError(
            "Generated news is not a list."
        )

    if len(news) != 12:
        raise RuntimeError(
            f"Expected exactly 12 news items, got {len(news)}."
        )

    if not isinstance(quizzes, list):
        raise RuntimeError(
            "Generated quizzes are not a list."
        )

    if len(quizzes) != 4:
        raise RuntimeError(
            f"Expected exactly 4 quizzes, got {len(quizzes)}."
        )

    if not isinstance(motivational, str):
        raise RuntimeError(
            "Motivational message is missing."
        )

    if not motivational.strip():
        raise RuntimeError(
            "Motivational message is empty."
        )

    # Validate news
    for index, item in enumerate(news, start=1):

        required = [
            "id",
            "category",
            "title",
            "date",
            "place",
            "persons_ministers",
            "officers",
            "countries_states",
            "reason",
            "mission",
            "conclusion"
        ]

        for field in required:

            if field not in item:
                raise RuntimeError(
                    f"News item {index} missing field: {field}"
                )

        for field in required:

            if contains_placeholder(
                item.get(field, "")
            ):

                raise RuntimeError(
                    f"Placeholder detected in "
                    f"news item {index}, field {field}: "
                    f"{item[field]}"
                )

        if not item["title"].strip():
            raise RuntimeError(
                f"News item {index} has empty title."
            )

    # Validate quizzes
    for index, quiz in enumerate(quizzes, start=1):

        if not quiz.get("question"):
            raise RuntimeError(
                f"Quiz {index} has no question."
            )

        options = quiz.get("options")

        if not isinstance(options, list):
            raise RuntimeError(
                f"Quiz {index} options are invalid."
            )

        if len(options) != 4:
            raise RuntimeError(
                f"Quiz {index} does not have exactly 4 options."
            )

        answer = quiz.get("answer")

        if answer not in [0, 1, 2, 3]:
            raise RuntimeError(
                f"Quiz {index} has invalid answer index."
            )

        if contains_placeholder(
            quiz["question"]
        ):
            raise RuntimeError(
                f"Placeholder detected in quiz {index}."
            )

    print("VALIDATION PASSED")
    print("News:", len(news))
    print("Quizzes:", len(quizzes))
    print("Motivation: OK")


# ============================================================
# UPDATE INDEX.HTML
# ============================================================

def update_index_html(data):

    if not os.path.exists("index.html"):

        raise FileNotFoundError(
            "index.html not found."
        )

    with open(
        "index.html",
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()

    json_data = json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    )

    pattern = r"const\s+appData\s*=\s*\{.*?\};"

    replacement = (
        "const appData = "
        + json_data
        + ";"
    )

    updated_html, count = re.subn(
        pattern,
        replacement,
        html,
        flags=re.DOTALL
    )

    if count != 1:

        raise RuntimeError(
            "Could not locate the appData block in index.html."
        )

    with open(
        "index.html",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(updated_html)

    print(
        "index.html successfully updated."
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("AURA EXAM AI - DAILY UPDATE")
    print("=" * 60)

    print("\n1. Fetching real news...")

    news_items = fetch_rss_headlines()

    print("\n2. Generating current affairs with Gemini...")

    data = call_gemini(news_items)

    print("\n3. Validating generated content...")

    validate_data(data)

    print("\n4. Updating index.html...")

    update_index_html(data)

    print("\n" + "=" * 60)
    print("UPDATE SUCCESSFUL")
    print("=" * 60)
