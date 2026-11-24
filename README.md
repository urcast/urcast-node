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
- **Seamless Provisioning and Token Refresh:** `setup_node.py` checks the saved login, guides the user through login or registration, registers the node, stores the JWT and credentials in `.env`, and the MQTT publisher renews the JWT automatically before it expires.

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
- **Peripheral Libraries:** Adafruit CircuitPython (`board`, `busio`, `bitbangio`, `adafruit_tsl2591`, `adafruit_bmp280`, `adafruit_dht`) with `gpiod` as the Raspberry Pi 5 GPIO backend
- **Network Libraries:** `paho-mqtt` (MQTT publishing), `urllib` (REST login, registration, and auth checks)
- **Configuration:** `python-dotenv` (loads the central `.env`)
- **Containers:** Docker and Docker Compose (multi-stage image, non-root runtime, device passthrough for the sensors)
- **Runtime Utilities:** `getpass` (password prompts), `time`, `datetime` (UTC-enforced timestamping)

---

## Project Architecture

```text
urcast-node/
│
├── .env.example          # Template for the central .env configuration
├── .gitignore            # Keeps .env and local Python files out of git
├── .dockerignore         # Keeps .env, venv and caches out of the image build
├── requirements.txt      # Python dependencies for the node
│
├── Dockerfile            # Multi-stage image with a prebuilt virtualenv
├── docker-compose.yml    # Local container run, no sensor hardware
├── docker-compose.prod.yml # Pi container with gpio/i2c passthrough
│
├── install.sh            # Installs and enables the systemd service
├── start.sh              # Activates the venv and runs run.py (used by systemd)
├── config.py             # Loads and saves the central .env values
├── auth_client.py        # Login, registration, auth checks, and JWT refresh
├── setup_node.py         # Interactive first-run setup and service launcher
├── register_node.py      # Non-interactive node registration with an existing JWT
├── mqtt_client.py        # MQTT publisher (readings, diagnostics, heartbeat)
├── run.py                # Main sensor loop (also started by setup_node.py)
├── bmp280.py             # Standalone hardware test script for BMP280
├── dht22.py              # Standalone hardware test script for DHT22
├── tsl2591.py            # Standalone hardware test script for TSL2591
│
└── README.md             # Project documentation
```

---

## Repository Commit History & Test Development

You can inspect the complete evolution of the individual sensor scripts and diagnostic code on GitHub:

