#!/usr/bin/env python
# playoff.py
# -*- coding: utf-8 -*-
__author__ = 'Martin Pihrt'

APP_current       = "1.0.18"                                         # current version of the application
APP_date          = "05.11.2026"                                     # current version date
update_check_link = "https://raw.githubusercontent.com/pihrt-com/playoff/refs/heads/main/Playoff%20app/version.json"    # path to JSON with APP version

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
from tkinter import font as tkfont

import math, json, os, sys
import subprocess
import urllib.request
import time

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.colors import HexColor, black
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    messagebox.showerror(
        "Chyba",
        "Pro vektorový PDF export je potřeba knihovna reportlab:\n\npip install reportlab"
    )

try:
    from openpyxl import Workbook, load_workbook
except ImportError:
    messagebox.showerror(
        "Chyba",
        "Pro import/export excell je potřeba knihovna openpyxl:\n\npip install openpyxl"
    )    

# universal path to resources (works in Python and PyInstaller EXE)
if getattr(sys, 'frozen', False):
    BASE_PATH = sys._MEIPASS
else:
    BASE_PATH = os.path.abspath(os.path.dirname(__file__))


def build_updater_command(updater_path, target_exe, update_info):
    installer_url = str(update_info.get("url") or "").strip()
    if not installer_url:
        raise ValueError("V informacích o aktualizaci chybí URL instalátoru.")

    command = [updater_path, target_exe, installer_url]
    version = str(update_info.get("version") or "").strip()
    if version:
        command.extend(["--version", version])

    sha256 = str(update_info.get("sha256") or "").strip().lower()
    if sha256:
        if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
            raise ValueError("Aktualizační manifest obsahuje neplatný SHA-256 součet.")
        command.extend(["--sha256", sha256])

    size = int(update_info.get("size") or 0)
    if size < 0:
        raise ValueError("Aktualizační manifest obsahuje neplatnou velikost souboru.")
    if size:
        command.extend(["--size", str(size)])
    return command


def is_newer_version(candidate, current):
    """Return True only when a numeric dotted candidate version is newer."""
    try:
        candidate_parts = tuple(int(part) for part in str(candidate).strip().split("."))
        current_parts = tuple(int(part) for part in str(current).strip().split("."))
    except (TypeError, ValueError):
        return False
    length = max(len(candidate_parts), len(current_parts))
    candidate_parts += (0,) * (length - len(candidate_parts))
    current_parts += (0,) * (length - len(current_parts))
    return candidate_parts > current_parts


TEAM_TABLE_DEFAULT_TITLE = "Účastníci soutěže"
TEAM_TABLE_DEFAULT_HEADERS = ("ID", "Škola / adresa školy", "Jméno soutěžícího", "Nejlepší čas jízdy")
TEAM_RECORD_FIELDS = ("id", "school", "participant", "best_time")


def normalize_team_record(record):
    """Return a backward-compatible team record with all display fields."""
    record = record if isinstance(record, dict) else {}
    school = record.get("school", record.get("desc", ""))
    return {
        "id": str(record.get("id", "") or ""),
        "school": str(school or ""),
        "participant": str(record.get("participant", "") or ""),
        "best_time": str(record.get("best_time", "") or ""),
    }


def normalize_team_records(records):
    return [normalize_team_record(record) for record in (records or [])]


def team_record_from_excel_row(row):
    """Read two to four optional Excel cells without discarding partial rows."""
    values = list(row or ())[:len(TEAM_RECORD_FIELDS)]
    values.extend([None] * (len(TEAM_RECORD_FIELDS) - len(values)))
    return dict(zip(
        TEAM_RECORD_FIELDS,
        ("" if value is None else str(value) for value in values),
    ))


def normalize_team_table_headers(headers):
    values = list(headers or ())[:len(TEAM_TABLE_DEFAULT_HEADERS)]
    values.extend(TEAM_TABLE_DEFAULT_HEADERS[len(values):])
    return [str(value or default) for value, default in zip(values, TEAM_TABLE_DEFAULT_HEADERS)]


def lap_is_eligible_for_best(record):
    try:
        return not bool(record.get("invalid", False)) and int(record.get("ms", 0)) >= 10000
    except (AttributeError, TypeError, ValueError):
        return False


def best_valid_lap_ms(records):
    valid_times = [int(record.get("ms", 0)) for record in records if lap_is_eligible_for_best(record)]
    return min(valid_times) if valid_times else None


# Pillow optional
try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# try import usb_module (the new module we added). If missing, we provide a stub.
# Always add the current folder to sys.path so that the local usb_module.py is loaded.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import usb_module   # C:\Playoff\usb_module.py
    USB_AVAILABLE = True
except Exception as e:
    self._log("USB module error:", e)
    usb_module = None
    USB_AVAILABLE = False

# default settings
DEFAULT_BOX_W = 180
DEFAULT_BOX_H = 30
DEFAULT_H_GAP = 200
DEFAULT_V_GAP = 10
LINE_COLOR = "#0b6bd6"              # blue color
THIRD_PLACE_LINE_COLOR = "#d62828"  # red color
BOX_FILL = "#ffffff"
BOX_OUTLINE = "#000000"
TITLE_COLOR = "#000000"
CANVAS_BG_DEFAULT = "#ffffff"
# vítěz
WINNER_FILL = "#ffe06a"
WINNER_OUTLINE = "#cc9a00"
WINNER_TEXT_COLOR = "#000000"

# Default USB settings defaults (kept in setup file)
DEFAULT_USB_PORT           = ""
DEFAULT_USB_BAUD           = 115200
DEFAULT_USB_TIMEOUT        = 10.0

DEFAULT_USB_DISPLAY_A_BAUD = 115200
DEFAULT_USB_DISPLAY_B_BAUD = 115200
USB_PORT_DISABLED_LABEL    = "Nepoužívat"

LED_REFRESH_OPTIONS        = tuple(round(value / 10, 1) for value in range(1, 11))
DEFAULT_LED_REFRESH        = 0.1
DEFAULT_LAPS_MAX_TEAMS     = 40
LAPS_COUNTDOWN_WARNING     = 10
LAPS_COUNTDOWN_BLINK_MS    = 500
PROMO_TEXT_MAX_LENGTH      = 79
PROMO_SCROLL_MIN_MS        = 50
PROMO_SCROLL_MAX_MS        = 1000
PROMO_SCROLL_STEP_MS       = 50
DEFAULT_PROMO_SCROLL_MS    = 250
DEFAULT_PROMO_MODE         = "continuous"
PROMO_MODE_LABELS          = {
    "continuous": "Plynulá rotace (FW 1.0)",
    "firmware": "Rolování řízené panelem (SCR)",
    "static": "Statický text (TXT)",
}


def normalize_led_refresh(value):
    """Return one of the supported LED refresh intervals."""
    try:
        interval = round(float(value), 1)
    except (TypeError, ValueError):
        return DEFAULT_LED_REFRESH

    if interval in LED_REFRESH_OPTIONS:
        return interval
    return DEFAULT_LED_REFRESH


def normalize_laps_max_teams(value, default=DEFAULT_LAPS_MAX_TEAMS):
    """Return a valid even LAPS team maximum or the supplied default."""
    try:
        maximum = int(value)
    except (TypeError, ValueError):
        return default
    if maximum < 2 or maximum % 2:
        return default
    return maximum


def normalize_laps_team_history(history):
    """Normalize saved per-team LAPS records while preserving valid history."""
    if not isinstance(history, dict):
        return {}

    normalized = {}
    for raw_team_id, raw_state in history.items():
        try:
            team_id = int(raw_team_id)
        except (TypeError, ValueError):
            continue
        if team_id < 1 or not isinstance(raw_state, dict):
            continue

        records = []
        used_rides = set()
        next_available_ride = 1
        raw_records = raw_state.get("records", [])
        if not isinstance(raw_records, list):
            raw_records = []
        for raw_record in raw_records:
            if not isinstance(raw_record, dict):
                continue
            try:
                ride = int(raw_record.get("ride", next_available_ride))
            except (TypeError, ValueError):
                ride = next_available_ride
            if ride < 1 or ride in used_rides:
                while next_available_ride in used_rides:
                    next_available_ride += 1
                ride = next_available_ride
            try:
                milliseconds = max(0, int(raw_record.get("ms", 0)))
            except (TypeError, ValueError):
                milliseconds = 0
            used_rides.add(ride)
            next_available_ride = max(next_available_ride, ride + 1)
            records.append({
                "id": team_id,
                "ride": ride,
                "date": str(raw_record.get("date", "") or ""),
                "time": str(raw_record.get("time", "") or ""),
                "ms": milliseconds,
                "invalid": bool(raw_record.get("invalid", False)),
            })

        try:
            saved_next_ride = int(raw_state.get("next_ride", next_available_ride))
        except (TypeError, ValueError):
            saved_next_ride = next_available_ride
        normalized[str(team_id)] = {
            "records": records,
            "next_ride": max(1, next_available_ride, saved_next_ride),
        }
    return normalized


def validate_promo_text(value):
    """Validate text supported by the seven-segment display firmware."""
    text = str(value or "")
    if not text.strip():
        text = ""
    if len(text) > PROMO_TEXT_MAX_LENGTH:
        return False, text, f"Text může mít nejvýše {PROMO_TEXT_MAX_LENGTH} znaků."
    if any(ord(char) < 32 or ord(char) > 126 for char in text):
        return False, text, "Použijte pouze základní znaky bez diakritiky."
    return True, text, ""


def normalize_promo_mode(value):
    mode = str(value or "").strip().lower()
    if mode in PROMO_MODE_LABELS:
        return mode
    return DEFAULT_PROMO_MODE


def normalize_promo_scroll_ms(value):
    """Return a supported promo scroll interval in milliseconds."""
    try:
        interval = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULT_PROMO_SCROLL_MS
    interval = max(PROMO_SCROLL_MIN_MS, min(PROMO_SCROLL_MAX_MS, interval))
    steps = round((interval - PROMO_SCROLL_MIN_MS) / PROMO_SCROLL_STEP_MS)
    return PROMO_SCROLL_MIN_MS + steps * PROMO_SCROLL_STEP_MS


def promo_display_window(text, position, width=7):
    """Return a circular display window while preserving intentional spaces."""
    text = str(text or "")
    if not text or width <= 0:
        return " " * max(0, width)
    return "".join(text[(position + offset) % len(text)] for offset in range(width))


def normalize_usb_port_choice(value):
    """Convert the disabled UI choice to the empty persisted port value."""
    port = str(value or "").strip()
    if port == USB_PORT_DISABLED_LABEL:
        return ""
    return port


def usb_port_choice(port):
    """Return the value displayed in a USB port combobox."""
    return str(port or "").strip() or USB_PORT_DISABLED_LABEL


def find_usb_port_conflict(gate_port, display_port_a, display_port_b):
    """Return the first duplicate active COM port assignment, if any."""
    assignments = (
        ("Měřící brána", normalize_usb_port_choice(gate_port)),
        ("LED displej ID-1", normalize_usb_port_choice(display_port_a)),
        ("LED displej ID-2", normalize_usb_port_choice(display_port_b)),
    )
    used = {}
    for device_name, port in assignments:
        if not port:
            continue
        key = port.casefold()
        if key in used:
            return port, used[key], device_name
        used[key] = device_name
    return None


def classify_usb_devices(port_details, gate_port="", display_port_a="", display_port_b=""):
    """Classify visible serial ports without opening or resetting the devices."""
    details_by_port = {
        str(item.get("device") or "").strip(): item
        for item in port_details
        if str(item.get("device") or "").strip()
    }
    assignments = {
        "gate": normalize_usb_port_choice(gate_port),
        "display_a": normalize_usb_port_choice(display_port_a),
        "display_b": normalize_usb_port_choice(display_port_b),
    }
    claimed = {port.casefold() for port in assignments.values() if port}

    detected_gates = []
    detected_displays = []
    for key in ("display_a", "display_b"):
        port = assignments[key]
        if port and port in details_by_port and port not in detected_displays:
            detected_displays.append(port)
    if assignments["gate"] and assignments["gate"] in details_by_port:
        detected_gates.append(assignments["gate"])

    for port, item in details_by_port.items():
        if port.casefold() in claimed:
            continue
        identity = " ".join(
            str(item.get(key) or "")
            for key in ("description", "hwid")
        ).casefold()
        if not assignments["gate"] and "mega" in identity:
            detected_gates.append(port)
            claimed.add(port.casefold())
            continue
        if "nano" in identity:
            detected_displays.append(port)
            claimed.add(port.casefold())

    result = {}
    for key, port in assignments.items():
        result[key] = {
            "port": port,
            "found": bool(port and port in details_by_port),
            "details": details_by_port.get(port, {}),
        }

    result["unassigned"] = [
        item for port, item in details_by_port.items()
        if port.casefold() not in claimed
    ]
    result["detected_gates"] = detected_gates
    result["detected_displays"] = detected_displays
    return result


def laps_countdown_position(canvas_width, canvas_height, timer_height):
    """Return the bottom-center canvas position for the LAPS countdown."""
    timer_height = max(1, timer_height)
    return (
        canvas_width / 2,
        max(timer_height / 2 + 10, canvas_height - timer_height / 2 - 20),
    )

# --- Data classes ---
class Slot:
    def __init__(self, text=""):
        self.text = text

class Match:
    def __init__(self, a=None, b=None):
        self.a = a if a else Slot()
        self.b = b if b else Slot()

class Bracket:
    def __init__(self, team_list, pre_round_list, use_pre_round=False):
        """team_list: list of initial team names (may be empty strings)"""
        self.use_pre_round = use_pre_round
        self.team_count = max(0, int(len(team_list)))
        self.pre_count = max(0, int(len(pre_round_list)))
        self.rounds = []  # list of lists of Match
        self.titles = []
        self.pre_rounds = []
        self.pre_titles = []
        if use_pre_round:
            self._build_pre(pre_round_list)
        self._build(team_list)

    def _build_pre(self, pre_round_list):
        self.pre_rounds = []
        self.pre_titles = ["Předkolo"]
        first_round_match_count = math.ceil(len(pre_round_list) / 2)
        matches = []
        for i in range(first_round_match_count):
            matches.append(Match(Slot(""), Slot("")))
        self.pre_rounds.append(matches)

    def _build(self, team_list):
        self.rounds = []
        self.titles = []
        # initial round: pair teams sequentially, allowing last single
        teams = list(team_list)
        teams = [str(t) if t is not None else "" for t in teams]

        # first round matches: ceil(n/2)
        first_matches = math.ceil(len(teams) / 2) if len(teams) > 0 else 1
        matches0 = []
        for i in range(first_matches):
            a_idx = 2 * i
            b_idx = 2 * i + 1
            a = Slot(teams[a_idx]) if a_idx < len(teams) else Slot("")
            b = Slot(teams[b_idx]) if b_idx < len(teams) else Slot("")
            matches0.append(Match(a, b))
        self.rounds.append(matches0)
        self.titles.append("Kolo 1")

        # build subsequent rounds until 1 match
        prev_matches = matches0
        r = 1
        while len(prev_matches) > 1:
            next_count = math.ceil(len(prev_matches) / 2)
            next_matches = [Match() for _ in range(next_count)]
            self.rounds.append(next_matches)
            # default title
            if next_count == 1:
                self.titles.append("Finále")
            else:
                self.titles.append(f"Kolo {r+1}")
            prev_matches = next_matches
            r += 1
        # --- Winner ---
        # last real round = final → add a round with one slot
        winner_match = Match(Slot(""), Slot(""))
        self.rounds.append([winner_match])
        self.titles.append("Vítěz")            

    def rounds_count(self):
        return len(self.rounds)

