import psutil

KNOWN_GAMES = {
    "eldenring.exe": "Elden Ring",
    "RocketLeague.exe": "Rocket League",
    "Minecraft.exe": "Minecraft",
    "GTA5.exe": "GTA V",
    "re8.exe": "Resident Evil Village",
    "Cyberpunk2077.exe": "Cyberpunk 2077",
    "DOOM.exe": "DOOM Eternal",
    "valheim.exe": "Valheim",
    "RDR2.exe": "Red Dead Redemption 2",
    "brave.exe": "Red Dead Redemption 2",
}

def detect_running_game():
    for process in psutil.process_iter(['name']):
        try:
            process_name = process.info['name']
            if process_name in KNOWN_GAMES:
                return KNOWN_GAMES[process_name]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return "Unknown Game"


if __name__=="__main__":
    print(detect_running_game())