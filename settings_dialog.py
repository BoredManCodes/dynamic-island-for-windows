import os

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtMultimedia import QMediaDevices
from PyQt6.QtWidgets import (QMessageBox, QDialog,QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
                             QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                             QListWidget, QListWidgetItem, QColorDialog, QLineEdit, QSlider)

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
        tabs.addTab(self.page_cards(), "Cards")
        tabs.addTab(self.page_outlook(), "Outlook")
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
        a = QComboBox(); a.addItems(["Glow Sweep", "Fluid Blobs", "Neon Border", "Equaliser"]); a.setCurrentText(isl.animation_style)
        a.currentTextChanged.connect(isl.set_animation_style); f.addRow("Animation style", a)
        s = QComboBox(); s.addItems(["Default", "Liquid Glass", "Notch Nook"]); s.setCurrentText(isl.island_style)
        s.currentTextChanged.connect(isl.set_island_style); f.addRow("Island style", s)
        d = QComboBox(); d.addItem("Main display only", "main"); d.addItem("All displays (mirrored, click-through)", "all")
        d.setCurrentIndex(1 if isl.settings.get("island_screens", "main") == "all" else 0); d.currentIndexChanged.connect(lambda _: isl.set_island_screens(d.currentData())); f.addRow("Show island on", d)
        c = QCheckBox("Cover the full screen (fixes the big box)"); c.setChecked(isl.compatibility_mode)
        c.toggled.connect(lambda _: isl.toggle_compatibility_mode()); f.addRow("Compatibility mode", c)
        loc = QPushButton(isl.weather_monitor.city); loc.clicked.connect(lambda: (isl.change_location_dialog(), loc.setText(isl.weather_monitor.city)))
        f.addRow("Weather location", loc)
        return w

    def beh_spin(self, form, label, key, default, lo, hi, step=1, suffix=""):
        s = QSpinBox(); s.setRange(lo, hi); s.setSingleStep(step); s.setSuffix(suffix); s.setValue(int(self.island.settings.get(key, default)))
        s.valueChanged.connect(lambda v, k=key: self.island.set_behavior(k, v)); form.addRow(label, s)

    def beh_check(self, form, label, text, key, default):
        c = QCheckBox(text); c.setChecked(bool(self.island.settings.get(key, default)))
        c.toggled.connect(lambda v, k=key: self.island.set_behavior(k, v)); form.addRow(label, c); return c

    CARD_NAMES = {"perf": "Performance", "media": "Music", "weather": "Weather", "calendar": "Calendar", "month": "Month", "basics": "Basics"}

    def page_cards(self):
        w = QWidget(); w.setObjectName("Page"); v = QVBoxLayout(w); v.setContentsMargins(14, 14, 14, 14)
        info = QLabel("Tick a card to show it. Drag rows or use the buttons to set the scroll order."); info.setWordWrap(True); info.setStyleSheet("color: #888;"); v.addWidget(info)
        self.card_list = QListWidget(); self.card_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        order, hidden = self.island.card_layout()
        for c in order:
            it = QListWidgetItem(self.CARD_NAMES.get(c, c)); it.setData(Qt.ItemDataRole.UserRole, c)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable); it.setCheckState(Qt.CheckState.Unchecked if c in hidden else Qt.CheckState.Checked)
            self.card_list.addItem(it)
        self.card_list.itemChanged.connect(self.cards_changed); self.card_list.model().rowsMoved.connect(self.cards_changed)
        v.addWidget(self.card_list)
        row = QHBoxLayout(); up = QPushButton("Move up"); dn = QPushButton("Move down")
        up.clicked.connect(lambda: self.move_card(-1)); dn.clicked.connect(lambda: self.move_card(1)); row.addWidget(up); row.addWidget(dn); v.addLayout(row)
        return w

    def move_card(self, d):
        r = self.card_list.currentRow(); n = r + d
        if r < 0 or not 0 <= n < self.card_list.count(): return
        it = self.card_list.takeItem(r); self.card_list.insertItem(n, it); self.card_list.setCurrentRow(n); self.cards_changed()

    def cards_changed(self, item=None, *_):
        items = [self.card_list.item(i) for i in range(self.card_list.count())]
        if not any(i.checkState() == Qt.CheckState.Checked for i in items):
            self.card_list.blockSignals(True); (item if isinstance(item, QListWidgetItem) else items[0]).setCheckState(Qt.CheckState.Checked); self.card_list.blockSignals(False)
        self.island.set_cards([i.data(Qt.ItemDataRole.UserRole) for i in items], [i.data(Qt.ItemDataRole.UserRole) for i in items if i.checkState() != Qt.CheckState.Checked])

    def page_outlook(self):
        w, f = self.page(); isl = self.island
        self.beh_check(f, "Outlook", "Read calendar, tasks and mail from classic Outlook", "outlook_enabled", True)
        self.status_lbl = QLabel(); self.status_lbl.setWordWrap(True); self.status_lbl.setStyleSheet("color: #888;"); f.addRow("Status", self.status_lbl)
        self.update_outlook_status()
        self.beh_spin(f, "Refresh every", "outlook_refresh_s", 60, 15, 3600, 15, " s")
        self.beh_spin(f, "Countdown on idle island within", "outlook_countdown_min", 30, 0, 240, 5, " min")
        self.beh_spin(f, "Alert before a meeting", "outlook_alert_min", 5, 0, 60, 1, " min")
        self.cal_list = QListWidget(); self.cal_list.setMaximumHeight(110); f.addRow("Calendars", self.cal_list)
        self.fill_calendars(); self.cal_list.itemChanged.connect(self.calendars_changed)
        rl = QPushButton("Reload calendar list"); rl.clicked.connect(lambda: (isl.outlook_monitor.refresh(), QTimer.singleShot(2500, self.fill_calendars))); f.addRow("", rl)
        self.beh_check(f, "Skip", "All-day events", "outlook_skip_allday", True)
        self.beh_check(f, "", "Declined meetings", "outlook_skip_declined", True)
        self.beh_check(f, "", "Events shown as Free", "outlook_skip_free", False)
        self.beh_check(f, "", "Out of office", "outlook_skip_oof", True)
        self.beh_check(f, "", "Events longer than 24 hours", "outlook_skip_multiday", True)
        self.beh_check(f, "", "Private events", "outlook_skip_private", False)
        kw = QLineEdit(isl.settings.get("outlook_exclude_keywords", "")); kw.setPlaceholderText("comma separated, e.g. lunch, focus time")
        kw.editingFinished.connect(lambda: isl.set_behavior("outlook_exclude_keywords", kw.text().strip())); f.addRow("Skip titles containing", kw)
        self.beh_check(f, "Tasks", "Show Microsoft To Do tasks (click the circle to complete)", "outlook_show_tasks", True)
        self.beh_spin(f, "Include tasks due within", "outlook_tasks_days", 0, 0, 30, 1, " days")
        self.beh_check(f, "Mail", "Show unread count on the idle island", "outlook_unread_idle", True)
        self.beh_check(f, "", "Alert when new mail arrives", "outlook_mail_alert", False)
        return w

    def fill_calendars(self):
        off = set(self.island.settings.get("outlook_calendars_off", [])); keys = list(dict.fromkeys(self.island.outlook_monitor.calendars + sorted(off)))
        self.cal_list.blockSignals(True); self.cal_list.clear()
        for k in keys:
            it = QListWidgetItem(k); it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable); it.setCheckState(Qt.CheckState.Unchecked if k in off else Qt.CheckState.Checked); self.cal_list.addItem(it)
        if not keys: self.cal_list.addItem("No calendars found yet (Outlook must be running)")
        self.cal_list.blockSignals(False)

    def calendars_changed(self, *_):
        items = [self.cal_list.item(i) for i in range(self.cal_list.count())]
        self.island.set_behavior("outlook_calendars_off", [i.text() for i in items if i.checkState() != Qt.CheckState.Checked])

    def update_outlook_status(self):
        st = self.island.outlook["status"]
        self.status_lbl.setText("Connected" if st == "ok" else st or "Not connected")
        self.status_lbl.setStyleSheet("color: #5C5;" if st == "ok" else "color: #E55;" if st else "color: #888;")

    def page_behavior(self):
        w, f = self.page(); isl = self.island
        self.beh_spin(f, "Hover delay before expanding", "hover_delay_ms", 500, 0, 3000, 50, " ms")
        self.beh_spin(f, "Grow on hover", "hover_grow_px", 30, 0, 100, 5, " px")
        self.beh_spin(f, "Collapse delay after leaving", "hover_exit_ms", 1200, 0, 5000, 100, " ms")
        self.beh_spin(f, "Notification display time", "notification_ms", 3500, 500, 15000, 250, " ms")
        self.beh_check(f, "Volume", "Show volume changes on the island", "volume_osd", True)
        self.beh_check(f, "Brightness", "Show brightness changes on the island", "brightness_osd", True)
        self.beh_check(f, "Charging", "Show charge level and time to full when plugged in", "charge_popup", True)
        self.beh_check(f, "", "Also watch external monitors (DDC/CI, polled every 1.5 s, may be flaky)", "brightness_ddc", False)
        self.beh_check(f, "Network", "Show Wi-Fi, LAN and Bluetooth connect/disconnect alerts", "network_alerts", True)
        self.beh_spin(f, "Bluetooth battery interval (0 = off)", "bt_battery_min", 15, 0, 120, 5, " min")
        self.beh_spin(f, "Volume display time", "volume_ms", 1500, 500, 5000, 100, " ms")
        self.beh_spin(f, "Alert popup width", "alert_width", 520, 300, 1100, 20, " px")
        self.beh_spin(f, "Alert popup height", "alert_height", 40, 40, 120, 4, " px")
        self.beh_spin(f, "Scroll sensitivity (lower = slower)", "scroll_sensitivity", 100, 10, 400, 10, " %")
        self.beh_spin(f, "Pause after each panel switch", "scroll_cooldown_ms", 250, 0, 1500, 50, " ms")
        self.beh_check(f, "Music", "Open the music tab when playback starts", "music_auto_open", False)
        self.beh_check(f, "Lyrics", "Show synced lyrics while music plays", "show_lyrics", True)
        self.beh_check(f, "Clock", "Hide the status dot next to the clock", "hide_clock_dot", False)
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
        self.api_on = QCheckBox("Enable HTTP API"); self.api_on.setChecked(s.get("api_enabled", False)); f.addRow(self.api_on)
        self.api_all = QCheckBox("Listen on all interfaces (0.0.0.0)"); self.api_all.setChecked(s.get("api_host", "127.0.0.1") == "0.0.0.0"); f.addRow(self.api_all)
        self.api_warn = QLabel("Warning: anyone on your network can send alerts and play sounds on this PC. Set a token, and use only on trusted networks. Traffic is plain HTTP, so the token is visible on the wire."); self.api_warn.setWordWrap(True); self.api_warn.setStyleSheet("color: #E94;"); f.addRow(self.api_warn)
        self.api_all.toggled.connect(self.api_warn.setVisible); self.api_warn.setVisible(self.api_all.isChecked())
        self.api_port = QSpinBox(); self.api_port.setRange(1024, 65535); self.api_port.setValue(int(s.get("api_port", 8765))); f.addRow("Port", self.api_port)
        self.api_token = QLineEdit(s.get("api_token", "")); self.api_token.setPlaceholderText("none (any local process can send alerts)"); f.addRow("Token", self.api_token)
        self.snd_dev = QComboBox(); self.snd_dev.addItem("System default", ""); cur = s.get("alert_sound_device", "")
        for d in QMediaDevices.audioOutputs(): self.snd_dev.addItem(d.description(), bytes(d.id()).decode(errors="ignore"))
        i = self.snd_dev.findData(cur); self.snd_dev.setCurrentIndex(max(i, 0)); f.addRow("Sound output", self.snd_dev)
        vrow = QHBoxLayout(); self.snd_vol = QSlider(Qt.Orientation.Horizontal); self.snd_vol.setRange(0, 100); self.snd_vol.setValue(int(s.get("alert_sound_volume", 100)))
        self.snd_vol_lbl = QLabel(f"{self.snd_vol.value()}%"); self.snd_vol_lbl.setMinimumWidth(36); test = QPushButton("Test")
        vrow.addWidget(self.snd_vol, 1); vrow.addWidget(self.snd_vol_lbl); vrow.addWidget(test); f.addRow("Sound volume", vrow)
        self.snd_save = QTimer(self); self.snd_save.setSingleShot(True); self.snd_save.setInterval(400); self.snd_save.timeout.connect(self.island.save_settings)
        self.snd_dev.currentIndexChanged.connect(self.change_sound); self.snd_vol.valueChanged.connect(self.change_sound); test.clicked.connect(self.test_sound)
        self.api_status = QLabel(); self.api_status.setWordWrap(True)
        apply = QPushButton("Apply"); apply.clicked.connect(self.apply_api); f.addRow(apply); f.addRow(self.api_status)
        help = QLabel("POST /notify with Content-Type: application/json. Fields: title, text, icon (mdi.name, emoji, file path or http URL), color (#RRGGBB or rgba()), "
                      "sound (http URL, local file path, or base64/data: URI of wav/mp3/ogg/flac/m4a, max 5 MB, plays when the alert shows), "
                      "duration_ms, sticky (true stays until clicked), mode (marquee or expand). POST /dismiss clears the current alert. GET /health checks the server. "
                      "With a token set, send Authorization: Bearer <token>.")
        help.setWordWrap(True); help.setStyleSheet("color: #888;"); f.addRow(help)
        self.show_api_status()
        return w

    def change_sound(self):
        s = self.island.settings; s["alert_sound_device"] = self.snd_dev.currentData() or ""; s["alert_sound_volume"] = self.snd_vol.value()
        self.snd_vol_lbl.setText(f"{self.snd_vol.value()}%"); self.snd_save.start()

    def test_sound(self):
        for name in ("Windows Notify System Generic.wav", "Windows Notify.wav", "tada.wav"):
            p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Media", name)
            if os.path.isfile(p): self.island.play_alert_sound(p); return

    def show_api_status(self):
        srv = self.island.api_server
        if srv.running: self.api_status.setText(f"Listening on http://{'0.0.0.0 (all interfaces)' if self.island.settings.get('api_host') == '0.0.0.0' else '127.0.0.1'}:{self.island.settings.get('api_port', 8765)}"); self.api_status.setStyleSheet("color: #5C5;")
        elif srv.error: self.api_status.setText(f"Failed to start: {srv.error}"); self.api_status.setStyleSheet("color: #E55;")
        else: self.api_status.setText("Off"); self.api_status.setStyleSheet("color: #888;")

    def apply_api(self):
        s = self.island.settings
        if self.api_all.isChecked() and self.api_on.isChecked() and s.get("api_host") != "0.0.0.0":
            msg = "This exposes the API to every device that can reach this PC." + ("" if self.api_token.text().strip() else " No token is set, so anyone can send alerts and play sounds.") + "\n\nContinue?"
            if QMessageBox.warning(self, "Open API to network", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        s["api_host"] = "0.0.0.0" if self.api_all.isChecked() else "127.0.0.1"
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
