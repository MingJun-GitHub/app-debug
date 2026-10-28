"""Redaction helpers for copied and exported diagnostic data."""

from __future__ import annotations

import re
from typing import Any


REDACTED = "[REDACTED]"

_KEY_VALUE_PATTERN = re.compile(
    r"(?i)(\b(?:"
    r"authorization|proxy-authorization|cookie|set-cookie|"
    r"access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"api[_-]?key|client[_-]?secret|private[_-]?key|"
    r"password|passwd|push[_-]?token|fcm[_-]?token|apns[_-]?token"
    r")\b[\"']?\s*[:=]\s*[\"']?)([^\"'\s,;}\]]+)"
)
_QUERY_SECRET_PATTERN = re.compile(
    r"(?i)([?&](?:access_token|refresh_token|token|key|signature|sign|password)=)(?![{<])([^&\s#]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_EMAIL_PATTERN = re.compile(
    r"\b([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]*)"
    r"@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
)
_LONG_HEX_SECRET_PATTERN = re.compile(r"\b(?:[0-9a-fA-F]{40,})\b")
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)^(?:authorization|proxy-authorization|cookie|set-cookie|"
    r"access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"api[_-]?key|client[_-]?secret|private[_-]?key|"
    r"password|passwd|push[_-]?token|fcm[_-]?token|apns[_-]?token|"
    r"udid|device[_-]?id|distinct[_-]?id)$"
)


def _mask_email(match: re.Match[str]) -> str:
    local = match.group(1) + match.group(2)
    domain = match.group(3)
    return f"{local[:1]}***@{domain}"


def redact_text(value: Any) -> str:
    """Return text with credentials and common user identifiers masked."""
    text = "" if value is None else str(value)
    text = _BEARER_PATTERN.sub(lambda match: f"{match.group(1)} {REDACTED}", text)
    text = _KEY_VALUE_PATTERN.sub(lambda match: f"{match.group(1)}{REDACTED}", text)
    text = _QUERY_SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{REDACTED}", text)
    text = _JWT_PATTERN.sub("[REDACTED_JWT]", text)
    text = _LONG_HEX_SECRET_PATTERN.sub("[REDACTED_HEX]", text)
    text = _EMAIL_PATTERN.sub(_mask_email, text)
    return text


def redact_data(value: Any) -> Any:
    """Recursively redact JSON-compatible values."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): REDACTED
            if _SENSITIVE_KEY_PATTERN.fullmatch(str(key))
            else redact_data(item)
            for key, item in value.items()
        }
    return value

