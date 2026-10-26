# 第 2 课：GPIO 输入 —— 按键与中断

> 目标：掌握输入读取、按键[消抖](词汇表.md#debounce)、[轮询](词汇表.md#polling)与[中断](词汇表.md#interrupt)两种范式，理解 [ISR](词汇表.md#isr)（中断服务函数）的纪律。
> 实验硬件：板载 BOOT 键（GPIO0）+ 板载 LED（GPIO2），**零接线**即可完成全部实验。

---

## 0. 从"说"到"听"

前几课的 GPIO 全是**输出**（我们主动给电平，指挥外界）。
这一课学**输入**：让程序"听"外界信号 —— 读电平、响应按键。

输出是"说"，输入是"听"，听比说难：**现实世界的信号又脏又抖**。

---

## 1. 最简单的读法：轮询（Polling）

轮询 = 主循环里不停地问："按了吗？按了吗？"

```python
import machine, time

led = machine.Pin(2, machine.Pin.OUT)
btn = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)  # BOOT 键，启用内部上拉

while True:
    if btn.value() == 0:          # 低电平有效：按下 = 0
        led.value(not led.value())  # 翻转 LED
    time.sleep(0.05)
```

> 回顾第 1 课上拉电路：松开时引脚被内部 ~45kΩ 电阻拉到 3.3V 读 1；按下直通 GND 读 0。

跑一下会发现**大问题**：轻轻按一下，LED 乱翻好几次，有时亮有时灭，像坏了。
这不是玄学，是下一个坑。

---

## 2. 坑一：机械抖动（Bounce）

按键内部是两片金属触点。按下瞬间，触点会**弹跳** —— 在几毫秒内（典型 5~20ms）反复接触、断开、接触，才稳定贴合。

```
理想信号：  ──────┐                     （一次干净的 1→0）
                  └──────────────────

现实信号：  ──────┐ ┌─┐ ┌──┐
                  └─┘ └─┘  └──────────── （抖！10ms 内跳了好几次）
```

主循环每 50ms 问一次，正好把抖动期间的好几次"按下"都逮住了 → LED 乱翻。

### 软件消抖（两种）

**法一：确认法** —— 发现按下后等 20ms 再读一次，还是 0 才算真按下：

```python
if btn.value() == 0:
    time.sleep(0.02)              # 跨过抖动期
    if btn.value() == 0:          # 仍为 0 → 真按下
        led.value(not led.value())
        while btn.value() == 0:   # 死等松手，防止一次长按翻 N 次
            time.sleep(0.01)
```

**法二：节流法（中断里用）** —— 记录上次触发时间，200ms 内的再次触发直接忽略。

> 也有硬件消抖（0.1μF 电容并联按键），学习阶段软件消抖够用。

---

## 3. 坑二：轮询霸占 CPU

轮询的死穴：`while True` 里必须一直问，**一走神就漏**。

```python
while True:
    if btn.value() == 0: ...   # 必须不停问
    # 想同时起网页服务？accept() 一阻塞就没人问按键了
    # 想省电休眠？睡下去按键就聋了
```

上一课的 `main.py` 网页服务就是死循环 —— 它跑着的时候，轮询代码根本没机会执行。
**轮询和阻塞式服务天生打架**，解药就是中断。

---

## 4. 中断（Interrupt）：从"我不停地问"到"它主动喊我"

中断 = 提前把回调函数登记给硬件："**这个脚的电平一变，立刻放下手里的事来执行我**"。

```python
import machine, time

led = machine.Pin(2, machine.Pin.OUT)
btn = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)

last_press = 0

def on_press(pin):                       # 中断服务函数（ISR）
    global last_press
    now = time.ticks_ms()
    if time.ticks_diff(now, last_press) < 200:   # 节流消抖
        return
    last_press = now
    led.value(not led.value())           # 只做这一件事

btn.irq(trigger=machine.Pin.IRQ_FALLING, handler=on_press)

# 主程序爱干嘛干嘛，按键再也不会漏
while True:
    time.sleep(1)     # 甚至可以是你的网页服务、传感器轮询……
```

- `IRQ_FALLING`：下降沿触发（1→0 的瞬间）。对应还有 `IRQ_RISING`（0→1）、`IRQ_RISING | IRQ_FALLING`（双边沿）
- **魔法时刻**：就算主程序阻塞在网页服务的 `accept()` 里一动不动，按键按下的一瞬间 ISR 照样执行 —— 这就是中断碾压轮询的地方

### ISR 三条纪律（MicroPython 硬性限制）

1. **越短越好** —— 中断是"插队"，干得越久，主程序和别的中断饿得越久
2. **禁止分配内存** —— 函数里不能新建 list/dict/字符串拼接等对象，否则可能直接崩溃重启（中断上下文里内存分配不安全）
3. **别用 print()、sleep()、网络操作** —— print 在某些固件上会卡死，sleep 违反第 1 条

正确姿势：ISR 里只改个全局变量/翻个灯，复杂逻辑留给主循环。需要传数据时用 `machine.Schedule` 风格的队列思路（进阶，先记概念）。

> 用 `ticks_ms()` / `ticks_diff()` 而不是 `time.time()`：前者是毫秒计数器，专门为 ISR 设计（不会分配对象、自动处理回绕）。

---

## 5. 进阶：长按 / 短按识别

利用"松手时刻 - 按下时刻"的时长分流：

```python
def wait_click():
    while btn.value() == 1:          # 等按下
        time.sleep(0.01)
    t0 = time.ticks_ms()
    while btn.value() == 0:          # 等松手
        time.sleep(0.01)
    return time.ticks_diff(time.ticks_ms(), t0)

held = wait_click()
if held >= 1000:
    print("长按（≥1秒）")     # 比如：进入配网模式
else:
    print("短按")             # 比如：翻转灯
```

长按/短按是最常用的"一个键两种功能"方案，智能设备的配网（长按 5 秒）全是这个套路。

---

## 6. 实战项目：按键 + 网页 双通道控制同一盏灯（板子回来后做）

把中断加进 `main.py`，让**物理按键和网页按钮同时控制板载 LED**：

```python
# 在 main.py 的 connect_wifi() 之前加入：
led = machine.Pin(2, machine.Pin.OUT)
btn = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
last_press = 0

def on_press(pin):
    global last_press
    now = time.ticks_ms()
    if time.ticks_diff(now, last_press) < 200:
        return
    last_press = now
    led.value(not led.value())     # 网页服务阻塞着也不耽误按键生效

btn.irq(trigger=machine.Pin.IRQ_FALLING, handler=on_press)
# LED 变量名要与后面 serve() 用的一致；页面刷新会显示最新状态
```

**验收标准**：网页开着不动，按 BOOT 键 → LED 立刻翻转；刷新网页 → 显示的"当前状态"也跟着变了。
两条控制通道共存，这就是中断的价值。

---

## 课后题

1. 为什么内部上拉接法下，判断"按下"要写 `btn.value() == 0` 而不是 `== 1`？
2. 消抖用 20ms 这个数字，取 2ms 或 2000ms 分别会出什么问题？
3. 在 ISR 里写 `print("pressed")` 和 `btn_state = []`（新建空列表），各违反哪条纪律、各有什么后果？

---

## 参考答案（先自己做完再看！）

<details>
<summary>点开查看答案</summary>

1. 上拉电路松开 = 引脚经 45kΩ 连 3.3V = 高电平 1；按下 = 直通 GND = 低电平 0。低电平有效设计换来了"不需要外接任何元件"（内部上拉 + 按键到 GND 一根线就够）。
2. **2ms**：还没跨过触点弹跳期（5~20ms），抖动被当成多次按下，消抖失败。**2000ms**：正常的快速连按（如连按切换）会被吞掉，手感变得"迟钝"，2 秒内只认第一次。20ms 是"略大于最坏抖动时间"的经验值。
3. `print()` 违反"别做慢操作"：print 走 UART 可能阻塞，中断里一阻塞，主程序和整个系统跟着卡死（部分固件直接崩溃）。`btn_state = []` 违反"禁止分配内存"：MicroPython 在中断上下文里执行内存分配可能触发 FatalError 直接重启板子。合法写法是 ISR 里只翻转已有的全局变量/已创建的对象。

</details>

---

<em>课程笔记归档 · 2026-10-22*
