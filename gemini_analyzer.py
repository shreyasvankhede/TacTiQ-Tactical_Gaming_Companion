from google import genai
from PIL import Image
import json
import os
from dotenv import load_dotenv
import io
import re
import os
import time

SESSION_DIR = "data/sessions"

load_dotenv()


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY2"))




def update_session_context(game_name: str, analysis: dict):
    entry = {
        "character": analysis.get("character", "").split(",")[0],
        "game_stage": analysis.get("progression", {}).get("game_stage"),
        "current_area": analysis.get("current_area"),
        "goal": analysis.get("player_intent", ["Unknown"])[0],
        "build": analysis.get("player_attributes")
    }
    save_session_entry(game_name, entry)

def build_context_hint(game_name: str) -> str:
    state = load_session_history(game_name)
    
    if not state:
        return "[First Analysis of Session: No prior context available.]"
    
    goals_str = ", ".join(state["recent_goals"])
    
    return f"""
    [PERSISTENT SESSION MEMORY]
    - Confirmed Character: {state['character']}
    - Highest Game Stage Reached: {state['max_game_stage']}
    - Last Known Location: {state['last_area']}
    - Identified Player Build: {state['current_build']}
    - Recent Objectives: {goals_str}
    
    CRITICAL: If visual cues suggest an earlier game stage, the player is likely 
    revisiting {state['last_area']} for side content or collectibles.
    """

def clean_gemini_response(text: str) -> str:
    # Remove markdown code blocks regardless of format
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = text.replace('```', '')
    return text.strip()

def analyze_screenshot(img: Image.Image, game_name: str) -> dict:
    context_hint = build_context_hint(game_name)
    print(f"Context hint being sent:\n{context_hint}")
    prompt =f"""
    <role>
    You are an expert on {game_name} with complete knowledge of its story, characters, locations, missions, and progression.
    Do NOT just describe what you visually see — use your knowledge to identify exactly what is happening.
    </role>

    <context>
        Game: {game_name}
        {context_hint}

        CRITICAL INSTRUCTION: If previous analyses show a later game stage than what 
        you might visually guess, you MUST trust the session history over visual cues.
        Visual cues like outfits and locations can be misleading when a player revisits 
        earlier areas. The session history is ground truth — if it shows a later stage, 
        the player is at that stage or beyond, never earlier.

        If the player is in an area associated with an earlier game stage than their 
        current progression, use your complete knowledge of {game_name} to reason about 
        WHY they might be revisiting it. Consider what that specific area offers in terms 
        of collectibles, side content, challenges, secrets, or resources that would 
        motivate a player at their current progression to return there.
        Use minimap waypoints, equipped items, and your knowledge of {game_name} to 
        determine the most likely revisit reason and reflect this in player_intent.
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
    - Cross-reference your character and stage guess against ALL visible HUD elements —
      . If HUD state contradicts your guess, revise it
    </instructions>

    <search_query_rules>
    You MUST follow these rules strictly when generating youtube_search.
    This field is the MOST IMPORTANT field in the output.

    RULE 1: Never generate a generic query like "{game_name} guide" or "{game_name} tutorial". This is strictly forbidden.
    RULE 2: Always use the most specific information available from the screenshot.
    RULE 3: Follow this priority strictly:
    - Active mission name visible → "{game_name} [mission name] guide"
    - Combat/boss fight → "{game_name} [enemy/boss name] fight strategy"
    - Known location + free roam → "{game_name} [specific location] tips secrets"
    - Game stage only → "{game_name} [chapter/stage] walkthrough guide"

    Current screenshot context:
    - If you identified a location → use it
    - If you identified hostile NPCs → use them
    - If you identified a mission → use it

    CORRECT: "Red Dead Redemption 2 Rhodes combat mission guide"
    WRONG: "Red Dead Redemption 2 guide tutorial"

    Never invent names you cannot see on screen.
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
    "player_attributes": "player build type, playstyle, or class if applicable to {game_name} — null if not relevant for {game_name}",
    "contextual_warning": "immediate threat or issue player may not have noticed — null if nothing noteworthy",
    "youtube_search": "specific query using location/mission/enemy from screenshot — NEVER generic"
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
    model="gemini-3-flash-preview",
    contents=[prompt, img_clean]
)
    
    try:
        cleaned = clean_gemini_response(response.text)
        result = json.loads(cleaned)
        update_session_context(game_name,result)  # save to session history
        return result
    except json.JSONDecodeError:
        print("Gemini returned invalid JSON, raw response:")
        print(response.text)
        return {
            "game_name": game_name,
            "current_area": "Unknown",
            "situation": "Analysis failed",
            "likely_stuck_on": "Unknown",
            "youtube_search": f"{game_name} guide"  
        }
    except Exception as e:
            if "429" in str(e):
                wait = 30 *  1  # 30s, 60s, 90s
                print(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise e
def summarize_analysis(analysis: dict) -> str:
    area = analysis.get("current_area", "Unknown location")
    character = analysis.get("character", "Unknown").split(".")[0]
    situation = analysis.get("situation", "").split(".")[0]
    stuck_on = analysis.get("likely_stuck_on", "").split(".")[0]
    build=str(analysis.get("player_attributes", "")).split(".")[0]
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
player_build:{build}
Likely issue: {stuck_on}"""

    return summary

def save_session_entry(game_name: str, entry: dict):
    os.makedirs(SESSION_DIR, exist_ok=True)
    file_path = f"{SESSION_DIR}/{game_name}_state.json"
    
    state = {
        "character": "Unknown",
        "max_game_stage": "Early Game",
        "last_area": "Unknown",
        "current_build": "Unknown",
        "recent_goals": []
    }

    # Load existing state if it exists
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            state = json.load(f)

    # Update state with new info
    state["character"] = entry.get("character", state["character"])
    state["last_area"] = entry.get("current_area", state["last_area"])
    state["current_build"] = entry.get("build", state["current_build"])
    
    # Simple logic to keep the "highest" stage (optional refinement)
    state["max_game_stage"] = entry.get("game_stage", state["max_game_stage"])

    # Maintain a small list of the last 3 goals
    new_goal = entry.get("goal", "Unknown")
    if new_goal not in state["recent_goals"]:
        state["recent_goals"].insert(0, new_goal)
        state["recent_goals"] = state["recent_goals"][:3]

    with open(file_path, "w") as f:
        json.dump(state, f, indent=4)

def load_session_history(game_name: str) -> dict:
    file_path = f"{SESSION_DIR}/{game_name}_state.json"
    if not os.path.exists(file_path):
        return None
    
    with open(file_path, "r") as f:
        return json.load(f)

