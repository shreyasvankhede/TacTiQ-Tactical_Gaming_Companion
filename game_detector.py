import psutil
import json

# Define where the JSON file lives
GAMES_FILE = "data/supported_games.json"

def load_known_games() -> dict:
    """Loads the list of supported games from the external JSON file."""
    try:
        with open(GAMES_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: '{GAMES_FILE}' not found. Please create the file.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: '{GAMES_FILE}' is corrupted. Check your JSON formatting.")
        return {}

def detect_running_game():
    """Scans active system processes and matches them against the JSON list."""
    known_games = load_known_games()
    
    for process in psutil.process_iter(['name']):
        try:
            process_name = process.info['name']
            if process_name in known_games:
                return known_games[process_name]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    return "Unknown Game"

if __name__=="__main__":
    print(f"Currently Detected: {detect_running_game()}")