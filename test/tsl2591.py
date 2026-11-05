import time

import adafruit_tsl2591
import board
import busio

import config

_GAIN_OPTIONS = {
    "low": adafruit_tsl2591.GAIN_LOW,
    "medium": adafruit_tsl2591.GAIN_MED,
    "med": adafruit_tsl2591.GAIN_MED,
    "high": adafruit_tsl2591.GAIN_HIGH,
    "max": adafruit_tsl2591.GAIN_MAX,
}

_INTEGRATION_OPTIONS = {
    "100ms": adafruit_tsl2591.INTEGRATIONTIME_100MS,
    "200ms": adafruit_tsl2591.INTEGRATIONTIME_200MS,
    "300ms": adafruit_tsl2591.INTEGRATIONTIME_300MS,
    "400ms": adafruit_tsl2591.INTEGRATIONTIME_400MS,
    "500ms": adafruit_tsl2591.INTEGRATIONTIME_500MS,
    "600ms": adafruit_tsl2591.INTEGRATIONTIME_600MS,
}


def _option(key, default, options):
    value = str(config.get(key, default)).strip().lower()
    if value not in options:
        choices = ", ".join(options)
        raise SystemExit(f"{key}={value!r} is invalid; choose one of: {choices}")
    return options[value]


i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_tsl2591.TSL2591(i2c)
sensor.gain = _option("TSL_GAIN", "low", _GAIN_OPTIONS)
sensor.integration_time = _option(
    "TSL_INTEGRATION_TIME", "100ms", _INTEGRATION_OPTIONS
)

read_interval = config.get_float("READ_INTERVAL_S", 3.0)

try:
    while True:
        broadband = sensor.infrared + sensor.visible
        lux = sensor.lux

        print(f"Lux: {lux:.2f} | Broadband: {broadband} | IR: {sensor.infrared}")
        time.sleep(read_interval)
except KeyboardInterrupt:
    print("\nStopping.")
finally:
    i2c.deinit()
