# 板载 WS2812 RGB 灯测试（无需接线）
# 出厂原理图与例程确认：数据脚 GPIO48，1 颗灯珠
# 运行：python -m mpremote connect COMx run esp32/rgb_led.py

import time

from machine import Pin
from neopixel import NeoPixel

np = NeoPixel(Pin(48, Pin.OUT), 1)
colors = [(64, 0, 0), (0, 64, 0), (0, 0, 64), (64, 64, 64)]
for _ in range(3):
    for color in colors:
        np[0] = color
        np.write()
        time.sleep_ms(400)
np[0] = (0, 0, 64)
np.write()
print("rgb led test done")
