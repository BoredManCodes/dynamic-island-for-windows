import base64
import json
import os
import shutil
import tempfile
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor

from theme import _RGBA

MAX_BODY = 8 * 1024 * 1024
MAX_ICON_BYTES = 1024 * 1024
MAX_SOUND_BYTES = 5 * 1024 * 1024
SOUND_EXTS = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".wma")
LOCAL_HOST = "127.0.0.1"
ALL_HOSTS = "0.0.0.0"
MODES = ("marquee", "expand")


def valid_color(s):
    s = s.strip()
    return bool(_RGBA.fullmatch(s)) or (s.startswith("#") and len(s) == 9) or QColor(s).isValid()


def parse_alert(data):
    if not isinstance(data, dict): raise ValueError("body must be a JSON object")
    title, text = data.get("title", ""), data.get("text", "")
    if not isinstance(title, str) or not isinstance(text, str): raise ValueError("title and text must be strings")
    if not (title.strip() or text.strip()): raise ValueError("title or text is required")
    alert = {"title": title[:200], "text": text[:4000], "sticky": data.get("sticky", False) is True}
    mode = data.get("mode", "marquee")
    if mode not in MODES: raise ValueError("mode must be 'marquee' or 'expand'")
    alert["mode"] = mode
    color = data.get("color")
    if color is not None:
        if not isinstance(color, str) or not valid_color(color): raise ValueError("color is not a valid color")
        alert["color"] = color
    dur = data.get("duration_ms")
    if dur is not None:
        if isinstance(dur, bool) or not isinstance(dur, int) or not 250 <= dur <= 600000: raise ValueError("duration_ms must be an integer from 250 to 600000")
        alert["duration_ms"] = dur
    icon = data.get("icon")
    if icon is not None:
        if not isinstance(icon, str): raise ValueError("icon must be a string")
        alert["icon"] = icon.strip()[:2000]
    sound = data.get("sound")
    if sound is not None:
        if not isinstance(sound, str): raise ValueError("sound must be a string")
        alert["sound"] = sound.strip()
    return alert


def fetch_bytes(url, limit, timeout=3):
    req = urllib.request.Request(url, headers={"User-Agent": "DynamicIsland"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(limit + 1)
    return data if len(data) <= limit else None


def fetch_icon(url): return fetch_bytes(url, MAX_ICON_BYTES)


def sniff_sound_ext(data):
    if data[:4] == b"RIFF": return ".wav"
    if data[:4] == b"OggS": return ".ogg"
    if data[:4] == b"fLaC": return ".flac"
    if data[4:8] == b"ftyp": return ".m4a"
    return ".mp3"


class SoundStore:
    def __init__(self): self.dir = None

    def save(self, data, ext):
        if self.dir is None: self.dir = tempfile.mkdtemp(prefix="dynisland_snd_")
        fd, path = tempfile.mkstemp(suffix=ext if ext in SOUND_EXTS else sniff_sound_ext(data), dir=self.dir)
        with os.fdopen(fd, "wb") as f: f.write(data)
        return path

    def resolve(self, spec):
        low = spec.lower()
        if low.startswith(("http://", "https://")):
            data = fetch_bytes(spec, MAX_SOUND_BYTES, 8)
            return self.save(data, os.path.splitext(urllib.parse.urlparse(spec).path)[1].lower()) if data else None
        if low.startswith("data:"):
            data = base64.b64decode(spec.split(",", 1)[1])
            return self.save(data, "") if 0 < len(data) <= MAX_SOUND_BYTES else None
        if os.path.isfile(spec) and os.path.splitext(spec)[1].lower() in SOUND_EXTS: return spec
        data = base64.b64decode(spec, validate=True)
        return self.save(data, "") if 0 < len(data) <= MAX_SOUND_BYTES else None

    def cleanup(self):
        if self.dir: shutil.rmtree(self.dir, ignore_errors=True); self.dir = None


class ApiServer(QObject):
    alert_received = pyqtSignal(dict)
    dismiss_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.httpd = None; self.thread = None; self.error = ""; self.sounds = SoundStore()

    @property
    def running(self): return self.httpd is not None

    def start(self, port, token, host=LOCAL_HOST):
        self.stop(); self.error = ""
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def reply(self, code, body):
                raw = json.dumps(body).encode()
                self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers()
                self.wfile.write(raw)

            def authorized(self):
                if not token: return True
                got = self.headers.get("Authorization", "")
                got = got[7:] if got.lower().startswith("bearer ") else self.headers.get("X-Token", "")
                return got == token

            def do_GET(self):
                if self.path == "/health": self.reply(200, {"ok": True})
                else: self.reply(404, {"ok": False, "error": "not found"})

            def do_POST(self):
                if self.path not in ("/notify", "/dismiss"): return self.reply(404, {"ok": False, "error": "not found"})
                if not self.authorized(): return self.reply(401, {"ok": False, "error": "bad token"})
                if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                    return self.reply(415, {"ok": False, "error": "Content-Type must be application/json"})
                try: n = int(self.headers.get("Content-Length", "0"))
                except ValueError: n = -1
                if not 0 <= n <= MAX_BODY: return self.reply(413, {"ok": False, "error": "body missing or over 8 MB"})
                try: data = json.loads(self.rfile.read(n) or b"{}")
                except ValueError: return self.reply(400, {"ok": False, "error": "invalid JSON"})
                if self.path == "/dismiss":
                    server.dismiss_requested.emit(); return self.reply(200, {"ok": True})
                try: alert = parse_alert(data)
                except ValueError as e: return self.reply(400, {"ok": False, "error": str(e)})
                icon = alert.get("icon", "")
                if icon.lower().startswith(("http://", "https://")):
                    try: alert["icon_bytes"] = fetch_icon(icon)
                    except Exception: alert["icon_bytes"] = None
                if alert.get("sound"):
                    try: alert["sound_path"] = server.sounds.resolve(alert["sound"])
                    except Exception: alert["sound_path"] = None
                server.alert_received.emit(alert); self.reply(200, {"ok": True})

        try: self.httpd = ThreadingHTTPServer((ALL_HOSTS if host == ALL_HOSTS else LOCAL_HOST, int(port)), Handler)
        except OSError as e:
            self.httpd = None; self.error = str(e); return False
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True); self.thread.start()
        return True

    def stop(self):
        if self.httpd is None: return
        httpd, self.httpd = self.httpd, None
        httpd.shutdown(); httpd.server_close()
