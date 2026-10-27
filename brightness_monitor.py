import ctypes
import time
from ctypes import wintypes
from PyQt6.QtCore import QThread, pyqtSignal

class PHYSICAL_MONITOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("handle", wintypes.HANDLE), ("desc", wintypes.WCHAR * 128)]

ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

class BrightnessMonitor(QThread):
    brightness_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True
        self.ddc_enabled = False
        self.last = {}

    def read_wmi(self, svc):
        out = []
        for m in svc.ExecQuery("SELECT CurrentBrightness FROM WmiMonitorBrightness"): out.append(int(m.CurrentBrightness))
        return out

    def read_ddc(self):
        user32, dxva2 = ctypes.windll.user32, ctypes.windll.dxva2
        handles = []
        def cb(hmon, hdc, rect, lp): handles.append(hmon); return True
        user32.EnumDisplayMonitors(None, None, ENUM_PROC(cb), 0)
        out = []
        for hmon in handles:
            n = wintypes.DWORD()
            if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(n)) or n.value == 0: continue
            arr = (PHYSICAL_MONITOR * n.value)()
            if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, n.value, arr): continue
            for pm in arr:
                lo, cur, hi = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                if dxva2.GetMonitorBrightness(pm.handle, ctypes.byref(lo), ctypes.byref(cur), ctypes.byref(hi)) and hi.value > lo.value:
                    out.append(round((cur.value - lo.value) * 100 / (hi.value - lo.value)))
            dxva2.DestroyPhysicalMonitors(n.value, arr)
        return out

    def check(self, key, values):
        for i, v in enumerate(values):
            k = (key, i)
            if k in self.last and self.last[k] != v: self.brightness_changed.emit(v)
            self.last[k] = v

    def run(self):
        import pythoncom
        pythoncom.CoInitialize()
        svc = None; n = 0
        try:
            while self._is_running:
                try:
                    if svc is None:
                        import win32com.client
                        svc = win32com.client.GetObject(r"winmgmts:\\.\root\wmi")
                    self.check("wmi", self.read_wmi(svc))
                except Exception: svc = None; time.sleep(2.0)
                if self.ddc_enabled and n % 5 == 0:
                    try: self.check("ddc", self.read_ddc())
                    except Exception: pass
                n += 1
                time.sleep(0.3)
        finally:
            pythoncom.CoUninitialize()

    def stop(self):
        self._is_running = False
        self.wait(1500)
