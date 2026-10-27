# 板载 BOOT 键（GPIO0）中断测试：按下 RGB 变绿，带 250ms 消抖
# ISR 只置标志，NeoPixel 写入放在主循环（第 2 课 ISR 纪律）
# 运行：python -m mpremote connect COMx run esp32/boot_key.py

import time

from machine import Pin
from neopixel import NeoPixel

np = NeoPixel(Pin(48, Pin.OUT), 1)
pressed = False


def on_press(pin):
    global pressed
    pressed = True


def show(color):
    np[0] = color
    np.write()


key = Pin(0, Pin.IN, Pin.PULL_UP)
key.irq(trigger=Pin.IRQ_FALLING, handler=on_press)

show((0, 0, 8))
print("等待第一次按下 BOOT（最长 60 秒）...")
count = 0
last = 0
ready_deadline = time.ticks_add(time.ticks_ms(), 60000)
while not pressed and time.ticks_diff(ready_deadline, time.ticks_ms()) > 0:
    time.sleep_ms(20)

if not pressed:
    print("no press within 60s")
else:
    print("检测到按键，继续统计 20 秒...")
    end = time.ticks_add(time.ticks_ms(), 20000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        if pressed:
            pressed = False
            now = time.ticks_ms()
            if time.ticks_diff(now, last) > 250:
                last = now
                count += 1
                show((0, 64, 0))
                print("press", count)
                time.sleep_ms(250)
                show((0, 0, 8))
        time.sleep_ms(10)
    print("total presses:", count)
show((0, 0, 0))

