import time
from PyQt6.QtCore import QThread, pyqtSignal

class VolumeMonitor(QThread):
    volume_changed = pyqtSignal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True

    def endpoint(self):
        from pycaw.pycaw import AudioUtilities
        dev = AudioUtilities.GetSpeakers()
        return dev.EndpointVolume

    def run(self):
        import comtypes
        comtypes.CoInitialize()
        last = None; ep = None; tick = 0
        try:
            while self._is_running:
                try:
                    if ep is None or tick % 40 == 0: ep = self.endpoint()
                    cur = (int(round(ep.GetMasterVolumeLevelScalar() * 100)), bool(ep.GetMute()))
                    if last is not None and cur != last: self.volume_changed.emit(*cur)
                    last = cur
                except Exception as e:
                    ep = None; last = None
                    time.sleep(1.0)
                tick += 1
                time.sleep(0.05)
        finally:
            comtypes.CoUninitialize()

    def stop(self):
        self._is_running = False
        self.wait(1500)
