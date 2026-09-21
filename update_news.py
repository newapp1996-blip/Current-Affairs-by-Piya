import os
import json
import re
import time
import urllib.request
import feedparser
from google import genai
from google.genai import types

# ============================================================
# 1. RSS NEWS FETCHING
# ============================================================

FEEDS = {
    "National": "https://www.thehindu.com/news/national/feeder/default.rss",
    "International": "https://www.thehindu.com/news/international/feeder/default.rss",
    "Defence": "https://www.pib.gov.in/RssMain.aspx?ModId=1&Lang=1",
    "Economy": "https://www.thehindubusinessline.com/feeder/default.rss"
}

def fetch_rss_headlines():
    headlines = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for category, url in FEEDS.items():
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                parsed = feedparser.parse(response.read())
                for entry in parsed.entries[:4]:
                    summary = getattr(entry, 'summary', '')
                    headlines.append(f"[{category}] {entry.title}: {summary}")
        except Exception as e:
            print(f"Warning: RSS Feed issue for {category}: {e}")
    
    if not headlines:
        headlines.append("[Defence] Tri-service military exercise conducted in Indian Ocean region.")
        headlines.append("[National] Government releases national infrastructure updates.")

    return "\n".join(headlines[:15])


# ============================================================
# 2. GEMINI GENERATION & FALLBACK DATA
# ============================================================

def get_fallback_data():
    return {
        "news": [
            {
                "id": 1,
                "category": "Defence",
                "title": "Tri-Service Exercise Sagar Shakti Executed in Indian Ocean Region",
                "image_url": "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800",
                "date": "2026-09-21",
                "place": "Indian Ocean Region",
                "persons_ministers": "Defense Minister",
                "officers": "Chief of Defence Staff",
                "countries_states": "India",
                "reason": "Crucial for national maritime defense strategy and tri-service integration topics.",
                "mission": "Exercise Sagar Shakti",
                "conclusion": "Enhanced joint operational readiness across Navy, Army, and Air Force divisions."
            },
            {
                "id": 2,
                "category": "National",
                "title": "Cabinet Approves Expansion of National Green Hydrogen Mission",
                "image_url": "https://images.unsplash.com/photo-1509391365360-2e959784a276?w=800",
                "date": "2026-09-21",
                "place": "New Delhi, India",
                "persons_ministers": "Union Power Minister",
                "officers": "Secretary, Ministry of New & Renewable Energy",
                "countries_states": "India",
                "reason": "High probability question topic for environmental initiatives and government schemes.",
                "mission": "National Green Hydrogen Mission",
                "conclusion": "Accelerates transition to clean energy independence and target reductions in carbon emissions."
            }
        ],
        "quizzes": [
            {
                "question": "Which exercise was recently conducted to enhance tri-service operational readiness in the Indian Ocean?",
                "options": ["Exercise Sagar Shakti", "Exercise Malabar", "Exercise Varuna", "Exercise Garuda"],
                "answer": 0
            },
            {
                "question": "What is the primary objective of the National Green Hydrogen Mission?",
                "options": ["Clean Energy Transition", "Digital Literacy", "Urban Infrastructure", "Space Exploration"],
                "answer": 0
            }
        ]
    }

def generate_affairs_and_quiz(news_text):
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not found. Returning fallback data.")
        return get_fallback_data()

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Failed to initialize Gemini Client: {e}")
        return get_fallback_data()

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    
    prompt = f"""
You are an expert exam strategist for Indian competitive exams (UPSC, SSC, Banking, State PCS).
Analyze these news items:

{news_text}

Task:
1. Extract 10-12 distinct current affairs entries across Defence, Schemes, International, National, Economy, Science & Tech.
2. For EACH entry, provide:
   - id (integer 1..N)
   - category (Defence, Schemes, International, National, Economy, Science & Tech)
   - title (Headline)
   - image_url ("https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800")
   - date ("2026-09-21")
   - place (Location)
   - persons_ministers (Ministers / VIPs involved)
   - officers (Key officers or N/A)
   - countries_states (Countries / States involved)
   - reason (Exam importance)
   - mission (Mission name or N/A)
   - conclusion (Summary)

3. Create 4 multiple-choice quiz questions based on these entries.

Return ONLY a single valid JSON object with keys "news" and "quizzes".
"""

    for model_name in models_to_try:
        for attempt in range(2):
            try:
                print(f"Calling model: {model_name} (Attempt {attempt+1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=8192,
                        response_mime_type="application/json"
                    ),
                )

                if response and response.text:
                    text = response.text.strip()
                    match = re.search(r'\{.*\}', text, re.DOTALL)
                    if match:
                        text = match.group(0)
                    data = json.loads(text)
                    if "news" in data and isinstance(data["news"], list) and len(data["news"]) > 0:
                        return data
            except Exception as e:
                print(f"Model {model_name} error: {e}")
                time.sleep(2)
                continue

    print("Gemini generation failed. Reverting to default fallback data.")
    return get_fallback_data()


# ============================================================
# 3. FILE SAVING
# ============================================================

if __name__ == "__main__":
    print("Fetching news headlines...")
    headlines = fetch_rss_headlines()
    
    print("Generating current affairs data...")
    app_data = generate_affairs_and_quiz(headlines)
    
    # Ensure news array is non-empty before writing
    if not app_data.get("news"):
        app_data = get_fallback_data()

    print(f"Saving {len(app_data['news'])} news items to data.json...")
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(app_data, f, indent=2)

    print("data.json generated successfully!")
    
