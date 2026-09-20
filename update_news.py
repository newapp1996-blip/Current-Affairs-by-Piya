import os
import json
import re
import urllib.request
import urllib.error
import feedparser

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
        print("ERROR: GEMINI_API_KEY environment variable is missing or empty!")
        raise ValueError("GEMINI_API_KEY secret is missing in GitHub Repository Settings -> Secrets and variables -> Actions!")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    prompt = f"""
You are an expert exam strategist for Indian competitive exams (UPSC, SSC, Banking, State PCS).
Analyze these news items:

{news_text}

Task:
1. Extract exactly 12 distinct current affairs entries across Defence, Schemes, International, National, Economy, Science & Tech.
2. For EACH current affair entry, provide complete concise information for these exact fields:
   - id (integer 1 to 12)
   - category (e.g. Defence, Schemes, International, National, Economy, Science & Tech)
   - title (Headline)
   - image_url (A stock photo URL from Unsplash e.g. "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800")
   - date (Important date / period e.g. September 2026)
   - place (Location / City / Region / State involved)
   - persons_ministers (Ministers / VIPs / Officials involved)
   - officers (Key administrative/military officers or designation)
   - countries_states (Countries or Indian States involved)
   - reason (Reason for importance for competitive exams)
   - mission (Mission / Scheme / Project / Operation name or N/A)
   - conclusion (Summary / Impact / Key Takeaway)

3. Create 4 multiple-choice quiz questions based on these entries.

Return ONLY a single valid JSON object following this exact structure:
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

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            text_content = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        print(f"HTTP Error from Gemini API: {e.code} - {e.read().decode('utf-8')}")
        raise e

    match = re.search(r'\{.*\}', text_content, re.DOTALL)
    if match:
        text_content = match.group(0)

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
