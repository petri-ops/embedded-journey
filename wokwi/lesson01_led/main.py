# Wokwi 仿真：外接 LED（GPIO4，串 220Ω）闪烁
# 真板同样适用（GPIO4 是 S3 安全脚）

import machine
import time

led = machine.Pin(4, machine.Pin.OUT)
while True:
    led.value(1)
    time.sleep(0.5)
    led.value(0)
    time.sleep(0.5)