# --- App ---
class PlayoffApp:
    def __init__(self, root):
        self.root = root
        root.title("Playoff generátor by Martin Pihrt © www.pihrt.com")

        # state
        self.bracket = None
        self.current_winner = ""
        self.bg_path = None
        self.bg_image = None
        self.bg_tk = None
        self.canvas_bg = CANVAS_BG_DEFAULT
        self.line_width = 2           # normal/thick
        self.font_scale = "large"     # small/medium/large
        self.odd_behavior = "manual"  # auto/manual/waiting
        self.lock_edit = False
        self.projector_mode = False
        self.enable_timer = True
        self.timer_value = '05:00'
        self.timer_running = False
        self.race_active = False
        self.timer_blink = False
        self.current_seconds = 0
        self.timer_start_mode = "ok"  # "start" | "ok"  
        self.laps_countdown_running = False
        self.laps_countdown_seconds = self.time_to_seconds(self.timer_value)
        self.laps_countdown_after_id = None
        self.laps_countdown_blink_after_id = None
        self.laps_countdown_blink_state = False
        self.team_names = []          # Team naming database
        self.team_table_title = TEAM_TABLE_DEFAULT_TITLE
        self.team_table_headers = list(TEAM_TABLE_DEFAULT_HEADERS)
        self.pre_round_enabled = True
        self.third_place_enabled = True
        self.third_place_title = "3. místo"
        self.lap_timer_enabled = True
        self.lap_timer_var = tk.BooleanVar(value=self.lap_timer_enabled)
        self.lap_time_a = 0   # ms
        self.lap_time_b = 0   # ms
        self.lap_time_a_var = tk.StringVar(value="A 00:00:000")
        self.lap_time_b_var = tk.StringVar(value="B 00:00:000")
        self.lap_running_a = False
        self.lap_running_b = False
        self.lap_after_id = None
        self.live_led_enabled = False
        self.live_led_refresh = DEFAULT_LED_REFRESH
        self.live_led_var = tk.BooleanVar(value=self.live_led_enabled)
        self.live_led_refresh_var = tk.StringVar(value=f"{self.live_led_refresh:.1f}")
        self.live_led_next_send = {1: 0.0, 2: 0.0}
        self.promo_text = ""
        self.promo_mode = DEFAULT_PROMO_MODE
        self.promo_scroll_ms = DEFAULT_PROMO_SCROLL_MS
        self.promo_active = False
        self.promo_scroll_position = 0
        self.promo_after_id = None
        self.font_scale_var = tk.StringVar(value=self.font_scale)
        self.odd_behavior_var = tk.StringVar(value=self.odd_behavior)
        self.line_width_var = tk.IntVar(value=self.line_width)
        self.timer_menu_var = tk.BooleanVar(value=self.enable_timer)
        self.timer_start_mode_var = tk.StringVar(value=self.timer_start_mode)
        self.pre_round_var = tk.BooleanVar(value=self.pre_round_enabled)
        self.third_place_var = tk.BooleanVar(value=self.third_place_enabled)

        self.third_place = {"a": "", "b": "", "winner": ""}        

        # USB manager (from usb_module)
        if USB_AVAILABLE:
            try:
                self.usb = usb_module.USBManager(self)
            except Exception:
                self.usb = None
        else:
            self.usb = None
        # store usb settings for saving into setup file
        self.usb_port = DEFAULT_USB_PORT
        self.usb_baud = DEFAULT_USB_BAUD
        self.usb_timeout = DEFAULT_USB_TIMEOUT

        # 7 seg LED display
        self.display_port_a = ""
        self.display_port_b = ""
        self.display_baud_a = DEFAULT_USB_DISPLAY_A_BAUD
        self.display_baud_b = DEFAULT_USB_DISPLAY_B_BAUD

        # view mode
        self.view_mode = "playoff"
        self.view_mode_var = tk.StringVar(value=self.view_mode)
        
        # laps mode data
        self.laps_max_teams = DEFAULT_LAPS_MAX_TEAMS
        self.laps_active_team_a = 1
        self.laps_teams = {}
        self.laps_a = []
        self.laps_b = []
        self.lap_id_a = 1
        self.lap_id_b = 1
        self._load_laps_team_pair(1, store_current=False, redraw=False)

        # Top toolbar: left settings (calls existing menu), right Start button and status label
        toolbar = tk.Frame(root)
        toolbar.pack(side='top', fill='x', padx=4, pady=4)

        # --- Settings icon (gear wheel) ---
        try:
            settings_img_path = os.path.join(BASE_PATH, "settings.ico")

            if PIL_AVAILABLE:
                img = Image.open(settings_img_path)

                if hasattr(img, "n_frames"):
                    best_pixels = 0
                    best_frame = 0
                    for i in range(img.n_frames):
                        img.seek(i)
                        w, h = img.size
                        if w * h > best_pixels:
                            best_pixels = w * h
                            best_frame = i
                    img.seek(best_frame)

                TARGET_H = 44

                w, h = img.size
                scale = TARGET_H / h
                new_w = int(w * scale)
                new_h = int(h * scale)

                img = img.resize((new_w, new_h), Image.LANCZOS)
                settings_raw = ImageTk.PhotoImage(img)

            else:
                # fallback bez Pillow
                settings_raw = tk.PhotoImage(file=settings_img_path)

            self.settings_btn = tk.Menubutton(toolbar, image=settings_raw, relief=tk.FLAT)
            self.settings_btn.image = settings_raw  # nutné pro garbage-collector

            self.settings_menu = tk.Menu(self.settings_btn, tearoff=0)
            self.settings_btn.config(menu=self.settings_menu)
            self.settings_btn.pack(side='left', padx=4)

            ver_txt = f"app verze: {APP_current} ({APP_date})"
            self.ver_label = tk.Label(toolbar, text=ver_txt, fg="#666666", font=("Arial", 7))
            self.ver_label.pack(side='left', padx=(10,0))

            # --- USB STATUS INDICATOR ---
            self.usb_status_canvas = tk.Canvas(toolbar, width=12, height=12, highlightthickness=0, bd=0, bg=toolbar.cget("bg"))
            self.usb_status_id = self.usb_status_canvas.create_oval(2, 2, 10, 10, fill="red", outline="red")
            self.usb_status_canvas.pack(side="left", padx=(10, 2))

            self.usb_status_label = tk.Label(toolbar, text="USB", fg="#333333", font=("Arial", 8, "bold"))
            self.usb_status_label.pack(side="left", padx=(0, 10))

            # --- DISPLAY ID-1 STATUS ---
            self.disp1_status_canvas = tk.Canvas(
                toolbar,
                width=12,
                height=12,
                highlightthickness=0,
                bd=0,
                bg=toolbar.cget("bg")
            )

            self.disp1_status_id = self.disp1_status_canvas.create_oval(
                2, 2, 10, 10,
                fill="red",
                outline="red"
            )

            self.disp1_status_canvas.pack(side="left", padx=(5, 2))

            self.disp1_status_label = tk.Label(
                toolbar,
                text="ID1",
                fg="#333333",
                font=("Arial", 8, "bold")
            )

            self.disp1_status_label.pack(side="left", padx=(0, 10))


            # --- DISPLAY ID-2 STATUS ---
            self.disp2_status_canvas = tk.Canvas(
                toolbar,
                width=12,
                height=12,
                highlightthickness=0,
                bd=0,
                bg=toolbar.cget("bg")
            )

            self.disp2_status_id = self.disp2_status_canvas.create_oval(
                2, 2, 10, 10,
                fill="red",
                outline="red"
            )

            self.disp2_status_canvas.pack(side="left", padx=(5, 2))

            self.disp2_status_label = tk.Label(
                toolbar,
                text="ID2",
                fg="#333333",
                font=("Arial", 8, "bold")
            )

            self.disp2_status_label.pack(side="left", padx=(0, 10))

            # --------------------------------------------------
            # VIEW MODE
            # --------------------------------------------------
            self.mode_frame = tk.Frame(toolbar)

            self.mode_frame.pack(
                side="left",
                padx=(20, 20)
            )

            mode_button_style = {
                "width": 10,
                "relief": "raised",
                "bd": 2,
                "cursor": "hand2",
                "padx": 8,
                "pady": 3,
                "font": ("Arial", 9),
                "highlightthickness": 0,
            }

            self.mode_playoff_btn = tk.Button(
                self.mode_frame,
                text="PLAYOFF",
                command=lambda: self.change_view_mode("playoff"),
                **mode_button_style,
            )

            self.mode_playoff_btn.pack(
                side="left",
                padx=(0, 2)
            )

            self.mode_laps_btn = tk.Button(
                self.mode_frame,
                text="LAPS",
                command=lambda: self.change_view_mode("laps"),
                **mode_button_style,
            )

            self.mode_laps_btn.pack(
                side="left"
            )

            self.promo_btn = tk.Button(
                self.mode_frame,
                text="PROMO",
                command=self.toggle_promo,
                state="disabled",
                **mode_button_style,
            )
            self.promo_btn.pack(side="left", padx=(2, 0))

            self.update_view_mode_buttons()

        except Exception as e:
            self._log("Nelze načíst settings ikonu:", e)
            self.settings_btn = tk.Menubutton(toolbar, text="⚙", relief=tk.RAISED)
            self.settings_menu = tk.Menu(self.settings_btn, tearoff=0)
            self.settings_btn.config(menu=self.settings_menu)
            self.settings_btn.pack(side='left')

            ver_txt = f"app verze: {APP_current} ({APP_date})"
            self.ver_label = tk.Label(toolbar, text=ver_txt, fg="#666666", font=("Arial", 7))
            self.ver_label.pack(side='left', padx=(10,0))


        # teams
        self.settings_menu.add_command(label='Počet týmů', command=self.ask_team_count)
        self.settings_menu.add_command(label='Generovat týmy', command=self.generate_from_entry)
        self.settings_menu.add_command(label='Pojmenování týmů', command=self.open_team_naming_dialog)
        self.settings_menu.add_command(label='Smazat jen obsah', command=self.reset_values)
        self.settings_menu.add_command(label='Vymazat všechno', command=self.clear_all)
        self.settings_menu.add_checkbutton(label='Používat předkolo', variable=self.pre_round_var, command=self.toggle_pre_round)
        self.settings_menu.add_checkbutton(label='Zobrazit 3. místo', variable=self.third_place_var, command=self.toggle_third_place)

        # odd behavior
        odd_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label='Chování při lichém počtu vítězů', menu=odd_menu)        
        odd_menu.add_radiobutton(
            label='Automatický BYE',
            variable=self.odd_behavior_var,
            value='auto',
            command=lambda: self.set_odd_behavior('auto')
        )

        odd_menu.add_radiobutton(
            label='Ruční postup',
            variable=self.odd_behavior_var,
            value='manual',
            command=lambda: self.set_odd_behavior('manual')
        )

        odd_menu.add_radiobutton(
            label='Čekající hráč',
            variable=self.odd_behavior_var,
            value='waiting',
            command=lambda: self.set_odd_behavior('waiting')
        )

        laps_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label='LAPS', menu=laps_menu)
        laps_menu.add_command(
            label='LAPS max počet týmů',
            command=self.ask_laps_max_teams,
        )
        laps_menu.add_command(
            label='Vymazat tabulky A a B všech týmů',
            command=self.clear_all_laps_history,
        )

        self.settings_menu.add_separator()
        self.settings_menu.add_command(label='Načíst pozadí', command=self.load_bg_image)
        self.settings_menu.add_command(label='Smazat pozadí', command=self.remove_bg)

        # font submenu
        font_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label='Velikost písma', menu=font_menu)        
        font_menu.add_radiobutton(
            label='Malé',
            variable=self.font_scale_var,
            value='small',
            command=lambda: self.set_font_scale('small')
        )

        font_menu.add_radiobutton(
            label='Střední',
            variable=self.font_scale_var,
            value='medium',
            command=lambda: self.set_font_scale('medium')
        )

        font_menu.add_radiobutton(
            label='Velké',
            variable=self.font_scale_var,
            value='large',
            command=lambda: self.set_font_scale('large')
        )
    
        self.settings_menu.add_command(label='Barva pozadí', command=self.choose_canvas_bg)

        # line width submenu
        lw_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label='Tloušťka čar', menu=lw_menu)
        lw_menu.add_radiobutton(
            label='Normální',
            variable=self.line_width_var,
            value=2,
            command=lambda: self.set_line_width(2)
        )

        lw_menu.add_radiobutton(
            label='Silné',
            variable=self.line_width_var,
            value=4,
            command=lambda: self.set_line_width(4)
        )

        self.settings_menu.add_separator()
        self.settings_menu.add_checkbutton(label='Zamknout editaci týmů', command=self.toggle_lock_edit)
        self.settings_menu.add_command(label='Načíst ze souboru', command=self.load_setup)
        self.settings_menu.add_command(label='Uložit do souboru', command=self.save_setup)

        # timer enable
        self.settings_menu.add_separator()        
        self.timer_menu_var = tk.BooleanVar(value=self.enable_timer)
        self.settings_menu.add_checkbutton(label='Povolit odpočet', variable=self.timer_menu_var, command=self.on_toggle_timer)

        # timer mode
        timer_mode_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label='Režim spuštění odpočtu', menu=timer_mode_menu)

        timer_mode_menu.add_radiobutton(
            label='Spustit odpočet ihned (po START)',
            variable=self.timer_start_mode_var,
            value='start',
            command=lambda: self.set_timer_start_mode('start')
        )

        timer_mode_menu.add_radiobutton(
            label='Spustit odpočet až po semaforu (OK)',
            variable=self.timer_start_mode_var,
            value='ok',
            command=lambda: self.set_timer_start_mode('ok')
        )

        self.settings_menu.add_checkbutton(
            label='Měřit a zobrazit čas kola',
            variable=self.lap_timer_var,
            command=self.on_toggle_lap_timer
        )

        self.settings_menu.add_checkbutton(
            label='Odesílat na LED průběžný čas',
            variable=self.live_led_var,
            command=self.on_toggle_live_led
        )
        self.settings_menu.add_command(
            label='Nastavit propagační text',
            command=self.open_promo_text_dialog
        )

        led_refresh_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label='Rychlost obnovování', menu=led_refresh_menu)
        for interval in LED_REFRESH_OPTIONS:
            led_refresh_menu.add_radiobutton(
                label=f"{interval:.1f} s",
                variable=self.live_led_refresh_var,
                value=f"{interval:.1f}",
                command=self.on_set_live_led_refresh
            )

        self.settings_menu.add_separator()
        self.settings_menu.add_command(label='USB nastavení', command=self.open_usb_dialog)

        self.settings_menu.add_separator()
        self.settings_menu.add_command(label='Export do PDF PLAYOFF', command=self.export_pdf)
        self.settings_menu.add_command(label='Export do PDF LAPS', command=self.export_laps_pdf)

        # Fullscreen mode toggle
        self.fullscreen_var = tk.BooleanVar(value=self.projector_mode)
        self.settings_menu.add_checkbutton(
            label='Celá obrazovka',
            variable=self.fullscreen_var,
            command=self.toggle_projector
        )

        self.settings_menu.add_command(label='Nápověda', command=self.show_help)
        
        self.settings_menu.add_command(label='Kontrola aktualizace', command=self.check_for_update)

        self.settings_btn.config(menu=self.settings_menu)
        self.settings_btn.pack(side='left')

        spacer = tk.Label(toolbar, text='')
        spacer.pack(side='left', expand=True)

        # ----- LAP TIMERS (A/B) -----
        self.lap_label_a = tk.Label(
            toolbar,
            textvariable=self.lap_time_a_var,
            font=("Consolas", 22, "bold"),
            fg="#FF8C00",
            bg="black",
            relief="ridge",
            bd=3,
            padx=12,
            pady=4
        )

        self.lap_label_b = tk.Label(
            toolbar,
            textvariable=self.lap_time_b_var,
            font=("Consolas", 22, "bold"),
            fg="#FF8C00",
            bg="black",
            relief="ridge",
            bd=3,
            padx=12,
            pady=4
        )

        # default hidden
        self.lap_label_a.pack_forget()
        self.lap_label_b.pack_forget()

        # ----- Live time and date -----
        self.datetime_var = tk.StringVar(value="")
        self.datetime_label = tk.Label(toolbar, textvariable=self.datetime_var, font=("Consolas", 22, "bold"))
        self.datetime_label.pack(side='left', expand=True)

        # status label at right
        self.status_var = tk.StringVar(value='')
        self.status_label = tk.Label(toolbar, textvariable=self.status_var)
        self.status_label.pack(side='right', padx=(0,8))

        # Start button
        self.start_btn = tk.Button(
            toolbar,
            text='Start',
            command=self.on_start,
            font=("Arial", 12, "bold"),   # ← larger and bold text
            padx=15,                      # ← horizontal padding
            pady=5                        # ← vertical padding
        )

        self.start_btn.pack(side='right', padx=4)
        if not USB_AVAILABLE:
            self.start_btn.config(state='disabled')
            self.status_var.set('USB modul chybí')

        # top controls
        self.team_var = tk.StringVar(value="16")

        # canvas
        self.canvas = tk.Canvas(root, bg=self.canvas_bg)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind('<Configure>', lambda e: self.redraw())

        # Timer overlay (canvas create_window)
        self.timer_label = tk.Label( # timer MM:SS box size
            self.root, 
            text=self.timer_value,
            font=("Consolas", 100, "bold"), 
            bg='black', 
            fg='white',
            bd=4,         # larger margin
            relief='ridge',
            padx=20,      # horizontal inner edge
            pady=10       # vertical inner edge
        ) 
        self.timer_label.bind('<Button-1>', self.on_timer_left_click)
        self.timer_label.bind('<Button-3>', self.on_timer_right_click)
        self.timer_window = None

        self.rect_items = {}
        self.text_items = {}
        self.title_items = {}
        self.line_items = []

        # initial bracket: empty list of N empty team slots based on team_var
        try:
            n = int(self.team_var.get())
        except Exception:
            n = 16

        self.update_datetime()
        self.apply_lap_timer_visibility()
        self.check_for_update()
        
        # automatic USB check every 1.5 s
        self.root.after(1500, self.auto_check_usb)

        root.bind('<Escape>', lambda e: self.exit_fullscreen())

        # try load usb settings from previous setup file if available
        try:
            settings_path = os.path.join(
                os.path.expanduser('~'),
                '.playoff_settings.json'
            )

            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    s = json.load(f)

                self.usb_port = s.get('usb_port', self.usb_port)
                self.usb_baud = s.get('usb_baud', self.usb_baud)
                self.usb_timeout = s.get('usb_timeout', self.usb_timeout)
                self.display_port_a = s.get('display_port_a', self.display_port_a)
                self.display_port_b = s.get('display_port_b', self.display_port_b)
                self.display_baud_a = s.get('display_baud_a', self.display_baud_a)
                self.display_baud_b = s.get('display_baud_b', self.display_baud_b)
                self.enable_timer = bool(s.get('enable_timer', self.enable_timer))
                self.timer_menu_var.set(self.enable_timer)
                saved_timer_value = str(s.get('timer_value', self.timer_value))
                if self.validate_time_format(saved_timer_value):
                    self.timer_value = saved_timer_value
                self.laps_countdown_seconds = self.time_to_seconds(self.timer_value)
                self.timer_label.config(text=self.timer_value)
                self.lap_timer_enabled = bool(s.get('lap_timer_enabled', self.lap_timer_enabled))
                self.lap_timer_var.set(self.lap_timer_enabled)
                self.live_led_enabled = bool(s.get('live_led_enabled', self.live_led_enabled))
                self.live_led_var.set(self.live_led_enabled)
                self.live_led_refresh = normalize_led_refresh(
                    s.get('live_led_refresh', self.live_led_refresh)
                )
                self.live_led_refresh_var.set(f"{self.live_led_refresh:.1f}")
                self.laps_max_teams = normalize_laps_max_teams(
                    s.get('laps_max_teams', self.laps_max_teams),
                    self.laps_max_teams,
                )
                promo_valid, promo_text, _promo_error = validate_promo_text(
                    s.get('promo_text', self.promo_text)
                )
                self.promo_text = promo_text if promo_valid else ""
                self.promo_mode = normalize_promo_mode(
                    s.get('promo_mode', self.promo_mode)
                )
                self.promo_scroll_ms = normalize_promo_scroll_ms(
                    s.get('promo_scroll_ms', self.promo_scroll_ms)
                )
                self.apply_lap_timer_visibility()

                self.view_mode = s.get('view_mode', 'playoff')
                self.view_mode_var.set(self.view_mode)

                self.root.after(100, self.update_view_mode_gui)

                try:
                    self.update_view_mode_buttons()
                except:
                    pass

                # LED panel status
                if self.display_port_a:
                    self.update_display_status(1, True)
                else:
                    self.update_display_status(1, False)

                if self.display_port_b:
                    self.update_display_status(2, True)
                else:
                    self.update_display_status(2, False)                

                if self.usb:
                    try:
                        if self.usb_port:
                            self.usb.validate_and_set(
                                self.usb_port,
                                self.usb_baud,
                                self.usb_timeout
                            )

                            # Apply the loaded port even when a prior initialization is active.
                            self.usb.reconnect(self.on_usb_line)
                            self.update_usb_status(True)
                            self._log(f"USB AUTO CONNECT: port {self.usb_port} speed {self.usb_baud}")
                        else:
                            self.usb.disconnect()
                            self.update_usb_status(False)

                        # LED displays are independent of the measuring gate.
                        self.usb.connect_displays()
                        self.root.after(
                            2500,
                            lambda: self.usb.send_display(1, "TXT:ID-1")
                        )
                        self.root.after(
                            2600,
                            lambda: self.usb.send_display(2, "TXT:ID-2")
                        )                
                        self.root.after(
                            7000,
                            lambda: self.usb.send_display(1, "TXT:-------")
                        )
                        self.root.after(
                            7200,
                            lambda: self.usb.send_display(2, "TXT:-------")
                        )                        
                        if self.usb_port:
                            if self.view_mode == "laps":
                                self.usb.handler.send(b"mode_laps\n")
                            else:
                                self.usb.handler.send(b"mode_playoff\n")

                    except Exception as e:
                        self._log("USB AUTO CONNECT ERROR:", e)
                        self.update_usb_status(False)

        except Exception as e:
            self._log("USB SETTINGS LOAD ERROR:", e)

        self.update_promo_button_state()

    def set_playoff_icon(self, window):
        try:
            window.iconbitmap(os.path.join(BASE_PATH, "playoff.ico"))
        except Exception:
            pass

    def _now(self):
        return time.strftime("%H:%M:%S")

    def _log(self, msg: str, param=""):
        print(f"[playoff {self._now()}] {msg} {param}", file=sys.stderr)

    def on_close(self):
        if self.usb:
            self.usb.disconnect_displays()
            self.usb.disconnect()
        self.root.destroy()

    def update_third_place_from_semifinal(self):
        if not self.bracket or not self.third_place_enabled:
            return

        rounds = self.bracket.rounds

        if len(rounds) < 3:
            return

        semifinal_round = len(rounds) - 3
        final_round = len(rounds) - 2

        semifinal_matches = rounds[semifinal_round]
        final_match = rounds[final_round][0]

        losers = []

        for m_idx, match in enumerate(semifinal_matches):
            a = match.a.text.strip()
            b = match.b.text.strip()

            finalist_a = final_match.a.text.strip()
            finalist_b = final_match.b.text.strip()

            if a == finalist_a or a == finalist_b:
                loser = b
            elif b == finalist_a or b == finalist_b:
                loser = a
            else:
                loser = ""

            if loser:
                losers.append(loser)

        if len(losers) >= 2:
            self.third_place["a"] = losers[0]
            self.third_place["b"] = losers[1]


    def toggle_pre_round(self):
        self.pre_round_enabled = self.pre_round_var.get()
        if not self.bracket:
            self.redraw()
            return

        if self.pre_round_enabled:
            if not self.bracket.pre_rounds:
                n = self.bracket.team_count
                pre_round_list = [""] * n
                self.bracket._build_pre(pre_round_list)
        else:
            pass

        self.redraw()

    def check_for_update(self):
        try:
            with urllib.request.urlopen(update_check_link, timeout=3) as r:
                info = json.loads(r.read().decode('utf-8'))
        except:
            messagebox.showwarning("Aktualizace programu", "Nepodařilo se stáhnout data z Internetu.")
            return

        latest = info.get("version")
        url = info.get("url")

        if is_newer_version(latest, APP_current):
            if messagebox.askyesno("Aktualizace programu", f"Dostupná verze {latest}. Aktualizovat?"):
                # path to the file to be updated
                if getattr(sys, 'frozen', False):
                    # runs as EXE
                    exe_path = sys.executable
                    app_dir = os.path.dirname(sys.executable)
                else:
                    # runs as .py
                    exe_path = os.path.abspath(__file__)
                    app_dir = os.path.dirname(exe_path)

                updater = os.path.join(app_dir, "updater.exe")

                try:
                    if not os.path.isfile(updater):
                        raise FileNotFoundError(f"Soubor nebyl nalezen: {updater}")
                    updater_command = build_updater_command(updater, exe_path, info)
                    subprocess.Popen(updater_command, close_fds=True)
                except Exception as e:
                    messagebox.showerror("Updater chyba", f"Nelze spustit updater.exe:\n{e}")
                    return

                self.root.destroy()
                sys.exit(0)

        else:
            messagebox.showinfo("Aktualizace", "Máte nejnovější verzi :-)")

    def edit_pre_title(self):
        if self.lock_edit:
            return

        current = self.bracket.pre_titles[0] if self.bracket.pre_titles else "Předkolo"

        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("Změnit nadpis předkola")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="Nadpis:").pack(padx=10, pady=(10,4))
        ent = tk.Entry(dlg, width=40)
        ent.insert(0, current)
        ent.pack(padx=10, pady=6)
        ent.focus_set()

        def on_ok():
            new = ent.get().strip()
            if not self.bracket.pre_titles:
                self.bracket.pre_titles = [new]
            else:
                self.bracket.pre_titles[0] = new
            dlg.destroy()
            self.redraw()

        tk.Button(dlg, text="OK", command=on_ok).pack(pady=10)
        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        self.root.wait_window(dlg)

    def edit_pre_slot(self, m_idx, side):
        if self.lock_edit:
            return

        match = self.bracket.pre_rounds[0][m_idx]
        slot = match.a if side == 'a' else match.b

        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("Zadej tým (Předkolo)")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="Zadej číslo nebo název týmu:").pack(padx=10, pady=(10, 4))
        ent = tk.Entry(dlg, width=40)
        ent.pack(padx=10, pady=6)
        ent.insert(0, slot.text)
        ent.focus_set()

        def on_ok():
            slot.text = ent.get()
            dlg.destroy()
            self.redraw()

        tk.Button(dlg, text="OK", command=on_ok).pack(pady=10)
        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

        self.root.wait_window(dlg)    

    def ask_team_count(self):
        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("Zadat počet týmů")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="Počet týmů:").pack(padx=10, pady=6)
        ent = tk.Entry(dlg, width=10)
        ent.insert(0, self.team_var.get())
        ent.pack(padx=10, pady=4)
        ent.focus_set()

        def on_ok():
            val = ent.get()
            if not val.isdigit() or int(val) < 1:
                messagebox.showerror("Chyba", "Počet týmů musí být kladné číslo.")
                return

            if not val.isdigit() or int(val) > 24:
                messagebox.showerror("Chyba", "Počet týmů musí být <= 24.")
                return                

            self.team_var.set(val)
            dlg.destroy()

            self.generate_bracket_with_empty(int(val))

        tk.Button(dlg, text="OK", command=on_ok).pack(pady=8)
        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
    
    def update_datetime(self):
        import datetime
        now = datetime.datetime.now()
        self.datetime_var.set(now.strftime("%d.%m.%Y  %H:%M:%S"))
        self.root.after(1000, self.update_datetime)

    def start_lap_timer(self):
        self.stop_promo()
        self.lap_running_a = True
        self.lap_running_b = True
        self.update_promo_button_state()

        if self.lap_after_id:
            try:
                self.root.after_cancel(self.lap_after_id)
            except:
                pass

        import time
        self.lap_last_time = time.time()
        self.reset_live_led_schedule(1, 2)

        self.lap_loop()

    def lap_loop(self):
        import time

        if not self.lap_running_a and not self.lap_running_b:
            return

        now = time.time()
        delta = now - self.lap_last_time
        self.lap_last_time = now

        delta_ms = int(delta * 1000)

        if self.lap_running_a:
            self.lap_time_a += delta_ms

        if self.lap_running_b:
            self.lap_time_b += delta_ms

        self.lap_time_a_var.set("A " + self.format_lap(self.lap_time_a))
        self.lap_time_b_var.set("B " + self.format_lap(self.lap_time_b))

        self.send_live_led_times()

        self.lap_after_id = self.root.after(50, self.lap_loop)

    def format_lap(self, ms):
        minutes = ms // 60000
        seconds = (ms % 60000) // 1000
        millis = ms % 1000
        return f"{minutes:02d}:{seconds:02d}:{millis:03d}"

    def start_laps_timer(self):
        self.stop_promo()
        self.update_promo_button_state()
        import time
        if self.lap_after_id:
            try:
                self.root.after_cancel(self.lap_after_id)
            except:
                pass
        self.lap_last_time = time.time()
        self.lap_after_id = self.root.after(50, self.laps_loop)        

    def laps_loop(self):
        import time
        if not self.lap_running_a and not self.lap_running_b:
            self.lap_after_id = None
            return

        now = time.time()
        delta = now - self.lap_last_time
        self.lap_last_time = now
        delta_ms = int(delta * 1000)
        if self.lap_running_a:
            self.lap_time_a += delta_ms
        if self.lap_running_b:
            self.lap_time_b += delta_ms
        self.lap_time_a_var.set(
            "A " + self.format_lap(self.lap_time_a)
        )
        self.lap_time_b_var.set(
            "B " + self.format_lap(self.lap_time_b)
        )
        self.send_live_led_times()
        self.lap_after_id = self.root.after(50, self.laps_loop)

    def finish_a(self):
        if not self.lap_running_a:
            return

        self._log("FINISH A")
        self.lap_running_a = False
        self.lap_label_a.config(fg="green")
        self.update_promo_button_state()


    def finish_b(self):
        if not self.lap_running_b:
            return

        self._log("FINISH B")
        self.lap_running_b = False
        self.lap_label_b.config(fg="green")
        self.update_promo_button_state()


    def format_display_time(self, ms):
        total_seconds = ms / 1000.0
        # 00.000 to 59.999
        if total_seconds < 60:
            return f"{total_seconds:06.3f}"
        # 01.00.0 to 99.59.9
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        tenths = int((total_seconds * 10) % 10)
        return f"{minutes:02d}.{seconds:02d}.{tenths}"

    def send_display_latest(self, display_id, text):
        if not self.usb:
            return False

        sender = getattr(self.usb, 'send_display_latest', None)
        if callable(sender):
            return sender(display_id, text)
        return self.usb.send_display(display_id, text)

    def reset_live_led_schedule(self, *display_ids):
        next_send = time.monotonic() + self.live_led_refresh
        for display_id in display_ids or (1, 2):
            self.live_led_next_send[display_id] = next_send

    def reset_led_times(self, *display_ids):
        ids = display_ids or (1, 2)
        for display_id in ids:
            self.send_display_latest(display_id, "TXT:00.000")
        self.reset_live_led_schedule(*ids)

    def send_live_led_times(self, now=None):
        if not self.live_led_enabled or not self.usb:
            return

        current = time.monotonic() if now is None else now
        displays = (
            (1, self.lap_running_a, self.lap_time_a),
            (2, self.lap_running_b, self.lap_time_b),
        )

        for display_id, running, elapsed_ms in displays:
            if not running or current < self.live_led_next_send[display_id]:
                continue
            self.send_display_latest(
                display_id,
                f"TXT:{self.format_display_time(elapsed_ms)}"
            )
            self.live_led_next_send[display_id] = current + self.live_led_refresh

    # small helper to open the existing settings menu -> we will just show the menubar cascade
    def _open_menu_settings(self):
        # open ask_team_count as a representative settings entry
        try:
            self.ask_team_count()
        except Exception:
            pass

    def update_usb_status(self, connected: bool):
        """GRN = connected, RED = disconnected."""
        try:
            color = "green" if connected else "red"
            self.usb_status_canvas.itemconfig(self.usb_status_id, fill=color, outline=color)
        except:
            pass

    def on_view_mode_change(self):
        new_mode = self.view_mode_var.get()
        if new_mode == self.view_mode:
            return

        if not messagebox.askyesno(
            "Změna režimu",
            f"Opravdu přepnout do režimu "
            f"{new_mode.upper()} ?"
        ):
            self.view_mode_var.set(self.view_mode)
            return

        self.stop_promo()
        self.stop_countdowns_for_mode_change()
        self.race_active = False
        self.view_mode = new_mode
        self.update_view_mode_gui()
        self._log(f"VIEW MODE = {self.view_mode}")
        self.redraw()
        try:
            if self.usb and self.usb_port:
                if self.view_mode == "laps":
                    self.usb.handler.send(b"mode_laps\n")
                else:
                    self.usb.handler.send(b"mode_playoff\n")
        except Exception as e:
            self._log(f"MODE SEND ERROR: {e}")        

    def change_view_mode(self, new_mode):
        if new_mode == self.view_mode:
            return

        if not messagebox.askyesno(
            "Změna režimu",
            f"Opravdu přepnout do režimu "
            f"{new_mode.upper()} ?"
        ):
            return

        self.stop_promo()
        self.stop_countdowns_for_mode_change()
        self.race_active = False
        self.lap_time_a = 0
        self.lap_time_b = 0
        self.lap_running_a = False
        self.lap_running_b = False
        self.lap_after_id = None
        self.view_mode = new_mode
        self.view_mode_var.set(new_mode)
        self.update_view_mode_buttons()
        self.update_view_mode_gui()
        self._log(f"VIEW MODE = {self.view_mode}")
        if new_mode == "laps":
            self.status_var.set("")
        self.root.update_idletasks()
        self.canvas.update_idletasks()
        self.redraw()
        try:
            if self.usb and self.usb_port:
                if self.view_mode == "laps":
                    self._log("TX mode_laps")
                    self.usb.handler.send(b"mode_laps\n")
                else:
                    self._log("TX mode_playoff")
                    self.usb.handler.send(b"mode_playoff\n")
        except Exception as e:
            self._log(f"MODE SEND ERROR: {e}")        

    def update_view_mode_buttons(self):
        if self.view_mode == "playoff":
            self.mode_playoff_btn.config(
                bg="#4CAF50",
                fg="white",
                relief="sunken"
            )

            self.mode_laps_btn.config(
                bg=self.root.cget("bg"),
                fg="black",
                relief="raised"
            )
        else:
            self.mode_laps_btn.config(
                bg="#4CAF50",
                fg="white",
                relief="sunken"
            )

            self.mode_playoff_btn.config(
                bg=self.root.cget("bg"),
                fg="black",
                relief="raised"
            )

    def update_view_mode_gui(self):
        self.start_btn.pack_forget()
        if self.view_mode == "playoff":
            self.start_btn.pack(side='right', padx=4)               

    def update_display_status(self, disp_id, connected):
        try:
            color = "green" if connected else "red"
            if disp_id == 1:
                self.disp1_status_canvas.itemconfig(self.disp1_status_id, fill=color, outline=color)
            elif disp_id == 2:
                self.disp2_status_canvas.itemconfig(self.disp2_status_id, fill=color, outline=color)
        except:
            pass            

    def auto_check_displays(self):
        try:
            ports = self.usb.list_ports() if self.usb else []
            id1 = (
                self.display_port_a
                and self.display_port_a in ports
                and self.usb.display_a
                and self.usb.display_a.is_open
            )
        except:
            id1 = False

        try:
            id2 = (
                self.display_port_b
                and self.display_port_b in ports
                and self.usb.display_b
                and self.usb.display_b.is_open
            )
        except:
            id2 = False

        self.update_display_status(1, id1)
        self.update_display_status(2, id2)

    def auto_check_usb(self):
        """Automatic USB port check."""
        try:
            if self.usb:
                ports = self.usb.list_ports()
                if self.usb_port and (self.usb_port not in ports):
                    self.update_usb_status(False)
                else:
                    if self.usb_port:
                        self.update_usb_status(True)
                    else:
                        self.update_usb_status(False)
        except Exception:
            self.update_usb_status(False)

        # refresh for 1500 ms
        self.root.after(1500, self.auto_check_usb)
        self.root.after(1500, self.auto_check_displays)
        self.update_promo_button_state()

    def on_usb_line(self, line):
        line = line.strip().lower()
        self._log(f"USB RX: {repr(line)}")

        def gui():
            if line == "ok":
                self.status_var.set("Přijato OK")
                self.status_label.config(fg="green")   
                if self.enable_timer and self.timer_start_mode == "ok":
                    self.reset_led_times(1, 2)
                    self.start_countdown()
                    self.lap_time_a = 0
                    self.lap_time_b = 0
                    self.lap_time_a_var.set("A 00:00:000")
                    self.lap_time_b_var.set("B 00:00:000")
                    if self.lap_timer_enabled:
                        self.start_lap_timer()

            elif line == "finish_a":
                self.finish_a()
                self.send_display_latest(1, f"TXT:{self.format_display_time(self.lap_time_a)}")

            elif line == "finish_b":
                self.finish_b()
                self.send_display_latest(2, f"TXT:{self.format_display_time(self.lap_time_b)}")

            elif line == "race_finished":
                if self.view_mode == "playoff":
                    self.status_var.set("Závod dokončen")
                    self.status_label.config(fg="blue")
                else:
                    self.status_var.set("")
                self.timer_running = False
                self.lap_running_a = False
                self.lap_running_b = False
                self.race_active = False
                self.update_promo_button_state()
                if self.lap_after_id:
                    try:
                        self.root.after_cancel(self.lap_after_id)
                    except:
                        pass
                    self.lap_after_id = None

            elif line == "start_a":
                self._log("LAPS START A")
                if self.view_mode == "laps":
                    self.reset_led_times(1)
                    self.lap_label_a.config(fg="#FF8C00")
                    self.lap_time_a = 0
                    self.lap_running_a = True
                    self._log(f"lap_after_id={self.lap_after_id}")
                    self.start_laps_timer()

            elif line == "start_b":
                self._log("LAPS START B")
                if self.view_mode == "laps":
                    self.reset_led_times(2)
                    self.lap_label_b.config(fg="#FF8C00")
                    self.lap_time_b = 0
                    self.lap_running_b = True
                    self._log(f"lap_after_id={self.lap_after_id}")
                    self.start_laps_timer()

            elif line == "stop_a":
                self._log("LAPS STOP A")
                self.lap_running_a = False
                self.update_promo_button_state()
                if self.view_mode == "laps":
                    self.lap_label_a.config(fg="green")
                    from datetime import datetime
                    rec = {
                        "id": self.laps_active_team_a,
                        "ride": self.lap_id_a,
                        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                        "time": self.format_lap(self.lap_time_a),
                        "ms": self.lap_time_a,
                        "invalid": False,
                    }
                    self.laps_a.insert(0, rec)
                    self.lap_id_a += 1
                    self.redraw()
                    self.send_display_latest(1, f"TXT:{self.format_display_time(self.lap_time_a)}")

            elif line == "stop_b":
                self._log("LAPS STOP B")
                self.lap_running_b = False
                self.update_promo_button_state()
                if self.view_mode == "laps":
                    self.lap_label_b.config(fg="green")
                    from datetime import datetime
                    rec = {
                        "id": self.laps_active_team_a + 1,
                        "ride": self.lap_id_b,
                        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                        "time": self.format_lap(self.lap_time_b),
                        "ms": self.lap_time_b,
                        "invalid": False,
                    }
                    self.laps_b.insert(0, rec)
                    self.lap_id_b += 1
                    self.redraw() 
                    self.send_display_latest(2, f"TXT:{self.format_display_time(self.lap_time_b)}")

        self.root.after(0, gui)        

    def on_start(self):
        self.stop_promo()
        self.race_active = True
        self.update_promo_button_state()
        self.lap_label_a.config(fg="#FF8C00")
        self.lap_label_b.config(fg="#FF8C00")
        self._log(f"usb_port= {self.usb_port} usb_baud= {self.usb_baud} usb_timeout= {self.usb_timeout} usb obj existuje: {bool(self.usb)} timer_start_mode= {self.timer_start_mode}")

        # STOP old countdown
        try:
            self.timer_running = False
            if getattr(self, 'countdown_after_id', None):
                self.root.after_cancel(self.countdown_after_id)
                self.countdown_after_id = None
        except Exception:
            pass

        # STOP old lap timer
        try:
            self.lap_running_a = False
            self.lap_running_b = False
            if self.lap_after_id:
                self.root.after_cancel(self.lap_after_id)
                self.lap_after_id = None

        except Exception:
            pass

        self.start_btn.config(state='disabled')

        self.status_var.set('Odesílám...')
        self.status_label.config(fg='black')

        # ---------------------------------------------------------
        # CALLBACK FROM USB MODULE
        # ---------------------------------------------------------
        def on_result(ok, reason):
            def cb():
                if ok:
                    # START packet was successfully sent
                    # WAITING FOR "ok" FROM ARDUINO
                    self.status_var.set('START odeslán')
                    self.status_label.config(fg='orange')
                    self.update_usb_status(True)

                else:
                    if reason == 'timeout':
                        self.status_var.set('Chyba spojení (timeout)')
                    elif isinstance(reason, str) and reason.startswith('open_error'):
                        self.status_var.set('Chyba spojení (otevření portu)')
                    elif reason == 'pyserial_missing':
                        self.status_var.set('pyserial není nainstalován')
                    else:
                        self.status_var.set('Chyba spojení (neznámá chyba)')
                    self.status_label.config(fg='red')
                    self.timer_running = False
                    self.race_active = False
                    self.update_usb_status(False)
                    self.update_promo_button_state()

                self.start_btn.config(state='normal')

            try:
                self.root.after(0, cb)

            except Exception:
                pass

        # ---------------------------------------------------------
        # PREPARE TIMER DISPLAY
        # ---------------------------------------------------------
        try:

            if self.enable_timer:

                self.current_seconds = self.time_to_seconds(self.timer_value)

                self.timer_label.config(
                    text=self.seconds_to_time(self.current_seconds)
                )

                # START MODE = start
                if self.timer_start_mode == 'start':

                    self.start_countdown()

                    # reset lap timer
                    self.lap_time_a = 0
                    self.lap_time_b = 0

                    self.lap_time_a_var.set("A 00:00:000")
                    self.lap_time_b_var.set("B 00:00:000")
                    self.reset_led_times(1, 2)

                    if self.lap_timer_enabled:
                        self.start_lap_timer()

                else:

                    # MODE "ok"
                    # only prepare display
                    # countdown starts after RX "ok"

                    self.timer_running = False

        except Exception as e:
            self._log("Timer prepare error:", e)

        # ---------------------------------------------------------
        # SEND START
        # ---------------------------------------------------------
        try:

            usb_available = bool(self.usb and self.usb_port)

            if usb_available:

                self.usb.validate_and_set(
                    self.usb_port,
                    self.usb_baud,
                    self.usb_timeout
                )

                self.usb.send_start_async(on_result)

                self.update_usb_status(True)

            else:

                self.status_var.set('Chyba spojení')
                self.status_label.config(fg='red')

                self.timer_running = False
                self.race_active = False

                self.update_usb_status(False)

                self.start_btn.config(state='normal')
                self.update_promo_button_state()

        except Exception as e:

            self.status_var.set(f'Chyba: {e}')
            self.status_label.config(fg='red')

            self.timer_running = False
            self.race_active = False

            self.start_btn.config(state='normal')
            self.update_promo_button_state()

            self.update_usb_status(False)

    def open_team_naming_dialog(self):
        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("Pojmenování týmů")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.geometry("1200x620")
        dlg.minsize(900, 420)

        # --- MAIN TEAM NAMES ---
        if not hasattr(self, "team_names"):
            self.team_names = []
        self.team_names = normalize_team_records(self.team_names)

        # --- SCROLL ---
        container = tk.Frame(dlg)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        scroll_frame.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        )

        # --- HEADS ---
        headers = ("ID týmu", "Škola / adresa školy", "Jméno soutěžícího", "Nejlepší čas jízdy", "Akce")
        for column, header in enumerate(headers):
            tk.Label(scroll_frame, text=header, font=("Arial", 10, "bold")).grid(row=0, column=column, padx=5, pady=5)

        row_widgets = []

        def refresh_table():
            nonlocal row_widgets
            for w in row_widgets:
                for el in w:
                    el.destroy()
            row_widgets.clear()

            for i, item in enumerate(self.team_names):
                id_var = tk.StringVar(value=item.get("id", ""))
                school_var = tk.StringVar(value=item.get("school", ""))
                participant_var = tk.StringVar(value=item.get("participant", ""))
                best_time_var = tk.StringVar(value=item.get("best_time", ""))

                e1 = tk.Entry(scroll_frame, textvariable=id_var, width=10)
                e2 = tk.Entry(scroll_frame, textvariable=school_var, width=52)
                e3 = tk.Entry(scroll_frame, textvariable=participant_var, width=30)
                e4 = tk.Entry(scroll_frame, textvariable=best_time_var, width=16)

                e1.grid(row=i+1, column=0, padx=5, pady=2)
                e2.grid(row=i+1, column=1, padx=5, pady=2)
                e3.grid(row=i+1, column=2, padx=5, pady=2)
                e4.grid(row=i+1, column=3, padx=5, pady=2)

                def make_delete(idx):
                    return lambda: delete_row(idx)

                btn_del = tk.Button(scroll_frame, text="Smazat", command=make_delete(i))

                btn_del.grid(row=i+1, column=4, padx=5)

                def make_trace(index, var_id, var_school, var_participant, var_best_time):
                    def tracer(*args):
                        self.team_names[index]["id"] = var_id.get()
                        self.team_names[index]["school"] = var_school.get()
                        self.team_names[index]["participant"] = var_participant.get()
                        self.team_names[index]["best_time"] = var_best_time.get()
                    return tracer

                trace = make_trace(i, id_var, school_var, participant_var, best_time_var)
                for variable in (id_var, school_var, participant_var, best_time_var):
                    variable.trace_add("write", trace)

                row_widgets.append((e1, e2, e3, e4, btn_del))

        def add_row():
            self.team_names.append(normalize_team_record({}))
            refresh_table()

        def delete_row(index):
            if index < 0 or index >= len(self.team_names):
                return
            self.team_names.pop(index)
            refresh_table()

        def clear_all_rows():
            if not messagebox.askyesno("Potvrzení", "Opravdu chceš smazat všechny záznamy?"):
                return
            self.team_names.clear()
            refresh_table()

        def export_to_excel():
            if not self.team_names:
                messagebox.showinfo("Info", "Nejsou žádná data k exportu.")
                return

            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")]
            )
            if not path:
                return

            wb = Workbook()
            ws = wb.active
            ws.title = "Pojmenování týmů"

            ws.append(["ID týmu", "Škola / adresa školy", "Jméno soutěžícího", "Nejlepší čas jízdy"])

            for item in self.team_names:
                record = normalize_team_record(item)
                ws.append([record[field] for field in TEAM_RECORD_FIELDS])

            wb.save(path)
            messagebox.showinfo("Hotovo", f"Export dokončen:\n{path}")

        def import_from_excel():
            path = filedialog.askopenfilename(
                filetypes=[("Excel", "*.xlsx")]
            )
            if not path:
                return

            wb = load_workbook(path)
            ws = wb.active

            self.team_names.clear()

            for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
                if not any(value is not None for value in row):
                    continue
                self.team_names.append(team_record_from_excel_row(row))

            refresh_table()

        # --- BUTTONS ---
        btn_frame = tk.Frame(dlg)
        btn_frame.pack(fill="x", pady=8)

        tk.Button(btn_frame, text="Přidat řádek", command=add_row).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Smazat vše", command=clear_all_rows).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Import z Excelu", command=import_from_excel).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Export do Excelu", command=export_to_excel).pack(side="left", padx=5)

        def on_save():
            dlg.destroy()
            self.redraw()

        tk.Button(btn_frame, text="Uložit", command=on_save).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Storno", command=dlg.destroy).pack(side="right", padx=5)

        refresh_table()
        self.root.wait_window(dlg)


    # --- settings handlers ---
    def set_odd_behavior(self, mode):
        self.odd_behavior = mode
        self.odd_behavior_var.set(mode)
        self.redraw()

    def set_font_scale(self, size):
        self.font_scale = size
        self.font_scale_var.set(size)
        self.redraw()

    def choose_canvas_bg(self):
        c = colorchooser.askcolor()[1]
        if c:
            self.canvas_bg = c
            self.canvas.config(bg=self.canvas_bg)
            self.redraw()

    def set_line_width(self, w):
        self.line_width = w
        self.line_width_var.set(w)
        self.redraw()

    def toggle_lock_edit(self):
        self.lock_edit = not self.lock_edit
        messagebox.showinfo('Info', f'Zamknutí polí bylo provedeno: {self.lock_edit}')

    def set_timer_start_mode(self, mode):
        self.timer_start_mode = mode
        self.timer_start_mode_var.set(mode)

    def toggle_third_place(self):
        self.third_place_enabled = self.third_place_var.get()
        self.redraw()        

    # --- USB wrapper ---
    def open_usb_dialog(self):
        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("USB spojení")
        dlg.transient(self.root)
        dlg.grab_set()
        w = 860; h = 650
        x = (dlg.winfo_screenwidth()-w)//2; y = (dlg.winfo_screenheight()-h)//2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        content_frame = tk.Frame(dlg)
        content_frame.pack(fill="both", expand=True)
        settings_panel = tk.Frame(content_frame, width=520)
        settings_panel.pack(side="left", fill="both", expand=True)
        detected_panel = tk.LabelFrame(
            content_frame,
            text="Nalezená zařízení",
            padx=12,
            pady=10,
            width=310,
        )
        detected_panel.pack(side="right", fill="y", padx=(0, 12), pady=12)
        detected_panel.pack_propagate(False)
        detected_rows = tk.Frame(detected_panel)
        detected_rows.pack(fill="x")
        tk.Label(
            detected_panel,
            text="Oba Nano panely jsou stejné. ID-1 a ID-2 určuje pouze přiřazení vlevo.",
            justify="left",
            wraplength=275,
            fg="#555555",
        ).pack(side="bottom", fill="x", pady=(12, 0))

        # --- PORTS LIST ---
        if self.usb:
            ports = self.usb.list_ports()
        else:
            ports = []

        def selected_ports():
            return (
                normalize_usb_port_choice(port_var.get()),
                normalize_usb_port_choice(display_port_a_var.get()),
                normalize_usb_port_choice(display_port_b_var.get()),
            )

        def validate_port_assignments():
            gate_port, display_a_port, display_b_port = selected_ports()
            conflict = find_usb_port_conflict(
                gate_port,
                display_a_port,
                display_b_port,
            )
            if conflict:
                port, first_device, second_device = conflict
                messagebox.showerror(
                    "Port je již použitý",
                    f"Port {port} je zvolený pro zařízení „{first_device}“ i „{second_device}“.\n\n"
                    "Každé připojené zařízení musí mít vlastní COM port. U nepoužívaného zařízení zvolte „Nepoužívat“.",
                    parent=dlg,
                )
                return None
            return gate_port, display_a_port, display_b_port

        def selected_display_baud(id):
            value = baud_var_A.get() if id == 1 else baud_var_B.get()
            try:
                return int(value)
            except (TypeError, ValueError):
                messagebox.showerror(
                    "Neplatná rychlost",
                    f"Rychlost LED displeje ID-{id} musí být celé číslo.",
                    parent=dlg,
                )
                return None

        def test_display(id=0):
            try:
                if not self.usb:
                    raise RuntimeError("USB modul není dostupný.")

                ports_for_devices = validate_port_assignments()
                if ports_for_devices is None:
                    return

                display_ports = {1: ports_for_devices[1], 2: ports_for_devices[2]}
                ids = (1, 2) if id == 0 else (id,)
                for display_id in ids:
                    port = display_ports[display_id]
                    if not port:
                        if id != 0:
                            messagebox.showwarning(
                                "Displej není používán",
                                f"Pro LED displej ID-{display_id} je zvoleno „Nepoužívat“.",
                                parent=dlg,
                            )
                        continue
                    baud = selected_display_baud(display_id)
                    if baud is None:
                        return
                    command = "CLS" if id == 0 else f"TXT:ID-{display_id}"
                    if not self.usb.send_display_to_port(display_id, command, port, baud):
                        detail = self.usb.display_error(display_id)
                        raise RuntimeError(
                            f"LED displej ID-{display_id} se nepodařilo otevřít na portu {port}."
                            + (f"\n\n{detail}" if detail else "")
                        )

            except Exception as e:
                self._log(f"Display error {e}")
                messagebox.showerror("Displej chyba", str(e), parent=dlg)

        # --- GATE A/B device ---
        tk.Label(settings_panel, text="Měřící brána", font=("Arial",10,"bold")).pack(anchor='w', padx=10, pady=(12,0))
        port_var = tk.StringVar(value=self.usb_port)
        combo = ttk.Combobox(
            settings_panel,
            textvariable=port_var,
            values=[USB_PORT_DISABLED_LABEL, *ports],
            state="readonly",
            width=20
        )
        combo.pack(padx=10, pady=4)

        frame = tk.Frame(settings_panel)
        frame.pack(fill='x', padx=10)

        # --- Preselect current port if available ---
        if self.usb_port in ports:
            port_var.set(self.usb_port)
        else:
            port_var.set(USB_PORT_DISABLED_LABEL)

        # --- REFRESH BUTTON ---
        def refresh_ports():
            new = self.usb.list_ports() if self.usb else []

            choices = [USB_PORT_DISABLED_LABEL, *new]
            combo["values"] = choices
            display_combo_a["values"] = choices
            display_combo_b["values"] = choices

            for variable in (port_var, display_port_a_var, display_port_b_var):
                if normalize_usb_port_choice(variable.get()) not in new:
                    variable.set(USB_PORT_DISABLED_LABEL)
            update_detected_devices()

        tk.Button(frame, text='Obnovit', command=refresh_ports).pack(side='right', padx=6)

        # --- BAUD ---
        tk.Label(settings_panel, text="Baud (rychlost) — výchozí 115200:").pack(anchor='w', padx=10, pady=(8,0))
        baud_var = tk.StringVar(value=str(self.usb_baud))
        tk.Entry(settings_panel, textvariable=baud_var, width=10).pack(padx=10, pady=4)

        # --- TIMEOUT ---
        tk.Label(settings_panel, text="Timeout (s) — výchozí 10.0:").pack(anchor='w', padx=10, pady=(8,0))
        to_var = tk.StringVar(value=str(self.usb_timeout))
        tk.Entry(settings_panel, textvariable=to_var, width=10).pack(padx=10, pady=4)

        # --- LED PANEL A ---
        ttk.Separator(settings_panel, orient="horizontal").pack(fill="x", padx=10, pady=8)
        tk.Label(settings_panel, text="LED displej ID-1",font=("Arial",10,"bold")).pack(anchor='w', padx=10, pady=(12,0))
        display_port_a_var = tk.StringVar(value=usb_port_choice(self.display_port_a))
        display_combo_a = ttk.Combobox(
            settings_panel,
            textvariable=display_port_a_var,
            values=[USB_PORT_DISABLED_LABEL, *ports],
            state="readonly",
            width=20
        )
        display_combo_a.pack(padx=10, pady=4)

        # --- BAUD LED A ---
        tk.Label(settings_panel, text="Baud (rychlost) — výchozí 115200:").pack(anchor='w', padx=10, pady=(8,0))
        baud_var_A = tk.StringVar(
            value=str(self.display_baud_a)
        )

        tk.Entry(
            settings_panel,
            textvariable=baud_var_A,
            width=10
        ).pack(padx=10, pady=4)

        # --- LED PANEL B ---
        ttk.Separator(settings_panel, orient="horizontal").pack(fill="x", padx=10, pady=8)
        tk.Label(settings_panel, text="LED displej ID-2",font=("Arial",10,"bold")).pack(anchor='w', padx=10, pady=(12,0))
        display_port_b_var = tk.StringVar(value=usb_port_choice(self.display_port_b))
        display_combo_b = ttk.Combobox(
            settings_panel,
            textvariable=display_port_b_var,
            values=[USB_PORT_DISABLED_LABEL, *ports],
            state="readonly",
            width=20
        )
        display_combo_b.pack(padx=10, pady=4)

        # --- BAUD LED B ---
        tk.Label(settings_panel, text="Baud (rychlost) — výchozí 115200:").pack(anchor='w', padx=10, pady=(8,0))
        baud_var_B = tk.StringVar(
            value=str(self.display_baud_b)
        )

        tk.Entry(
            settings_panel,
            textvariable=baud_var_B,
            width=10
        ).pack(padx=10, pady=4)        

        def update_detected_devices():
            for child in detected_rows.winfo_children():
                child.destroy()

            details = self.usb.list_port_details() if self.usb else []
            gate_port, display_a_port, display_b_port = selected_ports()
            detected = classify_usb_devices(
                details,
                gate_port,
                display_a_port,
                display_b_port,
            )

            def add_row(text, color="#222222"):
                tk.Label(
                    detected_rows,
                    text=text,
                    justify="left",
                    anchor="w",
                    fg=color,
                    wraplength=275,
                ).pack(fill="x", pady=3)

            configured_gate = detected["gate"]
            if configured_gate["port"]:
                status = "nalezeno" if configured_gate["found"] else "nenalezeno"
                color = "#147a24" if configured_gate["found"] else "#b00020"
                add_row(f"Brána: {configured_gate['port']} ({status})", color)
            else:
                for port in detected["detected_gates"]:
                    add_row(f"Brána: {port} (Arduino Mega)", "#147a24")

            for port in detected["detected_displays"]:
                add_row(f"LED displej: {port}", "#147a24")

            configured_display_ports = {
                detected["display_a"]["port"],
                detected["display_b"]["port"],
            }
            for key in ("display_a", "display_b"):
                item = detected[key]
                if item["port"] and not item["found"]:
                    add_row(f"LED displej: {item['port']} (nenalezeno)", "#b00020")

            for item in detected["unassigned"]:
                port = str(item.get("device") or "")
                description = str(item.get("description") or "Sériové zařízení")
                if port in configured_display_ports:
                    continue
                add_row(f"Neurčeno: {port}\n{description}", "#555555")

            if not detected_rows.winfo_children():
                add_row("Nebylo nalezeno žádné sériové zařízení.", "#777777")

        for port_combo in (combo, display_combo_a, display_combo_b):
            port_combo.bind(
                "<<ComboboxSelected>>",
                lambda _event: update_detected_devices(),
            )
        update_detected_devices()

        ttk.Separator(settings_panel, orient="horizontal").pack(fill="x", padx=10, pady=8)

        # --- TEST BUTTONS ---
        test_frame = tk.Frame(settings_panel)
        test_frame.pack(pady=10)

        tk.Button(
            test_frame,
            text="TEST ID-1",
            width=12,
            command=lambda: test_display(1)
        ).pack(side="left", padx=5)

        tk.Button(
            test_frame,
            text="TEST ID-2",
            width=12,
            command=lambda: test_display(2)
        ).pack(side="left", padx=5) 

        tk.Button(
            test_frame,
            text="SMAZAT",
            width=12,
            command=lambda: test_display(0)
        ).pack(side="left", padx=5)                      

        ttk.Separator(settings_panel, orient="horizontal").pack(fill="x", padx=10, pady=8)
        # --- OK HANDLER ---
        def on_ok():
            ports_for_devices = validate_port_assignments()
            if ports_for_devices is None:
                return

            self.usb_port, self.display_port_a, self.display_port_b = ports_for_devices
            self.update_display_status(1, bool(self.display_port_a))
            self.update_display_status(2, bool(self.display_port_b))            

            try:
                self.usb_baud = int(baud_var.get())
            except:
                self.usb_baud = DEFAULT_USB_BAUD

            try:
                self.display_baud_a = int(baud_var_A.get())
            except:
                self.display_baud_a = DEFAULT_USB_DISPLAY_A_BAUD

            try:
                self.display_baud_b = int(baud_var_B.get())
            except:
                self.display_baud_b = DEFAULT_USB_DISPLAY_B_BAUD                               

            try:
                self.usb_timeout = float(to_var.get())
            except:
                self.usb_timeout = DEFAULT_USB_TIMEOUT

            # save settings
            try:
                spath = os.path.join(os.path.expanduser('~'), '.playoff_settings.json')
                data = {}
                if os.path.exists(spath):
                    try:
                        with open(spath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    except:
                        data = {}

                data['usb_port'] = self.usb_port
                data['usb_baud'] = self.usb_baud
                data['usb_timeout'] = self.usb_timeout
                data['display_port_a'] = self.display_port_a
                data['display_port_b'] = self.display_port_b
                data['display_baud_a'] = self.display_baud_a
                data['display_baud_b'] = self.display_baud_b
                data['view_mode'] = self.view_mode

                with open(spath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except:
                pass

            # validate port
            try:
                if self.usb:
                    self.usb.validate_and_set(self.usb_port, self.usb_baud, self.usb_timeout)
                    self.update_usb_status(self.usb.reconnect(self.on_usb_line))
            except Exception as e:
                messagebox.showwarning("USB", f"Port nastaven, ale spojení selhalo:\n{e}")
                self.update_usb_status(False)

            try:
                display_results = self.usb.connect_displays()
                display_ports = {
                    1: self.display_port_a,
                    2: self.display_port_b,
                }
                failures = []
                for display_id, port in display_ports.items():
                    if port and not display_results[display_id]:
                        detail = self.usb.display_error(display_id)
                        failures.append(
                            f"LED displej ID-{display_id} ({port})"
                            + (f": {detail}" if detail else "")
                        )

                if failures:
                    messagebox.showerror(
                        "Displej se nepodařilo připojit",
                        "Nastavení bylo uloženo, ale připojení selhalo:\n\n"
                        + "\n".join(failures)
                        + "\n\nZkontrolujte, zda port nepoužívá jiné zařízení nebo jiná spuštěná aplikace.",
                        parent=dlg,
                    )
                    return

                if self.display_port_a:
                    self.root.after(
                        2500,
                        lambda: self.usb.send_display(1, "TXT:ID-1")
                    )
                    self.root.after(
                        7000,
                        lambda: self.usb.send_display(1, "TXT:-------")
                    )
                if self.display_port_b:
                    self.root.after(
                        2600,
                        lambda: self.usb.send_display(2, "TXT:ID-2")
                    )
                    self.root.after(
                        7200,
                        lambda: self.usb.send_display(2, "TXT:-------")
                    )
            except Exception as e:
                messagebox.showerror(
                    "Displej chyba",
                    f"Nastavení bylo uloženo, ale displeje se nepodařilo připojit:\n\n{e}",
                    parent=dlg,
                )
                return

            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        # --- BUTTONS ---
        btnf = tk.Frame(settings_panel)
        btnf.pack(pady=8)
        tk.Button(btnf, text='OK', width=10, command=on_ok).pack(side='left', padx=6)
        tk.Button(btnf, text='Zrušit', width=10, command=on_cancel).pack(side='left', padx=6)

        dlg.bind('<Return>', lambda e: on_ok())
        dlg.bind('<Escape>', lambda e: on_cancel())
        self.root.wait_window(dlg)


    # --- bracket generation (exact number of teams) ---
    def generate_bracket_with_empty(self, n):
        # create list of n empty slots
        team_list = [""] * int(max(0, n))
        use_pre_round=self.pre_round_enabled
        if use_pre_round:
            pre_round_list = [""] * int(max(0, n))
        else:
            pre_round_list = []   
        self.bracket = Bracket(team_list, pre_round_list=pre_round_list, use_pre_round=use_pre_round)
        # resolve automatic BYE if requested
        if self.odd_behavior == 'auto':
            self._auto_resolve_byes()
        self.redraw()

    def generate_from_entry(self):
        try:
            n = int(self.team_var.get())
            if n < 1:
                raise ValueError('Musí být alespoň 1 tým')
            self.generate_bracket_with_empty(n)
        except Exception:
            messagebox.showerror("Chyba", "Počet týmů není platné číslo.")

    # --- save / load setup ---
    def save_setup(self):
        self._log("SAVE_SETUP CALLED")
        fname = filedialog.asksaveasfilename(defaultextension='.setup', filetypes=[('Playoff setup', '.setup'), ('JSON', '.json')])

        if not fname:
            return

        if self.bracket:
            team_count = self.bracket.team_count
            titles = self.bracket.titles
            pre_titles = self.bracket.pre_titles
        else:
            team_count = 0
            titles = []
            pre_titles = []

        self._store_active_laps_pair()
        data = {
            'team_count': team_count,
            'odd_behavior': self.odd_behavior,
            'font_scale': self.font_scale,
            'canvas_bg': self.canvas_bg,
            'line_width': self.line_width,
            'bg_path': self.bg_path,
            'lock_edit': self.lock_edit,
            'titles': titles,
            'rounds': [],
            'winner': self.current_winner,
            'enable_timer': self.enable_timer,
            'timer_value': self.timer_value, 
            'timer_start_mode': self.timer_start_mode,
            'pre_round_enabled': self.pre_round_enabled,                       
            # USB fields
            'usb_port': self.usb_port,
            'usb_baud': self.usb_baud,
            'usb_timeout': self.usb_timeout,
            # USB LED panels fields
            'display_port_a': self.display_port_a,
            'display_port_b': self.display_port_b,
            'display_baud_a': self.display_baud_a,
            'display_baud_b': self.display_baud_b,
            # mode (playoff/laps)
            'view_mode': self.view_mode,
            # TEAMS names
            'team_names': normalize_team_records(self.team_names),
            'team_table_title': self.team_table_title,
            'team_table_headers': self.get_team_table_headers(),
            # THIRD place
            'third_place_enabled': self.third_place_enabled,
            'third_place': self.third_place,
            'third_place_title': self.third_place_title,
            # PRE ROUNDS
            'pre_titles': pre_titles,
            'pre_rounds': [],
            'lap_timer_enabled': self.lap_timer_enabled,
            'live_led_enabled': self.live_led_enabled,
            'live_led_refresh': self.live_led_refresh,
            'promo_text': self.promo_text,
            'promo_mode': self.promo_mode,
            'promo_scroll_ms': self.promo_scroll_ms,
            'laps_max_teams': self.laps_max_teams,
            'laps_active_team_a': self.laps_active_team_a,
            'laps_teams': self.laps_teams,
        }
        if (self.bracket and self.pre_round_enabled and self.bracket.pre_rounds):
            data['pre_rounds'] = [
                [
                    {
                        'a': m.a.text,
                        'b': m.b.text
                    }
                    for m in self.bracket.pre_rounds[0]
                ]
            ]
        if self.bracket:
            for r in self.bracket.rounds:
                rd = []
                for m in r:
                    rd.append({'a': m.a.text, 'b': m.b.text})
                data['rounds'].append(rd)
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo('Hotovo', f'Soubor byl uložen: {fname}')
        except Exception as e:
            messagebox.showerror('Chyba', str(e))

    def load_setup(self):
        self._log("LOAD setup.json")
        fname = filedialog.askopenfilename(filetypes=[('Playoff setup', '.setup .json')])
        if not fname:
            return
        try:
            with open(fname, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror('Chyba', f'Nepodařilo se načíst soubor: {e}')
            self._log('Chyba', f'Nepodařilo se načíst soubor: {e}')
            return
        self.stop_countdowns_for_mode_change()
        # rebuild bracket with exact count
        n = data.get('team_count', 0)
        self.odd_behavior = data.get('odd_behavior', 'manual')
        self.font_scale = data.get('font_scale', 'medium')
        self.canvas_bg = data.get('canvas_bg', CANVAS_BG_DEFAULT)
        self.line_width = data.get('line_width', 2)
        self.line_width_var.set(self.line_width)
        self.bg_path = data.get('bg_path')
        self.lock_edit = data.get('lock_edit', False)
        self.canvas.config(bg=self.canvas_bg)
        self.enable_timer = data.get('enable_timer', getattr(self, 'enable_timer', True))
        self.timer_value = data.get('timer_value', getattr(self, 'timer_value', '05:00'))
        if not self.validate_time_format(str(self.timer_value)):
            self.timer_value = '05:00'
        self.timer_value = str(self.timer_value)
        self.laps_countdown_seconds = self.time_to_seconds(self.timer_value)
        self.timer_start_mode = data.get('timer_start_mode', 'start')
        self.timer_start_mode_var.set(self.timer_start_mode)
        self.team_names = normalize_team_records(data.get('team_names', []))
        self.team_table_title = str(data.get('team_table_title', TEAM_TABLE_DEFAULT_TITLE) or TEAM_TABLE_DEFAULT_TITLE)
        self.team_table_headers = normalize_team_table_headers(data.get('team_table_headers'))
        self.pre_round_enabled = data.get('pre_round_enabled', True)
        self.pre_round_var.set(self.pre_round_enabled)
        self.third_place_enabled = data.get('third_place_enabled', False)
        self.third_place_var.set(self.third_place_enabled)
        self.third_place = data.get('third_place', {"a": "", "b": "", "winner": ""})
        self.third_place_title = data.get('third_place_title', "3. místo")
        self.lap_timer_enabled = data.get('lap_timer_enabled', False)
        self.lap_timer_var.set(self.lap_timer_enabled)
        self.live_led_enabled = bool(data.get('live_led_enabled', False))
        self.live_led_var.set(self.live_led_enabled)
        self.live_led_refresh = normalize_led_refresh(
            data.get('live_led_refresh', DEFAULT_LED_REFRESH)
        )
        self.live_led_refresh_var.set(f"{self.live_led_refresh:.1f}")
        self.reset_live_led_schedule(1, 2)
        promo_valid, promo_text, _promo_error = validate_promo_text(
            data.get('promo_text', self.promo_text)
        )
        self.promo_text = promo_text if promo_valid else ""
        self.promo_mode = normalize_promo_mode(
            data.get('promo_mode', self.promo_mode)
        )
        self.promo_scroll_ms = normalize_promo_scroll_ms(
            data.get('promo_scroll_ms', self.promo_scroll_ms)
        )
        self.promo_active = False
        self.promo_scroll_position = 0
        self.promo_after_id = None
        self._restore_laps_history(
            data.get('laps_teams', {}),
            data.get('laps_max_teams', DEFAULT_LAPS_MAX_TEAMS),
            data.get('laps_active_team_a', 1),
        )
        self.display_port_a = data.get('display_port_a', self.display_port_a)
        self.display_port_b = data.get('display_port_b', self.display_port_b)
        self.display_baud_a = data.get('display_baud_a', self.display_baud_a)
        self.display_baud_b = data.get('display_baud_b', self.display_baud_b)
        self.view_mode = data.get('view_mode', 'playoff')
        self.view_mode_var.set(self.view_mode)
        self.update_view_mode_gui()
        self.update_view_mode_buttons()
        self.update_promo_button_state()
        # apply UI lap timer state
        self.apply_lap_timer_visibility()
        self.generate_bracket_with_empty(n)

        # --- LOAD PRE ROUND ---
        pre_titles = data.get('pre_titles', [])
        pre_rounds = data.get('pre_rounds', [])

        if self.pre_round_enabled and pre_rounds:
            if not self.bracket.pre_rounds:
                self.bracket._build_pre([""] * n)

            self.bracket.pre_titles = pre_titles if pre_titles else ["Předkolo"]

            for m_idx, mdata in enumerate(pre_rounds[0]):
                if m_idx < len(self.bracket.pre_rounds[0]):
                    self.bracket.pre_rounds[0][m_idx].a.text = mdata.get('a', '')
                    self.bracket.pre_rounds[0][m_idx].b.text = mdata.get('b', '')
        try:
            # ensure timer menu var exists
            self.timer_menu_var.set(self.enable_timer)
        except Exception:
            pass
        # update timer display/visibility
        try:
            self.timer_label.config(text=self.timer_value)
            self.update_timer_visibility()
        except Exception:
            pass

        # rebuild rounds exactly as in setup
        rounds_in = data.get('rounds', [])
        if rounds_in:
            self.bracket.rounds = []
            for rdata in rounds_in:
                round_list = []
                for m in rdata:
                    a = Slot(m.get('a', ''))
                    b = Slot(m.get('b', ''))
                    round_list.append(Match(a, b))
                self.bracket.rounds.append(round_list)

        # load titles
        titles = data.get('titles', [])
        for i, t in enumerate(titles):
            if i < len(self.bracket.titles):
                self.bracket.titles[i] = t
        if self.bracket.rounds:
            if len(self.bracket.rounds[-1]) > 1:
                self.bracket.rounds[-1] = [self.bracket.rounds[-1][0]]

        # load rounds text
        rounds_in = data.get('rounds', [])
        for r_idx, rd in enumerate(rounds_in):
            if r_idx >= len(self.bracket.rounds):
                break
            matches = self.bracket.rounds[r_idx]
            for m_idx, mdata in enumerate(rd):
                if m_idx >= len(matches):
                    break
                matches[m_idx].a.text = mdata.get('a', '')
                matches[m_idx].b.text = mdata.get('b', '')

        # try load bg image if exists
        if self.bg_path and PIL_AVAILABLE and os.path.exists(self.bg_path):
            try:
                self.bg_image = Image.open(self.bg_path).convert('RGBA')
            except Exception:
                self.bg_image = None

        self.current_winner = data.get('winner', '')
        
        # load USB fields if present in setup file
        self.usb_port = data.get('usb_port', self.usb_port)
        self.usb_baud = data.get('usb_baud', self.usb_baud)
        self.usb_timeout = data.get('usb_timeout', self.usb_timeout)
        if self.usb:
            try:
                self.usb.validate_and_set(self.usb_port, self.usb_baud, self.usb_timeout)
                if self.usb_port:
                    self.update_usb_status(True)
                else:
                    self.update_usb_status(False)
            except Exception:
                self.update_usb_status(False)

        self.root.update_idletasks()
        self.root.after(50, self.redraw)
        messagebox.showinfo('Hotovo', 'Soubor byl načten')
        self._log('Hotovo', 'Soubor byl načten')

    # --- Timer methods (MM:SS input, countdown, blinking) ---
    def stop_countdowns_for_mode_change(self):
        self.timer_running = False
        countdown_after_id = getattr(self, 'countdown_after_id', None)
        if countdown_after_id:
            try:
                self.root.after_cancel(countdown_after_id)
            except Exception:
                pass
            self.countdown_after_id = None
        self.stop_blinking()
        self.stop_laps_countdown(reset=True)
        self.update_promo_button_state()

    def on_toggle_timer(self):
        self.enable_timer = self.timer_menu_var.get()
        # persist small settings to user home file
        try:
            spath = os.path.join(os.path.expanduser('~'), '.playoff_settings.json')
            data = {}
            if os.path.exists(spath):
                try:
                    with open(spath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data['enable_timer'] = self.enable_timer
            data['timer_value'] = self.timer_value
            with open(spath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        try:
            self.update_timer_visibility()
        except Exception:
            pass

        if self.view_mode == "laps":
            self.stop_laps_countdown(reset=True)

        self.redraw()

    def on_toggle_lap_timer(self):
        self.lap_timer_enabled = self.lap_timer_var.get()

        self.apply_lap_timer_visibility()

        # save to file
        self.persist_user_settings(
            lap_timer_enabled=self.lap_timer_enabled
        )

    def apply_lap_timer_visibility(self):
        if self.lap_timer_enabled:
            self.lap_label_a.pack(side='left', padx=(10, 5))
            self.lap_label_b.pack(side='left', padx=(0, 20))
        else:
            self.lap_label_a.pack_forget()
            self.lap_label_b.pack_forget()

    def on_toggle_live_led(self):
        self.live_led_enabled = bool(self.live_led_var.get())
        self.reset_live_led_schedule(1, 2)
        self.persist_user_settings(
            live_led_enabled=self.live_led_enabled,
            live_led_refresh=self.live_led_refresh
        )

    def on_set_live_led_refresh(self):
        self.live_led_refresh = normalize_led_refresh(
            self.live_led_refresh_var.get()
        )
        self.live_led_refresh_var.set(f"{self.live_led_refresh:.1f}")
        self.reset_live_led_schedule(1, 2)
        self.persist_user_settings(
            live_led_enabled=self.live_led_enabled,
            live_led_refresh=self.live_led_refresh
        )

    def open_promo_text_dialog(self):
        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("Propagační text")
        dlg.transient(self.root)
        dlg.grab_set()
        w, h = 620, 360
        x = (dlg.winfo_screenwidth() - w) // 2
        y = (dlg.winfo_screenheight() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(
            dlg,
            text="Vložte text pro propagaci:",
            font=("Arial", 11, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 5))
        text_var = tk.StringVar(value=self.promo_text)
        entry = tk.Entry(dlg, textvariable=text_var, width=58, font=("Arial", 11))
        entry.pack(fill="x", padx=18)
        entry.select_range(0, "end")
        entry.focus_set()
        tk.Label(
            dlg,
            text=f"Například ROBO2026. Nejvýše {PROMO_TEXT_MAX_LENGTH} znaků bez diakritiky; prázdný text PROMO vypne.",
            fg="#555555",
            wraplength=480,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(6, 10))

        tk.Label(
            dlg,
            text="Způsob zobrazení:",
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", padx=18, pady=(2, 4))
        mode_by_label = {label: mode for mode, label in PROMO_MODE_LABELS.items()}
        mode_var = tk.StringVar(value=PROMO_MODE_LABELS[self.promo_mode])
        mode_combo = ttk.Combobox(
            dlg,
            textvariable=mode_var,
            values=list(mode_by_label),
            state="readonly",
            width=58,
        )
        mode_combo.pack(fill="x", padx=18)

        speed_label_var = tk.StringVar()
        speed_var = tk.IntVar(value=self.promo_scroll_ms)

        def update_speed_label(*_args):
            interval = normalize_promo_scroll_ms(speed_var.get())
            speed_label_var.set(
                f"Rychlost posuvu: {1000 / interval:.1f} znaků/s ({interval} ms)"
                .replace(".", ",")
            )

        tk.Label(
            dlg,
            textvariable=speed_label_var,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", padx=18, pady=(12, 0))
        speed_scale = tk.Scale(
            dlg,
            from_=PROMO_SCROLL_MAX_MS,
            to=PROMO_SCROLL_MIN_MS,
            resolution=PROMO_SCROLL_STEP_MS,
            orient="horizontal",
            variable=speed_var,
            command=update_speed_label,
            showvalue=False,
            length=560,
        )
        speed_scale.pack(fill="x", padx=18)
        speed_ends = tk.Frame(dlg)
        speed_ends.pack(fill="x", padx=22)
        tk.Label(speed_ends, text="Pomaleji", fg="#555555").pack(side="left")
        tk.Label(speed_ends, text="Rychleji", fg="#555555").pack(side="right")
        tk.Label(
            dlg,
            text="Rychlost platí pro plynulou rotaci i rolování řízené panelem.",
            fg="#555555",
        ).pack(anchor="w", padx=18, pady=(2, 4))
        update_speed_label()

        def save_text():
            valid, promo_text, error = validate_promo_text(text_var.get())
            if not valid:
                messagebox.showerror("Neplatný propagační text", error, parent=dlg)
                return
            self.stop_promo()
            self.promo_text = promo_text
            self.promo_mode = mode_by_label.get(
                mode_var.get(),
                DEFAULT_PROMO_MODE,
            )
            self.promo_scroll_ms = normalize_promo_scroll_ms(speed_var.get())
            self.persist_user_settings(
                promo_text=self.promo_text,
                promo_mode=self.promo_mode,
                promo_scroll_ms=self.promo_scroll_ms,
            )
            self.update_promo_button_state()
            dlg.destroy()

        buttons = tk.Frame(dlg)
        buttons.pack(pady=4)
        tk.Button(buttons, text="Uložit", width=12, command=save_text).pack(side="left", padx=5)
        tk.Button(buttons, text="Zrušit", width=12, command=dlg.destroy).pack(side="left", padx=5)
        dlg.bind("<Return>", lambda _event: save_text())
        dlg.bind("<Escape>", lambda _event: dlg.destroy())
        self.root.wait_window(dlg)

    def is_timing_active(self):
        return any((
            bool(getattr(self, "race_active", False)),
            bool(getattr(self, "timer_running", False)),
            bool(getattr(self, "laps_countdown_running", False)),
            bool(getattr(self, "lap_running_a", False)),
            bool(getattr(self, "lap_running_b", False)),
        ))

    def configured_display_ids(self):
        result = []
        if str(getattr(self, "display_port_a", "") or "").strip():
            result.append(1)
        if str(getattr(self, "display_port_b", "") or "").strip():
            result.append(2)
        return result

    def update_promo_button_state(self):
        button = getattr(self, "promo_btn", None)
        if button is None:
            return
        active = bool(getattr(self, "promo_active", False))
        enabled = bool(
            active
            or (
                getattr(self, "promo_text", "")
                and getattr(self, "usb", None)
                and self.configured_display_ids()
                and not self.is_timing_active()
            )
        )
        button.config(
            state="normal" if enabled else "disabled",
            relief="sunken" if active else "raised",
            bg="#FF9800" if active else self.root.cget("bg"),
            fg="white" if active else "black",
        )

    def start_promo(self):
        if self.is_timing_active():
            messagebox.showwarning(
                "PROMO není dostupné",
                "Propagační text nelze spustit, dokud běží odpočet nebo měření času.",
            )
            self.update_promo_button_state()
            return False
        if not self.promo_text:
            messagebox.showwarning(
                "Chybí propagační text",
                "Nejprve nastavte text v nabídce Nastavení → Nastavit propagační text.",
            )
            return False
        if not self.usb:
            messagebox.showerror("PROMO chyba", "USB modul není dostupný.")
            return False

        self.promo_mode = normalize_promo_mode(self.promo_mode)
        self.promo_scroll_ms = normalize_promo_scroll_ms(self.promo_scroll_ms)
        if self.promo_mode == "continuous":
            initial_text = promo_display_window(self.promo_text, 0)
            command = f"TXT:{initial_text}"
        elif self.promo_mode == "static":
            command = f"TXT:{self.promo_text[:7]}"
        else:
            command = f"SCR:{self.promo_text}"

        sent_to = []
        for display_id in self.configured_display_ids():
            if self.promo_mode == "firmware":
                self.usb.send_display(
                    display_id,
                    f"SPD:{self.promo_scroll_ms}",
                )
            if self.usb.send_display(display_id, command):
                sent_to.append(display_id)
        if not sent_to:
            messagebox.showerror(
                "PROMO chyba",
                "Propagační text se nepodařilo odeslat na žádný LED displej.",
            )
            self.promo_active = False
            self.update_promo_button_state()
            return False

        self.promo_active = True
        self.promo_scroll_position = 1
        if self.promo_mode == "continuous":
            self.promo_after_id = self.root.after(
                self.promo_scroll_ms,
                self.promo_rotation_tick,
            )
        self.status_var.set("PROMO: " + self.promo_text)
        self.status_label.config(fg="#d26900")
        self.update_promo_button_state()
        return True

    def promo_rotation_tick(self):
        self.promo_after_id = None
        if (
            not bool(getattr(self, "promo_active", False))
            or normalize_promo_mode(getattr(self, "promo_mode", "")) != "continuous"
        ):
            return

        window = promo_display_window(
            self.promo_text,
            self.promo_scroll_position,
        )
        for display_id in self.configured_display_ids():
            self.send_display_latest(display_id, f"TXT:{window}")
        self.promo_scroll_position = (
            self.promo_scroll_position + 1
        ) % len(self.promo_text)
        self.promo_after_id = self.root.after(
            self.promo_scroll_ms,
            self.promo_rotation_tick,
        )

    def stop_promo(self):
        promo_after_id = getattr(self, "promo_after_id", None)
        if promo_after_id:
            try:
                self.root.after_cancel(promo_after_id)
            except Exception:
                pass
        self.promo_after_id = None

        if not bool(getattr(self, "promo_active", False)):
            self.update_promo_button_state()
            return False

        for display_id in self.configured_display_ids():
            self.send_display_latest(display_id, "CLS")
        self.promo_active = False
        status_var = getattr(self, "status_var", None)
        if status_var is not None and str(status_var.get()).startswith("PROMO:"):
            status_var.set("")
        self.update_promo_button_state()
        return True

    def toggle_promo(self):
        if self.promo_active:
            return self.stop_promo()
        return self.start_promo()

    def persist_user_settings(self, **updates):
        try:
            spath = os.path.join(os.path.expanduser('~'), '.playoff_settings.json')
            data = {}

            if os.path.exists(spath):
                try:
                    with open(spath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    data = {}

            data.update(updates)

            with open(spath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception:
            pass

    def update_timer_visibility(self):
        try:
            if getattr(self, 'timer_window', None) is None:
                return
            if self.enable_timer:
                self.canvas.itemconfigure(self.timer_window, state='normal')
            else:
                self.canvas.itemconfigure(self.timer_window, state='hidden')
        except Exception:
            try:
                if self.enable_timer:
                    self.timer_label.place(relx=0.98, rely=0.98, anchor='se')
                else:
                    self.timer_label.place_forget()
            except Exception:
                pass

    def update_timer_display(self):
        try:
            self.timer_label.config(text=self.timer_value, bg='black', fg='white')
        except Exception:
            pass

    def on_timer_left_click(self, event=None):
        if self.view_mode != "laps" or not self.enable_timer:
            return None
        self.start_laps_countdown()
        return "break"

    def on_timer_right_click(self, event=None):
        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title('Nastavení odpočtu')
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text='Zadejte čas ve formátu MM:SS').pack(padx=14, pady=(14, 4))
        value_var = tk.StringVar(value=getattr(self, 'timer_value', '05:00'))
        entry = tk.Entry(dlg, textvariable=value_var, width=15)
        entry.pack(padx=14, pady=4)
        entry.focus_set()

        def on_ok():
            val = value_var.get().strip()
            if not self.validate_time_format(val):
                messagebox.showerror('Chyba', 'Neplatný formát času. Použij MM:SS (např. 03:30).', parent=dlg)
                return
            self.timer_value = val
            if self.view_mode == "laps":
                self.stop_laps_countdown(reset=True)
            else:
                self.timer_label.config(text=self.timer_value)
            try:
                spath = os.path.join(os.path.expanduser('~'), '.playoff_settings.json')
                data = {}
                if os.path.exists(spath):
                    with open(spath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                data['timer_value'] = self.timer_value
                with open(spath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            dlg.destroy()

        buttons = tk.Frame(dlg)
        buttons.pack(pady=(6, 14))
        tk.Button(buttons, text='OK', width=10, command=on_ok).pack(side='left', padx=6)
        tk.Button(buttons, text='Zrušit', width=10, command=dlg.destroy).pack(side='left', padx=6)
        dlg.bind('<Return>', lambda _event: on_ok())
        dlg.bind('<Escape>', lambda _event: dlg.destroy())
        self.root.wait_window(dlg)

    def start_laps_countdown(self):
        self.stop_promo()
        if self.view_mode != "laps" or not self.enable_timer:
            return False

        maximum = self.time_to_seconds(self.timer_value)
        if maximum <= 0:
            self.stop_laps_countdown(reset=True)
            messagebox.showerror(
                'Chyba',
                'Pro opakovaný odpočet nastav čas větší než 00:00.'
            )
            return False

        self.stop_laps_countdown(reset=False)
        self.laps_countdown_seconds = maximum
        self.laps_countdown_running = True
        self.update_promo_button_state()
        self.timer_label.config(
            text=self.seconds_to_time(self.laps_countdown_seconds),
            bg='black',
            fg='white'
        )
        self.laps_countdown_after_id = self.root.after(
            1000,
            self.laps_countdown_tick
        )
        return True

    def laps_countdown_tick(self):
        self.laps_countdown_after_id = None
        if (
            not self.laps_countdown_running
            or self.view_mode != "laps"
            or not self.enable_timer
        ):
            return

        maximum = self.time_to_seconds(self.timer_value)
        if maximum <= 0:
            self.stop_laps_countdown(reset=True)
            return

        cycle_restarted = self.laps_countdown_seconds <= 1
        if cycle_restarted:
            self.laps_countdown_seconds = maximum
            self.stop_laps_countdown_blink()
        else:
            self.laps_countdown_seconds -= 1

        self.timer_label.config(
            text=self.seconds_to_time(self.laps_countdown_seconds),
            fg='white'
        )
        if not cycle_restarted:
            self.update_laps_countdown_warning()
        self.laps_countdown_after_id = self.root.after(
            1000,
            self.laps_countdown_tick
        )

    def update_laps_countdown_warning(self):
        warning_active = (
            self.laps_countdown_running
            and 0 < self.laps_countdown_seconds <= LAPS_COUNTDOWN_WARNING
        )
        if warning_active:
            if self.laps_countdown_blink_after_id is None:
                self.laps_countdown_blink_state = False
                self.laps_countdown_blink_step()
        else:
            self.stop_laps_countdown_blink()

    def laps_countdown_blink_step(self):
        self.laps_countdown_blink_after_id = None
        if (
            not self.laps_countdown_running
            or self.view_mode != "laps"
            or not self.enable_timer
            or not (0 < self.laps_countdown_seconds <= LAPS_COUNTDOWN_WARNING)
        ):
            self.stop_laps_countdown_blink()
            return

        self.laps_countdown_blink_state = not self.laps_countdown_blink_state
        self.timer_label.config(
            bg='red' if self.laps_countdown_blink_state else 'black',
            fg='white'
        )
        self.laps_countdown_blink_after_id = self.root.after(
            LAPS_COUNTDOWN_BLINK_MS,
            self.laps_countdown_blink_step
        )

    def stop_laps_countdown_blink(self):
        blink_after_id = getattr(self, 'laps_countdown_blink_after_id', None)
        if blink_after_id:
            try:
                self.root.after_cancel(blink_after_id)
            except Exception:
                pass
        self.laps_countdown_blink_after_id = None
        self.laps_countdown_blink_state = False
        try:
            self.timer_label.config(bg='black', fg='white')
        except Exception:
            pass

    def stop_laps_countdown(self, reset=False):
        self.laps_countdown_running = False
        countdown_after_id = getattr(self, 'laps_countdown_after_id', None)
        if countdown_after_id:
            try:
                self.root.after_cancel(countdown_after_id)
            except Exception:
                pass
        self.laps_countdown_after_id = None
        self.stop_laps_countdown_blink()
        self.update_promo_button_state()

        if reset:
            self.laps_countdown_seconds = self.time_to_seconds(self.timer_value)
            try:
                self.timer_label.config(
                    text=self.seconds_to_time(self.laps_countdown_seconds),
                    bg='black',
                    fg='white'
                )
            except Exception:
                pass

    def validate_time_format(self, text):
        try:
            parts = text.split(':')
            if len(parts) != 2:
                return False
            m = int(parts[0]); s = int(parts[1])
            if m < 0 or s < 0 or s >= 60:
                return False
            return True
        except Exception:
            return False

    def time_to_seconds(self, t):
        parts = t.split(':')
        if len(parts) != 2:
            return 0
        return int(parts[0]) * 60 + int(parts[1])

    def seconds_to_time(self, sec):
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}"

    def start_countdown(self):
        self.stop_promo()
        try:
            # stop blinking if active
            self.stop_blinking()
        except Exception:
            pass
        try:
            if getattr(self, 'countdown_after_id', None):
                try:
                    self.root.after_cancel(self.countdown_after_id)
                except Exception:
                    pass
                self.countdown_after_id = None
        except Exception:
            self.countdown_after_id = None
        try:
            self.current_seconds = self.time_to_seconds(self.timer_value)
            self.timer_label.config(text=self.seconds_to_time(self.current_seconds))
            self.timer_running = True
            self.update_promo_button_state()
            # schedule tick
            self.countdown_after_id = self.root.after(1000, self.countdown_tick)
        except Exception:
            pass

    def countdown_tick(self):
        try:
            if not getattr(self, 'timer_running', False):
                return
            if self.current_seconds <= 0:
                self.timer_running = False
                self.lap_running_a = False
                self.lap_running_b = False
                self.update_promo_button_state()
                if self.lap_after_id:
                    try:
                        self.root.after_cancel(self.lap_after_id)
                    except:
                        pass
                self.start_blinking()
                return
            self.current_seconds -= 1
            try:
                self.timer_label.config(text=self.seconds_to_time(self.current_seconds))
            except Exception:
                pass
            self.countdown_after_id = self.root.after(1000, self.countdown_tick)
        except Exception:
            pass

    def start_blinking(self):
        try:
            self.timer_blink = True
            self.blink_state = False
            # kickoff blink loop
            self._blink_step()
        except Exception:
            pass

    def _blink_step(self):
        try:
            if not getattr(self, 'timer_blink', False):
                return
            self.blink_state = not getattr(self, 'blink_state', False)
            if self.blink_state:
                self.timer_label.config(bg='red', fg='white')
            else:
                self.timer_label.config(bg='white', fg='red')
            # schedule next
            self.blink_after_id = self.root.after(500, self._blink_step)
        except Exception:
            pass

    def stop_blinking(self):
        try:
            self.timer_blink = False
            if getattr(self, 'blink_after_id', None):
                try:
                    self.root.after_cancel(self.blink_after_id)
                except Exception:
                    pass
                self.blink_after_id = None
            self.timer_label.config(bg='black', fg='white')
        except Exception:
            pass


    def _auto_resolve_byes(self):
        """Automatic BYE teams"""
        rounds = self.bracket.rounds
        last_round_index = len(rounds) - 1  # poslední kolo je Vítěz

        for r_idx in range(len(rounds) - 1):
            if r_idx == last_round_index:
                continue

            matches = rounds[r_idx]

            for m_idx, match in enumerate(matches):

                a = match.a.text.strip()
                b = match.b.text.strip()

                if (a and not b) or (b and not a):
                    winner = a if a else b

                    next_index = m_idx // 2
                    next_match = rounds[r_idx + 1][next_index]
                    side = 'a' if (m_idx % 2 == 0) else 'b'

                    if side == 'a':
                        next_match.a.text = winner
                    else:
                        next_match.b.text = winner


    # --- editing title (wide dialog) ---                       
    def edit_title(self, r_idx):
        if self.lock_edit:
            return

        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title('Změnit nadpis')
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text='Nadpis:').pack(padx=10, pady=(10, 4))

        ent = tk.Entry(dlg, width=40)
        current = self.bracket.titles[r_idx] if r_idx < len(self.bracket.titles) else ""
        ent.insert(0, current)
        ent.pack(padx=10, pady=4)
        ent.focus_set()

        def on_ok():
            new_title = ent.get().strip()
            if r_idx < len(self.bracket.titles):
                self.bracket.titles[r_idx] = new_title
            dlg.destroy()
            self.redraw()

        def on_cancel():
            dlg.destroy()

        btns = tk.Frame(dlg)
        btns.pack(pady=10)
        tk.Button(btns, text="OK", width=10, command=on_ok).pack(side="left", padx=6)
        tk.Button(btns, text="Zrušit", width=10, command=on_cancel).pack(side="left", padx=6)

        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: on_cancel())

        self.root.wait_window(dlg)

    def edit_team_table_title(self):
        if self.lock_edit:
            return

        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("Změnit nadpis tabulky účastníků")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="Nadpis:").pack(padx=10, pady=(10, 4))
        ent = tk.Entry(dlg, width=40)
        ent.insert(0, getattr(self, "team_table_title", TEAM_TABLE_DEFAULT_TITLE))
        ent.pack(padx=10, pady=4)
        ent.focus_set()

        def on_ok():
            self.team_table_title = ent.get().strip() or TEAM_TABLE_DEFAULT_TITLE
            dlg.destroy()
            self.redraw()

        buttons = tk.Frame(dlg)
        buttons.pack(pady=10)
        tk.Button(buttons, text="OK", width=10, command=on_ok).pack(side="left", padx=6)
        tk.Button(buttons, text="Zrušit", width=10, command=dlg.destroy).pack(side="left", padx=6)
        dlg.bind("<Return>", lambda _event: on_ok())
        dlg.bind("<Escape>", lambda _event: dlg.destroy())
        self.root.wait_window(dlg)

    def get_team_table_headers(self):
        self.team_table_headers = normalize_team_table_headers(
            getattr(self, "team_table_headers", TEAM_TABLE_DEFAULT_HEADERS)
        )
        return self.team_table_headers

    def edit_team_table_header(self, index):
        if self.lock_edit:
            return

        headers = self.get_team_table_headers()
        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("Změnit záhlaví tabulky účastníků")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="Záhlaví:").pack(padx=10, pady=(10, 4))
        ent = tk.Entry(dlg, width=40)
        ent.insert(0, headers[index])
        ent.pack(padx=10, pady=4)
        ent.focus_set()

        def on_ok():
            headers[index] = ent.get().strip() or TEAM_TABLE_DEFAULT_HEADERS[index]
            self.team_table_headers = headers
            dlg.destroy()
            self.redraw()

        buttons = tk.Frame(dlg)
        buttons.pack(pady=10)
        tk.Button(buttons, text="OK", width=10, command=on_ok).pack(side="left", padx=6)
        tk.Button(buttons, text="Zrušit", width=10, command=dlg.destroy).pack(side="left", padx=6)
        dlg.bind("<Return>", lambda _event: on_ok())
        dlg.bind("<Escape>", lambda _event: dlg.destroy())
        self.root.wait_window(dlg)


    # --- editing UI (wide dialog) ---
    def edit_slot_dialog(self, r_idx, m_idx, side):
        if self.lock_edit:
            return
        m = self.bracket.rounds[r_idx][m_idx]
        slot = m.a if side == 'a' else m.b
        # create custom dialog
        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title('Zadej tým')
        dlg.transient(self.root)
        dlg.grab_set()
        w = 480
        h = 120
        x = (dlg.winfo_screenwidth() - w)//2
        y = (dlg.winfo_screenheight() - h)//2
        dlg.geometry(f'{w}x{h}+{x}+{y}')
        tk.Label(dlg, text='Zadej číslo nebo název týmu:').pack(anchor='w', padx=10, pady=(10,0))
        ent = tk.Entry(dlg, width=60)
        ent.pack(padx=10, pady=8)
        ent.insert(0, slot.text)
        ent.focus_set()
        def on_ok():
            slot.text = ent.get()
            dlg.destroy()
            self.redraw()
        def on_cancel():
            dlg.destroy()
        btnf = tk.Frame(dlg)
        btnf.pack(pady=6)
        tk.Button(btnf, text='OK', command=on_ok).pack(side='left', padx=8)
        tk.Button(btnf, text='Zrušit', command=on_cancel).pack(side='left')
        dlg.bind('<Return>', lambda e: on_ok())
        dlg.bind('<Escape>', lambda e: on_cancel())
        self.root.wait_window(dlg)

    def edit_winner_dialog(self):
        if self.lock_edit:
            return
        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("Zadat vítěze")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="Jméno / číslo vítěze:").pack(padx=10, pady=(10, 4))
        ent = tk.Entry(dlg, width=40)
        ent.pack(padx=10, pady=6)
        ent.insert(0, self.current_winner)
        ent.focus_set()

        def on_ok():
            new_val = ent.get().strip()

            last_round = len(self.bracket.rounds) - 1
            winner_match = self.bracket.rounds[last_round][0]

            winner_match.a.text = new_val
            winner_match.b.text = ""

            self.current_winner = new_val
            self.update_third_place_from_semifinal()
            dlg.destroy()
            self.redraw()

        def on_cancel():
            dlg.destroy()

        btn = tk.Frame(dlg)
        btn.pack(pady=10)
        tk.Button(btn, text="OK", command=on_ok).pack(side="left", padx=6)
        tk.Button(btn, text="Zrušit", command=on_cancel).pack(side="left", padx=6)

        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: on_cancel())

        self.root.wait_window(dlg)

    # --- promote (right-click) ---
    def promote(self, r_idx, m_idx, side):
        match = self.bracket.rounds[r_idx][m_idx]
        winner = match.a.text.strip() if side == 'a' else match.b.text.strip()

        if not winner:
            messagebox.showwarning('Upozornění', 'Pole je prázdné — nejdřív vyplň tým.')
            return

        if r_idx + 1 < len(self.bracket.rounds):
            next_index = m_idx // 2
            next_match = self.bracket.rounds[r_idx + 1][next_index]
            next_side = 'a' if (m_idx % 2 == 0) else 'b'
            target = next_match.a if next_side == 'a' else next_match.b

            if target.text:
                if not messagebox.askyesno('Přepsat?', 'V cílovém poli už něco je. Přepsat?'):
                    return

            target.text = winner
            self.update_third_place_from_semifinal()
            self.redraw()
            return

        winner_round_index = len(self.bracket.rounds) - 1   
        winner_match = self.bracket.rounds[winner_round_index][0]

        winner_match.a.text = winner
        winner_match.b.text = ""  

        self.update_third_place_from_semifinal()
        self.redraw()
        return

    def promote_third_place(self, side):
        val = self.third_place[side].strip()
        if not val:
            return

        if self.third_place["winner"]:
            if not messagebox.askyesno("Přepsat?", "Vítěz pro 3. místo už existuje. Přepsat?"):
                return

        self.third_place["winner"] = val
        self.redraw()    

    def edit_third_place_title(self):
        if self.lock_edit:
            return

        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("Nadpis 3. místa")

        ent = tk.Entry(dlg, width=30)
        ent.pack(padx=10, pady=10)
        ent.insert(0, self.third_place_title)
        ent.focus()

        def ok():
            self.third_place_title = ent.get()
            dlg.destroy()
            self.redraw()

        tk.Button(dlg, text="OK", command=ok).pack(pady=5)
        dlg.bind("<Return>", lambda e: ok())            

    # --- reset vs clear ---
    def reset_values(self):
        if not self.bracket:
            return
        # --- NORMAL ROUNDS ---
        for r in self.bracket.rounds:
            for m in r:
                m.a.text = ''
                m.b.text = ''
        # --- PRE ROUND ---
        if self.pre_round_enabled and self.bracket.pre_rounds:
            for r in self.bracket.pre_rounds:
                for m in r:
                    m.a.text = ''
                    m.b.text = ''
        # --- WINNER ---
        self.current_winner = ""
        # --- THIRD PLACE ---
        self.third_place = {"a": "", "b": "", "winner": ""}
        self.redraw()

    def clear_all(self):
        # clear everything: remove bracket and background; user must generate again
        self.clear_all_laps_history(confirm=False, redraw=False)
        self.bracket = None
        self.canvas.delete("all")
        self.bg_path = None
        self.bg_image = None
        self.bg_tk = None
        self.canvas_bg = CANVAS_BG_DEFAULT
        self.canvas.config(bg=self.canvas_bg)
        self.team_var.set('0')
        self.canvas.delete('all')

    # --- background functions ---
    def load_bg_image(self):
        if not PIL_AVAILABLE:
            messagebox.showerror('Chyba python Pillow', 'Pillow není nainstalován. Nainstaluj: pip install pillow')
            return
        path = filedialog.askopenfilename(title='Vyber obrázek', filetypes=[('Images','*.png;*.jpg;*.jpeg;*.bmp;*.gif')])
        if not path:
            return
        try:
            img = Image.open(path).convert('RGBA')
            self.bg_path = path
            self.bg_image = img
            self.bg_tk = None
            messagebox.showinfo('Načteno', f'Načteno: {os.path.basename(path)}')
            self.redraw()
        except Exception as e:
            messagebox.showerror('Chyba', str(e))

    def remove_bg(self):
        self.bg_path = None
        self.bg_image = None
        self.bg_tk = None
        self.redraw()
        messagebox.showinfo('Hotovo', 'Pozadí bylo odstraněno')

    # --- help ---
    def show_help(self):
        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("Nápověda – Playoff generátor")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.geometry("800x600")

        frame = tk.Frame(dlg)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")

        text = tk.Text(
            frame,
            wrap="word",
            yscrollcommand=scrollbar.set,
            font=("Arial", 11)
        )
        text.pack(side="left", fill="both", expand=True)

        scrollbar.config(command=text.yview)

        help_text = (
            "NÁPOVĚDA – PLAYOFF GENERÁTOR\n"
            "Autor: Martin Pihrt © www.pihrt.com\n\n"

            "=== ZÁKLADNÍ OVLÁDÁNÍ ===\n"
            "- Počet týmů: Nastavení → Počet týmů max 24\n"
            "- Generovat prázdné týmy: Nastavení → Generovat týmy\n"
            "- Editace týmu: Levé tlačítko myši na buňku\n"
            "- Postup do dalšího kola: Pravé tlačítko myši na tým\n"
            "- Zamknout editaci: Nastavení → Zamknout editaci týmů\n"
            "- Smazat obsah: Vymaže pouze názvy týmů\n"
            "- Vymazat vše: Odstraní pavouka i pozadí\n\n"

            "=== KOLO A TITULKY ===\n"
            "- Kliknutím na nadpis kola lze změnit jeho název\n"
            "- Poslední sloupec je vždy VÍTĚZ\n\n"

            "=== POJMENOVÁNÍ TÝMŮ ===\n"
            "Nastavení → Pojmenování týmů\n"
            "- Sloupce: ID týmu / škola nebo adresa / jméno soutěžícího / nejlepší čas jízdy\n"
            "- Neomezený počet řádků\n"
            "- Ruční editace\n"
            "- Import z Excelu přijme i nevyplněné nové sloupce\n"
            "- Export do Excelu obsahuje všechny čtyři sloupce\n"
            "- Tlačítko Smazat vše\n"
            "- Data se ukládají do souboru spolu s pavoukem\n\n"

            "=== TABULKA VPRAVO OD PAVOUKA ===\n"
            "- Při zapnutém předkole se automaticky generuje z předkola i Kola 1 bez duplicitních ID\n"
            "- Zobrazuje pouze ID, které existují v pojmenování týmů\n"
            "- Zobrazuje ID, školu, soutěžícího a nejlepší čas jízdy\n"
            "- Nadpis Účastníci soutěže lze kliknutím změnit\n"
            "- Řazení je číselně vzestupně\n"
            "- Velikost písma odpovídá nastavení velikosti pavouka\n\n"

            "=== LICHÝ POČET TÝMŮ ===\n"
            "Nastavení → Chování při lichém počtu vítězů\n"
            "- Automatický BYE\n"
            "- Ruční postup\n"
            "- Čekající hráč\n\n"

            "=== VZHLED ===\n"
            "Nastavení → Velikost písma\n"
            "- Malé / Střední / Velké\n\n"
            "Nastavení → Tloušťka čar\n"
            "- Normální / Silné\n\n"
            "Nastavení → Barva pozadí\n"
            "Nastavení → Načíst pozadí\n"
            "Nastavení → Smazat pozadí\n\n"

            "=== USB SEMAFOR ===\n"
            "Nastavení → USB nastavení\n"
            "- Bránu i každý LED displej lze samostatně vypnout volbou Nepoužívat\n"
            "- Jeden COM port nelze současně přiřadit více zařízením\n"
            "- Pravá část dialogu ukazuje nalezenou bránu a LED displeje\n"
            "- Nastavení Baud rate (výchozí 115200)\n"
            "- Timeout odpovědi (výchozí 10 s)\n\n"
            "Tlačítko START:\n"
            "- Odešle text 'start' do zařízení\n"
            "- Očekává zpět text 'ok'\n"
            "- Stav je zobrazen v horní liště\n\n"

            "=== ODPOČET ===\n"
            "Nastavení → Povolit odpočet\n"
            "- Volba zobrazuje časovač MM:SS v režimech PLAYOFF i LAPS\n"
            "- Pravým tlačítkem myši lze změnit společný nastavený čas\n\n"
            "Režim PLAYOFF:\n"
            "- Pod vítězem se zobrazí jednorázový odpočet\n"
            "Režim spuštění odpočtu:\n"
            "- Spustit odpočet ihned (po START)\n"
            "- Spustit odpočet až po semaforu (OK)\n\n"

            "Režim LAPS:\n"
            "- Odpočet je dole uprostřed nad poli A a B\n"
            "- Levé tlačítko spustí odpočet od nastaveného maxima nebo jej kdykoliv resetuje\n"
            "- Po vypršení se odpočet automaticky obnoví a pokračuje v dalším cyklu\n"
            "- Posledních 10 sekund bliká pozadí černě a červeně, text zůstává bílý\n"
            "- Vypnutí odpočtu nebo změna režimu cyklus zastaví\n\n"

            "=== TÝMY A HISTORIE V LAPS ===\n"
            "- Modrá tlačítka Team, + a − přepínají dvojice týmů 1/2, 3/4 a dále; vedle tlačítek je aktuální dvojice vždy viditelná\n"
            "- Každý tým má vlastní historii a vlastní pokračující číslování ve sloupci Jízda\n"
            "- Přepnutí na jinou dvojici původní výsledky nesmaže; po návratu se znovu zobrazí\n"
            "- Nastavení → LAPS → LAPS max počet týmů přijímá sudé číslo nejméně 2\n"
            "- Nastavení → LAPS umožňuje po potvrzení vymazat výsledky všech týmů\n"
            "- Tlačítka SMAZAT nad tabulkami mažou jen právě zobrazenou dvojici\n\n"

            "=== PLATNOST KOL V LAPS ===\n"
            "- U každého záznamu A i B tlačítko ZNEPLATNIT řádek přeškrtne, ale nesmaže jej ani nezmění tým či číslo jízdy\n"
            "- Neplatné záznamy se nezapočítávají do zeleně označeného nejrychlejšího kola\n"
            "- Tlačítko OBNOVIT vrátí záznam mezi platná kola\n\n"

            "=== ČAS KOLA NA LED DISPLEJI ===\n"
            "Nastavení → Měřit a zobrazit čas kola\n"
            "- Zobrazí měřený čas drah A a B v aplikaci\n"
            "Nastavení → Odesílat na LED průběžný čas\n"
            "- Je-li volba zapnutá, během jízdy pravidelně aktualizuje příslušný LED displej\n"
            "- Po dokončení dráhy zůstane na jejím displeji konečný čas\n"
            "Nastavení → Rychlost obnovování\n"
            "- Nabízí intervaly od 0,1 s do 1,0 s\n"
            "- Kratší interval znamená plynulejší aktualizaci displeje\n\n"

            "=== PROPAGAČNÍ TEXT NA LED DISPLEJÍCH ===\n"
            "Nastavení → Nastavit propagační text\n"
            "- Uloží text o délce nejvýše 79 základních znaků bez diakritiky\n"
            "- Plynulá rotace řízená aplikací funguje i se starším firmwarem panelu\n"
            "- Další volby jsou nativní rolování panelu SCR a statický text TXT\n"
            "- Posuvník nastavuje rychlost 1 až 20 znaků za sekundu\n"
            "- Text, režim i rychlost se ukládají do uživatelského nastavení a projektu\n"
            "- Tlačítko PROMO vedle režimu LAPS odešle text na všechny nastavené LED displeje\n"
            "- PROMO je dostupné pouze tehdy, když neběží odpočet, závod ani měření času\n"
            "- START nebo potvrzená změna režimu PLAYOFF/LAPS propagační text z displejů smaže\n\n"

            "=== PDF EXPORT ===\n"
            "Nastavení → Export do PDF PLAYOFF\n"
            "- První stránka: pavouk + vítěz + datum a čas exportu\n"
            "- Další stránka: tabulka pojmenování týmů\n"
            "Nastavení → Export do PDF LAPS\n"
            "- Vytvoří jednu stránku pro každý nastavený tým se všemi jeho jízdami\n"
            "- Zachová barevné rozlišení nejrychlejších, krátkých a neplatných jízd\n\n"

            "=== PROJEKTOROVÝ REŽIM ===\n"
            "Nastavení → Celá obrazovka ZAP/VYP\n"
            "- Přepne aplikaci na fullscreen\n"
            "- Klávesa ESC režim ukončí\n\n"

            "=== UKLÁDÁNÍ A NAČÍTÁNÍ ===\n"
            "Nastavení → Uložit do souboru\n"
            "- Uloží kompletní stav pavouka, pozadí, USB, odpočet, pojmenování týmů i historii LAPS\n\n"
            "Nastavení → Načíst ze souboru\n"
            "- Obnoví veškerý uložený obsah\n\n"

            "=== AKTUALIZACE ===\n"
            "Nastavení → Kontrola aktualizace\n"
            "- Ověří novou verzi programu na internetu\n"
            "- Samostatné okno ukazuje stav stahování, velikost a průběh v procentech\n"
            "- Stažený instalátor se před spuštěním ověří podle velikosti a SHA-256\n"
            "- Při chybě lze stahování zopakovat nebo znovu spustit původní Playoff\n\n"

            "=== ČAS A DATUM ===\n"
            "- V horní liště se zobrazuje aktuální datum a čas v reálném čase\n"
        )

        text.insert("1.0", help_text)
        text.config(state="disabled")

        btn = tk.Button(dlg, text="Zavřít", command=dlg.destroy)
        btn.pack(pady=8)

        dlg.bind("<Escape>", lambda e: dlg.destroy())
        self.root.wait_window(dlg)

    # --- fullscreen ---
    def toggle_projector(self):
        self.projector_mode = self.fullscreen_var.get()
        # aktivace fullscreen
        self.root.attributes('-fullscreen', self.projector_mode)
        self.root.after(50, self.redraw)

    def exit_fullscreen(self):
        self.projector_mode = False
        self.fullscreen_var.set(False)
        self.root.attributes('-fullscreen', False)
        self.root.after(50, self.redraw)

    def build_team_lookup_from_round1(self):
        if not self.bracket or not self.bracket.rounds:
            return []

        ids = []
        source_rounds = []
        if self.pre_round_enabled and self.bracket.pre_rounds:
            source_rounds.append(self.bracket.pre_rounds[0])
        source_rounds.append(self.bracket.rounds[0])

        for source_round in source_rounds:
            for match in source_round:
                for slot in (match.a, match.b):
                    team_id = slot.text.strip()
                    if team_id and team_id not in ids:
                        ids.append(team_id)

        lookup = {
            record["id"].strip(): record
            for record in normalize_team_records(self.team_names)
        }

        result = []
        for tid in ids:
            if tid in lookup:
                result.append((tid, lookup[tid]))

        def sort_key(x):
            try:
                return int(x[0])
            except Exception:
                return 10**9

        result.sort(key=sort_key)
        return result

    # --- playoff mode ---
    def redraw(self):
        self.canvas.delete("all")
        self.timer_window = None
        if self.view_mode == "laps":
            self.draw_laps()
            return

        self.rect_items.clear()
        self.text_items.clear()
        self.title_items.clear()
        self.line_items.clear()

        # --- BACKGROUND IMAGE ---
        if self.bg_image and PIL_AVAILABLE:
            try:
                cw = self.canvas.winfo_width()
                ch = self.canvas.winfo_height()

                if cw > 1 and ch > 1:
                    # scale image to canvas size
                    img = self.bg_image.resize((cw, ch), Image.LANCZOS)
                    self.bg_tk = ImageTk.PhotoImage(img)
                    self.canvas.create_image(0, 0, image=self.bg_tk, anchor="nw")
            except Exception as e:
                self._log("BACKGROUND ERROR:", e)

        if not self.bracket:
            return

        width = self.root.winfo_screenwidth() if self.projector_mode else max(800, self.canvas.winfo_width())
        height = self.root.winfo_screenheight() if self.projector_mode else max(600, self.canvas.winfo_height())
        self.canvas.config(width=width, height=height, bg=self.canvas_bg)

        rounds = self.bracket.rounds
        pre_rounds = self.bracket.pre_rounds if self.pre_round_enabled else []
        rounds_count = len(rounds)
        last_round = rounds_count - 1
        final_real_round = last_round - 1

        # --- font sizes ---
        if self.font_scale == 'large':
            cell_font_size = 28
        elif self.font_scale == 'small':
            cell_font_size = 12
        else:
            cell_font_size = 14

        cell_font = tkfont.Font(family="Arial", size=cell_font_size)

        if self.font_scale == 'large':
            title_font_size = 13
        elif self.font_scale == 'medium':
            title_font_size = 11
        else:
            title_font_size = 8

        title_font = ("Arial", title_font_size, "bold")

        # --- column widths ---
        col_widths = []
        padding = 20
        min_w = 60
        max_w = 220

        for r_idx, matches in enumerate(rounds):
            if r_idx == last_round:
                winner_match = rounds[last_round][0]
                winner_text = winner_match.a.text.strip() or winner_match.b.text.strip() or self.current_winner
                text_px = cell_font.measure(winner_text)
                col_widths.append(max(min_w, min(max_w, text_px + padding)))
                continue

            max_px = 0
            for m in matches:
                max_px = max(max_px, cell_font.measure(m.a.text.strip()))
                max_px = max(max_px, cell_font.measure(m.b.text.strip()))
            col_widths.append(max(min_w, min(max_w, max_px + padding)))

        margin_x = 40
        margin_y = 40
        h_gap = 70 
        v_gap = 10

        box_h = 40
        per_match_h = box_h * 2 + 8
        initial_matches = len(rounds[0])

        total_h = initial_matches * per_match_h + (initial_matches - 1) * v_gap + 2 * margin_y
        if total_h > height:
            scale = height / total_h
            scale = max(0.25, scale)
            box_h = int(box_h * scale)
            v_gap = max(3, int(v_gap * scale))
            per_match_h = box_h * 2 + 8

        col_x_positions = []
        x = margin_x

        # --- PRE ROUND COLUMN ---
        if self.pre_round_enabled and self.bracket.pre_rounds:
            pre_w = col_widths[0] 
            col_x_positions.append(x)
            x += pre_w + h_gap

        # --- NORMAL ROUNDS ---
        for w in col_widths:
            col_x_positions.append(x)
            x += w + h_gap

        final_centers = []
        semi_losers_centers = []

        if self.pre_round_enabled and self.bracket.pre_rounds:

            pre_matches = self.bracket.pre_rounds[0]
            col_x = col_x_positions[0]
            box_w = col_widths[0]

            title_id = self.canvas.create_text(
                col_x + box_w/2,
                margin_y - 10,
                text=self.bracket.pre_titles[0] if self.bracket.pre_titles else "Předkolo",
                font=title_font,
                fill=TITLE_COLOR,
                width=box_w + 60,
                justify="center",
                anchor="n"                
            )

            if not self.lock_edit:
                self.canvas.tag_bind(title_id, '<Button-1>',
                                     lambda e: self.edit_pre_title())

            matches_count = len(pre_matches)
            total_col_h = matches_count * (box_h * 2 + 8) + (matches_count - 1) * v_gap
            start_y = max(margin_y + title_font_size + 10,
                          (height - total_col_h) // 2)

            for m_idx, match in enumerate(pre_matches):

                top_y = start_y + m_idx * ((box_h * 2 + 8) + v_gap)

                x1 = col_x
                y1 = top_y
                x2 = x1 + box_w
                y2 = y1 + box_h * 2 + 8

                self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=BOX_FILL,
                    outline=BOX_OUTLINE,
                    width=self.line_width
                )

                self.canvas.create_line(
                    x1, y1 + box_h + 4,
                    x2, y1 + box_h + 4,
                    fill=BOX_OUTLINE,
                    width=max(1, self.line_width - 1)
                )

                if not match.a.text.strip():
                    self.canvas.create_rectangle(x1, y1, x2, y1 + box_h,
                                                 fill=WINNER_FILL, outline="", width=0)

                if not match.b.text.strip():
                    self.canvas.create_rectangle(x1, y1 + box_h + 8, x2, y2,
                                                 fill=WINNER_FILL, outline="", width=0)

                self.canvas.create_text(
                    (x1 + x2)/2,
                    y1 + box_h/2,
                    text=match.a.text,
                    font=("Arial", cell_font_size)
                )

                self.canvas.create_text(
                    (x1 + x2)/2,
                    y1 + box_h + 8 + box_h/2,
                    text=match.b.text,
                    font=("Arial", cell_font_size)
                )

                # HITBOXES
                hit_a = self.canvas.create_rectangle(x1, y1, x2, y1 + box_h,
                                                     fill="", outline="")
                hit_b = self.canvas.create_rectangle(x1, y1 + box_h + 8, x2, y2,
                                                     fill="", outline="")

                if not self.lock_edit:
                    self.canvas.tag_bind(hit_a, '<Button-1>',
                                         lambda e, mm=m_idx: self.edit_pre_slot(mm, 'a'))
                    self.canvas.tag_bind(hit_b, '<Button-1>',
                                         lambda e, mm=m_idx: self.edit_pre_slot(mm, 'b'))                

        offset = 1 if (self.pre_round_enabled and self.bracket.pre_rounds) else 0
        for r_idx, matches in enumerate(rounds):
            col_x = col_x_positions[r_idx + offset]
            box_w = col_widths[r_idx]

            title_id = self.canvas.create_text(
                col_x + box_w/2,
                margin_y - 10,
                text=self.bracket.titles[r_idx],
                font=title_font,
                fill=TITLE_COLOR,
                width=box_w + 60,
                justify="center",
                anchor="n"
            )
            self.canvas.tag_bind(title_id, '<Button-1>', lambda e, rr=r_idx: self.edit_title(rr))

            matches_count = len(matches)
            total_col_h = matches_count * (box_h * 2 + 8) + (matches_count - 1) * v_gap
            start_y = max(margin_y + title_font_size + 10,
                          (height - total_col_h) // 2)

            finalists = set()

            try:
                final_match = rounds[final_real_round + 1][0]
                fa = final_match.a.text.strip()
                fb = final_match.b.text.strip()

                if fa and fb:
                    finalists = {fa, fb}
            except:
                pass

            for m_idx, match in enumerate(matches):

                if r_idx == last_round and len(matches) == 1:
                    continue

                top_y = start_y + m_idx * ((box_h * 2 + 8) + v_gap)

                match_x1 = col_x
                match_y1 = top_y
                match_x2 = match_x1 + box_w
                match_y2 = match_y1 + box_h * 2 + 8

                a_x1, a_y1, a_x2, a_y2 = match_x1, match_y1, match_x2, match_y1 + box_h
                b_x1, b_y1, b_x2, b_y2 = match_x1, a_y2 + 8, match_x2, match_y2

                rect_match = self.canvas.create_rectangle(
                    match_x1, match_y1, match_x2, match_y2,
                    fill=BOX_FILL, outline=BOX_OUTLINE, width=self.line_width
                )

                self.canvas.create_line(
                    a_x1, a_y2 + 4,
                    a_x2, a_y2 + 4,
                    fill=BOX_OUTLINE,
                    width=max(1, self.line_width - 1)
                )

                is_winner_a = (match.a.text.strip() == self.current_winner.strip())
                is_winner_b = (match.b.text.strip() == self.current_winner.strip())

                if is_winner_a:
                    self.canvas.create_rectangle(a_x1, a_y1, a_x2, a_y2, fill=WINNER_FILL, outline="", width=0)
                if is_winner_b:
                    self.canvas.create_rectangle(b_x1, b_y1, b_x2, b_y2, fill=WINNER_FILL, outline="", width=0)

                txt_a = self.canvas.create_text((a_x1+a_x2)/2, (a_y1+a_y2)/2,
                                                text=match.a.text, font=("Arial", cell_font_size))
                txt_b = self.canvas.create_text((b_x1+b_x2)/2, (b_y1+b_y2)/2,
                                                text=match.b.text, font=("Arial", cell_font_size))

                # HITBOXES MUST LAST
                hit_a = self.canvas.create_rectangle(a_x1, a_y1, a_x2, a_y2, fill="", outline="")
                hit_b = self.canvas.create_rectangle(b_x1, b_y1, b_x2, b_y2, fill="", outline="")

                if not self.lock_edit:
                    self.canvas.tag_bind(hit_a, '<Button-1>', lambda e, rr=r_idx, mm=m_idx: self.edit_slot_dialog(rr, mm, 'a'))
                    self.canvas.tag_bind(hit_b, '<Button-1>', lambda e, rr=r_idx, mm=m_idx: self.edit_slot_dialog(rr, mm, 'b'))
                    self.canvas.tag_bind(hit_a, '<Button-3>', lambda e, rr=r_idx, mm=m_idx: self.promote(rr, mm, 'a'))
                    self.canvas.tag_bind(hit_b, '<Button-3>', lambda e, rr=r_idx, mm=m_idx: self.promote(rr, mm, 'b'))

                if r_idx + 1 < rounds_count:
                    cx = a_x2
                    cy = (a_y1 + b_y2) / 2

                    next_col_x = col_x_positions[r_idx + 1 + offset]
                    next_idx = m_idx // 2
                    nm = len(rounds[r_idx + 1])
                    total_h_next = nm * (box_h * 2 + 8) + (nm - 1) * v_gap
                    start_y_next = max(margin_y + title_font_size + 10,
                                       (height - total_h_next) // 2)
                    ny = start_y_next + next_idx * ((box_h * 2 + 8) + v_gap) + box_h

                    self.canvas.create_line(cx, cy, next_col_x, ny,
                                            width=self.line_width, fill=LINE_COLOR, smooth=True)

                if r_idx == final_real_round:
                    final_centers.append(((a_x2), (a_y1 + b_y2) / 2))

                if r_idx == last_round - 2:
                    final_match = rounds[last_round - 1][0]
                    if m_idx == 0:
                        finalist = final_match.a.text.strip()
                    else:
                        finalist = final_match.b.text.strip()
                    if match.a.text.strip() and match.a.text.strip() != finalist:
                        semi_losers_centers.append((a_x2, (a_y1 + a_y2) / 2))
                    if match.b.text.strip() and match.b.text.strip() != finalist:
                        semi_losers_centers.append((b_x2, (b_y1 + b_y2) / 2))

        # --- Winner box ---
        winner_match = rounds[last_round][0]
        winner_text = winner_match.a.text.strip() or winner_match.b.text.strip() or self.current_winner

        text_width = cell_font.measure(winner_text) if winner_text else 0
        win_w = max(text_width + 60, col_widths[last_round] + 40)
        win_h = box_h * 2

        col_x = col_x_positions[last_round + offset]
        win_x_center = col_x + col_widths[last_round] / 2

        win_x1 = win_x_center - win_w/2
        win_x2 = win_x_center + win_w/2
        win_y1 = (height // 2) - win_h//2
        win_y2 = win_y1 + win_h

        self.canvas.create_rectangle(
            win_x1, win_y1, win_x2, win_y2,
            fill=BOX_FILL, outline=BOX_OUTLINE, width=self.line_width+1
        )

        self.canvas.create_text(
            (win_x1+win_x2)/2, (win_y1+win_y2)/2,
            text=winner_text,
            font=("Arial", cell_font_size*2, "bold")
        )

        # --- HITBOX WINNER ---
        hit_winner = self.canvas.create_rectangle(
            win_x1, win_y1, win_x2, win_y2,
            fill="", outline=""
        )

        if not self.lock_edit:
            self.canvas.tag_bind(hit_winner, '<Button-1>',
                                 lambda e: self.edit_winner_dialog())

        # one line between the final and the winner = we will use the AVERAGE of both centers
        if final_centers:
            avg_x = sum(p[0] for p in final_centers) / len(final_centers)
            avg_y = sum(p[1] for p in final_centers) / len(final_centers)
            self.line_items.append((avg_x, avg_y, win_x1, (win_y1 + win_y2) / 2, self.line_width, LINE_COLOR))

        # === TABLE WITH TEAMS NAMES ===
        table_drawn = False
        table_bottom_y = 0
        table_right_x = 0
        try:
            table_data = self.build_team_lookup_from_round1()
            if table_data:
                table_x1 = win_x2 + 20
                table_x2 = width - 20

                if table_x2 - table_x1 > 200:
                    table_y = margin_y - 10
                    table_font_size = min(cell_font_size - 1, 18)
                    row_h = max(26, table_font_size + 10)

                    table_title = getattr(self, "team_table_title", TEAM_TABLE_DEFAULT_TITLE)
                    title_row_h = row_h
                    title_id = self.canvas.create_text(
                        (table_x1 + table_x2) / 2, table_y + title_row_h / 2,
                        text=table_title, font=("Arial", min(16, table_font_size), "bold"),
                    )
                    self.canvas.create_rectangle(
                        table_x1, table_y, table_x2, table_y + title_row_h,
                        fill="#dddddd", outline=BOX_OUTLINE, width=1,
                    )
                    self.canvas.tag_raise(title_id)
                    if not self.lock_edit:
                        self.canvas.tag_bind(title_id, "<Button-1>", lambda _event: self.edit_team_table_title())

                    usable_width = table_x2 - table_x1
                    column_widths = (50, usable_width * 0.46, usable_width * 0.31, usable_width * 0.23 - 50)
                    column_headers = self.get_team_table_headers()
                    header_y = table_y + title_row_h
                    self.canvas.create_rectangle(
                        table_x1, header_y, table_x2, header_y + row_h,
                        fill="#dddddd", outline=BOX_OUTLINE, width=1,
                    )
                    x = table_x1
                    for header_index, (column_width, header) in enumerate(zip(column_widths, column_headers)):
                        header_id = self.canvas.create_text(
                            x + column_width / 2, header_y + row_h / 2,
                            text=header, font=("Arial", min(14, table_font_size), "bold"),
                            width=max(20, column_width - 8), justify="center",
                        )
                        if not self.lock_edit:
                            self.canvas.tag_bind(
                                header_id,
                                "<Button-1>",
                                lambda _event, index=header_index: self.edit_team_table_header(index),
                            )
                        x += column_width
                        if x < table_x2:
                            self.canvas.create_line(x, header_y, x, header_y + row_h, fill=BOX_OUTLINE, width=1)

                    y = header_y + row_h

                    for row_index, (tid, record) in enumerate(table_data):
                        if row_index % 2 == 0:
                            row_fill = "#ffffff"
                        else:
                            row_fill = "#f2f2f2"

                        self.canvas.create_rectangle(
                            table_x1, y,
                            table_x2, y + row_h,
                            fill=row_fill,
                            outline=BOX_OUTLINE,
                            width=1
                        )

                        x = table_x1
                        values = (str(tid), record["school"], record["participant"], record["best_time"])
                        for value_index, (column_width, value) in enumerate(zip(column_widths, values)):
                            value_font_size = table_font_size
                            if value_index in (1, 2):
                                value_font_size = max(10, table_font_size - 4)
                                while value_font_size > 9:
                                    value_font = tkfont.Font(family="Arial", size=value_font_size)
                                    if value_font.measure(value) <= column_width - 16:
                                        break
                                    value_font_size -= 1
                            self.canvas.create_text(
                                x + (column_width / 2 if x == table_x1 else 8), y + row_h / 2,
                                text=value, font=("Arial", value_font_size),
                                anchor="center" if x == table_x1 else "w",
                                width=0 if value_index in (1, 2) else max(20, column_width - 16), justify="left",
                            )
                            x += column_width
                            if x < table_x2:
                                self.canvas.create_line(x, y, x, y + row_h, fill=BOX_OUTLINE, width=1)

                        y += row_h

                    table_drawn = True
                    table_bottom_y = y
                    table_right_x = table_x2

        except Exception as e:
            self._log("TEAM TABLE ERROR:", e)

        # === 3RD PLACE ===
        if self.third_place_enabled:
            semi_col_index = final_real_round + offset
            semi_col_x = col_x_positions[semi_col_index]
            base_x = semi_col_x

            third_offset_y = 100
            base_y = win_y2 + third_offset_y

            # small boxes A/B
            box_w = col_widths[final_real_round] if col_widths else 120
            box_h_small = box_h
            gap = 6

            # --- BIG WINNER BOX ---
            winner_text_tp = self.third_place["winner"]
            text_width_tp = cell_font.measure(winner_text_tp) if winner_text_tp else 0

            winner_w = max(text_width_tp + 60, col_widths[last_round] + 40)
            winner_h = box_h * 2

            win_x = win_x1

            # TITLE
            title_id = self.canvas.create_text(
                base_x + 60,
                base_y - 25,
                text=self.third_place_title,
                font=title_font
            )

            if not self.lock_edit:
                self.canvas.tag_bind(title_id, "<Button-1>", lambda e: self.edit_third_place_title())

            # --- LEFT MATCH ---
            a_y1 = base_y
            b_y1 = a_y1 + box_h_small + gap

            # box A
            self.canvas.create_rectangle(
                base_x, a_y1, base_x + box_w, a_y1 + box_h_small,
                fill=BOX_FILL, outline=BOX_OUTLINE, width=self.line_width
            )

            self.canvas.create_text(
                base_x + box_w/2,
                a_y1 + box_h_small/2,
                text=self.third_place["a"],
                font=("Arial", cell_font_size)
            )

            # box B
            self.canvas.create_rectangle(
                base_x, b_y1, base_x + box_w, b_y1 + box_h_small,
                fill=BOX_FILL, outline=BOX_OUTLINE, width=self.line_width
            )

            self.canvas.create_text(
                base_x + box_w/2,
                b_y1 + box_h_small/2,
                text=self.third_place["b"],
                font=("Arial", cell_font_size)
            )

            # --- WINNER BOX ---
            win_y1 = a_y1

            self.canvas.create_rectangle(
                win_x, win_y1,
                win_x + winner_w, win_y1 + winner_h,
                fill=BOX_FILL, outline=BOX_OUTLINE, width=self.line_width
            )

            self.canvas.create_text(
                win_x + winner_w/2,
                win_y1 + winner_h/2,
                text=self.third_place["winner"],
                font=("Arial", cell_font_size*2, "bold")
            )

            # highlight clear fields
            if not self.third_place["a"].strip():
                self.canvas.create_rectangle(
                    base_x, a_y1, base_x + box_w, a_y1 + box_h_small,
                    fill=WINNER_FILL, outline="", width=0
                )

            if not self.third_place["b"].strip():
                self.canvas.create_rectangle(
                    base_x, b_y1, base_x + box_w, b_y1 + box_h_small,
                    fill=WINNER_FILL, outline="", width=0
                )

            # --- LINE ---
            self.canvas.create_line(
                base_x + box_w,
                a_y1 + box_h_small,
                win_x,
                win_y1 + winner_h/2,
                fill=THIRD_PLACE_LINE_COLOR,
                width=self.line_width
            )

            # --- LINES from semifinal to 3. place ---
            if len(semi_losers_centers) >= 2:

                p1 = semi_losers_centers[0]
                p2 = semi_losers_centers[1]

                target_x = base_x

                self.canvas.create_line(
                    p1[0], p1[1],
                    target_x,
                    a_y1 + box_h_small / 2,
                    fill=THIRD_PLACE_LINE_COLOR,
                    width=self.line_width,
                    smooth=True
                )

                self.canvas.create_line(
                    p2[0], p2[1],
                    target_x,
                    b_y1 + box_h_small / 2,
                    fill=THIRD_PLACE_LINE_COLOR,
                    width=self.line_width,
                    smooth=True
                )

            # --- HITBOXES ---
            if not self.lock_edit:

                def edit_tp(field):
                    dlg = tk.Toplevel(self.root)
                    self.set_playoff_icon(dlg)
                    dlg.title("3. místo")

                    ent = tk.Entry(dlg, width=30)
                    ent.pack(padx=10, pady=10)
                    ent.insert(0, self.third_place[field])
                    ent.focus()

                    def ok():
                        self.third_place[field] = ent.get()
                        dlg.destroy()
                        self.redraw()

                    tk.Button(dlg, text="OK", command=ok).pack(pady=5)
                    dlg.bind("<Return>", lambda e: ok())

                self.canvas.create_rectangle(
                    base_x, a_y1, base_x+box_w, a_y1+box_h_small,
                    fill="", outline="", tags="tp_a"
                )
                self.canvas.tag_bind("tp_a", "<Button-1>", lambda e: edit_tp("a"))

                self.canvas.create_rectangle(
                    base_x, b_y1, base_x+box_w, b_y1+box_h_small,
                    fill="", outline="", tags="tp_b"
                )
                self.canvas.tag_bind("tp_b", "<Button-1>", lambda e: edit_tp("b"))

                self.canvas.create_rectangle(
                    win_x, win_y1, win_x+winner_w, win_y1+winner_h,
                    fill="", outline="", tags="tp_w"
                )
                self.canvas.tag_bind("tp_w", "<Button-1>", lambda e: edit_tp("winner"))

                self.canvas.tag_bind("tp_a", "<Button-3>", lambda e: self.promote_third_place("a"))
                self.canvas.tag_bind("tp_b", "<Button-3>", lambda e: self.promote_third_place("b"))         

        # --- TIMER OVERLAY ---
        try:
            if self.enable_timer:

                self.timer_label.update_idletasks()
                timer_w = self.timer_label.winfo_width()
                timer_h = self.timer_label.winfo_height()

                if table_drawn:
                    left = win_x2 + 20
                    right = table_x1 - 20
                    tx = (left + right) / 2 - 240  # LEFT
                else:
                    tx = win_x2 + 120

                ty = margin_y + 120                # DOWN

                self.timer_window = self.canvas.create_window(
                    tx,
                    ty,
                    window=self.timer_label,
                    anchor='center'
                )

                self.canvas.itemconfigure(self.timer_window, state='normal')

            else:
                if self.timer_window:
                    self.canvas.itemconfigure(self.timer_window, state='hidden')

        except Exception as e:
            self._log("TIMER ERROR:", e)

    # --- laps mode ---
    def _ensure_laps_team_state(self, team_id):
        key = str(int(team_id))
        state = self.laps_teams.get(key)
        if not isinstance(state, dict):
            state = {"records": [], "next_ride": 1}
            self.laps_teams[key] = state
        state.setdefault("records", [])
        state.setdefault("next_ride", 1)
        return state

    def _store_active_laps_pair(self):
        if not hasattr(self, "laps_teams"):
            return
        team_a = int(getattr(self, "laps_active_team_a", 1))
        state_a = self._ensure_laps_team_state(team_a)
        state_b = self._ensure_laps_team_state(team_a + 1)
        state_a["records"] = self.laps_a
        state_a["next_ride"] = max(1, int(self.lap_id_a))
        state_b["records"] = self.laps_b
        state_b["next_ride"] = max(1, int(self.lap_id_b))

    def _load_laps_team_pair(self, team_a, store_current=True, redraw=True):
        if store_current and hasattr(self, "laps_a"):
            self._store_active_laps_pair()
        maximum = normalize_laps_max_teams(
            getattr(self, "laps_max_teams", DEFAULT_LAPS_MAX_TEAMS)
        )
        try:
            team_a = int(team_a)
        except (TypeError, ValueError):
            team_a = 1
        team_a = max(1, min(maximum - 1, team_a))
        if team_a % 2 == 0:
            team_a -= 1
        self.laps_active_team_a = team_a
        state_a = self._ensure_laps_team_state(team_a)
        state_b = self._ensure_laps_team_state(team_a + 1)
        self.laps_a = state_a["records"]
        self.laps_b = state_b["records"]
        self.lap_id_a = max(1, int(state_a.get("next_ride", 1)))
        self.lap_id_b = max(1, int(state_b.get("next_ride", 1)))
        if redraw:
            self.redraw()

    def _restore_laps_history(self, history, maximum, active_team_a):
        normalized = normalize_laps_team_history(history)
        highest_saved_team = max(
            (int(team_id) for team_id, state in normalized.items() if state["records"]),
            default=0,
        )
        maximum = normalize_laps_max_teams(maximum)
        if highest_saved_team > maximum:
            maximum = highest_saved_team + (highest_saved_team % 2)
        self.laps_max_teams = maximum
        self.laps_teams = normalized
        self._load_laps_team_pair(active_team_a, store_current=False, redraw=False)

    def change_laps_team_pair(self, step):
        target = self.laps_active_team_a + (2 if step > 0 else -2)
        target = max(1, min(self.laps_max_teams - 1, target))
        if target == self.laps_active_team_a:
            return False
        self._load_laps_team_pair(target)
        return True

    def ask_laps_max_teams(self):
        dlg = tk.Toplevel(self.root)
        self.set_playoff_icon(dlg)
        dlg.title("LAPS max počet týmů")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="Sudý počet týmů (nejméně 2):").pack(padx=12, pady=(12, 6))
        entry = tk.Entry(dlg, width=12)
        entry.insert(0, str(self.laps_max_teams))
        entry.pack(padx=12, pady=4)
        entry.focus_set()

        def save_maximum():
            raw_value = entry.get().strip()
            if not raw_value.isdigit() or int(raw_value) < 2 or int(raw_value) % 2:
                messagebox.showerror(
                    "Chyba",
                    "LAPS max počet týmů musí být sudé číslo nejméně 2.",
                    parent=dlg,
                )
                return
            maximum = int(raw_value)
            highest_team_with_results = max(
                (
                    int(team_id)
                    for team_id, state in self.laps_teams.items()
                    if state.get("records")
                ),
                default=0,
            )
            if maximum < highest_team_with_results:
                messagebox.showerror(
                    "Chyba",
                    f"Výsledky již obsahují tým {highest_team_with_results}. Nejdříve vymažte historii LAPS.",
                    parent=dlg,
                )
                return
            self.laps_max_teams = maximum
            target = min(self.laps_active_team_a, maximum - 1)
            self._load_laps_team_pair(target)
            self.persist_user_settings(laps_max_teams=maximum)
            dlg.destroy()

        tk.Button(dlg, text="Uložit", command=save_maximum).pack(pady=(6, 12))
        dlg.bind("<Return>", lambda _event: save_maximum())
        dlg.bind("<Escape>", lambda _event: dlg.destroy())

    def clear_all_laps_history(self, confirm=True, redraw=True):
        if confirm and not messagebox.askyesno(
            "Potvrzení",
            "Smazat všechny záznamy LAPS všech týmů?",
        ):
            return False
        self.laps_teams = {}
        self.laps_active_team_a = 1
        self._load_laps_team_pair(1, store_current=False, redraw=False)
        if redraw:
            self.redraw()
        return True

    def draw_laps(self):
        self.canvas.delete("all")
        self.timer_window = None
        self.canvas.update_idletasks()

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        mid = w // 2

        if self.font_scale == "small":
            title_font = ("Arial", 14, "bold")
            header_font = ("Arial", 9, "bold")
            row_font = ("Consolas", 8)
            row_height = 18

        elif self.font_scale == "large":
            title_font = ("Arial", 28, "bold")
            header_font = ("Arial", 20, "bold")
            row_font = ("Consolas", 19)
            row_height = 34

        else:
            title_font = ("Arial", 19, "bold")
            header_font = ("Arial", 13, "bold")
            row_font = ("Consolas", 12)
            row_height = 24

        # --------------------------------------------------
        # TABLE GEOMETRY
        # --------------------------------------------------

        left_x1 = 10
        left_x2 = mid - 10

        right_x1 = mid + 10
        right_x2 = w - 10

        top_y = 55

        if self.projector_mode:
            bottom_y = h - 10
        else:
            bottom_y = h - 80

        header_h = 34
        validity_column_width = 120
        validity_margin = 8

        # outer borders
        self.canvas.create_rectangle(
            left_x1,
            top_y,
            left_x2,
            bottom_y,
            outline="#0b6bd6",
            width=self.line_width
        )

        self.canvas.create_rectangle(
            right_x1,
            top_y,
            right_x2,
            bottom_y,
            outline="#0b6bd6",
            width=self.line_width
        )

        # --------------------------------------------------
        # TITLES and buttons
        # --------------------------------------------------

        self.canvas.create_text(
            mid // 2,
            25,
            text="A",
            font=title_font
        )

        self.canvas.create_text(
            mid + mid // 2,
            25,
            text="B",
            font=title_font
        )

        for x1, x2, text, tag, button_font in (
            (10, 78, "Team", "laps_team_settings", ("Arial", 9, "bold")),
            (84, 118, "+", "laps_team_next", ("Arial", 15, "bold")),
            (124, 158, "−", "laps_team_previous", ("Arial", 15, "bold")),
        ):
            self.canvas.create_rectangle(
                x1, 10, x2, 40,
                fill="#0b6bd6",
                outline="black",
                tags=tag,
            )
            self.canvas.create_text(
                (x1 + x2) / 2, 25,
                text=text,
                fill="white",
                font=button_font,
                tags=tag,
            )
        self.canvas.create_text(
            168,
            25,
            anchor="w",
            text=f"{self.laps_active_team_a}-{self.laps_active_team_a + 1}",
            fill="#0b6bd6",
            font=("Arial", 12, "bold"),
            tags="laps_team_pair_label",
        )
        self.canvas.tag_bind("laps_team_settings", "<Button-1>", lambda _event: self.ask_laps_max_teams())
        self.canvas.tag_bind("laps_team_next", "<Button-1>", lambda _event: self.change_laps_team_pair(1))
        self.canvas.tag_bind("laps_team_previous", "<Button-1>", lambda _event: self.change_laps_team_pair(-1))

        # button DEL A
        self.canvas.create_rectangle(
            mid // 2 + 25, 10,
            mid // 2 + 95, 40,
            fill="#d62828",
            outline="black",
            tags="clear_a"
        )

        self.canvas.create_text(
            mid // 2 + 60,
            25,
            text="SMAZAT",
            fill="white",
            font=("Arial", 9, "bold"),
            tags="clear_a"
        )

        self.canvas.tag_bind(
            "clear_a",
            "<Button-1>",
            lambda e: self.clear_laps_a()
        )

        # button DEL A+B
        clear_all_x1 = mid - 55
        clear_all_x2 = mid + 55
        self.canvas.create_rectangle(
            clear_all_x1, 10,
            clear_all_x2, 40,
            fill="#d62828",
            outline="black",
            tags="clear_all_laps"
        )

        self.canvas.create_text(
            mid,
            25,
            text="SMAZAT A+B",
            fill="white",
            font=("Arial", 9, "bold"),
            tags="clear_all_laps"
        )

        self.canvas.tag_bind(
            "clear_all_laps",
            "<Button-1>",
            lambda e: self.clear_laps_all()
        )

        # button DEL B
        self.canvas.create_rectangle(
            mid + mid // 2 + 25, 10,
            mid + mid // 2 + 95, 40,
            fill="#d62828",
            outline="black",
            tags="clear_b"
        )

        self.canvas.create_text(
            mid + mid // 2 + 60,
            25,
            text="SMAZAT",
            fill="white",
            font=("Arial", 9, "bold"),
            tags="clear_b"
        )

        self.canvas.tag_bind(
            "clear_b",
            "<Button-1>",
            lambda e: self.clear_laps_b()
        )        

        # --------------------------------------------------
        # BLUE HEADERS
        # --------------------------------------------------

        self.canvas.create_rectangle(
            left_x1,
            top_y,
            left_x2,
            top_y + header_h + 5,
            fill="#0b6bd6",
            outline="#0b6bd6"
        )

        self.canvas.create_rectangle(
            right_x1,
            top_y,
            right_x2,
            top_y + header_h + 5,
            fill="#0b6bd6",
            outline="#0b6bd6"
        )

        self.canvas.create_text(
            left_x1 + 8,
            top_y + 5 + header_h / 2,
            anchor="w",
            text=" ID  Jízda   Vloženo                       Čas",
            fill="white",
            font=header_font
        )
        self.canvas.create_text(
            left_x2 - validity_margin - validity_column_width / 2,
            top_y + 5 + header_h / 2,
            text="Platnost",
            fill="white",
            font=header_font,
        )

        self.canvas.create_text(
            right_x1 + 8,
            top_y + 5 + header_h / 2,
            anchor="w",
            text=" ID  Jízda   Vloženo                       Čas",
            fill="white",
            font=header_font
        )
        self.canvas.create_text(
            right_x2 - validity_margin - validity_column_width / 2,
            top_y + 5 + header_h / 2,
            text="Platnost",
            fill="white",
            font=header_font,
        )

        # --------------------------------------------------
        # DYNAMIC ROW COUNT
        # --------------------------------------------------
        first_row_y = top_y + header_h + row_height // 2 + 4
        visible_rows = max(1, int((bottom_y - first_row_y) / row_height) - 1)

        # --------------------------------------------------
        # LEFT TABLE
        # --------------------------------------------------
        best_a = best_valid_lap_ms(self.laps_a)

        y = first_row_y
        for idx, rec in enumerate(self.laps_a[:visible_rows]):
            row_top = y - row_height // 2
            row_bottom = row_top + row_height
            ms = int(rec.get("ms", 0))
            invalid = bool(rec.get("invalid", False))
            too_short = ms < 10000
            best = (best_a is not None and ms == best_a)
            
            if invalid:
                bg = "#d9d9d9"
            elif too_short:
                bg = "#ffb3b3"      # red
            elif best:
                bg = "#b8ffb8"      # grn
            elif idx % 2:
                bg = "#f2f7ff"
            else:
                bg = None

            self.canvas.create_rectangle(
                left_x1 + 1,
                row_top,
                left_x2 - 1,
                row_bottom,
                fill=bg,
                outline=""
            )

            txt = (
                f"{rec['id']:>3}   "
                f"{rec.get('ride', 1):>3}   "
                f"{rec['date']}   "
                f"{rec['time']}   "
                f"({ms}ms)"
            )

            self.canvas.create_text(
                left_x1 + 8,
                y,
                anchor="w",
                text=txt,
                font=row_font,
                fill="black"
            )

            ride_id = rec.get("ride", 1)
            action_tag = f"lap_validity_a_{rec['id']}_{ride_id}"
            action_x1 = left_x2 - validity_margin - validity_column_width
            self.canvas.create_rectangle(
                action_x1, row_top + 3, left_x2 - validity_margin, row_bottom - 3,
                fill="#777777" if invalid else "#d62828",
                outline="black", tags=action_tag,
            )
            self.canvas.create_text(
                (action_x1 + left_x2 - validity_margin) / 2, y,
                text="OBNOVIT" if invalid else "ZNEPLATNIT",
                fill="white", font=("Arial", max(7, row_font[1] - 8), "bold"), tags=action_tag,
            )
            self.canvas.tag_bind(
                action_tag, "<Button-1>",
                lambda _event, selected_ride=ride_id: self.toggle_lap_validity("a", selected_ride),
            )
            if invalid:
                self.canvas.create_line(left_x1 + 3, y, action_x1 - 4, y, fill="#555555", width=2)

            # separator line
            self.canvas.create_line(
                left_x1,
                row_bottom,
                left_x2,
                row_bottom,
                fill="#d8d8d8"
            )

            y += row_height

        # --------------------------------------------------
        # RIGHT TABLE
        # --------------------------------------------------
        best_b = best_valid_lap_ms(self.laps_b)

        y = first_row_y
        for idx, rec in enumerate(self.laps_b[:visible_rows]):
            row_top = y - row_height // 2
            row_bottom = row_top + row_height
            ms = int(rec.get("ms", 0))
            invalid = bool(rec.get("invalid", False))
            too_short = ms < 10000
            best = (best_b is not None and ms == best_b)

            if invalid:
                bg = "#d9d9d9"
            elif too_short:
                bg = "#ffb3b3"      # red
            elif best:
                bg = "#b8ffb8"      # grn
            elif idx % 2:
                bg = "#f2f7ff"
            else:
                bg = None

            self.canvas.create_rectangle(
                right_x1 + 1,
                row_top,
                right_x2 - 1,
                row_bottom,
                fill=bg,
                outline=""
            )

            txt = (
                f"{rec['id']:>3}   "
                f"{rec.get('ride', 1):>3}   "
                f"{rec['date']}   "
                f"{rec['time']}   "
                f"({ms}ms)"
            )

            self.canvas.create_text(
                right_x1 + 8,
                y,
                anchor="w",
                text=txt,
                font=row_font,
                fill="black"
            )                

            ride_id = rec.get("ride", 1)
            action_tag = f"lap_validity_b_{rec['id']}_{ride_id}"
            action_x1 = right_x2 - validity_margin - validity_column_width
            self.canvas.create_rectangle(
                action_x1, row_top + 3, right_x2 - validity_margin, row_bottom - 3,
                fill="#777777" if invalid else "#d62828",
                outline="black", tags=action_tag,
            )
            self.canvas.create_text(
                (action_x1 + right_x2 - validity_margin) / 2, y,
                text="OBNOVIT" if invalid else "ZNEPLATNIT",
                fill="white", font=("Arial", max(7, row_font[1] - 8), "bold"), tags=action_tag,
            )
            self.canvas.tag_bind(
                action_tag, "<Button-1>",
                lambda _event, selected_ride=ride_id: self.toggle_lap_validity("b", selected_ride),
            )
            if invalid:
                self.canvas.create_line(right_x1 + 3, y, action_x1 - 4, y, fill="#555555", width=2)

            # separator line
            self.canvas.create_line(
                right_x1,
                row_bottom,
                right_x2,
                row_bottom,
                fill="#d8d8d8"
            )

            y += row_height

        # Repeating LAPS countdown is drawn last so it stays above both fields.
        if self.enable_timer:
            self.timer_label.update_idletasks()
            timer_h = max(1, self.timer_label.winfo_reqheight())
            timer_x, timer_y = laps_countdown_position(w, h, timer_h)
            self.timer_window = self.canvas.create_window(
                timer_x,
                timer_y,
                window=self.timer_label,
                anchor='center'
            )
            self.canvas.itemconfigure(self.timer_window, state='normal')

    def toggle_lap_validity(self, lane, ride_id):
        records = self.laps_a if lane == "a" else self.laps_b
        for record in records:
            if record.get("ride", record.get("id")) == ride_id:
                record["invalid"] = not bool(record.get("invalid", False))
                self.redraw()
                return True
        return False

    def clear_laps_a(self):
        if messagebox.askyesno("Potvrzení", "Smazat všechny záznamy A?"):
            self.laps_a.clear()
            self.lap_id_a = 1
            self.redraw()

    def clear_laps_b(self):
        if messagebox.askyesno("Potvrzení", "Smazat všechny záznamy B?"):
            self.laps_b.clear()
            self.lap_id_b = 1
            self.redraw()

    def clear_laps_all(self):
        if messagebox.askyesno("Potvrzení", "Smazat všechny záznamy A i B?"):
            self.laps_a.clear()
            self.laps_b.clear()
            self.lap_id_a = 1
            self.lap_id_b = 1
            self.redraw()

    # --- PDF export ---
    def export_pdf(self):
        if not self.bracket:
            messagebox.showerror("Chyba", "Nejprve vytvoř pavouka.")
            return

        # --- Font ---
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(BASE_PATH, "DejaVuSans.ttf")))
        except Exception:
            messagebox.showerror(
                "Chyba",
                "Font DejaVuSans.ttf nebyl nalezen.\nUlož jej do stejné složky jako tento program."
            )
            return

        fname = filedialog.asksaveasfilename(defaultextension=".pdf",
                                             filetypes=[("PDF", "*.pdf")])
        if not fname:
            return

        # --- Geometry as redraw() ---
        base_rounds = self.bracket.rounds
        base_titles = self.bracket.titles

        if self.pre_round_enabled and self.bracket.pre_rounds:
            rounds = self.bracket.pre_rounds + base_rounds
            titles_list = (
                self.bracket.pre_titles if self.bracket.pre_titles else ["Předkolo"]
            ) + base_titles
            offset = 1
        else:
            rounds = base_rounds
            titles_list = base_titles
            offset = 0

        rounds_count = len(rounds)
        last_round = rounds_count - 1
        final_real_round = last_round - 1

        # canvas size
        canvas_w = self.root.winfo_screenwidth() if self.projector_mode else max(800, self.canvas.winfo_width())
        canvas_h = self.root.winfo_screenheight() if self.projector_mode else max(600, self.canvas.winfo_height())

        # font size
        if self.font_scale == 'large':
            cell_font_size = 28
        elif self.font_scale == 'small':
            cell_font_size = 10
        else:
            cell_font_size = 14

        cell_font = tkfont.Font(family="Arial", size=cell_font_size)

        title_font_size = (
            33 if self.projector_mode or self.font_scale == 'large'
            else 20 if self.font_scale == 'medium'
            else 12
        )

        # --- column widths ---
        col_widths = []
        padding = 20
        min_w = 60
        max_w = 220

        for r_idx, matches in enumerate(rounds):
            if r_idx == last_round:
                winner_match = rounds[last_round][0]
                winner_text = winner_match.a.text.strip() or winner_match.b.text.strip() or self.current_winner
                text_px = cell_font.measure(winner_text)
                col_widths.append(max(min_w, min(max_w, text_px + padding)))
                continue

            max_px = 0
            for m in matches:
                max_px = max(max_px, cell_font.measure(m.a.text.strip()))
                max_px = max(max_px, cell_font.measure(m.b.text.strip()))
            col_widths.append(max(min_w, min(max_w, max_px + padding)))

        # --- indents and spaces ---
        margin_x = 40
        margin_y = 40
        h_gap = 130 # 180
        v_gap = 10

        # --- wheel height ---
        box_h = 40
        per_match_h = box_h * 2 + 8
        initial_matches = len(rounds[0])

        total_h = initial_matches * per_match_h + (initial_matches - 1) * v_gap + 2 * margin_y
        if total_h > canvas_h:
            scale_local = canvas_h / total_h
            scale_local = max(0.25, scale_local)
            box_h = int(box_h * scale_local)
            v_gap = max(3, int(v_gap * scale_local))
            per_match_h = box_h * 2 + 8

        # --- X column positions ---
        col_x_positions = []
        x = margin_x
        for w in col_widths:
            col_x_positions.append(x)
            x += w + h_gap

        # --- Geometry for PDF ---
        rects = []
        lines = []
        titles = []
        semi_losers_centers = []        

        # We will save the ONLY point of the final
        final_center_x = None
        final_center_y = None

        # --- Wheel scanning ---
        for r_idx, matches in enumerate(rounds):
            col_x = col_x_positions[r_idx]
            box_w = col_widths[r_idx]

            # titles
            titles.append((col_x + box_w / 2, margin_y - 10,
                           titles_list[r_idx], title_font_size))

            matches_count = len(matches)
            total_col_h = matches_count * (box_h * 2 + 8) + (matches_count - 1) * v_gap
            start_y = max(margin_y + title_font_size + 10,
                          (canvas_h - total_col_h) // 2)

            for m_idx, match in enumerate(matches):

                # skip the WINNERS round (to be drawn later)
                if r_idx == last_round and len(matches) == 1:
                    continue

                top_y = start_y + m_idx * ((box_h * 2 + 8) + v_gap)

                # A box
                a_x1 = col_x
                a_y1 = top_y
                a_x2 = a_x1 + box_w
                a_y2 = a_y1 + box_h

                # B box
                b_x1 = col_x
                b_y1 = a_y2 + 8
                b_x2 = b_x1 + box_w
                b_y2 = b_y1 + box_h

                # winner/highlight
                is_winner_a = (match.a.text.strip() == self.current_winner.strip())
                is_winner_b = (match.b.text.strip() == self.current_winner.strip())

                fill_a = WINNER_FILL if is_winner_a else BOX_FILL
                fill_b = WINNER_FILL if is_winner_b else BOX_FILL
                outline_a = WINNER_OUTLINE if is_winner_a else BOX_OUTLINE
                outline_b = WINNER_OUTLINE if is_winner_b else BOX_OUTLINE

                rects.append((a_x1, a_y1, a_x2, a_y2,
                              self.line_width, fill_a, outline_a,
                              match.a.text, cell_font_size, False))
                rects.append((b_x1, b_y1, b_x2, b_y2,
                              self.line_width, fill_b, outline_b,
                              match.b.text, cell_font_size, False))

                # connection to the next round
                if (r_idx + 1 < rounds_count) and (r_idx != final_real_round) and (r_idx >= offset):                   
                    cx = a_x2
                    cy = (a_y1 + b_y2) / 2

                    next_col_x = col_x_positions[r_idx + 1]
                    next_idx = m_idx // 2
                    nm = len(rounds[r_idx + 1])
                    total_h_next = nm * (box_h * 2 + 8) + (nm - 1) * v_gap
                    start_y_next = max(margin_y + title_font_size + 10,
                                       (canvas_h - total_h_next) // 2)
                    ny = start_y_next + next_idx * ((box_h * 2 + 8) + v_gap) + box_h

                    lines.append((cx, cy, next_col_x, ny,
                                  self.line_width, LINE_COLOR))

                # --- THE ONLY center of the finals ---
                if r_idx == final_real_round and final_center_x is None:
                    final_center_x = a_x2
                    final_center_y = (a_y1 + b_y2) / 2

                if r_idx == last_round - 2:
                    final_match = rounds[last_round - 1][0]

                    if m_idx == 0:
                        finalist = final_match.a.text.strip()
                    else:
                        finalist = final_match.b.text.strip()

                    # A slot
                    if match.a.text.strip() and match.a.text.strip() != finalist:
                        semi_losers_centers.append((
                            a_x2,
                            (a_y1 + a_y2) / 2
                        ))

                    # B slot
                    if match.b.text.strip() and match.b.text.strip() != finalist:
                        semi_losers_centers.append((
                            b_x2,
                            (b_y1 + b_y2) / 2
                        ))

        # --- Drawing of the winner ---
        winner_match = rounds[last_round][0]
        winner_text = (winner_match.a.text.strip()
                       or winner_match.b.text.strip()
                       or self.current_winner)

        text_width = cell_font.measure(winner_text)
        win_w = max(text_width + 60, col_widths[last_round] + 40)
        win_h = box_h * 2

        col_x = col_x_positions[last_round]
        win_x_center = col_x + col_widths[last_round] / 2

        win_x1 = win_x_center - win_w / 2
        win_x2 = win_x_center + win_w / 2
        win_y1 = (canvas_h // 2) - win_h // 2
        win_y2 = win_y1 + win_h

        rects.append((win_x1, win_y1, win_x2, win_y2,
                      self.line_width + 1, BOX_FILL, BOX_OUTLINE,
                      winner_text, cell_font_size * 2, True))

        # --- ONE line from the final → winner ---
        if final_center_x is not None:
            lines.append((final_center_x, final_center_y,
                          win_x1, (win_y1 + win_y2) / 2,
                          self.line_width, LINE_COLOR))

        # 3. place winner
        if self.third_place_enabled:

            semi_col_index = final_real_round
            base_x = col_x_positions[semi_col_index]

            third_offset_y = 100
            base_y = win_y2 + third_offset_y

            box_w = col_widths[final_real_round]
            box_h_small = box_h
            gap = 6

            a_y1 = base_y
            b_y1 = a_y1 + box_h_small + gap

            rects.append((base_x, a_y1, base_x + box_w, a_y1 + box_h_small,
                          self.line_width, BOX_FILL, BOX_OUTLINE,
                          self.third_place["a"], cell_font_size, False))

            rects.append((base_x, b_y1, base_x + box_w, b_y1 + box_h_small,
                          self.line_width, BOX_FILL, BOX_OUTLINE,
                          self.third_place["b"], cell_font_size, False))

            winner_tp = self.third_place["winner"]
            text_width_tp = cell_font.measure(winner_tp) if winner_tp else 0

            winner_w = max(text_width_tp + 60, col_widths[last_round] + 40)
            winner_h = box_h * 2

            win3_x = win_x1
            win3_y = a_y1

            rects.append((win3_x, win3_y, win3_x + winner_w, win3_y + winner_h,
                          self.line_width, BOX_FILL, BOX_OUTLINE,
                          winner_tp, cell_font_size * 2, True))

            lines.append((
                base_x + box_w,
                a_y1 + box_h_small,
                win3_x,
                win3_y + winner_h / 2,
                self.line_width,
                THIRD_PLACE_LINE_COLOR
            ))

            if len(semi_losers_centers) >= 2:
                p1 = semi_losers_centers[0]
                p2 = semi_losers_centers[1]

                lines.append((
                    p1[0], p1[1],
                    base_x,
                    a_y1 + box_h_small / 2,
                    self.line_width,
                    THIRD_PLACE_LINE_COLOR
                ))

                lines.append((
                    p2[0], p2[1],
                    base_x,
                    b_y1 + box_h_small / 2,
                    self.line_width,
                    THIRD_PLACE_LINE_COLOR
                ))            

        # --- Bounding box calculation ---
        minx, miny = float('inf'), float('inf')
        maxx, maxy = float('-inf'), float('-inf')

        for x1, y1, x2, y2, *_ in rects:
            minx = min(minx, x1)
            miny = min(miny, y1)
            maxx = max(maxx, x2)
            maxy = max(maxy, y2)

        for x1, y1, x2, y2, *_ in lines:
            minx = min(minx, x1, x2)
            miny = min(miny, y1, y2)
            maxx = max(maxx, x1, x2)
            maxy = max(maxy, y1, y2)

        for tx, ty, *_ in titles:
            minx = min(minx, tx)
            miny = min(miny, ty)
            maxx = max(maxx, tx)
            maxy = max(maxy, ty)

        # --- Reserve for printing ---
        maxy += 60

        content_w = maxx - minx
        content_h = maxy - miny

        # --- PDF page ---
        page_w, page_h = landscape(A4)
        margin_pdf = 20

        scale_x = (page_w - 2 * margin_pdf) / content_w
        scale_y = (page_h - 2 * margin_pdf) / content_h
        scale = min(scale_x, scale_y)

        draw_w = content_w * scale
        draw_h = content_h * scale

        off_x = (page_w - draw_w) / 2 - minx * scale
        off_y = (page_h - draw_h) / 2 - miny * scale

        def TX(x): return off_x + x * scale
        def TY(y): return off_y + (content_h * scale) - (y - miny) * scale

        # --- PDF ---
        pdf = rl_canvas.Canvas(fname, pagesize=(page_w, page_h))

        # --- RECTANGLES & TEXT ---
        for x1, y1, x2, y2, lw, fill, outline, text, fsize, bold in rects:
            rw = (x2 - x1) * scale
            rh = (y2 - y1) * scale
            rx = TX(x1)
            ry_top = TY(y1)
            ry = ry_top - rh

            pdf.setStrokeColor(HexColor(outline))
            pdf.setFillColor(HexColor(fill))
            pdf.setLineWidth(max(0.5, lw * scale))
            pdf.rect(rx, ry, rw, rh, stroke=1, fill=1)

            # text
            font_pt = max(6, int(fsize * scale))
            baseline_shift = font_pt * 0.35

            txt_cx = rx + rw / 2
            txt_cy = ry + rh / 2

            pdf.setFont("DejaVu", font_pt)
            pdf.setFillColor(black)

            pdf.drawCentredString(txt_cx, txt_cy - baseline_shift, text)

        # --- TITLES ---
        for tx, ty, ttext, tsize in titles:
            font_pt = max(7, int(tsize * scale))
            baseline_shift = font_pt * 0.35
            px = TX(tx)
            py_top = TY(ty)
            py = py_top - baseline_shift

            pdf.setFont("DejaVu", font_pt)
            pdf.setFillColor(black)
            pdf.drawCentredString(px, py, ttext)

        # --- LINES ---
        for x1, y1, x2, y2, lw, color in lines:
            pdf.setStrokeColor(HexColor(color))
            pdf.setLineWidth(max(0.5, lw * scale))
            pdf.line(TX(x1), TY(y1), TX(x2), TY(y2))

        # --- DATE AND TIME EXPORT ---
        import datetime
        dt = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        pdf.setFont("DejaVu", 10)
        pdf.setFillColor(black)
        pdf.drawRightString(
            page_w - 120,
            20,
            f"Export: {dt}. Generováno programem PLAYOFF od www.pihrt.com"
        )

        # === TABULKA POJMENOVÁNÍ TÝMŮ NA SAMOSTATNÉ STRÁNCE PDF ===
        try:
            table_data = self.build_team_lookup_from_round1()
            if table_data:
                pdf.showPage()   # next page

                page_w, page_h = landscape(A4)
                margin = 40

                table_w = page_w - 2 * margin
                col_widths = (60, table_w * 0.46, table_w * 0.31, table_w * 0.23 - 60)
                column_headers = self.get_team_table_headers()
                row_h = max(26, min(cell_font_size, 18) + 10)

                x1 = margin
                y = page_h - margin

                def draw_table_header(current_y):
                    pdf.setFillColor(HexColor("#dddddd"))
                    pdf.rect(x1, current_y - row_h, table_w, row_h, stroke=1, fill=1)
                    pdf.setFont("DejaVu", 12)
                    pdf.setFillColor(black)
                    pdf.drawCentredString(
                        x1 + table_w / 2,
                        current_y - row_h / 2 - 4,
                        getattr(self, "team_table_title", TEAM_TABLE_DEFAULT_TITLE),
                    )
                    current_y -= row_h
                    x = x1
                    for column_width, header in zip(col_widths, column_headers):
                        pdf.setFillColor(HexColor("#dddddd"))
                        pdf.rect(x, current_y - row_h, column_width, row_h, stroke=1, fill=1)
                        pdf.setFillColor(black)
                        pdf.setFont("DejaVu", 10)
                        pdf.drawCentredString(x + column_width / 2, current_y - row_h / 2 - 4, header)
                        x += column_width
                    return current_y - row_h

                y = draw_table_header(y)
                pdf.setFont("DejaVu", 11)

                for tid, record in table_data:
                    # --- PAGE ---
                    if y - row_h * 2 < margin:
                        pdf.showPage()
                        y = page_h - margin
                        y = draw_table_header(y)
                        pdf.setFont("DejaVu", 11)

                    pdf.setFillColor(HexColor("#ffffff"))
                    x = x1
                    for column_width in col_widths:
                        pdf.rect(x, y - row_h, column_width, row_h, stroke=1, fill=1)
                        x += column_width
                    pdf.setFillColor(black)
                    values = (str(tid), record["school"], record["participant"], record["best_time"])
                    x = x1
                    for index, (column_width, value) in enumerate(zip(col_widths, values)):
                        if index in (0, 3):
                            pdf.drawCentredString(x + column_width / 2, y - row_h / 2 - 4, value)
                        else:
                            pdf.drawString(x + 6, y - row_h / 2 - 4, value)
                        x += column_width

                    y -= row_h

                pdf.setFont("DejaVu", 10)
                pdf.setFillColor(black)
                pdf.drawRightString(
                    page_w - 120,
                    20,
                    f"Export: {dt}. Generováno programem PLAYOFF od www.pihrt.com"
                )

        except Exception as e:
            self._log("PDF TEAM TABLE ERROR:", e)

        # --- Save PDF ---
        try:
            pdf.save()
            messagebox.showinfo("Hotovo", f"PDF uložen: {fname}")
        except Exception as e:
            messagebox.showerror("Chyba", str(e))

    def export_laps_pdf(self):
        try:
            pdfmetrics.registerFont(
                TTFont("DejaVu", os.path.join(BASE_PATH, "DejaVuSans.ttf"))
            )
        except Exception:
            messagebox.showerror(
                "Chyba",
                "Font DejaVuSans.ttf nebyl nalezen.",
            )
            return False

        fname = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="LAPS_vysledky.pdf",
        )
        if not fname:
            return False

        self._store_active_laps_pair()
        page_w, page_h = landscape(A4)
        margin = 28
        title_y = page_h - 35
        table_top = page_h - 58
        footer_h = 28
        header_h = 30
        table_w = page_w - 2 * margin
        column_widths = (
            table_w * 0.08,
            table_w * 0.10,
            table_w * 0.30,
            table_w * 0.29,
            table_w * 0.23,
        )
        headers = ("ID", "Jízda", "Vloženo", "Čas", "Platnost")

        def fit_text(text, width, font_size):
            text = str(text or "")
            if pdfmetrics.stringWidth(text, "DejaVu", font_size) <= width - 8:
                return text
            suffix = "…"
            while text and pdfmetrics.stringWidth(text + suffix, "DejaVu", font_size) > width - 8:
                text = text[:-1]
            return text + suffix

        try:
            pdf = rl_canvas.Canvas(fname, pagesize=(page_w, page_h))
            for team_id in range(1, self.laps_max_teams + 1):
                state = self._ensure_laps_team_state(team_id)
                records = list(state.get("records", []))
                lane = "A" if team_id % 2 else "B"
                best_time = best_valid_lap_ms(records)

                pdf.setFillColor(black)
                pdf.setFont("DejaVu", 17)
                pdf.drawCentredString(page_w / 2, title_y, f"LAPS - tým {team_id} - dráha {lane}")

                x = margin
                for width, header in zip(column_widths, headers):
                    pdf.setFillColor(HexColor(LINE_COLOR))
                    pdf.setStrokeColor(HexColor(LINE_COLOR))
                    pdf.rect(x, table_top - header_h, width, header_h, stroke=1, fill=1)
                    pdf.setFillColor(HexColor("#ffffff"))
                    pdf.setFont("DejaVu", 11)
                    pdf.drawCentredString(x + width / 2, table_top - header_h / 2 - 4, header)
                    x += width

                available_rows_h = table_top - header_h - footer_h - margin
                row_h = min(34, available_rows_h / max(1, len(records)))
                row_font_size = max(3, min(11, row_h * 0.42))
                y = table_top - header_h

                if not records:
                    pdf.setFillColor(HexColor("#ffffff"))
                    pdf.setStrokeColor(HexColor("#d8d8d8"))
                    pdf.rect(margin, y - 34, table_w, 34, stroke=1, fill=1)
                    pdf.setFillColor(black)
                    pdf.setFont("DejaVu", 11)
                    pdf.drawCentredString(page_w / 2, y - 21, "Bez zaznamenaných jízd")
                else:
                    for index, record in enumerate(records):
                        milliseconds = int(record.get("ms", 0))
                        invalid = bool(record.get("invalid", False))
                        if invalid:
                            fill = "#d9d9d9"
                        elif milliseconds < 10000:
                            fill = "#ffb3b3"
                        elif best_time is not None and milliseconds == best_time:
                            fill = "#b8ffb8"
                        elif index % 2:
                            fill = "#f2f7ff"
                        else:
                            fill = "#ffffff"

                        row_bottom = y - row_h
                        values = (
                            str(team_id),
                            str(record.get("ride", index + 1)),
                            str(record.get("date", "")),
                            f"{record.get('time', '')} ({milliseconds} ms)",
                            "NEPLATNÁ" if invalid else "PLATNÁ",
                        )
                        x = margin
                        pdf.setFont("DejaVu", row_font_size)
                        for width, value in zip(column_widths, values):
                            pdf.setFillColor(HexColor(fill))
                            pdf.setStrokeColor(HexColor("#d8d8d8"))
                            pdf.rect(x, row_bottom, width, row_h, stroke=1, fill=1)
                            pdf.setFillColor(black)
                            pdf.drawCentredString(
                                x + width / 2,
                                row_bottom + row_h / 2 - row_font_size * 0.35,
                                fit_text(value, width, row_font_size),
                            )
                            x += width
                        if invalid:
                            pdf.setStrokeColor(HexColor("#555555"))
                            pdf.setLineWidth(max(0.5, row_font_size / 8))
                            pdf.line(
                                margin + 3,
                                row_bottom + row_h / 2,
                                margin + table_w - 3,
                                row_bottom + row_h / 2,
                            )
                        y = row_bottom

                pdf.setFillColor(black)
                pdf.setFont("DejaVu", 9)
                pdf.drawRightString(
                    page_w - margin,
                    18,
                    f"Tým {team_id} z {self.laps_max_teams} - Generováno programem PLAYOFF od www.pihrt.com",
                )
                pdf.showPage()

            pdf.save()
            messagebox.showinfo("Hotovo", f"PDF LAPS uložen: {fname}")
            return fname
        except Exception as error:
            self._log("PDF LAPS ERROR:", error)
            messagebox.showerror("Chyba", str(error))
            return False

# --- run ---
if __name__ == '__main__':
    root = tk.Tk()

    # --- FIX icon for PyInstaller ONEFILE ---
    try:
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(base, "playoff.ico")
        root.iconbitmap(icon_path)

    except Exception as e:
        self._log("Icon load error:", e)

    app = PlayoffApp(root)

    # --- APP Windows ---
    win_w = 1920
    win_h = 1080

    root.geometry(f"{win_w}x{win_h}")

    root.update_idletasks()

    try:
        geom = root.wm_geometry()  # ex. "1920x1080+10+10"
        f = root.wm_frame()  # (left, top, right, bottom)
        frame_left, frame_top, frame_right, frame_bottom = f
    except:
        # fallback, if wm_frame not available
        frame_left = frame_top = frame_right = frame_bottom = 8

    outer_w = win_w + frame_left + frame_right
    outer_h = win_h + frame_top + frame_bottom

    # screen size
    scr_w = root.winfo_screenwidth()
    scr_h = root.winfo_screenheight()

    pos_x = (scr_w - outer_w) // 2
    pos_y = (scr_h - outer_h) // 2

    root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
    
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    
    root.mainloop()