- **Repository:** [leonas-stanis/udp-pi-test-code](https://github.com/leonas-stanis/udp-pi-test-code)
- **Commit History:** Track incremental updates, bug fixes, and bus isolation testing across individual commits via the [GitHub Commit Log](https://github.com/leonas-stanis/udp-pi-test-code/commits/main/).


## Getting Started and Installation

### Prerequisites

- A Raspberry Pi 5 running Raspberry Pi OS with I2C interfaces enabled via `sudo raspi-config`.
- Physical wiring of the TSL2591, BMP280, and DHT22 modules according to the hardware stack pinout table above.
- Access to the urcast API and MQTT broker. Their addresses go in the central `.env` file.
- For the Docker path: Docker Engine with the Compose plugin (`docker compose version`).
- For the systemd path: Python 3.10 or newer and a virtualenv.

### Setup Instructions

Both options provision the same account, node and `.env`. Pick one and keep it: running the container and `urcast.service` at the same time makes the node publish two readings per interval.

#### Option 1: Docker Compose (recommended)

The node runs as a single container built from this repository. Python and the virtualenv live inside the image, and Docker starts the container on boot, so nothing has to stay in an SSH session.

1. Clone the repository and create `.env`:
```bash
git clone https://github.com/urcast/urcast-node
cd urcast-node
cp .env.example .env
```

2. Build the image:
```bash
docker compose -f docker-compose.prod.yml build
```

3. Provision the account and node from inside the container. This step is interactive, so run it in a terminal rather than detached; `--setup-only` stops before starting the sensor loop:
```bash
docker compose run --rm node python setup_node.py --setup-only
```
It writes `URCAST_NODE_TOKEN`, the account credentials and `URCAST_NODE_ID` into `.env` on the host, because `.env` is bind-mounted into the container. It uses `docker-compose.yml`, which needs no hardware, so it works before the sensors are wired; run it once per node.

4. Start the node in the background:
```bash
docker compose -f docker-compose.prod.yml up -d
```
This is the only start you need: from here on the Docker service launches the container at boot, with no SSH session and nobody logged in.

5. Check that it is running and sampling:
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f node
```
The logs show the same sample blocks as the terminal version, plus the `sent reading` lines.

The image is built in two stages: dependencies are installed into a virtualenv in the build stage and copied into the runtime stage, which runs as the non-root `node` user (uid 1000). `.dockerignore` keeps `.env`, `venv/` and local caches out of the build context.

The node only makes outbound connections (HTTPS to the API, MQTT over TLS to the broker), so the container publishes no ports and stays on the default bridge network with Docker's embedded DNS. Nothing on the Pi needs to reach it. There is no container healthcheck for the same reason: the node has no HTTP surface, so `docker compose ... logs` is what shows that samples are arriving.

Hardware access is the only difference between the two compose files. `docker-compose.prod.yml` passes `/dev/i2c-1` and a gpiochip node into the container and adds the `gpio` and `i2c` group ids. Check what your kernel exposes:

```bash
ls /dev/gpiochip*        # gpiochip0 on current Pi 5 kernels, gpiochip4 on older ones
getent group gpio i2c    # usually gpio 986, i2c 997
```

The Raspberry Pi OS defaults are already in the file. If your chips or group ids differ, set `NODE_GPIO_CHIP`, `GPIO_GID` or `I2C_GID` (in the environment or in `.env`) before starting. The container rewrites `.env` when it refreshes the JWT, so it runs as uid/gid 1000 by default; if your Pi user has different ids, set `NODE_UID` and `NODE_GID` to the output of `id -u` and `id -g`.

Useful commands:

```bash
docker compose -f docker-compose.prod.yml logs -f node    # follow the samples
docker compose -f docker-compose.prod.yml restart node    # after editing .env
docker compose -f docker-compose.prod.yml down            # stop; image and .env stay
docker compose -f docker-compose.prod.yml up -d --build   # rebuild after git pull
```

`docker-compose.yml` (run as `docker compose up --build`, without `-f docker-compose.prod.yml`) builds the same image without hardware access. Every sensor read fails soft, so the loop, the JWT refresh and the MQTT publish path can be tested on a laptop or on the Pi before the sensors are wired; readings are sent with `null` sensor fields.

Boot behavior comes from Docker itself: the `docker` service is enabled by the package, and `restart: unless-stopped` brings the container back after a reboot or power cut. Verify with no SSH session open:

```bash
sudo reboot
# once the Pi is back:
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail 20 node
```

#### Option 2: systemd service (no Docker)

1. Clone or download this repository to your Raspberry Pi 5:
```bash
git clone https://github.com/urcast/urcast-node
```

2. Create and activate a virtual environment in urcast-node/:
```bash
cd urcast-node
python -m venv venv
source venv/bin/activate
```

3. Install the Python dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` installs Adafruit Blinka (`board`, `busio`, `bitbangio`), the three sensor drivers, `gpiod` for Raspberry Pi 5 GPIO, `paho-mqtt`, and `python-dotenv`. If pip cannot find a `gpiod` wheel for your Python version, install the matching libgpiod development package from Raspberry Pi OS and retry.

On Raspberry Pi OS, make sure your user can access GPIO:
```bash
sudo usermod -aG gpio "$USER"
```
Log out and back in after changing groups.

4. Create the central `.env` from the template:
```bash
cp .env.example .env
```

Our default API:
```dotenv
URCAST_API_URL=https://urcast.pjmisev.com
URCAST_MQTT_BROKER=urcast.pjmisev.com
URCAST_MQTT_PORT=8883
```

Leave `URCAST_NODE_ID`, `URCAST_NODE_TOKEN`, `URCAST_EMAIL`, and `URCAST_PASSWORD` empty. `setup_node.py` fills them in.

If the node runs on the Pi and the API runs on your laptop, use the laptop's LAN IP, not `localhost`.

5. Run the interactive setup:
```bash
python setup_node.py
```

The setup script will:

- check the saved JWT with `GET /api/auth/me`;
- ask whether to log in or register if no valid login exists;
- list the nodes on your account and let you pick one or register a new node;
- save the JWT, account credentials, and node id to `.env`;
- start the sensor service in the foreground.

To configure without starting the service, run:
```bash
python setup_node.py --setup-only
```

`.env` is created with owner-only permissions and is ignored by git. Keep it private: it contains the account password and node JWT.

6. Install the service so the node runs on boot, without an SSH session:

Stop the foreground copy first: `setup_node.py` starts `run.py` in the terminal, so press `Ctrl+C` once it has printed at least one `sent reading` line, or provision with `python setup_node.py --setup-only` so it never starts. Leaving it running and installing anyway would give you two publishers for the same node.

```bash
chmod +x install.sh
./install.sh
```

`install.sh` detects the absolute path of your clone (whatever user, folder, or home directory you chose), writes `/etc/systemd/system/urcast.service` with that path and your account, reloads systemd, enables the unit for boot, and starts it. `start.sh` is the service entry point: it enters the repo directory and runs `run.py` with the virtualenv's Python, reading `.env` and the saved JWT. It prompts for nothing and has no terminal, so the node starts sampling at boot before anyone logs in.

```bash
systemctl status urcast        # check it is running
journalctl -u urcast -f        # follow live logs
sudo systemctl restart urcast  # after changing .env or code
sudo systemctl stop urcast     # pause sampling
```

Output that used to go to the SSH terminal now goes to the journal, so you can close the session and the node keeps sampling. The installer can be rerun safely: it rewrites the service file with the current path and restarts the unit, so rerun it from the new location if you move the repository.

To confirm the boot behavior, reboot with no SSH session open and check afterwards:

```bash
sudo reboot
# once the Pi is back:
systemctl is-enabled urcast
systemctl is-active urcast
journalctl -u urcast -n 20
```

`is-enabled` should print `enabled`, `is-active` should print `active`, and the journal should show samples with recent timestamps and no prompts. `.env` and the JWT are read without user input, so the same applies after a power cut.

If you re-provision the account or node later, stop the service first, then rerun setup and start it again:

```bash
sudo systemctl stop urcast
python setup_node.py --setup-only
sudo systemctl start urcast
```

---

## Running and Testing

On a provisioned Pi the node normally starts at boot and does not need an SSH session. Use whichever option was installed.

With Docker:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f node
docker compose -f docker-compose.prod.yml restart node
```

With the systemd service:

```bash
systemctl status urcast
journalctl -u urcast -f
```

For a one-off foreground run from a host install (debugging, or before the systemd service is installed), the setup script can provision and start the node in the current terminal:

```bash
python setup_node.py
```

After `.env` is configured, the sensor loop can also be started directly with the venv active or through the wrapper script used by systemd:

```bash
source venv/bin/activate
python run.py
```

```bash
./start.sh
```

The container equivalent is `docker compose -f docker-compose.prod.yml up`, which logs to the terminal until you press `Ctrl+C`.

Press `Ctrl+C` at any time to safely terminate the execution loop and release hardware interfaces. Do not run a manual copy while `urcast.service` or the container is active: both would publish readings for the same node.

---

## Connecting to the urcast API

The node talks to the backend over two transports:

- **REST over HTTP(S)** is used to log in, register the account and node, and verify the saved JWT.
- **MQTT over TLS (port 8883)** carries every reading, diagnostic, and heartbeat. `mqtt_client.py` enables TLS with the Pi's system CA store, so the broker's Let's Encrypt certificate and hostname are verified on every connection. The broker accepts anonymous connections, but the backend reads the JWT from a `token` field inside each payload and drops anything with a missing, expired, or mismatched token.

`setup_node.py` performs the REST steps for you. The manual steps below are for debugging or for provisioning a node without the interactive setup.

### Automatic setup (recommended)

Run from the repository root:

```bash
python setup_node.py
```

The script:

1. Loads `.env`.
2. Calls `GET /api/auth/me` with `URCAST_NODE_TOKEN`.
3. If the token is missing or expired, asks whether to log in, register, or quit.
4. On login, validates the email and password, then writes `URCAST_EMAIL`, `URCAST_PASSWORD`, and `URCAST_NODE_TOKEN` to `.env`.
5. On registration, validates the username, email, and password, creates the account with `POST /api/user`, then logs in and saves the same values.
6. Calls `GET /api/nodes` and lists the nodes owned by your account as `<node_id> (<node_name>)`. You can pick one of them, or enter `n` to register a new node. For a new node it asks for the node name, location, and optional coordinates, then creates it with `POST /api/node`.
7. Saves `URCAST_NODE_ID` and the node details to `.env`.
8. Starts `run.py`.

Use `python setup_node.py --setup-only` to stop before step 8.

### What the setup writes to .env

| Key | Source |
| :--- | :--- |
| `URCAST_API_URL` | you |
| `URCAST_MQTT_BROKER` | you |
| `URCAST_MQTT_PORT` | you |
| `URCAST_EMAIL` | login/register prompt |
| `URCAST_PASSWORD` | login/register prompt |
| `URCAST_NODE_TOKEN` | `/api/auth/login` response |
| `URCAST_NODE_ID` | `POST /api/node` response |
| `URCAST_NODE_NAME`, `URCAST_NODE_LOCATION`, `URCAST_NODE_LATITUDE`, `URCAST_NODE_LONGITUDE` | information for database to be filled in manually |
| `URCAST_READ_INTERVAL_S` | you (optional, defaults to `60.0`) |

`.env` is gitignored and is set to owner-only permissions (`600`) on Linux. Do not share it: it contains the account password and node JWT.

### JWT lifetime and automatic refresh

The token is an HS256 JWT and is valid for **24 hours**. The node renews it automatically through `auth_client.py`:

- the token expiry is checked before every MQTT publish;
- when less than one hour remains, the node logs in again with `URCAST_EMAIL` and `URCAST_PASSWORD`;
- the new token is written back to `URCAST_NODE_TOKEN` in `.env`;
- if the API is temporarily unreachable, the old token keeps being used while it is still valid and the refresh is retried every 60 seconds.

This requires the API to be reachable around the refresh time and the stored credentials to remain valid. If the password changes, run `setup_node.py` and log in again to update `.env`.

### Manual registration (optional)

If you already have a JWT and want to register the node non-interactively, set `URCAST_API_URL`, `URCAST_NODE_TOKEN`, and the `URCAST_NODE_*` fields in `.env`, then run:

```bash
python register_node.py
```

The script sends `POST /api/node` with `Authorization: Bearer <token>` and saves the returned `node_id` to `.env`. This path does not prompt and does not refresh the token; use `setup_node.py` for the normal setup.

The API endpoints used are:

- `POST /api/user` with `username`, `email`, `password`
- `POST /api/auth/login` with `email`, `password`; returns `access_token`
- `GET /api/auth/me` with `Authorization: Bearer <token>`
- `GET /api/nodes` (all nodes; the setup script keeps only the ones owned by your account)
- `POST /api/node` with `Authorization: Bearer <token>` and `node_name`, `location_name`, `latitude`, and `longitude`

### MQTT topics

`run.py` continues to print samples to the terminal and additionally publishes:

| Topic | When | Payload |
| :--- | :--- | :--- |
| `urcast/<node_id>/reading` | every sample (~3 s) | `temperature`, `humidity`, `pressure`, `light_level`, `token` |
| `urcast/<node_id>/diagnostic` | every 10th successful reading | `uptime`, `light_sensor_status`, `dht22_status`, `pressure_sensor_status`, `token` |
| `urcast/<node_id>/heartbeat` | every 10th successful reading | `token` |

Sensor failures are sent as `null` (or omitted) rather than a made-up value, and the loop keeps running if the broker is unreachable. The terminal will show `could not send reading (TLS connection to broker failed): ...` and retry on the next sample.

### Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `No valid urcast login found` | Run `setup_node.py` and choose login or register. |
| Login returns `401` | Check `URCAST_EMAIL` and `URCAST_PASSWORD`; the API reports `Invalid email or password`. |
| Registration returns `400` | The username or email already exists. Choose login instead, or use a different email. |
| Registration returns `422` | The API validation failed; check the printed detail (for example, a password under 8 characters). |
| `Could not reach the API at ...` | Check `URCAST_API_URL` in `.env` and that the API is running. Use the server's LAN IP, not `localhost`, when the API is on another machine. |
| Backend drops readings with `token is missing or wrong for node <id>` | Run `setup_node.py` so the token belongs to the account that registered `URCAST_NODE_ID`. |
| Backend drops readings with `node <id> does not exist` | Run `setup_node.py` to register the node; do not use an id from another node. |
| `could not send reading (TLS connection to broker failed)` | Check `URCAST_MQTT_BROKER` (must be `urcast.pjmisev.com`, kept as a grey-cloud DNS record) and that Mosquitto is listening with TLS on `URCAST_MQTT_PORT` (8883). |
| Nothing arrives after 24 hours | Check that `URCAST_EMAIL` and `URCAST_PASSWORD` are still valid; the node refreshes the JWT one hour before expiry. |
| `URCAST_NODE_TOKEN` or `URCAST_NODE_ID` missing from `.env` | Run `setup_node.py` again. It reuses existing values and fills in missing ones. |
| `urcast.service` fails with `status=203/EXEC` | The service file points at a missing path or `start.sh` is not executable. Rerun `./install.sh` from the current repository location. |
| `urcast.service` restarts every 10 seconds | Check `journalctl -u urcast -n 50`. Usually `venv/` is missing, dependencies are not installed in it, or `.env` was never created. |
| Service starts but every sensor reports `n/a` or `init failed` | GPIO permissions. Confirm the service user is in the `gpio` group, then `sudo systemctl restart urcast`. |
| Readings stop after closing the SSH session | They should not. If they do, the node was started by hand instead of by `urcast.service`; check `systemctl is-enabled urcast` and `systemctl is-active urcast`. |

---

## Team

- **Pijus (PM)** – Back-End, Version Control
- **Raivis** – Database, Back-End
- **Anastasija** – Front-End, UI/UX/UD, Database
- **Leonas** – Hardware, Front-End
- **Kornel** – UI/UX/UD, Testing, Hardware