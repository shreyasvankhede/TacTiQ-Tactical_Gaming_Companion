from google import genai
from PIL import Image
import json
import os
from dotenv import load_dotenv
import io
import re
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
    backticks = '`' * 3
    text = re.sub(f'{backticks}(?:json)?\\s*', '', text)
    text = text.replace(backticks, '')
    return text.strip()

def analyze_screenshot(img: Image.Image, game_name: str) -> dict:
    context_hint = build_context_hint(game_name)
    
    # Let's grab the last few chat messages to pass to the AI so the greeting feels continuous
    history = load_chat_history(game_name)
    recent_history = ""
    for msg in history[-4:]: 
        role = "Player" if msg["role"] == "user" else "TacTiQ"
        recent_history += f"{role}: {msg['text']}\n"

    print(f"Context hint being sent:\n{context_hint}")
    
    prompt = f"""
    <role>
    You are TacTiQ, an elite AI gaming companion expert in {game_name}.
    Do NOT just describe what you visually see — use your knowledge to identify exactly what is happening.
    </role>

    <context>
        Game: {game_name}
        {context_hint}
        
        [RECENT CHAT HISTORY]
        {recent_history}
    </context>
    
    <instructions>
    Analyze the following carefully:
    - Character identity, location, progression, mission, minimap, and player intent.
    - IMPORTANT: You must generate a "chat_greeting". This should be a natural, conversational 1-2 sentence greeting speaking directly to the player (e.g., "Looks like you're facing..."). Use the RECENT CHAT HISTORY to ensure you don't repeat yourself if the player is in the same area.
    </instructions>

    <search_query_rules>
    RULE 1: Never generate a generic query like "{game_name} guide".
    RULE 2: Use the most specific info visible (boss name > active mission > location).
    </search_query_rules>

    <output_format>
    {{
        "game_name": "{game_name}",
        "character": "playable character name and one-line identification reason",
        "current_area": "specific named location or region",
        "player_intent": ["reason 1", "reason 2"],
        "progression": {{
            "game_stage": "early/mid/late game",
            "current_mission": "active mission name",
            "next_objective": "what to do next",
            "confidence": "high/medium/low"
        }},
        "situation": "one sentence description",
        "likely_stuck_on": "one sentence struggle",
        "player_attributes": "player build type",
        "youtube_search": "specific query using location/mission/enemy",
        "tips": ["tip 1", "tip 2", "tip 3"],
        "chat_greeting": f"Friendly 1-2 sentence conversational opener addressing their current situation for {game_name}."
    }}
    </output_format>

    <important>
    Return raw JSON only. No markdown. No code blocks. No extra text.
    </important>
    """
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=False)
    buffer.seek(0)
    img_clean = Image.open(buffer)
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=[prompt, img_clean]
    )
    
    try:
        cleaned = clean_gemini_response(response.text)
        result = json.loads(cleaned)
        update_session_context(game_name, result) 
        
        # Save the dynamically generated greeting directly into our chat history
        greeting = result.get("chat_greeting", f"Scan complete. How can I assist you with {game_name}?")
        history.append({"role": "model", "text": greeting})
        save_chat_history(game_name, history)
        
        return result
    except json.JSONDecodeError:
        print("Gemini returned invalid JSON, raw response:\n", response.text)
        return {"game_name": game_name, "current_area": "Unknown", "situation": "Analysis failed", "likely_stuck_on": "Unknown", "youtube_search": f"{game_name} guide", "chat_greeting": "Sorry, my scan glitched. What do you need help with?"}
    except Exception as e:
        if "429" in str(e):
            print("Rate limited. We hit a 429 error.")
            # We don't sleep anymore. We just return a polite failure so the UI doesn't freeze.
            return {"game_name": game_name, "chat_greeting": "I'm receiving too many requests right now. Give me a few seconds to cool down!", "youtube_search": ""}
        else:
            raise e

def summarize_analysis(analysis: dict) -> str:
    area = analysis.get("current_area", "Unknown location")
    character = analysis.get("character", "Unknown").split(".")[0]
    stuck_on = analysis.get("likely_stuck_on", "").split(".")[0]
    tips_data = analysis.get("tips", [])

    if isinstance(tips_data, list):
        tips = "\n".join([f"• {tip}" for tip in tips_data])
    else:
        tips = f"• {tips_data}"

    return f"--- Analysis Report ---\nLocation: {area}\nCharacter: {character}\nIssue: {stuck_on}\n\n💡 PRO TIPS:\n{tips}\n----------------------"

def save_session_entry(game_name: str, entry: dict):
    os.makedirs(SESSION_DIR, exist_ok=True)
    file_path = f"{SESSION_DIR}/{game_name}_state.json"
    state = {
        "character": "Unknown", "max_game_stage": "Early Game",
        "last_area": "Unknown", "current_build": "Unknown", "recent_goals": []
    }
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            state = json.load(f)

    state["character"] = entry.get("character", state["character"])
    state["last_area"] = entry.get("current_area", state["last_area"])
    state["current_build"] = entry.get("build", state["current_build"])
    state["max_game_stage"] = entry.get("game_stage", state["max_game_stage"])

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

 
# CHATBOT MEMORY & COMMUNICATION
 
def load_chat_history(game_name: str) -> list:
    os.makedirs(SESSION_DIR, exist_ok=True)
    file_path = f"{SESSION_DIR}/{game_name}_chat.json"
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_chat_history(game_name: str, history: list):
    os.makedirs(SESSION_DIR, exist_ok=True)
    file_path = f"{SESSION_DIR}/{game_name}_chat.json"
    history = history[-10:] 
    with open(file_path, "w") as f:
        json.dump(history, f, indent=4)

def chat_with_tactiq(game_name: str, user_message: str) -> str:
    state = load_session_history(game_name)
    history = load_chat_history(game_name)
    
    context_str = "No recent screen scan available."
    if state:
        context_str = f"Character: {state.get('character', 'Unknown')}, Location: {state.get('last_area', 'Unknown')}, Build: {state.get('current_build', 'Unknown')}"

    # --- HYPER-OPTIMIZED PROMPT ---
    prompt = f"""You are TacTiQ, an elite AI gaming companion for {game_name}.

CRITICAL RULES:
1. THE GREETING FAST-TRACK: If the player just says "hi", "hello", "ssup", or "?", reply IMMEDIATELY with a short 1-sentence greeting. Do NOT analyze the game state. Just say hi back and ask what they need. (e.g., "Hey , still surviving? What do you need?")
2. TACTICAL SUPPORT: If they ask a specific question, use the [GAME STATE] to give 1-3 sentences of pro-level advice.
3. Speak directly to the player. No markdown or bullet points.

[GAME STATE]
{context_str}

[CHAT HISTORY]
"""
    for msg in history[-6:]:
        role = "Player" if msg["role"] == "user" else "TacTiQ"
        prompt += f"{role}: {msg['text']}\n"
    
    prompt += f"Player: {user_message}\nTacTiQ:"

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=prompt
        )
        ai_response = response.text.strip()
        
        history.append({"role": "user", "text": user_message})
        history.append({"role": "model", "text": ai_response})
        save_chat_history(game_name, history)
        
        return ai_response
    except Exception as e:
        print(f"Chat Error: {e}")
        return "My connection to the TacTiQ servers was interrupted. Try asking again."