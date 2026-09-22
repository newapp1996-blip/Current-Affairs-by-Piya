import os
import json
import re
import urllib.request
import urllib.error
import feedparser
from html import unescape


# ============================================================
# AURA EXAM AI - DAILY CURRENT AFFAIRS UPDATE
# ============================================================

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
# FORBIDDEN PLACEHOLDER TEXT
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
# CLEAN TEXT
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = unescape(str(text))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# FETCH NEWS
# ============================================================

def fetch_news():

    print("Fetching current news from RSS feeds...")

    articles = []
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

                link = clean_text(
                    entry.get("link", "")
                )

                published = clean_text(
                    entry.get("published", "")
                )

                if not title:
                    continue

                key = title.lower()

                if key in seen_titles:
                    continue

                seen_titles.add(key)

                articles.append({
                    "category": category,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published": published
                })

        except Exception as error:

            print(
                f"RSS error in {category}: {error}"
            )

    print(
        f"Total unique news articles collected: "
        f"{len(articles)}"
    )

    if len(articles) < 12:
        raise RuntimeError(
            "Fewer than 12 real news articles were "
            "collected from the RSS feeds."
        )

    return articles


# ============================================================
# BUILD GEMINI PROMPT
# ============================================================

def build_prompt(news_items):

    news_text = []

    for number, item in enumerate(
        news_items,
        start=1
    ):

        news_text.append(
            f"""
NEWS ITEM {number}

Category:
{item["category"]}

Headline:
{item["title"]}

Summary:
{item["summary"]}

Published:
{item["published"]}

Source:
{item["link"]}
"""
        )

    joined_news = "\n".join(news_text)

    return f"""
You are the current-affairs editor for AURA EXAM AI.

Convert the REAL news material below into exam-focused
current affairs for Indian competitive examinations.

Target exams:

NDA
CDS
UPSC
SSC
Banking
Railway
State PSC
CTET
KVS
NVS


STRICT RULES:

1. Use ONLY real events contained in the supplied news.

2. Do NOT invent news.

3. Do NOT create fictional events.

4. Do NOT use template text.

5. Do NOT use placeholders.

6. Select exactly 12 DISTINCT important news events.

7. Avoid duplicate events.

8. Prefer important developments involving:
   Government
   Defence
   Economy
   RBI
   International relations
   Science
   Space
   Technology
   Government schemes
   Appointments
   Summits
   Agreements
   Missions
   Important reports

9. Write clear English suitable for competitive exams.

10. Return ONLY valid JSON.

11. Do NOT use Markdown.

12. Do NOT write anything outside the JSON.

13. Never use these phrases:

Actual current-affairs headline
A concise summary
What happened
Where it happened
Who or which institution is involved
Why it matters
Relevant exam concepts
Sample Question
Title here
Headline here
Summary here
National#1 of 1


NEWS FORMAT:

Each news object must contain:

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


For image_url:

Return an empty string unless a reliable direct image
URL is available from the supplied material.

Do NOT invent image URLs.


Generate exactly 4 MCQs.

Each MCQ must have:

question
options
answer

There must be exactly 4 options.

answer must be:

0 = option A
1 = option B
2 = option C
3 = option D


Also generate ONE short original motivational message.


FINAL JSON FORMAT:

{{
  "news": [
    {{
      "id": "1",
      "category": "National",
      "title": "Real headline",
      "image_url": "",
      "date": "date",
      "place": "place",
      "persons_ministers": "people involved",
      "officers": "officers or institutions",
      "countries_states": "countries or states",
      "mission": "mission or scheme",
      "reason": "why it matters",
      "conclusion": "exam-focused conclusion",
      "exam_relevance": "important exam fact"
    }}
  ],

  "quizzes": [
    {{
      "question": "Question",
      "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
      ],
      "answer": 0
    }}
  ],

  "motivational": "Daily motivational message"
}}


REQUIREMENTS:

Exactly 12 news articles.
Exactly 4 quizzes.
Exactly 4 options per quiz.
Answer must be 0, 1, 2 or 3.
No placeholders.
No duplicate news.
No Markdown.
No text outside JSON.


REAL NEWS MATERIAL:

{joined_news}
"""


