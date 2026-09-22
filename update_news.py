import os
import json
import re
import urllib.request
import urllib.error
import feedparser
import time
from html import unescape


print("=" * 60)
print("AURA EXAM AI - DAILY UPDATE")
print("=" * 60)


# ============================================================
# CONFIGURATION
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from GitHub Secrets."
    )

MODEL = "gemini-3.6-flash"

INDEX_FILE = "index.html"


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
    )
}


# ============================================================
# FORBIDDEN PLACEHOLDER PHRASES
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
    "national#1 of 1",
    "national #1 of 1",
    "insert headline",
    "insert summary",
    "your headline",
    "your summary"
]


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = unescape(str(text))

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# FETCH REAL NEWS
# ============================================================

def fetch_news():

    print("Fetching current news from RSS feeds...")

    all_news = []
    seen_titles = set()

    for category, feed_url in GOOGLE_NEWS_FEEDS.items():

        try:

            feed = feedparser.parse(feed_url)

            print(
                f"{category}: "
                f"{len(feed.entries)} RSS entries found"
            )

            for entry in feed.entries[:10]:

                title = clean_text(
                    entry.get("title", "")
                )

                summary = clean_text(
                    entry.get("summary", "")
                )

                link = entry.get(
                    "link",
                    ""
                )

                published = clean_text(
                    entry.get(
                        "published",
                        ""
                    )
                )

                if not title:
                    continue

                title_key = title.lower()

                if title_key in seen_titles:
                    continue

                seen_titles.add(title_key)

                all_news.append({

                    "category": category,

                    "title": title,

                    "summary": summary,

                    "link": link,

                    "published": published

                })

        except Exception as e:

            print(
                f"RSS error in {category}: {e}"
            )

    print(
        f"Total unique news articles collected: "
        f"{len(all_news)}"
    )

    if len(all_news) < 12:

        raise RuntimeError(
            "Not enough real news articles were collected."
        )

    return all_news


# ============================================================
# BUILD GEMINI PROMPT
# ============================================================

def build_prompt(news_items):

    news_text = ""

    for i, item in enumerate(
        news_items[:52],
        start=1
    ):

        news_text += (
            f"\nNEWS {i}\n"
            f"Category: {item['category']}\n"
            f"Title: {item['title']}\n"
            f"Summary: {item['summary']}\n"
            f"Published: {item['published']}\n"
            f"Source URL: {item['link']}\n"
        )

    prompt = f"""
You are the current affairs editor for AURA EXAM AI.

Create today's current affairs content for Indian competitive examinations.

TARGET EXAMS:
- NDA
- CDS
- UPSC
- SSC
- Banking
- Railway
- State government exams
- Other major Indian competitive examinations

IMPORTANT:

Use ONLY real events contained in the supplied news data.

Do NOT invent news.

Do NOT create fictional people, places, schemes, missions,
dates, organisations or events.

Select the most important and exam-relevant events.

Return EXACTLY:

12 current affairs articles

4 multiple-choice questions

1 motivational message

Each current affairs article must contain:

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
exam_relevance

Rules for current affairs:

- title must be the REAL headline/event
- summary/details must describe the REAL event
- place must be specific when available
- persons_ministers should contain relevant people only
- officers should contain relevant officers only
- countries_states should contain relevant countries/states
- mission should mention the relevant mission/programme if applicable
- reason should explain why the event matters
- conclusion should give the exam-oriented takeaway
- exam_relevance should mention relevant examination concepts
- Do not use placeholders
- Do not repeat the same event
- Do not fabricate information

IMAGE RULE:

image_url must be a valid publicly accessible image URL only if
one is available from the supplied information.

If no reliable image URL is available,
use an empty string.

MCQ RULES:

Create exactly 4 MCQs.

Each MCQ must have:

question
options

options must contain exactly 4 strings.

answer must be an integer:

0 = first option
1 = second option
2 = third option
3 = fourth option

Questions must be based on the supplied current affairs.

Avoid ambiguous questions.

The motivational message must be short and suitable for
students preparing for competitive examinations.

DO NOT return Markdown.

DO NOT return explanations outside the JSON.

Return ONLY valid JSON in this exact structure:

{{
  "news": [
    {{
      "id": "news-1",
      "category": "National",
      "title": "Real current affairs headline",
      "image_url": "",
      "date": "22 September 2026",
      "place": "",
      "persons_ministers": [],
      "officers": [],
      "countries_states": [],
      "mission": "",
      "reason": "",
      "conclusion": "",
      "exam_relevance": ""
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
  "motivational": "Short motivational message."
}}

NEWS DATA:

{news_text}
"""

    return prompt


