# 硬件配置

## 主控板

- **现用板：ESP32-S3 开发板（N16R8，双 Type-C 焊接板）**
  - 模组 ESP32-S3-WROOM-1-N16R8：16MB Flash + 8MB Octal PSRAM
  - 芯片 ESP32-S3 rev v0.2（QFN56），双核 240MHz
  - USB：两个 Type-C —— 原生 USB-Serial/JTAG（VID 303A，GPIO19/20）+ CH343P USB-UART（GPIO43/44）；刷机/REPL 用原生口
  - 板载：WS2812 RGB（GPIO48，1 颗）、BOOT 键（GPIO0）、RST 键、电源灯（常亮不可控）、TX/RX 指示灯（GPIO43/44）
  - 板载可感知：MCU 温度、WiFi RSSI/邻居扫描、BLE 广播扫描、BOOT 键状态；**没有**环境温湿度/光照/PIR/IMU 传感器
  - Flash 实测 16MB（XMC，RDID `20 70 18`）；文件系统约 14MB；PSRAM 8MB（gc 可用约 8MB）
  - 局域网 IP：**192.168.0.100**（DHCP，可能变化；网页/MQTT 以板子自报为准）
  - **出厂资料以 `ESP32-S3开发板N16R8焊接/` 为准**（原理图 `ESP32-S3-SCH.pdf`、例程、固件、下载工具）
- **串口端口号不固定**（已出现过 COM9→COM10），以设备管理器或下面命令为准：

  ```powershell
  powershell -NoProfile -Command "[System.IO.Ports.SerialPort]::GetPortNames()"
  ```

  - 正常运行（MicroPython）：设备名 `USB 设备 (COMx)`，PID_4001
  - 下载模式（刷机）：设备名 `USB 串行设备 (COMx)`，PID_1001
  - **运行中的 MicroPython 会占用 USB，esptool 连不上**：刷机前先按住 BOOT 再点 RST，或在 REPL 执行 `import machine; machine.bootloader()`
  - 端口报"被其他程序占用"时：用 `pnputil /disable-device` + `/enable-device` 强制重新枚举（实例 ID 以设备管理器为准），仍不行再物理拔插（见 `00-课程总览.md` 踩坑表 10-27）
- 固件：MicroPython v1.29.0 `ESP32_GENERIC_S3-SPIRAM_OCT` + XMC 启动补丁
  - 已打补丁镜像：`firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260824-v1.29.0-xmc207018.bin`
  - 补丁脚本：`firmware/patch_xmc_207018.py`（换 MicroPython 版本后需重新打，原因见 `00-课程总览.md` 踩坑表 10-27）
- 旧板已判废：ESP32 DevKit（ESP32-D0WD-V3 / 4MB / CP2102 / COM7），10-26 短路烧坏板载 3.3V LDO，仅作对照，不再使用

## 套件概览（进阶版 36 项）

完整清单以 `esp32-course/配件清单.md` 为准，速览：

- **显示**：0.96" OLED（I2C, SSD1306）、LCD1602、240×240 TFT（SPI, ST7789）、共阴数码管 4位+1位、LED 灯板（800×800，型号待到货确认）
- **传感器**：双轴摇杆、4×4 矩阵键盘、光敏（AO+DO）、LM35 温度（模拟）、声音、HC-SR04 超声波（宽电压版）、HC-SR501 人体红外、SW-420 震动、SW-520D 倾斜、干簧管、3144 霍尔、红外遥控+接收头
- **执行**：继电器模块、MG90S 舵机、步进电机+ULN2003 驱动板、无源蜂鸣器（PWM 音调）、有源蜂鸣器（数字）、MAX98357 I2S 功放（**套件未配喇叭，需另购 4-8Ω**）
- **耗材**：830 孔面包板、杜邦线 120 根（公公/母母/公母各 40）、电阻包 600 只、LED 200 只、30P 扩展板、四芯屏蔽线

## 安全红线（指导任何接线前必须核对）

