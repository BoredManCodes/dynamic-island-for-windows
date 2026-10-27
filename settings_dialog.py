from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
                             QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                             QListWidget, QColorDialog, QLineEdit)

from theme import qcolor, css

STYLE = """
QDialog, QTabWidget::pane {{ background-color: {bg}; color: {fg}; }}
QTabWidget::pane {{ border: 1px solid {border}; }}
QWidget {{ color: {fg}; }}
QDialog, QWidget#Page {{ background-color: {bg}; }}
QTabBar::tab {{ background: transparent; color: {fg}; padding: 6px 14px; border: none; }}
QTabBar::tab:selected {{ border-bottom: 2px solid {accent}; }}
QPushButton {{ background-color: #2A2A2A; border: 1px solid {border}; border-radius: 6px; padding: 5px 12px; }}
QPushButton:hover {{ background-color: #383838; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget {{ background-color: #242424; border: 1px solid {border}; border-radius: 6px; padding: 3px 6px; }}
QComboBox QAbstractItemView {{ background-color: #242424; selection-background-color: {accent}; }}
QListWidget::item:selected {{ background-color: {accent}; }}
"""


class ColorButton(QPushButton):
    changed = pyqtSignal(str)

    def __init__(self, value, alpha=False, parent=None):
        super().__init__(parent)
        self.alpha = alpha; self.setFixedWidth(110); self.set_value(value)
        self.clicked.connect(self.pick)

    def set_value(self, value):
        self.value = str(value); c = qcolor(self.value)
        self.setText(self.value if len(self.value) <= 14 else c.name().upper())
        self.setStyleSheet(f"QPushButton {{ background-color: {css(self.value)}; color: {'#000' if c.lightness() > 140 and c.alpha() > 128 else '#FFF'}; }}")

    def pick(self):
        opts = QColorDialog.ColorDialogOption.ShowAlphaChannel if self.alpha else QColorDialog.ColorDialogOption(0)
        c = QColorDialog.getColor(qcolor(self.value), self, "Pick color", opts)
        if not c.isValid(): return
        v = c.name().upper() if c.alpha() == 255 else f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha() / 255:.2f})"
        self.set_value(v); self.changed.emit(v)


