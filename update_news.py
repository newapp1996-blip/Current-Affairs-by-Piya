import os
import json
import re
import feedparser
from google import genai

# RSS Feeds for National, Defence, International News
FEEDS = {
    "National": "https://www.thehindu.com/news/national/feeder/default.rss",
    "International": "https://www.thehindu.com/news/international/feeder/default.rss",
    "Defence": "https://indianexpress.com/section/india/feed/"
}

def fetch_rss_headlines():
    headlines = []
    for category, url in FEEDS.items():
        parsed = feedparser.parse(url)
        for entry in parsed.entries[:3]:
            headlines.append(f"[{category}] {entry.title}: {entry.summary if 'summary' in entry else ''}")
    return "\n".join(headlines)

def generate_affairs_and_quiz(news_text):
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    prompt = f"""
You are an expert exam strategist for Indian competitive exams (UPSC, Defence, Teaching).
Based on the following recent news items:

{news_text}

Task:
1. Extract 4 distinct, high-yield current affairs headlines (1 Defence, 1 Schemes, 1 International, 1 National).
2. Create 2 multiple-choice questions based on these events.

Return ONLY a strictly valid JSON object matching this exact structure:
{{
  "news": [
    {{
      "category": "Defence",
      "title": "Short title",
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
        contents=prompt
    )
    
    # Clean up JSON text response
    clean_json = re.sub(r'```json\s*|\s*```', '', response.text).strip()
    return json.loads(clean_json)

def update_index_html(data):
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    # Formatted JS object string replacement
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
    
    print("Updating index.html...")
    update_index_html(app_data)
    print("Success! index.html updated.")
