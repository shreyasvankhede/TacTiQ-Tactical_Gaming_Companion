import google.generativeai as genai
from PIL import Image
import json
import os
from dotenv import load_dotenv
import io
import re
load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model=genai.GenerativeModel("gemini-2.5-flash")





def clean_gemini_response(text: str) -> str:
    # Remove markdown code blocks regardless of format
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = text.replace('```', '')
    return text.strip()

def analyze_screenshot(img: Image.Image, game_name: str) -> dict:
    prompt =f"""
You are an expert on {game_name} with complete knowledge of its story,
characters, locations, missions, and progression.

Do NOT just describe what you visually see. Instead, use your knowledge
of {game_name} to identify exactly what is happening in this screenshot.

Analyze the following carefully:
- Character identity: cross-reference appearance against ALL characters 
  in {game_name} — do not default to the main protagonist
- Specific named location using landmarks, environment, and minimap
- Story progression: use character identity, location, available mission 
  markers on minimap, gear/outfit quality, HUD upgrades, and world state 
  to estimate where in the story the player is
- Current mission: identify by name if possible using visible objectives,
  minimap markers, and situational context
- What was likely the previous mission based on current location and context
- What mission or objective is likely coming next based on available markers

Respond ONLY in raw JSON, no markdown, no code blocks, no backticks:
{{
    "game_name": "{game_name}",
    "character": "exact character name and one-line reason",
    "current_area": "specific named location",
    "progression": {{
        "game_stage": "early/mid/late game or specific chapter",
        "current_mission": "mission name if identifiable, otherwise best guess",
        "previous_mission": "likely previous mission based on context",
        "next_objective": "what the player should do next",
        "confidence": "high/medium/low"
    }},
    "situation": "one sentence of what is happening",
    "likely_stuck_on": "one sentence of likely struggle",
    "search_keywords": ["keyword 1", "keyword 2", "keyword 3"]
}}

IMPORTANT: Return raw JSON only. No markdown. No code blocks. No backticks.
"""
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=False)
    buffer.seek(0)
    img_clean = Image.open(buffer)
    
    # rest of your code
    response = model.generate_content([prompt, img_clean])
    
    try:
        cleaned = clean_gemini_response(response.text)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print("Gemini returned invalid JSON, raw response:")
        print(response.text)
        return {
            "game_name": game_name,
            "current_area": "Unknown",
            "situation": "Analysis failed",
            "likely_stuck_on": "Unknown",
            "search_keywords": [f"{game_name} guide"]
        }
def summarize_analysis(analysis: dict) -> str:
    area = analysis.get("current_area", "Unknown location")
    character = analysis.get("character", "Unknown").split(".")[0]
    situation = analysis.get("situation", "").split(".")[0]
    stuck_on = analysis.get("likely_stuck_on", "").split(".")[0]
    
    progression = analysis.get("progression", {})
    stage = progression.get("game_stage", "Unknown")
    current_mission = progression.get("current_mission", "Unknown")
    next_obj = progression.get("next_objective", "Unknown")
    confidence = progression.get("confidence", "low")

    summary = f"""Location: {area}
Character: {character}
Stage: {stage}
Mission: {current_mission} (confidence: {confidence})
Next: {next_obj}
Situation: {situation}
Likely issue: {stuck_on}"""

    return summary