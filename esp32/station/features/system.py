import gc
import machine
import time

import esp32

from .base import Feature


class SystemFeature(Feature):
    id = "system"
    title = "系统"
    order = 10
    fields = [
        {"key": "mcu_c", "label": "MCU 温度", "unit": "°C"},
        {"key": "uptime_s", "label": "运行时间", "unit": "s"},
        {"key": "heap_free", "label": "可用堆", "unit": "B"},
        {"key": "reset_cause", "label": "复位原因"},
        {"key": "ip", "label": "IP"},
        {"key": "ntp", "label": "NTP 时间"},
        {"key": "mqtt", "label": "MQTT"},
        {"key": "last_pub", "label": "最后上报", "unit": "s"},
        {"key": "prefix", "label": "MQTT 主题"},
    ]
    card_fields = ["mcu_c", "mqtt"]

    def status(self):
        return {
            "mcu_c": esp32.mcu_temperature(),
            "uptime_s": time.ticks_ms() // 1000,
            "heap_free": gc.mem_free(),
            "reset_cause": machine.reset_cause(),
            "ip": self.app.state["ip"],
            "ntp": self.app.state["ntp"],
            "mqtt": self.app.state["mqtt"],
            "last_pub": self.app.state["last_pub"],
            "prefix": self.app.prefix,
        }
