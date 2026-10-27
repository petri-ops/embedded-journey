from .system import SystemFeature
from .led import LedFeature
from .boot import BootFeature
from .network import NetworkFeature
from .weather import WeatherFeature
from .log import LogFeature


def build_features(app):
    return [
        SystemFeature(app),
        LedFeature(app),
        BootFeature(app),
        NetworkFeature(app),
        WeatherFeature(app),
        LogFeature(app),
    ]
