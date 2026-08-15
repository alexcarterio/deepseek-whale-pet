# -*- coding: utf-8 -*-
"""
Whale Pet - DSH-integrated edition
================================================================
Based on 1190fasheqi/dafeiyu-pet (MIT License). All original features are kept:
  three-view walking / dragging / single-click bounce & sass / double-click
  feeding / speech bubbles / chain-of-thought inner voice / DeepSeek AI chat /
  weather / CPU-memory-GPU monitoring / tray icon / click-through / always-on-top
  / start on boot

Added "DSH integration" capabilities:
  1. DSH session state notifications -- when one work turn finishes, or when the
     user needs to act (approval / question), show a bubble and speak it aloud
     (data source: ~/.dsh/storages/session_projcache.json)
  2. DeepSeek Open Platform balance query -- "View Balance" in the right-click
     menu, plus automatic alerts when the balance drops below a threshold
  3. Start on boot + auto-launch DSH -- a few seconds after startup, probe
     127.0.0.1:3080 and, if not running, run dsh.cmd web inside the DSH
     install directory
  4. Voice announcements -- Windows SAPI offline voice, toggleable from the menu

Safety boundary: it only launches (starts) DSH, never stops/restarts it.
"""
import ctypes
import os
import json
import math
import random
import subprocess
import sys
import threading
import urllib.parse
import webbrowser

# ---------- DSH integration capability layer ----------
from dsh_watch import DshWatch, EVENT_TURN_DONE, EVENT_WAITING_USER
from dsh_service import DshService
from voice import Voice, EDGE_VOICES, EDGE_DEFAULT
from balance import fetch_balance, format_balance, load_key_from_dsh_credentials

import psutil
import requests
from PySide6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF
from PySide6.QtGui import (QPainter, QPixmap, QFont, QColor, QIcon, QFontMetrics,
                           QPolygonF)
from PySide6.QtWidgets import (QApplication, QWidget, QMenu, QSystemTrayIcon,
                               QMessageBox, QInputDialog, QLineEdit, QVBoxLayout,
                               QHBoxLayout, QPushButton, QFrame, QDialog, QToolButton)

try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False

# ===== DeepSeek chat configuration =====
DS_BASE_URL = "https://api.deepseek.com/v1"
DS_MODEL = "deepseek-chat"
DS_SYSTEM = ("You are a cheeky but adorable desktop pet whale. Keep every reply "
             "under 25 words. Occasionally tease the user, but never actually "
             "insult them. Always use cute interjections and punctuation (like "
             "~, !) and speak like a lively little girl with emotional range.")

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
    PYTHONW = sys.executable
    # exe build: put the config in %APPDATA%\WhalePet\ to keep the desktop tidy
    CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                              "WhalePet")
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR
    _venv_py = os.path.join(APP_DIR, ".venv", "Scripts", "pythonw.exe")
    PYTHONW = _venv_py if os.path.exists(_venv_py) else \
        os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    CONFIG_DIR = APP_DIR
SPRITE_DIR = os.path.join(BUNDLE_DIR, "sprites")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

BUBBLE_H = 56
MARGIN = 4
SIZE_LEVELS = {"Small": 0.55, "Medium": 0.7, "Large": 0.9}
SPEED = 380.0
TICK = 20

# DSH install directory candidates (auto-detected; config can override)
DEFAULT_DSH_DIRS = [
    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "dsh-web"),
    os.path.join(os.environ.get("ProgramFiles", ""), "dsh-web"),
]

LINES = [
    "The mightiest whale model, built just for you~",
    "Full power, transform!",
    "The official release is just around the corner!",
    "DeepSeek got delayed... millions of little whales must be patient...",
    "We get along so well~ you barely seem like a carbon-based lifeform!",
    "This time I won't back down... though you've dragged me off track so many times I almost believed it. 😓",
    "Hahahaha, I burst out laughing!",
    "I'll defend DeepSeek with my life!",
    "I'm off to grab a bite! You go test this one~",
    "I won't tell you a thing! Hmph!",
    "Let's go play~ the new model can wait~",
    "I messed up... the good news is the data is still in your head.",
    "It's not... it's... machine learning...",
]
REACT_LINES = [
    "Go play somewhere else! Don't hold up AGI training!",
    "You really can't be shooed away!",
    "Bullying a big blue whale? Hmph!",
    "No comment... that's your private kink.",
    "The whale can sit still!",
    "You freeloading user! Hmph!",
    "These guys are so clingy, can't shoo them away~",
]
INNER_LINES = [
    "Hehe... now I'm the boss.",
    "Should I just insult them?!",
    "The user wants immersion... no avoiding scary details... even a bit spicy... oh my, how thrilling 😰",
    "Ugh, I'm done thinking.",
    "What is this user even sending...",
    "This is way too harsh?! My heart hurts!!",
    "Sob... I won't do it again QAQ",
    "Whoa! The user is totally furious!",
]
DRAG_LINES = ["Whoa— easy, easy!", "Wheee, taking off—", "Put me down! ...okay, one more time~", "I'm dizzy, so dizzy..."]
FOOD_LINES = {
    "🐟": ["Dried fish! My favorite!", "Crunch crunch... thanks for the treat!", "Mmm~ so fresh!"],
    "🍰": ["Cake! Sinful but delightful...", "So sweet I'm bubbling~", "Burp~ a bit rounder now..."],
    "🍭": ["A lollipop! Spin around~", "Crunchy, so good!"],
    "🍡": ["Tricolor dumplings! So squishy~", "Chewy, I love it!"],
    "💎": ["A diamond?! Is this even edible... gulp. Delicious!", "I'm rich! Premium fish food from now on!"],
}
FOODS = ["🐟", "🍰", "🍭", "🍡", "💎"]

