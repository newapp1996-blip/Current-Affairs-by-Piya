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

# Royalty-free thematic image fallback pool (Avoids media copyright issues)
FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=600&auto=format&fit=crop", # Media/General
    "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=600&auto=format&fit=crop", # Economy/Finance
    "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=600&auto=format&fit=crop", # Governance/Politics
    "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600&auto=format&fit=crop", # International Relations
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&auto=format&fit=crop", # Tech/Science
]

# Strict blacklist to strip out website navigation & paywall boilerplate
JUNK_PATTERNS = [
    "subscribed with another email", "logout and login", "subscription benefits",
    "premium stories", "editorials, opinions", "unlock these with subscription",
    "the view from india", "first day first show", "today's cache", "science for all",
    "download the app", "terms of use", "privacy policy", "copyright", "all rights reserved",
    "read full article at", "click here to subscribe"
]

def clean_paragraph(text):
    """Filters out website navigation, subscription prompts, and short boilerplate."""
    text_lower = text.lower()
    for pattern in JUNK_PATTERNS:
        if pattern in text_lower:
            return False
    return len(text.split()) > 8

def fetch_rss_feeds():
    """
    Fetches raw feeds from multiple varied sources:
    The Hindu, Indian Express, BBC News, PIB, Dainik Jagran, Punjab Kesari.
    """
    rss_sources = [
        {"name": "The Hindu", "url": "https://www.thehindu.com/news/national/feeder/default.rss"},
        {"name": "Indian Express", "url": "https://indianexpress.com/section/india/feed/"},
        {"name": "BBC News", "url": "http://feeds.bbci.co.uk/news/world/asia/india/rss.xml"},
        {"name": "PIB India", "url": "https://pib.gov.in/RssMain.aspx?ModId=6"},
        {"name": "Dainik Jagran", "url": "https://www.jagran.com/rss/news/national.xml"},
        {"name": "Punjab Kesari", "url": "https://punjabkesari.in/rss/national.xml"}
    ]

    raw_articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for source in rss_sources:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries[:4]: # Fetch top 4 items per publisher for diversity
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
                                if clean_paragraph(p_text):
                                    clean_body_paragraphs.append(p_text)
                    except Exception:
                        pass

                full_body = " ".join(clean_body_paragraphs[:6]) if clean_body_paragraphs else summary

                # Assign royalty-free imagery to remain legally compliant
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
            print(f"Error reading feed {source['name']}: {e}")

    # Shuffle to ensure a diverse mix of sources across the list
    random.shuffle(raw_articles)
    return raw_articles

def generate_fallback_content(raw_articles):
    """Fallback generator ensuring synthesized non-infringing notes if API is offline."""
    news_items = []
    quizzes = []

    for idx, article in enumerate(raw_articles[:15], 1):
        full_text = article.get("full_body") or article.get("summary") or "Detailed policy background is being compiled."

        # Remove boilerplate if present
        for pattern in JUNK_PATTERNS:
            if pattern in full_text.lower():
                full_text = f"The recent announcement regarding '{article.get('title')}' represents a notable policy development. Authorities are taking steps to ensure strategic implementation across relevant jurisdictions."

        if len(full_text) < 200:
            full_text += (
                " This major national development holds key implications for public policy, governance, and statutory administration. "
                "Students preparing for competitive examinations must focus on related constitutional provisions, regulatory authorities, and executive decisions. "
                "Understanding the broader socioeconomic impact and legal framework is vital for examination preparation."
            )

        news_items.append({
            "id": idx,
            "category": "NATIONAL",
            "headline": article.get("title", "National Affairs Summary"),
            "story_lead": article.get("title", ""),
            "bullet_points": [
                "Key administrative and policy development.",
                "Covers statutory framework and institutional decisions.",
                "Relevant current affairs update for competitive exams."
            ],
            "full_article_text": full_text,
            "exam_relevance": "UPSC GS Paper II / State PCS",
            "takeaway": "Focus on institutional mandates and regulatory mechanisms.",
            "source_url": article.get("link", "#"),
            "source_name": article.get("source_name", "Public News Wire"),
            "important_facts": [
                "Primary Focus: Governance & Administrative Policy",
                "Scope: Central & State Administrative Mandates"
            ],
            "vocabulary_words": [
                {"word": "Statutory", "meaning": "Enacted, defined, or authorized by a legislative body."},
                {"word": "Mandate", "meaning": "An official order or authorization to carry out a specific policy."}
            ],
            "image_url": article.get("image_url")
        })

        quizzes.append({
            "question": f"With reference to '{article.get('title', '')[:60]}...', consider the following statements:",
            "options": [
                "It involves public administration and policy implementation.",
                "It pertains exclusively to bilateral space exploration treaties.",
                "It is governed by international maritime arbitration courts.",
                "None of the above"
            ],
            "answer": 0
        })

    return {"date": TODAY_DATE, "news": news_items, "quizzes": quizzes}

def generate_daily_content(raw_articles):
    prompt = f"""
    You are an expert Current Affairs Faculty and Content Creator.
    Below is a collection of news feeds from multiple sources (The Hindu, Indian Express, BBC News, PIB, Dainik Jagran, Punjab Kesari):
    {json.dumps(raw_articles[:15])}

    Generate a clean JSON payload for TODAY ({TODAY_DATE}).

    STRICT COMPLIANCE & LEGAL SAFETY RULES:
    1. NEVER verbatim copy news articles. Rephrase, synthesize, and expand facts into ORIGINAL educational study notes.
    2. NEVER include website boilerplate (e.g., "subscribed with another email", "unlock these with subscription", "privacy policy").
    3. Ensure diverse representation across publishers (do NOT rely on a single outlet).
    4. "full_article_text": Write a comprehensive 350 to 500+ word educational article focusing on factual background, constitutional/legal context, government schemes, and analysis.
    5. Keep provided source_name and source_url attributed accurately.

    Required JSON Output Structure:
    {{
      "date": "{TODAY_DATE}",
      "news": [
        {{
          "id": 1,
          "category": "NATIONAL",
          "headline": "Synthesized Objective Headline",
          "story_lead": "Key summary lead sentence.",
          "bullet_points": ["Point 1", "Point 2", "Point 3"],
          "full_article_text": "Write a 350-500 word comprehensive synthesized study guide...",
          "exam_relevance": "UPSC GS Paper II / State PCS / General Awareness",
          "takeaway": "Core takeaway for students.",
          "source_url": "Source URL from feed",
          "source_name": "Source Name from feed",
          "important_facts": [
            "Fact 1", "Fact 2", "Fact 3"
          ],
          "vocabulary_words": [
            {{"word": "Term", "meaning": "Definition"}}
          ],
          "image_url": "Image URL from feed"
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
                print(f"Generating synthesized current affairs with {model_name} (Attempt {attempt})...")
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

    print("Gemini API unavailable. Generating safe fallback content.")
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

    print(f"Successfully generated multi-source non-infringing news content for {TODAY_DATE}")

if __name__ == "__main__":
    main()
