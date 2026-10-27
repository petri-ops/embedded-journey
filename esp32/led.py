# 外接 LED 闪烁：GPIO4 ── 220Ω ── LED ── GND（S3 安全脚）
import machine
import time


pin4 = machine.Pin(4, machine.Pin.OUT)

while True:
    pin4.value(1)
    time.sleep(1)
    pin4.value(0)
    time.sleep(1)
