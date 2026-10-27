import machine
from neopixel import NeoPixel

from .base import Feature


class LedFeature(Feature):
    id = "led"
    title = "板载灯"
    order = 20
    fields = [
        {"key": "led", "label": "状态"},
        {"key": "pwm", "label": "PWM", "unit": "/1023"},
    ]
    card_fields = ["led"]
    actions = [
        {"action": "on", "label": "开灯", "type": "button"},
        {"action": "off", "label": "关灯", "type": "button"},
        {"action": "pwm", "label": "PWM", "type": "range", "min": 0, "max": 1023, "value_key": "pwm"},
    ]

    def init(self):
        self.pixel = NeoPixel(machine.Pin(48, machine.Pin.OUT), 1)
        self.led = "off"
        self.pwm = 0
        self.show()

    def show(self):
        if self.led == "on":
            self.pixel[0] = (0, 64, 0)
        elif self.led == "pwm":
            b = max(0, min(64, self.pwm * 64 // 1023))
            self.pixel[0] = (b, b, b)
        else:
            self.pixel[0] = (0, 0, 0)
        self.pixel.write()

    def status(self):
        return {"led": self.led, "pwm": self.pwm}

    def command(self, action, value=None):
        if action == "on":
            self.led = "on"
        elif action == "off":
            self.led = "off"
        elif action == "toggle":
            self.led = "off" if self.led != "off" else "on"
        elif action == "pwm":
            try:
                v = max(0, min(1023, int(value)))
            except (TypeError, ValueError):
                return {"ok": False, "error": "invalid pwm"}
            self.pwm = v
            self.led = "pwm" if v > 0 else "off"
        else:
            return {"ok": False, "error": "unsupported action"}
        self.show()
        return {"ok": True, "led": self.led, "pwm": self.pwm}
