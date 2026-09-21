import os
import json
import urllib.request
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

import feedparser


# ============================================================
# CONFIGURATION
# ============================================================

GEMINI_MODEL = "gemini-2.5-flash"

FEEDS = {
    "National": "https://www.thehindu.com/news/national/feeder/default.rss",
    "International": "https://www.thehindu.com/news/international/feeder/default.rss",
    "Defence": "https://indianexpress.com/section/india/feed/",
    "Economy": "https://www.thehindubusinessline.com/feeder/default.rss",
}

USER_AGENT = (
    "Mozilla/5.0 (compatible; AURA-Exam-AI/1.0; "
    "+https://github.com/)"
)


# ============================================================
# GET CURRENT DATE - INDIA
# ============================================================

def get_india_date():
    india_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    return india_now.strftime("%Y-%m-%d")


# ============================================================
# FETCH RSS NEWS
# ============================================================

def fetch_rss_headlines():
    headlines = []

    print("Fetching RSS feeds...")

    for category, feed_url in FEEDS.items():

        try:
            request = urllib.request.Request(
                feed_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/rss+xml, application/xml, text/xml",
                },
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                feed_data = response.read()

            parsed = feedparser.parse(feed_data)

            if not parsed.entries:
                print(f"WARNING: No entries found for {category}")
                continue

            count = 0

            for entry in parsed.entries:

                title = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", "").strip()

                if not title:
                    continue

                # Limit summary size so Gemini prompt does not become huge.
                summary = summary[:1500]

                headlines.append(
                    f"""
CATEGORY: {category}
HEADLINE: {title}
SUMMARY: {summary}
"""
                )

                count += 1

                if count >= 5:
                    break

            print(f"{category}: {count} articles collected")

        except Exception as e:
            print(f"WARNING: RSS failed for {category}: {type(e).__name__}: {e}")

    if not headlines:
        raise RuntimeError(
            "No RSS news could be fetched from any configured source."
        )

    # Limit total source material.
    headlines = headlines[:20]

    return "\n".join(headlines)


# ============================================================
# VALIDATE GEMINI OUTPUT
# ============================================================

def validate_app_data(data):

    if not isinstance(data, dict):
        raise ValueError("Gemini response is not a JSON object.")

    news = data.get("news")
    quizzes = data.get("quizzes")

    if not isinstance(news, list):
        raise ValueError("Missing or invalid 'news' array.")

    if not isinstance(quizzes, list):
        raise ValueError("Missing or invalid 'quizzes' array.")

    if len(news) != 12:
        raise ValueError(
            f"Expected exactly 12 news entries, received {len(news)}."
        )

    if len(quizzes) != 4:
        raise ValueError(
            f"Expected exactly 4 quizzes, received {len(quizzes)}."
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
        "reason",
        "mission",
        "conclusion",
    ]

    for index, item in enumerate(news, start=1):

        if not isinstance(item, dict):
            raise ValueError(f"News item {index} is not an object.")

        for field in required_news_fields:
            if field not in item:
                raise ValueError(
                    f"News item {index} is missing field: {field}"
                )

        item["id"] = index

    for index, quiz in enumerate(quizzes, start=1):

        if not isinstance(quiz, dict):
            raise ValueError(f"Quiz {index} is not an object.")

        if "question" not in quiz:
            raise ValueError(f"Quiz {index} missing question.")

        if "options" not in quiz:
            raise ValueError(f"Quiz {index} missing options.")

        if "answer" not in quiz:
            raise ValueError(f"Quiz {index} missing answer.")

        if not isinstance(quiz["options"], list):
            raise ValueError(f"Quiz {index} options are not an array.")

        if len(quiz["options"]) != 4:
            raise ValueError(
                f"Quiz {index} must have exactly 4 options."
            )

        answer = quiz["answer"]

        if not isinstance(answer, int) or answer not in range(4):
            raise ValueError(
                f"Quiz {index} answer must be 0, 1, 2, or 3."
            )

    return data


