import asyncio
import machine
import time

from .base import Feature
from ..config import LOCAL_OFFSET


class BootFeature(Feature):
    id = "boot"
    title = "BOOT 键"
    order = 30
    fields = [
        {"key": "boot", "label": "状态"},
        {"key": "boot_count", "label": "次数"},
        {"key": "boot_last", "label": "最后按下"},
    ]
    card_fields = ["boot", "boot_count"]
    has_loop = True

    def init(self):
        self.key = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
        self.count = 0
        self.last = None
        self._last_val = self.key.value()
        self._last_edge = 0

    def status(self):
        return {
            "boot": "按下" if self.key.value() == 0 else "松开",
            "boot_count": self.count,
            "boot_last": self.last,
        }

    async def loop(self):
        while True:
            val = self.key.value()
            if self._last_val == 1 and val == 0:
                now = time.ticks_ms()
                if time.ticks_diff(now, self._last_edge) > 250:
                    self._last_edge = now
                    self.count += 1
                    t = time.localtime(time.time() + LOCAL_OFFSET)
                    self.last = "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])
                    self.app.command("led", "toggle")
            self._last_val = val
            await asyncio.sleep(0.02)
