import os
import json
import re
from datetime import datetime
import feedparser
from google import genai
from google.genai import types

# Set up Gemini Client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

def fetch_rss_feeds():
    # Fetch news headlines from reliable sources
    rss_urls = [
        "https://www.thehindu.com/news/national/feeder/default.rss",
        "https://pib.gov.in/RssMain.aspx?ModId=6",
        "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"
    ]
    raw_articles = []
    for url in rss_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            raw_articles.append({
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", "")
            })
    return raw_articles

def generate_daily_content(raw_articles):
    prompt = f"""
    You are an expert UPSC/PCS Current Affairs Faculty and Content Developer.
    Based on the provided raw news feed: {json.dumps(raw_articles[:15])}, generate a JSON response for TODAY ({TODAY_DATE}).

    Create exactly 15 detailed exam-focused news items and 15 matching quiz questions.

    For each news item, ensure:
    1. "full_article_text": A detailed explanation (minimum 100 to 500+ words) covering full context, background, locations (plant site, city, state, country), military drills, international affairs, and key historical dates.
    2. "entities": List key personalities mentioned (Ministers, Presidents, Dignitaries). Include:
       - "name": Full name
       - "role": Current designation/ministry
       - "party_and_state": E.g., "BJP (Lucknow, Uttar Pradesh)" or "Independent (USA)"
       - "bio_details": Comprehensive profile including age, educational background, career, political party, key portfolios, and major initiatives/views.
    3. "source_url": Authentic direct web link (e.g., The Hindu, PIB, Hindustan Times).
    4. "key_locations": Specific places, plants, cities, or countries of importance.
    5. "important_dates": Important dates/deadlines mentioned.

    JSON Structure strictly required:
    {{
      "date": "{TODAY_DATE}",
      "news": [
        {{
          "id": 1,
          "category": "NATIONAL",
          "headline": "Headline Here",
          "story_lead": "Summary lead sentence.",
          "bullet_points": ["Point 1", "Point 2", "Point 3"],
          "full_article_text": "Comprehensive 100 to 500+ word detailed article content explaining all key aspects of the topic...",
          "exam_relevance": "UPSC GS Paper II (Governance) & State PCS",
          "takeaway": "Key takeaway for competitive exams.",
          "source_url": "https://www.thehindu.com/news/example",
          "source_name": "The Hindu",
          "key_locations": "Noida, Uttar Pradesh, India",
          "important_dates": "October 1, 2026",
          "entities": [
            {{
              "name": "Rajnath Singh",
              "role": "Minister of Defence",
              "party_and_state": "BJP (Lucknow, Uttar Pradesh)",
              "bio_details": "Born July 10, 1951. Educated at Gorakhpur University (M.Sc Physics). Union Minister of Defence, former Chief Minister of Uttar Pradesh, and former National President of BJP. Known for modernizing defense infrastructure and promoting Atmanirbhar Bharat in defense manufacturing."
            }}
          ],
          "image_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=600&q=80"
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
        model='gemini-2.0-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3
        )
    )

    return json.loads(response.text)

def main():
    raw_news = fetch_rss_feeds()
    data = generate_daily_content(raw_news)

    # Save today's date JSON
    os.makedirs("data", exist_ok=True)
    with open(f"data/{TODAY_DATE}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Update main index data.json
    data_json_path = "data.json"
    available_dates = [TODAY_DATE]
    if os.path.exists(data_json_path):
        try:
            with open(data_json_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                available_dates = list(set(existing.get("available_dates", []) + [TODAY_DATE]))
                available_dates.sort(reverse=True)
        except Exception:
            pass

    payload = {
        "current_date": TODAY_DATE,
        "available_dates": available_dates,
        "today": data
    }

    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Successfully updated current affairs data for {TODAY_DATE}")

if __name__ == "__main__":
    main()
