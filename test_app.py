import sys
import os
from datetime import datetime
import keyboard
import mss
from PIL import Image

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QScrollArea, QFrame, QLabel, QPushButton)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject, QPoint, QUrl
from PyQt6.QtGui import QColor, QPainter

# --- CRITICAL: OPENGL & WEB ENGINE ---
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage

from game_detector import detect_running_game
from gemini_analyzer import analyze_screenshot, summarize_analysis
from youtube_search import search_tutorials

DATA_DIR = "data/screenshots"

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

def get_js_iframe_html(video_id):
    """Bulletproof JS Bridge"""
    return f"""
    <!DOCTYPE html><html><head>
        <style>body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: transparent; }}</style>
    </head><body>
        <div id="player"></div>
        <script>
            var tag = document.createElement('script');
            tag.src = "https://www.youtube.com/iframe_api";
            var firstScriptTag = document.getElementsByTagName('script')[0];
            firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
            var player;
            function onYouTubeIframeAPIReady() {{
                player = new YT.Player('player', {{
                    height: '100%', width: '100%', videoId: '{video_id}',
                    playerVars: {{ 'playsinline': 1, 'autoplay': 0, 'rel': 0, 'modestbranding': 1, 'origin': 'https://localhost' }},
                    events: {{
                        'onStateChange': function(event) {{
                            if (event.data === 1) {{ console.log("TACTIQ_PLAYING"); }}
                            else if (event.data === 2 || event.data === 0) {{ console.log("TACTIQ_STOPPED"); }}
                        }}
                    }}
                }});
            }}
        </script>
    </body></html>
    """

class CustomWebPage(QWebEnginePage):
    state_changed = pyqtSignal(bool)
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """Mutes all Chromium warnings and only listens for PiP triggers"""
        if "TACTIQ_PLAYING" in message:
            self.state_changed.emit(True)
        elif "TACTIQ_STOPPED" in message:
            self.state_changed.emit(False)

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
            analysis = analyze_screenshot(img, game)
            summary = summarize_analysis(analysis)

            if isinstance(analysis, dict):
                yt_query = analysis.get("youtube_search", "")
                if isinstance(yt_query, list): yt_query = " ".join(yt_query)
                tips = self.parse_tips(analysis.get("tips", ""))
            else:
                yt_query = ""
                tips = ["Active Game Detected.", "Check analysis for tactical details."]

            videos = search_tutorials(yt_query, game)
            video_ids = [extract_video_id(v.get('url', '')) for v in videos]
            self.finished_signal.emit(tips, str(summary), video_ids)
        except Exception as e:
            self.error_signal.emit(str(e))


