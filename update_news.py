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

# Strict blacklist to eliminate news site paywall/subscription boilerplate
JUNK_PATTERNS = [
    "subscribed with another email", "logout and login", "subscription benefits",
    "premium stories", "editorials, opinions", "unlock these with subscription",
    "the view from india", "first day first show", "today's cache", "science for all",
    "download the app", "terms of use", "privacy policy", "copyright", "all rights reserved"
]

def clean_paragraph(text):
    """Filters out website navigation, subscription prompts, and short filler text."""
    text_lower = text.lower()
    for pattern in JUNK_PATTERNS:
        if pattern in text_lower:
            return False
    return len(text.split()) > 8

def fetch_rss_feeds():
    """Fetches articles and extracts clean paragraph text without site ads/paywalls."""
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

                # Image extraction
                image_url = None
                if "media_content" in entry and len(entry.media_content) > 0:
                    image_url = entry.media_content[0].get("url")
                elif "enclosures" in entry and len(entry.enclosures) > 0:
                    image_url = entry.enclosures[0].get("href")

                # Web scrape full body strictly skipping junk boilerplate
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
            print(f"Error reading feed {url}: {e}")

    return raw_articles

def generate_fallback_content(raw_articles):
    """Generates clean structured study notes if Gemini API traffic is high."""
    news_items = []
    quizzes = []

    for idx, article in enumerate(raw_articles[:15], 1):
        full_text = article.get("full_body") or article.get("summary") or "Detailed coverage for this news item is being compiled."

        # Ensure no junk text leaks into fallback mode
        for pattern in JUNK_PATTERNS:
            if pattern in full_text.lower():
                full_text = f"The recent announcement regarding '{article.get('title')}' marks an important policy update. Government departments and statutory authorities are taking measures to ensure proper implementation across affected jurisdictions."

        if len(full_text) < 200:
            full_text += (
                " This major national development holds key implications for public policy, governance, and statutory administration. "
                "Students preparing for competitive examinations must focus on related constitutional provisions, regulatory authorities, and executive decisions. "
                "Understanding the broader socioeconomic impact and legal framework is vital for examination preparation."
            )

        news_items.append({
            "id": idx,
            "category": "NATIONAL",
            "headline": article.get("title", "National News Update"),
            "story_lead": article.get("title", ""),
            "bullet_points": [
                "Significant policy and governance initiative.",
                "Covers statutory framework and administrative requirements.",
                "Important current affairs topic for UPSC and State PCS exams."
            ],
            "full_article_text": full_text,
            "exam_relevance": "UPSC GS Paper II / State PCS",
            "takeaway": "Focus on institutional frameworks, statutory mandates, and administrative impact.",
            "source_url": article.get("link", "https://pib.gov.in"),
            "source_name": "Official Feed",
            "important_facts": [
                "Location Context: New Delhi, India",
                "Key Policy Scope: National Governance & Statutory Administration"
            ],
            "vocabulary_words": [
                {"word": "Statutory", "meaning": "Created, defined, or required by a formal legal legislative act."},
                {"word": "Jurisdiction", "meaning": "The scope of legal authority given to a governing court or body."}
            ],
            "image_url": article.get("image_url")
        })

        quizzes.append({
            "question": f"With reference to '{article.get('title', '')[:60]}...', consider the following statements:",
            "options": [
                "It involves central/state policy execution and regulatory compliance.",
                "It pertains exclusively to bilateral defense export treaties.",
                "It is monitored by the United Nations Security Council.",
                "None of the above"
            ],
            "answer": 0
        })

    return {"date": TODAY_DATE, "news": news_items, "quizzes": quizzes}

def generate_daily_content(raw_articles):
    prompt = f"""
    You are an expert Current Affairs Faculty and Subject Matter Expert.
    Based on the provided raw articles feed: {json.dumps(raw_articles[:15])}, generate a JSON response for TODAY ({TODAY_DATE}).

    STRICT CRITICAL RULES:
    1. NEVER include website boilerplate (like "subscribed with another email", "unlock these with subscription", "privacy policy").
    2. "full_article_text": Write a comprehensive, detailed, 350 to 500+ word newspaper-style article covering background, current facts, policy analysis, constitutional/statutory provisions, and future implications so students do NOT need to visit external sources.
    3. "important_facts": Provide 3 high-value exam facts (State details like Capital, Literacy Rate, GI Tags, National Parks, or Constitutional Articles).
    4. "vocabulary_words": Include 2 key vocabulary words used in the article with definitions.
    5. "image_url": Keep the provided image URL.

    Required JSON Output Format:
    {{
      "date": "{TODAY_DATE}",
      "news": [
        {{
          "id": 1,
          "category": "NATIONAL",
          "headline": "Comprehensive Article Headline",
          "story_lead": "Key summary lead sentence.",
          "bullet_points": ["Point 1", "Point 2", "Point 3"],
          "full_article_text": "Write a 350-500 word complete article text without subscription filler...",
          "exam_relevance": "UPSC GS Paper II / State PCS",
          "takeaway": "Core takeaway summary.",
          "source_url": "https://example.com",
          "source_name": "Official Source",
          "important_facts": [
            "Fact 1", "Fact 2", "Fact 3"
          ],
          "vocabulary_words": [
            {{"word": "ExampleWord", "meaning": "Definition here"}}
          ],
          "image_url": "URL from feed"
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
                print(f"Generating current affairs with {model_name} (Attempt {attempt})...")
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

    print("Gemini API busy. Using fallback content generator.")
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

    print(f"Successfully generated clean news without subscription boilerplate for {TODAY_DATE}")

if __name__ == "__main__":
    main()