class SettingsDialog(QDialog):
    def __init__(self, island):
        super().__init__(None)
        self.island = island; self.theme = island.theme
        self.setWindowTitle("Dynamic Island Settings")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumSize(460, 480)
        mn = self.theme['menu']
        self.setStyleSheet(STYLE.format(bg=css(mn['background']), fg=css(mn['text']), border=css(mn['border']), accent=island.accent_color))
        lay = QVBoxLayout(self); tabs = QTabWidget(); lay.addWidget(tabs)
        tabs.addTab(self.page_general(), "General")
        tabs.addTab(self.page_behavior(), "Behavior")
        tabs.addTab(self.page_indicator(), "Indicator")
        tabs.addTab(self.page_theme(), "Theme")
        tabs.addTab(self.page_notifications(), "Notifications")
        tabs.addTab(self.page_api(), "API")

    def page(self):
        w = QWidget(); w.setObjectName("Page"); f = QFormLayout(w); f.setContentsMargins(14, 14, 14, 14); f.setSpacing(10); return w, f

    def th(self, path, value):
        self.island.set_theme_values({path: value})

    def color_row(self, form, label, path, alpha=False):
        d = self.theme
        for k in path.split("."): d = d[k]
        b = ColorButton(d, alpha); b.changed.connect(lambda v, p=path: self.th(p, v)); form.addRow(label, b); return b

    def spin_row(self, form, label, path, lo, hi, step=1, decimals=None):
        d = self.theme
        for k in path.split("."): d = d[k]
        if decimals is None: s = QSpinBox(); s.setRange(lo, hi); s.setValue(int(d))
        else: s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(decimals); s.setSingleStep(step); s.setValue(float(d))
        s.valueChanged.connect(lambda v, p=path: self.th(p, v)); form.addRow(label, s); return s

    def page_general(self):
        w, f = self.page(); isl = self.island
        a = QComboBox(); a.addItems(["Glow Sweep", "Fluid Blobs", "Neon Border"]); a.setCurrentText(isl.animation_style)
        a.currentTextChanged.connect(isl.set_animation_style); f.addRow("Animation style", a)
        s = QComboBox(); s.addItems(["Default", "Liquid Glass", "Notch Nook"]); s.setCurrentText(isl.island_style)
        s.currentTextChanged.connect(isl.set_island_style); f.addRow("Island style", s)
        c = QCheckBox("Cover the full screen (fixes the big box)"); c.setChecked(isl.compatibility_mode)
        c.toggled.connect(lambda _: isl.toggle_compatibility_mode()); f.addRow("Compatibility mode", c)
        loc = QPushButton(isl.weather_monitor.city); loc.clicked.connect(lambda: (isl.change_location_dialog(), loc.setText(isl.weather_monitor.city)))
        f.addRow("Weather location", loc)
        return w

    def beh_spin(self, form, label, key, default, lo, hi, step=1, suffix=""):
        s = QSpinBox(); s.setRange(lo, hi); s.setSingleStep(step); s.setSuffix(suffix); s.setValue(int(self.island.settings.get(key, default)))
        s.valueChanged.connect(lambda v, k=key: self.island.set_behavior(k, v)); form.addRow(label, s)

    def page_behavior(self):
        w, f = self.page(); isl = self.island
        self.beh_spin(f, "Hover delay before expanding", "hover_delay_ms", 500, 0, 3000, 50, " ms")
        self.beh_spin(f, "Grow on hover", "hover_grow_px", 30, 0, 100, 5, " px")
        self.beh_spin(f, "Collapse delay after leaving", "hover_exit_ms", 1200, 0, 5000, 100, " ms")
        self.beh_spin(f, "Notification display time", "notification_ms", 3500, 500, 15000, 250, " ms")
        g = QCheckBox("Hold CTRL over the island to ghost it and click through"); g.setChecked(isl.settings.get("ctrl_ghost", True))
        g.toggled.connect(lambda v: isl.set_behavior("ctrl_ghost", v)); f.addRow("CTRL ghost", g)
        self.spin_row(f, "Ghost opacity", "island.ctrl_ghost_opacity", 0, 1, 0.05, 2)
        return w

    def page_indicator(self):
        w, f = self.page()
        m = QComboBox(); m.addItems(["auto", "battery", "album", "weather", "accent"]); m.setCurrentText(str(self.theme['status_indicator']['mode']).lower())
        m.currentTextChanged.connect(lambda v: self.th("status_indicator.mode", v)); f.addRow("Mode", m)
        hint = QLabel("auto: battery when low or charging, else album color, else accent"); hint.setWordWrap(True); hint.setStyleSheet("color: #888;"); f.addRow(hint)
        self.spin_row(f, "Size", "status_indicator.size", 8, 40)
        self.color_row(f, "OK color", "status_indicator.ok_color")
        self.color_row(f, "Charging color", "status_indicator.charging_color")
        self.color_row(f, "Low color", "status_indicator.low_color")
        self.color_row(f, "Critical color", "status_indicator.critical_color")
        self.spin_row(f, "Low below (%)", "status_indicator.low_percent", 1, 99)
        self.spin_row(f, "Critical below (%)", "status_indicator.critical_percent", 1, 99)
        return w

    def page_theme(self):
        w, f = self.page(); isl = self.island
        auto = str(self.theme['accent']).lower() == 'auto'
        self.accent_btn = ColorButton(isl.accent_color); self.accent_btn.setEnabled(not auto)
        self.accent_btn.changed.connect(lambda v: self.th("accent", v))
        ac = QCheckBox("Follow Windows accent"); ac.setChecked(auto)
        def toggle(on):
            self.accent_btn.setEnabled(not on); self.th("accent", "auto" if on else self.accent_btn.value)
        ac.toggled.connect(toggle); f.addRow("Accent", ac); f.addRow("", self.accent_btn)
        self.color_row(f, "Island background", "island.background", alpha=True)
        self.color_row(f, "Border color", "island.border_color", alpha=True)
        self.spin_row(f, "Border width", "island.border_width", 0, 10, 0.1, 1)
        self.spin_row(f, "Corner radius", "island.radius", 0, 60)
        self.color_row(f, "Text", "text.primary")
        self.color_row(f, "Secondary text", "text.secondary")
        self.color_row(f, "Progress bar start", "progress.from")
        self.color_row(f, "Progress bar end", "progress.to")
        row = QHBoxLayout()
        eb = QPushButton("Edit theme.json"); eb.clicked.connect(isl.open_theme_file)
        rb = QPushButton("Reload theme.json"); rb.clicked.connect(isl.apply_theme)
        row.addWidget(eb); row.addWidget(rb); f.addRow(row)
        return w

    def page_notifications(self):
        w = QWidget(); w.setObjectName("Page"); v = QVBoxLayout(w); v.setContentsMargins(14, 14, 14, 14)
        isl = self.island
        info = QLabel("Notifications from these apps never reach the island. Names match the app name shown in the notification, ignoring case."); info.setWordWrap(True); info.setStyleSheet("color: #888;")
        v.addWidget(info)
        self.ignored = QListWidget(); self.ignored.addItems(isl.settings.get("ignored_apps", [])); v.addWidget(self.ignored)
        row = QHBoxLayout(); self.app_input = QComboBox(); self.app_input.setEditable(True); self.app_input.setMinimumWidth(200)
        self.app_input.addItems(isl.settings.get("seen_notif_apps", [])); self.app_input.setCurrentText("")
        add = QPushButton("Ignore"); rem = QPushButton("Remove selected")
        add.clicked.connect(self.add_ignored); rem.clicked.connect(self.remove_ignored)
        row.addWidget(self.app_input, 1); row.addWidget(add); v.addLayout(row); v.addWidget(rem)
        hint = QLabel("The dropdown lists apps that have sent a notification since you started using this page."); hint.setWordWrap(True); hint.setStyleSheet("color: #888;"); v.addWidget(hint)
        return w

    def page_api(self):
        w, f = self.page(); isl = self.island; s = isl.settings
        self.api_on = QCheckBox("Enable local HTTP API (127.0.0.1 only)"); self.api_on.setChecked(s.get("api_enabled", False)); f.addRow(self.api_on)
        self.api_port = QSpinBox(); self.api_port.setRange(1024, 65535); self.api_port.setValue(int(s.get("api_port", 8765))); f.addRow("Port", self.api_port)
        self.api_token = QLineEdit(s.get("api_token", "")); self.api_token.setPlaceholderText("none (any local process can send alerts)"); f.addRow("Token", self.api_token)
        self.api_status = QLabel(); self.api_status.setWordWrap(True)
        apply = QPushButton("Apply"); apply.clicked.connect(self.apply_api); f.addRow(apply); f.addRow(self.api_status)
        help = QLabel("POST /notify with Content-Type: application/json. Fields: title, text, icon (mdi.name, emoji, file path or http URL), color (#RRGGBB or rgba()), "
                      "duration_ms, sticky (true stays until clicked), mode (marquee or expand). POST /dismiss clears the current alert. GET /health checks the server. "
                      "With a token set, send Authorization: Bearer <token>.")
        help.setWordWrap(True); help.setStyleSheet("color: #888;"); f.addRow(help)
        self.show_api_status()
        return w

    def show_api_status(self):
        srv = self.island.api_server
        if srv.running: self.api_status.setText(f"Listening on http://127.0.0.1:{self.island.settings.get('api_port', 8765)}"); self.api_status.setStyleSheet("color: #5C5;")
        elif srv.error: self.api_status.setText(f"Failed to start: {srv.error}"); self.api_status.setStyleSheet("color: #E55;")
        else: self.api_status.setText("Off"); self.api_status.setStyleSheet("color: #888;")

    def apply_api(self):
        s = self.island.settings
        s["api_enabled"] = self.api_on.isChecked(); s["api_port"] = self.api_port.value(); s["api_token"] = self.api_token.text().strip()
        self.island.save_settings(); self.island.apply_api(); self.show_api_status()

    def add_ignored(self):
        name = self.app_input.currentText().strip()
        if not name: return
        have = [self.ignored.item(i).text().lower() for i in range(self.ignored.count())]
        if name.lower() not in have: self.ignored.addItem(name)
        self.app_input.setCurrentText(""); self.save_ignored()

    def remove_ignored(self):
        for it in self.ignored.selectedItems(): self.ignored.takeItem(self.ignored.row(it))
        self.save_ignored()

    def save_ignored(self):
        self.island.settings["ignored_apps"] = [self.ignored.item(i).text() for i in range(self.ignored.count())]
        self.island.save_settings()
