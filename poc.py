import keyboard
import mss
import threading
from PIL import Image
from datetime import datetime
from game_detector import detect_running_game
from gemini_analyzer import analyze_screenshot, summarize_analysis
from youtube_search import search_tutorials
import os
DATA_DIR="data/screenshots"

def capture_screenshot(game_name):
    # 1. Define the specific folder for this game
    game_dir = os.path.join(DATA_DIR, game_name)
    os.makedirs(game_dir, exist_ok=True)
    
    # 2. Define ONLY the filename (not the full path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"screenshot_{timestamp}.png"
    
    # 3. Combine them for the full save path
    full_path = os.path.join(game_dir, file_name)
    
    with mss.mss() as sct:
        # Capture from the primary monitor
        raw = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.rgb)
        img.save(full_path) # Use the clean full path here
        
    print(f"Screenshot saved: {full_path}")
    return img, full_path

def process():
    try:
        game = detect_running_game()
        print(f"Game detected: {game}")

        img, filename = capture_screenshot(game)

        analysis = analyze_screenshot(img, game)
        print("Raw youtube_search field:", analysis.get("youtube_search"))
        summary = summarize_analysis(analysis)
        print(f"\n--- Tactiq Analysis ---")
        print(summary)

        videos=search_tutorials(analysis.get("youtube_search",[]),game)
        print("\n--- Tutorial Videos ---")
        for i, v in enumerate(videos, 1):
            print(f"{i}. {v['title']}")
            print(f"   {v['channel']}")
            print(f"   {v['url']}\n")

    except Exception as e:
        print(f"Error during analysis: {e}")

def on_f9():
    print("F9 pressed — analyzing in background...")
    thread = threading.Thread(target=process)
    thread.daemon = True
    thread.start()

if __name__ == "__main__":
    print("Tactiq running... Press F9 to capture. Ctrl+C to quit.")
    keyboard.add_hotkey('f9', on_f9)
    keyboard.wait()