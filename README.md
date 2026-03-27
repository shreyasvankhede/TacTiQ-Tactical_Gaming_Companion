# TacTiQ — Tactical Gaming Companion

> **Real-time AI gaming overlay. Press a hotkey. Get unstuck. Never leave your game.**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-41CD52?style=flat-square&logo=qt&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_Vision-AI_Engine-4285F4?style=flat-square&logo=google&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## What Is TacTiQ?

TacTiQ is a desktop overlay application that acts as a real-time AI co-pilot for gamers. When you're stuck — in a boss fight, lost in an open world, unsure of your next objective — press a single hotkey. TacTiQ captures your screen, analyzes your game situation using Gemini Vision, and surfaces instant tactical tips and context-aware YouTube tutorials directly over your game.

No alt-tabbing. No typing. No breaking immersion.

---

## Demo

![TacTiQ Overlay — Red Dead Redemption 2 ]
Input image:
<img width="1920" height="1080" alt="Screenshot 2026-03-26 203304" src="https://github.com/user-attachments/assets/dd4b2d5b-7669-4573-ad45-245d5790c1d6" />

Output:
<img width="1920" height="1080" alt="Screenshot 2026-03-26 203347" src="https://github.com/user-attachments/assets/c39d83aa-d3c1-47d3-b644-f66b8f843914" />
<img width="1920" height="1080" alt="Screenshot 2026-03-26 203415" src="https://github.com/user-attachments/assets/b5e6fc26-578b-4de3-86fe-488f0e7c816e" />
<img width="1920" height="1080" alt="Screenshot 2026-03-26 203439" src="https://github.com/user-attachments/assets/dac353bf-6ce8-4494-bfc7-52f6a4fe125b" />

*TacTiQ correctly identifying John marston,based on the game stage and enviroment — providing tips and embedded tutorial videos in real time*

---

## How It Works

```
Press F8
  → Silent screenshot captured (mss)
  → Active game detected (psutil + Steam manifest)
  → Gemini Vision analyzes game state
       — character, location, mission, progression stage
       — player intent inference (why are you in this area?)
       — contextual warnings (wrong gear, low resources)
  → YouTube Data API fetches relevant tutorials
  → Tips + videos appear in overlay (F9 to toggle)
  → Session memory updates for future context
```

All API calls run in background threads — zero FPS impact on your game.

---

## Key Features

### AI-Powered Situation Analysis
Gemini Vision reads your screenshot and identifies:
- Exact location and named region
- Character and story progression stage
- Active mission or free-roam objective
- Why you might be in that area (collectibles, boss, exploration)
- Contextual warnings (environmental hazards, gear mismatches)

### Session Memory
TacTiQ remembers your session history per game. If you revisit an earlier area in Elden Ring or RDR2, it knows you're not replaying from the start — it correctly identifies you as a late-game player revisiting for a reason.

Session history is stored locally in `data/sessions/{game_name}.txt` and persists across app restarts.

### Smart YouTube Integration
Generates a single targeted search query from your game context — not generic guides, but specific tutorials:
- `"Elden Ring Malenia Waterfowl Dance dodge guide"` not `"Elden Ring guide"`
- `"Red Dead Redemption 2 Grizzlies White Arabian location"` not `"RDR2 tutorial"`

Videos are embedded directly in the overlay using hardware-accelerated WebEngine viewports.

### Xbox Game Bar Inspired UI
- Translucent dark overlay with green accent
- Three-column layout: Alerts | Analysis | Resources
- Structured analysis cards per field (location, character, stage, mission)
- Picture-in-Picture mode for active video playback
- Draggable PiP window that stays out of your way

