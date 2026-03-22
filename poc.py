from pynput import keyboard
import mss
from PIL import Image
from datetime import datetime
from game_detector import detect_running_game
from gemini_analyzer import analyze_screenshot, summarize_analysis


def capture_screenshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.rgb)
        img.save(filename)
    
    print(f"Screenshot saved: {filename}")
    return img, filename

def on_f9():
    print("F9 pressed — capturing screen...")
    game = detect_running_game()
    print(f"Detected game: {game}")
    img, filename = capture_screenshot()

    print("Analyzing screenshot...")
    analysis = analyze_screenshot(img, game)
    summary = summarize_analysis(analysis)
    
    print("\n--- Tactiq Analysis ---")
    print(summary)
    print("\nSearch keywords:", analysis.get("search_keywords", []))

def on_press(key):
    if key == keyboard.Key.f9:
        on_f9()
with keyboard.Listener(on_press=on_press) as listener:
    listener.join()

if __name__ == "__main__":
    print("Tactiq running... Press F9 to capture. Ctrl+C to quit.")
    keyboard.add_hotkey('f9', on_f9)
    keyboard.wait()