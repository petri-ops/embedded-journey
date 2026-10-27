# 外接 LED 呼吸灯：GPIO4 ── 220Ω ── LED ── GND（S3 安全脚）
from machine import Pin, PWM
import time


led = PWM(Pin(4))
led.freq(1000)


while True:
    for i in range(0, 1024):
        led.duty(i)
        time.sleep_ms(1)
        
    for i in range(1023, -1, -1):
        led.duty(i)
        time.sleep_ms(1)

