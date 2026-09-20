import os
import json
import re
import feedparser
from google import genai
from google.genai import types

FEEDS = {
    "National": "https://www.thehindu.com/news/national/feeder/default.rss",
    "International": "https://www.thehindu.com/news/international/feeder/default.rss",
    "Defence": "https://indianexpress.com/section/india/feed/"
}

def fetch_rss_headlines():
    headlines = []
    for category, url in FEEDS.items():
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:3]:
                summary = getattr(entry, 'summary', '')
                headlines.append(f"[{category}] {entry.title}: {summary}")
        except Exception as e:
            print(f"Warning: RSS feed issue for {category}: {e}")
    
    if not headlines:
        headlines.append("[Defence] Joint tri-service military exercise initiated.")
        headlines.append("[National] Government introduces new education grant.")

    return "\n".join(headlines)

def generate_affairs_and_quiz(news_text):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY secret is missing or empty in GitHub Settings!")

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
You are an expert exam strategist for Indian competitive exams.
Analyze these news items:

{news_text}

Task:
1. Extract 4 distinct current affairs headlines (1 Defence, 1 Schemes, 1 International, 1 National).
2. Create 2 multiple-choice quiz questions based on them.

Return ONLY a valid JSON object with this exact structure:
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
    if not os.path.exists("index.html"):
        raise FileNotFoundError("index.html not found in repository root.")
        
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
    headlines = fetch_rss_headlines()
    
    print("Generating current affairs with Gemini...")
    app_data = generate_affairs_and_quiz(headlines)
    
    print("Updating index.html...")
    update_index_html(app_data)
    print("Update complete!")
