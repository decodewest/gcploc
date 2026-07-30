"""Fake GCS manage actions (local REST)."""

from __future__ import annotations

import urllib.parse
from typing import Any

import observe

from . import http as manage_http


def _base() -> str:
    port = observe.gcs_host_port()
    return f"http://127.0.0.1:{port}/storage/v1"


def create_bucket(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("Bucket name is required")
    project = observe.project_id()
    url = f"{_base()}/b?{urllib.parse.urlencode({'project': project})}"
    ok, data, err = manage_http.http_json_method("POST", url, body={"name": name})
    if not ok:
        raise RuntimeError(err or "create_bucket failed")
    return data if isinstance(data, dict) else {"name": name}


def delete_bucket(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("Bucket name is required")
    quoted = urllib.parse.quote(name, safe="")
    url = f"{_base()}/b/{quoted}"
    ok, data, err = manage_http.http_json_method("DELETE", url, body=None)
    if not ok:
        raise RuntimeError(err or "delete_bucket failed")
    return data if isinstance(data, dict) else {"deleted": name}


def upload_object(payload: dict[str, Any]) -> dict[str, Any]:
    bucket = str(payload.get("bucket", "")).strip()
    name = str(payload.get("name", "")).strip()
    content = payload.get("content")
    if not bucket or not name:
        raise ValueError("Bucket and object name are required")
    if content is None:
        raise ValueError("Content is required")
    body = content if isinstance(content, bytes) else str(content).encode("utf-8")
    bucket_q = urllib.parse.quote(bucket, safe="")
    query = urllib.parse.urlencode({"uploadType": "media", "name": name})
    port = observe.gcs_host_port()
    url = f"http://127.0.0.1:{port}/upload/storage/v1/b/{bucket_q}/o?{query}"
    ok, data, err = manage_http.http_json_method(
        "POST",
        url,
        body=body,
        content_type="application/octet-stream",
    )
    if not ok:
        raise RuntimeError(err or "upload_object failed")
    return data if isinstance(data, dict) else {"bucket": bucket, "name": name}


def delete_object(payload: dict[str, Any]) -> dict[str, Any]:
    bucket = str(payload.get("bucket", "")).strip()
    name = str(payload.get("name", "")).strip()
    if not bucket or not name:
        raise ValueError("Bucket and object name are required")
    bucket_q = urllib.parse.quote(bucket, safe="")
    object_q = urllib.parse.quote(name, safe="")
    url = f"{_base()}/b/{bucket_q}/o/{object_q}"
    ok, data, err = manage_http.http_json_method("DELETE", url, body=None)
    if not ok:
        raise RuntimeError(err or "delete_object failed")
    return data if isinstance(data, dict) else {"deleted": name}