# ============================================================
# GENERATE CURRENT AFFAIRS WITH GEMINI
# ============================================================

def generate_affairs_and_quiz(news_text):

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. "
            "Add it under GitHub Repository → Settings → "
            "Secrets and variables → Actions."
        )

    today = get_india_date()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent"
    )

    prompt = f"""
You are AURA EXAM AI, an expert current-affairs editor for Indian
competitive examinations.

Today's date in India is: {today}

SOURCE NEWS:
{news_text}

IMPORTANT RULES:

1. Generate EXACTLY 12 current-affairs entries.
2. Generate EXACTLY 4 MCQs.
3. Focus on information useful for:
   - UPSC
   - SSC
   - Banking
   - State PCS
   - NDA
   - CDS
   - Defence examinations
   - Teaching/government examinations

4. Use CURRENT and VERIFIED information.
5. Use the provided news as the primary source material.
6. You may use Google Search to verify facts and fill important gaps.
7. NEVER invent names, dates, missions, places, ministers or officers.
8. If a field genuinely does not apply, use "N/A".
9. Do not repeat the same event.
10. Give a balanced mixture of:
    Defence
    Schemes
    International
    National
    Economy
    Science & Tech

11. The "reason" field must explain why the event matters for exams.
12. The "conclusion" field must give the key exam takeaway.
13. "date" should contain the relevant date or period.
14. "mission" should contain the mission/scheme/project/operation name,
    or "N/A".
15. "image_url" should contain a direct HTTPS image URL only if you
    have a reliable image URL. Otherwise use an empty string "".
16. Do NOT put markdown around the JSON.
17. Return ONLY valid JSON.

Each news item MUST contain:

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

The final JSON structure MUST be:

{{
  "news": [
    {{
      "id": 1,
      "category": "Defence",
      "title": "Example title",
      "image_url": "",
      "date": "{today}",
      "place": "New Delhi, India",
      "persons_ministers": "Name / N/A",
      "officers": "Designation / N/A",
      "countries_states": "India / N/A",
      "reason": "Why important for competitive exams",
      "mission": "Mission / Scheme / Project / N/A",
      "conclusion": "Key exam takeaway"
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
  ]
}}
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],

        # Real-time Google Search grounding
        "tools": [
            {
                "google_search": {}
            }
        ],

        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",

            "responseSchema": {
                "type": "OBJECT",
                "properties": {

                    "news": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "id": {"type": "INTEGER"},
                                "category": {"type": "STRING"},
                                "title": {"type": "STRING"},
                                "image_url": {"type": "STRING"},
                                "date": {"type": "STRING"},
                                "place": {"type": "STRING"},
                                "persons_ministers": {"type": "STRING"},
                                "officers": {"type": "STRING"},
                                "countries_states": {"type": "STRING"},
                                "reason": {"type": "STRING"},
                                "mission": {"type": "STRING"},
                                "conclusion": {"type": "STRING"},
                            },
                            "required": [
                                "id",
                                "category",
                                "title",
                                "image_url",
                                "date",
                                "place",
                                "persons_ministers",
                                "officers",
                                "countries_states",
                                "reason",
                                "mission",
                                "conclusion",
                            ],
                        },
                    },

                    "quizzes": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "question": {"type": "STRING"},
                                "options": {
                                    "type": "ARRAY",
                                    "items": {"type": "STRING"},
                                },
                                "answer": {"type": "INTEGER"},
                            },
                            "required": [
                                "question",
                                "options",
                                "answer",
                            ],
                        },
                    },
                },

                "required": [
                    "news",
                    "quizzes"
                ],
            },
        },
    }

    request_data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=request_data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": USER_AGENT,
        },
    )

    print("Calling Gemini API...")
    print(f"Model: {GEMINI_MODEL}")
    print(f"Date: {today}")

    try:

        with urllib.request.urlopen(request, timeout=120) as response:
            response_body = response.read().decode("utf-8")

    except urllib.error.HTTPError as e:

        error_body = e.read().decode("utf-8", errors="replace")

        print("\n========== GEMINI API ERROR ==========")
        print(f"HTTP STATUS: {e.code}")
        print(error_body)
        print("======================================\n")

        raise RuntimeError(
            f"Gemini API request failed with HTTP {e.code}."
        ) from e

    except urllib.error.URLError as e:

        raise RuntimeError(
            f"Could not connect to Gemini API: {e}"
        ) from e

    except Exception as e:

        raise RuntimeError(
            f"Unexpected Gemini API error: {type(e).__name__}: {e}"
        ) from e

    try:
        result = json.loads(response_body)
    except json.JSONDecodeError as e:
        print("Gemini returned invalid outer JSON:")
        print(response_body[:5000])
        raise RuntimeError("Gemini API returned invalid JSON.") from e

    # Safely extract generated text
    try:
        candidates = result["candidates"]

        if not candidates:
            raise ValueError("Gemini returned no candidates.")

        content = candidates[0]["content"]
        parts = content.get("parts", [])

        text_parts = [
            part.get("text", "")
            for part in parts
            if part.get("text")
        ]

        if not text_parts:
            raise ValueError("Gemini response contained no text.")

        text_content = "".join(text_parts).strip()

    except Exception as e:

        print("Unexpected Gemini response:")
        print(json.dumps(result, indent=2)[:8000])

        raise RuntimeError(
            f"Could not extract generated content: {e}"
        ) from e

    try:
        data = json.loads(text_content)
    except json.JSONDecodeError as e:

        print("\n========== INVALID GEMINI JSON ==========")
        print(text_content[:10000])
        print("=========================================\n")

        raise RuntimeError(
            "Gemini generated text that was not valid JSON."
        ) from e

    return validate_app_data(data)


# ============================================================
# UPDATE INDEX.HTML
# ============================================================

def update_index_html(data):

    if not os.path.exists("index.html"):
        raise FileNotFoundError(
            "index.html not found in repository root."
        )

    with open("index.html", "r", encoding="utf-8") as file:
        html_content = file.read()

    json_string = json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    )

    # Prevent a generated "</script>" from breaking the HTML.
    json_string = json_string.replace(
        "</script>",
        "<\\/script>"
    )

    start_marker = "/* AURA_DATA_START */"
    end_marker = "/* AURA_DATA_END */"

    start_index = html_content.find(start_marker)
    end_index = html_content.find(end_marker)

    if start_index == -1 or end_index == -1:
        raise RuntimeError(
            "AURA data markers were not found in index.html. "
            "Add the markers exactly as shown in the updated index code."
        )

    data_start = start_index + len(start_marker)

    updated_html = (
        html_content[:data_start]
        + "\n    const appData = "
        + json_string
        + ";\n    "
        + html_content[end_index:]
    )

    with open("index.html", "w", encoding="utf-8") as file:
        file.write(updated_html)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("AURA EXAM AI - DAILY CURRENT AFFAIRS UPDATE")
    print("=" * 60)

    try:

        print("\n[1/3] Fetching RSS news...")
        headlines = fetch_rss_headlines()

        print("\n[2/3] Generating current affairs with Gemini...")
        app_data = generate_affairs_and_quiz(headlines)

        print("\n[3/3] Updating index.html...")
        update_index_html(app_data)

        print("\nSUCCESS!")
        print(f"News entries: {len(app_data['news'])}")
        print(f"Quiz questions: {len(app_data['quizzes'])}")
        print("index.html successfully updated.")

    except Exception as e:

        print("\n" + "=" * 60)
        print("AURA UPDATE FAILED")
        print("=" * 60)
        print(f"ERROR TYPE: {type(e).__name__}")
        print(f"ERROR: {e}")
        print("=" * 60)

        raise
