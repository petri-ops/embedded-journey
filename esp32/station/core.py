import asyncio
import machine
import network
import os
import time
import _thread

import esp32
import wifi_config

from .config import LOCAL_OFFSET, LOG_DIR, LOG_PATH, TOPIC_FILE
from .features import build_features


def fmt_time():
    t = time.localtime(time.time() + LOCAL_OFFSET)
    return "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])


class Station:
    def __init__(self):
        self.state = {"ip": None, "ntp": None, "mqtt": "init", "last_pub": None}
        self.prefix = self._load_prefix()
        self.lock = _thread.allocate_lock()
        self.wlan = None
        self.features = []
        self.log_rows = 0
        self.wdt = None

    def _load_prefix(self):
        try:
            p = open(TOPIC_FILE).read().strip()
            if p:
                return p
        except OSError:
            pass
        p = "petri/lab-" + os.urandom(3).hex()
        try:
            open(TOPIC_FILE, "w").write(p)
        except OSError:
            pass
        return p

    def connect_wifi(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        if not self.wlan.isconnected():
            self.wlan.connect(wifi_config.SSID, wifi_config.PASSWORD)
            for _ in range(100):
                if self.wlan.isconnected():
                    break
                time.sleep(0.2)
        try:
            self.wlan.config(pm=0)
        except Exception:
            pass
        self.state["ip"] = self.wlan.ifconfig()[0]
        print("WiFi", self.wlan.isconnected(), self.state["ip"])

    def ntp_sync(self):
        try:
            import ntptime

            ntptime.host = "ntp.aliyun.com"
            ntptime.settime()
            self.state["ntp"] = fmt_time()
            print("NTP", self.state["ntp"])
        except Exception as e:
            self.state["ntp"] = "fail"
            print("ntp err", e)

    def ensure_log(self):
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
                self.log_rows = max(0, len(f.readlines()) - 1)
        except OSError as e:
            print("log init err", e)

    def log_row(self):
        try:
            self.ensure_log()
            w = self.feature("weather")
            wd = w.status() if w else {}
            l = self.feature("led")
            ld = l.status() if l else {}
            rssi = self.wlan.status("rssi") if self.wlan and self.wlan.isconnected() else ""
            row = "%s,%s,%s,%s,%s,%s,%s\n" % (
                fmt_time(),
                esp32.mcu_temperature(),
                rssi,
                wd.get("temp_c", ""),
                wd.get("humidity", ""),
                ld.get("led", ""),
                ld.get("pwm", ""),
            )
            with open(LOG_PATH, "a") as f:
                f.write(row)
            self.log_rows += 1
        except Exception as e:
            print("log err", e)

    def read_log(self, n):
        try:
            with open(LOG_PATH) as f:
                lines = f.read().splitlines()
            return lines[-n:] if n > 0 else lines
        except OSError:
            return []

    def init_features(self):
        self.features = build_features(self)
        for f in self.features:
            f.init()

    def feature(self, fid):
        for f in self.features:
            if f.id == fid:
                return f
        return None

    def command(self, fid, action, value=None):
        f = self.feature(fid)
        if not f:
            return {"ok": False, "error": "unknown feature"}
        self.lock.acquire()
        try:
            res = f.command(action, value)
            if not isinstance(res, dict):
                res = {"ok": True}
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        finally:
            self.lock.release()
        res["feature"] = fid
        res["action"] = action
        return res

    def status(self):
        return {
            "station": {
                "prefix": self.prefix,
                "ip": self.state["ip"],
                "ntp": self.state["ntp"],
                "mqtt": self.state["mqtt"],
                "last_pub": self.state["last_pub"],
                "uptime_s": time.ticks_ms() // 1000,
            },
            "features": {f.id: f.status() for f in self.features},
        }

    def features_json(self):
        out = []
        for f in self.features:
            m = f.meta()
            m["status"] = f.status()
            out.append(m)
        return {"station": self.status()["station"], "features": out}

    async def _feature_loops(self):
        for f in self.features:
            if f.has_loop:
                asyncio.create_task(f.loop())

    async def _net_task(self):
        while True:
            try:
                if not self.wlan.isconnected():
                    self.connect_wifi()
                else:
                    self.state["ip"] = self.wlan.ifconfig()[0]
            except Exception as e:
                print("net task err", e)
            await asyncio.sleep(10)

    async def _wdt_task(self):
        while True:
            if self.wdt:
                self.wdt.feed()
            await asyncio.sleep(10)

    async def _heartbeat(self):
        while True:
            await asyncio.sleep(30)
            print("alive_s", time.ticks_ms() // 1000)

    async def _async_main(self):
        try:
            self.wdt = machine.WDT(timeout=120000)
        except Exception as e:
            self.wdt = None
            print("wdt err", e)
        await self._feature_loops()
        asyncio.create_task(self._net_task())
        asyncio.create_task(self._wdt_task())
        asyncio.create_task(self._heartbeat())
        while True:
            await asyncio.sleep(1)

    def run(self):
        self.connect_wifi()
        self.ntp_sync()
        self.init_features()
        self.ensure_log()
        self.log_row()
        print("TOPIC", self.prefix)
        from .web import web_thread
        from .mqtt_link import mqtt_thread

        _thread.start_new_thread(web_thread, (self,))
        _thread.start_new_thread(mqtt_thread, (self,))
        asyncio.run(self._async_main())
