import machine
import time


a = machine.Pin(13, machine.Pin.OUT)
b = machine.Pin(12, machine.Pin.OUT)
c = machine.Pin(14, machine.Pin.OUT)
d = machine.Pin(27, machine.Pin.OUT)
e = machine.Pin(26, machine.Pin.OUT)
f = machine.Pin(25, machine.Pin.OUT)
g = machine.Pin(33, machine.Pin.OUT)
dot = machine.Pin(32, machine.Pin.OUT)

number_led = [a, b, c, d, e, f, g, dot]

number_dict = {
    0: "00000011",
    1: "10011111",
    2: "00100101",
    3: "00001101",
    4: "10011001",
    5: "01001001",
    6: "01000001",
    7: "00011111",
    8: "00000001",
    9: "00001001",
    "open": "00000000",
    "close": "11111111"
}

def show_number(number):
    if number_dict.get(number):
        i = 0
        for bit in number_dict.get(number):
            if bit == "1":
                number_led[i].value(1)
            else:
                number_led[i].value(0)
            i += 1

def main():
    # show_number("open")  # 全亮（共阳极低电平有效，所以全0）
    # show_number("close")  # 全灭（全1）

    for i in range(10):
        show_number(i)
        time.sleep(0.3)

if __name__ == "__main__":
    main()
