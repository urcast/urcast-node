"""Validation helpers shared by the node setup flow.

The urcast API rejects malformed input with HTTP 400/422 responses. Checking the
same constraints locally gives the user a clear message before a request is sent
and lets the interactive setup loop ask again without leaving a half-created
account or node behind.
"""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_EMAIL_LENGTH = 255
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 100
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72
MAX_NODE_NAME_LENGTH = 100
MAX_LOCATION_LENGTH = 150


class ValidationError(ValueError):
    """A user-supplied value does not satisfy the API's constraints."""


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def email(value) -> str:
    text = _text(value)
    if not text:
        raise ValidationError("Email is required.")
    if len(text) > MAX_EMAIL_LENGTH:
        raise ValidationError(
            f"Email must be {MAX_EMAIL_LENGTH} characters or fewer."
        )
    if not EMAIL_RE.fullmatch(text):
        raise ValidationError(
            "Enter a valid email address, for example you@example.com."
        )
    return text


def username(value) -> str:
    text = _text(value)
    if not MIN_USERNAME_LENGTH <= len(text) <= MAX_USERNAME_LENGTH:
        raise ValidationError(
            f"Username must be {MIN_USERNAME_LENGTH}-{MAX_USERNAME_LENGTH} characters."
        )
    return text


def password(value) -> str:
    text = "" if value is None else str(value)
    if len(text) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    if len(text) > MAX_PASSWORD_LENGTH:
        raise ValidationError(
            f"Password must be {MAX_PASSWORD_LENGTH} characters or fewer."
        )
    return text


def any_password(value) -> str:
    """Validate a password used to log in without changing its whitespace."""
    text = "" if value is None else str(value)
    if not text:
        raise ValidationError("Password is required.")
    return text


def node_name(value) -> str:
    text = _text(value)
    if not 1 <= len(text) <= MAX_NODE_NAME_LENGTH:
        raise ValidationError(
            f"Node name must be 1-{MAX_NODE_NAME_LENGTH} characters."
        )
    return text


def location(value) -> str:
    text = _text(value)
    if len(text) > MAX_LOCATION_LENGTH:
        raise ValidationError(
            f"Location must be {MAX_LOCATION_LENGTH} characters or fewer."
        )
    return text


def latitude(value) -> float | None:
    return _coordinate(value, "Latitude", -90.0, 90.0)


def longitude(value) -> float | None:
    return _coordinate(value, "Longitude", -180.0, 180.0)


def non_empty(value, label="Value") -> str:
    text = _text(value)
    if not text:
        raise ValidationError(f"{label} is required.")
    return text


def _coordinate(value, label, minimum, maximum):
    text = _text(value)
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            f"{label} must be a number, got {text!r}."
        ) from error
    if not minimum <= number <= maximum:
        raise ValidationError(
            f"{label} must be between {minimum:g} and {maximum:g}."
        )
    return number
