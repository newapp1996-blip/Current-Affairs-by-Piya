import os
import json
import re
import feedparser
from google import genai
from google.genai import types

# RSS Feeds for National, Defence, and International News
FEEDS = {
    "National": "https://www.thehindu.com/news/national/feeder/default.rss",
    "International": "https://www.thehindu.com/news/international/feeder/default.rss",
    "Defence": "https://indianexpress.com/section/india/feed/"
}

def fetch_rss_headlines():
    """Fetches top headlines from specified RSS feeds."""
    headlines = []
    for category, url in FEEDS.items():
        parsed = feedparser.parse(url)
        for entry in parsed.entries[:3]:
            summary = entry.summary if 'summary' in entry else ''
            headlines.append(f"[{category}] {entry.title}: {summary}")
    return "\n".join(headlines)

def generate_affairs_and_quiz(news_text):
    """Generates current affairs items and multiple choice quiz questions using Gemini API."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing or empty in GitHub Secrets.")

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
You are an expert exam strategist for Indian competitive exams (UPSC, Defence, Teaching, SSC).
Analyze these recent news items:

{news_text}

Task:
1. Extract 4 distinct, high-yield current affairs headlines (1 Defence, 1 Schemes, 1 International, 1 National). Assign sequential integer IDs (1, 2, 3, 4).
2. Create 2 multiple-choice questions directly based on these news events.

Return ONLY a strictly valid JSON object matching this exact structure:
{{
  "news": [
    {{
      "id": 1,
      "category": "Defence",
      "title": "Headline title",
      "detail": "Exam relevant brief breakdown."
    }}
  ],
  "quizzes": [
    {{
      "question": "Question text?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": 0
    }}
  ]
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)

def update_index_html(data):
    """Replaces the existing `appData` JavaScript object inside index.html with new content."""
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    json_str = json.dumps(data, indent=2)
    updated_html = re.sub(
        r'const appData = \{.*?\};',
        f'const appData = {json_str};',
        html_content,
        flags=re.DOTALL
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(updated_html)

if __name__ == "__main__":
    print("Fetching news feeds...")
    news_headlines = fetch_rss_headlines()
    
    print("Generating current affairs and quizzes with Gemini...")
    app_data = generate_affairs_and_quiz(news_headlines)
    
    print("Updating index.html with generated content...")
    update_index_html(app_data)
    print("Success! index.html updated.")
