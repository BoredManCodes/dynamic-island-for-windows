import asyncio
import json
import re
import subprocess
import time
import psutil
from PyQt6.QtCore import QThread, pyqtSignal

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SKIP_IFACE = ("vethernet", "loopback", "bluetooth", "virtual", "vmware", "vbox", "wsl", "docker", "hyper-v", "isatap", "teredo", "npcap", "wi-fi direct", "local area connection*")
WIFI_IFACE = ("wi-fi", "wifi", "wireless", "wlan")
VPN_IFACE = ("tailscale", "wireguard", "openvpn", "vpn", "zerotier", "nord", "proton", "anyconnect", "tap-windows", "wintun", "mullvad", "cloudflare warp")
VPN_SHORT = re.compile(r"(^|[^a-z])(tap|tun|wg|ppp)([^a-z]|$)")
BATT_KEY = "{104EA319-6EE2-4701-BD47-8DDBF425BBAA} 2"


def iface_kind(name):
    low = name.lower()
    if any(k in low for k in VPN_IFACE) or VPN_SHORT.search(low): return "vpn"
    if any(k in low for k in SKIP_IFACE): return None
    if any(k in low for k in WIFI_IFACE): return "wifi"
    return "lan"


def iface_ips(addrs, name):
    return [a.address for a in addrs.get(name, []) if a.family.name == "AF_INET" and not a.address.startswith("169.254")]


