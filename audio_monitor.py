import time
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

RATE, BLOCK = 44100, 1024
F_MIN, F_MAX = 40.0, 14000.0


class AudioMonitor(QThread):
    levels_updated = pyqtSignal(list)

    def __init__(self, bands=32, parent=None):
        super().__init__(parent)
        self._is_running = True
        self.bands = int(bands)
        self.window = np.hanning(BLOCK).astype(np.float32)
        self.freqs = np.fft.rfftfreq(BLOCK, 1.0 / RATE)
        self.peak = 1e-3

    def edges(self):
        return np.geomspace(F_MIN, F_MAX, self.bands + 1)

    def analyse(self, block):
        mono = block.mean(axis=1) * self.window
        mag = np.abs(np.fft.rfft(mono)) / (BLOCK / 4)
        edges = self.edges(); out = np.zeros(self.bands, dtype=np.float32)
        for i in range(self.bands):
            m = (self.freqs >= edges[i]) & (self.freqs < edges[i + 1])
            if m.any(): out[i] = mag[m].max()
            else: out[i] = mag[np.searchsorted(self.freqs, edges[i])]
        out = np.sqrt(out)
        out *= np.linspace(0.8, 1.6, self.bands)
        top = float(out.max())
        self.peak = max(top, self.peak * 0.995, 0.02)
        return np.clip(out / self.peak, 0.0, 1.0).tolist()

    def run(self):
        while self._is_running:
            try:
                import soundcard as sc
                speaker = sc.default_speaker()
                mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
                with mic.recorder(samplerate=RATE, channels=2, blocksize=BLOCK) as rec:
                    while self._is_running:
                        self.levels_updated.emit(self.analyse(rec.record(numframes=BLOCK)))
            except Exception as e:
                print("Audio capture error:", e)
                self.levels_updated.emit([])
                for _ in range(20):
                    if not self._is_running: break
                    time.sleep(0.1)

    def stop(self):
        self._is_running = False
        self.wait(1500)