# ============================================================
# CALL GEMINI WITH AUTOMATIC RETRIES
# ============================================================

def call_gemini(news_items):

    print("Generating current affairs with Gemini...")
    print(f"Gemini model: {MODEL}")

    prompt = build_prompt(news_items)

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        f"{MODEL}:generateContent?key={API_KEY}"
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

            "temperature": 0.2,

            "responseMimeType": "application/json"

        }

    }

    data = json.dumps(
        payload,
        ensure_ascii=False
    ).encode("utf-8")

    max_attempts = 5

    for attempt in range(
        1,
        max_attempts + 1
    ):

        print(
            f"Gemini API attempt "
            f"{attempt}/{max_attempts}..."
        )

        request = urllib.request.Request(

            url,

            data=data,

            headers={
                "Content-Type":
                "application/json"
            },

            method="POST"
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=180
            ) as response:

                response_body = (
                    response
                    .read()
                    .decode("utf-8")
                )

                result = json.loads(
                    response_body
                )

            text = (
                result
                ["candidates"][0]
                ["content"]
                ["parts"][0]
                ["text"]
            )

            text = text.strip()

            # Remove accidental Markdown fences
            if text.startswith(
                "```json"
            ):

                text = text[7:]

            elif text.startswith(
                "```"
            ):

                text = text[3:]

            if text.endswith(
                "```"
            ):

                text = text[:-3]

            text = text.strip()

            parsed = json.loads(text)

            print(
                "Gemini generation successful."
            )

            return parsed

        except urllib.error.HTTPError as e:

            error_body = (
                e.read()
                .decode(
                    "utf-8",
                    errors="replace"
                )
            )

            print(
                "GEMINI HTTP ERROR:"
            )

            print(error_body)

            # Temporary errors
            if e.code in (
                429,
                500,
                502,
                503,
                504
            ):

                if attempt < max_attempts:

                    wait_seconds = (
                        10 *
                        (2 ** (attempt - 1))
                    )

                    print(
                        f"Temporary Gemini "
                        f"error {e.code}."
                    )

                    print(
                        f"Retrying in "
                        f"{wait_seconds} "
                        f"seconds..."
                    )

                    time.sleep(
                        wait_seconds
                    )

                    continue

                raise RuntimeError(
                    f"Gemini API HTTP "
                    f"{e.code} after "
                    f"{max_attempts} "
                    f"attempts\n"
                    f"Error: "
                    f"{error_body}"
                )

            # Permanent errors
            raise RuntimeError(
                f"Gemini API HTTP "
                f"{e.code}\n"
                f"Error: "
                f"{error_body}"
            )

        except urllib.error.URLError as e:

            print(
                f"NETWORK ERROR: {e}"
            )

            if attempt < max_attempts:

                wait_seconds = (
                    10 *
                    (2 ** (attempt - 1))
                )

                print(
                    f"Retrying in "
                    f"{wait_seconds} "
                    f"seconds..."
                )

                time.sleep(
                    wait_seconds
                )

                continue

            raise RuntimeError(
                f"Gemini network error "
                f"after {max_attempts} "
                f"attempts: {e}"
            )

        except (
            json.JSONDecodeError,
            KeyError,
            IndexError
        ) as e:

            print(
                f"Invalid Gemini response: {e}"
            )

            if attempt < max_attempts:

                wait_seconds = (
                    10 *
                    (2 ** (attempt - 1))
                )

                print(
                    f"Retrying in "
                    f"{wait_seconds} "
                    f"seconds..."
                )

                time.sleep(
                    wait_seconds
                )

                continue

            raise RuntimeError(
                "Gemini returned an "
                "invalid response after "
                f"{max_attempts} attempts: "
                f"{e}"
            )

    raise RuntimeError(
        "Gemini generation failed unexpectedly."
    )


# ============================================================
# VALIDATE GENERATED DATA
# ============================================================