def fmt_bytes(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB": return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def fmt_duration(sec):
    sec = int(sec); h, m = divmod(sec // 60, 60)
    return f"{h}h {m}m" if h else f"{m}m" if m else f"{sec}s"


def fmt_speed(mbps):
    if not mbps: return ""
    return f"{mbps / 1000:g} Gbps" if mbps >= 1000 else f"{mbps:g} Mbps"


class NetworkMonitor(QThread):
    event = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True
        self.battery_minutes = 15
        self.enabled = True

    def wifi_info(self):
        try:
            out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW).stdout
        except Exception:
            return None
        ssid = re.search(r"^\s*SSID\s*:\s*(.+?)\s*$", out, re.M)
        if not ssid: return None
        name = re.search(r"^\s*Name\s*:\s*(.+?)\s*$", out, re.M)
        rate = re.search(r"^\s*Receive rate[^:]*:\s*([\d.]+)", out, re.M)
        speed = float(rate.group(1)) if rate else 0
        if not speed and name:
            st = psutil.net_if_stats().get(name.group(1))
            speed = st.speed if st else 0
        return ssid.group(1), speed

    def lan_info(self):
        stats = psutil.net_if_stats(); addrs = psutil.net_if_addrs()
        for name, st in stats.items():
            if st.isup and iface_kind(name) == "lan" and iface_ips(addrs, name): return name, st.speed
        return None

    def vpn_info(self):
        stats = psutil.net_if_stats(); addrs = psutil.net_if_addrs(); out = {}
        for name, st in stats.items():
            if st.isup and iface_kind(name) == "vpn":
                ips = iface_ips(addrs, name)
                if ips: out[name] = ips[0]
        return out

    async def bt_connected(self):
        from winsdk.windows.devices.enumeration import DeviceInformation
        from winsdk.windows.devices.bluetooth import BluetoothDevice, BluetoothLEDevice
        found = {}
        for cls in (BluetoothDevice, BluetoothLEDevice):
            try:
                devs = await DeviceInformation.find_all_async(cls.get_device_selector_from_pairing_state(True), ["System.Devices.Aep.IsConnected"])
            except Exception:
                continue
            for d in devs:
                try:
                    if d.properties.get("System.Devices.Aep.IsConnected") and d.name: found[d.id] = d.name
                except Exception:
                    pass
        return found

    def bt_battery(self, name):
        script = ("$d = Get-PnpDevice -FriendlyName $env:BT_NAME -PresentOnly -ErrorAction SilentlyContinue; "
                  f"foreach ($x in $d) {{ $v = (Get-PnpDeviceProperty -InstanceId $x.InstanceId -KeyName '{BATT_KEY}' -ErrorAction SilentlyContinue).Data; if ($v -ne $null) {{ $v; break }} }}")
        try:
            import os
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW, env={**os.environ, "BT_NAME": name}).stdout.strip()
            v = int(out.splitlines()[0]); return v if 0 <= v <= 100 else None
        except Exception:
            return None

    def emit(self, title, text, icon):
        if self.enabled: self.event.emit(title, text, icon)

    def run(self):
        loop = asyncio.new_event_loop()
        wifi = self.wifi_info(); lan = self.lan_info(); bt = None
        try: bt = loop.run_until_complete(self.bt_connected())
        except Exception: bt = {}
        now_t = time.time(); io = psutil.net_io_counters(pernic=True)
        vpn = {n: {"ip": ip, "t": now_t, "rx": io[n].bytes_recv if n in io else 0, "tx": io[n].bytes_sent if n in io else 0} for n, ip in self.vpn_info().items()}; vpn_miss = {}
        wifi_miss = lan_miss = 0; bt_miss = {}; last_batt = {}; tick = 0
        try:
            while self._is_running:
                time.sleep(2.0); tick += 1
                try:
                    cur = self.wifi_info()
                    if cur and (not wifi or cur[0] != wifi[0]):
                        self.emit("Wi-Fi connected", f"{cur[0]}" + (f" ({fmt_speed(cur[1])})" if cur[1] else ""), "mdi.wifi")
                        wifi = cur; wifi_miss = 0
                    elif cur: wifi = cur; wifi_miss = 0
                    elif wifi:
                        wifi_miss += 1
                        if wifi_miss >= 2: self.emit("Wi-Fi disconnected", f"Disconnected from {wifi[0]}", "mdi.wifi-off"); wifi = None

                    cur = self.lan_info()
                    if cur and not lan:
                        self.emit("LAN connected", f"{cur[0]}" + (f" ({fmt_speed(cur[1])})" if cur[1] else ""), "mdi.ethernet-cable"); lan = cur; lan_miss = 0
                    elif cur: lan = cur; lan_miss = 0
                    elif lan:
                        lan_miss += 1
                        if lan_miss >= 2: self.emit("LAN disconnected", f"Disconnected from {lan[0]}", "mdi.ethernet-cable-off"); lan = None

                    cur = self.vpn_info(); io = psutil.net_io_counters(pernic=True)
                    for n, ip in cur.items():
                        vpn_miss.pop(n, None)
                        if n in vpn and n in io: vpn[n]["lrx"] = io[n].bytes_recv; vpn[n]["ltx"] = io[n].bytes_sent
                        if n not in vpn:
                            vpn[n] = {"ip": ip, "t": time.time(), "rx": io[n].bytes_recv if n in io else 0, "tx": io[n].bytes_sent if n in io else 0}
                            self.emit("VPN connected", f"{n} ({ip})", "mdi.shield-lock")
                    for n in list(vpn):
                        if n in cur: continue
                        vpn_miss[n] = vpn_miss.get(n, 0) + 1
                        if vpn_miss[n] >= 2:
                            v = vpn.pop(n); vpn_miss.pop(n)
                            rx = max(0, v.get("lrx", v["rx"]) - v["rx"]); tx = max(0, v.get("ltx", v["tx"]) - v["tx"])
                            self.emit("VPN disconnected", f"{n}: {fmt_duration(time.time() - v['t'])}, ↓ {fmt_bytes(rx)} ↑ {fmt_bytes(tx)}", "mdi.shield-off")

                    if tick % 2 == 0:
                        now = loop.run_until_complete(self.bt_connected())
                        for did, name in now.items():
                            bt_miss.pop(did, None)
                            if did not in bt:
                                b = self.bt_battery(name); last_batt[did] = time.time()
                                self.emit("Bluetooth connected", name + (f" ({b}%)" if b is not None else ""), "mdi.bluetooth-connect")
                            elif self.battery_minutes > 0 and time.time() - last_batt.get(did, 0) >= self.battery_minutes * 60:
                                last_batt[did] = time.time(); b = self.bt_battery(name)
                                if b is not None: self.emit("Bluetooth battery", f"{name}: {b}%", "mdi.bluetooth")
                        for did, name in bt.items():
                            if did in now: continue
                            bt_miss[did] = bt_miss.get(did, 0) + 1
                            if bt_miss[did] >= 2:
                                self.emit("Bluetooth disconnected", f"Disconnected from {name}", "mdi.bluetooth-off"); bt_miss.pop(did); last_batt.pop(did, None)
                                continue
                            now[did] = name
                        bt = now
                except Exception:
                    pass
        finally:
            loop.close()

    def stop(self):
        self._is_running = False
        self.wait(3000)
