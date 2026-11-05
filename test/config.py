# Central configuration for the urcast node.
#
# All runtime settings live in the repository-level .env file. The file is
# created from .env.example on first run, and setup_node.py writes the JWT,
# account credentials and node id back into it.

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
EXAMPLE_PATH = ROOT_DIR / ".env.example"

# Fallbacks used when .env is missing or a key has not been added yet.
DEFAULTS = {
    "API_URL": "http://localhost:8000",
    "MQTT_BROKER": "localhost",
    "MQTT_PORT": "1883",
    "MQTT_TOPIC_PREFIX": "urcast",
    "AUTH_EMAIL": "",
    "AUTH_PASSWORD": "",
    "JWT_TOKEN": "",
    "NODE_ID": "",
    "NODE_NAME": "pi5-outdoor",
    "NODE_LOCATION": "",
    "NODE_LATITUDE": "",
    "NODE_LONGITUDE": "",
    "TOKEN_REFRESH_MARGIN_S": "300",
    "READ_INTERVAL_S": "3.0",
    "DHT_PIN": "D4",
    "BMP_SDA_PIN": "D17",
    "BMP_SCL_PIN": "D27",
    "BMP280_ADDRESS": "0x76",
    "BMP_SEA_LEVEL_PRESSURE_HPA": "1013.25",
    "TSL_GAIN": "low",
    "TSL_INTEGRATION_TIME": "100ms",
}


def _parse_value(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw[1:-1]
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return raw[1:-1]
    # Allow trailing comments on unquoted values.
    if " #" in raw:
        raw = raw.split(" #", 1)[0].rstrip()
    return raw


def _format_value(value) -> str:
    text = "" if value is None else str(value)
    if not text or any(char.isspace() for char in text) or any(
        char in text for char in '#"\'\\'
    ):
        # JSON quoting keeps passwords with spaces or special characters intact.
        return json.dumps(text)
    return text


def _parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key:
            values[key] = _parse_value(value)
    return values


def _restrict_permissions() -> None:
    if os.name == "posix" and ENV_PATH.exists():
        try:
            os.chmod(ENV_PATH, 0o600)
        except OSError:
            pass


def load() -> dict[str, str]:
    """Load .env into os.environ without overriding real environment variables."""
    values = _parse_env(ENV_PATH.read_text(encoding="utf-8")) if ENV_PATH.exists() else {}
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return values


def ensure_env() -> Path:
    """Create .env from the example on first run and load it."""
    if not ENV_PATH.exists():
        if EXAMPLE_PATH.exists():
            shutil.copyfile(EXAMPLE_PATH, ENV_PATH)
        else:
            ENV_PATH.write_text(
                "\n".join(f"{key}={_format_value(value)}" for key, value in DEFAULTS.items())
                + "\n",
                encoding="utf-8",
            )
        _restrict_permissions()
    load()
    return ENV_PATH


def save(values: dict) -> None:
    """Update keys in .env, preserving comments and any unrelated entries."""
    ensure_env()

    remaining = {key: _format_value(value) for key, value in values.items()}
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)

    if remaining:
        if output and output[-1].strip():
            output.append("")
        for key, value in remaining.items():
            output.append(f"{key}={value}")

    temp_path = ENV_PATH.with_name(ENV_PATH.name + ".tmp")
    temp_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.replace(temp_path, ENV_PATH)
    _restrict_permissions()

    for key, value in values.items():
        os.environ[key] = "" if value is None else str(value)


def get(key: str, default=None):
    value = os.environ.get(key)
    if value is None or value == "":
        value = DEFAULTS.get(key)
    if value is None or value == "":
        return default
    return value


def get_int(key: str, default: int = 0) -> int:
    raw = get(key)
    if raw is None:
        return default
    try:
        return int(str(raw), 0)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{key} must be an integer, got {raw!r}") from error


def get_float(key: str, default: float = 0.0) -> float:
    raw = get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{key} must be a number, got {raw!r}") from error


def get_bool(key: str, default: bool = False) -> bool:
    raw = get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


ensure_env()
