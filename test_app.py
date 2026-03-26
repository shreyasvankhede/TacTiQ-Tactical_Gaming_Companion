import sys
import os
import ctypes
import random
from datetime import datetime
import keyboard
import mss
from PIL import Image
import concurrent.futures # <-- NEW: For simultaneous API calls

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QScrollArea, QFrame, QLabel, QPushButton, QLineEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject, QUrl
from PyQt6.QtGui import QColor, QPainter

# --- CRITICAL: OPENGL & WEB ENGINE ---
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

from game_detector import detect_running_game
from gemini_analyzer import analyze_screenshot, summarize_analysis, chat_with_tactiq, generate_chat_greeting
from youtube_search import search_tutorials

DATA_DIR = "data/screenshots"

# ==========================================
# 1. CAPTURE LOGIC & UTILS
# ==========================================
def capture_screenshot(game_name):
    game_dir = os.path.join(DATA_DIR, game_name)
    os.makedirs(game_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"screenshot_{timestamp}.png"
    full_path = os.path.join(game_dir, file_name)
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.rgb)
        img.save(full_path) 
    return img, full_path

def extract_video_id(url):
    if "watch?v=" in url: return url.split("watch?v=")[1].split("&")[0]
    elif "youtu.be/" in url: return url.split("youtu.be/")[1].split("?")[0]
    elif "embed/" in url: return url.split("embed/")[1].split("?")[0]
    return ""

def get_simple_iframe_html(video_id):
    return f"""
    <!DOCTYPE html><html><head>
        <meta name="referrer" content="strict-origin-when-cross-origin"/>
        <style>body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: transparent; }}</style>
    </head><body>
        <iframe width="100%" height="100%" src="https://www.youtube-nocookie.com/embed/{video_id}?autoplay=0&rel=0" frameborder="0" allow="autoplay; encrypted-media; fullscreen"></iframe>
    </body></html>
    """

# ==========================================
# 2. BACKGROUND WORKERS
# ==========================================
class GeminiWorker(QThread):
    finished_signal = pyqtSignal(list, str, list)
    error_signal = pyqtSignal(str)

    def parse_tips(self, raw_tips):
        if isinstance(raw_tips, list): return raw_tips 
        if isinstance(raw_tips, str):
            if '•' in raw_tips: return [t.strip() for t in raw_tips.split('•') if len(t.strip()) > 5]
            if '\n' in raw_tips:
                lines = [t.strip() for t in raw_tips.split('\n') if len(t.strip()) > 5]
                if len(lines) > 1: return lines
            sentences = [s.strip() for s in raw_tips.split('. ') if len(s.strip()) > 5]
            return [s + '.' if not s.endswith('.') else s for s in sentences]
        return ["Active Game Detected.", "Check analysis for tactical details."]

    def run(self):
        try:
            game = detect_running_game()
            img, filename = capture_screenshot(game)
            
            # --- NEW: CONCURRENT API CALLS ---
            # We run analyze_screenshot and youtube_search at the EXACT same time
            # because youtube_search can use a generic fallback if needed immediately.
            # Then we run the chat greeting.
            
            analysis = analyze_screenshot(img, game)
            
            # Backend logging
            summary = summarize_analysis(analysis)
            print(summary) 
            
            # Extract basic data needed for parallel tasks
            if isinstance(analysis, dict):
                yt_query = analysis.get("youtube_search", "")
                if isinstance(yt_query, list): yt_query = " ".join(yt_query)
                tips = self.parse_tips(analysis.get("tips", ""))
            else:
                yt_query = ""
                tips = ["Active Game Detected.", "Check analysis for tactical details."]

            if not yt_query or len(yt_query) < 3:
                area = analysis.get('current_area', '')
                yt_query = f"{game} {area} guide"

            # Execute the heavy Chat Generation and YouTube Search SIMULTANEOUSLY
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Start both tasks
                future_greeting = executor.submit(generate_chat_greeting, game, analysis)
                future_youtube = executor.submit(search_tutorials, yt_query, game)
                
                # Wait for both to finish
                greeting = future_greeting.result()
                
                videos = []
                try:
                    videos = future_youtube.result()
                except Exception as e:
                    print(f"YT Search Error: {e}")
                    
            # Fallback if primary YT search failed
            if not videos:
                try:
                    videos = search_tutorials(f"{game} tips and tricks", game)
                except:
                    pass

            video_ids = [extract_video_id(v.get('url', '')) for v in videos]
            
            self.finished_signal.emit(tips, greeting, video_ids)
            
        except Exception as e:
            self.error_signal.emit(str(e))