# ==========================================
# 4. MAIN HUD OVERLAY
# ==========================================
class TacTiQOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Core State
        self.is_pip_mode = False
        self.playing_video_view = None
        self.oldPos = QPoint()

        # Master Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # --- DASHBOARD CONTAINER (Fullscreen Mode) ---
        self.dash_widget = QWidget()
        self.dash_layout = QHBoxLayout(self.dash_widget)
        self.dash_layout.setContentsMargins(50, 50, 50, 50)
        self.dash_layout.setSpacing(35)

        self.left_col = QVBoxLayout()
        self.lbl_tips_header = QLabel("Alerts")
        self.lbl_tips_header.setObjectName("ColHeader")
        self.left_col.addWidget(self.lbl_tips_header)
        self.tips_container = QWidget()
        self.tips_layout = QVBoxLayout(self.tips_container)
        self.tips_layout.setContentsMargins(0, 0, 0, 0)
        self.tips_layout.setSpacing(12) 
        self.left_col.addWidget(self.tips_container)
        self.left_col.addStretch() 
        self.dash_layout.addLayout(self.left_col, stretch=20)

        self.mid_col = QVBoxLayout()
        self.lbl_analysis_header = QLabel("Analysis")
        self.lbl_analysis_header.setObjectName("ColHeader")
        self.mid_col.addWidget(self.lbl_analysis_header)
        self.analysis_frame = QFrame()
        self.analysis_frame.setObjectName("GameBarContainer")
        self.analysis_layout = QVBoxLayout(self.analysis_frame)
        self.analysis_layout.setContentsMargins(25, 25, 25, 25)
        self.summary_label = QLabel("Awaiting Scan...")
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("AnalysisText")
        self.analysis_layout.addWidget(self.summary_label)
        self.mid_col.addWidget(self.analysis_frame)
        self.mid_col.addStretch() 
        self.dash_layout.addLayout(self.mid_col, stretch=55)

        self.right_col = QVBoxLayout()
        self.lbl_yt_header = QLabel("Resources")
        self.lbl_yt_header.setObjectName("ColHeader")
        self.right_col.addWidget(self.lbl_yt_header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("GameBarContainer") 
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.yt_container = QWidget()
        self.yt_container.setStyleSheet("background: transparent;")
        self.yt_layout = QVBoxLayout(self.yt_container)
        self.yt_layout.setContentsMargins(15, 15, 15, 15)
        self.yt_layout.setSpacing(20) 
        self.scroll.setWidget(self.yt_container)
        self.right_col.addWidget(self.scroll)
        self.dash_layout.addLayout(self.right_col, stretch=25)

        # --- PIP CONTAINER (Collapsed Mode) ---
        self.pip_widget = QWidget()
        self.pip_layout = QVBoxLayout(self.pip_widget)
        self.pip_layout.setContentsMargins(0, 0, 0, 0)
        self.pip_layout.setSpacing(0)

        self.pip_toolbar = QFrame()
        self.pip_toolbar.setFixedHeight(30)
        self.pip_toolbar.setStyleSheet("background-color: rgba(20, 20, 20, 255);")
        t_layout = QHBoxLayout(self.pip_toolbar)
        t_layout.setContentsMargins(10, 0, 5, 0)
        
        lbl = QLabel("TacTiQ PiP")
        lbl.setStyleSheet("color: #FFFFFF; font-family: 'Segoe UI Variable Display'; font-weight: bold; font-size: 12px;")
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet("QPushButton { color: white; background: transparent; border: none; font-weight: bold; } QPushButton:hover { background: #FF4444; border-radius: 4px; }")
        btn_close.clicked.connect(self.close_pip)
        
        t_layout.addWidget(lbl)
        t_layout.addStretch()
        t_layout.addWidget(btn_close)

        self.pip_video_area = QVBoxLayout()
        self.pip_layout.addWidget(self.pip_toolbar)
        self.pip_layout.addLayout(self.pip_video_area)
        self.pip_widget.hide() 

        self.main_layout.addWidget(self.dash_widget)
        self.main_layout.addWidget(self.pip_widget)

        self.setStyleSheet("""
            #ColHeader { color: #FFFFFF; font-family: 'Segoe UI Variable Display', sans-serif; font-size: 16px; font-weight: 600; padding-bottom: 5px; }
            #GameBarContainer { background-color: rgba(32, 32, 32, 220); border: 1px solid rgba(255, 255, 255, 15); border-radius: 8px; }
            #TipCard { background-color: rgba(42, 42, 42, 230); border: 1px solid rgba(255, 255, 255, 15); border-radius: 6px; padding: 14px; }
            #TipText { color: #E6E6E6; font-family: 'Segoe UI Variable Text', sans-serif; font-size: 14px; line-height: 1.4; background: transparent; }
            #AnalysisText { background-color: transparent; color: #FFFFFF; border: none; font-size: 16px; font-family: 'Segoe UI Variable Text', sans-serif; line-height: 1.5; }
        """)

        self.video_widgets = []
        self.placeholders = []
        
        for i in range(5): 
            placeholder = QVBoxLayout()
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.yt_layout.addLayout(placeholder)
            self.placeholders.append(placeholder)
            
            view = QWebEngineView()
            view.setFixedSize(320, 180) 
            view.page().setBackgroundColor(Qt.GlobalColor.transparent)
            
            page = CustomWebPage()
            view.setPage(page)
            page.state_changed.connect(lambda is_playing, v=view: self.on_video_state_changed(is_playing, v))
            
            view.hide()
            placeholder.addWidget(view)
            self.video_widgets.append(view)

        # Removed the buggy QTimer! We rely completely on global hotkeys now.

    def on_video_state_changed(self, is_playing, view_widget):
        if is_playing: self.playing_video_view = view_widget
        elif self.playing_video_view == view_widget: self.playing_video_view = None

    def collapse_to_pip(self):
        self.is_pip_mode = True
        self.dash_widget.hide()
        self.pip_video_area.addWidget(self.playing_video_view)
        self.pip_widget.show()
        self.showNormal()
        self.resize(320, 180 + 30) 
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 340, screen.height() - 260)

    def expand_to_dashboard(self):
        self.is_pip_mode = False
        self.pip_widget.hide()
        if self.playing_video_view:
            idx = self.video_widgets.index(self.playing_video_view)
            self.placeholders[idx].addWidget(self.playing_video_view)
        self.dash_widget.show()
        self.showFullScreen()

    def toggle_overlay(self):
        if self.is_pip_mode:
            self.expand_to_dashboard()
        elif self.isVisible():
            if self.playing_video_view:
                self.collapse_to_pip()
            else:
                self.hide()
        else:
            self.expand_to_dashboard()

    def close_pip(self):
        if self.playing_video_view:
            self.playing_video_view.setHtml("") 
            self.playing_video_view = None
        self.hide()
        self.is_pip_mode = False

    def mousePressEvent(self, event):
        if self.is_pip_mode: self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.is_pip_mode and hasattr(self, 'oldPos'):
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def update_parameters(self, tips: list, analysis: str, video_ids: list):
        for i in reversed(range(self.tips_layout.count())):
            self.tips_layout.itemAt(i).widget().setParent(None)
        for text in tips:
            card = QFrame()
            card.setObjectName("TipCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(15, 15, 15, 15)
            body = QLabel(text)
            body.setWordWrap(True)
            body.setObjectName("TipText")
            card_layout.addWidget(body)
            self.tips_layout.addWidget(card)

        self.summary_label.setText(analysis.replace('\n', '<br>'))
        for vw in self.video_widgets:
            vw.hide()
            vw.setHtml("")
        for i, vid in enumerate(video_ids[:5]):
            if vid:
                self.video_widgets[i].setHtml(get_js_iframe_html(vid), QUrl("https://localhost"))
                self.video_widgets[i].show()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self.is_pip_mode:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 160))
        else:
            painter.fillRect(self.rect(), QColor(25, 25, 25, 255))

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
        self.label.setStyleSheet("color: #FFFFFF; font-family: 'Segoe UI Variable Text'; font-size: 14px; font-weight: 600;")
        self.layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignVCenter)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(32, 32, 32, 230))
        painter.setPen(QColor(255, 255, 255, 40)) 
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)

    def show_toast(self, message, duration=None):
        self.label.setText(message)
        self.show()
        if duration:
            QTimer.singleShot(duration, self.hide)