### Zero-Lag Architecture
- `QThread` workers for all API calls
- Screenshot capture and game detection run before API calls complete
- Hotkey listener never blocked by background processing

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI Framework | PyQt6 + PyQt6-WebEngine |
| AI Vision | Google Gemini 2.0 Flash / 2.5 Flash |
| Screen Capture | mss |
| Global Hotkeys | keyboard |
| YouTube Search | YouTube Data API v3 |
| Game Detection | psutil + Steam manifest parsing |
| Session Storage | Plain text, pipe-separated, per-game |

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/shreyasvankhede/TacTiQ-Tactical_Gaming_Companion.git
cd TacTiQ-Tactical_Gaming_Companion
```

### 2. Create a virtual environment
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up API keys
Create a `.env` file in the root directory:
```
GEMINI_API_KEY=your_gemini_api_key_here
YOUTUBE_API_KEY=your_youtube_api_key_here
```

**Getting API keys:**
- Gemini API key → [aistudio.google.com](https://aistudio.google.com) (free tier available)
- YouTube Data API v3 → [Google Cloud Console](https://console.cloud.google.com) (10,000 units/day free)

### 5. Run the app
```bash
python test_app.py
```

> **Important:** Run your terminal as Administrator. The `keyboard` library requires elevated permissions to intercept global hotkeys over fullscreen games.

---

## Usage

| Hotkey | Action |
|---|---|
| `F8` | Capture screen + analyze |
| `F9` | Toggle overlay open/closed |
| `Esc` | Hide overlay (or collapse to PiP if video playing) |
| `Alt+Tab` | Collapse to PiP mode |

**Recommended game setting:** Switch your game from Fullscreen Exclusive to **Borderless Windowed** for best hotkey compatibility.

---

## Supported Games (Auto-Detection)

TacTiQ auto-detects games via process scanning. Currently includes:

`Elden Ring` · `Red Dead Redemption 2` · `GTA V` · `Cyberpunk 2077` · `Minecraft` · `Rocket League` · `Resident Evil Village` · `DOOM Eternal` · `Valheim`

**Any game not listed** can be added manually by adding its executable to `KNOWN_GAMES` in `game_detector.py`:
```python
"YourGame.exe": "Your Game Name"
```

Full Steam library auto-detection is planned for V2.

---

## Project Structure

```
TacTiQ/
├── test_app.py          # Main entry point — PyQt6 overlay UI
├── poc.py               # Terminal POC — pipeline without UI
├── game_detector.py     # psutil process scanner + game library
├── gemini_analyzer.py   # Vision analysis, session memory, prompt engineering
├── youtube_search.py    # Contextual tutorial search
├── session_manager.py   # Persistent session history per game
├── data/
│   └── sessions/        # Per-game session history files
├── .env                 # API keys (not committed)
└── requirements.txt
```

---

## Architecture Notes

### Prompt Engineering
The Gemini prompt uses XML-structured sections (`<role>`, `<context>`, `<instructions>`, `<search_query_rules>`, `<output_format>`) to separate concerns and improve output reliability. Key design decisions:

- **Session history injection** — prior game state is injected as context so Gemini correctly handles revisited areas
- **HUD cross-referencing** — Gemini is instructed to cross-reference character/stage guesses against visible HUD elements (core sizes, money, Dead Eye level) to avoid visual bias
- **Single targeted search query** — instead of keyword lists, a single optimized YouTube query is generated based on priority rules (active mission > known location > game stage > fallback)

### Threading Model
Hotkey callbacks spawn `QThread` workers immediately and return. The UI thread is never blocked by API calls. Results are delivered via Qt signals when ready.

### Session Memory
Each game gets its own session file at `data/sessions/{game_name}.txt`. Entries are pipe-separated with 5 fields: `character | game_stage | current_area | confidence | goal`. Last 3 entries are injected into each Gemini prompt as ground truth context.

---

## Roadmap

### V2
- [ ] Auto-detect Steam, Epic, and GOG game libraries
- [ ] Groq + Llama chat panel for follow-up questions
- [ ] Game library launcher screen with cover art
- [ ] Confidence-based UI — auto-tips for high confidence, ask user for low confidence
- [ ] SQLite caching with perceptual hashing (skip redundant API calls)

### V3
- [ ] Per-game tip history and manual notes editor
- [ ] Controller navigation support
- [ ] Multi-monitor support
- [ ] Hotkey customization

---

## Comparison

| Feature | TacTiQ | NVIDIA G-Assist | Xbox Gaming Copilot |
|---|---|---|---|
| Hardware requirement | Any PC | RTX GPU only | Xbox ecosystem |
| Works offline | No | Yes (local model) | No |
| YouTube integration | ✅ | ❌ | ❌ |
| Session memory | ✅ | ❌ | ❌ |
| Open source | ✅ | ❌ | ❌ |
| Free to use | ✅ (API limits) | ✅ | Paid features |
| Privacy | Local + Gemini API | Fully local | Microsoft servers |

---

## Disclaimer

TacTiQ is a personal portfolio project. It does not interact with game memory, files, or processes in any way. All analysis is performed entirely through external visual analysis of screenshots. It does not violate any game's terms of service.

---

## Author

**Shreyas Vankhede**


[LinkedIn](https://linkedin.com/in/shreyasvankhede)