# Small REST client for the urcast API.
#
# The node only uses REST for three things: logging in, registering an account,
# and creating (or checking) its node. Sensor readings go over MQTT.

from __future__ import annotations

import json
import urllib.error
import urllib.request

import config

DEFAULT_TIMEOUT_S = 10


class ApiError(Exception):
    """An API call failed with an HTTP status or an invalid response."""

    def __init__(self, message: str, status: int | None = None, detail: str = ""):
        super().__init__(message)
        self.status = status
        self.detail = detail


class ApiConnectionError(ApiError):
    """The API could not be reached (DNS, refused connection, timeout)."""


def _api_url(api_url: str | None = None) -> str:
    base = (api_url or config.get("API_URL", "http://localhost:8000")).rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise ApiError(
            f"API_URL must start with http:// or https://, got {base!r}"
        )
    return base


def _format_detail(detail) -> str:
    if detail is None:
        return ""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                location = ".".join(
                    str(part)
                    for part in item.get("loc", ())
                    if part not in ("body", "query", "path")
                )
                message = item.get("msg") or item.get("message") or "invalid value"
                parts.append(f"{location}: {message}" if location else message)
            else:
                parts.append(str(item))
        return "; ".join(parts)
    if isinstance(detail, dict):
        return json.dumps(detail, ensure_ascii=False)
    return str(detail)


def _decode_body(body: str):
    if not body.strip():
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _request(
    method: str,
    path: str,
    payload: dict | None = None,
    token: str | None = None,
    api_url: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_S,
):
    base = _api_url(api_url)
    url = f"{base}{path}"
    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            parsed = _decode_body(body)
            if parsed is None and body.strip():
                raise ApiError(
                    "the API returned a response that is not valid JSON",
                    status=response.status,
                )
            return parsed
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        parsed = _decode_body(body)
        detail = _format_detail(
            parsed.get("detail") if isinstance(parsed, dict) else parsed
        )
        message = f"HTTP {error.code}"
        if detail:
            message += f": {detail}"
        raise ApiError(message, status=error.code, detail=detail) from error
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", error)
        raise ApiConnectionError(f"could not reach {base}: {reason}") from error
    except TimeoutError as error:
        raise ApiConnectionError(
            f"request to {base} timed out after {timeout} seconds"
        ) from error
    except OSError as error:
        raise ApiConnectionError(f"could not reach {base}: {error}") from error


def login(email: str, password: str, api_url: str | None = None) -> str:
    """Log in and return the access token."""
    result = _request(
        "POST",
        "/api/auth/login",
        {"email": email, "password": password},
        api_url=api_url,
    )
    token = result.get("access_token") if isinstance(result, dict) else None
    if not token:
        raise ApiError("login response did not contain an access_token")
    return token


def register_user(
    username: str, email: str, password: str, api_url: str | None = None
) -> dict:
    """Create an account and return the API's user object."""
    result = _request(
        "POST",
        "/api/user",
        {"username": username, "email": email, "password": password},
        api_url=api_url,
    )
    if not isinstance(result, dict) or "user_id" not in result:
        raise ApiError("registration response did not contain a user_id")
    return result


def get_me(token: str, api_url: str | None = None) -> dict:
    """Return the user that owns the token, or raise a 401 ApiError."""
    result = _request("GET", "/api/auth/me", token=token, api_url=api_url)
    if not isinstance(result, dict) or "user_id" not in result:
        raise ApiError("the API returned an invalid user record")
    return result


def create_node(
    token: str,
    node_name: str,
    location_name: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    api_url: str | None = None,
) -> dict:
    """Create a node owned by the token's user."""
    payload: dict = {"node_name": node_name}
    if location_name:
        payload["location_name"] = location_name
    if latitude is not None:
        payload["latitude"] = latitude
    if longitude is not None:
        payload["longitude"] = longitude

    result = _request("POST", "/api/node", payload, token=token, api_url=api_url)
    if not isinstance(result, dict) or "node_id" not in result:
        raise ApiError("node registration response did not contain a node_id")
    return result


def get_node(node_id: int, api_url: str | None = None) -> dict:
    """Return a node by id. The API returns 404 when it does not exist."""
    result = _request("GET", f"/api/node/{int(node_id)}", api_url=api_url)
    if not isinstance(result, dict) or "node_id" not in result:
        raise ApiError("the API returned an invalid node record")
    return result