> 本板是 ESP32-S3。**旧讲义里按经典 ESP32 写的引脚示例不能直接照抄**，尤其 GPIO26-39 的用法完全不同。

1. **GPIO 是信号不是电源**：LED、数码管每段必串 ≥220Ω 电阻。历史事故：10-22 数码管未限流，3.3V 被拉垮触发 Brownout，最终烧坏旧板 LDO
2. **避开 GPIO26-32**：接内部 SPI Flash，碰了直接死机
3. **避开 GPIO33-37**：本板 8MB Octal PSRAM 占用
4. **避开 GPIO19/20**：原生 USB D-/D+，外接会掉 USB/REPL
5. **避开 GPIO43/44**：UART0 默认串口（REPL 走 USB，但刷机与底层日志仍可能占用）
6. **Strapping 引脚 GPIO0/3/45/46**：上电瞬间决定启动模式，别外接强上/下拉；GPIO0 低电平进下载模式
7. **ADC2 与 WiFi 冲突**：GPIO11-20 属 ADC2，WiFi 开启后读不了；联网项目的模拟量（摇杆、光敏、LM35、声音）优先用 ADC1（GPIO1-10）
8. **5V/3.3V 兼容**：模块先看是否宽电压。HC-SR04 为宽电压版（3-5.5V）可 3.3V 直连；继电器/舵机/步进电机逻辑脚可 3.3V 控制，但电源脚接 5V（VIN）
9. **断电接线**：接线、改线前先断 USB 电；上电前自查正负极和短路

数字 IO 的稳妥选择：GPIO4-18（避开 19/20）；模拟量用 GPIO1-10。最终以板子丝印为准。

## S3 课程引脚分配（2026-10-27 适配）

> 同一时刻只做一个实验；不同实验可以复用同一引脚，但不要把两个外设同时接到同一脚。

| 用途 | 引脚 | 备注 |
|---|---|---|
| 板载 WS2812 | GPIO48 | 出厂固定，1 颗，`neopixel` 驱动 |
| 板载 BOOT 键 | GPIO0 | 上电勿拉低，运行时可当按键 |
| 外接 LED | GPIO4 | 串 ≥220Ω 到 GND |
| 外接按键 | GPIO5 | 内部上拉，按下接 GND |
| 光敏 AO | GPIO1 | ADC1 |
| 摇杆 VRx / VRy / SW | GPIO2 / GPIO4 / GPIO5 | ADC1 + 数字（与 LED/按键实验复用） |
| LM35 | GPIO6 | ADC1 |
| 声音 AO | GPIO7 | ADC1 |
| 舵机信号 | GPIO8 | 5V 电源，3.3V 信号 |
| 无源蜂鸣器 | GPIO9 | PWM |
| 步进 IN1-4 | GPIO10/11/12/13 | ULN2003，5V 电源 |
| UART2 TX/RX | GPIO17/16 | 回环/外设 |
| I2C SDA/SCL | GPIO8/9 | OLED 等 |
| SPI SCK/MOSI/CS/DC/RST | GPIO12/11/5/2/4 | ST7789 |
| 矩阵键盘 行/列 | 13/14/15/16；17/18/21/38 | 8 根 |
| 数码管 a-g/dp | 4/5/6/7/15/16/17/18 | 每段串 220Ω+ |

## 引脚速记（随课程使用持续补充）

- 板载 WS2812 RGB：**GPIO48**（出厂原理图与例程 `main.py` / `test-main.py` 一致，1 颗）
- BOOT 键：**GPIO0**（上电瞬间拉低进下载模式；运行后可当普通按键，出厂例程 `test-main.py` 用它做中断）
- TX/RX 指示灯：GPIO43/44（串口收发时闪烁）；电源灯常亮、不可编程
- 触摸 T1-T14 = GPIO1-14
- 数码管接线（seg.py）：a4 b5 c6 d7 e15 f16 g17 dp18（S3 安全脚），每段串 220Ω+；段码表按共阳编写，套件共阴需 0/1 取反
- seg.py 段码表按共阳极编写，套件数码管是**共阴**，0/1 需全部取反
