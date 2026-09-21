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

# Initialize Gemini Client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&auto=format&fit=crop",
]

# Strict blacklist to eliminate website menus, navigation, and subscription boilerplate
JUNK_PATTERNS = [
    "subscribed with another email", "logout and login", "subscription benefits",
    "premium stories", "editorials, opinions", "unlock these with subscription",
    "the view from india", "first day first show", "today's cache", "science for all",
    "data point decoding", "theedge at the cutting edge", "health matters ramya kannan",
    "the hindu on books", "published - september", "photo credit:", "download the app",
    "terms of use", "privacy policy", "copyright", "all rights reserved"
]

def is_clean_paragraph(text):
    """Filters out menu text, dates, photo credits, and promo text."""
    text_lower = text.lower()
    for pattern in JUNK_PATTERNS:
        if pattern in text_lower:
            return False
    return len(text.split()) > 8

def fetch_rss_feeds():
    """Fetches articles across diverse news sources."""
    rss_sources = [
        {"name": "PIB India", "url": "https://pib.gov.in/RssMain.aspx?ModId=6"},
        {"name": "Indian Express", "url": "https://indianexpress.com/section/india/feed/"},
        {"name": "BBC News", "url": "http://feeds.bbci.co.uk/news/world/asia/india/rss.xml"},
        {"name": "The Hindu", "url": "https://www.thehindu.com/news/national/feeder/default.rss"},
        {"name": "Dainik Jagran", "url": "https://www.jagran.com/rss/news/national.xml"},
        {"name": "Punjab Kesari", "url": "https://punjabkesari.in/rss/national.xml"}
    ]

    raw_articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for source in rss_sources:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries[:5]: # Extract top 5 from each source to reach 20+ total
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")

                clean_body_paragraphs = []
                if link:
                    try:
                        res = requests.get(link, headers=headers, timeout=5)
                        if res.status_code == 200:
                            soup = BeautifulSoup(res.text, "html.parser")
                            for p in soup.find_all("p"):
                                p_text = p.get_text().strip()
                                if is_clean_paragraph(p_text):
                                    clean_body_paragraphs.append(p_text)
                    except Exception:
                        pass

                full_body = " ".join(clean_body_paragraphs[:6]) if clean_body_paragraphs else summary
                
                # Sanitize extracted text
                for pattern in JUNK_PATTERNS:
                    full_body = re.sub(pattern, "", full_body, flags=re.IGNORECASE)

                image_url = FALLBACK_IMAGES[len(raw_articles) % len(FALLBACK_IMAGES)]

                raw_articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "full_body": full_body,
                    "source_name": source["name"],
                    "image_url": image_url
                })
        except Exception as e:
            print(f"Error fetching {source['name']}: {e}")

    random.shuffle(raw_articles)
    return raw_articles[:20] # Return up to 20 articles

def generate_daily_content(raw_articles):
    prompt = f"""
    You are an expert Current Affairs Faculty and Content Creator for competitive exams (UPSC / State PCS).
    Below is a feed of raw news updates: {json.dumps(raw_articles)}

    Generate a clean JSON response containing AT LEAST 15 to 20 unique news items for TODAY ({TODAY_DATE}).

    STRICT COMPLIANCE RULES:
    1. FORMATTING MANDATE: Inside "full_article_text", "headline", and "important_facts", EVERY key person name, organization name, statutory body, city, state, or country MUST be wrapped in HTML bold and underline tags: `<b><u>Name or Location</u></b>`. Example: `<b><u>Supreme Court of India</u></b>` or `<b><u>New Delhi</u></b>`.
    2. NO WEBPAGE BOILERPLATE: NEVER include menu links, dates, author names, or site navigation text.
    3. ORIGINAL SYNTHESIS: Rephrase and expand each story into 350+ words of complete, original exam notes to ensure copyright compliance.
    4. Provide 3 factual points in "important_facts" and 2 terms in "vocabulary_words".

    JSON Output Structure:
    {{
      "date": "{TODAY_DATE}",
      "news": [
        {{
          "id": 1,
          "category": "NATIONAL",
          "headline": "Headline with <b><u>Key Entity</u></b>",
          "story_lead": "Lead sentence...",
          "bullet_points": ["Point 1", "Point 2", "Point 3"],
          "full_article_text": "Write a 350+ word article where every important location (e.g., <b><u>New Delhi</u></b>) and key person or institution (e.g., <b><u>Prime Minister</u></b>) is wrapped in <b><u>...</u></b> tags.",
          "exam_relevance": "UPSC GS Paper II / State PCS",
          "takeaway": "Core takeaway for students.",
          "source_url": "Source link",
          "source_name": "Source Name",
          "important_facts": [
            "Location: <b><u>New Delhi</u></b>, India",
            "Authority: <b><u>Ministry of Finance</u></b>",
            "Scope: National Governance"
          ],
          "vocabulary_words": [
            {{"word": "Jurisdiction", "meaning": "Legal power or authority."}}
          ],
          "image_url": "Image URL"
        }}
      ],
      "quizzes": [
        {{
          "question": "Question?",
          "options": ["A", "B", "C", "D"],
          "answer": 0
        }}
      ]
    }}
    """

    candidate_models = ['gemini-2.5-flash', 'gemini-1.5-flash']

    for model_name in candidate_models:
        for attempt in range(1, 4):
            try:
                print(f"Generating content using {model_name} (Attempt {attempt})...")
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
                print(f"Warning: {model_name} attempt {attempt} failed: {e}")
                time.sleep(5)

    return {"date": TODAY_DATE, "news": [], "quizzes": []}

def main():
    raw_news = fetch_rss_feeds()
    data = generate_daily_content(raw_news)

    os.makedirs("data", exist_ok=True)
    with open(f"data/{TODAY_DATE}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"current_date": TODAY_DATE, "today": data}, f, indent=2, ensure_ascii=False)

    print("News script execution complete.")

if __name__ == "__main__":
    main()
