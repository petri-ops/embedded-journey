import asyncio
import time

import urequests

from .base import Feature
from ..config import WEATHER_URL


class WeatherFeature(Feature):
    id = "weather"
    title = "天气"
    order = 50
    fields = [
        {"key": "temp_c", "label": "温度", "unit": "°C"},
        {"key": "humidity", "label": "湿度", "unit": "%"},
        {"key": "quality", "label": "空气"},
        {"key": "city", "label": "城市"},
        {"key": "type", "label": "天气"},
        {"key": "high", "label": "最高"},
        {"key": "low", "label": "最低"},
        {"key": "time", "label": "更新时间"},
    ]
    card_fields = ["temp_c", "humidity"]
    actions = [{"action": "refresh", "label": "刷新天气", "type": "button", "on_card": False, "auto_open": True}]
    has_loop = True

    def init(self):
        self.data = None
        self.req = False
        self.last_fetch = 0

    def status(self):
        return self.data or {}

    def command(self, action, value=None):
        if action == "refresh":
            self.req = True
            return {"ok": True, "requested": True}
        return {"ok": False, "error": "unsupported action"}

    def fetch(self):
        try:
            r = urequests.get(WEATHER_URL, timeout=15)
            d = r.json()
            r.close()
            data = d.get("data", {})
            info = d.get("cityInfo", {})
            fc = (data.get("forecast") or [{}])[0]
            hum = data.get("shidu")
            if hum:
                hum = int(hum.replace("%", ""))
            wendu = data.get("wendu")
            self.data = {
                "city": info.get("city"),
                "temp_c": float(wendu) if wendu not in (None, "") else None,
                "humidity": hum,
                "quality": data.get("quality"),
                "type": fc.get("type"),
                "high": fc.get("high"),
                "low": fc.get("low"),
                "time": d.get("time"),
            }
        except Exception as e:
            print("weather err", e)
        self.last_fetch = time.ticks_ms()

    async def loop(self):
        while True:
            if self.req or self.data is None or time.ticks_diff(time.ticks_ms(), self.last_fetch) > 600000:
                self.req = False
                self.fetch()
            await asyncio.sleep(1)
