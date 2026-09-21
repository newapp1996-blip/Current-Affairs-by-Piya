import os
import json
import re
import time
import urllib.request
from datetime import datetime
import feedparser
from google import genai
from google.genai import types

# Current execution date
TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

# Live RSS feeds
FEEDS = {
    "National": "https://www.thehindu.com/news/national/feeder/default.rss",
    "International": "https://www.thehindu.com/news/international/feeder/default.rss",
    "Business": "https://www.thehindubusinessline.com/feeder/default.rss",
    "PIB Release": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
    "Sci-Tech": "https://www.thehindu.com/sci-tech/feeder/default.rss"
}

def fetch_rss_headlines():
    headlines = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for category, url in FEEDS.items():
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                parsed = feedparser.parse(response.read())
                for entry in parsed.entries[:8]:
                    summary = getattr(entry, 'summary', '')
                    clean_summary = re.sub(r'<[^>]+>', '', summary)[:250]
                    headlines.append(f"[{category}] {entry.title}: {clean_summary}")
        except Exception as e:
            print(f"Warning: Feed error for {category}: {e}")
    
    return "\n\n".join(headlines)

def generate_affairs_and_quiz(news_text):
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set in GitHub Secrets.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    available_models = []
    try:
        for m in client.models.list():
            if hasattr(m, 'supported_generation_methods') and 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name.replace("models/", ""))
    except Exception as e:
        print(f"Could not list models: {e}")

    if not available_models:
        available_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

    prompt = f"""
You are an expert competitive exam strategist for UPSC, SSC CGL, Banking, and State PCS.
Today's date is strictly {TODAY_DATE}.

Analyze these live news headlines and generate EXACTLY 15 distinct, comprehensive current affairs entries.
Each entry MUST contain all key facts so students do NOT need to read full news articles elsewhere.
In the detailed narrative text, wrap critical names, numbers, scores, locations, and achievements in <b>bold tags</b> (like newspaper infographics).

LIVE HEADLINES:
{news_text}

For EACH of the 15 entries, generate:
1. id: integer 1 to 15
2. category: (e.g. SHOOTING, CRICKET, HOCKEY, DEFENCE, NATIONAL, ECONOMY, SCI-TECH)
3. headline: Concise catchy main title (e.g., "WOMEN LEAD EARLY CHARGE FOR INDIA AT ASIAD")
4. story_lead: Paragraph with <b>bolded highlights</b> detailing the story, names, background, and records set.
5. bullet_points: Array of 2 to 3 detailed key fact bullet points with <b>bold highlights</b>.
6. image_url: A high quality HD sports/news image URL (use Unsplash current event placeholders).
7. exam_relevance: Specific UPSC/SSC topic relevance statement.
8. takeaway: Short summary takeaway.

ALSO, create EXACTLY 15 multiple-choice quiz questions (1 question directly corresponding to each news item, from id 1 to 15).

Return ONLY a single valid JSON object formatted as:
{{
  "date": "{TODAY_DATE}",
  "news": [
    {{
      "id": 1,
      "category": "SHOOTING",
      "headline": "Elavenil Valarivan Wins Silver at Asian Games",
      "story_lead": "<b>Elavenil Valarivan</b> signalled a brilliant campaign for India, winning a <b>silver double in the 10m air rifle individual and team events</b>.",
      "bullet_points": [
        "Mentored by 2010 Asiad silver winner <b>Gagan Narang</b>.",
        "Team silver achieved alongside <b>Sonam U Maskar</b> and <b>Vidarsa Vinod</b> with 1898 points."
      ],
      "image_url": "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800",
      "exam_relevance": "Important for Sports Current Affairs & Asian Games records in UPSC/SSC.",
      "takeaway": "India secures silver double in 10m Air Rifle."
    }}
  ],
  "quizzes": [
    {{
      "id": 1,
      "question": "Who mentored Elavenil Valarivan to win silver in 10m Air Rifle?",
      "options": ["Gagan Narang", "Abhinav Bindra", "Rajyavardhan Rathore", "Jaspal Rana"],
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
                if "news" in data and len(data["news"]) == 15 and len(data["quizzes"]) == 15:
                    data["date"] = TODAY_DATE
                    return data
        except Exception as e:
            print(f"Model {model_name} error: {e}")
            time.sleep(1)

    raise RuntimeError("Failed to generate complete news and quiz dataset.")

if __name__ == "__main__":
    print(f"Fetching live news feeds for date: {TODAY_DATE}...")
    news_text = fetch_rss_headlines()

    print("Generating news data...")
    app_data = generate_affairs_and_quiz(news_text)

    # Save to history folder
    os.makedirs("data", exist_ok=True)
    history_file = f"data/{TODAY_DATE}.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(app_data, f, indent=2)

    # Maintain available dates index starting from 2026-09-20
    dates_index_file = "data/dates.json"
    available_dates = ["2026-09-20"]
    if os.path.exists(dates_index_file):
        with open(dates_index_file, "r") as f:
            available_dates = json.load(f)
    if TODAY_DATE not in available_dates:
        available_dates.append(TODAY_DATE)
    available_dates = sorted(list(set(available_dates)), reverse=True)

    with open(dates_index_file, "w", encoding="utf-8") as f:
        json.dump(available_dates, f, indent=2)

    # Save latest current payload
    app_payload = {
        "current_date": TODAY_DATE,
        "available_dates": available_dates,
        "today": app_data
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(app_payload, f, indent=2)

    print(f"Successfully saved {len(app_data['news'])} news and {len(app_data['quizzes'])} quiz items for {TODAY_DATE}!")
