import json
import os
import select
import time

from umqtt.simple import MQTTClient

from .config import BROKER


def handle_command(station, raw):
    if raw in ("on", "off"):
        fid, action, value = "led", raw, None
    elif raw.startswith("pwm"):
        parts = raw.split()
        fid, action = "led", "pwm"
        value = parts[1] if len(parts) > 1 else None
    else:
        parts = raw.split(":")
        fid = parts[0]
        action = parts[1] if len(parts) > 1 else ""
        value = parts[2] if len(parts) > 2 else None
    return station.command(fid, action, value)


def mqtt_thread(station):
    pending = []

    def on_msg(topic, msg):
        pending.append(msg)

    n = 0
    while True:
        try:
            c = MQTTClient("esp32-lab-" + os.urandom(3).hex(), BROKER, keepalive=60)
            try:
                c.set_last_will(station.prefix + "/online", b"offline", retain=True)
            except Exception:
                pass
            c.set_callback(on_msg)
            c.connect()
            c.subscribe(station.prefix + "/cmd")
            c.publish(station.prefix + "/online", b"online", retain=True)
            station.state["mqtt"] = "connected"
            print("MQTT", BROKER)
            while True:
                if c.sock:
                    r, _, _ = select.select([c.sock], [], [], 0)
                    if r:
                        c.check_msg()
                while pending:
                    raw = pending.pop(0).decode().strip()
                    res = handle_command(station, raw)
                    c.publish(station.prefix + "/ack", json.dumps(res))
                n += 1
                c.publish(station.prefix + "/status", json.dumps(station.status()))
                station.state["mqtt"] = "ok"
                station.state["last_pub"] = time.ticks_ms() // 1000
                time.sleep(5)
        except Exception as e:
            station.state["mqtt"] = "err"
            print("mqtt thread", e)
            time.sleep(5)
