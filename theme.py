import copy
import json
import os
import re
import sys

from PyQt6.QtGui import QColor

DEFAULT_THEME = {
    "accent": "auto",
    "font_family": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
    "text": {
        "primary": "#FFFFFF",
        "secondary": "#A0A0A0",
        "muted": "#888888",
        "dim": "#AAAAAA",
        "perf": "#CCCCCC",
        "heading_muted": "#BBBBBB",
        "title_size": 13,
        "subtitle_size": 11,
    },
    "island": {
        "background": "#000000",
        "border_color": "rgba(255,255,255,0.12)",
        "border_width": 1.2,
        "radius": 30,
        "notch_radius": 18,
        "notch_scoop": 25,
        "shadow_color": "#000000",
        "shadow_alpha": 15,
        "shadow_layers": 5,
    },
    "animation": {
        "phase_speed": 0.005,
        "blob_color": "album",
        "blob_alpha": 100,
        "blob_secondary_lighten": 125,
        "blob_sizes": [0.45, 0.35],
        "glow_color": "album",
        "glow_alpha": 120,
        "neon_colors": ["#FF0000", "#FFFF00", "#00FF00", "#00FFFF", "#0000FF", "#FF00FF"],
        "neon_width": 2.2,
        "shine_colors": ["#FFFFFF", "#00A0FF", "#5A00FF"],
    },
    "charging": {
        "glow_colors": ["#00FFFF", "#8C00FF"],
        "beam_colors": ["#FFFFFF", "#00F0FF", "#A000FF"],
        "dot_color": "#FFFFFF",
    },
    "panels": {
        "weather": {"top": "rgb(20,40,100)", "bottom": "rgb(10,20,60)",
                    "blooms": ["rgba(60,130,250,0.47)", "rgba(40,80,220,0.39)"], "bloom_size": 0.6},
        "perf": {"top": "rgb(0,40,20)", "bottom": "rgb(0,20,10)",
                 "blooms": ["rgba(50,255,50,0.31)", "rgba(200,255,0,0.24)"], "bloom_size": 0.5},
        "calendar": {"top": "rgb(60,40,0)", "bottom": "rgb(30,20,0)",
                     "blooms": ["rgba(255,180,0,0.35)", "rgba(255,255,0,0.24)"], "bloom_size": 0.55},
        "month": {"top": "rgb(30,0,50)", "bottom": "rgb(15,0,30)",
                  "blooms": ["rgba(180,0,255,0.31)", "rgba(255,0,180,0.24)"], "bloom_size": 0.5},
    },
    "buttons": {
        "text": "#FFFFFF",
        "action_bg": "rgba(255,255,255,0.06)",
        "action_bg_hover": "rgba(255,255,255,0.14)",
        "action_bg_pressed": "rgba(255,255,255,0.20)",
        "action_border": "rgba(255,255,255,0.04)",
        "action_border_hover": "rgba(255,255,255,0.16)",
        "media_hover": "rgba(255,255,255,0.12)",
        "media_pressed": "rgba(255,255,255,0.20)",
        "ball_bg": "#000000",
        "ball_bg_hover": "#282828",
        "ball_border": "rgba(255,255,255,0.16)",
        "ball_border_hover": "rgba(255,255,255,0.31)",
        "nav": "#888888",
        "nav_hover": "#FFFFFF",
    },
    "progress": {"track": "#222222", "from": "#00FF80", "to": "#80FF00"},
    "inputs": {
        "background": "rgba(255,255,255,0.05)",
        "border": "rgba(255,255,255,0.06)",
        "radius": 8,
        "list_item_bg": "rgba(255,255,255,0.04)",
    },
    "menu": {"background": "#1A1A1A", "text": "#FFFFFF", "border": "#333333"},
    "month_progress": {"percent": "#00A0FF"},
    # Raw Qt stylesheet (QSS) appended last. Selectors: QLabel, QPushButton#MediaButton, etc.
    "custom_qss": "",
}


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def theme_path():
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "theme.json")


def load_theme():
    """Defaults deep-merged with theme.json. Returns (theme, mtime)."""
    theme = copy.deepcopy(DEFAULT_THEME)
    path = theme_path()
    mtime = 0.0
    if os.path.exists(path):
        try:
            mtime = os.path.getmtime(path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _merge(theme, data)
            qss_file = theme.get("custom_qss_file")
            if qss_file:
                qp = os.path.join(os.path.dirname(path), qss_file)
                if os.path.exists(qp):
                    with open(qp, "r", encoding="utf-8") as f:
                        theme["custom_qss"] = (theme.get("custom_qss") or "") + "\n" + f.read()
        except Exception as e:
            print(f"theme.json ignored: {e}")
    return theme, mtime


def write_default_theme():
    path = theme_path()
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_THEME, f, indent=4)
    return path


_RGBA = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", re.I)


def qcolor(value, fallback="#FFFFFF"):
    """Parse '#RGB', '#RRGGBB', '#RRGGBBAA' (CSS order), 'rgb()', 'rgba(r,g,b,0-1)' or a named color."""
    if isinstance(value, QColor):
        return QColor(value)
    s = str(value).strip()
    m = _RGBA.fullmatch(s)
    if m:
        r, g, b = (min(255, int(float(m.group(i)))) for i in (1, 2, 3))
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        return QColor(r, g, b, max(0, min(255, round(a * 255))))
    if s.startswith("#") and len(s) == 9:
        return QColor(int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16), int(s[7:9], 16))
    c = QColor(s)
    return c if c.isValid() else QColor(fallback)


def css(value):
    """QSS-safe rgba() string for any accepted color value."""
    c = qcolor(value)
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()})"