class YouTubeWorker(QThread):
    finished_signal = pyqtSignal(list)
    def __init__(self):
        super().__init__()
        self.query = ""
    def run(self):
        game = detect_running_game()
        videos = search_tutorials(self.query, game)
        video_ids = [extract_video_id(v.get('url', '')) for v in videos]
        self.finished_signal.emit(video_ids)

class ChatWorker(QThread):
    finished_signal = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.message = ""
    def run(self):
        game = detect_running_game()
        response = chat_with_tactiq(game, self.message)
        self.finished_signal.emit(response)

# ==========================================
# 3. TOAST NOTIFICATION
# ==========================================
class ToastNotification(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen.width() - 320, screen.height() - 110, 300, 50)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 0, 20, 0)
        self.label = QLabel("")
        self.label.setStyleSheet("color: #FFFFFF; font-family: 'Segoe UI', Roboto, sans-serif; font-size: 14px; font-weight: 600;")
        self.layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignVCenter)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(20, 20, 25, 240))
        painter.setPen(QColor(168, 85, 247, 80)) 
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 16, 16)

    def show_toast(self, message, duration=None):
        self.label.setText(message)
        self.show()
        if duration:
            QTimer.singleShot(duration, self.hide)


# ==========================================
# 4. MAIN HUD OVERLAY (FROSTED GLASS & CHAT)
# ==========================================
class TacTiQOverlay(QWidget):
    search_requested = pyqtSignal(str) 
    chat_submitted = pyqtSignal(str) 

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())
        
        self.current_video_ids = ["", "", ""]

        self.dash_layout = QHBoxLayout(self)
        self.dash_layout.setContentsMargins(40, 40, 40, 40)
        self.dash_layout.setSpacing(25)

        # --- LEFT: TIPS (Alerts) ---
        self.left_col = QVBoxLayout()
        self.lbl_tips_header = QLabel("TACTICAL ALERTS")
        self.lbl_tips_header.setObjectName("ColHeader")
        self.left_col.addWidget(self.lbl_tips_header)
        
        self.tips_container = QWidget()
        self.tips_layout = QVBoxLayout(self.tips_container)
        self.tips_layout.setContentsMargins(0, 0, 0, 0)
        self.tips_layout.setSpacing(12) 
        self.left_col.addWidget(self.tips_container)
        self.left_col.addStretch() 
        self.dash_layout.addLayout(self.left_col, stretch=20)

        # --- MIDDLE: AI CHATBOT INTERFACE ---
        self.mid_col = QVBoxLayout()
        self.lbl_chat_header = QLabel("TACTIQ AI ASSISTANT")
        self.lbl_chat_header.setObjectName("ColHeader")
        self.mid_col.addWidget(self.lbl_chat_header)
        
        self.chat_frame = QFrame()
        self.chat_frame.setObjectName("GlassContainer")
        self.chat_layout = QVBoxLayout(self.chat_frame)
        self.chat_layout.setContentsMargins(15, 15, 15, 15)
        self.chat_layout.setSpacing(10)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setObjectName("TransparentScroll")
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.chat_history_widget = QWidget()
        self.chat_history_widget.setStyleSheet("background: transparent;")
        self.chat_history_layout = QVBoxLayout(self.chat_history_widget)
        self.chat_history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_history_layout.setSpacing(16)
        self.chat_scroll.setWidget(self.chat_history_widget)
        
        self.chat_layout.addWidget(self.chat_scroll)

        self.chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ask TacTiQ anything about the game...")
        self.chat_input.setObjectName("ChatInput")
        self.chat_input.returnPressed.connect(self.emit_chat)
        
        self.btn_send = QPushButton("➤")
        self.btn_send.setObjectName("SendBtn")
        self.btn_send.clicked.connect(self.emit_chat)
        
        self.chat_input_layout.addWidget(self.chat_input)
        self.chat_input_layout.addWidget(self.btn_send)
        self.chat_layout.addLayout(self.chat_input_layout)

        self.mid_col.addWidget(self.chat_frame)
        self.dash_layout.addLayout(self.mid_col, stretch=55)

        # --- RIGHT: YOUTUBE & SEARCH ---
        self.right_col = QVBoxLayout()
        self.lbl_yt_header = QLabel("RESOURCES")
        self.lbl_yt_header.setObjectName("ColHeader")
        self.right_col.addWidget(self.lbl_yt_header)

        self.search_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search YouTube...")
        self.search_bar.setObjectName("SearchBar")
        self.search_bar.returnPressed.connect(self.emit_search)
        self.btn_search = QPushButton("🔍")
        self.btn_search.setObjectName("SearchBtn")
        self.btn_search.clicked.connect(self.emit_search)
        
        self.search_layout.addWidget(self.search_bar)
        self.search_layout.addWidget(self.btn_search)
        self.right_col.addLayout(self.search_layout)
        
        self.yt_container = QWidget()
        self.yt_container.setObjectName("GlassContainer") 
        self.yt_layout = QVBoxLayout(self.yt_container)
        self.yt_layout.setContentsMargins(15, 15, 15, 15)
        self.yt_layout.setSpacing(15) 
        self.right_col.addWidget(self.yt_container)
        self.right_col.addStretch() 
        self.dash_layout.addLayout(self.right_col, stretch=25)

        # --- PREMIUM TYPOGRAPHY STYLESHEET ---
        self.setStyleSheet("""
            * { font-family: 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif; }
            #ColHeader { 
                color: #FFFFFF; font-size: 13px; font-weight: 800; letter-spacing: 1.5px; padding-bottom: 5px; 
            }
            #GlassContainer { 
                background-color: rgba(20, 20, 25, 160); border: 1px solid rgba(255, 255, 255, 15); border-radius: 16px; 
            }
            #TransparentScroll { background: transparent; border: none; }
            
            #TipCard { background-color: rgba(30, 30, 35, 180); border-left: 4px solid #A855F7; border-radius: 12px; }
            #TipText { color: #E2E8F0; font-size: 14.5px; }
            
            #UserBubble {
                background-color: #8B5CF6; color: white; 
                border-radius: 16px; border-top-right-radius: 4px; padding: 12px 16px; 
            }
            #AIBubble {
                background-color: rgba(35, 35, 40, 240); color: #E2E8F0; 
                border: 1px solid rgba(255, 255, 255, 10);
                border-radius: 16px; border-top-left-radius: 4px; padding: 12px 16px; 
            }
            #ChatNameTag {
                color: #A855F7; font-size: 11px; font-weight: 800; letter-spacing: 1px; padding-left: 2px;
            }
            
            #ChatInput, #SearchBar { 
                background-color: rgba(10, 10, 12, 180); color: #FFF; 
                border: 1px solid rgba(255,255,255,20); border-radius: 20px; padding: 10px 18px; font-size: 14px; 
            }
            #ChatInput:focus, #SearchBar:focus { border: 1px solid #A855F7; }
            
            #SendBtn, #SearchBtn { 
                background-color: rgba(168, 85, 247, 180); color: #FFF; 
                border: none; border-radius: 20px; padding: 10px 18px; font-weight: bold;
            }
            #SendBtn:hover, #SearchBtn:hover { background-color: rgba(168, 85, 247, 255); }
        """)

        self.add_chat_bubble("Welcome to TacTiQ! Press F8 to scan your screen, or ask me a question.", is_user=False)

        self.video_widgets = []
        for _ in range(3): 
            view = QWebEngineView()
            view.setFixedSize(320, 180) 
            view.page().setBackgroundColor(Qt.GlobalColor.transparent)
            view.setStyleSheet("background: rgba(10,10,12,150); border-radius: 12px;")
            self.yt_layout.addWidget(view, alignment=Qt.AlignmentFlag.AlignCenter)
            self.video_widgets.append(view)

    def emit_search(self):
        query = self.search_bar.text().strip()
        if query: self.search_requested.emit(query)

    def emit_chat(self):
        text = self.chat_input.text().strip()
        if text:
            self.add_chat_bubble(text, is_user=True)
            self.chat_input.clear()
            self.chat_submitted.emit(text)

    def add_chat_bubble(self, text, is_user=False):
        bubble_container = QWidget()
        bubble_layout = QVBoxLayout(bubble_container)
        bubble_layout.setContentsMargins(0, 0, 0, 10) 
        bubble_layout.setSpacing(4)
        
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl = QLabel()
        formatted_text = f"<div style='line-height: 1.5; font-size: 14.5px;'>{text}</div>"
        lbl.setText(formatted_text)
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(480) 
        
        if is_user:
            lbl.setObjectName("UserBubble")
            row_layout.addStretch()
            row_layout.addWidget(lbl)
            bubble_layout.addLayout(row_layout)
        else:
            lbl.setObjectName("AIBubble")
            name_lbl = QLabel("✧ TACTIQ AI")
            name_lbl.setObjectName("ChatNameTag")
            bubble_layout.addWidget(name_lbl)
            
            row_layout.addWidget(lbl)
            row_layout.addStretch()
            bubble_layout.addLayout(row_layout)
            
        self.chat_history_layout.addWidget(bubble_container)
        QTimer.singleShot(100, lambda: self.chat_scroll.verticalScrollBar().setValue(self.chat_scroll.verticalScrollBar().maximum()))

    def load_videos(self, video_ids: list):
        self.current_video_ids = video_ids + [""] * (3 - len(video_ids))
        for i, vid in enumerate(self.current_video_ids[:3]):
            if vid:
                self.video_widgets[i].setHtml(get_simple_iframe_html(vid), QUrl("https://localhost"))
            else:
                self.video_widgets[i].setHtml("")

    def update_parameters(self, tips: list, greeting: str, video_ids: list):
        for i in reversed(range(self.tips_layout.count())):
            self.tips_layout.itemAt(i).widget().setParent(None)
        
        icons = ["🎯", "⚔️", "🛡️", "⚡", "🔥"]
        for text in tips:
            card = QFrame()
            card.setObjectName("TipCard")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(15, 15, 15, 15)
            
            icon_lbl = QLabel(random.choice(icons))
            icon_lbl.setStyleSheet("font-size: 20px; background: transparent;")
            card_layout.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignTop)
            
            body = QLabel(text)
            body.setWordWrap(True)
            body.setObjectName("TipText")
            card_layout.addWidget(body)
            self.tips_layout.addWidget(card)

        self.add_chat_bubble(greeting, is_user=False)
        self.load_videos(video_ids)

    def hide_overlay(self):
        for view in self.video_widgets:
            view.setHtml("")
        self.hide()

    def show_overlay(self):
        self.load_videos(self.current_video_ids)
        self.showFullScreen()
        self.activateWindow()
        self.setFocus()

    def toggle_overlay(self):
        if self.isVisible(): self.hide_overlay()
        else: self.show_overlay()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 10, 15, 190))


