import os
import json
import re
import urllib.request
import urllib.error
import feedparser
from html import unescape


# ============================================================
# AURA EXAM AI
# DAILY CURRENT AFFAIRS AUTO UPDATE
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
        "GEMINI_API_KEY is missing. "
        "Add GEMINI_API_KEY to GitHub Repository Secrets."
    )


# IMPORTANT:
# Updated Gemini model
MODEL = "gemini-3.6-flash"


# ============================================================
# GOOGLE NEWS RSS FEEDS
# ============================================================

GOOGLE_NEWS_FEEDS = {

    "National":
        "https://news.google.com/rss/search?"
        "q=India+government+OR+India+national+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen",

    "Defence":
        "https://news.google.com/rss/search?"
        "q=India+defence+military+DRDO+Army+Navy+Air+Force+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen",

    "Economy":
        "https://news.google.com/rss/search?"
        "q=India+economy+RBI+budget+banking+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen",

    "International":
        "https://news.google.com/rss/search?"
        "q=international+world+India+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen",

    "Science & Tech":
        "https://news.google.com/rss/search?"
        "q=India+science+technology+space+ISRO+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen",

    "Schemes":
        "https://news.google.com/rss/search?"
        "q=India+government+scheme+mission+yojana+when%3A2d"
        "&hl=en-IN&gl=IN&ceid=IN%3Aen"
}


# ============================================================
# PLACEHOLDER PHRASES
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

    if text is None:
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
# FETCH RSS NEWS
# ============================================================

def fetch_news():

    print("Fetching current news from RSS feeds...")

    all_articles = []
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

                title_key = title.lower()

                if title_key in seen_titles:
                    continue

                seen_titles.add(title_key)

                all_articles.append({

                    "category": category,

                    "title": title,

                    "summary": summary,

                    "link": link,

                    "published": published

                })

        except Exception as error:

            print(
                f"RSS error for {category}: "
                f"{error}"
            )


    print(
        f"Total unique news articles collected: "
        f"{len(all_articles)}"
    )


    if len(all_articles) < 12:

        raise RuntimeError(
            "Not enough real news articles were "
            "collected from RSS feeds."
        )


    return all_articles


# ============================================================
# CREATE GEMINI PROMPT
# ============================================================

