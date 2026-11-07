# urcast Raspberry Pi 5 Weather Node README

> A Python-based telemetry collection and diagnostic script designed for the urcast weather station project running on a Raspberry Pi 5. This script validates hardware communication, independent I2C bus splitting, and continuous raw environmental data acquisition.

---

## About the Weather Node

The **urcast Weather Node** runs locally on a Raspberry Pi 5 deployed inside an outdoor protective enclosure. It simultaneously communicates with three separate environmental sensors using isolated peripheral interfaces—utilizing the Raspberry Pi 5's hardware I2C bus, a software bit-banged I2C bus, and a direct single-wire GPIO connection. Each sensor read is wrapped in fault-tolerant exception handling to guarantee that a glitch or failure in one sensor never interrupts the others.

---

## Key Features and Responsibilities

- **Isolated Multi-Bus Architecture:** Communicates with the TSL2591 light sensor via hardware I2C (Bus 1) and the BMP280 pressure sensor via software bit-banged I2C (`adafruit_bitbangio`) on separate pins, eliminating bus contention and speed interference.
- **Fault-Tolerant Error Handling:** Implements independent `try/except` boundaries around every sensor call, returning `None` on failure so the continuous sampling loop remains active.
- **Raw Telemetry Output:** Captures unadjusted base metrics (`ch0`, `ch1`, `lux`, `temperature`, `humidity`, and absolute station `pressure`), leaving derivative math like altitude, dew point, cloud index, and pressure trends to the backend application.
- **Formatted Terminal Diagnostics:** Prints structured, columnar log lines with UTC ISO timestamps and sequential sample numbering.

---

## Hardware Stack & Wiring Guide

- **Microcontroller:** Raspberry Pi 5

| Sensor | Protocol | GPIO Pins | Physical Connections |
| :--- | :--- | :--- | :--- |
| **TSL2591** (Light) | Hardware I2C (Bus 1) | GPIO 2 (SDA), GPIO 3 (SCL) | VIN $\rightarrow$ Pin 17 (3.3V)<br>GND $\rightarrow$ Pin 6<br>SCL $\rightarrow$ Pin 5<br>SDA $\rightarrow$ Pin 3 |
| **BMP280** (Pressure) | Software I2C (Bitbangio) | GPIO 17 (SDA), GPIO 27 (SCL) | VCC $\rightarrow$ Pin 1 (3.3V)<br>GND $\rightarrow$ Pin 9<br>SCL $\rightarrow$ Pin 13<br>SDA $\rightarrow$ Pin 11 |
| **DHT22** (Temp/Humidity) | Single-Wire Data | GPIO 4 | VCC $\rightarrow$ Pin 4 (5V)<br>DATA $\rightarrow$ Pin 7 *(with pull-up resistor to VCC)*<br>GND $\rightarrow$ Pin 14 |

---

## Data Fields and Backend Processing Strategy

The node focuses strictly on raw data collection to keep edge operations simple and lightweight:

| Sensor | Reported Fields | Calculated / Derived on Backend |
| :--- | :--- | :--- |
| **TSL2591** | `lux`, `ch0` (Full Spectrum), `ch1` (Infrared) | `visible` ($ch0 - ch1$), `broadband` ($ch0$), gain clipping detection |
| **DHT22** | `temperature` (°C), `humidity` (%) | Dew point, dew point spread, air comfort index |
| **BMP280** | `pressure` (hPa absolute) | Relative sea-level pressure, altitude estimation, pressure trend |

---

## Technology Stack

- **Language:** Python 3.10+
- **Peripheral Libraries:** Adafruit CircuitPython (`board`, `busio`, `adafruit_tsl2591`, `adafruit_bmp280`, `adafruit_dht`) from `adafruit-blinka`, plus `adafruit_bitbangio` from `adafruit-circuitpython-bitbangio`
- **GPIO Backend:** `gpiod` / `libgpiod` and `lgpio` (used by Blinka for GPIO on the Raspberry Pi 5)
- **Network Libraries:** `paho-mqtt` (MQTT publishing), `urllib` (REST login, account registration, node creation, and JWT refresh)
- **Runtime Utilities:** `time`, `datetime`, `threading`, `getpass`, `base64`, `json`

