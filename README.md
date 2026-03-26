# 🎯 TacTiQ  
### *Your AI-Powered Tactical Gaming Companion*

TacTiQ is a seamless, real-time gaming overlay that acts as your personal AI co-pilot. Powered by the **Google Gemini Vision API**, it captures your live gameplay, analyzes your current situation (locations, bosses, builds), and provides instant tactical advice and context-aware YouTube guides — all without breaking your game's immersion.

> ⚠️ Replace the image below with your actual screenshot  
```md
![TacTiQ Screenshot](docs/screenshot.png)
```

---

## ✨ Key Features

### 🧠 Real-Time Visual Analysis
Press a single hotkey to scan your screen. TacTiQ identifies:
- Your exact location  
- The boss you are fighting  
- What you are likely struggling with  

---

### 💬 Context-Aware AI Chatbot
- Fully interactive conversational UI  
- Persistent session memory  
- Ask follow-up questions — the AI remembers your current game state  

---

### 📺 Smart YouTube Integration
- Automatically fetches relevant tutorials  
- Example: *"Malenia dodge guide"*  
- Embedded directly into floating, hardware-accelerated viewports  

---

### ⚡ Zero-Lag Architecture
- Built using `concurrent.futures` and `QThread`  
- All API calls and image processing run asynchronously  
- Ensures **zero FPS drop during gameplay**

---

### 🎨 Premium "Frosted Glass" UI
- Built with **PyQt6**  
- Features:
  - Translucent acrylic design  
  - Pill-shaped inputs  
  - Dynamic layout grids  
- Inspired by overlays like Discord and Xbox Game Bar  

---

### ⌨️ Global OS Hooking
- Hardware-level hotkeys  
- Works seamlessly over:
  - DirectX  
  - Vulkan fullscreen games  

---

## 🛠️ Technology Stack

| Component         | Technology Used |
|------------------|----------------|
| Language         | Python 3.10+   |
| GUI Framework    | PyQt6 & PyQt6-WebEngine |
| AI Engine        | Google GenAI SDK (Gemini Flash Vision) |
| Screen Capture   | mss |
| System Hooks     | keyboard |

---

## 🚀 Architecture Highlights

### 🔄 Asynchronous Multi-Threading
- UI runs on the main thread  
- Workers:
  - `GeminiWorker`
  - `YouTubeWorker`
  - `ChatWorker`  
- Prevents UI freezing during API calls  

---

### ⚙️ Concurrent Execution
- Uses `ThreadPoolExecutor`  
- Runs:
  - Visual analysis  
  - YouTube scraping  
- **Reduces response time significantly**

---

### 🧾 JSON State Memory
- Maintains session context using:
  - `_chat.json`  
  - `_state.json`  
- Avoids unnecessary re-scanning  
- Enables persistent conversations  

---

### 🎥 Bypassing Embed Restrictions
- Custom HTML/JS injection  
- Uses strict referrer policies  
- Runs inside `QWebEngineView`  
- Allows playback of restricted YouTube embeds  

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/yourusername/TacTiQ.git
cd TacTiQ
```

---

### 2️⃣ Install Dependencies
> Recommended: Use a virtual environment

```bash
pip install PyQt6 PyQt6-WebEngine google-genai pillow mss keyboard python-dotenv
```

---

### 3️⃣ Set Up API Key
Create a `.env` file in the root directory:

```env
GEMINI_API_KEY2=your_api_key_here
```

---

### 4️⃣ Run the App
```bash
python app.py
```

---

### ⚠️ Important Note
You may need to run your terminal/IDE as **Administrator** for global hotkeys to work properly with:
- Anti-cheat systems  
- Exclusive fullscreen games  

---

## 🎮 How to Use

- **F8** → Capture & Analyze  
  - Takes a silent screenshot  
  - Sends it to AI for analysis  

- **F9** → Toggle Overlay  
  - Opens/closes TacTiQ dashboard  

- **Esc / Alt+Tab** → Quick Hide  
  - Minimizes overlay  
  - Pauses background video/audio  

---

## 🔮 Future Roadmap

- [ ] 🗄️ Local Database  
  - SQLite for long-term player tracking  

- [ ] 🎮 Controller Integration  
  - XInput support  
  - Navigate UI without mouse  

- [ ] 🔊 Audio Feedback  
  - Text-to-Speech (TTS) alerts during gameplay  

---

## ⚠️ Disclaimer

> This is a personal portfolio project.  
TacTiQ does **not** interact with game memory or files.  
It relies entirely on **external visual analysis**.