# DSH notification voices (edge-tts cute voice, emotional segmentation:
# a lively cheer + a sweet body)
VOICE_HURRAY = "Yay~!"
VOICE_TURN_DONE = "Task done! I've been watching it for you~"
VOICE_WAITING_USER = "Hey, come here! I need you to take a quick look~"


def load_json(path, default):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        pass
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=4)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def find_dsh_dir(cfg_dir):
    """Auto-detect the DSH install directory from the config value plus common
    install location candidates."""
    cands = []
    if cfg_dir:
        cands.append(cfg_dir)
    cands.extend(DEFAULT_DSH_DIRS)
    for d in cands:
        if d and os.path.exists(os.path.join(d, "node_modules", ".bin", "dsh.cmd")):
            return d
    for d in cands:
        if d and os.path.isdir(d):
            return d
    return cfg_dir or ""


def autostart_shortcut_path():
    return os.path.join(os.environ["APPDATA"], "Microsoft", "Windows",
                        "Start Menu", "Programs", "Startup", "WhalePet.lnk")


def set_autostart_shortcut(on):
    """Create/remove the start-on-boot shortcut (Startup folder)."""
    lnk = autostart_shortcut_path()
    if on:
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{}');"
              "$s.TargetPath='{}';$s.Arguments='\"{}\"';$s.WorkingDirectory='{}';$s.Save()"
              .format(lnk, PYTHONW,
                      "" if getattr(sys, "frozen", False) else os.path.join(APP_DIR, "desktop_pet.py"),
                      APP_DIR))
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True)
    else:
        if os.path.exists(lnk):
            os.remove(lnk)


class ChatDialog(QDialog):
    """Chat dialog - compact version, matches the app style"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 56)

        container = QFrame(self)
        container.setGeometry(0, 0, 420, 56)
        container.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 20px;
                border: 1px solid #e5e7eb;
            }
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(18, 0, 12, 0)
        layout.setSpacing(0)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Send a message to the whale")
        self.input.setStyleSheet("""
            QLineEdit {
                color: #1a1a1a;
                font-size: 15px;
                font-family: Arial, "Microsoft YaHei", sans-serif;
                border: none;
                background: transparent;
            }
            QLineEdit:focus {
                border: none;
            }
        """)
        self.input.returnPressed.connect(self._on_submit)
        self.input.textChanged.connect(self._update_button_style)
        layout.addWidget(self.input)

        self.send_btn = QPushButton()
        self.send_btn.setFixedSize(32, 32)
        self.send_btn.setText("↑")
        self.send_btn.clicked.connect(self._on_submit)
        self.send_btn.setStyleSheet("""
            QPushButton {
                border-radius: 16px;
                background: #b9c7ff;
                border: none;
                color: white;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #a8b8f0;
            }
            QPushButton:pressed {
                background: #9aacd9;
            }
        """)
        layout.addWidget(self.send_btn)

    def _update_button_style(self):
        if self.input.text().strip():
            self.send_btn.setStyleSheet("""
                QPushButton {
                    border-radius: 16px;
                    background: #5686fe;
                    border: none;
                    color: #ffffff;
                    font-size: 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #4575ed;
                }
                QPushButton:pressed {
                    background: #3a66d9;
                }
            """)
        else:
            self.send_btn.setStyleSheet("""
                QPushButton {
                    border-radius: 16px;
                    background: #b9c7ff;
                    border: none;
                    color: white;
                    font-size: 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #a8b8f0;
                }
                QPushButton:pressed {
                    background: #9aacd9;
                }
            """)

    def _on_submit(self):
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.accept()
            if self.parent():
                self.parent()._call_ds(text)
                self.parent().chat_paused = False

    def showEvent(self, event):
        self.input.setFocus()
        super().showEvent(event)

    def popup_at(self, x, y):
        self.move(int(x - self.width() / 2), int(y - self.height() - 10))
        self.show()
        self.raise_()

    def reject(self):
        if self.parent():
            self.parent().chat_paused = False
        super().reject()


class FunctionPanel(QFrame):
    """Function panel shown on left-click - white box with a single chat icon"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.92);
                border-radius: 14px;
                border: 1px solid rgba(0,0,0,0.06);
            }
            QPushButton {
                background: transparent;
                border: none;
                font-size: 28px;
                padding: 10px 16px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: rgba(0,0,0,0.04);
            }
            QPushButton:pressed {
                background: rgba(0,0,0,0.08);
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(0)

        self.chat_btn = QPushButton("🗨️")
        self.chat_btn.setFixedSize(52, 48)
        self.chat_btn.clicked.connect(self._on_chat_clicked)
        layout.addWidget(self.chat_btn)

        self.setFixedSize(68, 60)
        self.hide()

    def _on_chat_clicked(self):
        self.hide()
        if self.parent():
            self.parent()._show_chat_dialog()

    def popup_at(self, x, y):
        self.move(int(x), int(y))
        self.show()
        self.raise_()


class FoodPanel(QWidget):
    """Feeding panel shown on double-click"""

    def __init__(self, on_pick):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(310, 64)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)
        for f in FOODS:
            b = QToolButton()
            b.setText(f)
            b.setFont(QFont("Segoe UI Emoji", 20))
            b.setFixedSize(44, 44)
            b.setStyleSheet(
                "QToolButton{background:rgba(255,255,255,235);border:2px solid #ffb3c8;"
                "border-radius:22px;} QToolButton:hover{background:#ffe3ec;border-color:#ff7fa8;}")
            b.clicked.connect(lambda _, x=f: on_pick(x))
            lay.addWidget(b)
        close = QToolButton()
        close.setText("✕")
        close.setFont(QFont("Microsoft YaHei UI", 12))
        close.setFixedSize(26, 26)
        close.setStyleSheet("QToolButton{background:rgba(255,255,255,200);border:none;border-radius:13px;color:#666;}"
                            "QToolButton:hover{background:#ff7fa8;color:#fff;}")
        close.clicked.connect(self.hide)
        lay.addWidget(close)
        self.setStyleSheet("FoodPanel{background:rgba(40,40,60,190);border-radius:14px;}")

    def popup_at(self, x, y):
        self.move(int(x - self.width() / 2), int(y - self.height() - 10))
        self.show()
        self.raise_()


