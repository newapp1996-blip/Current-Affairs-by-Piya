import os
import json
import re
import time
import urllib.request
import feedparser
from google import genai
from google.genai import types

# ============================================================
# 1. LIVE RSS NEWS FETCHING
# ============================================================

FEEDS = {
    "National": "https://www.thehindu.com/news/national/feeder/default.rss",
    "International": "https://www.thehindu.com/news/international/feeder/default.rss",
    "Business": "https://www.thehindubusinessline.com/feeder/default.rss",
    "PIB Release": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
    "Sci-Tech": "https://www.thehindu.com/sci-tech/feeder/default.rss"
}

def fetch_rss_headlines():
    headlines = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for category, url in FEEDS.items():
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                parsed = feedparser.parse(response.read())
                for entry in parsed.entries[:5]: # Extract top 5 per feed
                    summary = getattr(entry, 'summary', '')
                    clean_summary = re.sub(r'<[^>]+>', '', summary)[:250]
                    headlines.append(f"[{category}] {entry.title}: {clean_summary}")
        except Exception as e:
            print(f"Warning: Feed error for {category}: {e}")
    
    return "\n\n".join(headlines)

# ============================================================
# 2. GEMINI GENERATION WITH MINISTRY DETAILS
# ============================================================

def generate_affairs_and_quiz(news_text):
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set in GitHub Secrets.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
You are an expert competitive exam strategist for UPSC, SSC CGL, Banking, and State PCS.
Analyze these live headlines and generate EXACTLY 15 distinct current affairs entries.

LIVE HEADLINES:
{news_text}

For EACH entry, extract:
1. id: (integer 1 to 15)
2. category: (Defence, Schemes, National, International, Economy, Science & Tech, Sports)
3. title: (Clean factual news headline)
4. image_url: ("https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800")
5. date: (Current date in YYYY-MM-DD format)
6. place: (City / State / Country)
7. person_name: (Full name of the Minister or key Leader / Personality involved, or "N/A")
8. ministry_portfolio: (Exact Ministry / Portfolio controlled by them, e.g., "Ministry of Defence", "Ministry of Finance", or "N/A")
9. officers: (Key secretaries/military officers involved, or "N/A")
10. countries_states: (States/Countries involved)
11. reason: (Exam relevance explanation)
12. mission: (Scheme/Project/Operation name, or "N/A")
13. conclusion: (Key summary takeaway)

Also generate 5 exam-style multiple-choice questions based on these items.

Return ONLY a single valid JSON object formatted as:
{{
  "news": [
    {{
      "id": 1,
      "category": "National",
      "title": "Title here",
      "image_url": "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800",
      "date": "2026-09-21",
      "place": "New Delhi",
      "person_name": "Rajnath Singh",
      "ministry_portfolio": "Ministry of Defence",
      "officers": "General Anil Chauhan (CDS)",
      "countries_states": "India",
      "reason": "Crucial for national security and governance questions",
      "mission": "Operation Raksha",
      "conclusion": "Strengthened national defense framework"
    }}
  ],
  "quizzes": [
    {{
      "question": "Sample Question?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": 0
    }}
  ]
}}
"""

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    
    for model_name in models_to_try:
        try:
            print(f"Generating news with {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=8192,
                    response_mime_type="application/json"
                ),
            )

            if response and response.text:
                data = json.loads(response.text.strip())
                if "news" in data and len(data["news"]) >= 10:
                    return data
        except Exception as e:
            print(f"Model {model_name} error: {e}")
            time.sleep(2)

    raise RuntimeError("All Gemini API models failed to generate valid news data.")

# ============================================================
# 3. MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    print("Fetching live news feeds...")
    news_text = fetch_rss_headlines()

    print("Generating news data...")
    app_data = generate_affairs_and_quiz(news_text)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(app_data, f, indent=2)

    print(f"Successfully updated data.json with {len(app_data['news'])} news items!")
    
