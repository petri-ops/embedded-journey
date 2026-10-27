# 远程监测站 v2：WiFi + MQTT + HTTP 网页 + BLE + NTP + CSV
# 数据：MCU 温度 / WiFi RSSI / uptime / heap / 天气 / 灯状态 / 日志行数
# 网页：http://<板子IP>/（局域网）
# BLE：设备名 ESP32-Lab（自定义 UART 服务，可写命令、读状态）
# MQTT：<prefix>/status、/weather、/ack；命令 <prefix>/cmd：on/off/pwm/weather/log
# 运行：上传为 main.py 开机自启

import asyncio
import gc
import json
import machine
import network
import os
import select
import socket
import time
import _thread

import bluetooth
import esp32
import ntptime
import urequests
from neopixel import NeoPixel
from umqtt.simple import MQTTClient

import wifi_config

BROKER = "broker.emqx.io"
WEB_PORT = 80
BLE_ENABLE = False  # BLE 连接会拖垮 WiFi/网页；需要 BLE 时改 True（建议单独会话）
LOG_DIR = "/data"
LOG_PATH = "/data/log.csv"
LOCAL_OFFSET = 8 * 3600
BLE_NAME = "ESP32-Lab"

try:
    PREFIX = open("/lab_id.txt").read().strip()
except OSError:
    PREFIX = "petri/lab-" + os.urandom(3).hex()
    open("/lab_id.txt", "w").write(PREFIX)

STATUS = PREFIX + "/status"
CMD = PREFIX + "/cmd"
ACK = PREFIX + "/ack"
ONLINE = PREFIX + "/online"
WEATHER = PREFIX + "/weather"
# 中国天气网数据镜像（免 key）；杭州 101210101，换城市改这里
WEATHER_URL = "http://t.weather.itboy.net/api/weather/city/101210101"

UUID_SERVICE = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
UUID_RX = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
UUID_TX = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

led = NeoPixel(machine.Pin(48, machine.Pin.OUT), 1)
state = {
    "led": "off",
    "pwm": 0,
    "weather": None,
    "ip": None,
    "ntp": None,
    "ble": False,
    "ble_scan": None,
    "wifi_scan": None,
    "wifi_detail": None,
    "log_rows": 0,
    "mcu_c": None,
    "rssi": None,
    "mqtt": "init",
    "last_pub": None,
    "boot_count": 0,
    "boot_last": None,
}
pending = []
client = None
wlan = None
ble = None
ble_rx = None
ble_tx = None
ble_conn = None
ble_dirty = False
ble_scan_count = 0
ble_scan_best = None
ble_scan_done = False
wifi_scan_req = False
ble_scan_req = False
wdt = None
cmd_lock = _thread.allocate_lock()
boot_key = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)


