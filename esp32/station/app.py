import time

from .core import Station


def run():
    while True:
        try:
            Station().run()
        except Exception as e:
            print("fatal", e)
            time.sleep(5)
