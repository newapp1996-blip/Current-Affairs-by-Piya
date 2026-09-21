import os
import json
import time
import random
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

def generate_fallback_content(raw_articles):
    """Fallback generator if Gemini API experiences global 503 outage."""
    news_items = []
    quizzes = []
    for idx, article in enumerate(raw_articles[:15], 1):
        news_items.append({
            "id": idx,
            "category": "NATIONAL",
            "headline": article.get("title", "National News Update"),
            "story_lead": article.get("summary", "")[:150] + "...",
            "bullet_points": ["Key development in national affairs.", "Examine policy and administrative context."],
            "full_article_text": article.get("summary", "Detailed coverage in progress."),
            "exam_relevance": "UPSC GS Paper II / State PCS",
            "takeaway": "Important update for general competitive examination prep.",
            "source_url": article.get("link", "https://pib.gov.in"),
            "source_name": "Official News Stream",
            "key_locations": "New Delhi, India",
            "important_dates": TODAY_DATE,
            "entities": [],
            "image_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=600&q=80"
        })
        quizzes.append({
            "question": f"Regarding the recent news '{article.get('title', '')[:50]}...', which statement is correct?",
            "options": ["It pertains to national development policy.", "It is an international treaty.", "It relates to environmental standard updates.", "None of the above"],
            "answer": 0
        })
    return {"date": TODAY_DATE, "news": news_items, "quizzes": quizzes}

def generate_daily_content(raw_articles):
    prompt = f"""
    You are an expert UPSC/PCS Current Affairs Faculty and Content Developer.
    Based on the provided raw news feed: {json.dumps(raw_articles[:15])}, generate a JSON response for TODAY ({TODAY_DATE}).

    Create exactly 15 detailed exam-focused news items and 15 matching quiz questions.

    JSON Structure strictly required:
    {{
      "date": "{TODAY_DATE}",
      "news": [
        {{
          "id": 1,
          "category": "NATIONAL",
          "headline": "Headline Here",
          "story_lead": "Summary lead sentence.",
          "bullet_points": ["Point 1", "Point 2"],
          "full_article_text": "Comprehensive explanation of context...",
          "exam_relevance": "UPSC GS Paper II & State PCS",
          "takeaway": "Key takeaway.",
          "source_url": "https://www.thehindu.com/news/example",
          "source_name": "The Hindu",
          "key_locations": "New Delhi, India",
          "important_dates": "{TODAY_DATE}",
          "entities": [],
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

    candidate_models = ['gemini-2.5-flash', 'gemini-1.5-flash']

    for model_name in candidate_models:
        for attempt in range(1, 4):
            try:
                print(f"Attempting content generation with {model_name} (Attempt {attempt})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.3
                    )
                )
                return json.loads(response.text)
            except Exception as e:
                print(f"Warning: Attempt {attempt} with {model_name} failed: {e}")
                time.sleep(15 * attempt + random.uniform(1, 4))

    print("Gemini API server overloaded across all models. Falling back to structured RSS feed generation.")
    return generate_fallback_content(raw_articles)

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
