# 第 4 课：通信协议 —— UART / I2C / SPI

> 目标：理解三种芯片间"对话"协议的原理与分工，能把 OLED、彩屏、矩阵键盘接上跑通，掌握"拿到任何陌生模块都能接"的方法论。
> 实验硬件：OLED 0.96"（SSD1306）、240×240 彩屏（ST7789）、矩阵键盘 4×4、一根杜邦线（UART 回环实验）。

---

## 0. 为什么需要总线：引脚不够用了

GPIO 的"说和听"一次只够跟一个器件交流——第 3 课的数码管就吃掉了 8 个引脚。
如果一个项目要接：屏幕 + 温度传感器 + 按键阵 + 时钟芯片……GPIO 立刻破产。

**总线（Bus）**的思路：把多个器件挂到同一组线上，靠**协议**（谁先说、说什么、说给谁）协调通话。

三种总线，一句话分工：

| 协议 | 线数 | 速度 | 一句话定位 |
|---|---|---|---|
| UART | 2（TX/RX） | 慢 | 点对点私聊（两台设备） |
| I2C | 2（SDA/SCL） | 中 | 一根线挂一串小器件（靠地址点名） |
| SPI | 4+（MOSI/MISO/SCK/CS） | 快 | 高速专线（彩屏、SD 卡） |

---

## 1. UART：点对点私聊（10 分钟速通）

UART 你早已概念通关（串口问答那课）：TX 发、RX 收，两端约定**波特率**（每秒位数）。

**实验：自发自收（回环）**——用一根杜邦线把 GPIO17（TX2）和 GPIO16（RX2）短接，让板子跟自己聊天：

```python
from machine import UART

uart = UART(2, baudrate=115200, tx=17, rx=16)   # UART2；UART0 被 REPL 占用，别碰

uart.write("hello bus!")          # 从 TX 发出去
data = uart.read(128)             # 从 RX 收回来（自己发给自己的）
print("收到:", data)
```

> 回顾红线：GPIO1/3 是 UART0，被 REPL/刷机占用，所以实验用 UART2（任意空闲 GPIO 都能当 TX2/RX2）。
> UART 的典型实战：GPS 模块、另一个单片机、串口屏——都是"整条线路只有你我"的场景。

---

## 2. I2C：一根线上的一串器件（本课主菜）

### 原理：地址 + 时钟

I2C 只要两根线，却能挂几十个器件：

- **SDA**（数据线）：实际内容
- **SCL**（时钟线）：节奏线——主机（ESP32）拨一下时钟，大家同步走一步

每个从器件出厂自带一个 **7 位地址**（如 OLED 的 0x3C）。主机想跟谁说话，先在总线上喊地址，应答者回应，其余装聋。

```
ESP32(主机)
  │SDA ──┬─────────┬─────────┐
  │SCL ──┼────┬────┼────┬────┼───┐
         │    │    │    │    │
      OLED 0x3C  传感器0x48  时钟0x68 ...
```

### 魔法时刻：扫描总线

```python
from machine import Pin, SoftI2C

i2c = SoftI2C(sda=Pin(21), scl=Pin(22), freq=400000)
print("总线上的设备地址:", [hex(a) for a in i2c.scan()])
```

接好 OLED 运行，会打印 `['0x3c']`——你没用任何 OLED 代码，板子已经"看见"它了。
这就是 I2C 的哲学：**协议层先通，应用层再说**。以后接任何 I2C 模块，第一件事永远是 `scan()`。

### OLED 显示实战

OLED 需要 SSD1306 驱动库（MicroPython 不内置）。板子联网后一条命令在线安装：

```python
# 先连上 WiFi（复用我们的配置文件），然后：
import mip
mip.install("ssd1306")
```

**接线**：OLED 的 VCC→3V3，GND→GND，SCL→GPIO22，SDA→GPIO21（正好是 scan 用的两根）。

```python
from machine import Pin, SoftI2C, ADC
from ssd1306 import SSD1306_I2C
import time

i2c = SoftI2C(sda=Pin(21), scl=Pin(22))
oled = SSD1306_I2C(128, 64, i2c)        # 128×64 像素

light = ADC(Pin(34)); light.atten(ADC.ATTN_11DB)

while True:
    oled.fill(0)                        # 清屏
    oled.text("embedded-journey", 0, 0)
    oled.text("Lesson 04", 0, 16)
    oled.text("light: %d" % light.read(), 0, 32)
    oled.show()                         # 刷新到屏幕（没有这行不显示！）
    time.sleep(0.5)
```

第 3 课的光敏读数上了屏——`fill→text→show` 三板斧就是 OLED 的全部日常。

---

## 3. SPI：高速公路（彩屏为什么不用 I2C）

I2C 每个时钟搬一位、还要地址应答，跑彩色屏幕（240×240×16位色 ≈ 每帧 112KB）太慢。
SPI 用**更多线换更快速度**：时钟线 SCK 打拍，MOSI 主出从入（MISO 主入从出）并行铺数据，每挂一个器件多用一根 CS 片选线（"CS 拉低 = 现在轮到你"）。

