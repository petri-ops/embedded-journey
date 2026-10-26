# 第 5 课：MQTT 与 asyncio —— 跨上互联网

> 目标：理解 MQTT 发布/订阅模型，让板子与**世界上任何角落**双向通信；掌握 asyncio 并发编程，让"采集、联网、响应"三件事真正同时发生。
> 实验硬件：光敏/温度传感器 + 板载 LED + 电脑或手机浏览器（收发消息用）。

---

## 0. 从"局域网红人"到"互联网公民"

`main.py` 的网页控制有个天花板：**只有同一 WiFi 下的设备能访问**。出差在外想看看家里的灯？没戏。

要跨上互联网，就要回答一个问题：家里的板子（没有公网 IP、随时可能掉线）和你的手机，如何找到彼此？

答案是** broker（消息代理）**模式——双方不直接对话，都只跟一个永不掉线的"邮局"通信。

---

## 1. MQTT：物联网的"邮局 + 报刊订阅"

### 三个角色

```
   发布者                    Broker（邮局）                 订阅者
  (ESP32) ──发布──▶  topic: petri/home/light ──推送──▶  (你的手机)
                      petri/home/temp
                      petri/home/led/cmd
```

- **Publisher** 发布消息到某个**主题（topic）**
- **Subscriber** 订阅感兴趣的主题，有新消息立刻收到
- **Broker** 居中转发，双方互不需要知道对方的存在

topic 用斜线分层，像网址路径：`petri/home/light/state`（谁的/哪个设备/什么量/状态还是命令）。

### 为什么这个设计统治了物联网

1. **发布者和订阅者解耦**——板子不需要知道"谁在看我"，手机也不需要知道"谁在发"，都只认识 broker
2. **天然一对多**——一个温度数据，手机、电脑、服务器可以同时订阅
3. **轻量**——协议头最小 2 字节，拨号上网时代的嵌入式设备都扛得住
4. QoS（消息质量等级）：0 最多发一次（丢就丢）/ 1 至少一次（可能重复）/ 4 恰好一次。传感器上报用 0，控制命令用 1

### 安全提醒（威胁模型回扣！）

我们用公共测试 broker（`broker.emqx.io`），它像广场上的公告栏：**你发的每条消息全世界都能订阅**。
所以：topic 和消息里**不要出现真实姓名、住址、密码**。正经产品会：用私有 broker + 账号密码 + TLS 加密（阶段 2 再学）。

---

## 2. 上手：让板子在互联网上说话

### 第一步：安装库 + 联网

```python
# 板子先连 WiFi（main.py 开机自启，REPL 里确认 wlan.isconnected() 为 True）
import mip
mip.install("umqtt.simple")
```

### 第二步：电脑/手机端准备一个"耳朵"

任选其一：
- 浏览器打开 `https://mqttx.app/zh`（MQTTX 网页客户端）→ 连接 `broker.emqx.io` → 订阅 `petri/#`（`#` 是通配符=所有子主题）
- 或手机装任意 MQTT 调试 App（如 IoT Debugger）

### 第三步：板子发布 + 订阅

```python
from umqtt.simple import MQTTClient
from machine import Pin, ADC
import time

light = ADC(Pin(34)); light.atten(ADC.ATTN_11DB)
led = Pin(2, Pin.OUT)

def on_msg(topic, msg):                       # 收到订阅消息的回调
    print("收到:", topic, msg)
    if msg == b"on":
        led.value(1)
    elif msg == b"off":
        led.value(0)

c = MQTTClient("petri-esp32-01", "broker.emqx.io")   # 客户端ID要全局唯一
c.set_callback(on_msg)
c.connect()
c.subscribe(b"petri/home/led/cmd")            # 订阅"灯控制命令"主题
print("MQTT 已连接")

while True:
    c.publish(b"petri/home/light", str(light.read()))   # 发布光照
    c.check_msg()                             # 非阻塞地检查有没有新命令
    time.sleep(5)
```

**魔法时刻**：
- 你在 MQTTX 里向 `petri/home/led/cmd` 发一条 `on` —— 板子上的灯亮了，**这次没有路由器边界，人在火星也能发**
- MQTTX 的订阅窗口每 5 秒跳出一条光照数据——你家传感器的数据流上了互联网

---

## 3. 坑：单循环的崩溃现场 → asyncio 登场

