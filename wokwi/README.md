# Wokwi 仿真（无板练习）

用途：不在板子旁时，用浏览器验证代码逻辑和接线思路。Wokwi 支持 ESP32 全系（含 ESP32-S3）的 MicroPython 仿真。

## 能仿什么

- GPIO 输入输出、按键、LED、NeoPixel、OLED（SSD1306）、SPI 屏、舵机、蜂鸣器、超声波、矩阵键盘等常见件
- WiFi：SSID 填 `Wokwi-GUEST`，密码留空；HTTP/MQTT 走虚拟网关，可连公网 broker
- 串口监视器、逻辑分析仪、断点调试

## 不能仿什么（重要）

- **电气红线**：电流、发热、Brownout、5V 耐压不会报错
- **S3 的 Flash/PSRAM 占用**：仿真里 GPIO26-37 可能"能用"，真板会死机；GPIO22-25 在 S3 上不存在
- **ADC**：读数是固定值，不能用来验证光敏/LM35/摇杆的真实电压变化
- **WiFi 射频、时序精度**：与真板有差异，最终要回板子验证

## 用法

1. 打开 https://wokwi.com，New Project → 选 ESP32 或 ESP32-S3
2. 代码编辑器粘贴 `main.py`；`diagram.json` 面板粘贴对应工程的 JSON
3. 点绿色运行，串口监视器看 print
4. 只用 `hardware.md` 里「S3 课程引脚分配表」的安全脚（GPIO26-37、22-25、19/20、43/44 不要用）

## 目录

- `lesson01_led/`：外接 LED + 220Ω 接 GPIO4，闪烁。用经典 ESP32 板模板，S3 上同样适用（GPIO4 是安全脚）。

> 注：Wokwi 的 MicroPython 固件版本可能低于板上的 v1.29；若 API 不一致，以真板为准。
