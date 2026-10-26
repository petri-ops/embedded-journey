# main.py - ESP32 开机自动运行程序
# 功能: 自动连接 WiFi -> 启动网页服务 -> 浏览器远程控制板载 LED
# 板子断电重启后此程序会自动执行, 无需电脑和 USB 线

import network
import machine
import socket
import time

# ===== WiFi 配置 =====
# 密码已抽到 wifi_config.py（不入库）；首次使用：复制 wifi_config.example.py 为 wifi_config.py 并填入 WiFi
try:
    from wifi_config import SSID, PASSWORD
except ImportError:
    SSID = PASSWORD = None  # 缺配置：跳过连路由器，直接开热点兜底

LED = machine.Pin(2, machine.Pin.OUT)  # 板载 LED 在 GPIO2
LED.value(0)

PAGE = """HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32 远程控制</title><style>
body{font-family:sans-serif;text-align:center;padding-top:50px;background:#f4f4f4}
.st{font-size:42px;margin:24px}
button{font-size:22px;padding:14px 44px;margin:8px;border:none;border-radius:12px;color:#fff;cursor:pointer}
.on{background:#e74c3c}.off{background:#2ecc71}
small{color:#888}
</style></head><body>
<h1>&#128161; ESP32 LED 远程控制</h1>
<div class="st">LED 当前: {STATE}</div>
<a href="/on"><button class="on">开灯 ON</button></a>
<a href="/off"><button class="off">关灯 OFF</button></a>
<p><small>{IP} · MicroPython v1.29</small></p>
</body></html>
"""


def connect_wifi():
    """连接家里路由器的 WiFi; 失败则开启自带热点兜底"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if SSID and not wlan.isconnected():
        print("正在连接 WiFi:", SSID)
        wlan.connect(SSID, PASSWORD)
        for _ in range(150):  # 最多等 15 秒
            if wlan.isconnected():
                break
            time.sleep(0.1)
    if wlan.isconnected():
        print("WiFi 已连接, IP:", wlan.ifconfig()[0])
        return "http://" + wlan.ifconfig()[0]
    # 家里 WiFi 连不上时(如路由器断网), 板子自己开热点, 仍可访问
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid="ESP32-Demo", password="12345678")
    print("WiFi 连接失败, 已开启热点 ESP32-Demo(密码12345678)")
    return "http://" + ap.ifconfig()[0]


def serve(url):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(socket.getaddrinfo("0.0.0.0", 80)[0][-1])
    s.listen(3)
    print("网页服务已启动:", url)
    while True:
        conn = None
        try:
            conn, _addr = s.accept()
            req = conn.recv(1024).decode()
            path = req.split(" ")[1] if " " in req else "/"
            if path == "/on":
                LED.value(1)
            elif path == "/off":
                LED.value(0)
            state = "亮 &#128161;" if LED.value() else "灭"
            conn.send(PAGE.replace("{STATE}", state).replace("{IP}", url))
        except Exception as e:
            print("处理请求出错:", e)
        finally:
            if conn:
                conn.close()


serve(connect_wifi())