def build_prompt(news_items):

    news_text = []

    for index, item in enumerate(news_items, start=1):

        news_text.append(
            f"""
NEWS ITEM {index}

Category:
{item["category"]}

Headline:
{item["title"]}

Summary:
{item["summary"]}

Published:
{item["published"]}

Source Link:
{item["link"]}
"""
        )


    joined_news = "\n".join(news_text)


    prompt = f"""
You are the current-affairs editor for AURA EXAM AI.

Your task is to convert the REAL news material below into
exam-focused current affairs for Indian competitive exams.

Target exams include:

- NDA
- CDS
- UPSC
- SSC
- Banking
- Railway
- State PSC
- CTET
- KVS
- NVS
- Other government competitive examinations


IMPORTANT RULES:

1. Use ONLY REAL NEWS EVENTS contained in the supplied RSS material.

2. DO NOT invent events.

3. DO NOT create generic or fictional news.

4. DO NOT write templates.

5. DO NOT use placeholder text.

6. DO NOT write:
   - "Actual current-affairs headline"
   - "A concise summary"
   - "What happened"
   - "Where it happened"
   - "Who or which institution is involved"
   - "Why it matters"
   - "Relevant exam concepts"
   - "Sample Question"
   - "Title here"
   - "National#1 of 1"

7. Every title must describe a real event from the supplied material.

8. Select exactly 12 DISTINCT and important current-affairs events.

9. Avoid selecting multiple articles about exactly the same event.

10. Prefer events involving:
    - Government
    - Defence
    - International relations
    - Economy
    - RBI
    - Science
    - Space
    - Technology
    - Government schemes
    - Important appointments
    - Summits
    - Agreements
    - Missions
    - Important reports
    - Important national developments

11. Write in clear English suitable for competitive-exam preparation.

12. Do not use Markdown.

13. Do not add explanations outside the JSON.

14. Return ONLY valid JSON.


FOR EACH NEWS ARTICLE RETURN:

{
  "id": "unique-number",
  "category": "category",
  "title": "real news headline",
  "image_url": "",
  "date": "date or date description",
  "place": "place if relevant",
  "persons_ministers": "important people involved",
  "officers": "important officers or institutions",
  "countries_states": "countries or Indian states involved",
  "mission": "mission, scheme, operation or initiative if applicable",
  "reason": "why the event matters",
  "conclusion": "short exam-focused conclusion",
  "exam_relevance": "important exam fact or concept"
}


IMAGE RULE:

For image_url, return an empty string unless a reliable direct
image URL is available from the supplied information.

DO NOT invent image URLs.


ALSO GENERATE EXACTLY 4 MCQs.

Each MCQ must be directly based on the generated current affairs.

MCQ FORMAT:

{
  "question": "question",
  "options": [
    "option A",
    "option B",
    "option C",
    "option D"
  ],
  "answer": 0
}

The answer field must be the zero-based index:

0 = option A
1 = option B
2 = option C
3 = option D


ALSO GENERATE ONE SHORT DAILY MOTIVATIONAL MESSAGE.

It must be original and suitable for competitive-exam students.


FINAL JSON FORMAT:

{
  "news": [
    {
      "id": "1",
      "category": "...",
      "title": "...",
      "image_url": "",
      "date": "...",
      "place": "...",
      "persons_ministers": "...",
      "officers": "...",
      "countries_states": "...",
      "mission": "...",
      "reason": "...",
      "conclusion": "...",
      "exam_relevance": "..."
    }
  ],
  "quizzes": [
    {
      "question": "...",
      "options": [
        "...",
        "...",
        "...",
        "..."
      ],
      "answer": 0
    }
  ],
  "motivational": "..."
}


REQUIREMENTS:

Exactly 12 news articles.

Exactly 4 quizzes.

Exactly 4 options for every quiz.

Every answer must be 0, 1, 2 or 3.

Every news article must contain a real headline.

No placeholders.

No Markdown.

No text outside JSON.


REAL RSS NEWS MATERIAL:

{joined_news}
"""

    return prompt


# ============================================================
# CALL GEMINI
# ============================================================

def call_gemini(news_items):

    print("Sending real news to Gemini...")
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

            "responseMimeType":
                "application/json"

        }

    }


    data = json.dumps(
        payload
    ).encode("utf-8")


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
            timeout=120
        ) as response:

            response_body =
                response.read().decode("utf-8")

            result =
                json.loads(response_body)


    except urllib.error.HTTPError as error:

        error_body = ""

        try:
            error_body =
                error.read().decode("utf-8")

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

        print(
            "Unexpected Gemini response:"
        )

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


    try:

        parsed =
            json.loads(text)

    except json.JSONDecodeError as error:

        print(
            "Gemini returned invalid JSON:"
        )

        print(text)

        raise RuntimeError(
            f"Gemini JSON parsing failed: {error}"
        )


    return parsed


# ============================================================
# VALIDATE GEMINI OUTPUT
# ============================================================