# ==========================================
# 5. SIGNAL BRIDGE & CONTROLLER
# ==========================================
class HotkeyBridge(QObject):
    f8_pressed = pyqtSignal()
    f9_pressed = pyqtSignal()
    force_hide_triggered = pyqtSignal() 

class AppController(QObject):
    def __init__(self):
        super().__init__()
        self.overlay = TacTiQOverlay() 
        self.toast = ToastNotification() 
        
        self.worker = GeminiWorker()
        self.yt_worker = YouTubeWorker() 
        self.chat_worker = ChatWorker()
        
        self.worker.finished_signal.connect(self.on_api_finished)
        self.worker.error_signal.connect(self.on_api_error)
        self.yt_worker.finished_signal.connect(self.on_manual_search_finished)
        self.chat_worker.finished_signal.connect(self.on_chat_response_received)
        
        self.overlay.search_requested.connect(self.perform_manual_search)
        self.overlay.chat_submitted.connect(self.handle_chat_message)

        self.bridge = HotkeyBridge()
        self.bridge.f8_pressed.connect(self.take_screenshot_and_analyze)
        self.bridge.f9_pressed.connect(self.overlay.toggle_overlay)
        self.bridge.force_hide_triggered.connect(self.handle_force_hide)

        print("TacTiQ running... F8: Capture | F9: Toggle Overlay | Esc/Alt+Tab: Hide")
        
        keyboard.add_hotkey('f8', self.bridge.f8_pressed.emit)
        keyboard.add_hotkey('f9', self.bridge.f9_pressed.emit)
        keyboard.add_hotkey('esc', self.bridge.force_hide_triggered.emit)
        keyboard.add_hotkey('alt+tab', self.bridge.force_hide_triggered.emit)

    def handle_chat_message(self, text):
        if self.chat_worker.isRunning(): return
        self.toast.show_toast("TacTiQ: Thinking...", duration=2000)
        self.chat_worker.message = text
        self.chat_worker.start()

    def on_chat_response_received(self, response_text):
        self.overlay.add_chat_bubble(response_text, is_user=False)

    def handle_force_hide(self):
        if self.overlay.isVisible():
            self.overlay.hide_overlay() 

    def perform_manual_search(self, query):
        if self.yt_worker.isRunning(): return
        self.toast.show_toast(f"Searching for '{query}'...", duration=2000)
        self.yt_worker.query = query
        self.yt_worker.start()

    def on_manual_search_finished(self, urls):
        self.overlay.load_videos(urls) 

    def take_screenshot_and_analyze(self):
        if self.worker.isRunning(): return 
        self.toast.show_toast("TacTiQ: Capturing & Analyzing...", duration=None)
        self.worker.start()

    def on_api_finished(self, tips, greeting, urls):
        self.overlay.update_parameters(tips, greeting, urls)
        self.toast.show_toast("TacTiQ Intel Ready. Press F9.", duration=4000)

    def on_api_error(self, error_msg):
        self.toast.show_toast(f"Error: {error_msg}", duration=4000)

if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    controller = AppController()
    sys.exit(app.exec())