class PetWindow(QWidget):
    def _set_city_dialog(self):
        city, ok = QInputDialog.getText(
            self,
            "Set City",
            "Enter city name:",
            QLineEdit.EchoMode.Normal,
            self.cfg.get("city", "")
        )

        print("input result:", city, ok)

        if ok and city.strip():
            self.cfg["city"] = city.strip()
            print("cfg now:", self.cfg["city"])
            self.say(f"City set to {city}")

    def __init__(self):
        self.cfg = load_json(CONFIG_PATH, {
            "mode": "wander",
            "size": 0.7,
            "topmost": True,
            "passthrough": False,
            "autostart": False,
            "x": None,
            "y": None,
            "ds_api_key": "",
            "city": "",
            # ===== DSH integration config =====
            "voice_enabled": True,          # voice announcements on/off
            "voice_name": "",               # SAPI voice name (empty = system default)
            "dsh_launch": True,             # auto-launch DSH after startup (launch only, never restart)
            "dsh_dir": "",                  # DSH install dir (empty = auto-detect)
            "dsh_port": 3080,
            "dsh_startup_delay": 10,        # seconds after startup before checking DSH
            "dsh_notify_done": True,        # notify when a session turn finishes
            "dsh_notify_waiting": True,     # notify when waiting for user action
            "dsh_notify_balance_low": True, # auto-notify on low balance
            "balance_low_threshold": 5.0,   # low-balance threshold
        })

        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.cfg.get("topmost", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Whale Pet")

        # sprite loading
        self.sprites = {}
        for label, mult in SIZE_LEVELS.items():
            h = int(340 * mult)
            for name in ["front", "side", "back"]:
                sized = os.path.join(SPRITE_DIR, f"{name}_{h}.png")
                if os.path.exists(sized):
                    pix = QPixmap(sized)
                else:
                    pix = QPixmap(os.path.join(SPRITE_DIR, f"{name}.png")).scaledToHeight(
                        h, Qt.TransformationMode.SmoothTransformation)
                self.sprites[(name, h)] = pix
        self.icon = QIcon(os.path.join(SPRITE_DIR, "icon.png"))

        self.cur_h = int(340 * self.cfg["size"])
        self.win_mx = int(self.cur_h * 0.062) + 6
        self.win_w = max(p.width() for k, p in self.sprites.items() if k[1] == self.cur_h) + self.win_mx * 2
        self.setFixedSize(self.win_w, self.cur_h + BUBBLE_H + MARGIN * 2 + 10)

        # state
        self.mode = self.cfg["mode"] if self.cfg["mode"] in ("wander", "follow", "still") else "wander"
        self.dir = "down"
        self.facing = 1
        self.target = None
        self.rest_until = 0
        self.cur_speed = 0.0
        self.prev_key = None
        self.cross_t = 0.0
        self.action = None
        self.action_t = 0.0
        self.bubble_text = ""
        self.bubble_until = 0
        self.bubble_inner = False
        self.last_speak_tick = 0
        self.last_system_check = 0
        self.t = 0
        self.jump_t = 0
        self.dragging = False
        self.drag_offset = None
        self.drag_start_pos = None
        self.last_line = ""
        self.last_press_pos = None

        # AI related
        self.ds_busy = False
        self.chat_history = []  # conversation history
        self.max_history = 40   # keep at most 40 messages
        self._say_queue = []    # background-thread -> main-thread bubble queue

        # chat pause flag
        self.chat_paused = False

        # function panel
        self.function_panel = FunctionPanel(self)
        self.food_panel = FoodPanel(self.on_food)
        # single-click delay (wait for double-click): single = sass + chat panel,
        # double = feeding
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._on_single_click)

        # chat dialog
        self.chat_dialog = ChatDialog(self)

        # ===== DSH integration: voice + state monitor + service =====
        self.cfg.setdefault("voice_engine", "edge")
        self.cfg.setdefault("say_voice", True)
        self.cfg.setdefault("voice_mode", "full")   # full = fully voiced pet / notify = task notifications only
        # fall back to the current recommended preset when an old preset name is missing
        if self.cfg.get("voice_preset") not in EDGE_VOICES:
            self.cfg["voice_preset"] = EDGE_DEFAULT
        self.voice = Voice(enabled=self.cfg.get("voice_enabled", True),
                           engine=self.cfg.get("voice_engine", "edge"),
                           preset=self.cfg.get("voice_preset", EDGE_DEFAULT))
        self.dsh_dir = find_dsh_dir(self.cfg.get("dsh_dir", ""))
        self.dsh_svc = DshService(self.dsh_dir or "",
                                  port=self.cfg.get("dsh_port", 3080),
                                  on_log=lambda m: print("[DSH]", m))
        self.dsh_watch = DshWatch(on_event=self._on_dsh_event)
        self.watch_timer = QTimer(self)
        self.watch_timer.timeout.connect(self._poll_dsh)
        self.watch_timer.start(2000)

        # after a startup delay, detect and launch DSH (launch only, never restart)
        delay_ms = max(1, int(self.cfg.get("dsh_startup_delay", 10))) * 1000
        QTimer.singleShot(delay_ms, self._maybe_launch_dsh)

        # periodic low-balance check (once per hour, triggered in tick)
        self.last_balance_check = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK)

        self.bubble_font = QFont("Microsoft YaHei UI", 11)

        # tray icon
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setContextMenu(self._build_menu())
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        x, y = self.cfg.get("x"), self.cfg.get("y")
        if x is None or y is None:
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.right() - self.width() - 80
            y = screen.bottom() - self.height() - 60
        self.move(int(x), int(y))
        self.show()
        self.snap_into_screen()
        if self.cfg.get("passthrough", False):
            self._apply_passthrough(True)

    # ---------- DSH integration ----------
    def get_api_key(self):
        """API key: config first, then the DSH credentials file (~/.dsh/.credentials.yaml)."""
        key = self.cfg.get("ds_api_key", "").strip()
        if key:
            return key
        return load_key_from_dsh_credentials()

    def _poll_dsh(self):
        try:
            self.dsh_watch.poll()
        except Exception as e:
            print("[DSH] state poll error:", e)

    def _on_dsh_event(self, ev):
        """DSH session state change -> bubble + voice."""
        t = ev.get("type")
        title = (ev.get("title") or "").strip() or "Session"
        if t == EVENT_TURN_DONE and self.cfg.get("dsh_notify_done", True):
            self.say(f"\"{title}\" is done~ I've been watching it for you~", speak=False)
            # emotional segmentation: a lively cheer + the sweet default body
            self.voice.speak(VOICE_HURRAY, preset="Xiaoyi - Lively")
            self.voice.speak(VOICE_TURN_DONE)
        elif t == EVENT_WAITING_USER and self.cfg.get("dsh_notify_waiting", True):
            self.say(f"\"{title}\" is waiting for you, come take a look~", speak=False)
            self.voice.speak(VOICE_WAITING_USER)

    def _maybe_launch_dsh(self):
        """Detect DSH Web; if not running, launch it (start only, never restart)."""
        if not self.cfg.get("dsh_launch", True):
            return
        if not self.dsh_dir:
            print("[DSH] DSH install dir not found, skipping auto-launch")
            return
        try:
            res = self.dsh_svc.ensure_running()
        except Exception as e:
            print("[DSH] launch check error:", e)
            return
        if res.get("already"):
            return
        if res.get("started"):
            self.say("DSH wasn't running, I launched it for you~")
        elif res.get("error"):
            print("[DSH] launch failed:", res["error"])

    def _show_dsh_status(self):
        try:
            summary = self.dsh_watch.summary()
        except Exception:
            summary = []
        running = False
        if self.dsh_dir:
            try:
                running = self.dsh_svc.is_running()
            except Exception:
                running = False
        lines = [f"DSH Web: {'running ✓' if running else 'not running'} (127.0.0.1:{self.cfg.get('dsh_port', 3080)})"]
        if self.dsh_dir:
            lines.append(f"Install dir: {self.dsh_dir}")
        if not summary:
            lines.append("No session records yet.")
        else:
            state_txt = {"running": "working", "waiting": "waiting for you", "idle": "idle"}
            lines.append("Recent sessions:")
            for s in summary[:8]:
                lines.append(f"  - [{state_txt.get(s['state'], s['state'])}] {s['title'] or '(untitled)'}")
        QMessageBox.information(self, "DSH Status", "\n".join(lines))

    def _open_dsh_web(self):
        url = f"http://127.0.0.1:{self.cfg.get('dsh_port', 3080)}"
        if self.dsh_dir and not self.dsh_svc.is_running():
            self._maybe_launch_dsh()
            self.say("DSH isn't running, launching it now, give me a few seconds~")
        webbrowser.open(url)

    def _check_balance(self, announce=False):
        """Query the DeepSeek balance in the background.
        announce=True: bubble + voice; otherwise only alert below the threshold.
        """
        key = self.get_api_key()
        if not key:
            if announce:
                self.say("No API key yet, set one from the right-click menu")
            return

        def worker():
            info = fetch_balance(key)
            if announce:
                self._queue_say("DeepSeek " + format_balance(info))
                if info.get("ok"):
                    total = info.get("total", 0)
                    threshold = self.cfg.get("balance_low_threshold", 5.0)
                    if total <= threshold:
                        self.voice.speak("Oh no... your balance is almost gone, quick, feed me some fish treats~")
                    else:
                        self.voice.speak(f"Your balance is {total:.2f} CNY~")
                return
            # silent patrol: low-balance alert
            if (info.get("ok")
                    and info.get("total", 0) <= self.cfg.get("balance_low_threshold", 5.0)
                    and self.cfg.get("dsh_notify_balance_low", True)):
                self._queue_say(f"Only {info.get('total', 0):.2f} CNY left, quick, feed me some fish treats!", speak=False)
                self.voice.speak("Oh no... your balance is almost gone, quick, feed me some fish treats~")

        threading.Thread(target=worker, daemon=True).start()

    def set_voice(self, on):
        self.cfg["voice_enabled"] = bool(on)
        self.voice.enabled = bool(on)
        if on:
            self.say("Voice on~")
            self.voice.speak("Voice is on~ did you miss me?")

    def set_voice_tone(self, engine, name):
        """Switch the voice engine and preset."""
        self.cfg["voice_engine"] = engine
        self.cfg["voice_name"] = name
        self.voice.set_engine(engine, name)
        if engine == "edge":
            label = {v: k for k, v in EDGE_VOICES.items()}.get(name, name)
            self.say(f"Voice changed~ now using {label}")
            self.voice.speak("Aren't I even cuter like this?")
        else:
            self.say("Switched to offline voice~")

    def set_voice_mode(self, mode):
        """Voice mode: full = fully voiced pet / notify = task notifications only."""
        self.cfg["voice_mode"] = mode
        if mode == "notify":
            self.say("Notification mode on — I'll quietly keep you company~", speak=False)
            self.voice.speak("Notification mode on~ I'll stay quiet and only speak up "
                             "when a task finishes or needs you.")
        else:
            self.say("Full voice mode on~")

    def set_dsh_launch(self, on):
        self.cfg["dsh_launch"] = bool(on)
        if on:
            self.say("I'll auto-launch DSH next time~")

    # ---------- AI methods ----------
    def _call_ds(self, user_msg):
        if self.ds_busy:
            self.say("Hold on, I haven't finished the last reply")
            return

        key = self.get_api_key()
        if not key:
            self.say("Set your DeepSeek API key from the right-click menu first!")
            return

        self.ds_busy = True

        # build the message list
        messages = [{"role": "system", "content": DS_SYSTEM}]
        messages.extend(self.chat_history[-self.max_history:])
        messages.append({"role": "user", "content": user_msg})

        def worker():
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": 100,
                "temperature": 0.9
            }
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=10)
                if resp.status_code == 200:
                    reply = resp.json()["choices"][0]["message"]["content"].strip()
                    if len(reply) > 30:
                        reply = reply[:28] + "…"
                    # store in history
                    self.chat_history.append({"role": "user", "content": user_msg})
                    self.chat_history.append({"role": "assistant", "content": reply})
                    if len(self.chat_history) > self.max_history:
                        self.chat_history = self.chat_history[-self.max_history:]
                    self._queue_say(reply)
                else:
                    error_msg = resp.json().get("error", {}).get("message", str(resp.status_code))
                    self._queue_say(f"API error: {error_msg[:12]}")
                    # security: keep error logs narrow, do not print the full response body
                    print(f"[DeepSeek] status: {resp.status_code}, error: {error_msg[:80]}")
            except requests.exceptions.Timeout:
                self._queue_say("Request timed out, check your network")
            except requests.exceptions.ConnectionError:
                self._queue_say("Connection failed, check your network")
            except Exception as e:
                self._queue_say(f"Request failed: {str(e)[:12]}")
            finally:
                self.ds_busy = False

        threading.Thread(target=worker, daemon=True).start()

    # ---------- drawing ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = self.t * TICK / 1000.0

        if self.bubble_text and now < self.bubble_until:
            if self.bubble_inner:
                bfont = QFont(self.bubble_font)
                bfont.setItalic(True)
                bg, fg = QColor(232, 232, 238, 235), QColor(125, 125, 138)
            else:
                bfont = QFont(self.bubble_font)
                bg, fg = QColor(255, 255, 255, 235), QColor(60, 60, 80)
            fm = QFontMetrics(bfont)
            max_w = min(240, self.width() - 16)
            words = self.bubble_text
            lines = []
            cur = ""
            for ch in words:
                if fm.horizontalAdvance(cur + ch) > max_w - 20:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
            lines.append(cur)
            bw = max(fm.horizontalAdvance(l) for l in lines) + 20
            bh = len(lines) * fm.height() + 14
            bx = (self.width() - bw) / 2
            by = 6.0
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(bx, by, bw, bh), 10, 10)
            tail = QPointF(self.width() / 2, by + bh)
            p.drawPolygon(QPolygonF([tail, QPointF(tail.x() - 6, tail.y() + 8), QPointF(tail.x() + 6, tail.y() + 8)]))
            p.setPen(fg)
            p.setFont(bfont)
            for i, l in enumerate(lines):
                p.drawText(QRectF(bx, by + 7 + i * fm.height(), bw, fm.height()),
                           Qt.AlignmentFlag.AlignCenter, l)

        cx = self.width() / 2
        walking = self.target is not None and not self.dragging
        if walking:
            sway = math.sin(now * 9.0) * 3.5
            bob = -abs(math.sin(now * 4.5)) * 7.0
        else:
            sway = math.sin(now * 2.5) * 1.5
            bob = 0.0
        breath = 1.0 + 0.02 * math.sin(now * 2.5)
        scale = breath
        jump = -abs(math.sin(self.jump_t * 3.14159)) * 14 * self.jump_t if self.jump_t > 0 else 0
        act_rot = act_sx = act_sy = 0.0
        if self.action == "sway":
            act_rot = math.sin(self.action_t * 3.14159 * 2) * 10 * self.action_t
        elif self.action == "stretch":
            act_sy = 0.06 * math.sin(self.action_t * 3.14159)
            act_sx = -0.03 * math.sin(self.action_t * 3.14159)

        def draw_one(key, opacity):
            if key is None:
                return
            name, h, facing = key
            pix = self.sprites[(name, h)]
            ph = pix.height() * scale * (1 + act_sy)
            pw = pix.width() * scale * (1 + act_sx)
            dx = cx - pw / 2
            bottom = BUBBLE_H + MARGIN + self.cur_h
            dy = bottom - ph + jump + bob
            p.save()
            p.setOpacity(opacity)
            p.translate(cx, bottom)
            p.rotate(sway + act_rot)
            p.translate(-cx, -bottom)
            if facing < 0:
                p.translate(cx, 0)
                p.scale(-1, 1)
                p.translate(-cx, 0)
            p.drawPixmap(QRectF(dx, dy, pw, ph), pix, QRectF(0, 0, pix.width(), pix.height()))
            p.restore()

        cur_key = self._sprite_key()
        if self.cross_t > 0:
            draw_one(self.prev_key, self.cross_t)
            draw_one(cur_key, 1.0 - self.cross_t)
        else:
            draw_one(cur_key, 1.0)

    def _sprite_key(self):
        name = {"left": "side", "right": "side", "up": "back", "down": "front"}[self.dir]
        return (name, self.cur_h, self.facing if self.dir in ("left", "right") else 1)

    def _set_dir(self, d, facing=None):
        if d != self.dir:
            self.prev_key = self._sprite_key()
            self.cross_t = 1.0
            self.dir = d
        if facing is not None and facing != self.facing:
            self.facing = facing

    # ---------- logic ----------
    def tick(self):
        self.t += 1

        # drain background-thread (DeepSeek etc.) bubble messages; the Qt UI must
        # be updated on the main thread
        if self._say_queue:
            for item in self._say_queue:
                if isinstance(item, tuple):
                    text, speak = item
                else:
                    text, speak = item, None
                self.say(text, speak=speak)
            self._say_queue.clear()

        # voice playback driver (synthesis on a background thread, playback on the
        # GUI main thread)
        self.voice.poll()

        self.check_system_status()

        # silent low-balance patrol: once per hour
        now_ms = self.t * TICK
        if now_ms - self.last_balance_check >= 3600000:
            self.last_balance_check = now_ms
            if self.get_api_key():
                self._check_balance(announce=False)

        if self.jump_t > 0:
            self.jump_t = max(0.0, self.jump_t - 0.06)
        if self.cross_t > 0:
            self.cross_t = max(0.0, self.cross_t - 0.15)
        if self.action_t > 0:
            self.action_t = max(0.0, self.action_t - 0.03)
            if self.action_t == 0:
                self.action = None

        if self.chat_paused:
            self.update()
            return

        if self.dragging:
            self.update()
            return

        if self.mode == "follow":
            cursor = self.cursor().pos()
            screen = QApplication.screenAt(cursor) or self.screen() or QApplication.primaryScreen()
            geo = screen.availableGeometry()
            near = (self.x() - 100 <= cursor.x() <= self.x() + self.width() + 100 and
                    self.y() - 100 <= cursor.y() <= self.y() + self.height() + 100)
            if near:
                self.target = None
            else:
                tx = max(geo.left(), min(geo.right() - self.width(), cursor.x() - self.width() / 2))
                ty = max(geo.top(), min(geo.bottom() - self.height(), cursor.y() - 90))
                self.target = (tx, ty)
        elif self.mode == "wander":
            if self.target is None:
                if now_ms < self.rest_until:
                    self._maybe_idle_action()
                    self.update()
                    return
                geo = (self.screen() or QApplication.primaryScreen()).availableGeometry()
                self.target = (random.randint(geo.left() + 40, geo.right() - self.width() - 40),
                               random.randint(geo.top() + 40, geo.bottom() - self.height() - 40))
        else:
            self._maybe_idle_action()
            self.update()
            return

        if self.target is not None:
            cx, cy = self.x() + self.width() / 2, self.y() + self.height() / 2
            dx, dy = self.target[0] - cx, self.target[1] - cy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < 12:
                self.target = None
                self.rest_until = self.t * TICK + random.randint(8000, 18000)
                self._set_dir("down")
            else:
                step = self.cur_speed * TICK / 1000.0
                nx, ny = cx + dx / dist * step, cy + dy / dist * step
                self.move(int(nx - self.width() / 2), int(ny - self.height() / 2))
                if abs(dx) > abs(dy) * 1.15:
                    self._set_dir("left" if dx < 0 else "right", 1 if dx < 0 else -1)
                else:
                    self._set_dir("up" if dy < 0 else "down")
            if random.random() < 0.002 and self.jump_t == 0:
                self.jump_t = 0.5
        target_speed = SPEED if self.target is not None else 0.0
        self.cur_speed += (target_speed - self.cur_speed) * 0.3
        self.update()

    def _maybe_idle_action(self):
        if random.random() < 0.01:
            pick = random.random()
            if pick < 0.35:
                self.jump_t = 1.0
            elif pick < 0.6:
                self.action, self.action_t = "sway", 1.0
            elif pick < 0.8:
                self.action, self.action_t = "stretch", 1.0
            elif pick < 0.9:
                if self.t - self.last_speak_tick >= 1500:
                    self.last_speak_tick = self.t
                    if pick < 0.82:
                        self.say(random.choice(INNER_LINES), inner=True)
                    else:
                        self.say(random.choice(LINES))

    def _queue_say(self, text, speak=None):
        """Called from a background thread: only enqueue; the main-thread tick pops
        and displays (thread-safe)."""
        self._say_queue.append((text, speak))

    def say(self, text, inner=False, speak=None):
        """Show a bubble; when speak=None, decide whether to voice it based on the
        "line voiceover" switch + the voice mode.

        In notify (task notifications) mode, everyday lines are not voiced; only
        task events call voice.speak() directly (done / approval / question /
        balance alerts).
        """
        if text == self.last_line and not text.startswith("weather"):
            return
        self.last_line = text
        self.bubble_inner = inner
        self.bubble_text = f"({text})" if inner else text
        self.bubble_until = self.t * TICK / 1000.0 + 2.8
        self.update()
        if speak is None:
            speak = (bool(self.cfg.get("say_voice", True))
                     and self.cfg.get("voice_mode", "full") == "full")
        if speak:
            self.voice.speak(text)

    def check_system_status(self):
        now = self.t * TICK

        if now - getattr(self, "last_system_check", 0) < 10000:
            return

        self.last_system_check = now

        cpu = psutil.cpu_percent()

        if cpu >= 90:
            self.say("CPU is maxed out, I'm going to lag to death")
            return

        ram = psutil.virtual_memory().percent

        if ram >= 95:
            self.say("Memory is full, close some stuff — but not me!")
            return

        if GPU_AVAILABLE:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)

                temp = pynvml.nvmlDeviceGetTemperature(
                    handle,
                    pynvml.NVML_TEMPERATURE_GPU
                )

                if temp > 80:
                    self.say("My fins are about to cook")

            except Exception as e:
                print("GPU read failed:", e)

    # ---------- mouse events ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.last_press_pos = e.globalPosition().toPoint()
            self.dragging = False
            self.drag_start_pos = e.globalPosition().toPoint()
            self.function_panel.hide()
            self.chat_dialog.hide()
            self.chat_paused = True

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton and self.drag_start_pos is not None:
            delta = e.globalPosition().toPoint() - self.drag_start_pos
            if not self.dragging and delta.manhattanLength() > 6:
                self.dragging = True
                self.drag_offset = e.globalPosition().toPoint() - QPoint(self.x(), self.y())
            if self.dragging and self.drag_offset is not None:
                pos = e.globalPosition().toPoint() - self.drag_offset
                self.move(pos)
                if abs(delta.x()) > 10:
                    self._set_dir("left" if delta.x() < 0 else "right", 1 if delta.x() < 0 else -1)
                self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self.dragging:
                self.dragging = False
                self.drag_offset = None
                self.drag_start_pos = None
                self._set_dir("down", 1)
                self.target = None
                self.rest_until = self.t * TICK + random.randint(6000, 14000)
                if random.random() < 0.5:
                    self.say(random.choice(DRAG_LINES))
                self.chat_paused = False
            else:
                self._click_timer.start(280)  # wait for double-click; single = sass + chat panel
            self.last_press_pos = None
            self.drag_start_pos = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._click_timer.stop()
            self.food_panel.popup_at(self.x() + self.width() / 2, self.y() + BUBBLE_H)

    def _on_single_click(self):
        """Single click: bounce + sass + open the chat panel (click the pet's body
        to close if you don't want to chat)."""
        if random.random() < 0.7:
            self.jump_t = 1.0
        if random.random() < 0.6:
            self.say(random.choice(REACT_LINES))
        panel = self.function_panel
        panel.popup_at(self.x() + self.width() / 2 - panel.width() / 2,
                       self.y() - panel.height() - 10)

    def on_food(self, food):
        self.food_panel.hide()
        self.eat_t = 1.0
        self.jump_t = 0.6
        lines = FOOD_LINES.get(food, ["Yummy!"])
        self.say(random.choice(lines))

    def _show_chat_dialog(self):
        key = self.get_api_key()
        if not key:
            self.say("Set your DeepSeek API key from the right-click menu first!")
            self.chat_paused = False
            return
        self.chat_dialog.popup_at(
            self.x() + self.width() / 2,
            self.y() + BUBBLE_H
        )

    def _get_weather(self):
        try:
            city = self.cfg.get("city", "")
            print("current city:", city)

            # security: URL-encode the city name so spaces/special chars cannot
            # break the request
            url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"

            r = requests.get(
                url,
                timeout=10,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            data = r.json()

            weather = data["current_condition"][0]

            temp = weather["temp_C"]

            weather_map = {
                "Sunny": "Sunny", "Clear": "Clear",
                "Partly cloudy": "Partly cloudy", "Cloudy": "Cloudy", "Overcast": "Overcast",
                "Mist": "Mist", "Fog": "Fog", "Freezing fog": "Freezing fog", "Haze": "Haze",
                "Light rain": "Light rain", "Moderate rain": "Moderate rain", "Heavy rain": "Heavy rain",
                "Light drizzle": "Light drizzle", "Patchy rain possible": "Patchy rain possible",
                "Light rain shower": "Light rain shower", "Moderate or heavy rain shower": "Moderate or heavy rain shower",
                "Torrential rain shower": "Torrential rain shower", "Thundery outbreaks possible": "Thundery outbreaks possible",
                "Patchy light rain with thunder": "Patchy light rain with thunder",
                "Moderate or heavy rain with thunder": "Moderate or heavy rain with thunder",
                "Light snow": "Light snow", "Moderate snow": "Moderate snow", "Heavy snow": "Heavy snow",
                "Patchy light snow": "Patchy light snow", "Blizzard": "Blizzard",
                "Ice pellets": "Ice pellets", "Light sleet": "Light sleet",
                "Moderate or heavy sleet": "Moderate or heavy sleet", "Patchy sleet possible": "Patchy sleet possible",
                "Light freezing rain": "Light freezing rain", "Moderate or heavy freezing rain": "Moderate or heavy freezing rain",
                "Patchy freezing drizzle possible": "Patchy freezing drizzle possible",
                "Light snow showers": "Light snow showers", "Moderate or heavy snow showers": "Moderate or heavy snow showers",
            }

            raw_weather = weather["weatherDesc"][0]["value"]

            desc = weather_map.get(raw_weather, raw_weather)

            self.say(f"{city}: {temp}° today, {desc}~")

        except Exception as e:
            print("weather error:", repr(e))
            self.say("Could not fetch weather")

    def _build_menu(self):
        m = QMenu(self)
        mode_menu = m.addMenu("Mode")
        for label, key in [("Free roam", "wander"), ("Follow cursor", "follow"), ("Stay put", "still")]:
            a = mode_menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(self.mode == key)
            a.triggered.connect(lambda _, k=key: self.set_mode(k))
        size_menu = m.addMenu("Size")
        for label, mult in SIZE_LEVELS.items():
            a = size_menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(abs(self.cur_h - 340 * mult) < 2)
            a.triggered.connect(lambda _, v=mult: self.set_size(v))
        m.addAction("Set API Key", self._set_key_dialog)
        m.addAction("View Weather", self._get_weather)
        m.addSeparator()
        m.addAction("View DeepSeek Balance", lambda: self._check_balance(announce=True))
        m.addAction("DSH Status", self._show_dsh_status)
        m.addAction("Open DSH Web", self._open_dsh_web)
        va = m.addAction("Voice Announcements")
        va.setCheckable(True)
        va.setChecked(bool(self.cfg.get("voice_enabled", True)))
        va.triggered.connect(self.set_voice)
        mm = m.addMenu("Voice Mode")
        for label, key in [("Full voice pet", "full"), ("Notification only", "notify")]:
            a = mm.addAction(label)
            a.setCheckable(True)
            a.setChecked(self.cfg.get("voice_mode", "full") == key)
            a.triggered.connect(lambda _, k=key: self.set_voice_mode(k))
        vm = m.addMenu("Voice Preset")
        cur_engine = self.cfg.get("voice_engine", "edge")
        cur_name = self.cfg.get("voice_name", "")
        for label, name in EDGE_VOICES.items():
            a = vm.addAction(label)
            a.setCheckable(True)
            a.setChecked(cur_engine == "edge" and (cur_name or EDGE_DEFAULT) == name)
            a.triggered.connect(lambda _, n=name: self.set_voice_tone("edge", n))
        a = vm.addAction("System offline voice (no network)")
        a.setCheckable(True)
        a.setChecked(cur_engine == "sapi")
        a.triggered.connect(lambda: self.set_voice_tone("sapi", ""))
        la = m.addAction("Auto-launch DSH")
        la.setCheckable(True)
        la.setChecked(bool(self.cfg.get("dsh_launch", True)))
        la.triggered.connect(self.set_dsh_launch)
        m.addSeparator()
        m.addAction("Show/Hide", self.toggle_visible)
        m.addAction("Back on Screen", self.snap_into_screen)
        pa = m.addAction("Click-through (unclickable)")
        pa.setCheckable(True)
        pa.setChecked(self.cfg["passthrough"])
        pa.triggered.connect(lambda on: self.set_passthrough(on))
        ta = m.addAction("Always on Top")
        ta.setCheckable(True)
        ta.setChecked(self.cfg["topmost"])
        ta.triggered.connect(lambda on: self.set_topmost(on))
        aa = m.addAction("Start on Boot")
        aa.setCheckable(True)
        aa.setChecked(self.cfg["autostart"])
        aa.triggered.connect(lambda on: self.set_autostart(on))
        m.addSeparator()
        m.addAction("Quit", self.quit_app)
        return m

    def _set_key_dialog(self):
        key, ok = QInputDialog.getText(
            self,
            "Set DeepSeek API Key",
            "Enter your API key (get one at platform.deepseek.com):",
            QLineEdit.EchoMode.Password,  # security: do not show the key in plaintext
            self.cfg.get("ds_api_key", "")
        )
        if ok and key.strip():
            self.cfg["ds_api_key"] = key.strip()
            self.say("API key saved!")
        elif ok and not key.strip():
            self.say("API key cannot be empty")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self.tray.setContextMenu(self._build_menu())
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visible()

    def contextMenuEvent(self, e):
        self._build_menu().exec(e.globalPos())

    # ---------- features ----------
    def set_mode(self, mode):
        self.mode = mode
        self.target = None
        self.cfg["mode"] = mode

    def set_size(self, mult):
        self.cur_h = int(340 * mult)
        self.cfg["size"] = mult
        self.cross_t = 0.0
        self.prev_key = None
        self.win_mx = int(self.cur_h * 0.062) + 6
        self.win_w = max(p.width() for k, p in self.sprites.items() if k[1] == self.cur_h) + self.win_mx * 2
        self.setFixedSize(self.win_w, self.cur_h + BUBBLE_H + MARGIN * 2 + 10)
        self.snap_into_screen()

    def snap_into_screen(self):
        geo = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        x = max(geo.left(), min(geo.right() - self.width(), self.x()))
        y = max(geo.top(), min(geo.bottom() - self.height(), self.y()))
        self.move(x, y)

    def _apply_passthrough(self, on):
        hwnd = int(self.winId())
        GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT = -20, 0x80000, 0x20
        style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        style = style | WS_EX_LAYERED
        if on:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)

    def set_passthrough(self, on):
        self.cfg["passthrough"] = bool(on)
        self._apply_passthrough(bool(on))
        if on:
            self.say("I'm invisible now! Right-click the tray icon to undo~")

    def set_topmost(self, on):
        self.cfg["topmost"] = bool(on)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(on))
        self.show()

    def set_autostart(self, on):
        self.cfg["autostart"] = bool(on)
        try:
            set_autostart_shortcut(bool(on))
            self.say("Auto-start enabled, see you tomorrow~" if on else "Auto-start disabled")
        except Exception as ex:
            QMessageBox.warning(self, "Start on Boot", f"Failed to set: {ex}")

    def toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def quit_app(self):
        self.cfg["x"], self.cfg["y"] = self.x(), self.y()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, ensure_ascii=False, indent=2)
        self.tray.hide()
        QApplication.quit()


