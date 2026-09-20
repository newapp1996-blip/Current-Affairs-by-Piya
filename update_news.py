import os
import json
import re
import feedparser
from google import genai
from google.genai import types

FEEDS = {
    "National": "https://www.thehindu.com/news/national/feeder/default.rss",
    "International": "https://www.thehindu.com/news/international/feeder/default.rss",
    "Defence": "https://indianexpress.com/section/india/feed/",
    "Economy": "https://www.thehindubusinessline.com/feeder/default.rss"
}

def fetch_rss_headlines():
    headlines = []
    for category, url in FEEDS.items():
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:4]:
                summary = getattr(entry, 'summary', '')
                headlines.append(f"[{category}] {entry.title}: {summary}")
        except Exception as e:
            print(f"Warning: RSS feed issue for {category}: {e}")
    
    if not headlines:
        headlines.append("[Defence] Tri-service military exercise conducted in Indian Ocean region.")
        headlines.append("[National] Government releases national infrastructure updates.")

    return "\n".join(headlines[:15])

def generate_affairs_and_quiz(news_text):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY secret is missing or empty in GitHub Settings!")

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
You are an expert exam strategist for Indian competitive exams (UPSC, SSC, Banking, State PCS).
Analyze these news items:

{news_text}

Task:
1. Extract exactly 12 distinct current affairs entries across Defence, Schemes, International, National, Economy, Science & Tech.
2. For EACH current affair entry, provide complete detailed information for these exact fields:
   - id (1 to 12)
   - category (e.g. Defence, Schemes, International, National, Economy, Science & Tech)
   - title (Headline)
   - image_url (A relevant image topic query URL from Unsplash e.g. "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800" or similar high quality placeholder URL)
   - date (Important date / period e.g. September 2026)
   - place (Location / City / Region / State involved)
   - persons_ministers (Ministers / VIPs / Officials involved)
   - officers (Key administrative/military officers or designation)
   - countries_states (Countries or Indian States involved)
   - reason (Reason for importance for exams)
   - mission (Mission / Scheme / Project / Operation name or N/A)
   - conclusion (Summary / Impact / Key Takeaway)

3. Create 4 multiple-choice quiz questions based on these entries.

Return ONLY a valid JSON object formatted as follows:
{{
  "news": [
    {{
      "id": 1,
      "category": "Defence",
      "title": "Title here",
      "image_url": "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800",
      "date": "2026-09-20",
      "place": "New Delhi, India",
      "persons_ministers": "Defense Minister",
      "officers": "Chief of Defence Staff",
      "countries_states": "India & Partner Nations",
      "reason": "Crucial for national security questions in competitive exams",
      "mission": "Operation Raksha",
      "conclusion": "Strengthened defense posture and international cooperation"
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

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    text_content = response.text.strip()
    if "```json" in text_content:
        text_content = text_content.split("```json")[1].split("```")[0].strip()
    elif "```" in text_content:
        text_content = text_content.split("```")[1].split("```")[0].strip()

    return json.loads(text_content)

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
    
    print("Generating 12 detailed current affairs with Gemini...")
    app_data = generate_affairs_and_quiz(headlines)
    
    print("Updating index.html...")
    update_index_html(app_data)
    print("Update complete!")
