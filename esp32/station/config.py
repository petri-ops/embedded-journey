# 站点级配置（不放凭据；WiFi 凭据在根目录 wifi_config.py）
BROKER = "broker.emqx.io"
WEB_PORT = 80
STATION_TITLE = "ESP32-S3 控制台"
LOG_DIR = "/data"
LOG_PATH = "/data/log.csv"
TOPIC_FILE = "/lab_id.txt"
LOCAL_OFFSET = 8 * 3600
WEATHER_URL = "http://t.weather.itboy.net/api/weather/city/101210101"