# ==========================================
# 5. SIGNAL BRIDGE & CONTROLLER
# ==========================================
class HotkeyBridge(QObject):
    f8_pressed = pyqtSignal()
    f9_pressed = pyqtSignal()
    # NEW: Signal to force close/collapse the overlay globally
    force_hide_triggered = pyqtSignal() 

class AppController(QObject):
    def __init__(self):
        super().__init__()
        self.overlay = TacTiQOverlay() 
        self.toast = ToastNotification() 
        self.worker = GeminiWorker()
        
        self.worker.finished_signal.connect(self.on_api_finished)
        self.worker.error_signal.connect(self.on_api_error)

        self.bridge = HotkeyBridge()
        self.bridge.f8_pressed.connect(self.take_screenshot_and_analyze)
        self.bridge.f9_pressed.connect(self.overlay.toggle_overlay)
        self.bridge.force_hide_triggered.connect(self.handle_force_hide)

        print("TacTiQ running... F8: Capture | F9: Toggle Overlay | Esc/Alt+Tab: Hide/PiP")
        
        # Globally bind hotkeys to our signals
        keyboard.add_hotkey('f8', self.bridge.f8_pressed.emit)
        keyboard.add_hotkey('f9', self.bridge.f9_pressed.emit)
        keyboard.add_hotkey('esc', self.bridge.force_hide_triggered.emit)
        keyboard.add_hotkey('alt+tab', self.bridge.force_hide_triggered.emit)

    def handle_force_hide(self):
        """Forces the overlay to hide or collapse into PiP instantly"""
        if self.overlay.isVisible() and not self.overlay.is_pip_mode:
            if self.overlay.playing_video_view:
                self.overlay.collapse_to_pip()
            else:
                self.overlay.hide()

    def take_screenshot_and_analyze(self):
        if self.worker.isRunning(): return 
        self.toast.show_toast("TacTiQ: Capturing & Analyzing...", duration=None)
        self.worker.start()

    def on_api_finished(self, tips, analysis, urls):
        self.overlay.update_parameters(tips, analysis, urls)
        self.toast.show_toast("TacTiQ Intel Ready. Press F9.", duration=4000)

    def on_api_error(self, error_msg):
        self.toast.show_toast(f"Error: {error_msg}", duration=4000)

if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    controller = AppController()
    sys.exit(app.exec())