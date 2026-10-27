import psutil
from PyQt6.QtCore import QThread, pyqtSignal
import time
from network_monitor import iface_kind

class PerfMonitor(QThread):
    metrics_updated = pyqtSignal(dict) 

    def __init__(self, interval_sec=1.0, parent=None):
        super().__init__(parent)
        self.interval_sec = interval_sec
        self._is_running = True
        psutil.cpu_percent(interval=None)

    def run(self):
        last_net = psutil.net_io_counters(pernic=True)
        last_time = time.time()
        
        while self._is_running:
            cpu = psutil.cpu_percent(interval=None) 
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            
            cur_net = psutil.net_io_counters(pernic=True)
            cur_time = time.time()
            dt = cur_time - last_time
            
                              
            nics = {}
            for n, c in cur_net.items():
                k = iface_kind(n); l = last_net.get(n)
                if k and l and dt > 0: nics[n] = (k, max(0, c.bytes_recv - l.bytes_recv) / dt, max(0, c.bytes_sent - l.bytes_sent) / dt)
            phys = [v for v in nics.values() if v[0] != "vpn"]
            down = sum(v[1] for v in phys); up = sum(v[2] for v in phys)

            data = {
                "cpu": cpu,
                "ram": ram,
                "disk": disk,
                "down": down,
                "up": up,
                "nics": nics
            }
            
            self.metrics_updated.emit(data)
            
            last_net = cur_net
            last_time = cur_time
            
            for _ in range(int(self.interval_sec * 10)):
                if not self._is_running:
                    break
                time.sleep(0.1)

    def stop(self):
        self._is_running = False
        self.wait()
