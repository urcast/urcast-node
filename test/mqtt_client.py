# MQTT publisher for the urcast weather node.
#
# Every message is published to <prefix>/<node_id>/<kind> and carries the
# owner's JWT in the "token" field. The backend drops anything with a missing,
# expired, or wrong token, so the token comes from the shared .env file.
#
# All settings live in the repository-level .env file:
#   MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_PREFIX
#   NODE_ID     -- written by setup_node.py after registration
#   JWT_TOKEN   -- written by setup_node.py after login

import json
import time

import paho.mqtt.client as mqtt

import config

_STARTED_AT = time.monotonic()
_client = None
_connection = None


def _new_client():
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        # paho-mqtt older than 2.0 has no CallbackAPIVersion
        return mqtt.Client()


def _drop_client():
    global _client, _connection
    if _client is not None:
        try:
            _client.loop_stop()
            _client.disconnect()
        except Exception:
            pass
        _client = None
    _connection = None


def _get_client(broker, port):
    global _client, _connection
    if (
        _client is not None
        and _client.is_connected()
        and _connection == (broker, port)
    ):
        return _client

    _drop_client()
    _client = _new_client()
    _client.connect(broker, port)
    _client.loop_start()
    _connection = (broker, port)
    return _client


def _publish(kind, fields):
    broker = config.get("MQTT_BROKER", "localhost")
    port = config.get_int("MQTT_PORT", 1883)
    prefix = config.get("MQTT_TOPIC_PREFIX", "urcast")
    node_id = config.get("NODE_ID")
    token = config.get("JWT_TOKEN", "")

    if not node_id:
        print(
            f"could not send {kind}: NODE_ID is not configured; "
            "run setup_node.py first"
        )
        return False
    try:
        node_id = int(node_id)
    except (TypeError, ValueError):
        print(f"could not send {kind}: NODE_ID must be a number, got {node_id!r}")
        return False
    if not token:
        print(
            f"could not send {kind}: JWT_TOKEN is not configured; "
            "run setup_node.py first"
        )
        return False

    payload = dict(fields)
    payload["token"] = token
    topic = f"{prefix}/{node_id}/{kind}"

    try:
        client = _get_client(broker, port)
        result = client.publish(topic, json.dumps(payload))
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"publish returned code {result.rc}")
        return True
    except Exception as error:
        _drop_client()
        print(f"could not send {kind} (no connection to broker): {error}")
        return False


def send_reading(temperature, humidity, pressure, light_level):
    return _publish(
        "reading",
        {
            "temperature": temperature,
            "humidity": humidity,
            "pressure": pressure,
            "light_level": light_level,
        },
    )


def send_diagnostic(light_ok, air_ok, pressure_ok):
    return _publish(
        "diagnostic",
        {
            "uptime": int(time.monotonic() - _STARTED_AT),
            "light_sensor_status": light_ok,
            "dht22_status": air_ok,
            "pressure_sensor_status": pressure_ok,
        },
    )


def send_heartbeat():
    return _publish("heartbeat", {})


def close():
    _drop_client()
