import os
import json
import re
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
            with urllib.request.urlopen(req, timeout=10) as response:
                parsed = feedparser.parse(response.read())
                for entry in parsed.entries[:4]:
                    summary = getattr(entry, 'summary', '')
                    headlines.append(f"[{category}] {entry.title}: {summary}")
        except Exception as e:
            print(f"Warning: Feed issue for {category}: {e}")
    
    if not headlines:
        headlines.append("[Defence] Tri-service military exercise conducted in Indian Ocean region.")
        headlines.append("[National] Government releases national infrastructure updates.")

    return "\n".join(headlines[:15])


# ============================================================
# 2. GEMINI GENERATION
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

client = genai.Client(api_key=GEMINI_API_KEY)

# Fallback model list to prevent 404/deprecation errors
MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]

def generate_affairs_and_quiz(news_text):
    prompt = f"""
You are an expert exam strategist for Indian competitive exams (UPSC, SSC, Banking, State PCS).
Analyze these news items:

{news_text}

Task:
1. Extract exactly 12 distinct current affairs entries across Defence, Schemes, International, National, Economy, Science & Tech.
2. For EACH entry, provide complete concise information for these fields:
   - id (integer 1 to 12)
   - category (e.g. Defence, Schemes, International, National, Economy, Science & Tech)
   - title (Headline)
   - image_url (A stock photo URL from Unsplash e.g. "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800")
   - date (Important date / period)
   - place (Location / City / Region / State)
   - persons_ministers (Ministers / VIPs / Officials involved)
   - officers (Key administrative/military officers)
   - countries_states (Countries or Indian States involved)
   - reason (Reason for importance for exams)
   - mission (Mission / Scheme / Operation name or N/A)
   - conclusion (Summary / Impact / Key Takeaway)

3. Create 4 multiple-choice quiz questions based on these entries.

Return ONLY a valid JSON object matching this exact structure:
{{
  "news": [
    {{
      "id": 1,
      "category": "Defence",
      "title": "Title here",
      "image_url": "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800",
      "date": "2026-09-21",
      "place": "New Delhi, India",
      "persons_ministers": "Defense Minister",
      "officers": "Chief of Defence Staff",
      "countries_states": "India",
      "reason": "Crucial for national security questions",
      "mission": "Operation Raksha",
      "conclusion": "Enhanced preparedness"
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

    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            print(f"Trying Gemini model: {model_name}...")
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
                text_content = response.text.strip()
                match = re.search(r'\{.*\}', text_content, re.DOTALL)
                if match:
                    text_content = match.group(0)
                return json.loads(text_content)

        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            last_error = e
            continue

    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")


# ============================================================
# 3. FILE SAVING & INJECTION
# ============================================================

def update_output_files(data_dict):
    # Save standalone data.json so async fetch calls succeed
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data_dict, f, indent=2)
    print("Updated data.json successfully!")

    # Inject into index.html variable if present
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()

        json_str = json.dumps(data_dict, indent=2)
        updated_html = re.sub(
            r'(const|let|var)\s+appData\s*=\s*\{.*?\};',
            f'const appData = {json_str};',
            html_content,
            flags=re.DOTALL
        )

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(updated_html)
        print("Updated index.html successfully!")


if __name__ == "__main__":
    print("Fetching news feeds...")
    news_text = fetch_rss_headlines()
    
    print("Generating current affairs with Gemini...")
    app_data = generate_affairs_and_quiz(news_text)
    
    print("Saving updated files...")
    update_output_files(app_data)
    print("Completed successfully!")
