import sys
import psutil
import winreg
import ctypes
import datetime
import time
import threading
import math
import qtawesome as qta
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QPropertyAnimation, QEasingCurve, QPoint, QParallelAnimationGroup, QPointF, QAbstractAnimation, pyqtProperty
from PyQt6.QtGui import (QCursor, QPainter, QColor, QBrush, QPaintEvent, 
                         QLinearGradient, QRadialGradient, QConicalGradient, QAction, QPen, QPainterPath, QRegion, QPixmap)
from api_server import ApiServer
import json
import os
import re
import webbrowser
import subprocess

from app_styles import get_stylesheet
from theme import load_theme, write_default_theme, update_theme_file, theme_path, qcolor, css
from settings_dialog import SettingsDialog

def css_hex(v):
    return qcolor(v).name()
from perf_monitor import PerfMonitor
from media_monitor import MediaMonitor
from event_monitor import KeyLockMonitor
from audio_monitor import AudioMonitor
from notification_monitor import NotificationMonitor
from weather_monitor import WeatherMonitor
from weather_bg import WeatherScene
from outlook_monitor import OutlookMonitor
from volume_monitor import VolumeMonitor
from network_monitor import NetworkMonitor
from brightness_monitor import BrightnessMonitor
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QMenu, QPushButton, QGraphicsOpacityEffect, 
                             QGridLayout, QFrame, QProgressBar, QInputDialog,
                             QDialog, QLineEdit, QListWidget, QListWidgetItem,
                             QComboBox, QScrollArea)

               
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMSBT_DISABLE = 1
DWMWCP_ROUND = 2

DEFAULT_TASKS = [
    {"name": "Project Sync", "category": "Work", "color": "#00A0FF", "time": "2:00 PM"},
    {"name": "Gym Session", "category": "Health", "color": "#00FF80", "time": "5:30 PM"},
    {"name": "Dinner with Family", "category": "Personal", "color": "#FF5050", "time": "8:00 PM"}
]

class ToggleSwitch(QWidget):
    ON_COLOR, OFF_COLOR = QColor("#34C759"), QColor("#FF3B30")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 28); self._pos = 0.0
        self.anim = QPropertyAnimation(self, b"knob", self); self.anim.setDuration(260); self.anim.setEasingCurve(QEasingCurve.Type.OutBack)

    def get_pos(self): return self._pos
    def set_pos(self, v): self._pos = v; self.update()
    knob = pyqtProperty(float, get_pos, set_pos)

    def set_checked(self, on, animate=True):
        self.anim.stop()
        if animate:
            self.anim.setStartValue(self._pos); self.anim.setEndValue(1.0 if on else 0.0); self.anim.start()
        else: self.set_pos(1.0 if on else 0.0)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
        t = max(0.0, min(1.0, self._pos)); a, b = self.OFF_COLOR, self.ON_COLOR
        p.setBrush(QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t), int(a.blue() + (b.blue() - a.blue()) * t)))
        h = self.height(); p.drawRoundedRect(QRectF(0, 0, self.width(), h), h / 2, h / 2)
        d = h - 6; x = 3 + (self.width() - d - 6) * self._pos
        p.setBrush(QColor(0, 0, 0, 40)); p.drawEllipse(QRectF(x, 4, d, d))
        p.setBrush(QColor("white")); p.drawEllipse(QRectF(x, 3, d, d))

class VolumeBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(110, 8); self.value = 0; self.muted = False; self.fill = QColor("white")
        self.fill_anim = QPropertyAnimation(self, b"shown", self); self.fill_anim.setDuration(1100); self.fill_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_value(self, value, muted, fill):
        self.fill_anim.stop(); self.value = value; self.muted = muted; self.fill = QColor(fill); self.update()

    def get_shown(self): return self.value
    def set_shown(self, v): self.value = v; self.update()
    shown = pyqtProperty(float, get_shown, set_shown)

    def fill_to(self, value, fill):
        self.fill_anim.stop(); self.muted = False; self.fill = QColor(fill); self.value = 0
        self.fill_anim.setStartValue(0.0); self.fill_anim.setEndValue(float(value)); self.fill_anim.start()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
        r = self.height() / 2; p.setBrush(QColor(255, 255, 255, 50)); p.drawRoundedRect(QRectF(self.rect()), r, r)
        w = self.width() * max(0, min(100, self.value)) / 100
        if w > 0: p.setBrush(QColor(150, 150, 150) if self.muted else self.fill); p.drawRoundedRect(QRectF(0, 0, max(w, self.height()), self.height()), r, r)

class IslandMirror(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents); self.frame = None

    def set_frame(self, pm): self.frame = pm; self.update()

    def showEvent(self, event):
        super().showEvent(event); DynamicIsland.remove_dwm_border(self)

    def paintEvent(self, e):
        if self.frame is None: return
        p = QPainter(self); p.drawPixmap(self.rect(), self.frame)

class MarqueeLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.full = ""; self.color = QColor("white"); self.offset = 0.0; self.pause = 0; self.gap = 40
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick)

    def set_marquee(self, text, color):
        self.full = text; self.color = QColor(color); self.offset = 0.0; self.pause = 40; self.update()

    def showEvent(self, e): super().showEvent(e); self.timer.start(25)

    def hideEvent(self, e): super().hideEvent(e); self.timer.stop()

    def tick(self):
        tw = self.fontMetrics().horizontalAdvance(self.full)
        if tw <= self.width(): self.offset = 0.0; return
        if self.pause > 0: self.pause -= 1; return
        self.offset += 1.5
        if self.offset >= tw + self.gap: self.offset = 0.0; self.pause = 40
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setFont(self.font()); p.setPen(self.color)
        fm = self.fontMetrics(); y = (self.height() + fm.ascent() - fm.descent()) // 2; tw = fm.horizontalAdvance(self.full)
        if tw <= self.width(): p.drawText(0, y, self.full); return
        p.drawText(int(-self.offset), y, self.full); p.drawText(int(-self.offset + tw + self.gap), y, self.full)


class ControlBall(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ControlBall")
        self.setFixedSize(40, 40)
        self._ball_scale = 1.0
        self.action_cmd = None
        self.clicked.connect(self.execute_action)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)
        
    @pyqtProperty(float)
    def ball_scale(self): return self._ball_scale
    @ball_scale.setter
    def ball_scale(self, val):
        self._ball_scale = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._ball_scale != 1.0:
            painter.translate(self.width()/2, self.height()/2)
            painter.scale(self._ball_scale, self._ball_scale)
            painter.translate(-self.width()/2, -self.height()/2)
        super().paintEvent(event)
        
    def execute_action(self):
        if self.action_cmd:
            if isinstance(self.action_cmd, str) and self.action_cmd.startswith("http"):
                webbrowser.open(self.action_cmd)
            else:
                try: subprocess.Popen(self.action_cmd, shell=True)
                except: pass

    def animate_to(self, pos, opacity, scale=1.0, duration=600, delay=0):
        if hasattr(self, "_current_anim"):
            self._current_anim.stop()
        
        self._current_anim = QParallelAnimationGroup(self)
        
                            
        p_anim = QPropertyAnimation(self, b"pos")
        p_anim.setDuration(duration)
        p_anim.setEasingCurve(QEasingCurve.Type.OutBack if opacity > 0 else QEasingCurve.Type.OutExpo)
        p_anim.setEndValue(pos)
        
                           
        o_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        o_anim.setDuration(duration)
        o_anim.setEndValue(opacity)

                         
        s_anim = QPropertyAnimation(self, b"ball_scale")
        s_anim.setDuration(duration)
        s_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        s_anim.setEndValue(scale)
        
        self._current_anim.addAnimation(p_anim)
        self._current_anim.addAnimation(o_anim)
        self._current_anim.addAnimation(s_anim)
        
        if delay > 0:
            QTimer.singleShot(delay, self._current_anim.start)
        else:
            self._current_anim.start()

# TaskEditorDialog class removed since we are integrating it directly into the island.