---

## Project Architecture

```text
urcast-node/
│
├── .env.example          # Template copied to the git-ignored .env on first run
├── requirements.txt      # Python packages installed with pip
├── test/
│   ├── bmp280.py         # Standalone hardware test script for BMP280 pressure sensor
│   ├── dht22.py          # Standalone hardware test script for DHT22 temp & humidity sensor
│   ├── tsl2591.py        # Standalone hardware test script for TSL2591 light sensor
│   ├── config.py         # Loads and saves the repository-level .env file
│   ├── validation.py     # Shared input validation for setup
│   ├── api_client.py     # REST login, account registration, and node creation
│   ├── token_refresh.py  # Renews the JWT before its 24-hour lifetime ends
│   ├── setup_node.py     # Guided first-run setup and service launcher
│   ├── register_node.py  # Standalone node registration using the saved JWT
│   ├── mqtt_client.py    # MQTT publisher (readings, diagnostics, heartbeat)
│   └── combinedTest.py   # Main entry point executing multi-bus setup, reading loop, and formatted output
└── README.md             # Project documentation
```

---

## Repository Commit History & Test Development

You can inspect the complete evolution of the individual sensor scripts and diagnostic code on GitHub:

- **Repository:** [leonas-stanis/udp-pi-test-code](https://github.com/leonas-stanis/udp-pi-test-code)
- **Commit History:** Track incremental updates, bug fixes, and bus isolation testing across individual commits via the [GitHub Commit Log](https://github.com/leonas-stanis/udp-pi-test-code/commits/main/).


## Getting Started and Installation

### Prerequisites

- A Raspberry Pi 5 running Raspberry Pi OS.
- Physical wiring of the TSL2591, BMP280, and DHT22 modules according to the hardware stack pinout table above.
- I2C enabled, plus the GPIO/libgpiod packages that Adafruit Blinka uses on the Pi 5:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv i2c-tools gpiod libgpiod2 python3-libgpiod python3-lgpio
sudo raspi-config   # Interface Options -> I2C -> Enable
```

### Setup Instructions

1. Clone or download this repository to your Raspberry Pi 5:
```bash
git clone https://github.com/urcast/urcast-node.git
cd urcast-node
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

3. Install the Python dependencies:
```bash
pip install -r requirements.txt
```

`requirements.txt` contains `adafruit-blinka` (provides `board` and `busio`), `adafruit-circuitpython-bitbangio` (provides `adafruit_bitbangio`), the three sensor libraries, `lgpio`, and `paho-mqtt`. The `gpiod` packages above are installed system-wide with `apt` because they are native GPIO bindings, not pure Python packages.

### Import and Package Reference

| Import | Package | Purpose |
| :--- | :--- | :--- |
| `board`, `busio` | `adafruit-blinka` | Raspberry Pi pin names, hardware I2C |
| `adafruit_bitbangio` | `adafruit-circuitpython-bitbangio` | Software I2C for the BMP280 |
| `adafruit_tsl2591` | `adafruit-circuitpython-tsl2591` | Light sensor |
| `adafruit_bmp280` | `adafruit-circuitpython-bmp280` | Pressure sensor |
| `adafruit_dht` | `adafruit-circuitpython-dht` | DHT22 temperature and humidity |
| `paho.mqtt.client` | `paho-mqtt` | MQTT publishing |
| `gpiod`, `lgpio` | `gpiod`, `libgpiod2`, `python3-libgpiod`, `lgpio` | GPIO backend used by Blinka on the Pi 5 |

---

## Quick Start (Recommended)

From the repository root, run:

```bash
python test/setup_node.py
```

The first run:

1. Creates `.env` from `.env.example` if it does not exist.
2. Reuses a valid saved JWT, or asks whether you want to **log in** or **create an account** if the node is not authenticated.
3. Validates the email, username, password, node name, location, and coordinates before sending them to the API.
4. Registers this node unless `NODE_ID` is already set and still belongs to the signed-in account.
5. Writes `JWT_TOKEN`, `AUTH_EMAIL`, `AUTH_PASSWORD`, and `NODE_ID` back to `.env`.
6. Starts the sensor and MQTT service.

The JWT is renewed in the background 5 minutes before it expires (configurable with `TOKEN_REFRESH_MARGIN_S`), so publishing continues past the 24-hour token lifetime without editing any files or restarting the service.

To run setup without starting the sensor loop:

```bash
python test/setup_node.py --setup-only
```

> `.env` stores the account password so the node can log in again and renew its JWT. It is git-ignored and is written with mode `600` on Linux. Keep it private and do not commit it.

---

## Configuration (.env)

All runtime settings live in the repository-level `.env`. `.env.example` documents the defaults; `setup_node.py` writes the authentication and node values for you.

| Key | Default | Purpose |
| :--- | :--- | :--- |
| `API_URL` | `http://localhost:8000` | urcast API base URL |
| `MQTT_BROKER` | `localhost` | Machine running Mosquitto |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC_PREFIX` | `urcast` | Topic prefix |
| `AUTH_EMAIL` | *(empty)* | Account email used to refresh the JWT |
| `AUTH_PASSWORD` | *(empty)* | Account password used to refresh the JWT |
| `JWT_TOKEN` | *(empty)* | Current access token |
| `NODE_ID` | *(empty)* | Node id returned by registration |
| `NODE_NAME` | `pi5-outdoor` | Node name sent during registration |
| `NODE_LOCATION` | *(empty)* | Optional human-readable location |
| `NODE_LATITUDE` | *(empty)* | Optional latitude, -90 to 90 |
| `NODE_LONGITUDE` | *(empty)* | Optional longitude, -180 to 180 |
| `TOKEN_REFRESH_MARGIN_S` | `300` | Refresh the JWT this many seconds before expiry |
| `READ_INTERVAL_S` | `3.0` | Seconds between sensor samples |
| `DHT_PIN` | `D4` | DHT22 data pin |
| `BMP_SDA_PIN` | `D17` | BMP280 software I2C SDA pin |
| `BMP_SCL_PIN` | `D27` | BMP280 software I2C SCL pin |
| `BMP280_ADDRESS` | `0x76` | BMP280 I2C address |
| `BMP_SEA_LEVEL_PRESSURE_HPA` | `1013.25` | Reference pressure for the standalone BMP280 altitude test |
| `TSL_GAIN` | `low` | `low`, `medium`, `high`, or `max` |
| `TSL_INTEGRATION_TIME` | `100ms` | `100ms` through `600ms` |

---

## Running and Testing

To execute the data collection loop and monitor sensor readings directly in your terminal (after `.env` is configured):

```bash
cd test
python combinedTest.py
```

Press `Ctrl+C` at any time to safely terminate the execution loop and release hardware interfaces.

---

## Connecting to the urcast API

`setup_node.py` handles the normal path. The node talks to the backend over two transports:

- **HTTPS REST** is used for login, account creation, node registration, and JWT refresh.
- **MQTT** carries every reading, diagnostic, and heartbeat. The broker accepts anonymous connections, but the backend reads the JWT from a `token` field inside each payload and drops anything with a missing, expired, or mismatched token.

A node can only be created by a logged-in user. `setup_node.py` performs that flow and stores the results in `.env`.

### 1. Authentication (handled by setup_node.py)

Run:

```bash
python test/setup_node.py
```

If the saved JWT is still valid, setup reuses it. Otherwise it asks:

```text
This node is not signed in.
  1) Log in with an existing urcast account
  2) Create a new account
