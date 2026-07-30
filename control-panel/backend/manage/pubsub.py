"""Pub/Sub emulator manage actions (local REST)."""

from __future__ import annotations

import base64
import urllib.parse
from typing import Any

import observe

from . import http as manage_http


def _project() -> str:
    return observe.project_id()


def _base_v1() -> str:
    port = observe.pubsub_host_port()
    pid = urllib.parse.quote(_project(), safe="")
    return f"http://127.0.0.1:{port}/v1/projects/{pid}"


def _topic_path(name: str) -> str:
    short = name.strip()
    if short.startswith("projects/"):
        return short
    return f"projects/{_project()}/topics/{short}"


def create_topic(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("Topic name is required")
    short = name.split("/")[-1]
    url = f"{_base_v1()}/topics/{urllib.parse.quote(short, safe='')}"
    ok, data, err = manage_http.http_json_method("PUT", url, body={})
    if not ok:
        raise RuntimeError(err or "create_topic failed")
    return data if isinstance(data, dict) else {"name": _topic_path(short)}


def delete_topic(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("Topic name is required")
    short = name.split("/")[-1]
    url = f"{_base_v1()}/topics/{urllib.parse.quote(short, safe='')}"
    ok, data, err = manage_http.http_json_method("DELETE", url, body=None)
    if not ok:
        raise RuntimeError(err or "delete_topic failed")
    return data if isinstance(data, dict) else {"deleted": short}


def create_subscription(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    topic = str(payload.get("topic", "")).strip()
    if not name or not topic:
        raise ValueError("Subscription name and topic are required")
    short = name.split("/")[-1]
    topic_path = _topic_path(topic)
    url = f"{_base_v1()}/subscriptions/{urllib.parse.quote(short, safe='')}"
    ok, data, err = manage_http.http_json_method("PUT", url, body={"topic": topic_path})
    if not ok:
        raise RuntimeError(err or "create_subscription failed")
    return data if isinstance(data, dict) else {"name": name, "topic": topic_path}


def delete_subscription(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("Subscription name is required")
    short = name.split("/")[-1]
    url = f"{_base_v1()}/subscriptions/{urllib.parse.quote(short, safe='')}"
    ok, data, err = manage_http.http_json_method("DELETE", url, body=None)
    if not ok:
        raise RuntimeError(err or "delete_subscription failed")
    return data if isinstance(data, dict) else {"deleted": short}


def publish(payload: dict[str, Any]) -> dict[str, Any]:
    topic = str(payload.get("topic", "")).strip()
    data_raw = payload.get("data")
    if not topic:
        raise ValueError("Topic is required")
    if data_raw is None:
        raise ValueError("Message data is required")
    short = topic.split("/")[-1]
    encoded = base64.b64encode(str(data_raw).encode("utf-8")).decode("ascii")
    url = f"{_base_v1()}/topics/{urllib.parse.quote(short, safe='')}:publish"
    ok, data, err = manage_http.http_json_method(
        "POST",
        url,
        body={"messages": [{"data": encoded}]},
    )
    if not ok:
        raise RuntimeError(err or "publish failed")
    return data if isinstance(data, dict) else {"topic": short}
