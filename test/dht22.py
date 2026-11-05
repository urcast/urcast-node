import time

import adafruit_dht
import board

import config

pin_name = str(config.get("DHT_PIN", "D4")).strip().upper()
pin = getattr(board, pin_name, None)
if pin is None:
    raise SystemExit(f"DHT_PIN={pin_name!r} is not a valid board pin")

read_interval = config.get_float("READ_INTERVAL_S", 3.0)
dht_device = adafruit_dht.DHT22(pin, use_pulseio=False)

try:
    while True:
        try:
            temp = dht_device.temperature
            hum = dht_device.humidity
            print(f"Temp: {temp}C | Humidity: {hum}%")
        except RuntimeError as error:
            print(f"Read error: {error.args[0]}")
        time.sleep(read_interval)
except KeyboardInterrupt:
    print("\nStopping.")
finally:
    dht_device.exit()
