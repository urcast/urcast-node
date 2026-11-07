#!/usr/bin/env python3
"""Guided first-run setup for the urcast weather node.

Run it from anywhere in the repository:

    python test/setup_node.py

The first run creates .env from .env.example, checks whether the saved JWT is
still valid, and asks you to log in or create an account when it is not. It then
registers this node (unless NODE_ID is already set), writes the JWT, account
credentials and node id back to .env, and starts the sensor service.

Use --setup-only to save the configuration without starting the sensors.
"""

from __future__ import annotations

import argparse
import getpass
import sys

import api_client
import config
import token_refresh
import validation

DEFAULT_NODE_NAME = "pi5-outdoor"


class SetupError(Exception):
    """Setup cannot continue, usually because the API refused a request."""


def _ask(prompt, default=None, secret=False):
    suffix = f" [{default}]" if default not in (None, "") else ""
    reader = getpass.getpass if secret else input
    try:
        answer = reader(f"{prompt}{suffix}: ")
    except EOFError as error:
        raise SetupError("Input ended before setup was complete.") from error
    if not answer.strip() and default not in (None, ""):
        return str(default)
    return answer


def ask_validated(prompt, validator, default=None, secret=False):
    while True:
        raw = _ask(prompt, default=default, secret=secret)
        try:
            return validator(raw)
        except validation.ValidationError as error:
            print(f"  {error}")


def ask_password(prompt="Password", confirm=False):
    while True:
        value = ask_validated(prompt, validation.password, secret=True)
        if not confirm:
            return value
        repeated = _ask("Confirm password", secret=True)
        if repeated != value:
            print("  Passwords do not match. Try again.")
            continue
        return value


def choose_action():
    print("This node is not signed in.")
    print("  1) Log in with an existing urcast account")
    print("  2) Create a new account")
    while True:
        choice = _ask("Choose 1 or 2").strip().lower()
        if choice in {"1", "l", "login"}:
            return "login"
        if choice in {"2", "r", "register", "signup", "sign up"}:
            return "register"
        print("  Enter 1 to log in or 2 to create an account.")


def login():
    email_default = config.get("AUTH_EMAIL") or None
    email_value = ask_validated("Email", validation.email, default=email_default)
    password_value = ask_validated(
        "Password",
        validation.any_password,
        secret=True,
    )

    try:
        token = api_client.login(email_value, password_value)
    except api_client.ApiConnectionError as error:
        raise SetupError(f"Could not reach the API: {error}") from error
    except api_client.ApiError as error:
        if error.status == 401:
            raise SetupError("Login failed: the email or password is incorrect.") from error
        raise SetupError(f"Login failed: {error}") from error

    try:
        user = api_client.get_me(token)
    except api_client.ApiError as error:
        raise SetupError(
            f"Login succeeded but the account could not be verified: {error}"
        ) from error

    config.save(
        {
            "JWT_TOKEN": token,
            "AUTH_EMAIL": email_value,
            "AUTH_PASSWORD": password_value,
        }
    )
    print(f"Signed in as {user.get('username') or email_value}.")
    return token, user


def register():
    print("Create a new urcast account.")
    username_value = ask_validated("Username", validation.username)
    email_value = ask_validated("Email", validation.email)
    password_value = ask_password(confirm=True)

    try:
        account = api_client.register_user(username_value, email_value, password_value)
    except api_client.ApiConnectionError as error:
        raise SetupError(f"Could not reach the API: {error}") from error
    except api_client.ApiError as error:
        if error.status == 400:
            raise SetupError(
                f"Registration failed: {error.detail or error}"
            ) from error
        raise SetupError(f"Registration failed: {error}") from error

    print(f"Account created for {account.get('username') or username_value}.")

    try:
        token = api_client.login(email_value, password_value)
        user = api_client.get_me(token)
    except api_client.ApiConnectionError as error:
        raise SetupError(f"Could not reach the API: {error}") from error
    except api_client.ApiError as error:
        raise SetupError(
            "The account was created, but signing in failed. "
            f"Run setup_node.py again and choose log in: {error}"
        ) from error

    config.save(
        {
            "JWT_TOKEN": token,
            "AUTH_EMAIL": email_value,
            "AUTH_PASSWORD": password_value,
        }
    )
    print(f"Signed in as {user.get('username') or username_value}.")
    return token, user


