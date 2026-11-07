"""Keep the node's JWT fresh while the sensor service is running.

The urcast API issues HS256 tokens that expire after 24 hours and has no refresh
endpoint, so the node signs in again with the credentials saved in .env shortly
before the current token expires. mqtt_client reads JWT_TOKEN from .env on every
publish, which means the new token takes effect without restarting the service.
"""

from __future__ import annotations

import base64
import binascii
import json
import threading
import time

import api_client
import config

DEFAULT_REFRESH_MARGIN_S = 300
RETRY_DELAY_S = 60
MAX_SLEEP_S = 3600
TOKEN_LIFETIME_S = 24 * 60 * 60


def token_expiry(token):
    """Return the JWT exp claim as a Unix timestamp, or None if it is unreadable."""
    if not token or token.count(".") != 2:
        return None

    payload = token.split(".")[1]
    try:
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        expiry = claims.get("exp")
        return float(expiry) if expiry is not None else None
    except (binascii.Error, ValueError, TypeError, json.JSONDecodeError):
        return None


def refresh_margin():
    margin = config.get_int("TOKEN_REFRESH_MARGIN_S", DEFAULT_REFRESH_MARGIN_S)
    if margin < 0:
        raise ValueError("TOKEN_REFRESH_MARGIN_S must be zero or greater")
    if margin >= TOKEN_LIFETIME_S:
        raise ValueError("TOKEN_REFRESH_MARGIN_S must be less than 24 hours")
    return margin


def seconds_until_refresh(token, margin):
    expiry = token_expiry(token)
    if expiry is None:
        return None
    return expiry - margin - time.time()


class TokenRefresher:
    """Background thread that logs in again before the JWT expires."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="token-refresher", daemon=True
        )

    def start(self):
        self._thread.start()
        return self

    def stop(self, timeout=5.0):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout)

    def _run(self):
        while not self._stop.is_set():
            token = config.get("JWT_TOKEN", "")
            try:
                margin = refresh_margin()
            except ValueError as error:
                print(f"JWT refresh disabled: {error}")
                return

            delay = seconds_until_refresh(token, margin)
            if delay is None:
                print("JWT refresh disabled: the token has no readable exp claim.")
                return

            if delay > 0:
                # Wake up at least once an hour so a clock change cannot postpone
                # the refresh indefinitely.
                if self._stop.wait(min(delay, MAX_SLEEP_S)):
                    return
                continue

            refreshed = self._refresh()
            if refreshed is None:
                return
            if not refreshed:
                if self._stop.wait(RETRY_DELAY_S):
                    return
                continue

            # If the system clock is behind the API server, the new token can
            # still look expired locally. Do not spin on repeated logins.
            new_delay = seconds_until_refresh(config.get("JWT_TOKEN", ""), margin)
            if new_delay is not None and new_delay <= 0:
                if self._stop.wait(RETRY_DELAY_S):
                    return

    def _refresh(self):
        saved_email = config.get("AUTH_EMAIL", "")
        saved_password = config.get("AUTH_PASSWORD", "")
        if not saved_email or not saved_password:
            print(
                "JWT refresh disabled: AUTH_EMAIL/AUTH_PASSWORD are missing from "
                ".env; run setup_node.py again."
            )
            return None

        try:
            token = api_client.login(saved_email, saved_password)
        except (api_client.ApiConnectionError, api_client.ApiError) as error:
            print(f"JWT refresh failed: {error}")
            return False

        try:
            config.save({"JWT_TOKEN": token})
        except OSError as error:
            print(f"JWT refresh failed: could not update .env: {error}")
            return False
        expiry = token_expiry(token)
        if expiry is None:
            print("JWT refreshed, but the new token has no readable exp claim.")
        else:
            minutes = max(0, int((expiry - time.time()) / 60))
            print(f"JWT refreshed; the new token expires in about {minutes} minutes.")
        return True


def start_refresher():
    return TokenRefresher().start()
