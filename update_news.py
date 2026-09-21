import os
import json
import time
import random
import re
from datetime import datetime
import feedparser
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# Set up Gemini Client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

# Dynamic topic-based fallback image pool so images are never identical
FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=600&auto=format&fit=crop", # News / Media
    "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=600&auto=format&fit=crop", # Economy / Finance
    "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=600&auto=format&fit=crop", # Governance / Politics
    "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600&auto=format&fit=crop", # Defense / International
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&auto=format&fit=crop", # Tech / Science
]

def fetch_rss_feeds():
    """Fetches articles, extracts image thumbnails, and scrapes main body text from source URLs."""
    rss_urls = [
        "https://www.thehindu.com/news/national/feeder/default.rss",
        "https://pib.gov.in/RssMain.aspx?ModId=6",
        "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"
    ]
    raw_articles = []
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")

                # 1. Try extracting actual image URL from feed enclosures or media tags
                image_url = None
                if "media_content" in entry and len(entry.media_content) > 0:
                    image_url = entry.media_content[0].get("url")
                elif "enclosures" in entry and len(entry.enclosures) > 0:
                    image_url = entry.enclosures[0].get("href")

                # 2. Extract detailed paragraph content directly from source link if possible
                full_body = summary
                if link:
                    try:
                        res = requests.get(link, headers=headers, timeout=5)
                        if res.status_code == 200:
                            soup = BeautifulSoup(res.text, "html.parser")
                            paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 50]
                            if paragraphs:
                                full_body = " ".join(paragraphs[:6]) # Get top paragraphs
                            
                            # Find meta image if thumbnail wasn't in RSS feed
                            if not image_url:
                                meta_img = soup.find("meta", property="og:image")
                                if meta_img:
                                    image_url = meta_img.get("content")
                    except Exception:
                        pass

                # Fallback to topic image pool if no specific photo was found
                if not image_url:
                    image_url = FALLBACK_IMAGES[len(raw_articles) % len(FALLBACK_IMAGES)]

                raw_articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "full_body": full_body,
                    "image_url": image_url
                })
        except Exception as e:
            print(f"Error reading feed {url}: {e}")

    return raw_articles

def generate_fallback_content(raw_articles):
    """Generates detailed articles directly from scraped RSS text if AI API is busy."""
    news_items = []
    quizzes = []

    for idx, article in enumerate(raw_articles[:15], 1):
        full_text = article.get("full_body") or article.get("summary") or "Detailed coverage for this development is being compiled."
        
        # Ensure a minimum article length even in fallback mode
        if len(full_text) < 200:
            full_text = full_text + " This initiative highlights key policy, legal, and governance implications for national development. Exam candidates should focus on institutional roles, constitutional provisions, and administrative implementation strategies."

        news_items.append({
            "id": idx,
            "category": "NATIONAL",
            "headline": article.get("title", "National News Update"),
            "story_lead": article.get("title", ""),
            "bullet_points": [
                "Key national development with policy and legal ramifications.",
                "Examine underlying statutory framework and administrative context.",
                "Important topic for civil services and state competitive examinations."
            ],
            "full_article_text": full_text,
            "exam_relevance": "UPSC GS Paper II (Governance & Polity) / State PCS",
            "takeaway": "Understand core regulatory frameworks, institutional duties, and policy objectives.",
            "source_url": article.get("link", "https://pib.gov.in"),
            "source_name": "Official Feed",
            "key_locations": "New Delhi, India",
            "important_dates": TODAY_DATE,
            "entities": [],
            "image_url": article.get("image_url")
        })

        quizzes.append({
            "question": f"With reference to '{article.get('title', '')[:60]}...', consider the key statements:",
            "options": [
                "It involves central/state policy execution.",
                "It is an international trade treaty.",
                "It relates strictly to defense exports.",
                "None of the above"
            ],
            "answer": 0
        })

    return {"date": TODAY_DATE, "news": news_items, "quizzes": quizzes}

def generate_daily_content(raw_articles):
    prompt = f"""
    You are an expert UPSC/PCS Current Affairs Faculty.
    Based on the provided raw articles feed: {json.dumps(raw_articles[:15])}, generate a JSON response for TODAY ({TODAY_DATE}).

    STRICT CRITICAL REQUIREMENTS FOR EACH ITEM:
    1. "full_article_text": Must be a long, thorough 300 to 500+ word detailed newspaper-style analysis covering context, history, legal/policy implications, key arguments, and significance.
    2. "image_url": Use the exact "image_url" provided for each article in the raw feed. Do NOT replace them with duplicate images.
    3. Generate 15 news items and 15 corresponding quiz questions.

    JSON Structure strictly required:
    {{
      "date": "{TODAY_DATE}",
      "news": [
        {{
          "id": 1,
          "category": "NATIONAL",
          "headline": "Full Detailed Headline Here",
          "story_lead": "Detailed summary sentence.",
          "bullet_points": ["Key Point 1", "Key Point 2", "Key Point 3"],
          "full_article_text": "Write a massive 300 to 500 word full article here with background, controversy/support, key legal quotes, and impact...",
          "exam_relevance": "UPSC GS Paper II (Polity & Governance) & State PCS",
          "takeaway": "Key takeaway for competitive exams.",
          "source_url": "https://example.com",
          "source_name": "Source Name",
          "key_locations": "Location, India",
          "important_dates": "{TODAY_DATE}",
          "entities": [],
          "image_url": "URL from feed"
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
                time.sleep(12 * attempt + random.uniform(1, 3))

    print("Gemini API high traffic spike. Generating detailed articles directly from scraped RSS text.")
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
