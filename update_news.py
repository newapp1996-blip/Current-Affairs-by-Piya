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

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

TODAY_DATE = datetime.now().strftime("%Y-%m-%d")

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&auto=format&fit=crop",
]

# Blacklist menu text, navigation headers, photo credits, and subscription prompts
JUNK_PATTERNS = [
    r"subscribed with another email", r"logout and login", r"subscription benefits",
    r"premium stories", r"editorials, opinions", r"unlock these with subscription",
    r"the view from india", r"first day first show", r"today's cache", r"science for all",
    r"data point decoding", r"theedge at the cutting edge", r"health matters ramya kannan",
    r"the hindu on books", r"published - \w+ \d+, \d{4}", r"photo credit:.*$",
    r"download the app", r"terms of use", r"privacy policy", r"copyright", r"all rights reserved"
]

def clean_extracted_text(text):
    """Filters out junk patterns and removes raw webpage artifacts."""
    for pattern in JUNK_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()

def fetch_rss_feeds():
    """Fetches articles across multiple sources."""
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
            for entry in feed.entries[:5]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = clean_extracted_text(entry.get("summary", ""))

                clean_paragraphs = []
                if link:
                    try:
                        res = requests.get(link, headers=headers, timeout=5)
                        if res.status_code == 200:
                            soup = BeautifulSoup(res.text, "html.parser")
                            for p in soup.find_all("p"):
                                p_text = clean_extracted_text(p.get_text())
                                if len(p_text.split()) > 10:
                                    clean_paragraphs.append(p_text)
                    except Exception:
                        pass

                full_body = " ".join(clean_paragraphs[:5]) if clean_paragraphs else summary

                raw_articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "full_body": full_body,
                    "source_name": source["name"],
                    "image_url": FALLBACK_IMAGES[len(raw_articles) % len(FALLBACK_IMAGES)]
                })
        except Exception as e:
            print(f"Error reading source {source['name']}: {e}")

    random.shuffle(raw_articles)
    return raw_articles[:20]

def generate_daily_content(raw_articles):
    prompt = f"""
    You are an expert Current Affairs Faculty for UPSC and State PCS competitive exams.
    Synthesize these raw news feeds into study material: {json.dumps(raw_articles)}

    CRITICAL RULES:
    1. EXTRACT FACTS (NO N/A): Do NOT output "N/A" for any field. Always extract or infer meaningful locations, agencies, or key dates from the news event.
    2. HTML HIGHLIGHTING: In "full_article_text", "headline", and "important_locations", every important location, person name, statutory body, or government ministry MUST be enclosed in `<b><u>...</u></b>` tags. Example: `<b><u>New Delhi</u></b>` or `<b><u>Supreme Court of India</u></b>`.
    3. ORIGINAL REWRITING: Synthesize news into original 350+ word comprehensive study notes to prevent copyright issues.
    4. NO WEBPAGE JUNK: Exclude author credits, dates, or site menu snippets.

    JSON Output Structure:
    {{
      "date": "{TODAY_DATE}",
      "news": [
        {{
          "id": 1,
          "category": "NATIONAL",
          "headline": "Headline with <b><u>Entity Name</u></b>",
          "story_lead": "Key summary sentence...",
          "bullet_points": ["Point 1", "Point 2", "Point 3"],
          "full_article_text": "Write a 350+ word study article. Enclose all major locations (e.g., <b><u>Bengaluru</u></b>) and key figures/agencies in <b><u>...</u></b> tags.",
          "exam_relevance": "UPSC GS Paper II / State PCS",
          "takeaway": "Core takeaway for exam preparation.",
          "important_locations": "<b><u>New Delhi</u></b>, India",
          "important_dates": "September 2026",
          "source_url": "Source Link",
          "source_name": "Source Name",
          "important_facts": [
            "Fact 1 featuring <b><u>Ministry of Home Affairs</u></b>",
            "Fact 2"
          ],
          "vocabulary_words": [
            {{"word": "Statutory", "meaning": "Authorized or defined by legislation."}}
          ],
          "image_url": "Image URL"
        }}
      ],
      "quizzes": [
        {{
          "question": "Question?",
          "options": ["Option A", "Option B", "Option C", "Option D"],
          "answer": 0
        }}
      ]
    }}
    """

    for model_name in ['gemini-2.5-flash', 'gemini-1.5-flash']:
        for attempt in range(1, 4):
            try:
                print(f"Generating content via {model_name} (Attempt {attempt})...")
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
                print(f"Attempt {attempt} failed: {e}")
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

    print(f"Update completed successfully for {TODAY_DATE}.")

if __name__ == "__main__":
    main()
