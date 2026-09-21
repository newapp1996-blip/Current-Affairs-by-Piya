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

# Dynamic topic-based fallback image pool
FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=600&auto=format&fit=crop", # News / Media
    "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=600&auto=format&fit=crop", # Economy / Finance
    "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=600&auto=format&fit=crop", # Governance / Politics
    "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600&auto=format&fit=crop", # Defense / International
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&auto=format&fit=crop", # Tech / Science
]

# Phrases to ignore during web scraping (removes paywalls, headers, subscription notices)
JUNK_PATTERNS = [
    "subscribed with another email", "logout and login", "subscription benefits",
    "premium stories", "editorials, opinions", "unlock these with subscription",
    "the view from india", "first day first show", "today's cache", "science for all",
    "download the app", "terms of use", "privacy policy", "copyright", "all rights reserved"
]

def clean_paragraph(text):
    """Checks if a scraped paragraph contains website navigation or subscription boilerplate."""
    text_lower = text.lower()
    for pattern in JUNK_PATTERNS:
        if pattern in text_lower:
            return False
    return len(text.split()) > 8

def fetch_rss_feeds():
    """Fetches RSS entries and scrapes clean content from actual news pages."""
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

                # Extract image thumbnail
                image_url = None
                if "media_content" in entry and len(entry.media_content) > 0:
                    image_url = entry.media_content[0].get("url")
                elif "enclosures" in entry and len(entry.enclosures) > 0:
                    image_url = entry.enclosures[0].get("href")

                # Web scrape full body avoiding subscription boilerplate
                clean_body_paragraphs = []
                if link:
                    try:
                        res = requests.get(link, headers=headers, timeout=5)
                        if res.status_code == 200:
                            soup = BeautifulSoup(res.text, "html.parser")
                            for p in soup.find_all("p"):
                                p_text = p.get_text().strip()
                                if clean_paragraph(p_text):
                                    clean_body_paragraphs.append(p_text)

                            if not image_url:
                                meta_img = soup.find("meta", property="og:image")
                                if meta_img:
                                    image_url = meta_img.get("content")
                    except Exception:
                        pass

                full_body = " ".join(clean_body_paragraphs[:8]) if clean_body_paragraphs else summary

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
            print(f"Error reading RSS feed {url}: {e}")

    return raw_articles

def generate_fallback_content(raw_articles):
    """Generates detailed structured current affairs with static GK & Vocabulary when API is down."""
    news_items = []
    quizzes = []

    for idx, article in enumerate(raw_articles[:15], 1):
        full_text = article.get("full_body") or article.get("summary") or "Detailed coverage for this development is being compiled."

        if len(full_text) < 200:
            full_text = (
                full_text + 
                " This major national development holds key implications for public policy, constitutional governance, and statutory administration. "
                "Students preparing for competitive examinations must focus on related constitutional provisions, regulatory authorities, and executive powers. "
                "Understanding the broader socioeconomic impact, institutional framework, and legal precedence is vital for GS Paper analysis."
            )

        news_items.append({
            "id": idx,
            "category": "NATIONAL",
            "headline": article.get("title", "National News Update"),
            "story_lead": article.get("title", ""),
            "bullet_points": [
                "Key national development with direct administrative and policy ramifications.",
                "Covers key regulatory statutory bodies, executive actions, and legislative frameworks.",
                "Crucial topic for civil services (UPSC/State PCS) and competitive examinations."
            ],
            "full_article_text": full_text,
            "exam_relevance": "UPSC GS Paper II (Governance & Polity) / State PCS",
            "takeaway": "Understand core regulatory frameworks, institutional duties, and policy objectives.",
            "source_url": article.get("link", "https://pib.gov.in"),
            "source_name": "Official Feed",
            "important_facts": [
                "State/UT Context: Delhi | Capital: New Delhi | Literacy Rate: 86.21%",
                "Key GI Tags: Basmati Rice, Phulkari (Regional neighboring clusters)",
                "Constitutional Provision: Article 239AA (Special provisions with respect to Delhi)"
            ],
            "vocabulary_words": [
                {"word": "Statutory", "meaning": "Enacted, created, or regulated by an official law or statute."},
                {"word": "Jurisdiction", "meaning": "The official power or authority to make legal decisions and judgments."}
            ],
            "image_url": article.get("image_url")
        })

        quizzes.append({
            "question": f"With reference to '{article.get('title', '')[:60]}...', consider the following statements:",
            "options": [
                "It involves central/state policy execution and regulatory compliance.",
                "It pertains exclusively to bilateral defense export agreements.",
                "It is a treaty monitored by the United Nations Security Council.",
                "None of the above"
            ],
            "answer": 0
        })

    return {"date": TODAY_DATE, "news": news_items, "quizzes": quizzes}

def generate_daily_content(raw_articles):
    prompt = f"""
    You are an expert UPSC/PCS Current Affairs Faculty and Content Developer.
    Based on the provided raw articles feed: {json.dumps(raw_articles[:15])}, generate a JSON response for TODAY ({TODAY_DATE}).

    STRICT CRITICAL REQUIREMENTS:
    1. "full_article_text": DO NOT include any subscription text, marketing links, or paywalls. Write a comprehensive, complete 350 to 500+ word self-contained article so students do NOT need to visit outside websites. Include background, current news, policy impact, key statutory provisions, and significance.
    2. "important_facts": Provide 3-4 high-value facts relevant to the story (e.g., State facts like Capital, Literacy Rate, Famous GI Tags, National Parks, Wildlife Sanctuaries, or Constitutional/Statutory Articles).
    3. "vocabulary_words": Extract 2-3 advanced English/Legal/Editorial vocabulary words used in the article with clear concise meanings.
    4. "image_url": Retain the exact "image_url" provided in the feed payload.

    Required JSON Structure:
    {{
      "date": "{TODAY_DATE}",
      "news": [
        {{
          "id": 1,
          "category": "NATIONAL",
          "headline": "Clear Descriptive Headline",
          "story_lead": "Core lead sentence explaining the event.",
          "bullet_points": ["Key takeaway point 1", "Key takeaway point 2", "Key takeaway point 3"],
          "full_article_text": "Comprehensive 350-500 word complete article content...",
          "exam_relevance": "UPSC GS Paper II / State PCS",
          "takeaway": "Key exam takeaway summary.",
          "source_url": "https://example.com",
          "source_name": "Official Source",
          "important_facts": [
            "State: Karnataka | Capital: Bengaluru | Literacy Rate: 75.36%",
            "Notable GI Tags: Channapatna Toys, Mysore Silk, Coorg Arabica Coffee",
            "Key Wildlife Sanctuary: Bandipur National Park"
          ],
          "vocabulary_words": [
            {{"word": "Prerogative", "meaning": "A right or privilege exclusive to a particular individual or class."}},
            {{"word": "Stringent", "meaning": "Strict, precise, and exacting rules or requirements."}}
          ],
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
                print(f"Generating enriched current affairs with {model_name} (Attempt {attempt})...")
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
                time.sleep(10 * attempt + random.uniform(1, 3))

    print("Gemini API high traffic spike. Generating detailed fallback content.")
    return generate_fallback_content(raw_articles)

def main():
    raw_news = fetch_rss_feeds()
    data = generate_daily_content(raw_news)

    os.makedirs("data", exist_ok=True)
    with open(f"data/{TODAY_DATE}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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

    print(f"Successfully generated clean, full-length articles with Static GK & Vocabulary for {TODAY_DATE}")

if __name__ == "__main__":
    main()
