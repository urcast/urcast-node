# Register the node with POST /api/node using the JWT stored in .env.
#
# setup_node.py is the recommended entry point because it also handles login,
# registration, token storage and starting the sensor service. This script is
# kept as a standalone registration step for users who already have a token.

import sys

import api_client
import config


def _optional_float(key):
    raw = config.get(key)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise SystemExit(f"Configuration error: {key} must be a number, got {raw!r}")


def register_node():
    config.ensure_env()

    token = config.get("JWT_TOKEN")
    if not token:
        print("No JWT_TOKEN in .env. Run setup_node.py to log in first.")
        return None

    node_name = str(config.get("NODE_NAME", "pi5-outdoor")).strip()
    if not 1 <= len(node_name) <= 100:
        print("Configuration error: NODE_NAME must be 1-100 characters.")
        return None

    location_name = str(config.get("NODE_LOCATION", "")).strip()
    if len(location_name) > 150:
        print("Configuration error: NODE_LOCATION must be 150 characters or fewer.")
        return None

    latitude = _optional_float("NODE_LATITUDE")
    longitude = _optional_float("NODE_LONGITUDE")
    if latitude is not None and not -90 <= latitude <= 90:
        print("Configuration error: NODE_LATITUDE must be between -90 and 90.")
        return None
    if longitude is not None and not -180 <= longitude <= 180:
        print("Configuration error: NODE_LONGITUDE must be between -180 and 180.")
        return None

    existing_id = config.get("NODE_ID")
    if existing_id:
        print(f"NODE_ID is already set to {existing_id}; creating another node anyway.")

    try:
        node = api_client.create_node(
            token,
            node_name,
            location_name or None,
            latitude,
            longitude,
        )
    except api_client.ApiConnectionError as error:
        print(f"Could not reach the API: {error}")
        print("Check API_URL in .env and that the backend is running.")
        return None
    except api_client.ApiError as error:
        if error.status == 401:
            print("Registration failed: the token is invalid or expired (HTTP 401).")
            print("Run setup_node.py to log in again and refresh JWT_TOKEN.")
        elif error.status == 403:
            print("Registration failed: this account is not allowed to create the node.")
        else:
            print(f"Registration failed: {error}")
        return None

    node_id = node["node_id"]
    config.save(
        {
            "NODE_ID": node_id,
            "NODE_NAME": node_name,
            "NODE_LOCATION": location_name,
            "NODE_LATITUDE": "" if latitude is None else latitude,
            "NODE_LONGITUDE": "" if longitude is None else longitude,
        }
    )

    print(f"Node registered with id {node_id}.")
    print(f"Saved NODE_ID={node_id} to {config.ENV_PATH}.")
    return node_id


def main():
    if register_node() is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
