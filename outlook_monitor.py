import datetime
import threading
import pythoncom
import win32com.client
from PyQt6.QtCore import QThread, pyqtSignal

NO_DUE = 4000
RESPONSE_DECLINED = 4

def _dt(v):
    return datetime.datetime(v.year, v.month, v.day, v.hour, v.minute, v.second)

class OutlookMonitor(QThread):
    outlook_updated = pyqtSignal(object)

    def __init__(self, parent=None, interval=60):
        super().__init__(parent)
        self._is_running = True
        self.interval = interval
        self.days_ahead = 1
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.pending_complete = []
        self.app = None
        self.ns = None

    def refresh(self):
        self.wake.set()

    def complete_task(self, entry_id):
        with self.lock: self.pending_complete.append(entry_id)
        self.wake.set()

    def connect_outlook(self):
        try:
            self.app = win32com.client.GetActiveObject("Outlook.Application")
            self.ns = self.app.GetNamespace("MAPI")
            return True
        except Exception:
            self.app = self.ns = None
            return False

    def run(self):
        pythoncom.CoInitialize()
        try:
            while self._is_running:
                self.poll()
                self.wake.wait(self.interval)
                self.wake.clear()
        finally:
            self.app = self.ns = None
            pythoncom.CoUninitialize()

    def poll(self):
        if self.ns is None and not self.connect_outlook():
            self.outlook_updated.emit({"status": "Outlook is not running", "events": [], "tasks": [], "unread": 0}); return
        try:
            self.run_commands()
            data = {"status": "ok", "events": self.read_events(), "tasks": self.read_tasks(), "unread": self.read_unread()}
        except Exception as e:
            self.app = self.ns = None
            data = {"status": f"Outlook error: {e}", "events": [], "tasks": [], "unread": 0}
        self.outlook_updated.emit(data)

    def run_commands(self):
        with self.lock: cmds, self.pending_complete = self.pending_complete, []
        for eid in cmds:
            try:
                item = self.ns.GetItemFromID(eid); item.MarkComplete(); item.Save()
            except Exception as e:
                print("OutlookMonitor complete error:", e)

    def read_events(self):
        folder = self.ns.GetDefaultFolder(9)
        items = folder.Items; items.Sort("[Start]"); items.IncludeRecurrences = True
        start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + datetime.timedelta(days=self.days_ahead + 1)
        fmt = "%m/%d/%Y %H:%M"
        found = items.Restrict(f"[Start] < '{end.strftime(fmt)}' AND [End] > '{start.strftime(fmt)}'")
        out = []
        for it in found:
            try:
                out.append({"subject": it.Subject or "(no title)", "start": _dt(it.Start), "end": _dt(it.End), "all_day": bool(it.AllDayEvent),
                            "location": it.Location or "", "busy": int(it.BusyStatus), "declined": int(it.ResponseStatus) == RESPONSE_DECLINED,
                            "private": int(it.Sensitivity) == 2, "calendar": folder.Name})
            except Exception:
                continue
            if len(out) >= 100: break
        out.sort(key=lambda e: e["start"])
        return out

    def read_tasks(self):
        out = []
        def scan(folder, depth=0):
            try:
                for it in folder.Items.Restrict("[Complete] = False"):
                    try:
                        due = it.DueDate; due = _dt(due) if due.year < NO_DUE else None
                        out.append({"id": it.EntryID, "subject": it.Subject or "(no title)", "due": due, "list": folder.Name, "importance": int(it.Importance)})
                    except Exception:
                        continue
                if depth == 0:
                    for sub in folder.Folders: scan(sub, 1)
            except Exception:
                pass
        scan(self.ns.GetDefaultFolder(13))
        return out[:200]

    def read_unread(self):
        return int(self.ns.GetDefaultFolder(6).UnReadItemCount)

    def stop(self):
        self._is_running = False; self.wake.set(); self.wait(2000)
