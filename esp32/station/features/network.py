import asyncio

from .base import Feature


class NetworkFeature(Feature):
    id = "network"
    title = "网络"
    order = 40
    fields = [
        {"key": "rssi", "label": "WiFi 信号", "unit": "dBm"},
        {"key": "wifi_count", "label": "邻居数"},
        {"key": "wifi_best", "label": "最强信号", "unit": "dBm"},
    ]
    card_fields = ["rssi", "wifi_count"]
    actions = [{"action": "scan", "label": "扫描 WiFi", "type": "button", "on_card": False, "auto_open": True}]
    list_key = "wifi_list"
    list_label = "附近 WiFi"
    has_loop = True

    def init(self):
        self.scan_req = False
        self.count = None
        self.best = None
        self.items = []

    def status(self):
        wlan = self.app.wlan
        rssi = wlan.status("rssi") if wlan and wlan.isconnected() else None
        return {
            "rssi": rssi,
            "wifi_count": self.count,
            "wifi_best": self.best,
            "wifi_list": self.items,
        }

    def command(self, action, value=None):
        if action == "scan":
            self.scan_req = True
            return {"ok": True, "requested": True}
        return {"ok": False, "error": "unsupported action"}

    async def loop(self):
        while True:
            if self.scan_req:
                self.scan_req = False
                try:
                    nets = self.app.wlan.scan()
                    items = []
                    best = None
                    for n in nets:
                        ssid = n[0]
                        if isinstance(ssid, bytes):
                            try:
                                ssid = ssid.decode("utf-8", "replace")
                            except Exception:
                                ssid = str(ssid)
                        if ssid:
                            items.append((ssid, n[3]))
                            if best is None or n[3] > best:
                                best = n[3]
                    items.sort(key=lambda x: x[1], reverse=True)
                    self.count = len(nets)
                    self.best = best
                    self.items = ["%s — %d dBm" % (s, r) for s, r in items[:12]]
                except Exception as e:
                    print("wifi scan err", e)
            await asyncio.sleep(0.5)
