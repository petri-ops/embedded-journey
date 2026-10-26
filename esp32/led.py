import machine
import time


pin2 = machine.Pin(2, machine.Pin.OUT)

while True:
    pin2.value(1)
    time.sleep(1)
    pin2.value(0)
    time.sleep(1)