**ST7789 彩屏接线**：

| 屏引脚 | ESP32 | 说明 |
|---|---|---|
| VCC | 3V3 | |
| GND | GND | |
| SCL | GPIO18 | SPI 时钟 |
| SDA | GPIO23 | SPI 数据（MOSI） |
| RES | GPIO4 | 复位 |
| DC | GPIO2 | 数据/命令选择 |
| CS | GPIO5 | 片选 |
| BLK | 3V3 | 背光常开 |

驱动用 `st7789py` 纯 Python 库（GitHub 搜 russhughes/st7789py，下载 st7789py.py 放进板子）：

```python
from machine import Pin, SPI
import st7789py as st7789

spi = SPI(2, baudrate=40000000, polarity=1, sck=Pin(18), mosi=Pin(23))
lcd = st7789.ST7789(spi, 240, 240, cs=Pin(5), dc=Pin(2), rst=Pin(4))

lcd.fill(st7789.color565(90, 125, 238))          # 蓝色洗屏
lcd.text("Hello, Product World!", 20, 110, st7789.color565(255, 255, 255))
```

> 学习重点不是背 API，而是理解分工：**SPI 管快跑，I2C 管省线，库负责寄存器细节**。驱动库读的正是数据手册里的命令表——工业级产品工程师的日常就是读手册写这些。

---

## 4. 矩阵键盘：GPIO 扫描的组合拳（不用总线，胜似总线）

16 个键只用 8 个 GPIO——行 4 + 列 4 交叉排列，每个键坐在一个交点上：

```python
from machine import Pin
import time

ROWS = [Pin(p, Pin.OUT) for p in (13, 14, 27, 26)]   # 行：输出
COLS = [Pin(p, Pin.IN, Pin.PULL_UP) for p in (25, 33, 32, 4)]  # 列：输入上拉

KEYS = [["1","2","3","A"],
        ["4","5","6","B"],
        ["7","8","9","C"],
        ["*","0","#","D"]]

def scan_key():
    for r, row in enumerate(ROWS):
        row.value(0)                       # 逐行拉低
        for c, col in enumerate(COLS):
            if col.value() == 0:           # 该列也变低 → 交点键按下
                row.value(1)
                return KEYS[r][c]          # 行列坐标 → 键名
        row.value(1)
    return None

while True:
    k = scan_key()
    if k:
        print("按下:", k)
        time.sleep(0.25)                   # 粗消抖（第 2 课技能）
```

原理：某行拉低 + 某列读到低 → 唯一锁定一个交点。**行列扫描 = 用时间换引脚**，老式手机键盘、洗衣机面板全是它。

---

## 5. 方法论：拿到任何陌生模块怎么办

四步，屡试不爽：

1. **看引脚名**：VCC/GND 之外，标 SDA/SCL → I2C；标 MOSI/MISO/SCK/CS → SPI；标 TX/RX → UART；标 AO/DO → 模拟/数字输出直连 GPIO
2. **查电压**：模块标 3.3-5.5V 或宽电压 → 直连；只标 5V 的要小心分压（红线第 7 条）
3. **找 MicroPython 库**：mip 有就 `mip.install`；没有就 GitHub 搜"器件名 + micropython"，下载 .py 上传板子
4. **跑最小示例**：I2C 先 `scan()` 确认器件活着，SPI 先 fill 一色，UART 先回环——**先通协议再写应用**

---

## 课后题

1. I2C 的 OLED 和温度传感器都挂 SDA/SCL 两根线上，主机怎么区分该把数据发给谁？
2. 彩屏为什么选 SPI 而不是 I2C？代价是什么？
3. 矩阵键盘行列扫描时，为什么列引脚要配"输入上拉"，而直接接地读会出问题？

## 参考答案（先自己做完再看！）

<details>
<summary>点开查看答案</summary>

1. 每个器件有唯一 7 位地址（OLED 0x3C、常见温度传感器 0x48）。主机每次通信先广播地址，只有地址匹配的器件应答，其余保持沉默。这就是为什么 `i2c.scan()` 能"点名"出总线上所有器件。
2. 彩屏一帧数据量大（240×240×2B ≈ 112KB），SPI 时钟可跑几十 MHz 且点到点专线全速搬数据；I2C 默认 100~400kHz 还要挂地址应答，刷屏会卡成幻灯片。代价是线多（4 根起）、每加一个器件多一根片选线——**速度和引脚数量的交换**，工程里到处是这种取舍。
3. 列引脚不扫描的行都悬空着，若用纯输入（无上拉），读到的是"天线电平"（第 1 课悬空坑），会乱报按键。上拉给列一个确定默认值 1，只有"被按下的键所在行拉低"时才变 0——配合逐行扫描就能唯一确定按键。本质和第 2 课按键上拉完全相同，只是规模化了。

</details>

---

*课程归档于 ZCode 学习实践 · 2026-10-26*