class DynamicIsland(QWidget):
    def __init__(self):
        super().__init__()
        
                                                                        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        
        self.compatibility_mode = False
        
        self.theme, self._theme_mtime = load_theme()
        self.accent_color = self.get_windows_accent_color() if str(self.theme['accent']).lower() == 'auto' else css_hex(self.theme['accent'])
        self.album_accent_color = QColor(0, 0, 0); self.weather_icon = None
        self.gradient_phase = 0.0
        self.animation_style = "Fluid Blobs"
        self.island_style = "Default" 
        
        self.setObjectName("IslandWidget")
        self.setStyleSheet(get_stylesheet(self.accent_color, self.theme))
        
        self.last_power_plugged = psutil.sensors_battery().power_plugged if psutil.sensors_battery() else False
        
                                                         
        self._island_w = 180
        self._island_h = 40
        self.island_w_anim = QPropertyAnimation(self, b"island_w")
        self.island_h_anim = QPropertyAnimation(self, b"island_h")
        for anim in [self.island_w_anim, self.island_h_anim]:
            anim.setDuration(850); anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self.grow_w_anim = QPropertyAnimation(self, b"island_w"); self.grow_h_anim = QPropertyAnimation(self, b"island_h")
        self.grow_base = None
            
        self.shine_phase = -1.0
        self.shine_anim = QPropertyAnimation(self, b"shine_phase")
        self.shine_anim.setDuration(1800)
        self.shine_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        self.charging_phase = 0.0; self.charge_samples = []
        self.charging_anim = QPropertyAnimation(self, b"charging_phase")
        self.charging_anim.setDuration(3000)
        self.charging_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        self.is_dialog_open = False
        self.is_editing_tasks = False
        
        self._weather_bg_opacity = 0.0
        self.weather_bg_anim = QPropertyAnimation(self, b"weather_bg_opacity")
        self.weather_bg_anim.setDuration(1200)
        self.weather_bg_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        self.weather_bg_phase = 0.0
        self.weather_scene = WeatherScene(); self.weather_has_data = False
        
        self._perf_bg_opacity = 0.0
        self.perf_bg_anim = QPropertyAnimation(self, b"perf_bg_opacity")
        self.perf_bg_anim.setDuration(1200)
        self.perf_bg_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._calendar_bg_opacity = 0.0
        self.calendar_bg_anim = QPropertyAnimation(self, b"calendar_bg_opacity")
        self.calendar_bg_anim.setDuration(1200)
        self.calendar_bg_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._month_bg_opacity = 0.0
        self.month_bg_anim = QPropertyAnimation(self, b"month_bg_opacity")
        self.month_bg_anim.setDuration(1200)
        self.month_bg_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.power_timer = QTimer(self)
        self.power_timer.timeout.connect(self.check_power_status)
        self.power_timer.start(2000)
        
                              
        self.IDLE_W, self.IDLE_H = 180, 40
        self.EXP_W, self.EXP_H = 340, 100
        self.PERF_W, self.PERF_H = 360, 180
        self.MUSIC_W, self.MUSIC_H = 420, 40
        self.NOTIFY_W, self.NOTIFY_H = 380, 40
        self.WEATHER_W, self.WEATHER_H = 360, 160
        self.CALENDAR_W, self.CALENDAR_H = 420, 165
        self.MONTH_W, self.MONTH_H = 360, 140
        self.EDIT_W, self.EDIT_H = 540, 520
        self.WIDE_W = 1200                                             
        
        self.is_charging = False
        
        self.current_state = "Idle"
        self.media_state = "Idle"
        self.media_title, self.media_artist = "", ""
        self.ALL_CARDS = ["perf", "media", "weather", "calendar", "month", "basics"]
        self.features = list(self.ALL_CARDS)
        self.current_feature_index = 0
        self.showing_lyrics = False
        self.media_lyric_text = ""
        self.LYRIC_W = 640; self.COUNTDOWN_W = 300; self.cd_active = False; self.cd_name_text = ""
        
                            
        self.basic_controls_index = 0
        self.basic_controls_items = [
            {"name": "Shutdown", "icon": "mdi.power", "cmd": "shutdown /s /t 0"},
            {"name": "Restart", "icon": "mdi.refresh", "cmd": "shutdown /r /t 0"},
            {"name": "Sleep", "icon": "mdi.sleep", "cmd": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0"},
            {"name": "File Explorer", "icon": "mdi.folder-outline", "cmd": "explorer ."},
            {"name": "Settings", "icon": "mdi.cog-outline", "cmd": "start ms-settings:"},
            {"name": "Task Manager", "icon": "mdi.chart-bubble", "cmd": "taskmgr"},
            {"name": "Chrome", "icon": "mdi.google-chrome", "cmd": "start chrome"},
            {"name": "YouTube", "icon": "mdi.youtube", "cmd": "https://www.youtube.com"},
            {"name": "CMD", "icon": "mdi.console", "cmd": "start cmd"}
        ]
        self.control_balls = []
        
                                  
        self.event_title, self.event_text = "", ""; self.key_event_on = None
        self.revert_timer = QTimer(self); self.revert_timer.setSingleShot(True); self.revert_timer.timeout.connect(self.on_revert)
        self.alert = None; self.alert_queue = []; self.alert_size = (self.NOTIFY_W, self.NOTIFY_H)
        self._alert_tint = 0.0; self.alert_tint_color = None
        self.tint_anim = QPropertyAnimation(self, b"alert_tint"); self.tint_anim.setDuration(400)

        self.outlook = {"status": "", "events": [], "tasks": [], "unread": 0}; self.outlook_alerted = set(); self.last_unread = None
        self.mirrors = {}; self.mirror_timer = QTimer(self); self.mirror_timer.timeout.connect(self.refresh_mirrors)
        self.load_settings(); self.apply_cards()
        self.setup_monitors()
        self.init_ui()
        self.setup_autostart()
        self.apply_outlook()
        
        self.master_timer = QTimer(self); self.master_timer.timeout.connect(self.update_content); self.master_timer.timeout.connect(self.check_theme_reload); self.master_timer.start(1000)
        self.anim_timer = QTimer(self); self.anim_timer.timeout.connect(self.update_animation); self.anim_timer.start(16)
        self.apply_behavior(); self.hover_enter_t = None
        self.hit_timer = QTimer(self); self.hit_timer.timeout.connect(self.check_mouse_position); self.hit_timer.start(25)
        
                                                                            
        self.setFixedSize(1200, 700); self.recenter_window()
        for sig in (QApplication.instance().screenAdded, QApplication.instance().screenRemoved, QApplication.instance().primaryScreenChanged): sig.connect(lambda *_: QTimer.singleShot(500, self.recenter_window))
        
        self.anim_group = QParallelAnimationGroup()
        self.opacity_anim = QPropertyAnimation(self.content_opacity, b"opacity"); self.opacity_anim.setDuration(850); self.opacity_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.content_pos_anim = QPropertyAnimation(self.content_container, b"pos"); self.content_pos_anim.setDuration(850); self.content_pos_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        
        self.anim_group.addAnimation(self.island_w_anim); self.anim_group.addAnimation(self.island_h_anim)
        self.anim_group.addAnimation(self.opacity_anim); self.anim_group.addAnimation(self.content_pos_anim)

    @pyqtProperty(float)
    def alert_tint(self): return self._alert_tint
    @alert_tint.setter
    def alert_tint(self, val): self._alert_tint = val; self.update()

    @pyqtProperty(float)
    def weather_bg_opacity(self): return self._weather_bg_opacity
    @weather_bg_opacity.setter
    def weather_bg_opacity(self, val): self._weather_bg_opacity = val; self.update()

    @pyqtProperty(float)
    def perf_bg_opacity(self): return self._perf_bg_opacity
    @perf_bg_opacity.setter
    def perf_bg_opacity(self, val): self._perf_bg_opacity = val; self.update()

    @pyqtProperty(float)
    def calendar_bg_opacity(self): return self._calendar_bg_opacity
    @calendar_bg_opacity.setter
    def calendar_bg_opacity(self, val): self._calendar_bg_opacity = val; self.update()

    @pyqtProperty(float)
    def month_bg_opacity(self): return self._month_bg_opacity
    @month_bg_opacity.setter
    def month_bg_opacity(self, val): self._month_bg_opacity = val; self.update()

    def load_settings(self):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        self.config_path = os.path.join(base_path, "config.json")
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    self.settings = json.load(f)
            except:
                self.settings = {"location": "Varanasi, India", "lat": 25.3333, "lon": 83.0, "compatibility_mode": False, "tasks": DEFAULT_TASKS}
        else:
            self.settings = {"location": "Varanasi, India", "lat": 25.3333, "lon": 83.0, "compatibility_mode": False, "tasks": DEFAULT_TASKS}
        
        if "tasks" not in self.settings:
            self.settings["tasks"] = DEFAULT_TASKS
        
        self.compatibility_mode = self.settings.get("compatibility_mode", False)
        self.island_style = self.settings.get("island_style", "Default")
        self.animation_style = self.settings.get("animation_style", "Fluid Blobs")
        
        if hasattr(self, 'weather_monitor'):
            self.weather_monitor.city = self.settings.get("location", "Varanasi, India")
            self.weather_monitor.lat = self.settings.get("lat", 25.3333)
            self.weather_monitor.lon = self.settings.get("lon", 83.0)
            self.weather_monitor.refresh()

    def save_settings(self):
        self.settings["location"] = self.weather_monitor.city
        self.settings["lat"] = self.weather_monitor.lat
        self.settings["lon"] = self.weather_monitor.lon
        self.settings["compatibility_mode"] = self.compatibility_mode
        self.settings["island_style"] = self.island_style
        self.settings["animation_style"] = self.animation_style
        # self.settings["tasks"] is updated directly by the task editor or elsewhere
        with open(self.config_path, "w") as f:
            json.dump(self.settings, f, indent=4)

    def change_location_dialog(self):
        city, ok = QInputDialog.getText(self, "Change Location", "Enter City Name:", text=self.weather_monitor.city)
        if ok and city:
            success, msg = self.weather_monitor.set_location(city)
            if success:
                self.save_settings()
                self.show_notification("Weather", "Location Updated", f"Now showing weather for {msg}")
            else:
                self.show_notification("Weather", "Error", f"Could not find location: {city}")

    def get_current_radius(self):
        if self.island_style == "Notch Nook":
            return min(self._island_h / 2.0, float(self.theme['island']['notch_radius']))
        return min(self._island_h / 2.0, float(self.theme['island']['radius']))

    @pyqtProperty(int)
    def island_w(self): return self._island_w
    @island_w.setter
    def island_w(self, val): 
        self._island_w = val
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())
        self.update()

    @pyqtProperty(int)
    def island_h(self): return self._island_h
    @island_h.setter
    def island_h(self, val): 
        self._island_h = val
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())
        self.update()

    def build_notch_path(self, rect):
        radius = self.get_current_radius()
        scoop = min(radius * 1.4, float(self.theme['island']['notch_scoop']))
        path = QPainterPath()
        path.moveTo(rect.left() - scoop, rect.top())
        path.cubicTo(
            rect.left() - scoop * 0.05, rect.top(),
            rect.left(), rect.top() + scoop * 0.05,
            rect.left(), rect.top() + scoop
        )
        path.lineTo(rect.left(), rect.bottom() - radius)
        path.quadTo(rect.left(), rect.bottom(), rect.left() + radius, rect.bottom())
        path.lineTo(rect.right() - radius, rect.bottom())
        path.quadTo(rect.right(), rect.bottom(), rect.right(), rect.bottom() - radius)
        path.lineTo(rect.right(), rect.top() + scoop)
        path.cubicTo(
            rect.right(), rect.top() + scoop * 0.05,
            rect.right() + scoop * 0.05, rect.top(),
            rect.right() + scoop, rect.top()
        )
        path.lineTo(rect.left() - scoop, rect.top())
        path.closeSubpath()
        return path

    def _draw_shape(self, painter, rect, radius):
        if self.island_style == "Notch Nook":
            painter.drawPath(self.build_notch_path(rect))
        else:
            painter.drawRoundedRect(rect, radius, radius)

    def paintEvent(self, a0: QPaintEvent):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.get_island_rect()
        p_rect = rect.adjusted(1, 1, -1, -1)
        radius = self.get_current_radius()
        is_notch = self.island_style == "Notch Nook"

        if self.charging_phase > 0.0:
            self.paint_charging_ears(painter, rect, radius)
        
        painter.setPen(Qt.PenStyle.NoPen)
        isl = self.theme['island']
        bg = qcolor(isl['background'])
        if self._alert_tint > 0 and self.alert_tint_color is not None:
            t = self._alert_tint; c = self.alert_tint_color
            bg = QColor(*(int(a + (b - a) * t) for a, b in ((bg.red(), c.red()), (bg.green(), c.green()), (bg.blue(), c.blue()), (bg.alpha(), c.alpha()))))
        shadow = qcolor(isl['shadow_color']); n_sh = int(isl['shadow_layers']); a_sh = int(isl['shadow_alpha'])

        if is_notch:
            notch_path = self.build_notch_path(rect)
            for i in range(n_sh):
                shadow.setAlpha(max(0, a_sh - i*3)); painter.setBrush(QColor(shadow))
                shadow_rect = rect.adjusted(i, 0, -i, -i)
                painter.drawPath(self.build_notch_path(shadow_rect))
            painter.setBrush(QBrush(bg))
            painter.drawPath(notch_path)
        else:
            for i in range(n_sh):
                shadow.setAlpha(max(0, a_sh - i*3)); painter.setBrush(QColor(shadow))
                painter.drawRoundedRect(rect.adjusted(i, i, -i, -i), radius, radius)
            painter.setBrush(QBrush(bg)); painter.drawRoundedRect(rect, radius, radius)

        if self._weather_bg_opacity > 0.0:
            self.paint_weather_bg(painter, rect, radius)
        if self._perf_bg_opacity > 0.0:
            self.paint_perf_bg(painter, rect, radius)
        if self._calendar_bg_opacity > 0.0:
            self.paint_calendar_bg(painter, rect, radius)
        if self._month_bg_opacity > 0.0:
            self.paint_month_bg(painter, rect, radius)
            
        clip_path = QPainterPath()
        if is_notch:
            clip_path = self.build_notch_path(rect)
        else:
            clip_path.addRoundedRect(QRectF(rect), radius, radius)
        painter.setClipPath(clip_path)

        can_anim = (self.current_state in ("Hover", "Notify") and self.features[self.current_feature_index] == "media") or\
                   (self.current_state == "Idle" and self.features[self.current_feature_index] == "media" and self.media_state in ("Playing", "Paused"))
        
        if can_anim:
            if self.animation_style == "Glow Sweep": self.paint_glow_sweep(painter, rect, radius)
            elif self.animation_style == "Fluid Blobs": self.paint_fluid_blobs(painter, rect, radius)
            elif self.animation_style == "Neon Border": self.paint_neon_border(painter, rect, radius)
            elif self.animation_style == "Equaliser": self.paint_equaliser(painter, rect, radius)
        else:
            if not is_notch:
                painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(qcolor(self.theme['island']['border_color']), float(self.theme['island']['border_width'])))
                painter.drawRoundedRect(p_rect, radius, radius)

        if self.shine_phase > 0.0 and self.shine_phase < 1.0:
            self.paint_shine_sweep(painter, rect, radius)
        
        painter.setClipping(False)                   
                                     

    def paint_shine_sweep(self, painter, rect, radius):
        import math
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        
                                                               
        p = self.shine_phase
        if p <= 0 or p >= 1.0: return
        
                                                    
        opacity = math.sin(p * math.pi)
        
        start_x = 35
        max_reach = rect.width() * 1.5
        current_expansion = max_reach * p
        base_alpha = int(220 * math.sin(p * math.pi))
        for i in range(2):
            jitter_x = 0; jitter_y = 0
            W = current_expansion * (0.6 + i * 0.1)
            h = rect.height()
            target_x = start_x + (current_expansion * 0.4) + jitter_x
            target_y = (h / 2) + jitter_y
            painter.save()
            painter.translate(target_x, target_y)
            painter.scale(2.5, 0.8) 
            grad = QRadialGradient(QPointF(0, 0), W / 2)
            alpha = int(base_alpha * (1.0 - i * 0.3))
            sc0, sc1, sc2 = (qcolor(c) for c in (self.theme['animation']['shine_colors'] + ["#FFFFFF"] * 3)[:3])
            for c_, a_ in ((sc0, alpha), (sc1, int(alpha * 0.6)), (sc2, int(alpha * 0.15))): c_.setAlpha(a_)
            grad.setColorAt(0.0, sc0)
            grad.setColorAt(0.3, sc1)
            grad.setColorAt(0.6, sc2)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(grad); painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(0, 0), W / 2, W / 2)
            painter.restore()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def paint_glow_sweep(self, painter, rect, radius):
        from PyQt6.QtGui import QTransform
        glow = self.anim_color('glow_color'); glow.setAlpha(int(self.theme['animation']['glow_alpha']))
        gradient = QLinearGradient(0, 0, rect.width(), 0); gradient.setSpread(QLinearGradient.Spread.RepeatSpread)
        gradient.setColorAt(0.0, Qt.GlobalColor.transparent); gradient.setColorAt(0.5, glow); gradient.setColorAt(1.0, Qt.GlobalColor.transparent)
        brush = QBrush(gradient); transform = QTransform(); transform.translate(self.gradient_phase * rect.width() * 2, 0); brush.setTransform(transform)
        painter.setBrush(brush); self._draw_shape(painter, rect, radius)

    def paint_fluid_blobs(self, painter, rect, radius):
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        an = self.theme['animation']; glow_color = self.anim_color('blob_color'); glow_color.setAlpha(int(an['blob_alpha'])); p = self.gradient_phase * 2 * math.pi
        x1, y1 = rect.width() * (0.2 + 0.15 * math.sin(p)), rect.height() * (0.5 + 0.25 * math.cos(p))
        g1 = QRadialGradient(x1, y1, rect.width() * float(an['blob_sizes'][0])); g1.setColorAt(0, glow_color); g1.setColorAt(1, Qt.GlobalColor.transparent)
        painter.setBrush(g1); self._draw_shape(painter, rect, radius)
        x2, y2 = rect.width() * (0.8 + 0.15 * math.cos(p * 0.7)), rect.height() * (0.5 + 0.25 * math.sin(p * 1.2))
        g2 = QRadialGradient(x2, y2, rect.width() * float(an['blob_sizes'][1])); g2.setColorAt(0, QColor(glow_color).lighter(int(an['blob_secondary_lighten']))); g2.setColorAt(1, Qt.GlobalColor.transparent)
        painter.setBrush(g2); self._draw_shape(painter, rect, radius)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def paint_equaliser(self, painter, rect, radius):
        an = self.theme['animation']; n = max(4, int(an['eq_bars']))
        vals = self._eq_vals; slot = rect.width() / n; bw = slot * 0.6; max_h = rect.height() * float(an['eq_height'])
        col = self.anim_color('eq_color'); top = QColor(col); top.setAlpha(int(an['eq_alpha'])); bot = QColor(col); bot.setAlpha(int(an['eq_alpha']) // 4)
        grad = QLinearGradient(0, rect.bottom(), 0, rect.bottom() - max_h); grad.setColorAt(0, bot); grad.setColorAt(1, top)
        painter.setBrush(grad); painter.setPen(Qt.PenStyle.NoPen)
        for i in range(n):
            v = vals[i * len(vals) // n] if vals else 0.0
            h = max_h * v + 2.0
            painter.drawRoundedRect(QRectF(rect.x() + slot * i + (slot - bw) / 2, rect.bottom() + 1 - h, bw, h), bw / 2, bw / 2)

    def on_audio_levels(self, levels):
        old = self._eq_vals
        if not levels: self._eq_vals = [v * 0.8 for v in old]
        elif len(old) != len(levels): self._eq_vals = list(levels)
        else: self._eq_vals = [max(l, o * 0.82) for l, o in zip(levels, old)]

    def update_audio_capture(self):
        want = self.animation_style == "Equaliser"
        if want and self.audio_monitor is None:
            self.audio_monitor = AudioMonitor(int(self.theme['animation']['eq_bars']), self); self.audio_monitor.levels_updated.connect(self.on_audio_levels); self.audio_monitor.start()
        elif not want and self.audio_monitor is not None:
            self.audio_monitor.levels_updated.disconnect(self.on_audio_levels); self.audio_monitor.stop(); self.audio_monitor = None; self._eq_vals = []

    def paint_neon_border(self, painter, rect, radius):
        conical = QConicalGradient(QPointF(rect.center()), self.gradient_phase * 360)
        cols = list(self.theme['animation']['neon_colors']); cols = cols + [cols[0]] if cols else ["#FFFFFF", "#FFFFFF"]
        for i, c in enumerate(cols): conical.setColorAt(i/(len(cols)-1), qcolor(c))
        painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QBrush(conical), float(self.theme['animation']['neon_width'])))
        if self.island_style == "Notch Nook":
            border = QPainterPath()
            r = radius; sc = min(r * 1.4, float(self.theme['island']['notch_scoop'])); pr = rect.adjusted(1,1,-1,-1)
            border.moveTo(pr.left() - sc, pr.top())
            border.cubicTo(pr.left() - sc * 0.05, pr.top(), pr.left(), pr.top() + sc * 0.05, pr.left(), pr.top() + sc)
            border.lineTo(pr.left(), pr.bottom() - r)
            border.quadTo(pr.left(), pr.bottom(), pr.left() + r, pr.bottom())
            border.lineTo(pr.right() - r, pr.bottom())
            border.quadTo(pr.right(), pr.bottom(), pr.right(), pr.bottom() - r)
            border.lineTo(pr.right(), pr.top() + sc)
            border.cubicTo(pr.right(), pr.top() + sc * 0.05, pr.right() + sc * 0.05, pr.top(), pr.right() + sc, pr.top())
            painter.drawPath(border)
        else:
            painter.drawRoundedRect(rect.adjusted(1,1,-1,-1), radius, radius)

    def update_animation(self):
        self.gradient_phase = (self.gradient_phase + float(self.theme['animation']['phase_speed'])) % 1.0
        self.weather_bg_phase = (self.weather_bg_phase + 0.003) % 1.0
        if self.current_state in ("Hover", "Notify") or self.media_state in ("Playing", "Paused") or\
           self._weather_bg_opacity > 0.0 or self._perf_bg_opacity > 0.0 or\
           self._calendar_bg_opacity > 0.0 or self._month_bg_opacity > 0.0: 
            self.update()

    def anim_color(self, key):
        v = self.theme['animation'][key]
        return QColor(self.album_accent_color) if str(v).lower() == 'album' else qcolor(v)

    def beam_colors(self, alpha):
        cs = [qcolor(c) for c in (self.theme['charging']['beam_colors'] + ["#FFFFFF"] * 3)[:3]]
        cs[0].setAlpha(alpha); cs[1].setAlpha(alpha); cs[2].setAlpha(alpha // 2)
        return cs

    def check_theme_reload(self):
        try:
            m = os.path.getmtime(theme_path())
        except OSError:
            return
        if m != self._theme_mtime:
            self.apply_theme()

    def apply_theme(self):
        self.theme, self._theme_mtime = load_theme()
        self.accent_color = self.get_windows_accent_color() if str(self.theme['accent']).lower() == 'auto' else css_hex(self.theme['accent'])
        self.setStyleSheet(get_stylesheet(self.accent_color, self.theme))
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())
        self.update()

    def open_theme_file(self):
        os.startfile(write_default_theme())

    def get_windows_accent_color(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM")
            v, _ = winreg.QueryValueEx(key, "ColorizationColor"); winreg.CloseKey(key); return f"#{(v & 0xFFFFFF):06x}"
        except: return "#0078D7"

    def get_shine_phase(self): return self._shine_phase
    def set_shine_phase(self, value): self._shine_phase = value; self.update()
    shine_phase = pyqtProperty(float, get_shine_phase, set_shine_phase)

    def get_charging_phase(self): return self._charging_phase
    def set_charging_phase(self, value): self._charging_phase = value; self.update()
    charging_phase = pyqtProperty(float, get_charging_phase, set_charging_phase)

    def setup_autostart(self):
        try:
            app_path = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{sys.argv[0]}"'
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "DynamicIsland", 0, winreg.REG_SZ, app_path)
            winreg.CloseKey(key)
        except Exception as e: print("Autostart error:", e)

    def init_ui(self):
        self.main_layout = QVBoxLayout(self); self.main_layout.setContentsMargins(0, 0, 0, 0); self.main_layout.setSpacing(0)
        self.island_root = QWidget(self)
        self.island_root.setObjectName("IslandRoot")
        # Reduced horizontal margins from 15 to 5 to prevent clipping of wide content
        self.island_root_layout = QVBoxLayout(self.island_root); self.island_root_layout.setContentsMargins(5, 0, 5, 0); self.island_root_layout.setSpacing(0)
        self.content_container = QWidget(); self.content_layout = QVBoxLayout(self.content_container); self.content_layout.setContentsMargins(0, 0, 0, 0); self.content_layout.setSpacing(0)
        self.content_opacity = QGraphicsOpacityEffect(self.content_container); self.content_container.setGraphicsEffect(self.content_opacity)
        self.header_widget = QWidget(); self.header_layout = QHBoxLayout(self.header_widget); self.header_layout.setContentsMargins(25, 0, 25, 0); self.header_layout.setSpacing(10)
        self.status_icon = QLabel(); self.status_icon.setObjectName("IconLabel"); self.status_icon.setFixedSize(22, 22)
        self.status_icon.setPixmap(qta.icon('mdi.circle', color=self.accent_color).pixmap(20, 20))
        self.status_text = QLabel(""); self.status_text.setObjectName("TitleLabel")
        self.header_layout.addWidget(self.status_icon); self.header_layout.addWidget(self.status_text)
        self.cd_name = MarqueeLabel(); self.cd_name.setObjectName("TitleLabel"); self.cd_name.setFixedHeight(28); self.cd_name.hide()
        self.cd_time = QLabel(""); self.cd_time.setObjectName("TitleLabel"); self.cd_time.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); self.cd_time.hide()
        self.header_layout.addWidget(self.cd_name, 1); self.header_layout.addWidget(self.cd_time)
        self.alert_text =MarqueeLabel(); self.alert_text.setObjectName("TitleLabel"); self.alert_text.setFixedHeight(28); self.alert_text.hide()
        self.header_layout.addWidget(self.alert_text)
        self.alert_body = QLabel(); self.alert_body.setWordWrap(True); self.alert_body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.alert_body.setContentsMargins(30, 0, 30, 12); self.alert_body.hide()
        self.media_controls = QWidget(); self.media_controls_layout = QHBoxLayout(self.media_controls); self.media_controls_layout.setContentsMargins(0, 0, 0, 0); self.media_controls_layout.setSpacing(2)
        self.btn_prev = QPushButton(icon=qta.icon('mdi.skip-previous', color='white')); self.btn_play = QPushButton(icon=qta.icon('mdi.play', color='white')); self.btn_next = QPushButton(icon=qta.icon('mdi.skip-next', color='white'))
        for b in [self.btn_prev, self.btn_play, self.btn_next]: b.setObjectName("MediaButton")
        self.btn_prev.clicked.connect(self.media_monitor.prev_track); self.btn_play.clicked.connect(self.media_monitor.toggle_play_pause); self.btn_next.clicked.connect(self.media_monitor.next_track)
        for b in [self.btn_prev, self.btn_play, self.btn_next]: self.media_controls_layout.addWidget(b)
        self.perf_widget = QWidget(); self.perf_layout = QHBoxLayout(self.perf_widget); self.perf_layout.setContentsMargins(0, 0, 0, 0); self.perf_layout.setSpacing(8)
        self.cpu_label = QLabel("CPU: 0%"); self.cpu_label.setObjectName("PerfLabel")
        self.ram_label = QLabel("RAM: 0%"); self.ram_label.setObjectName("PerfLabel")
        self.perf_layout.addWidget(self.cpu_label); self.perf_layout.addWidget(self.ram_label)
        self.header_layout.addStretch(); self.header_layout.addWidget(self.media_controls); self.header_layout.addWidget(self.perf_widget); self.media_controls.hide(); self.perf_widget.hide()
        self.key_switch = ToggleSwitch(); self.header_layout.addWidget(self.key_switch); self.key_switch.hide()
        self.vol_bar = VolumeBar(); self.vol_pct = QLabel(""); self.vol_pct.setObjectName("TitleLabel"); self.vol_pct.setFixedWidth(52); self.vol_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.header_layout.addWidget(self.vol_bar); self.header_layout.addWidget(self.vol_pct); self.vol_bar.hide(); self.vol_pct.hide()
        
                            
        self.perf_panel = self.create_perf_panel()
        self.weather_panel = self.create_weather_panel()
        self.calendar_panel = self.create_calendar_panel()
        self.month_panel = self.create_month_panel()
        self.basics_panel = self.create_basics_panel()
        
        for p in [self.perf_panel, self.weather_panel, self.calendar_panel, self.month_panel, self.basics_panel]: p.hide()
        
                                                         
        for _ in range(4):
            ball = ControlBall(self)
            ball.hide()
                                                                     
            ball.move(-100, -100)
            self.control_balls.append(ball)
        
        self.content_layout.addWidget(self.header_widget)
        self.content_layout.addWidget(self.perf_panel)
        self.content_layout.addWidget(self.weather_panel)
        self.content_layout.addWidget(self.calendar_panel)
        self.content_layout.addWidget(self.month_panel)
        self.content_layout.addWidget(self.basics_panel)
        self.content_layout.addWidget(self.alert_body, 1)

        self.island_root_layout.addWidget(self.content_container); self.update_content()
        # Removed hardcoded move(15, 0) which was causing right-side clipping
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())

    def setup_monitors(self):
        self.perf_monitor = PerfMonitor(parent=self); self.perf_monitor.metrics_updated.connect(self.update_perf); self.perf_monitor.start()
        self.media_monitor = MediaMonitor(self); self.media_monitor.media_updated.connect(self.update_media); self.media_monitor.start()
        self.media_monitor.lyrics_updated.connect(self.update_lyrics)
        self.key_monitor = KeyLockMonitor(self); self.key_monitor.lock_changed.connect(self.show_key_event); self.key_monitor.start()
        self.notif_monitor = NotificationMonitor(self); self.notif_monitor.notification_received.connect(self.show_notification); self.notif_monitor.start()
        self.api_server = ApiServer(self); self.api_server.alert_received.connect(self.enqueue_alert); self.api_server.dismiss_requested.connect(self.dismiss_alert); self.apply_api()
        self.audio_monitor = None; self._eq_vals = []; self.update_audio_capture()
        self.outlook_monitor = OutlookMonitor(self); self.outlook_monitor.outlook_updated.connect(self.on_outlook)
        self.volume_event = None; self.volume_monitor = VolumeMonitor(self); self.volume_monitor.volume_changed.connect(self.show_volume); self.volume_monitor.start()
        self.net_monitor = NetworkMonitor(self); self.net_monitor.event.connect(self.show_net_event); self.apply_net_settings(); self.net_monitor.start()
        self.brightness_monitor = BrightnessMonitor(self); self.brightness_monitor.ddc_enabled = bool(self.settings.get("brightness_ddc", False)); self.brightness_monitor.brightness_changed.connect(self.show_brightness); self.brightness_monitor.start()

                                              
        loc = self.settings.get("location", "Varanasi, India")
        lat = self.settings.get("lat", 25.3333)
        lon = self.settings.get("lon", 83.0)
        self.weather_monitor = WeatherMonitor(city=loc, lat=lat, lon=lon)
        self.weather_monitor.weather_updated.connect(self.update_weather)
        self.weather_monitor.start()

    def update_island_geometry(self, rect, radius):
        if not hasattr(self, 'island_root'): return
        self.island_root.setGeometry(int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
        path = QPainterPath()
        if self.island_style == "Notch Nook":
            path.moveTo(0, 0)
            path.lineTo(rect.width(), 0)
            path.lineTo(rect.width(), rect.height() - radius)
            path.quadTo(rect.width(), rect.height(), rect.width() - radius, rect.height())
            path.lineTo(radius, rect.height())
            path.quadTo(0, rect.height(), 0, rect.height() - radius)
            path.closeSubpath()
        else:
            path.addRoundedRect(QRectF(0, 0, rect.width(), rect.height()), radius, radius)
        self.island_root.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def paint_charging_ears(self, painter, rect, radius):
        p = self.charging_phase
        if p <= 0: return
        
        opacity = math.sin(p * math.pi)
        centerX = rect.center().x()
        centerY = rect.top() + rect.height() / 2
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)

                                                    
        glow_path = QPainterPath()
        glow_path.addRoundedRect(rect.adjusted(-20*opacity, -10*opacity, 20*opacity, 10*opacity), radius+10, radius+10)
        
                                 
        for i in range(5):
            alpha = int(70 * opacity / (i + 1))
            glow_grad = QRadialGradient(rect.center(), rect.width() / 1.5)
                                                         
            gc = self.theme['charging']['glow_colors']; color = qcolor(gc[i % 2 if len(gc) > 1 else 0]); color.setAlpha(alpha)
            painter.setPen(QPen(color, 12 + i*8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(glow_path)

                                                        
        beam_len = 500 * opacity
        left_edge = rect.left()
        right_edge = rect.right()
        
                                   
        for i in range(3):
            beam_w = 4 - i
            if beam_w <= 0: continue
            alpha = int(180 * opacity / (i + 1))
            r_beam_grad = QLinearGradient(right_edge, centerY, right_edge + beam_len, centerY)
            bc = self.beam_colors(alpha)
            r_beam_grad.setColorAt(0.0, bc[0]); r_beam_grad.setColorAt(0.1, bc[1])
            r_beam_grad.setColorAt(0.5, bc[2]); r_beam_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            
            painter.setPen(QPen(QBrush(r_beam_grad), beam_w + 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(right_edge, centerY), QPointF(right_edge + beam_len, centerY))

                                  
        for i in range(3):
            beam_w = 4 - i
            if beam_w <= 0: continue
            alpha = int(180 * opacity / (i + 1))
            l_beam_grad = QLinearGradient(left_edge, centerY, left_edge - beam_len, centerY)
            bc = self.beam_colors(alpha)
            l_beam_grad.setColorAt(0.0, bc[0]); l_beam_grad.setColorAt(0.1, bc[1])
            l_beam_grad.setColorAt(0.5, bc[2]); l_beam_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            
            painter.setPen(QPen(QBrush(l_beam_grad), beam_w + 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(left_edge, centerY), QPointF(left_edge - beam_len, centerY))

                                      
        dot = qcolor(self.theme['charging']['dot_color']); dot.setAlpha(int(255 * opacity)); painter.setBrush(dot)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(right_edge, centerY), 4, 3)
        painter.drawEllipse(QPointF(left_edge, centerY), 4, 3)
        
        painter.restore()

    def check_power_status(self):
        try:
            battery = psutil.sensors_battery()
            if battery:
                is_plugged = battery.power_plugged
                if is_plugged and not self.last_power_plugged:
                    self.charge_samples = []
                    self.trigger_charging_anim()
                if is_plugged:
                    now = time.time()
                    if not self.charge_samples or self.charge_samples[-1][1] != battery.percent: self.charge_samples.append((now, battery.percent)); del self.charge_samples[:-20]
                else: self.charge_samples = []
                self.last_power_plugged = is_plugged
        except: pass

    def trigger_charging_anim(self):
        self.is_charging = True
        self.execute_liquid_transition()
        self.charging_anim.stop()
        self.charging_anim.setStartValue(0.0)
        self.charging_anim.setEndValue(1.0)
        self.charging_anim.start()
        QTimer.singleShot(3100, self.cleanup_charging_anim)

    def cleanup_charging_anim(self):
        self.is_charging = False
        self.charging_phase = 0.0
        self.execute_liquid_transition()
        QTimer.singleShot(900, self.show_charge_popup)

    def battery_eta(self, pct):
        class SBS(ctypes.Structure):
            _fields_ = [('AcOnLine', ctypes.c_ubyte), ('BatteryPresent', ctypes.c_ubyte), ('Charging', ctypes.c_ubyte), ('Discharging', ctypes.c_ubyte), ('Spare', ctypes.c_ubyte * 3), ('Tag', ctypes.c_ubyte), ('MaxCapacity', ctypes.c_uint32), ('RemainingCapacity', ctypes.c_uint32), ('Rate', ctypes.c_int32), ('EstimatedTime', ctypes.c_uint32), ('DefaultAlert1', ctypes.c_uint32), ('DefaultAlert2', ctypes.c_uint32)]
        try:
            s = SBS()
            if ctypes.windll.powrprof.CallNtPowerInformation(5, None, 0, ctypes.byref(s), ctypes.sizeof(s)) == 0 and s.Charging and s.Rate > 0 and s.MaxCapacity > s.RemainingCapacity:
                return (s.MaxCapacity - s.RemainingCapacity) / s.Rate * 3600
        except Exception: pass
        pts = self.charge_samples
        if len(pts) >= 2 and pts[-1][1] > pts[0][1] and pts[-1][0] > pts[0][0]:
            return (100 - pct) * (pts[-1][0] - pts[0][0]) / (pts[-1][1] - pts[0][1])
        return None

    def show_charge_popup(self):
        if not self.settings.get("charge_popup", True): return
        try: batt = psutil.sensors_battery()
        except Exception: batt = None
        if not batt or not batt.power_plugged: return
        pct = int(round(batt.percent))
        if pct >= 100: eta = "Full"
        else:
            sec = self.battery_eta(pct)
            if sec is None: eta = "..."
            else:
                m = max(1, int(round(sec / 60))); eta = f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"
        self.show_osd("charging", pct, eta)

    def apply_net_settings(self):
        self.net_monitor.enabled = bool(self.settings.get("network_alerts", True)); self.net_monitor.battery_minutes = int(self.settings.get("bt_battery_min", 15))

    def show_net_event(self, title, text, icon):
        self.enqueue_alert({"title": title, "text": text, "sticky": False, "mode": "marquee", "icon": icon, "duration_ms": 3500})

    def show_volume(self, pct, muted): self.show_osd("volume", pct, muted)

    def show_brightness(self, pct): self.show_osd("brightness", pct, False)

    def show_osd(self, kind, pct, muted):
        if not self.settings.get({"volume": "volume_osd", "brightness": "brightness_osd"}.get(kind, "charge_popup"), True) or self.alert or self.is_dialog_open or self.current_state not in ("Idle", "Notify"): return
        was = self.volume_event is not None and self.current_state == "Notify"
        self.volume_event = (pct, muted, kind); self.key_event_on = None
        if was: self.apply_volume_view()
        elif self.current_state == "Notify": self.update_feature_view(); self.execute_liquid_transition()
        else: self.change_state("Notify")
        self.revert_timer.start(4500 if kind == "charging" else int(self.settings.get("volume_ms", 1500)))

    def apply_volume_view(self):
        pct, muted, kind = self.volume_event
        self.vol_pct.setFixedWidth(84 if kind == "charging" else 52)
        if kind == "charging":
            self.status_icon.setPixmap(qta.icon('mdi.battery-charging', color='white').pixmap(18, 18)); self.status_text.setText(f"Charging {pct}%")
            self.vol_pct.setText(f"{muted}" if muted in ("Full", "...") else f"{muted} left"); self.vol_bar.show(); self.vol_pct.show()
            if self.vol_bar.fill_anim.state() != QAbstractAnimation.State.Running: self.vol_bar.fill_to(pct, self.theme['status_indicator']['charging_color'])
            return
        if kind == "brightness":
            self.status_icon.setPixmap(qta.icon('mdi.brightness-5' if pct < 50 else 'mdi.brightness-7', color='white').pixmap(18, 18)); self.status_text.setText("Brightness")
            self.vol_pct.setText(f"{pct}%"); self.vol_bar.set_value(pct, False, self.accent_color); self.vol_bar.show(); self.vol_pct.show(); return
        icon = 'mdi.volume-off' if muted or pct == 0 else 'mdi.volume-low' if pct < 34 else 'mdi.volume-medium' if pct < 67 else 'mdi.volume-high'
        self.status_icon.setPixmap(qta.icon(icon, color='white').pixmap(18, 18)); self.status_text.setText("Volume")
        self.vol_pct.setText("Muted" if muted else f"{pct}%"); self.vol_bar.set_value(pct, muted, self.accent_color)
        self.vol_bar.show(); self.vol_pct.show()

    def on_revert(self):
        self.volume_event = None
        if self.alert: self.finish_alert()
        else: self.change_state("Idle")

    def apply_api(self):
        if self.settings.get("api_enabled", False): self.api_server.start(int(self.settings.get("api_port", 8765)), self.settings.get("api_token", ""))
        else: self.api_server.stop()
        return self.api_server.running

    def set_tint(self, target):
        self.tint_anim.stop(); self.tint_anim.setStartValue(self._alert_tint); self.tint_anim.setEndValue(target); self.tint_anim.start()

    def enqueue_alert(self, alert):
        if self.alert is None: self.start_alert(alert)
        elif len(self.alert_queue) < 50: self.alert_queue.append(alert)

    def start_alert(self, a):
        self.alert = a; self.volume_event = None
        if a.get("color"): self.alert_tint_color = qcolor(a["color"])
        self.set_tint(1.0 if a.get("color") else 0.0)
        w = int(self.settings.get("alert_width", 520)); h = int(self.settings.get("alert_height", 40))
        if a["mode"] == "expand":
            self.alert_body.setText(a["text"]); self.alert_body.ensurePolished()
            h = min(300, 44 + self.alert_body.heightForWidth(w - 10) + 6) if a["text"].strip() else self.NOTIFY_H
        self.alert_size = (w, h)
        if a.get("sticky"): self.revert_timer.stop()
        else: self.revert_timer.start(int(a.get("duration_ms", self.settings.get("notification_ms", 3500))))
        if self.current_state == "Notify": self.update_feature_view(); self.execute_liquid_transition()
        else: self.change_state("Notify")

    def finish_alert(self):
        self.revert_timer.stop()
        if self.alert_queue: self.start_alert(self.alert_queue.pop(0)); return
        self.alert = None; self.set_tint(0.0); self.change_state("Idle")

    def dismiss_alert(self):
        if self.alert: self.finish_alert()

    def alert_fg(self):
        c = self.alert_tint_color if self.alert and self.alert.get("color") else None
        return "#000000" if c is not None and c.lightness() > 150 else "#FFFFFF"

    def reset_alert_widgets(self):
        self.status_icon.show(); self.key_switch.hide(); self.vol_bar.hide(); self.vol_pct.hide(); self.alert_text.hide(); self.alert_body.hide(); self.cd_name.hide(); self.cd_time.hide(); self.status_text.show(); self.status_text.setStyleSheet(""); self.status_icon.setStyleSheet(""); self.header_widget.setMinimumHeight(0)

    def show_alert_content(self):
        a = self.alert; fg = self.alert_fg(); spec = a.get("icon", ""); self.status_icon.show(); self.cd_name.hide(); self.cd_time.hide()
        is_url = spec.lower().startswith(("http://", "https://")); is_qta = bool(re.fullmatch(r"[a-z0-9]+\.[\w-]+", spec, re.I))
        pm = None
        if is_url and a.get("icon_bytes"): pm = QPixmap(); pm.loadFromData(a["icon_bytes"])
        elif not is_url and os.path.isfile(spec): pm = QPixmap(spec)
        elif is_qta:
            try: pm = qta.icon(spec, color=fg).pixmap(18, 18)
            except Exception: pm = None
        if pm is not None and not pm.isNull():
            self.status_icon.setStyleSheet(""); self.status_icon.setPixmap(pm.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        elif spec and not is_url and not is_qta and not os.path.isfile(spec):
            self.status_icon.setPixmap(QPixmap()); self.status_icon.setText(spec[:2]); self.status_icon.setStyleSheet(f"color: {fg};")
        else:
            self.status_icon.setStyleSheet(""); self.status_icon.setPixmap(qta.icon('mdi.bell', color=fg).pixmap(18, 18))
        title, text = a["title"].strip(), a["text"].strip()
        if a["mode"] == "expand":
            self.alert_text.hide(); self.status_text.show(); self.header_widget.setMinimumHeight(self.NOTIFY_H)
            self.status_text.setStyleSheet(f"color: {fg};")
            self.status_text.setText(self.status_text.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, self.alert_size[0] - 100))
            self.alert_body.setStyleSheet(f"color: {fg};"); self.alert_body.setText(text); self.alert_body.setVisible(bool(text))
        else:
            self.status_text.hide(); self.alert_body.hide(); self.header_widget.setMinimumHeight(0)
            self.alert_text.setFixedWidth(self.alert_size[0] - 92); self.alert_text.show()
            self.alert_text.set_marquee(f"{title}: {text}" if title and text else (title or text), fg)

    def show_key_event(self, name, is_on):
        if self.alert:
            if not self.alert.get("transient"): self.alert_queue.insert(0, self.alert)
            self.start_alert({"title": name, "text": "ENABLED" if is_on else "DISABLED", "sticky": False, "mode": "marquee", "icon": "mdi.lightning-bolt", "duration_ms": 2500, "transient": True}); return
        self.event_title = name; self.event_text = ("ENABLED" if is_on else "DISABLED"); self.key_event_on = is_on; self.volume_event = None
        if self.current_state == "Notify": self.update_feature_view(); self.execute_liquid_transition()
        else: self.change_state("Notify")
        self.key_switch.set_checked(not is_on, animate=False); QTimer.singleShot(280, lambda: self.key_switch.set_checked(is_on))
        self.revert_timer.start(2500)

    def show_notification(self, app, title, text):
        seen = self.settings.setdefault("seen_notif_apps", [])
        if app and app not in seen: seen.append(app); del seen[:-30]; self.save_settings()
        if app.lower() in [a.lower() for a in self.settings.get("ignored_apps", [])]: return
        if self.alert:
            self.enqueue_alert({"title": app, "text": f"{title}: {text}" if title else text, "sticky": False, "mode": "marquee", "icon": "mdi.email"}); return
        self.event_title = app; self.event_text = (f"{title}: {text}" if title else text); self.key_event_on = None; self.volume_event = None
        if self.current_state == "Notify": self.update_feature_view(); self.execute_liquid_transition()
        else: self.change_state("Notify")
        self.revert_timer.start(int(self.settings.get("notification_ms", 3500)))

    def paint_weather_bg(self, painter, rect, radius):
        if self.weather_has_data:
            clip = self.build_notch_path(rect) if self.island_style == "Notch Nook" else QPainterPath()
            if self.island_style != "Notch Nook": clip.addRoundedRect(QRectF(rect), radius, radius)
            self.weather_scene.paint(painter, rect, clip, self._weather_bg_opacity); return
        painter.save(); pt = self.theme['panels']['weather']
        painter.setOpacity(self._weather_bg_opacity)
        p = self.weather_bg_phase * 2 * math.pi
        
                        
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, qcolor(pt['top']))
        grad.setColorAt(1, qcolor(pt['bottom']))
        painter.setBrush(grad); self._draw_shape(painter, rect, radius)
        
                       
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        for i, color in enumerate([qcolor(c) for c in pt['blooms']]):
            x = rect.center().x() + math.sin(p + i) * (rect.width() * 0.3)
            y = rect.center().y() + math.cos(p * 0.7 + i*2) * (rect.height() * 0.2)
            bloom = QRadialGradient(QPointF(x, y), rect.width() * float(pt['bloom_size']))
            bloom.setColorAt(0, color); bloom.setColorAt(1, Qt.GlobalColor.transparent)
            painter.setBrush(bloom); self._draw_shape(painter, rect, radius)
        painter.restore()

    def paint_perf_bg(self, painter, rect, radius):
        painter.save(); pt = self.theme['panels']['perf']
        painter.setOpacity(self._perf_bg_opacity)
        p = self.weather_bg_phase * 2 * math.pi                          
        
                                
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, qcolor(pt['top']))
        grad.setColorAt(1, qcolor(pt['bottom']))
        painter.setBrush(grad); self._draw_shape(painter, rect, radius)
        
                            
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        for i, color in enumerate([qcolor(c) for c in pt['blooms']]):
            x = rect.center().x() + math.sin(p * 0.8 + i*1.5) * (rect.width() * 0.35)
            y = rect.center().y() + math.cos(p * 0.5 + i) * (rect.height() * 0.25)
            bloom = QRadialGradient(QPointF(x, y), rect.width() * float(pt['bloom_size']))
            bloom.setColorAt(0, color); bloom.setColorAt(1, Qt.GlobalColor.transparent)
            painter.setBrush(bloom); self._draw_shape(painter, rect, radius)
        painter.restore()

    def paint_calendar_bg(self, painter, rect, radius):
        painter.save(); pt = self.theme['panels']['calendar']
        painter.setOpacity(self._calendar_bg_opacity)
        p = self.weather_bg_phase * 2 * math.pi
        
                               
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, qcolor(pt['top']))
        grad.setColorAt(1, qcolor(pt['bottom']))
        painter.setBrush(grad); self._draw_shape(painter, rect, radius)
        
                                    
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        for i, color in enumerate([qcolor(c) for c in pt['blooms']]):
            x = rect.center().x() + math.sin(p * 0.9 + i*2) * (rect.width() * 0.3)
            y = rect.center().y() + math.cos(p * 0.6 + i) * (rect.height() * 0.2)
            bloom = QRadialGradient(QPointF(x, y), rect.width() * float(pt['bloom_size']))
            bloom.setColorAt(0, color); bloom.setColorAt(1, Qt.GlobalColor.transparent)
            painter.setBrush(bloom); self._draw_shape(painter, rect, radius)
        painter.restore()

    def paint_month_bg(self, painter, rect, radius):
        painter.save(); pt = self.theme['panels']['month']
        painter.setOpacity(self._month_bg_opacity)
        p = self.weather_bg_phase * 2 * math.pi
        
                                   
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, qcolor(pt['top']))
        grad.setColorAt(1, qcolor(pt['bottom']))
        painter.setBrush(grad); self._draw_shape(painter, rect, radius)
        
                                      
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        for i, color in enumerate([qcolor(c) for c in pt['blooms']]):
            x = rect.center().x() + math.sin(p * 1.1 + i) * (rect.width() * 0.3)
            y = rect.center().y() + math.cos(p * 0.8 + i*1.2) * (rect.height() * 0.2)
            bloom = QRadialGradient(QPointF(x, y), rect.width() * float(pt['bloom_size']))
            bloom.setColorAt(0, color); bloom.setColorAt(1, Qt.GlobalColor.transparent)
            painter.setBrush(bloom); self._draw_shape(painter, rect, radius)
        painter.restore()

    def create_action_button(self, app_type):
        btn = QPushButton(icon=qta.icon('mdi.open-in-new', color='white'))
        btn.setObjectName("ActionButton")
        btn.setFixedSize(32, 32)
        btn.clicked.connect(lambda: self.open_app(app_type))
        return btn

    def open_app(self, app_type):
        schemes = {"weather": "bingweather:", "month": "ms-settings:dateandtime"}
        if app_type in schemes: webbrowser.open(schemes[app_type])

    def create_weather_panel(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(25, 10, 25, 15); l.setSpacing(12)
        h1 = QHBoxLayout(); self.weather_temp_label = QLabel("--°"); self.weather_temp_label.setStyleSheet("font-size: 38px; font-weight: bold;")
        info = QVBoxLayout(); 
        loc_name = self.settings.get("location", "Varanasi, India")
        self.weather_city_label = QLabel(loc_name); self.weather_city_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.weather_cond_label = QLabel("Loading..."); self.weather_cond_label.setStyleSheet(f"font-size: 11px; color: {css(self.theme['text']['dim'])};")
        info.addWidget(self.weather_city_label); info.addWidget(self.weather_cond_label); h1.addLayout(info); h1.addStretch(); h1.addWidget(self.weather_temp_label)
        l.addLayout(h1)
        self.hourly_layout = QHBoxLayout(); self.hourly_layout.setSpacing(5)
                           
        self.hourly_slots = []
        for _ in range(5):
            slot = QVBoxLayout(); slot.setSpacing(2); st = QLabel("--"); st.setStyleSheet(f"font-size: 9px; color: {css(self.theme['text']['muted'])};"); st.setAlignment(Qt.AlignmentFlag.AlignCenter)
            si = QLabel(); si.setPixmap(qta.icon("mdi.weather-cloudy", color='white').pixmap(18, 18)); si.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stp = QLabel("--°"); stp.setStyleSheet("font-size: 10px; font-weight: 600;"); stp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slot.addWidget(st); slot.addWidget(si); slot.addWidget(stp); self.hourly_layout.addLayout(slot)
            self.hourly_slots.append((st, si, stp))
        l.addLayout(self.hourly_layout); return w

    def update_weather(self, data):
        self.weather_icon = data.get("icon")
        if data.get("code") is not None: self.weather_scene.set_condition(data["code"], data.get("is_day", True)); self.weather_has_data = True
        self.weather_temp_label.setText(data["temp"])
        self.weather_city_label.setText(data["city"])
        self.weather_cond_label.setText(data["desc"])
        for i, slot in enumerate(data["hourly"]):
            if i < len(self.hourly_slots):
                st, si, stp = self.hourly_slots[i]
                st.setText(slot["time"])
                si.setPixmap(qta.icon(slot["icon"], color='white').pixmap(18, 18))
                stp.setText(slot["temp"])

        
    def create_calendar_panel(self):
        self.calendar_panel_widget = QWidget()
        # Initial size for View Mode
        self.calendar_panel_widget.setFixedSize(self.CALENDAR_W, self.CALENDAR_H)
        cal_layout = QVBoxLayout(self.calendar_panel_widget)
        cal_layout.setContentsMargins(0, 0, 0, 0); cal_layout.setSpacing(0)
        
        # View Mode Container
        self.task_view_widget = QWidget()
        view_layout = QVBoxLayout(self.task_view_widget)
        # Increased horizontal padding for a centered, narrower content look
        view_layout.setContentsMargins(25, 12, 25, 18); view_layout.setSpacing(12)
        
        h = QHBoxLayout(); t = QLabel("Next Up"); t.setStyleSheet("font-weight: bold; font-size: 15px;"); self.cal_title_label = t
        self.ev_count_label = QLabel("0 tasks"); self.ev_count_label.setStyleSheet(f"color: {css(self.theme['text']['muted'])}; font-size: 11px;")
        eb = self.create_action_button("calendar"); eb.setIcon(qta.icon("mdi.pencil", color="white")); eb.clicked.connect(self.open_task_editor)
        # Move pencil to the left to avoid overflow
        h.addWidget(eb); h.addSpacing(5); h.addWidget(t); h.addWidget(self.ev_count_label); h.addStretch()
        view_layout.addLayout(h)
        
        self.tasks_container_widget = QWidget()
        self.tasks_container_layout = QVBoxLayout(self.tasks_container_widget)
        self.tasks_container_layout.setContentsMargins(0, 0, 0, 0); self.tasks_container_layout.setSpacing(10)
        view_layout.addWidget(self.tasks_container_widget); view_layout.addStretch()
        
        # Edit Mode Container
        self.task_edit_widget = QWidget(); self.task_edit_widget.hide()
        edit_layout = QVBoxLayout(self.task_edit_widget)
        # Increased horizontal padding to 25px to make content narrower and centered
        edit_layout.setContentsMargins(25, 20, 25, 20); edit_layout.setSpacing(15)
        
        # Syncing with TaskEditorDialog's premium style but within panel
        self.edit_list = QListWidget()
        self.edit_list.setStyleSheet(f"QListWidget {{ background: transparent; border: none; }} QListWidget::item {{ background: {css(self.theme['inputs']['list_item_bg'])}; border-radius: 10px; padding: 10px; margin-bottom: 5px; }} QListWidget::item:selected {{ border: 1px solid {self.accent_color}; }}")
        
        # Inputs with glassmorphism styling
        input_grid = QGridLayout(); input_grid.setSpacing(10)
        input_style = f"QLineEdit, QComboBox {{ background-color: {css(self.theme['inputs']['background'])}; border: 1px solid {css(self.theme['inputs']['border'])}; border-radius: {self.theme['inputs']['radius']}px; color: white; padding: 10px; font-size: 13px; }} QLineEdit:focus {{ border: 1px solid {self.accent_color}; }}"
        self.edit_name = QLineEdit(); self.edit_name.setPlaceholderText("Task Name"); self.edit_name.setStyleSheet(input_style)
        self.edit_time = QLineEdit(); self.edit_time.setPlaceholderText("Time (e.g. 3:00 PM)"); self.edit_time.setStyleSheet(input_style)
        self.edit_cat = QComboBox(); self.edit_cat.addItems(["Work", "Health", "Personal", "Study", "Other"]); self.edit_cat.setStyleSheet(input_style)
        
        input_grid.addWidget(self.edit_name, 0, 0, 1, 2)
        input_grid.addWidget(self.edit_time, 1, 0)
        input_grid.addWidget(self.edit_cat, 1, 1)
        
        # Buttons with premium feel
        btn_style = "QPushButton { background-color: rgba(255, 255, 255, 10); color: white; border: 1px solid rgba(255, 255, 255, 15); border-radius: 10px; padding: 10px; font-weight: 600; } QPushButton:hover { background-color: rgba(255, 255, 255, 20); }"
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add"); add_btn.clicked.connect(self.add_task_integrated); add_btn.setStyleSheet(btn_style)
        del_btn = QPushButton("Delete Selected"); del_btn.clicked.connect(self.delete_task_integrated); del_btn.setStyleSheet(btn_style)
        # Using "and" instead of "&" to avoid mnemonic behavior in Qt
        save_btn = QPushButton("Save and Close"); save_btn.setStyleSheet(f"background-color: {self.accent_color}; color: white; border-radius: 10px; padding: 12px; font-weight: bold;")
        save_btn.clicked.connect(self.save_and_close_editor)
        
        btn_layout.addWidget(add_btn); btn_layout.addWidget(del_btn)
        
        edit_layout.addWidget(QLabel("Manage Tasks", styleSheet="font-weight: bold; font-size: 16px;"))
        edit_layout.addWidget(self.edit_list)
        edit_layout.addLayout(input_grid)
        edit_layout.addLayout(btn_layout)
        edit_layout.addWidget(save_btn)
        
        cal_layout.addWidget(self.task_view_widget)
        cal_layout.addWidget(self.task_edit_widget)
        
        self.refresh_calendar_panel()
        return self.calendar_panel_widget

    def add_task_integrated(self):
        name = self.edit_name.text()
        if name:
            tasks = self.settings.get("tasks", [])
            tasks.append({"name": name, "category": self.edit_cat.currentText(), "time": self.edit_time.text() or "N/A", "color": "#00A0FF"})
            self.settings["tasks"] = tasks
            self.refresh_calendar_panel(); self.edit_name.clear(); self.edit_time.clear()

    def delete_task_integrated(self):
        idx = self.edit_list.currentRow()
        if idx >= 0:
            tasks = self.settings.get("tasks", [])
            tasks.pop(idx); self.settings["tasks"] = tasks
            self.refresh_calendar_panel()

    def save_and_close_editor(self):
        self.save_settings()
        self.open_task_editor() # Toggle back

    def open_task_editor(self):
        self.is_editing_tasks = not self.is_editing_tasks
        self.task_view_widget.setVisible(not self.is_editing_tasks)
        self.task_edit_widget.setVisible(self.is_editing_tasks)
        
        # Adjust internal widget size based on mode
        if self.is_editing_tasks:
            self.calendar_panel_widget.setFixedSize(self.EDIT_W, self.EDIT_H)
        else:
            self.calendar_panel_widget.setFixedSize(self.CALENDAR_W, self.CALENDAR_H)
            
        # Toggle compatibility mode for stability
        if self.is_editing_tasks:
            self._prev_comp = self.compatibility_mode
            self.compatibility_mode = True
        else:
            self.compatibility_mode = getattr(self, "_prev_comp", self.compatibility_mode)
            
        self.recenter_window()
        self.execute_liquid_transition()

    def refresh_calendar_panel(self):
        # Deep clean existing tasks to prevent overlapping ghost widgets
        for child in self.tasks_container_widget.findChildren(QWidget):
            child.hide()
            child.setParent(None)
            child.deleteLater()
            
        while self.tasks_container_layout.count():
            item = self.tasks_container_layout.takeAt(0)
            if item.layout():
                # Manually clear sub-layouts if any remain
                while item.layout().count():
                    si = item.layout().takeAt(0)
                    if si.widget(): si.widget().deleteLater()
            
        tasks = self.settings.get("tasks", DEFAULT_TASKS)

        # Update integrated edit list
        self.edit_list.clear()
        for t in tasks:
            item = QListWidgetItem(f"{t['name']} • {t['time']}\n{t.get('category', 'Task').upper()}")
            self.edit_list.addItem(item)

        use_outlook = self.settings.get("outlook_enabled", True) and self.outlook["status"] == "ok"
        rows = []
        if use_outlook:
            now = datetime.datetime.now(); evs = self.outlook_events(now); due = self.outlook_due_tasks(now)
            for e in evs:
                live = e["start"] <= now; tm = "now" if live else e["start"].strftime("%I:%M %p").lstrip("0")
                sub = e["location"] or f"{e['start'].strftime('%I:%M').lstrip('0')} - {e['end'].strftime('%I:%M %p').lstrip('0')}"
                rows.append({"name": e["subject"], "sub": sub, "time": tm, "color": "#FF9F0A" if live else self.accent_color})
            for t in due:
                late = t["due"].date() < now.date()
                rows.append({"name": t["subject"], "sub": t["list"], "time": "overdue" if late else "due today" if t["due"].date() == now.date() else t["due"].strftime("%a %d"), "color": "#FF5050" if late else "#00FF80", "task_id": t["id"]})
            if not rows: rows.append({"name": "Nothing left today", "sub": "", "time": "", "color": self.accent_color})
            bits = [f"{len(evs)} events", f"{len(due)} tasks", f"{self.outlook['unread']} unread"]
            self.ev_count_label.setText(" · ".join(bits)); self.cal_title_label.setText("Today")
        else:
            rows = [{"name": t["name"], "sub": t.get("category", "Task"), "time": t.get("time", ""), "color": t.get("color", "#00A0FF")} for t in tasks]
            self.ev_count_label.setText(f"{len(tasks)} tasks" if not self.settings.get("outlook_enabled", True) else (self.outlook["status"] or "Outlook: connecting") + f" · {len(tasks)} local tasks"); self.cal_title_label.setText("Next Up")

        # Rebuild view list
        shown_count = 0
        for r in rows[:4]: # Show only first 4 in view mode
            shown_count += 1
            row = QHBoxLayout()
            if r.get("task_id"):
                chk = QPushButton(); chk.setIcon(qta.icon("mdi.checkbox-blank-circle-outline", color=r["color"])); chk.setFixedSize(18, 18); chk.setFlat(True); chk.setCursor(Qt.CursorShape.PointingHandCursor)
                chk.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0px; }"); chk.setToolTip("Mark complete in Outlook")
                chk.clicked.connect(lambda _, i=r["task_id"]: self.complete_outlook_task(i)); row.addWidget(chk)
            bar = QFrame(); bar.setFixedWidth(3); bar.setStyleSheet(f"background-color: {r['color']}; border-radius: 1px;")
            det = QVBoxLayout(); det.setContentsMargins(0, 0, 0, 0); det.setSpacing(1)
            n = QLabel(r['name']); n.setStyleSheet("font-size: 13px; font-weight: 600; padding: 0px;")
            n.setText(n.fontMetrics().elidedText(r['name'], Qt.TextElideMode.ElideRight, 250))
            c = QLabel(r['sub']); c.setStyleSheet(f"font-size: 10px; color: {css(self.theme['text']['muted'])}; padding: 0px;")
            c.setText(c.fontMetrics().elidedText(r['sub'], Qt.TextElideMode.ElideRight, 250))
            det.addWidget(n); det.addWidget(c)
            tm = QLabel(r['time']); tm.setStyleSheet("font-size: 11px; font-weight: 500;")
            row.addWidget(bar); row.addLayout(det); row.addStretch(); row.addWidget(tm)
            self.tasks_container_layout.addLayout(row)

        # Calculate dynamic height for View Mode
        # Base height (Header + Margins) approx 80px, each task approx 35px for better breathing room
        old_h = self.CALENDAR_H
        self.CALENDAR_H = 80 + (shown_count * 35)
        if shown_count == 0: self.CALENDAR_H = 105

        if not self.is_editing_tasks:
            self.calendar_panel_widget.setFixedSize(self.CALENDAR_W, self.CALENDAR_H)
            # If we are in Hover state and looking at calendar, trigger a smooth transition to new size
            if self.current_state == "Hover" and self.features[self.current_feature_index] == "calendar" and old_h != self.CALENDAR_H:
                self.execute_liquid_transition()

    def create_perf_panel(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(25, 12, 25, 18); l.setSpacing(12)
        header = QHBoxLayout(); title = QLabel("System Status"); title.setStyleSheet("font-weight: bold; font-size: 15px;")
        header.addWidget(title); header.addStretch(); header.addWidget(self.create_action_button("month"))           
        l.addLayout(header)

                         
        def add_item(layout, icon, label):
            v = QVBoxLayout(); v.setSpacing(4)
            h = QHBoxLayout(); ico = QLabel(); ico.setPixmap(qta.icon(icon, color="white").pixmap(14, 14))
            txt = QLabel(label); txt.setStyleSheet(f"font-size: 11px; color: {css(self.theme['text']['muted'])}; font-weight: 600;")
            h.addWidget(ico); h.addWidget(txt); h.addStretch()
            val = QLabel("0%"); val.setStyleSheet("font-size: 13px; font-weight: 600;")
            bar = QProgressBar(); bar.setFixedHeight(4); bar.setTextVisible(False); bar.setMaximum(100)
            pg = self.theme['progress']; bar.setStyleSheet(f"QProgressBar {{ background-color: {css(pg['track'])}; border-radius: 2px; border: none; }} QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {css(pg['from'])}, stop:1 {css(pg['to'])}); border-radius: 2px; }}")
            v.addLayout(h); v.addWidget(val); v.addWidget(bar)
            layout.addLayout(v); return bar, val

        r1 = QHBoxLayout(); r1.setSpacing(30)
        self.cpu_bar_L = add_item(r1, "mdi.cpu-64-bit", "CPU")
        self.ram_bar_L = add_item(r1, "mdi.memory", "RAM")
        l.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(30)
        self.disk_bar_L = add_item(r2, "mdi.harddisk", "STORAGE")
        
        nv = QVBoxLayout(); nv.setSpacing(4)
        nh = QHBoxLayout(); nico = QLabel(); nico.setPixmap(qta.icon("mdi.web", color="white").pixmap(14, 14))
        ntxt = QLabel("NETWORK"); ntxt.setStyleSheet(f"font-size: 11px; color: {css(self.theme['text']['muted'])}; font-weight: 600;")
        nh.addWidget(nico); nh.addWidget(ntxt); nh.addStretch(); nv.addLayout(nh)
        self.net_title_L = ntxt
        self.net_down_L = QLabel("↓ 0 KB/s"); self.net_up_L = QLabel("↑ 0 KB/s"); self.net_vpn_L = QLabel(""); self.net_vpn_L.hide()
        for lb in [self.net_down_L, self.net_up_L]: lb.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.net_vpn_L.setStyleSheet(f"font-size: 10px; color: {css(self.theme['text']['muted'])}; font-weight: 600;")
        nv.addWidget(self.net_down_L); nv.addWidget(self.net_up_L); nv.addWidget(self.net_vpn_L); r2.addLayout(nv)
        l.addLayout(r2); return w
        return w

    def create_month_panel(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(25, 8, 25, 18); l.setSpacing(8)
        now = datetime.datetime.now(); days = (datetime.date(now.year, now.month + 1, 1) - datetime.date(now.year, now.month, 1)).days if now.month < 12 else 31
        header = QHBoxLayout(); title = QLabel(now.strftime("%B Progress")); title.setStyleSheet("font-weight: bold; font-size: 14px;")
        perc = QLabel(f"{int(now.day/days*100)}%"); perc.setStyleSheet(f"color: {css(self.theme['month_progress']['percent'])}; font-weight: bold; font-size: 14px;")
        header.addWidget(title); header.addStretch(); header.addWidget(perc); header.addWidget(self.create_action_button("month"))
        l.addLayout(header); grid = QGridLayout(); grid.setSpacing(8); grid.setContentsMargins(0, 5, 0, 0)
        for i in range(days):
            dot = QFrame(); dot.setFixedSize(12, 12); color = "#00A0FF" if (i+1) <= now.day else "#333"
            dot.setStyleSheet(f"background-color: {color}; border-radius: 6px;"); grid.addWidget(dot, i//10, i%10)
        l.addLayout(grid); return w

    def create_basics_panel(self):
        w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(25, 0, 25, 0); l.setSpacing(10); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_l = QPushButton("<", objectName="NavButton"); btn_r = QPushButton(">", objectName="NavButton")
        btn_l.clicked.connect(lambda: self.scroll_controls(-1)); btn_r.clicked.connect(lambda: self.scroll_controls(1))
        lbl = QLabel("Basics"); lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {css(self.theme['text']['heading_muted'])}; letter-spacing: 1.2px;")
        l.addWidget(btn_l); l.addWidget(lbl); l.addWidget(btn_r); return w



    def update_content(self):
        if self.current_state == "Idle":
            feature = self.features[self.current_feature_index]; self.status_icon.show()
            media_on = feature == "media" and self.media_state in ("Playing", "Paused")
            cd = None if media_on else self.outlook_countdown(datetime.datetime.now())
            self.cd_name.setVisible(bool(cd)); self.cd_time.setVisible(bool(cd)); self.status_text.setVisible(not cd)
            if bool(cd) != self.cd_active:
                self.cd_active = bool(cd)
                if not self.is_charging: self.execute_liquid_transition()
            if media_on:
                if self.showing_lyrics and self.media_lyric_text:
                    self.status_text.setText(self.media_lyric_text)
                else:
                    dt = self.media_title; self.status_text.setText(dt[:22] + "..." if len(dt) > 25 else dt)
                self.status_icon.setPixmap(qta.icon('mdi.music', color='white').pixmap(18, 18))
            else:
                now = datetime.datetime.now(); ts = now.strftime("%I:%M %p").lstrip("0")
                unread = self.outlook["unread"] if self.settings.get("outlook_enabled", True) and self.settings.get("outlook_unread_idle", True) else 0
                if cd:
                    if cd[0] != self.cd_name_text: self.cd_name_text = cd[0]; self.cd_name.set_marquee(cd[0], "white")
                    self.cd_time.setText(cd[1]); self.status_icon.setPixmap(qta.icon('mdi.calendar-clock', color=self.accent_color).pixmap(18, 18))
                else:
                    self.status_text.setText(f"{ts} · ✉ {unread}" if unread else f"{now.strftime('%a')}, {ts}")
                    name, color = self.status_indicator(); sz = int(self.theme['status_indicator']['size'])
                    self.status_icon.setPixmap(qta.icon(name, color=color).pixmap(sz, sz)); self.status_icon.setVisible(not self.settings.get("hide_clock_dot", False))
        self.check_outlook_alerts()
        minute = datetime.datetime.now().minute
        if minute != getattr(self, "_cal_minute", None):
            self._cal_minute = minute
            if hasattr(self, "tasks_container_layout") and self.outlook["status"] == "ok" and not self.is_editing_tasks: self.refresh_calendar_panel()
        self.update()

    def apply_outlook(self):
        m = self.outlook_monitor; m.interval = max(15, int(self.settings.get("outlook_refresh_s", 60))); m.excluded = set(self.settings.get("outlook_calendars_off", []))
        if self.settings.get("outlook_enabled", True):
            if m.isRunning(): m.refresh()
            else: m._is_running = True; m.start()
        else:
            if m.isRunning(): m.stop()
            self.outlook = {"status": "", "events": [], "tasks": [], "unread": 0}
        self.refresh_calendar_panel(); self.update_content()

    def on_outlook(self, data):
        if not self.settings.get("outlook_enabled", True): return
        prev, self.last_unread = self.last_unread, data["unread"]
        self.outlook = data
        if self.settings.get("outlook_mail_alert", False) and prev is not None and data["unread"] > prev:
            self.enqueue_alert({"title": "Outlook", "text": f"{data['unread'] - prev} new, {data['unread']} unread", "sticky": False, "mode": "marquee", "icon": "mdi.email", "duration_ms": 3500})
        self.refresh_calendar_panel(); self.update_content()

    def outlook_events(self, now=None):
        now = now or datetime.datetime.now(); s = self.settings
        words = [w.strip().lower() for w in str(s.get("outlook_exclude_keywords", "")).split(",") if w.strip()]
        out = []
        for e in self.outlook["events"]:
            if e["end"] <= now or e["start"].date() > now.date(): continue
            if s.get("outlook_skip_allday", True) and e["all_day"]: continue
            if s.get("outlook_skip_declined", True) and e["declined"]: continue
            if s.get("outlook_skip_free", False) and e["busy"] == 0: continue
            if s.get("outlook_skip_oof", True) and e["busy"] == 3: continue
            if s.get("outlook_skip_multiday", True) and (e["end"] - e["start"]) > datetime.timedelta(hours=24): continue
            if s.get("outlook_skip_private", False) and e["private"]: continue
            if any(w in e["subject"].lower() for w in words): continue
            out.append(e)
        return out

    def outlook_due_tasks(self, now=None):
        now = now or datetime.datetime.now()
        if not self.settings.get("outlook_show_tasks", True): return []
        limit = (now + datetime.timedelta(days=int(self.settings.get("outlook_tasks_days", 0)))).date()
        due = [t for t in self.outlook["tasks"] if t["due"] and t["due"].date() <= limit]
        due.sort(key=lambda t: (t["due"], -t["importance"])); return due

    def outlook_countdown(self, now):
        if not self.settings.get("outlook_enabled", True): return None
        win = int(self.settings.get("outlook_countdown_min", 30))
        for e in self.outlook_events(now):
            mins = (e["start"] - now).total_seconds() / 60
            if mins <= 0: continue
            if mins > win: return None
            return e["subject"], f"{int(math.ceil(mins))}m"
        return None

    def check_outlook_alerts(self):
        mins = int(self.settings.get("outlook_alert_min", 5))
        if mins <= 0 or not self.settings.get("outlook_enabled", True): return
        now = datetime.datetime.now()
        for e in self.outlook_events(now):
            left = (e["start"] - now).total_seconds() / 60
            key = (e["subject"], e["start"])
            if 0 < left <= mins and key not in self.outlook_alerted:
                self.outlook_alerted.add(key)
                self.enqueue_alert({"title": e["subject"], "text": f"in {int(math.ceil(left))} min" + (f" · {e['location']}" if e["location"] else ""), "sticky": False, "mode": "marquee", "icon": "mdi.calendar-clock", "duration_ms": 6000})
        if len(self.outlook_alerted) > 200: self.outlook_alerted.clear()

    def complete_outlook_task(self, task_id):
        self.outlook["tasks"] = [t for t in self.outlook["tasks"] if t["id"] != task_id]
        self.outlook_monitor.complete_task(task_id); self.refresh_calendar_panel()

    def status_indicator(self):
        si =self.theme['status_indicator']; mode = str(si['mode']).lower()
        dot_accent = ('mdi.circle', QColor(self.accent_color))
        dot_album = ('mdi.circle', self.album_accent_color if self.media_state in ("Playing", "Paused") else QColor(self.accent_color))
        if mode == "accent": return dot_accent
        if mode == "album": return dot_album
        if mode == "weather":
            return (self.weather_icon, QColor("white")) if self.weather_icon else dot_accent
        try: batt = psutil.sensors_battery()
        except Exception: batt = None
        if mode in ("auto", "battery") and batt:
            pct = batt.percent
            if batt.power_plugged: return ('mdi.lightning-bolt', qcolor(si['charging_color']))
            if pct <= float(si['critical_percent']): return ('mdi.circle', qcolor(si['critical_color']))
            if pct <= float(si['low_percent']): return ('mdi.circle', qcolor(si['low_color']))
            if mode == "battery": return ('mdi.circle', qcolor(si['ok_color']))
        return dot_album if mode == "auto" else dot_accent

    def update_perf(self, data):
        cpu, ram, disk = data["cpu"], data["ram"], data["disk"]
        down, up = data["down"], data["up"]
        
                                              
        self.cpu_label.setText(f"CPU: {int(cpu)}%"); self.ram_label.setText(f"RAM: {int(ram)}%")
        
                                      
        self.cpu_bar_L[0].setValue(int(cpu)); self.cpu_bar_L[1].setText(f"{int(cpu)}%")
        self.ram_bar_L[0].setValue(int(ram)); self.ram_bar_L[1].setText(f"{int(ram)}%")
        self.disk_bar_L[0].setValue(int(disk)); self.disk_bar_L[1].setText(f"{int(disk)}%")
        
                                     
        def fmt(b):
            if b < 1024: return f"{int(b)} B/s"
            if b < 1024*1024: return f"{int(b/1024)} KB/s"
            return f"{b/(1024*1024):.1f} MB/s"
            
        self.net_down_L.setText(f"↓ {fmt(down)}"); self.net_up_L.setText(f"↑ {fmt(up)}")
        nics = data.get("nics", {}); act = max((n for n, v in nics.items() if v[0] != "vpn"), key=lambda n: nics[n][1] + nics[n][2], default=None)
        self.net_title_L.setText(f"NETWORK · {act}" if act and nics[act][1] + nics[act][2] > 0 else "NETWORK")
        vpns = [v for v in nics.values() if v[0] == "vpn"]
        if vpns: self.net_vpn_L.setText(f"VPN ↓ {fmt(sum(v[1] for v in vpns))} ↑ {fmt(sum(v[2] for v in vpns))}"); self.net_vpn_L.show()
        else: self.net_vpn_L.hide()

    def update_media(self, state, title, artist, accent_hex):
        started = state == "Playing" and self.media_state == "Idle"
        self.media_state, self.media_title, self.media_artist = state, title, artist; self.album_accent_color = QColor(accent_hex)
        if started and "media" in self.features and self.settings.get("music_auto_open", False) and self.current_state == "Idle" and not self.alert and not self.is_charging:
            self.current_feature_index = self.features.index("media"); self.change_state("Hover"); self.revert_timer.start(int(self.settings.get("hover_exit_ms", 1200)) + 2500)
        if state == "Idle":
            self.showing_lyrics = False
            self.media_lyric_text = ""
        self.btn_play.setIcon(qta.icon('mdi.pause' if state == "Playing" else 'mdi.play', color='white')); self.update_content()
        if self.current_state == "Hover": self.update_feature_view()

    def update_lyrics(self, text):
        if not self.settings.get("show_lyrics", True): text = ""
        was_showing = self.showing_lyrics
        self.media_lyric_text = text
        self.showing_lyrics = bool(text)
        
                                                                                  
        if was_showing != self.showing_lyrics:
            self.execute_liquid_transition()
        else:
            self.update_content()

    def update_feature_view(self):
        if self.current_state == "Notify" and self.alert:
            for p in (self.perf_panel, self.perf_widget, self.media_controls, self.weather_panel, self.calendar_panel, self.month_panel, self.basics_panel): p.hide()
            self.header_widget.show(); self.show_alert_content(); return
        self.reset_alert_widgets()
        if self.current_state == "Idle":
            self.perf_panel.hide(); self.perf_widget.hide(); self.media_controls.hide(); self.weather_panel.hide(); self.calendar_panel.hide(); self.month_panel.hide(); self.basics_panel.hide()
            self.header_widget.show(); self.update_content(); return
        if self.current_state == "Notify":
            self.perf_panel.hide(); self.perf_widget.hide(); self.media_controls.hide(); self.weather_panel.hide(); self.calendar_panel.hide(); self.month_panel.hide(); self.basics_panel.hide(); self.header_widget.show()
            if self.volume_event is not None: self.apply_volume_view(); return
            if self.key_event_on is not None:
                self.status_icon.setPixmap(qta.icon('mdi.keyboard-variant', color='white').pixmap(18, 18))
                self.status_text.setText(self.event_title); self.key_switch.show(); return
            self.status_icon.setPixmap(qta.icon('mdi.email', color='white').pixmap(18, 18))
            dt = f"{self.event_title} - {self.event_text}"; self.status_text.setText(dt[:45] + "..." if len(dt) > 48 else dt)
            return
        feature = self.features[self.current_feature_index]
        self.header_widget.show() if feature == "media" else self.header_widget.hide()
        self.perf_panel.setVisible(feature == "perf")
        self.media_controls.setVisible(feature == "media")
        self.weather_panel.setVisible(feature == "weather"); self.calendar_panel.setVisible(feature == "calendar"); self.month_panel.setVisible(feature == "month")
        self.basics_panel.setVisible(feature == "basics")
        if feature == "perf": self.status_text.setText("Performance Status"); self.status_icon.setPixmap(qta.icon('mdi.speedometer', color='white').pixmap(18, 18))
        elif feature == "media":
            if self.media_state in ("Playing", "Paused"):
                if self.showing_lyrics and self.media_lyric_text:
                    self.status_text.setText(self.media_lyric_text)
                else:
                    dt = f"{self.media_title} - {self.media_artist}"; self.status_text.setText(dt[:37] + "..." if len(dt) > 40 else dt)
            else: self.status_text.setText("Music Player")
            self.status_icon.setPixmap(qta.icon('mdi.music', color='white').pixmap(18, 18))

    def wheelEvent(self, event):
        if self.current_state == "Hover" and not self.is_editing_tasks:
            now = time.monotonic(); delta = event.angleDelta().y()
            if now < getattr(self, "_scroll_block_until", 0): event.accept(); return
            if delta * getattr(self, "_scroll_acc", 0) < 0 or now - getattr(self, "_scroll_last", 0) > 0.4: self._scroll_acc = 0
            self._scroll_last = now; self._scroll_acc = getattr(self, "_scroll_acc", 0) + delta
            if abs(self._scroll_acc) >= 120 / max(0.1, self.settings.get("scroll_sensitivity", 100) / 100):
                step = 1 if self._scroll_acc < 0 else -1; self._scroll_acc = 0
                self._scroll_block_until = now + max(0, self.settings.get("scroll_cooldown_ms", 250)) / 1000
                self.current_feature_index = (self.current_feature_index + step) % len(self.features)
                self.execute_liquid_transition()
        super().wheelEvent(event)

    def keyPressEvent(self, event):
                                                                                    
        super().keyPressEvent(event)

    def scroll_controls(self, delta):
        n = len(self.basic_controls_items)
        prev_idx = self.basic_controls_index
        self.basic_controls_index = (self.basic_controls_index + delta) % n
        
                                    
        self.animate_control_balls(True)
        
    def refresh_control_balls(self):
                                                                          
        pass

    def animate_control_balls(self, show):
                                                                    
                                                                                        
        pill_x = (self.width() - self.IDLE_W) // 2
        rect = QRect(pill_x, 20, self.IDLE_W, self.IDLE_H)
        cx = rect.right() - 22                   
        cy = rect.center().y()
        
                                                  
        targets = [
            QPoint(int(cx + 35), int(cy - 60)),                          
            QPoint(int(cx + 42), int(cy - 24)),           
            QPoint(int(cx + 25), int(cy + 22)),                  
            QPoint(int(cx - 18), int(cy + 44)),                                 
            QPoint(int(cx - 58), int(cy + 44))                                  
        ]
        
        n_items = len(self.basic_controls_items)
        
                                                           
                                                                                                         
        indices = [
            (self.basic_controls_index - 2) % n_items,
            (self.basic_controls_index - 1) % n_items,
            self.basic_controls_index,
            (self.basic_controls_index + 1) % n_items,
            (self.basic_controls_index + 2) % n_items
        ]

                                                              
                                                                      
        for i, ball in enumerate(self.control_balls):
            if not show:
                                      
                group = QParallelAnimationGroup(self)
                pos_anim = QPropertyAnimation(ball, b"pos"); pos_anim.setDuration(400); pos_anim.setEasingCurve(QEasingCurve.Type.InQuad)
                                                                          
                pos_anim.setEndValue(QPoint(int(rect.right() - 20), int(rect.bottom() - 20)))
                opa_anim = QPropertyAnimation(ball.graphicsEffect(), b"opacity"); opa_anim.setDuration(400)
                opa_anim.setEndValue(0.0)
                                        
                s_anim = QPropertyAnimation(ball, b"ball_scale"); s_anim.setDuration(400); s_anim.setEndValue(0.7)
                group.addAnimation(pos_anim); group.addAnimation(opa_anim); group.addAnimation(s_anim)
                group.finished.connect(ball.hide); group.start()
                continue

                        
            if show:
                if ball.isHidden() or ball.graphicsEffect().opacity() < 0.1:
                                                                                               
                    ball.move(QPoint(int(rect.right() - 20), int(rect.bottom() - 20)))
                ball.show()
                
            item_idx = (self.basic_controls_index + (i - 1)) % n_items
            item = self.basic_controls_items[item_idx]
            
            ball.setIcon(qta.icon(item["icon"], color='white'))
            ball.action_cmd = item["cmd"]
            
            target = targets[i+1]                                        
            opacity = 1.0 if (i >= 0 and i <= 2) else 0.0
            
                                                     
                                                                      
            scale = 1.15 if i == 1 else 1.0
            
                                                                   
            delay = i * 45 
            ball.animate_to(target, opacity, scale=scale, delay=delay)

    def idle_w(self):
        return self.COUNTDOWN_W if self.cd_active else self.IDLE_W

    def get_centered_x(self, width):
        sr = QApplication.primaryScreen().availableGeometry(); return sr.x() + (sr.width() // 2) - (width // 2)

    def execute_liquid_transition(self):
        self.grow_w_anim.stop(); self.grow_h_anim.stop(); self.grow_base = None
        if self.is_charging: w, h = 850, 40
        elif self.current_state == "Idle": 
            if self.features[self.current_feature_index] == "media" and self.showing_lyrics:
                w, h = self.LYRIC_W, self.IDLE_H
            else:
                w, h = self.idle_w(), self.IDLE_H
        elif self.current_state == "Notify": w, h = self.alert_size if self.alert else (self.NOTIFY_W, self.NOTIFY_H)
        else:
            feature = self.features[self.current_feature_index]
            if feature == "media": w, h = (self.LYRIC_W, self.MUSIC_H) if self.showing_lyrics else (self.MUSIC_W, self.MUSIC_H)
            elif feature == "perf": w, h = self.PERF_W, self.PERF_H
            elif feature == "weather": w, h = self.WEATHER_W, self.WEATHER_H
            elif feature == "calendar": 
                w, h = (self.EDIT_W, self.EDIT_H) if self.is_editing_tasks else (self.CALENDAR_W, self.CALENDAR_H)
            elif feature == "month": w, h = self.MONTH_W, self.MONTH_H
            elif feature == "basics": w, h = self.IDLE_W, self.IDLE_H                    
            else: w, h = self.EXP_W, self.EXP_H
        if not self.is_charging:
             self.shine_anim.stop(); self.shine_anim.setStartValue(0.0); self.shine_anim.setEndValue(1.0); self.shine_anim.start()
        
                                      
        def set_bg_target(anim, current_val, target_val):
            anim.stop(); anim.setStartValue(current_val); anim.setEndValue(target_val); anim.start()

        is_hover = (self.current_state != "Idle" and self.current_state != "Notify")
        feat = self.features[self.current_feature_index] if is_hover else None

                                        
        self.animate_control_balls(feat == "basics")
        
        set_bg_target(self.weather_bg_anim, self._weather_bg_opacity, 1.0 if feat == "weather" else 0.0)
        set_bg_target(self.perf_bg_anim, self._perf_bg_opacity, 1.0 if feat == "perf" else 0.0)
        set_bg_target(self.calendar_bg_anim, self._calendar_bg_opacity, 1.0 if feat == "calendar" else 0.0)
        set_bg_target(self.month_bg_anim, self._month_bg_opacity, 1.0 if feat == "month" else 0.0)

        self.anim_group.stop()
        self.content_pos_anim.setStartValue(QPoint(0, 0))
        self.content_pos_anim.setEndValue(QPoint(0, 0))
        self.opacity_anim.setStartValue(1.0); self.opacity_anim.setKeyValueAt(0.3, 0.0); self.opacity_anim.setEndValue(1.0)
        self.island_w_anim.setStartValue(self._island_w); self.island_w_anim.setEndValue(w)
        self.island_h_anim.setStartValue(self._island_h); self.island_h_anim.setEndValue(h)
        QTimer.singleShot(250, self.update_feature_view)
        QTimer.singleShot(250, lambda: self.reset_content_slide(w))
        self.anim_group.start()

    def reset_content_slide(self, target_w):
        current_y = self.content_container.y()
        self.content_pos_anim.stop()
        self.content_pos_anim.setStartValue(QPoint(target_w // 4, current_y))
        self.content_pos_anim.setEndValue(QPoint(0, current_y))
        self.content_pos_anim.start()

    def change_state(self, new):
        if self.current_state == new: return
        self.current_state = new; self.execute_liquid_transition()

    def set_island_style(self, style):
        self.island_style = style
        self.save_settings()
        self.recenter_window()
        self.execute_liquid_transition()
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())
        self.update()

    def set_animation_style(self, style):
        self.animation_style = style
        self.update_audio_capture()
        self.save_settings()
        self.update()

    def get_island_rect(self):
        W = self._island_w
        H = self._island_h
        centerX = self.width() / 2
        if self.island_style == "Notch Nook":
            return QRectF(centerX - W/2, 0, W, H)
        return QRectF(centerX - W/2, 10, W, H)

    def recenter_window(self):
        if self.compatibility_mode:
            # Unlock size restrictions to allow full-screen expansion
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            sr = QApplication.primaryScreen().availableGeometry()
            self.setGeometry(sr)
        else:
            self.setFixedSize(1200, 700)
            top_y = 0 if self.island_style == "Notch Nook" else 10
            self.move(self.get_centered_x(self.width()), QApplication.primaryScreen().geometry().y() + top_y)
        self.apply_screens()

    def apply_screens(self):
        if not hasattr(self, "mirrors"): return
        primary = QApplication.primaryScreen()
        want = [sc for sc in QApplication.screens() if sc is not primary] if self.settings.get("island_screens", "main") == "all" else []
        for name in [n for n in self.mirrors if n not in [sc.name() for sc in want]]: self.mirrors.pop(name).close()
        top_y = 0 if self.island_style == "Notch Nook" else 10
        for sc in want:
            m = self.mirrors.get(sc.name())
            if m is None: m = self.mirrors[sc.name()] = IslandMirror()
            m.setFixedSize(self.size())
            if self.compatibility_mode: g = sc.availableGeometry(); y = g.y()
            else: g = sc.geometry(); y = g.y() + top_y
            m.move(g.x() + (g.width() - self.width()) // 2, y)
            if not m.isVisible(): m.show()
        if want and not self.mirror_timer.isActive(): self.mirror_timer.start(33)
        elif not want: self.mirror_timer.stop()

    def refresh_mirrors(self):
        if not self.mirrors or not self.isVisible(): return
        pm = self.grab()
        for m in self.mirrors.values(): m.set_frame(pm)

    def set_island_screens(self, mode):
        self.settings["island_screens"] = mode; self.save_settings(); self.apply_screens()

    def toggle_compatibility_mode(self):
        self.compatibility_mode = not self.compatibility_mode
        self.save_settings()
        self.recenter_window()
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.remove_dwm_border()

    def remove_dwm_border(self):
        # Win11 draws a 1px DWM border and rounded corners around top-level windows,
        # which shows as a box around the transparent window.
        try:
            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi
            border_none = ctypes.c_uint(0xFFFFFFFE)   # DWMWA_COLOR_NONE
            dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border_none), 4)   # DWMWA_BORDER_COLOR
            no_round = ctypes.c_int(1)                # DWMWCP_DONOTROUND
            dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(no_round), 4)      # DWMWA_WINDOW_CORNER_PREFERENCE
        except Exception:
            pass

    def check_mouse_position(self):
        if self.alert and not self.is_dialog_open: self.alert_click_through(); return
        if self.current_state == "Notify" or self.is_dialog_open: return
        cursor_pos = QCursor.pos()
        rect = self.get_island_rect()
        
                                                                                  
        global_top_left = self.mapToGlobal(QPoint(int(rect.x()), int(rect.y())))
        global_bottom_right = self.mapToGlobal(QPoint(int(rect.right()), int(rect.bottom())))
        global_rect = QRect(global_top_left, global_bottom_right)
        
                                                                            
                                                                              
        hit_rect = global_rect.adjusted(-15, -10, 80, 50)  
        hwnd = int(self.winId())
        ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        WS_EX_TRANSPARENT = 0x20
        
        ghost = self.settings.get("ctrl_ghost", True) and hit_rect.contains(cursor_pos) and bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
        ghost_op = float(self.theme['island']['ctrl_ghost_opacity'])
        if ghost != getattr(self, "_ghost", False):
            self._ghost = ghost; self.setWindowOpacity(ghost_op if ghost else 1.0)
        elif ghost and abs(self.windowOpacity() - ghost_op) > 0.01:
            self.setWindowOpacity(ghost_op)
        if hit_rect.contains(cursor_pos) and not ghost:
            if ex & WS_EX_TRANSPARENT:
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex & ~WS_EX_TRANSPARENT)
            if self.current_state != "Hover":
                if self.hover_enter_t is None:
                    self.hover_enter_t = time.monotonic(); self.start_hover_grow()
                if time.monotonic() - self.hover_enter_t >= self.HOVER_DELAY:
                    self.hover_enter_t = None; self.change_state("Hover")
            else:
                self.hover_enter_t = None
            self.revert_timer.stop()
        else:
            if self.hover_enter_t is not None: self.hover_enter_t = None; self.end_hover_grow()
            if not (ex & WS_EX_TRANSPARENT): 
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | WS_EX_TRANSPARENT)
            if self.current_state == "Hover":
                if not self.revert_timer.isActive():
                    self.revert_timer.start(int(self.settings.get("hover_exit_ms", 1200)))

    def alert_click_through(self):
        rect = self.get_island_rect()
        gr = QRect(self.mapToGlobal(QPoint(int(rect.x()), int(rect.y()))), self.mapToGlobal(QPoint(int(rect.right()), int(rect.bottom()))))
        hwnd = int(self.winId()); ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        over = gr.contains(QCursor.pos())
        if over and ex & 0x20: ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex & ~0x20)
        elif not over and not ex & 0x20: ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x20)

    def mousePressEvent(self, event):
        if self.alert and event.button() == Qt.MouseButton.LeftButton: self.finish_alert(); return
        super().mousePressEvent(event)

    def start_hover_grow(self):
        if self.current_state != "Idle" or self.is_charging or self.anim_group.state() != QAbstractAnimation.State.Stopped: return
        lyrics = self.features[self.current_feature_index] == "media" and self.showing_lyrics
        self.grow_base = (self.LYRIC_W if lyrics else self.idle_w(), self.IDLE_H)
        for anim, cur, end in [(self.grow_w_anim, self._island_w, self.grow_base[0] + self.HOVER_GROW), (self.grow_h_anim, self._island_h, self.grow_base[1] + self.HOVER_GROW // 3)]:
            anim.stop(); anim.setDuration(int(self.HOVER_DELAY * 1000)); anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            anim.setStartValue(cur); anim.setEndValue(end); anim.start()

    def end_hover_grow(self):
        if self.grow_base is None: return
        for anim, cur, end in [(self.grow_w_anim, self._island_w, self.grow_base[0]), (self.grow_h_anim, self._island_h, self.grow_base[1])]:
            anim.stop(); anim.setDuration(300); anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(cur); anim.setEndValue(end); anim.start()
        self.grow_base = None

    def contextMenuEvent(self, event):
        menu = QMenu(self); mn = self.theme['menu']; menu.setStyleSheet(f"QMenu {{ background-color: {css(mn['background'])}; color: {css(mn['text'])}; border: 1px solid {css(mn['border'])}; padding: 4px; border-radius: 6px; }} QMenu::item:selected {{ background-color: {self.accent_color}; }}")
        menu.addAction("Settings").triggered.connect(self.open_settings)
        menu.addSeparator(); menu.addAction("Exit").triggered.connect(self.close); menu.exec(self.mapToGlobal(event.pos()))

    def open_settings(self):
        if getattr(self, 'settings_dialog', None) is not None and self.settings_dialog.isVisible():
            self.settings_dialog.raise_(); self.settings_dialog.activateWindow(); return
        self.settings_dialog = SettingsDialog(self); self.settings_dialog.show()

    def apply_behavior(self):
        self.HOVER_DELAY = max(0, self.settings.get("hover_delay_ms", 500)) / 1000; self.HOVER_GROW = max(0, self.settings.get("hover_grow_px", 30))

    def card_layout(self):
        saved = [c for c in self.settings.get("card_order", []) if c in self.ALL_CARDS]
        order = list(dict.fromkeys(saved + self.ALL_CARDS)); hidden = set(self.settings.get("card_hidden", []))
        return order, hidden

    def apply_cards(self):
        order, hidden = self.card_layout()
        vis = [c for c in order if c not in hidden] or list(order)
        cur = self.features[self.current_feature_index] if self.current_feature_index < len(self.features) else None
        self.features = vis
        self.current_feature_index = vis.index(cur) if cur in vis else min(self.current_feature_index, len(vis) - 1)
        if hasattr(self, "anim_group") and self.current_state == "Hover" and self.features[self.current_feature_index] != cur: self.execute_liquid_transition()

    def set_cards(self, order, hidden):
        self.settings["card_order"] = list(order); self.settings["card_hidden"] = list(hidden); self.save_settings(); self.apply_cards()

    def set_behavior(self, key, value):
        self.settings[key] = value; self.apply_behavior(); self.save_settings()
        if key == "hide_clock_dot": self.update_content()
        if key == "show_lyrics" and not value: self.update_lyrics("")
        if key == "brightness_ddc": self.brightness_monitor.ddc_enabled = bool(value)
        if key.startswith("outlook_"): self.apply_outlook()
        if key in ("network_alerts", "bt_battery_min"): self.apply_net_settings()

    def set_theme_values(self, changes):
        update_theme_file(changes); self.apply_theme()

    def closeEvent(self, event):
        if getattr(self, 'settings_dialog', None) is not None: self.settings_dialog.close()
        if self.audio_monitor is not None: self.audio_monitor.stop()
        self.perf_monitor.stop()
        self.media_monitor.stop()
        self.key_monitor.stop()
        self.volume_monitor.stop()
        self.brightness_monitor.stop()
        self.net_monitor.stop()
        for m in self.mirrors.values(): m.close()
        self.notif_monitor.stop()
        self.api_server.stop()
        self.weather_monitor.stop()
        self.outlook_monitor.stop()
        super().closeEvent(event); QApplication.quit()

def install_crash_log():
    import faulthandler, traceback
    base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    log = open(os.path.join(base, "crash.log"), "a", buffering=1, encoding="utf-8")
    log.write(f"\n--- start {datetime.datetime.now().isoformat()} ---\n"); faulthandler.enable(log, all_threads=True)
    def hook(t, v, tb): log.write("".join(traceback.format_exception(t, v, tb))); sys.__excepthook__(t, v, tb)
    sys.excepthook = hook
    def thread_hook(a): log.write(f"thread {a.thread.name if a.thread else '?'}:\n" + "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))
    threading.excepthook = thread_hook

if __name__ == "__main__":
    try: install_crash_log()
    except Exception: pass
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False); island = DynamicIsland(); island.show()
    QTimer.singleShot(100, lambda: (island.update_island_geometry(island.get_island_rect(), island.get_current_radius()), island.content_container.move(0, 0), island.update()))
    sys.exit(app.exec())