```

Registration enforces the API's rules locally: usernames are 3-100 characters, emails must be valid, passwords are 8-72 characters, and the password is entered twice. Login and registration errors are shown with the API's detail message, and an incorrect password re-prompts instead of writing a bad token.

The manual API calls remain available for debugging. Create an account:

```bash
curl -X POST http://<api-host>:8000/api/user \
  -H "Content-Type: application/json" \
  -d '{"username": "pijus", "email": "pijus@example.com", "password": "S3curePass!"}'
```

Log in and copy the `access_token` from the response:

```bash
curl -X POST http://<api-host>:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "pijus@example.com", "password": "S3curePass!"}'
```

The token is an HS256 JWT valid for **24 hours**. `setup_node.py` stores the token and credentials in `.env`, and `token_refresh.py` signs in again 5 minutes before expiry (`TOKEN_REFRESH_MARGIN_S`). You do not need to edit Python files when it expires.

### 2. Register the node (once)

`setup_node.py` registers the node automatically when `NODE_ID` is empty or no longer belongs to the signed-in account, then saves the returned id to `.env`. To run only the registration step:

```bash
python test/register_node.py
```

It reads `API_URL`, `JWT_TOKEN`, `NODE_NAME`, `NODE_LOCATION`, `NODE_LATITUDE`, and `NODE_LONGITUDE` from `.env`, sends `POST /api/node` with `Authorization: Bearer <token>`, and writes `NODE_ID` back to `.env`. A `401` means the token is invalid or expired; re-run `setup_node.py`. A `422` means the API rejected a field; the API's detail is printed.

### 3. Configure MQTT

MQTT settings come from `.env`:

```ini
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=urcast
NODE_ID=1
```

- `MQTT_BROKER` must point at the machine running Mosquitto.
- `NODE_ID` must match the id returned by registration. A different id publishes on a topic the token does not own, and the backend silently drops the message.
- `JWT_TOKEN` is read fresh for every publish, so the background refresh takes effect without restarting the service.

### 4. Run the service

```bash
python test/setup_node.py
```

or, if `.env` is already configured, the original loop:

```bash
cd test
python combinedTest.py
```

`combinedTest.py` continues to print samples to the terminal and additionally publishes:

| Topic | When | Payload |
| :--- | :--- | :--- |
| `urcast/<node_id>/reading` | every sample (~3 s) | `temperature`, `humidity`, `pressure`, `light_level`, `token` |
| `urcast/<node_id>/diagnostic` | every 10th successful reading | `uptime`, `light_sensor_status`, `dht22_status`, `pressure_sensor_status`, `token` |
| `urcast/<node_id>/heartbeat` | every 10th successful reading | `token` |

Sensor failures are sent as `null` (or omitted) rather than a made-up value, and the loop keeps running if the broker is unreachable. The terminal will show `could not send reading (no connection to broker): ...` and retry on the next sample.

### Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| Registration returns `401` | The JWT is missing or expired. Re-run `python test/setup_node.py`; it logs in again and refreshes the token. |
| Login fails with "email or password is incorrect" | Check `AUTH_EMAIL`/`AUTH_PASSWORD`, or choose "create a new account" when setup asks. |
| Backend drops readings with `token is missing or wrong for node <id>` | Check `JWT_TOKEN` in `.env` and that `NODE_ID` belongs to the signed-in account; re-run `setup_node.py`. |
| Backend drops readings with `node <id> does not exist` | Run `setup_node.py` or `register_node.py` to register the node and save `NODE_ID`. |
| Readings land on the wrong node or disappear | `NODE_ID` must be the id returned by registration, not an id copied from another node. |
| `could not send reading (no connection to broker)` | Check `MQTT_BROKER` and that Mosquitto is running on port `1883`. |
| Nothing arrives after 24 hours | Check that the service was started with `setup_node.py` (not only `--setup-only`), that `AUTH_EMAIL`/`AUTH_PASSWORD` are present, and that `TOKEN_REFRESH_MARGIN_S` is less than `86400`. |
| `ImportError: No module named 'board'` / `'busio'` / `'adafruit_bitbangio'` | Activate the virtual environment and run `pip install -r requirements.txt`; install `gpiod`, `libgpiod2`, and `python3-libgpiod` with `apt`. |
| GPIO permission error on the Pi | Install `gpiod`, `libgpiod2`, `python3-libgpiod`, and `python3-lgpio`, then add your user to the `gpio` group if needed. |

---

## Team

- **Pijus (PM)** – Back-End, Version Control
- **Raivis** – Database, Back-End
- **Anastasija** – Front-End, UI/UX/UD, Database
- **Leonas** – Hardware, Front-End
- **Kornel** – UI/UX/UD, Testing, Hardware