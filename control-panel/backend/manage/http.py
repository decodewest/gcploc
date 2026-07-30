"""HTTP helpers for manage actions (non-GET)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import observe

HTTP_TIMEOUT_SEC = observe.HTTP_TIMEOUT_SEC


def http_json_method(
    method: str,
    url: str,
    body: dict[str, Any] | bytes | None = None,
    content_type: str | None = "application/json",
    timeout: float = HTTP_TIMEOUT_SEC,
) -> tuple[bool, Any, str | None]:
    data: bytes | None = None
    headers = {"Accept": "application/json"}
    if body is not None:
        if isinstance(body, dict):
            data = json.dumps(body).encode("utf-8")
            if content_type:
                headers["Content-Type"] = content_type
        elif isinstance(body, bytes):
            data = body
            if content_type:
                headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except OSError:
            detail = str(exc)
        return False, None, f"HTTP {exc.code}: {detail}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, None, str(exc)
    if not raw.strip():
        return True, None, None
    try:
        return True, json.loads(raw), None
    except json.JSONDecodeError:
        return True, raw, None