def show_led():
    if state["led"] == "on":
        led[0] = (0, 64, 0)
    elif state["led"] == "pwm":
        b = max(0, min(64, state["pwm"] * 64 // 1023))
        led[0] = (b, b, b)
    else:
        led[0] = (0, 0, 0)
    led.write()


def fmt_time():
    t = time.localtime(time.time() + LOCAL_OFFSET)
    return "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])


def connect_wifi():
    global wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(wifi_config.SSID, wifi_config.PASSWORD)
        for _ in range(100):
            if wlan.isconnected():
                break
            time.sleep(0.2)
    try:
        wlan.config(pm=0)  # 关闭 WiFi 省电，避免 BLE 共存时掉线
    except Exception:
        pass
    state["ip"] = wlan.ifconfig()[0]
    print("WiFi", wlan.isconnected(), state["ip"])


def ntp_sync():
    try:
        ntptime.host = "ntp.aliyun.com"
        ntptime.settime()
        state["ntp"] = fmt_time()
        print("NTP", state["ntp"])
    except Exception as e:
        state["ntp"] = "fail"
        print("ntp err", e)


def on_msg(topic, msg):
    pending.append(msg)


def fetch_weather():
    try:
        r = urequests.get(WEATHER_URL, timeout=15)
        d = r.json()
        r.close()
        data = d.get("data", {})
        info = d.get("cityInfo", {})
        forecast = (data.get("forecast") or [{}])[0]
        hum = data.get("shidu")
        if hum:
            hum = int(hum.replace("%", ""))
        wendu = data.get("wendu")
        state["weather"] = {
            "city": info.get("city"),
            "temp_c": float(wendu) if wendu not in (None, "") else None,
            "humidity": hum,
            "quality": data.get("quality"),
            "high": forecast.get("high"),
            "low": forecast.get("low"),
            "type": forecast.get("type"),
            "time": d.get("time"),
        }
        return state["weather"]
    except Exception as e:
        print("weather err", e)
        return None


def ensure_log():
    try:
        os.mkdir(LOG_DIR)
    except OSError:
        pass
    try:
        try:
            os.stat(LOG_PATH)
        except OSError:
            with open(LOG_PATH, "w") as f:
                f.write("time,mcu_c,rssi,weather_c,humidity,led,pwm\n")
        with open(LOG_PATH) as f:
            state["log_rows"] = max(0, len(f.readlines()) - 1)
    except OSError as e:
        print("log init err", e)


def log_row():
    try:
        ensure_log()
        w = state.get("weather") or {}
        row = "%s,%s,%s,%s,%s,%s,%s\n" % (
            fmt_time(),
            esp32.mcu_temperature(),
            wlan.status("rssi") if wlan and wlan.isconnected() else "",
            w.get("temp_c", ""),
            w.get("humidity", ""),
            state["led"],
            state["pwm"],
        )
        with open(LOG_PATH, "a") as f:
            f.write(row)
        state["log_rows"] += 1
    except Exception as e:
        print("log err", e)


def read_log(n):
    try:
        with open(LOG_PATH) as f:
            lines = f.read().splitlines()
        return lines[-n:] if n > 0 else lines
    except OSError:
        return []


def apply_command(cmd):
    cmd = cmd.strip().lower()
    cmd_lock.acquire()
    try:
        if cmd == "on":
            state["led"] = "on"
        elif cmd == "off":
            state["led"] = "off"
        elif cmd == "toggle":
            state["led"] = "off" if state["led"] != "off" else "on"
        elif cmd.startswith("pwm"):
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    v = int(parts[1])
                    v = max(0, min(1023, v))
                    state["pwm"] = v
                    state["led"] = "pwm" if v > 0 else "off"
                except ValueError:
                    pass
        elif cmd == "weather":
            fetch_weather()
        elif cmd == "log":
            log_row()
        elif cmd == "wifi_scan":
            global wifi_scan_req
            wifi_scan_req = True
        elif cmd == "ble_scan":
            global ble_scan_req
            ble_scan_req = True
        show_led()
        return {
            "cmd": cmd,
            "led": state["led"],
            "pwm": state["pwm"],
            "weather": state["weather"],
            "log_rows": state["log_rows"],
        }
    finally:
        cmd_lock.release()


def ble_notify(payload):
    if ble and ble_conn is not None:
        try:
            ble.gatts_notify(ble_conn, ble_tx, payload)
        except Exception:
            pass


def ble_start():
    global ble, ble_rx, ble_tx, ble_conn
    ble = bluetooth.BLE()
    ble.active(True)
    ble.config(gap_name=BLE_NAME)
    flags = bluetooth.FLAG_WRITE | getattr(bluetooth, "FLAG_WRITE_NO_RESPONSE", 0)
    service = (
        UUID_SERVICE,
        (
            (UUID_RX, flags),
            (UUID_TX, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY),
        ),
    )
    ((ble_rx, ble_tx),) = ble.gatts_register_services((service,))
    ble.gatts_set_buffer(ble_rx, 64, True)
    ble.gatts_write(ble_tx, b"ready")

    adv = bytearray(b"\x02\x01\x06")
    adv += bytes([len(BLE_NAME) + 1, 0x09]) + BLE_NAME.encode()

    def irq(event, data):
        global ble_conn, ble_dirty, ble_scan_count, ble_scan_best, ble_scan_done
        if event == 1:  # central connected
            ble_conn = data[0]
            state["ble"] = True
        elif event == 2:  # central disconnected
            ble_conn = None
            state["ble"] = False
            try:
                ble.gap_advertise(100000, adv_data=adv)
            except Exception:
                pass
        elif event == 3:  # gatts write
            if data[1] == ble_rx:
                ble_dirty = True
        elif event == 5:  # scan result (只统计，不记录地址)
            ble_scan_count += 1
            rssi = data[3]
            if ble_scan_best is None or rssi > ble_scan_best:
                ble_scan_best = rssi
        elif event == 6:  # scan done
            ble_scan_done = True

    ble.irq(irq)
    ble.gap_advertise(100000, adv_data=adv)
    print("BLE", BLE_NAME)


async def mqtt_connect():
    global client
    c = MQTTClient("esp32-lab-" + os.urandom(3).hex(), BROKER, keepalive=60)
    try:
        c.set_last_will(ONLINE, b"offline", retain=True)
    except Exception:
        pass
    c.set_callback(on_msg)
    c.connect()
    c.subscribe(CMD)
    c.publish(ONLINE, b"online", retain=True)
    client = c
    state["mqtt"] = "connected"
    print("MQTT", BROKER)
    return c


STATUS_KEYS = ("led", "pwm", "weather", "log_rows", "ble")


def status_dict(n=0):
    w = wlan.status("rssi") if wlan and wlan.isconnected() else None
    d = {
        "prefix": PREFIX,
        "ip": state["ip"],
        "ntp": state["ntp"],
        "mqtt": state["mqtt"],
        "last_pub": state["last_pub"],
        "mcu_c": esp32.mcu_temperature(),
        "rssi": w,
        "uptime_s": time.ticks_ms() // 1000,
        "heap_free": gc.mem_free(),
        "reset_cause": machine.reset_cause(),
        "led": state["led"],
        "pwm": state["pwm"],
        "weather": state["weather"],
        "log_rows": state["log_rows"],
        "ble": state["ble"],
        "ble_scan": state["ble_scan"],
        "wifi_scan": state["wifi_scan"],
        "boot": boot_key.value(),
        "boot_count": state["boot_count"],
        "boot_last": state["boot_last"],
        "heartbeat": n,
    }
    state["mcu_c"] = d["mcu_c"]
    state["rssi"] = d["rssi"]
    return d


def mqtt_thread():
    global client
    n = 0
    while True:
        try:
            c = MQTTClient("esp32-lab-" + os.urandom(3).hex(), BROKER, keepalive=60)
            try:
                c.set_last_will(ONLINE, b"offline", retain=True)
            except Exception:
                pass
            c.set_callback(on_msg)
            c.connect()
            c.subscribe(CMD)
            c.publish(ONLINE, b"online", retain=True)
            client = c
            state["mqtt"] = "connected"
            print("MQTT", BROKER)
            while True:
                if c.sock:
                    r, _, _ = select.select([c.sock], [], [], 0)
                    if r:
                        c.check_msg()
                while pending:
                    raw = pending.pop(0)
                    ack = apply_command(raw.decode().strip().lower())
                    c.publish(ACK, json.dumps(ack))
                n += 1
                c.publish(STATUS, json.dumps(status_dict(n)))
                state["mqtt"] = "ok"
                state["last_pub"] = time.ticks_ms() // 1000
                time.sleep(5)
        except Exception as e:
            state["mqtt"] = "err"
            client = None
            print("mqtt thread", e)
            time.sleep(5)


async def publish_status():
    n = 0
    while True:
        n += 1
        data = status_dict(n)
        try:
            client.publish(STATUS, json.dumps(data))
            state["mqtt"] = "ok"
            state["last_pub"] = time.ticks_ms() // 1000
            ble_notify(json.dumps({"mcu_c": data["mcu_c"], "weather": data["weather"], "led": data["led"]}))
        except Exception as e:
            state["mqtt"] = "err"
            print("publish err", e)
            try:
                await mqtt_connect()
            except Exception as e2:
                print("reconnect err", e2)
        await asyncio.sleep(5)


async def weather_task():
    while True:
        fetch_weather()
        await asyncio.sleep(600)


async def logger_task():
    log_row()
    while True:
        await asyncio.sleep(60)
        log_row()


async def wifi_scan_task():
    global wifi_scan_req
    while True:
        if wifi_scan_req:
            wifi_scan_req = False
            try:
                nets = wlan.scan()
                best = max((n[3] for n in nets), default=None)
                details = []
                for n in nets:
                    ssid = n[0]
                    if isinstance(ssid, bytes):
                        try:
                            ssid = ssid.decode("utf-8", "replace")
                        except Exception:
                            ssid = str(ssid)
                    if ssid:
                        details.append({"ssid": ssid, "rssi": n[3]})
                details.sort(key=lambda x: x["rssi"], reverse=True)
                state["wifi_detail"] = details[:12]
                state["wifi_scan"] = {"count": len(nets), "best": best}
            except Exception as e:
                print("wifi scan err", e)
        await asyncio.sleep(0.5)


async def ble_scan_task():
    global ble_scan_req, ble_scan_count, ble_scan_best, ble_scan_done
    while True:
        if ble_scan_req and ble and ble_conn is None:
            ble_scan_req = False
            ble_scan_count = 0
            ble_scan_best = None
            ble_scan_done = False
            try:
                ble.gap_scan(1000, 100000, 30000, False)
            except Exception as e:
                print("ble scan err", e)
            for _ in range(20):
                if ble_scan_done:
                    break
                await asyncio.sleep(0.1)
            state["ble_scan"] = {"count": ble_scan_count, "best": ble_scan_best}
        await asyncio.sleep(0.5)


async def mqtt_health_task():
    while True:
        await asyncio.sleep(15)
        try:
            if client:
                client.ping()
                state["mqtt"] = "ok"
        except Exception as e:
            state["mqtt"] = "err"
            print("mqtt ping err", e)
            try:
                await mqtt_connect()
            except Exception as e2:
                print("mqtt health reconnect err", e2)


async def net_task():
    while True:
        try:
            if not wlan.isconnected():
                connect_wifi()
            else:
                state["ip"] = wlan.ifconfig()[0]
        except Exception as e:
            print("net task err", e)
        await asyncio.sleep(10)


async def wdt_task():
    while True:
        if wdt:
            wdt.feed()
        await asyncio.sleep(10)


async def boot_task():
    last_val = boot_key.value()
    last_edge = 0
    while True:
        val = boot_key.value()
        if last_val == 1 and val == 0:
            now = time.ticks_ms()
            if time.ticks_diff(now, last_edge) > 250:
                last_edge = now
                state["boot_count"] += 1
                state["boot_last"] = fmt_time()
                apply_command("toggle")
                print("boot key", state["boot_count"])
        last_val = val
        await asyncio.sleep(0.02)


async def ble_task():
    global ble_dirty
    while True:
        if ble and ble_dirty:
            ble_dirty = False
            try:
                cmd = ble.gatts_read(ble_rx).decode().strip().lower()
                ack = apply_command(cmd)
                ble_notify(json.dumps(ack))
            except Exception as e:
                print("ble cmd err", e)
        await asyncio.sleep(0.1)


async def command_task():
    global ble_dirty
    while True:
        try:
            if client and client.sock:
                r, _, _ = select.select([client.sock], [], [], 0)
                if r:
                    client.check_msg()
            while pending:
                raw = pending.pop(0)
                cmd = raw.decode().strip().lower()
                ack = apply_command(cmd)
                client.publish(ACK, json.dumps(ack))
                ble_notify(json.dumps(ack))
                print("mqtt cmd", cmd)
            if ble_dirty:
                ble_dirty = False
                try:
                    cmd = ble.gatts_read(ble_rx).decode().strip().lower()
                    ack = apply_command(cmd)
                    ble_notify(json.dumps(ack))
                    print("ble cmd", cmd)
                except Exception as e:
                    print("ble cmd err", e)
        except Exception as e:
            print("cmd err", e)
        await asyncio.sleep(0.2)


async def heartbeat():
    while True:
        await asyncio.sleep(30)
        print("alive_s", time.ticks_ms() // 1000)


HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32-S3 监测站</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#0f172a;color:#e2e8f0}
h1{font-size:20px;margin:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;padding:0 16px}
.card{background:#1e293b;border-radius:10px;padding:12px}
.card b{display:block;font-size:22px;margin-top:6px;color:#38bdf8}
.card small{display:block;color:#94a3b8;font-size:11px;margin-top:4px}
.controls{display:flex;flex-wrap:wrap;gap:8px;padding:16px}
button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:10px 14px;font-size:14px}
input[type=range]{width:180px}
canvas{background:#1e293b;border-radius:10px;margin:0 16px;max-width:calc(100% - 32px)}
table{border-collapse:collapse;width:calc(100% - 32px);margin:12px 16px;font-size:12px}
td,th{border-bottom:1px solid #334155;padding:6px;text-align:left}
a{color:#93c5fd}
</style></head><body>
<h1>ESP32-S3 远程监测站</h1>
<div id="conn" style="margin:0 16px 8px;color:#22c55e;font-size:13px">在线</div>
<div class="grid">
<div class="card">MCU 温度<b id="mcu">--</b></div>
<div class="card">WiFi 信号<b id="rssi">--</b></div>
<div class="card">运行时间<b id="uptime">--</b></div>
<div class="card">可用堆<b id="heap">--</b></div>
<div class="card" onclick="detail('weather')" style="cursor:pointer">天气<b id="weather">--</b><small>点击看详情</small></div>
<div class="card">灯状态<b id="led">--</b></div>
<div class="card">日志行数<b id="logs">--</b></div>
<div class="card" onclick="detail('ble')" style="cursor:pointer">BLE<b id="ble">--</b><small>点击查看</small></div>
<div class="card" onclick="detail('wifi')" style="cursor:pointer">WiFi 邻居<b id="wifiscan">--</b><small>点击扫描</small></div>
<div class="card" onclick="detail('ble')" style="cursor:pointer">BLE 扫描<b id="blescan">--</b><small>点击查看</small></div>
<div class="card">MQTT<b id="mqtt">--</b><small id="mqttinfo"></small></div>
<div class="card">MQTT 主题<b id="prefix" style="font-size:13px">--</b></div>
<div class="card">BOOT 键<b id="boot">--</b><small id="bootinfo"></small></div>
<div class="card">IP<b id="ip">--</b></div>
<div class="card">NTP 时间<b id="ntp">--</b></div>
</div>
<div class="controls">
<button onclick="cmd('on')">开灯</button>
<button onclick="cmd('off')">关灯</button>
<input id="pwm" type="range" min="0" max="1023" value="512">
<button onclick="cmd('pwm&v='+document.getElementById('pwm').value)">应用 PWM</button>
<button onclick="cmd('weather')">抓天气</button>
<button onclick="cmd('wifi_scan')">扫 WiFi</button>
<button onclick="cmd('ble_scan')">扫 BLE</button>
<button onclick="cmd('log')">记录一行</button>
<a href="/download">下载 CSV</a>
</div>
<div id="detail" style="display:none;margin:12px 16px;background:#1e293b;border-radius:10px;padding:12px">
<div style="display:flex;justify-content:space-between;align-items:center">
<b id="dtitle">详情</b><button onclick="document.getElementById('detail').style.display='none'">关闭</button>
</div>
<div id="dbody" style="font-size:13px;margin-top:8px;line-height:1.6"></div>
</div>
<canvas id="chart" width="600" height="160"></canvas>
<table><thead><tr><th>时间</th><th>MCU</th><th>RSSI</th><th>天气</th><th>湿度</th><th>灯</th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
function fmt(v){return v===null||v===undefined?'--':v}
function detail(kind){
  const d=document.getElementById('detail'); d.style.display='block';
  const title=document.getElementById('dtitle'), body=document.getElementById('dbody');
  if(kind==='weather'){
    title.textContent='天气详情';
    fetch('/api/weather').then(r=>r.json()).then(w=>{
      body.textContent='';
      [['城市',w.city],['温度',(w.temp_c===undefined?'--':w.temp_c+' °C')],['湿度',(w.humidity===undefined?'--':w.humidity+' %')],['天气',w.type],['高/低',(w.high||'--')+' / '+(w.low||'--')],['空气',w.quality],['更新时间',w.time]].forEach(([k,v])=>{
        const div=document.createElement('div'); div.textContent=k+'：'+fmt(v); body.appendChild(div);
      });
    });
  } else if(kind==='wifi'){
    title.textContent='WiFi 邻居';
    body.textContent='扫描中（约 2 秒）...';
    cmd('wifi_scan');
    setTimeout(()=>fetch('/api/wifi').then(r=>r.json()).then(list=>{
      body.textContent='';
      if(!list.length){body.textContent='没扫到，再点一次';return}
      title.textContent='WiFi 邻居（'+list.length+' 个）';
      list.forEach(x=>{const div=document.createElement('div');div.textContent=x.ssid+' — '+x.rssi+' dBm';body.appendChild(div)});
    }),2500);
  } else if(kind==='ble'){
    title.textContent='BLE 扫描';
    fetch('/api/ble').then(r=>r.json()).then(info=>{
      body.textContent='';
      if(!info.enabled){body.textContent='BLE 默认关闭：开启会拖垮 WiFi/网页；需要时把 BLE_ENABLE 改 True';return}
      const s=info.scan||{}; body.textContent='广播 '+(s.count===undefined?'--':s.count)+' 个，最强 '+(s.best===undefined?'--':s.best)+' dBm';
    });
  }
}
async function refresh(){
  try{
    const s=await (await fetch('/api/status')).json();
    document.getElementById('mcu').textContent=fmt(s.mcu_c)+' °C';
    document.getElementById('rssi').textContent=fmt(s.rssi)+' dBm';
    document.getElementById('uptime').textContent=Math.floor(s.uptime_s/60)+' min';
    document.getElementById('heap').textContent=Math.floor(s.heap_free/1024)+' KB';
    document.getElementById('led').textContent=s.led+(s.led==='pwm'?' '+s.pwm:'');
    document.getElementById('logs').textContent=s.log_rows;
    document.getElementById('ble').textContent=s.ble===true?'已连接':(s.ble==='off'?'关闭':(s.ble==='err'?'错误':'广播中'));
    const ws=s.wifi_scan||{}; document.getElementById('wifiscan').textContent=(ws.count===undefined?'--':ws.count+' 个 / '+ws.best+' dBm');
    const bs=s.ble_scan||{}; document.getElementById('blescan').textContent=(bs.count===undefined?'--':bs.count+' 包 / '+bs.best+' dBm');
    document.getElementById('mqtt').textContent=s.mqtt||'--';
    document.getElementById('mqtt').style.color=(s.mqtt==='ok'||s.mqtt==='connected')?'#22c55e':'#f87171';
    document.getElementById('mqttinfo').textContent=s.last_pub!==null?'上报 '+Math.max(0,s.uptime_s-s.last_pub)+'s 前':'';
    document.getElementById('prefix').textContent=s.prefix||'--';
    document.getElementById('boot').textContent=s.boot===0?'按下':'松开';
    document.getElementById('boot').style.color=s.boot===0?'#22c55e':'';
    document.getElementById('bootinfo').textContent='次数 '+s.boot_count+(s.boot_last?' · '+s.boot_last:'');
    document.getElementById('ip').textContent=fmt(s.ip);
    document.getElementById('ntp').textContent=fmt(s.ntp);
    const w=s.weather||{};
    document.getElementById('weather').textContent=(w.temp_c===undefined?'--':w.temp_c+' °C / '+w.humidity+'%'+(w.quality?' / '+w.quality:''));
    const logs=await (await fetch('/api/logs?n=30')).json();
    document.getElementById('rows').innerHTML=logs.slice(1).slice(-8).reverse().map(r=>{const c=r.split(',');return '<tr><td>'+c[0]+'</td><td>'+c[1]+'</td><td>'+c[2]+'</td><td>'+c[3]+'</td><td>'+c[4]+'</td><td>'+c[5]+'</td></tr>'}).join('');
    draw(logs);
    document.getElementById('conn').textContent='在线 · '+new Date().toLocaleTimeString();
    document.getElementById('conn').style.color='#22c55e';
  }catch(e){
    document.getElementById('conn').textContent='连接中断，自动重试中...';
    document.getElementById('conn').style.color='#f87171';
  }
}
function draw(logs){
  const c=document.getElementById('chart'), x=c.getContext('2d');
  x.clearRect(0,0,c.width,c.height);
  const rows=logs.slice(1).map(r=>r.split(','));
  if(rows.length<2)return;
  const mcu=rows.map(r=>parseFloat(r[1]));
  const w=rows.map(r=>parseFloat(r[3]));
  const all=mcu.concat(w).filter(v=>!isNaN(v));
  if(all.length<2)return;
  const min=Math.min(...all), max=Math.max(...all);
  function line(vals,color){
    x.strokeStyle=color; x.beginPath(); let started=false;
    vals.forEach((v,i)=>{
      if(isNaN(v))return;
      const px=10+i*(c.width-20)/(vals.length-1);
      const py=c.height-10-(v-min)/(max-min||1)*(c.height-20);
      if(started)x.lineTo(px,py); else {x.moveTo(px,py);started=true}
    });
    x.stroke();
  }
  line(w,'#38bdf8'); line(mcu,'#f59e0b');
  x.fillStyle='#94a3b8'; x.fillText('MCU(橙) / 天气(蓝)  '+min.toFixed(1)+'~'+max.toFixed(1)+' °C',10,14);
}
function cmd(c){fetch('/api/cmd?c='+encodeURIComponent(c)).then(r=>r.json()).then(refresh)}
setInterval(refresh,3000);refresh();
</script></body></html>"""


def http_response(writer, status, ctype, body, extra=""):
    if isinstance(body, str):
        body = body.encode()
    head = "HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n%s\r\n" % (
        status,
        ctype,
        len(body),
        extra,
    )
    writer.write(head.encode())
    writer.write(body)


async def handle_client(reader, writer):
    try:
        line = await reader.readline()
        if not line:
            return
        parts = line.decode().split()
        if len(parts) < 2:
            return
        # 读空请求头，避免关闭时因未读数据触发 TCP RST（浏览器 fetch 会报 connection reset）
        while True:
            h = await reader.readline()
            if not h or h in (b"\r\n", b"\n"):
                break
        path = parts[1]
        query = ""
        if "?" in path:
            path, query = path.split("?", 1)
        qs = {}
        for kv in query.split("&"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                qs[k] = v
        if path == "/":
            http_response(writer, "200 OK", "text/html; charset=utf-8", HTML)
        elif path == "/api/status":
            http_response(writer, "200 OK", "application/json", json.dumps(status_dict()))
        elif path == "/api/cmd":
            c = qs.get("c", "")
            if c == "pwm" and "v" in qs:
                c = "pwm " + qs["v"]
            ack = apply_command(c)
            http_response(writer, "200 OK", "application/json", json.dumps(ack))
        elif path == "/api/logs":
            n = int(qs.get("n", "30"))
            http_response(writer, "200 OK", "application/json", json.dumps(read_log(n)))
        elif path == "/download":
            body = "\n".join(read_log(0))
            http_response(
                writer,
                "200 OK",
                "text/csv",
                body,
                "Content-Disposition: attachment; filename=log.csv\r\n",
            )
        else:
            http_response(writer, "404 Not Found", "text/plain", "not found")
        await writer.drain()
    except Exception as e:
        print("web err", e)
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def web_task():
    global WEB_PORT
    try:
        server = await asyncio.start_server(handle_client, "0.0.0.0", WEB_PORT)
    except OSError:
        WEB_PORT = 8080
        server = await asyncio.start_server(handle_client, "0.0.0.0", WEB_PORT)
    print("WEB http://%s:%d/" % (state["ip"], WEB_PORT))
    while True:
        await asyncio.sleep(3600)


def web_response(path, query):
    qs = {}
    for kv in query.split("&"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            qs[k] = v
    if path == "/":
        return "200 OK", "text/html; charset=utf-8", HTML, ""
    if path == "/api/status":
        return "200 OK", "application/json", json.dumps(status_dict()), ""
    if path == "/api/cmd":
        c = qs.get("c", "")
        if c == "pwm" and "v" in qs:
            c = "pwm " + qs["v"]
        ack = apply_command(c)
        return "200 OK", "application/json", json.dumps(ack), ""
    if path == "/api/logs":
        try:
            n = int(qs.get("n", "30"))
        except ValueError:
            n = 30
        return "200 OK", "application/json", json.dumps(read_log(n)), ""
    if path == "/api/wifi":
        return "200 OK", "application/json", json.dumps(state["wifi_detail"] or []), ""
    if path == "/api/weather":
        return "200 OK", "application/json", json.dumps(state["weather"] or {}), ""
    if path == "/api/ble":
        return "200 OK", "application/json", json.dumps({"enabled": bool(ble), "scan": state["ble_scan"]}), ""
    if path == "/download":
        body = "\n".join(read_log(0))
        return "200 OK", "text/csv", body, "Content-Disposition: attachment; filename=log.csv\r\n"
    return "404 Not Found", "text/plain", "not found", ""


def web_send(conn, status, ctype, body, extra=""):
    if isinstance(body, str):
        body = body.encode()
    head = "HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n%s\r\n" % (
        status,
        ctype,
        len(body),
        extra,
    )
    conn.sendall(head.encode() + body)


def web_thread():
    global WEB_PORT
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", WEB_PORT))
    except OSError:
        WEB_PORT = 8080
        s.bind(("0.0.0.0", WEB_PORT))
    s.listen(5)
    print("WEB http://%s:%d/" % (state["ip"], WEB_PORT))
    while True:
        conn = None
        try:
            conn, _ = s.accept()
            conn.settimeout(3)
            req = b""
            while b"\r\n\r\n" not in req and len(req) < 2048:
                chunk = conn.recv(512)
                if not chunk:
                    break
                req += chunk
            if not req:
                continue
            line = req.split(b"\r\n", 1)[0].decode()
            parts = line.split()
            if len(parts) < 2:
                continue
            path = parts[1]
            query = ""
            if "?" in path:
                path, query = path.split("?", 1)
            web_send(conn, *web_response(path, query))
        except Exception as e:
            print("web err", e)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


async def main():
    global wdt
    connect_wifi()
    ntp_sync()
    if BLE_ENABLE:
        try:
            ble_start()
        except Exception as e:
            state["ble"] = "err"
            print("ble err", e)
    else:
        state["ble"] = "off"
    ensure_log()
    show_led()
    print("TOPIC", PREFIX)
    try:
        wdt = machine.WDT(timeout=120000)
    except Exception as e:
        wdt = None
        print("wdt err", e)
    _thread.start_new_thread(mqtt_thread, ())
    _thread.start_new_thread(web_thread, ())
    asyncio.create_task(weather_task())
    asyncio.create_task(logger_task())
    asyncio.create_task(wifi_scan_task())
    asyncio.create_task(ble_scan_task())
    asyncio.create_task(net_task())
    asyncio.create_task(boot_task())
    asyncio.create_task(ble_task())
    asyncio.create_task(wdt_task())
    asyncio.create_task(heartbeat())
    while True:
        await asyncio.sleep(1)


while True:
    try:
        asyncio.run(main())
    except Exception as e:
        print("fatal", e)
        time.sleep(5)
