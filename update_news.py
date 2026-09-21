import os
from google import genai
from google.genai import types

# ============================================================
# GEMINI CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

client = genai.Client(api_key=GEMINI_API_KEY)

# Current stable Gemini Flash model
GEMINI_MODEL = "gemini-3.8-flash"


# ============================================================
# GEMINI GENERATION
# ============================================================

def generate_with_gemini(prompt):
    """
    Generate text using the current Google GenAI SDK.
    """

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=8192,
            ),
        )

        if not response or not response.text:
            raise RuntimeError("Gemini returned an empty response.")

        return response.text.strip()

    except Exception as e:
        raise RuntimeError(
            f"Gemini API request failed using {GEMINI_MODEL}: {e}"
        ) from e
