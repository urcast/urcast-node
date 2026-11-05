import time

import adafruit_bitbangio as bitbangio
import adafruit_bmp280
import board

import config


def _board_pin(key, default):
    name = str(config.get(key, default)).strip().upper()
    pin = getattr(board, name, None)
    if pin is None:
        raise SystemExit(f"{key}={name!r} is not a valid board pin")
    return pin


i2c = bitbangio.I2C(
    _board_pin("BMP_SCL_PIN", "D27"),
    _board_pin("BMP_SDA_PIN", "D17"),
)
sensor = adafruit_bmp280.Adafruit_BMP280_I2C(
    i2c, address=config.get_int("BMP280_ADDRESS", 0x76)
)
sensor.sea_level_pressure = config.get_float("BMP_SEA_LEVEL_PRESSURE_HPA", 1013.25)

read_interval = config.get_float("READ_INTERVAL_S", 3.0)

try:
    while True:
        temp = sensor.temperature
        pressure = sensor.pressure
        altitude = sensor.altitude

        print(
            f"Temp: {temp:.2f} °C | Pressure: {pressure:.2f} hPa | Altitude: {altitude:.2f} m"
        )
        time.sleep(read_interval)
except KeyboardInterrupt:
    print("\nStopping.")
finally:
    i2c.deinit()