上面的程序藏着隐患——`time.sleep(5)` 期间命令进不来（最坏等 5 秒灯才响应）。要响应快就把 sleep 缩短？那消息发布又太频繁。

本质矛盾：**采集、收命令、发数据是三件节奏不同的事，单循环只能串行伺候一个**。

`asyncio`（异步并发）是正解：多个任务"同时"跑，谁需要等待（sleep、网络）谁就让出 CPU。

```python
import asyncio
from umqtt.simple import MQTTClient
from machine import Pin, ADC

light = ADC(Pin(34)); light.atten(ADC.ATTN_11DB)
led = Pin(2, Pin.OUT)
client = None

def on_msg(topic, msg):
    if msg == b"on":  led.value(1)
    elif msg == b"off": led.value(0)

async def mqtt_task():                        # 任务1：守着 MQTT
    global client
    client = MQTTClient("petri-esp32-01", "broker.emqx.io")
    client.set_callback(on_msg)
    client.connect()
    client.subscribe(b"petri/home/led/cmd")
    while True:
        client.check_msg()
        await asyncio.sleep(0.1)              # 0.1秒查一次，命令秒达

async def report_task():                      # 任务2：每10秒上报
    while True:
        if client:
            client.publish(b"petri/home/light", str(light.read()))
        await asyncio.sleep(10)

async def heartbeat_task():                   # 任务3：心跳闪烁，证明系统活着
    while True:
        led2 = Pin(2, Pin.OUT)
        await asyncio.sleep(0.5)

async def main():
    asyncio.create_task(mqtt_task())          # 三个任务并发启动
    asyncio.create_task(report_task())
    while True:
        await asyncio.sleep(1)

asyncio.run(main())
```

> 注：心跳任务示例里没动 LED（被 MQTT 占用了）；实战中可接另一个 GPIO 的 LED 或改成打印。要点是看清结构：**async def 定义任务，await 让出 CPU，create_task 并发调度**。
> 这正是 FreeRTOS 任务的 Python 露出的衣角——你第一次问题就问过它！固件底层，每个任务就是一个 FreeRTOS task。

---

## 4. 小项目：跨互联网的环境监控站 v1

整合三课技能，交付一个真正可用的远程监控：

- **采集**：光敏 + LM35 温度（第 3 课）
- **显示**：本地 OLED 实时显示（第 4 课，可选）
- **联网**：MQTT 每 30 秒上报 `petri/home/light` 和 `petri/home/temp`
- **控制**：订阅 `petri/home/led/cmd`，远程开关灯，命令 0.5 秒内响应
- **验收**：用手机流量（不连家里 WiFi！）发 `on`，家中板子灯亮、数据持续刷新

把程序存为 `esp32/monitor.py` 结构（配置读 `wifi_config.py`），开机自动运行——这就是结业项目"桌面气象站"的雏形。

---

## 课后题

1. 为什么 MQTT 要设计 broker 中转，而不是让手机直连板子？
2. `while True: check_msg(); sleep(5)` 的程序，把 sleep 改成 0.1 能不能解决命令延迟？代价是什么？asyncio 怎么两全？
3. 用公共 broker 时，别人如何"偷看"你的数据？说出至少两层防护思路。

## 参考答案（先自己做完再看！）

<details>
<summary>点开查看答案</summary>

1. 家用板子没有公网 IP（运营商 NAT 后面），手机直连板子找不到门牌号；且板子随时掉线重启。broker 是双方都能主动连上的固定中点：板子主动连 broker 报数据，手机主动连 broker 取数据——**把"双向可达"难题转化为两次"单向出站连接"**，这是所有 NAT 穿透类架构的通用智慧。
2. 能降延迟，但代价是主循环被 check_msg 占满，采集/上报节奏没法独立调——所有逻辑被最快的那个需求绑架。asyncio 让每个任务自带节奏（0.1 秒查命令、10 秒报数据），等待时主动让出 CPU，互不干扰。这就是并发与轮询的分野。
3. 第一层：topic 是公开可订阅的，任何人连上 broker 订阅 `#`（全部主题）就能看到你的数据流——所以消息内容要脱敏（不写真名/地址/密码）。第二层：用**私有 broker + 用户名密码认证**，未授权者连不上；第三层：上 TLS 加密，即使截获流量也读不懂；第四层：topic 名本身不用可猜测的规律（加随机串）。安全从来是分层洋葱，没有单点银弹。

</details>

---

*课程归档于 ZCode 学习实践 · 2026-10-26*
