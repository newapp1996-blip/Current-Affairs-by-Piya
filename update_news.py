import time

# Valid Gemini models in order of preference
MODELS_TO_TRY = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]

def generate_affairs_and_quiz(news_text):
    prompt = f"""
You are an expert exam strategist for Indian competitive exams (UPSC, SSC, Banking, State PCS).
Analyze these news items:

{news_text}

Task:
1. Extract exactly 12 distinct current affairs entries across Defence, Schemes, International, National, Economy, Science & Tech.
2. For EACH entry, provide complete concise information for these fields:
   - id (integer 1 to 12)
   - category (e.g. Defence, Schemes, International, National, Economy, Science & Tech)
   - title (Headline)
   - image_url (A stock photo URL from Unsplash e.g. "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800")
   - date (Important date / period)
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

    for model_name in MODELS_TO_TRY:
        for attempt in range(3):  # Retry up to 3 times per model for 503 errors
            try:
                print(f"Trying Gemini model: {model_name} (Attempt {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=8192,
                        response_mime_type="application/json"
                    ),
                )

                if response and response.text:
                    text_content = response.text.strip()
                    match = re.search(r'\{.*\}', text_content, re.DOTALL)
                    if match:
                        text_content = match.group(0)
                    data = json.loads(text_content)
                    if "news" in data and len(data["news"]) > 0:
                        return data

            except Exception as e:
                err_msg = str(e)
                print(f"Model {model_name} attempt {attempt + 1} failed: {err_msg}")
                if "503" in err_msg or "UNAVAILABLE" in err_msg:
                    time.sleep(3 * (attempt + 1))  # Wait 3s, 6s before retrying 503 errors
                    continue
                else:
                    break  # Skip model on 404 / non-transient errors

    print("Warning: All API calls failed. Generating fallback dataset.")
    return get_fallback_data()


def get_fallback_data():
    return {
        "news": [
            {
                "id": 1,
                "category": "Defence",
                "title": "Tri-Service Military Exercise Conducted in Indian Ocean Region",
                "image_url": "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=800",
                "date": "2026-09-21",
                "place": "Indian Ocean Region",
                "persons_ministers": "Defense Minister",
                "officers": "Chief of Defence Staff",
                "countries_states": "India",
                "reason": "Important for maritime security and defence exercises topics",
                "mission": "Exercise Sagar Shakti",
                "conclusion": "Strengthened joint maritime readiness and inter-service operational capabilities"
            }
        ],
        "quizzes": [
            {
                "question": "Which exercise was recently conducted in the Indian Ocean Region?",
                "options": ["Exercise Sagar Shakti", "Exercise Malabar", "Exercise Varuna", "Exercise Garuda"],
                "answer": 0
            }
        ]
    }
    