# ============================================================
# CALL GEMINI
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

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=120
        ) as response:

            response_body = response.read().decode(
                "utf-8"
            )

            result = json.loads(
                response_body
            )

    except urllib.error.HTTPError as error:

        error_body = ""

        try:
            error_body = error.read().decode(
                "utf-8"
            )
        except Exception:
            pass

        print("GEMINI HTTP ERROR:")
        print(error_body)

        raise RuntimeError(
            f"Gemini API HTTP {error.code}\n"
            f"Error: {error_body}"
        )

    except Exception as error:

        raise RuntimeError(
            f"Gemini request failed: {error}"
        )

    try:

        text = (
            result["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

    except Exception:

        print("Unexpected Gemini response:")
        print(
            json.dumps(
                result,
                indent=2
            )
        )

        raise RuntimeError(
            "Could not extract Gemini response."
        )

    text = text.strip()

    # Remove accidental Markdown fences

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    try:

        parsed = json.loads(text)

    except json.JSONDecodeError as error:

        print("Gemini returned invalid JSON:")
        print(text)

        raise RuntimeError(
            f"Gemini JSON parsing failed: {error}"
        )

    return parsed


# ============================================================
# VALIDATE OUTPUT
# ============================================================

def validate_data(data):

    print("Validating Gemini output...")

    if not isinstance(data, dict):
        raise RuntimeError(
            "Gemini output is not a JSON object."
        )

    news = data.get("news")
    quizzes = data.get("quizzes")
    motivational = data.get("motivational")

    # --------------------------------------------------------
    # NEWS
    # --------------------------------------------------------

    if not isinstance(news, list):
        raise RuntimeError(
            "The news field is not a list."
        )

    if len(news) != 12:
        raise RuntimeError(
            f"Expected 12 news articles, "
            f"received {len(news)}."
        )

    required_fields = [
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

    titles = []

    for index, article in enumerate(news):

        if not isinstance(article, dict):
            raise RuntimeError(
                f"News item {index + 1} is invalid."
            )

        for field in required_fields:

            if field not in article:
                raise RuntimeError(
                    f"News item {index + 1} "
                    f"is missing: {field}"
                )

        title = str(
            article.get("title", "")
        ).strip()

        if not title:
            raise RuntimeError(
                f"News item {index + 1} "
                "has an empty title."
            )

        titles.append(
            title.lower()
        )

        article_text = json.dumps(
            article,
            ensure_ascii=False
        ).lower()

        for phrase in FORBIDDEN_PHRASES:

            if phrase.lower() in article_text:

                raise RuntimeError(
                    f"Placeholder detected in "
                    f"news item {index + 1}: "
                    f"{phrase}"
                )

    if len(set(titles)) != len(titles):
        raise RuntimeError(
            "Duplicate news titles detected."
        )

    # --------------------------------------------------------
    # QUIZZES
    # --------------------------------------------------------

    if not isinstance(quizzes, list):
        raise RuntimeError(
            "The quizzes field is not a list."
        )

    if len(quizzes) != 4:
        raise RuntimeError(
            f"Expected 4 quizzes, "
            f"received {len(quizzes)}."
        )

    for index, quiz in enumerate(quizzes):

        if not isinstance(quiz, dict):
            raise RuntimeError(
                f"Quiz {index + 1} is invalid."
            )

        question = str(
            quiz.get("question", "")
        ).strip()

        options = quiz.get("options")
        answer = quiz.get("answer")

        if not question:
            raise RuntimeError(
                f"Quiz {index + 1} "
                "has an empty question."
            )

        if not isinstance(options, list):
            raise RuntimeError(
                f"Quiz {index + 1} "
                "options are invalid."
            )

        if len(options) != 4:
            raise RuntimeError(
                f"Quiz {index + 1} "
                "must have exactly 4 options."
            )

        try:
            answer = int(answer)
        except Exception:
            raise RuntimeError(
                f"Quiz {index + 1} "
                "has an invalid answer."
            )

        if answer not in [0, 1, 2, 3]:
            raise RuntimeError(
                f"Quiz {index + 1} "
                "answer must be 0, 1, 2 or 3."
            )

        quiz_text = json.dumps(
            quiz,
            ensure_ascii=False
        ).lower()

        for phrase in FORBIDDEN_PHRASES:

            if phrase.lower() in quiz_text:

                raise RuntimeError(
                    f"Placeholder detected in "
                    f"quiz {index + 1}: "
                    f"{phrase}"
                )

    # --------------------------------------------------------
    # MOTIVATION
    # --------------------------------------------------------

    if not isinstance(
        motivational,
        str
    ) or not motivational.strip():

        raise RuntimeError(
            "Motivational message is empty."
        )

    print("Validation successful.")
    print(f"News articles: {len(news)}")
    print(f"Quiz questions: {len(quizzes)}")
    print("Motivational message: available")


# ============================================================
# UPDATE INDEX.HTML
# ============================================================

def update_index(data):

    print("Updating index.html...")

    index_file = "index.html"

    if not os.path.exists(index_file):
        raise RuntimeError(
            "index.html was not found."
        )

    with open(
        index_file,
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
        r"const\s+appData\s*=\s*"
        r"\{.*?\};"
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
            "Could not locate "
            "'const appData = {...};' "
            "inside index.html."
        )

    with open(
        index_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(updated_html)

    print(
        "index.html updated successfully."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("1. Fetching real news...")

    news_items = fetch_news()

    print()
    print("2. Generating current affairs with Gemini...")

    data = call_gemini(news_items)

    print()
    print("3. Validating generated content...")

    validate_data(data)

    print()
    print("4. Updating website...")

    update_index(data)

    print()
    print("=" * 60)
    print(
        "AURA EXAM AI UPDATE COMPLETED SUCCESSFULLY"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
