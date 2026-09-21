import os
import json
import re
import time
import urllib.request
from datetime import datetime
import feedparser
from google import genai
from google.genai import types

# Get today's execution date
TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

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
                for entry in parsed.entries[:8]: # Fetch latest entries per feed
                    summary = getattr(entry, 'summary', '')
                    clean_summary = re.sub(r'<[^>]+>', '', summary)[:250]
                    pub_date = getattr(entry, 'published', getattr(entry, 'updated', 'Recent'))
                    headlines.append(f"[{category}] (Published: {pub_date}) {entry.title}: {clean_summary}")
        except Exception as e:
            print(f"Warning: Feed error for {category}: {e}")
    
    return "\n\n".join(headlines)

# ============================================================
# 2. GEMINI GENERATION WITH DYNAMIC MODEL & STRICT DATE FILTERING
# ============================================================

def generate_affairs_and_quiz(news_text):
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set in GitHub Secrets.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Retrieve available models directly from API to avoid hardcoded name mismatches
    available_models = []
    try:
        for m in client.models.list():
            if hasattr(m, 'supported_generation_methods') and 'generateContent' in m.supported_generation_methods:
                model_id = m.name.replace("models/", "")
                available_models.append(model_id)
            elif hasattr(m, 'name'):
                model_id = m.name.replace("models/", "")
                available_models.append(model_id)
    except Exception as e:
        print(f"Could not list models: {e}")

    if not available_models:
        available_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

    print(f"Discovered available models for key: {available_models}")

    prompt = f"""
You are an expert competitive exam strategist for UPSC, SSC CGL, Banking, and State PCS.
Today's date is strictly {TODAY_DATE}.

Analyze these live headlines and generate EXACTLY 15 distinct, fresh current affairs entries.
IMPORTANT: Ensure all extracted entries represent active current affairs. The "date" field MUST be set to "{TODAY_DATE}".

LIVE HEADLINES:
{news_text}

For EACH entry, extract:
1. id: (integer 1 to 15)
2. category: (Defence, Schemes, National, International, Economy, Science & Tech, Sports)
3. title: (Clean factual news headline)
4. image_url: ("https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800")
5. date: ("{TODAY_DATE}")
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
      "date": "{TODAY_DATE}",
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

    for model_name in available_models:
        try:
            print(f"Generating news with model: {model_name}...")
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
                    # Enforce current execution date across all items
                    for item in data["news"]:
                        item["date"] = TODAY_DATE
                    return data
        except Exception as e:
            print(f"Model {model_name} error: {e}")
            time.sleep(1)

    raise RuntimeError("All Gemini API models failed to generate valid news data.")

# ============================================================
# 3. MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    print(f"Fetching live news feeds for date: {TODAY_DATE}...")
    news_text = fetch_rss_headlines()

    print("Generating news data...")
    app_data = generate_affairs_and_quiz(news_text)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(app_data, f, indent=2)

    print(f"Successfully updated data.json with {len(app_data['news'])} news items dated {TODAY_DATE}!")