def validate_data(data):

    print("Validating generated data...")

    if not isinstance(
        data,
        dict
    ):

        raise RuntimeError(
            "Gemini output is not a JSON object."
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

    if not isinstance(
        news,
        list
    ):

        raise RuntimeError(
            "News is not a list."
        )

    if len(news) != 12:

        raise RuntimeError(
            f"Expected 12 news articles, "
            f"got {len(news)}."
        )

    if not isinstance(
        quizzes,
        list
    ):

        raise RuntimeError(
            "Quizzes is not a list."
        )

    if len(quizzes) != 4:

        raise RuntimeError(
            f"Expected 4 quizzes, "
            f"got {len(quizzes)}."
        )

    if not motivational:

        raise RuntimeError(
            "Motivational message is empty."
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
        "exam_relevance"

    ]

    titles = set()

    for index, item in enumerate(
        news,
        start=1
    ):

        if not isinstance(
            item,
            dict
        ):

            raise RuntimeError(
                f"News item {index} "
                f"is not an object."
            )

        for field in required_news_fields:

            if field not in item:

                raise RuntimeError(
                    f"News item {index} "
                    f"is missing field: "
                    f"{field}"
                )

        title = str(
            item["title"]
        ).strip()

        if not title:

            raise RuntimeError(
                f"News item {index} "
                f"has an empty title."
            )

        title_key = title.lower()

        if title_key in titles:

            raise RuntimeError(
                f"Duplicate news title: "
                f"{title}"
            )

        titles.add(
            title_key
        )

        full_text = json.dumps(
            item,
            ensure_ascii=False
        ).lower()

        for phrase in FORBIDDEN_PHRASES:

            if phrase in full_text:

                raise RuntimeError(
                    "Placeholder text detected "
                    f"in news item {index}: "
                    f"{phrase}"
                )

    for index, quiz in enumerate(
        quizzes,
        start=1
    ):

        if not isinstance(
            quiz,
            dict
        ):

            raise RuntimeError(
                f"Quiz {index} "
                f"is not an object."
            )

        if "question" not in quiz:

            raise RuntimeError(
                f"Quiz {index} "
                f"is missing question."
            )

        if "options" not in quiz:

            raise RuntimeError(
                f"Quiz {index} "
                f"is missing options."
            )

        if "answer" not in quiz:

            raise RuntimeError(
                f"Quiz {index} "
                f"is missing answer."
            )

        options = quiz["options"]

        if not isinstance(
            options,
            list
        ):

            raise RuntimeError(
                f"Quiz {index} "
                f"options are not a list."
            )

        if len(options) != 4:

            raise RuntimeError(
                f"Quiz {index} "
                f"must have exactly "
                f"4 options."
            )

        answer = quiz["answer"]

        if not isinstance(
            answer,
            int
        ) or answer not in range(4):

            raise RuntimeError(
                f"Quiz {index} "
                f"has invalid answer index."
            )

        quiz_text = json.dumps(
            quiz,
            ensure_ascii=False
        ).lower()

        for phrase in FORBIDDEN_PHRASES:

            if phrase in quiz_text:

                raise RuntimeError(
                    "Placeholder text detected "
                    f"in quiz {index}: "
                    f"{phrase}"
                )

    print(
        "Validation successful:"
    )

    print(
        "- 12 current affairs"
    )

    print(
        "- 4 MCQs"
    )

    print(
        "- 1 motivational message"
    )

    return True


# ============================================================
# UPDATE INDEX.HTML
# ============================================================

def update_index(data):

    print(
        "Updating index.html..."
    )

    if not os.path.exists(
        INDEX_FILE
    ):

        raise RuntimeError(
            "index.html not found."
        )

    with open(
        INDEX_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        html = file.read()

    app_data_json = json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    )

    replacement = (
        "const appData = "
        + app_data_json
        + ";"
    )

    pattern = (
        r"const\s+appData\s*="
        r"\s*\{.*?\};"
    )

    updated_html, count = re.subn(
        pattern,
        replacement,
        html,
        count=1,
        flags=re.DOTALL
    )

    if count != 1:

        raise RuntimeError(
            "Could not find the "
            "'const appData = {...};' "
            "section in index.html."
        )

    with open(
        INDEX_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            updated_html
        )

    print(
        "index.html updated successfully."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "1. Fetching real news..."
    )

    news_items = fetch_news()

    print()

    print(
        "2. Generating current "
        "affairs with Gemini..."
    )

    data = call_gemini(
        news_items
    )

    print()

    print(
        "3. Validating generated data..."
    )

    validate_data(
        data
    )

    print()

    print(
        "4. Updating website..."
    )

    update_index(
        data
    )

    print()

    print("=" * 60)

    print(
        "AURA EXAM AI UPDATE "
        "COMPLETED SUCCESSFULLY"
    )

    print("=" * 60)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