def validate_data(data):

    print("Validating Gemini output...")


    if not isinstance(data, dict):

        raise RuntimeError(
            "Gemini output is not a JSON object."
        )


    news =
        data.get("news")


    quizzes =
        data.get("quizzes")


    motivational =
        data.get("motivational")


    # --------------------------------------------------------
    # NEWS COUNT
    # --------------------------------------------------------

    if not isinstance(news, list):

        raise RuntimeError(
            "Gemini news field is not a list."
        )


    if len(news) != 12:

        raise RuntimeError(
            f"Expected exactly 12 news articles, "
            f"received {len(news)}."
        )


    # --------------------------------------------------------
    # QUIZ COUNT
    # --------------------------------------------------------

    if not isinstance(quizzes, list):

        raise RuntimeError(
            "Gemini quizzes field is not a list."
        )


    if len(quizzes) != 4:

        raise RuntimeError(
            f"Expected exactly 4 quizzes, "
            f"received {len(quizzes)}."
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


    # --------------------------------------------------------
    # NEWS VALIDATION
    # --------------------------------------------------------

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


    for index, article in enumerate(news):

        if not isinstance(
            article,
            dict
        ):

            raise RuntimeError(
                f"News item {index + 1} is invalid."
            )


        for field in required_fields:

            if field not in article:

                raise RuntimeError(
                    f"News item {index + 1} "
                    f"is missing field: {field}"
                )


        title =
            str(
                article.get(
                    "title",
                    ""
                )
            ).strip()


        if not title:

            raise RuntimeError(
                f"News item {index + 1} "
                "has an empty title."
            )


        article_text =
            json.dumps(
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


    # --------------------------------------------------------
    # DUPLICATE TITLE CHECK
    # --------------------------------------------------------

    titles = []

    for article in news:

        title =
            str(
                article["title"]
            ).strip().lower()

        titles.append(title)


    if len(set(titles)) != len(titles):

        raise RuntimeError(
            "Duplicate news titles detected."
        )


    # --------------------------------------------------------
    # QUIZ VALIDATION
    # --------------------------------------------------------

    for index, quiz in enumerate(quizzes):

        if not isinstance(
            quiz,
            dict
        ):

            raise RuntimeError(
                f"Quiz {index + 1} is invalid."
            )


        question =
            str(
                quiz.get(
                    "question",
                    ""
                )
            ).strip()


        options =
            quiz.get("options")


        answer =
            quiz.get("answer")


        if not question:

            raise RuntimeError(
                f"Quiz {index + 1} "
                "has an empty question."
            )


        if not isinstance(
            options,
            list
        ):

            raise RuntimeError(
                f"Quiz {index + 1} "
                "options are invalid."
            )


        if len(options) != 4:

            raise RuntimeError(
                f"Quiz {index + 1} "
                f"must have exactly 4 options."
            )


        try:

            answer =
                int(answer)

        except Exception:

            raise RuntimeError(
                f"Quiz {index + 1} "
                "answer must be 0, 1, 2 or 3."
            )


        if answer not in [0, 1, 2, 3]:

            raise RuntimeError(
                f"Quiz {index + 1} "
                "answer index is invalid."
            )


        quiz_text =
            json.dumps(
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


    print(
        "Validation successful."
    )

    print(
        f"News articles: {len(news)}"
    )

    print(
        f"Quiz questions: {len(quizzes)}"
    )

    print(
        "Motivation: available"
    )


# ============================================================
# UPDATE INDEX.HTML
# ============================================================

def update_index(data):

    print(
        "Updating index.html..."
    )


    index_file = "index.html"


    if not os.path.exists(
        index_file
    ):

        raise RuntimeError(
            "index.html was not found."
        )


    with open(
        index_file,
        "r",
        encoding="utf-8"
    ) as file:

        html =
            file.read()


    # --------------------------------------------------------
    # Remove any accidentally existing old appData
    # --------------------------------------------------------

    new_app_data =
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        )


    replacement =
        "const appData = " \
        + new_app_data \
        + ";"


    pattern =
        r"const\s+appData\s*=\s*\{.*?\};"


    updated_html, count =
        re.subn(
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


    news_items =
        fetch_news()


    print(
        "\n2. Generating current affairs with Gemini..."
    )


    data =
        call_gemini(
            news_items
        )


    print(
        "\n3. Validating generated content..."
    )


    validate_data(
        data
    )


    print(
        "\n4. Updating website..."
    )


    update_index(
        data
    )


    print(
        "\n" + "=" * 60
    )

    print(
        "AURA EXAM AI UPDATE COMPLETED SUCCESSFULLY"
    )

    print(
        "=" * 60
    )


if __name__ == "__main__":

    main()
