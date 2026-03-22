from google import genai
from PIL import Image
import json
import os
from dotenv import load_dotenv
import io
import re
import os

SESSION_DIR = "data/sessions"

load_dotenv()


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Store everything
session_history = []



def update_session_context(analysis: dict):
    entry = {
        "character": analysis.get("character", "").split(",")[0],
        "game_stage": analysis.get("progression", {}).get("game_stage"),
        "current_area": analysis.get("current_area"),
        "confidence": analysis.get("progression", {}).get("confidence"),
       "goal": analysis.get("player_intent", ["Unknown"])[0]
    }
    session_history.append(entry)

def build_context_hint() -> str:
    if not session_history:
        return ""
    
    recent = session_history[-3:]
    history_text = "\n".join([
        f"- {e['character']} | {e['game_stage']} | {e['current_area']} (confidence: {e['confidence']} |{e['goal']})"
        for e in recent
    ])
    
    return f"""
Previous analyses this session:
{history_text}
If current screenshot shows an earlier location, player is likely revisiting it.
"""

def clean_gemini_response(text: str) -> str:
    # Remove markdown code blocks regardless of format
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = text.replace('```', '')
    return text.strip()

def analyze_screenshot(img: Image.Image, game_name: str) -> dict:
    context_hint = build_context_hint()
    prompt =f"""
    <role>
    You are an expert on {game_name} with complete knowledge of its story, characters, locations, missions, and progression. Do NOT just describe what you visually see — use your knowledge to identify exactly what is happening.
    </role>

    <context>
    Game: {game_name}
    {context_hint}
    </context>

    <instructions>
    Analyze the following carefully:
    - Character identity: cross-reference appearance against ALL characters in {game_name} — do not default to the main protagonist
    - Specific named location using landmarks, environment, and minimap
    - Story progression: use character identity, location, minimap markers, gear quality, HUD upgrades, and world state to estimate story position
    - Current mission: identify by name if possible using visible objectives, minimap markers, and situational context
    - Minimap markers: waypoints, custom markers, path lines and what they suggest the player is navigating toward
    - Player intent: most likely reason this player is in this area based on location, waypoint direction, equipped items, and game knowledge
    - Environmental mismatch: is the player's outfit or equipment appropriate for this environment
    - Cross-reference your character and stage guess against ALL visible HUD elements — health/stamina core sizes, money amount, dead eye level. If HUD state contradicts your guess, revise it
    </instructions>

    <search_query_rules>
    Generate exactly ONE youtube_search query as a plain string using this priority:
    1. If active mission visible on screen → "{game_name} [exact mission name] guide"
    2. If known location + free roam → "{game_name} [location name] tips secrets"
    3. If boss fight detected → "{game_name} [boss name] strategy guide"
    4. If only game stage known → "{game_name} [game stage] walkthrough"

    Good example: "Red Dead Redemption 2 Grizzlies White Arabian location guide"
    Bad example: "Red Dead Redemption 2 guide"

    Never invent mission or location names you cannot explicitly read on screen.
    </search_query_rules>

    <output_format>
    {{
        "game_name": "{game_name}",
        "character": "playable character name and one-line identification reason",
        "current_area": "specific named location or region",
        "player_intent": [
        "most likely reason player is in this area (high/medium/low confidence)",
        "second likely reason",
        "third likely reason"
    ],
    "progression": {{
        "game_stage": "early/mid/late game or specific chapter/act",
        "current_mission": "active mission name if visible, otherwise null",
        "next_objective": "what the player should do next",
        "confidence": "high/medium/low"
    }},
    "situation": "one sentence describing what is currently happening",
    "likely_stuck_on": "one sentence describing the most likely struggle",
    "contextual_warning": "immediate threat or issue player may not have noticed — null if nothing noteworthy",
    "youtube_search": "single optimized search query string"
    }}
    </output_format>

    <important>
    Return raw JSON only. No markdown. No code blocks. No backticks. No extra text.
    </important>
"""
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=False)
    buffer.seek(0)
    img_clean = Image.open(buffer)
    
    # rest of your code
    response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[prompt, img_clean]
)
    
    try:
        cleaned = clean_gemini_response(response.text)
        result = json.loads(cleaned)
        update_session_context(result)  # save to session history
        return result
    except json.JSONDecodeError:
        print("Gemini returned invalid JSON, raw response:")
        print(response.text)
        return {
            "game_name": game_name,
            "current_area": "Unknown",
            "situation": "Analysis failed",
            "likely_stuck_on": "Unknown",
            "youtube_search": f"{game_name} guide"  # fix this too — was search_keywords
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

def save_session_entry(game_name: str, entry: dict):
    os.makedirs(SESSION_DIR, exist_ok=True)
    file_path = f"{SESSION_DIR}/{game_name}.txt"
    
    line = "|".join([
        entry.get("character", ""),
        entry.get("game_stage", ""),
        entry.get("current_area", ""),
        entry.get("confidence", ""),
        entry.get("goal", "")
    ])
    
    with open(file_path, "a") as f:
        f.write(line + "\n")

def load_session_history(game_name: str) -> list:
    file_path = f"{SESSION_DIR}/{game_name}.txt"
    
    if not os.path.exists(file_path):
        return []
    
    with open(file_path, "r") as f:
        lines = f.readlines()
    
    history = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) == 5:
            history.append({
                "character": parts[0],
                "game_stage": parts[1],
                "current_area": parts[2],
                "confidence": parts[3],
                "goal": parts[4]
            })
    
    return history[-3:]