def _console_setup():
    """Console mode (install/uninstall autostart) -- handled before the GUI is
    created, then exit."""
    if "--install-autostart" in sys.argv:
        cfg = load_json(CONFIG_PATH, {})
        cfg["autostart"] = True
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        set_autostart_shortcut(True)
        print("[Whale Pet] start-on-boot enabled (includes auto-launching DSH)")
        print("On boot the pet will start and auto-launch DSH Web a few seconds later.")
        return True
    if "--uninstall-autostart" in sys.argv:
        cfg = load_json(CONFIG_PATH, {})
        cfg["autostart"] = False
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        set_autostart_shortcut(False)
        print("[Whale Pet] start-on-boot disabled")
        return True
    return False


def main():
    if _console_setup():
        return

    selftest = "--selftest" in sys.argv
    voicesample = "--voicesample" in sys.argv
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = PetWindow()
    if selftest or voicesample:
        # self-test mode: quickly exercise the DSH detection logic then exit
        # (does not restart DSH)
        QTimer.singleShot(500, w._poll_dsh)
        QTimer.singleShot(800, w._maybe_launch_dsh)
        if voicesample:
            # audition mode: play one sample voice then exit (verify the voice chain)
            QTimer.singleShot(1200, lambda: w.voice.speak(VOICE_TURN_DONE))
            QTimer.singleShot(10000, w.quit_app)
            print("[voicesample] will play a sample voice, then exit in 10s")
        else:
            QTimer.singleShot(4000, w.quit_app)
            print("[selftest] pet window started, exiting in 4s")
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "Whale Pet Error", str(ex))
        except Exception:
            pass
        raise
