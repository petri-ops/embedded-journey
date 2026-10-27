# Station 门户框架

定位：**控制 + 呈现 + 交互**（不是开发平台）。代码/Git/构建留在 PC；站里负责状态、控制、日志和页面。

## 运行结构

```
main.py                 -> station.app.run()
station/core.py         Station：WiFi/NTP/状态/命令/日志/看门狗
station/web.py          HTTP 线程 + 动态页面/API
station/mqtt_link.py    MQTT 线程 + 聚合状态 + 命令路由
station/features/*      功能模块（system/led/boot/network/weather/log）
```

一个 MicroPython 进程内：web 线程、MQTT 线程、asyncio core/feature loops；共享 `Station` 状态，命令经 `Station.command()` 的锁串行化。

## Feature 契约

每个功能一个文件，继承 `features/base.py`：

| 属性/方法 | 作用 |
|---|---|
| `id` / `title` / `order` | 唯一标识、页面标题、排序 |
| `fields` | 详情字段：`[{"key","label","unit"?}]` |
| `card_fields` | 卡片优先展示的字段 key |
| `actions` | 按钮/滑杆：`{"action","label","type":"button"/"range","min","max","value_key","on_card"?,"auto_open"?}`；`on_card:false` 不在卡片显示，`auto_open:true` 打开详情时自动执行（适合刷新/扫描） |
| `list_key` / `list_label` | `status` 中的列表字段（详情页展示，如 WiFi 邻居） |
| `has_loop` + `async def loop()` | 需要后台任务的模块（扫描、天气、按键） |
| `init()` | 初始化硬件/状态 |
| `status()` | 返回字段值（网页/MQTT 自动汇总） |
| `command(action, value)` | 处理控制命令，返回 ack dict |

## 新增一个功能

1. 复制 `features/log.py` 为模板，改 `id/title/order/fields/actions`
2. 在 `features/__init__.py` 的 `build_features()` 里注册
3. 重新上传 `station/` 和 `main.py`
4. 网页卡片、详情、`/api/cmd`、MQTT 命令/状态自动出现

## HTTP API

- `GET /api/features`：所有 feature 的元数据 + 当前状态
- `GET /api/status`：聚合状态
- `GET /api/cmd?feature=led&action=pwm&value=512`：控制
- `GET /api/logs?n=30`、`GET /download`：日志

## MQTT

- 状态：`<prefix>/status`（聚合 JSON）
- 命令：`<prefix>/cmd`，格式 `feature:action[:value]`，如 `led:on`、`led:pwm:512`、`network:scan`、`weather:refresh`、`log:now`
- 兼容旧命令：`on` / `off` / `pwm 512`
- ACK：`<prefix>/ack`

## 部署

```bash
python -m mpremote connect COMx mkdir :station
python -m mpremote connect COMx mkdir :station/features
# 上传 station/*.py 和 station/features/*.py（或 cp -r）
python -m mpremote connect COMx cp esp32/station_main.py :main.py
python -m mpremote connect COMx reset
```

`wifi_config.py` 在板子根目录；`main.py` 由 `station_main.py` 提供。旧版单文件 `remote_station.py` 可作回滚备份。

## 边界

- 这里只做控制/呈现；不做代码编辑、Git、CI
- 未来加继电器/强电前必须先加认证（网页 token/私有 MQTT/TLS）
- BLE GATT 与 WiFi 共存不稳，默认不启用；需要时作为单独 feature 开启
