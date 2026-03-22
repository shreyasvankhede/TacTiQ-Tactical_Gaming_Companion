import keyboard
import mss
import threading
from PIL import Image
from datetime import datetime
from game_detector import detect_running_game
from gemini_analyzer import analyze_screenshot, summarize_analysis
from youtube_search import search_tutorials


def capture_screenshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.rgb)
        img.save(filename)
    print(f"Screenshot saved: {filename}")
    return img, filename

def process():
    try:
        game = detect_running_game()
        print(f"Game detected: {game}")

        img, filename = capture_screenshot()

        analysis = analyze_screenshot(img, game)
        summary = summarize_analysis(analysis)
        print(f"\n--- Tactiq Analysis ---")
        print(summary)

        videos=search_tutorials(analysis.get("search_keywords",[]),game)
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