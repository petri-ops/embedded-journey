# 第 3 课：ADC 与 PWM 进阶 —— 模拟量与执行器

> 目标：掌握 [ADC](词汇表.md#adc) 模拟量采集（摇杆/光敏/温度），学会用 [PWM](词汇表.md#pwm) 驱动[舵机](词汇表.md#servo)、[蜂鸣器](词汇表.md#buzzer)、[步进电机](词汇表.md#stepper-motor)，做出"感知→决策→动作"的完整闭环。
> 实验硬件：双轴摇杆、光敏模块、LM35 温度、MG90S 舵机、无源蜂鸣器、步进电机+ULN2003 驱动板。
> 接线红线（S3）：模拟量只能接 **ADC1 引脚（GPIO1~10）**——ADC2（GPIO11~20）开 WiFi 后读不了；S3 没有"只能输入"的 GPIO；避开 GPIO26~37（Flash/PSRAM）与 GPIO19/20（USB）。本课引脚已按 S3 重映射，旧板的 GPIO32~39 方案不再适用。

---

## 0. 从"开/关"到"多少"：模拟世界

前两课的 GPIO 只有两种状态：0 或 1，亮或灭。
但真实世界是连续的：光照有明暗、温度有高低、摇杆有角度。

**ADC（模数转换器）**就是把连续电压翻译成数字的桥：

```
电压 0V ─────────────── 3.3V
         ↓ ADC（12位 = 2¹² = 4096 级）
读数  0 ──────────────── 4095
```

第 1 课埋的伏笔在这里回收：光敏、LM35、摇杆本质全是**分压器**——物理量变化 → 电阻变化 → 电压变化 → ADC 读数变化。

```python
from machine import ADC, Pin

adc = ADC(Pin(1))             # 光敏 AO 接 GPIO1（ADC1）
adc.atten(ADC.ATTN_11DB)      # 量程设为约 0~3.3V（11dB 衰减）

raw = adc.read()              # 0 ~ 4095
volts = raw / 4095 * 3.3      # 换算成电压
print("原始值:", raw, " 电压:", volts, "V")
```

`atten` 是衰减器：引脚电压先被"分压"再测量，量程才够到 3.3V。学习阶段固定用 `ATTN_11DB` 即可。

---

## 1. 实验：光敏 + 摇杆，把环境变成数字

### 接线表（共 3V3 和 GND）

| 器件 | 模块引脚 | ESP32-S3 引脚 |
|---|---|---|
| 光敏（4针） | AO | GPIO1（ADC1） |
| 光敏（4针） | DO | 不接（本课用不上） |
| 摇杆 | VRx | GPIO2（ADC1） |
| 摇杆 | VRy | GPIO4（ADC1） |
| 摇杆 | SW | GPIO5（数字脚，内部上拉） |

```python
import machine, time

light = machine.ADC(machine.Pin(1)); light.atten(machine.ADC.ATTN_11DB)
x = machine.ADC(machine.Pin(2));     x.atten(machine.ADC.ATTN_11DB)
y = machine.ADC(machine.Pin(4));     y.atten(machine.ADC.ATTN_11DB)
sw = machine.Pin(5, machine.Pin.IN, machine.Pin.PULL_UP)

while True:
    print("光: %4d  X: %4d  Y: %4d  按键: %d"
          % (light.read(), x.read(), y.read(), sw.value()))
    time.sleep(0.2)
```

**观察三件事**：
1. 光敏：用手捂住 / 手机手电照射，读数大幅跳变
2. 摇杆：居中时约 2048（正好一半！这就是分压器的中间位），推到两边是 0 / 4095
3. 摇杆按下是 0——又见"低电平有效"（第 2 课内部上拉同款电路）

### LM35 温度（顺手一起接上）

LM35 输出电压 = 温度 × 10mV/°C（25°C 时输出 0.25V）：

```python
t = machine.ADC(machine.Pin(6)); t.atten(machine.ADC.ATTN_11DB)

temp_mv = t.read() / 4095 * 3300      # 换算成毫伏
print("温度约:", temp_mv / 10, "°C")
```

> 注意：诚实声明：LM35 手册标称 4V 起供电，我们用 3.3V 属于"超规但能用"，读数偏低、看趋势够用。正经产品要用其他传感器（如 DS18B20 数字温度传感器，第 4 课后你就能自己接）。

---

## 2. 第一个坑：临界值抖动 → [滞回](词汇表.md#hysteresis)（Hysteresis）

做光控灯最直觉的写法：

```python
if light.read() > 2500:      # 暗 → 开灯
    led.value(1)
else:
    led.value(0)             # 亮 → 关灯
```

跑起来会发现：光照在临界值附近时（比如黄昏），灯**疯狂闪烁**——读数在 2499/2501 之间横跳，和第 2 课按键抖动是同一族问题！

解法是**滞回**：开灯和关灯用**两个不同的阈值**，中间留一段"缓冲带"：

```python
if light.read() > 2500:      # 很暗才开
    led.value(1)
elif light.read() < 1800:    # 相当亮才关
    led.value(0)
    # 1800~2500 之间：保持原状态，不动
```

灯一旦开了，光照要亮到 1800 以下才关；一旦关了，要暗回 2500 以上才开。抖动被缓冲带吸收。
滞回是工业控制的标配思想：空调温控（26°C 制冷、到 24°C 停）、电饭锅保温，全是它。

---

## 3. PWM 驱动执行器：从"说"到"干活"

`pwm.py` 里你已经用过 `duty()` 控制亮度。PWM 的真正威力在**驱动执行器**——不同执行器"听"PWM 的方式不同：

| 执行器 | 听什么 | 关键参数 |
|---|---|---|
| LED | [占空比](词汇表.md#duty-cycle)（duty cycle）= 亮度 | duty 0~1023 |
| 舵机 | 高电平**时长** = 角度 | freq=50，脉宽 0.5~2.5ms |
| 无源蜂鸣器 | **频率** = 音高 | freq=音高，duty=开/关声 |

### 3.1 [舵机](词汇表.md#servo)（Servo）MG90S：PWM 的"时长语言"

舵机内有个小电路：把 50Hz 信号里高电平的**持续时间**翻译成角度：

```
周期 20ms（freq=50）
高电平 0.5ms → 0°      高电平 1.5ms → 90°      高电平 2.5ms → 180°
```

换算成 duty（10 位，1023 ≈ 20ms）：0.5ms ≈ **26**，2.5ms ≈ **128**。

**接线**：舵机棕线→GND，红线→**VIN（5V）**，橙线（信号）→GPIO8。
（信号 3.3V 足够；电源必须 5V——舵机是要干活的，功率走 VIN，GPIO 只出信号。第 1 课红线又回扣了。）

```python
from machine import Pin, PWM
import time

servo = PWM(Pin(8), freq=50)

def set_angle(angle):                     # angle: 0~180
    duty = 26 + int(angle / 180 * 102)    # 0°→26, 180°→128
    servo.duty(duty)

while True:
    for a in range(0, 181, 10):           # 0° 扫到 180°
        set_angle(a); time.sleep_ms(100)
    for a in range(180, -1, -10):         # 再扫回来
        set_angle(a); time.sleep_ms(100)
```

### 3.2 [无源蜂鸣器](词汇表.md#buzzer-passive)（Passive Buzzer）：PWM 的"频率语言"

无源蜂鸣器像个小喇叭——你给什么频率它发什么音。**频率=音高，duty=音量开关**：

```python
buzzer = PWM(Pin(9), freq=523, duty=0)    # duty=0 静音

def tone(freq, ms):
    buzzer.freq(freq)
    buzzer.duty(512)                      # 50% 占空比发声
    time.sleep_ms(ms)
    buzzer.duty(0)                        # 静音

# 音符频率表（低八度小星星）
C4,D4,E4,F4,G4,A4,B4,C5 = 262,294,330,349,392,440,494,523

melody = [C4,C4,G4,G4,A4,A4,G4, F4,F4,E4,E4,D4,D4,C4]
beat   = [1,1,1,1,1,1,2,    1,1,1,1,1,1,2]

for n, b in zip(melody, beat):
    tone(n, 400 * b)
    time.sleep_ms(50)                     # 音符间留缝，更清晰
```

（有源蜂鸣器则相反：通电就响固定音，duty 数字脚当开关用，做报警器更省事。）

### 3.3 [步进电机](词汇表.md#stepper-motor)（Stepper Motor）28BYJ-48：不听 PWM，听"节拍"

步进电机靠 4 组线圈按顺序通电，一步一步精确走。[ULN2003 驱动板](词汇表.md#uln2003)接 GPIO10/11/12/13，红线→**VIN(5V)**：

```python
from machine import Pin
import time

IN1, IN2, IN3, IN4 = Pin(10, Pin.OUT), Pin(11, Pin.OUT), Pin(12, Pin.OUT), Pin(13, Pin.OUT)
COILS = (IN1, IN2, IN3, IN4)

# 半步序列：相邻两相交替通电，转得更顺
SEQ = [(1,0,0,0),(1,1,0,0),(0,1,0,0),(0,1,1,0),
       (0,0,1,0),(0,0,1,1),(0,0,0,1),(1,0,0,1)]

def step(n, delay_ms=2):
    for _ in range(n):
        for s in SEQ:
            for i in range(4):
                COILS[i].value(s[i])
            time.sleep_ms(delay_ms)

# 28BYJ-48 减速比 1:64，半步模式一圈约 4096 步（实测约 4076，精确场合要校准）
step(2048)         # 半圈
step(-0)           # 反转让序列倒着放即可：for s in reversed(SEQ)
```

步进电机的价值：**角度可精确控制、可原地保持**——打印机、云台、打印机头全是它。代价是慢、费电。

> 注意：功率提醒：舵机和步进电机都从 VIN 吃 5V。USB 供电下轻载没问题；两个同时满负荷可能电压骤降触发 Brownout（老朋友了）。到时给 VIN 外接独立 5V 电源，**共地**即可。

---

## 4. 小项目：摇杆控制的"扫描雷达云台"

组合本课全部技能：摇杆 X 轴 → 舵机角度，摇杆按下 → 播一声提示音，光敏太暗 → 蜂鸣器报警。

```python
from machine import Pin, PWM, ADC
import time

servo  = PWM(Pin(8), freq=50)
buzzer = PWM(Pin(9), freq=880, duty=0)
x      = ADC(Pin(2)); x.atten(ADC.ATTN_11DB)
light  = ADC(Pin(1)); light.atten(ADC.ATTN_11DB)
sw     = Pin(5, Pin.IN, Pin.PULL_UP)

while True:
    angle = (x.read() / 4095) * 180           # 摇杆值 → 0~180°
    servo.duty(26 + int(angle / 180 * 102))

    if light.read() > 3000:                   # 太暗：短促报警
        buzzer.duty(512); time.sleep_ms(80); buzzer.duty(0)

    if sw.value() == 0:                       # 按下摇杆：确认音
        buzzer.freq(1318); buzzer.duty(512)
        time.sleep_ms(150); buzzer.duty(0); buzzer.freq(880)

    time.sleep_ms(50)
```

**验收**：推动摇杆舵机平滑跟随；按下摇杆"叮"一声；捂住光敏听到连续短鸣。

---

## 课后题

1. 摇杆居中时读数约 2048，为什么正好是 4095 的一半左右？这背后是什么电路结构？
2. 光控灯用单阈值 2500 会闪烁，改成"开 >2500 / 关 <1800"就不闪了。请用"滞回"一词向一个非工程师解释为什么不闪了。
3. 舵机信号脉宽 1.5ms 对应 90°。若程序里 `freq` 误设成 100（周期 10ms），同样发 1.5ms 脉宽，舵机行为会怎样？

## 参考答案（先自己做完再看！）

<details>
<summary>点开查看答案</summary>

1. 摇杆内部是**两个电位器**（分压器）：动触点在电阻中间位置时，上下两段电阻相等，分压比 1:1，输出电压 = 3.3V × 1/2，ADC 读数 ≈ 4095/2。这验证了第 1 课的分压器公式：Vout = Vin × R2/(R1+R2)。
2. 想象走廊声控灯，人来就亮、人走就灭，有人在门口探头探脑就会一闪一闪。滞回相当于规定"进来才算开灯（很暗），走到灯正下方才关（很亮）"，门口徘徊的"半明半暗"不再影响状态——开关动作之间留了缓冲带，临界抖动够不着。
3. 舵机内部按"高电平时长"解码，1.5ms 仍是 90° 的指令，但周期变成 10ms 意味着信号频率翻倍（100Hz）。多数舵机期望 50Hz，频率不对时解码电路可能误判或抖动，常见现象是舵机嗡嗡发热、角度漂移。结论：**脉宽决定角度，频率必须是约定值**——这就是协议。

</details>

---

<em>课程笔记归档 · 2026-10-26*