def authenticate():
    token = config.get("JWT_TOKEN", "")
    if token:
        try:
            user = api_client.get_me(token)
        except api_client.ApiConnectionError as error:
            raise SetupError(f"Could not reach the API: {error}") from error
        except api_client.ApiError as error:
            if error.status != 401:
                raise SetupError(f"Could not verify the saved JWT: {error}") from error
            print("The saved JWT is invalid or has expired.")
        else:
            print(f"Already signed in as {user.get('username') or 'user'}.")
            return token, user

    saved_email = config.get("AUTH_EMAIL", "")
    saved_password = config.get("AUTH_PASSWORD", "")
    if saved_email and saved_password:
        print("Trying the account credentials saved in .env...")
        try:
            token = api_client.login(saved_email, saved_password)
            user = api_client.get_me(token)
        except api_client.ApiConnectionError as error:
            raise SetupError(f"Could not reach the API: {error}") from error
        except api_client.ApiError as error:
            if error.status == 401:
                print("The saved credentials are no longer valid.")
            else:
                print(f"The saved credentials could not be used: {error}")
        else:
            config.save({"JWT_TOKEN": token})
            print(f"Signed in as {user.get('username') or saved_email}.")
            return token, user

    action = choose_action()
    return login() if action == "login" else register()


def _configured_node_name():
    raw = config.get("NODE_NAME", DEFAULT_NODE_NAME)
    try:
        return validation.node_name(raw)
    except validation.ValidationError as error:
        print(f"NODE_NAME in .env is invalid: {error}")
    return ask_validated("Node name", validation.node_name, default=DEFAULT_NODE_NAME)


def _configured_location():
    raw = config.get("NODE_LOCATION", "")
    try:
        return validation.location(raw)
    except validation.ValidationError as error:
        print(f"NODE_LOCATION in .env is invalid: {error}")
    return ask_validated("Location (optional)", validation.location)


def _configured_coordinate(key, validator, label):
    raw = config.get(key, "")
    try:
        return validator(raw)
    except validation.ValidationError as error:
        print(f"{key} in .env is invalid: {error}")
    return ask_validated(f"{label} (optional)", validator)


def ensure_node(token, user):
    saved_id = config.get("NODE_ID", "")
    if saved_id:
        try:
            node_id = int(saved_id)
        except (TypeError, ValueError):
            raise SetupError(
                f"NODE_ID in .env must be a number, got {saved_id!r}."
            ) from None

        try:
            node = api_client.get_node(node_id)
        except api_client.ApiConnectionError as error:
            raise SetupError(f"Could not reach the API: {error}") from error
        except api_client.ApiError as error:
            if error.status != 404:
                raise SetupError(
                    f"Could not check node {node_id}: {error}"
                ) from error
            print(f"Node {node_id} was not found; registering a new node.")
        else:
            if node.get("user_id") == user.get("user_id"):
                print(
                    f"Using registered node {node_id} "
                    f"({node.get('node_name') or 'unnamed'})."
                )
                return node_id
            print(
                f"Node {node_id} belongs to another account; "
                "registering a new node."
            )

    node_name_value = _configured_node_name()
    location_value = _configured_location()
    latitude_value = _configured_coordinate(
        "NODE_LATITUDE", validation.latitude, "Latitude"
    )
    longitude_value = _configured_coordinate(
        "NODE_LONGITUDE", validation.longitude, "Longitude"
    )

    try:
        node = api_client.create_node(
            token,
            node_name_value,
            location_value or None,
            latitude_value,
            longitude_value,
        )
    except api_client.ApiConnectionError as error:
        raise SetupError(f"Could not reach the API: {error}") from error
    except api_client.ApiError as error:
        if error.status == 401:
            raise SetupError(
                "The JWT was rejected while registering the node. "
                "Run setup_node.py again."
            ) from error
        raise SetupError(f"Node registration failed: {error}") from error

    node_id = int(node["node_id"])
    config.save(
        {
            "NODE_ID": node_id,
            "NODE_NAME": node_name_value,
            "NODE_LOCATION": location_value,
            "NODE_LATITUDE": "" if latitude_value is None else latitude_value,
            "NODE_LONGITUDE": "" if longitude_value is None else longitude_value,
        }
    )
    print(f"Registered node {node_id} and saved it to .env.")
    return node_id


def start_service():
    try:
        import combinedTest
    except ImportError as error:
        raise SetupError(
            "The sensor service could not be imported. Run this on the "
            "Raspberry Pi after installing the packages in requirements.txt "
            "(see README.md).\n"
            f"Import error: {error}"
        ) from error

    print("\nStarting the sensor service. Press Ctrl+C to stop.\n")
    combinedTest.main()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Set up and start the urcast weather node."
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="save authentication and node details, but do not start the service",
    )
    args = parser.parse_args(argv)

    try:
        config.ensure_env()
        print(f"Using configuration file: {config.ENV_PATH}")

        token, user = authenticate()
        ensure_node(token, user)

        if args.setup_only:
            print(
                "\nSetup complete. Run the same command without --setup-only "
                "to start the service."
            )
            return 0

        if not config.get("AUTH_EMAIL") or not config.get("AUTH_PASSWORD"):
            print(
                "Warning: AUTH_EMAIL/AUTH_PASSWORD are missing from .env; "
                "the JWT will not refresh automatically."
            )

        refresher = token_refresh.start_refresher()
        try:
            start_service()
        finally:
            refresher.stop()
        return 0
    except SetupError as error:
        print(f"\nSetup failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
