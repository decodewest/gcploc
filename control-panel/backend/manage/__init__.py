"""Scoped local emulator management for the control panel."""

from __future__ import annotations

from typing import Any

from . import cloudtasks, gcs, pubsub
from .types import ActionSpec

MANAGEABLE_IDS = frozenset({"gcs", "pubsub", "cloudtasks"})

_ACTIONS: dict[str, dict[str, ActionSpec]] = {
    "gcs": {
        "create_bucket": ActionSpec(
            id="create_bucket",
            label="Create bucket",
            handler=gcs.create_bucket,
            fields=[
                {"name": "name", "label": "Bucket name", "type": "text", "required": True},
            ],
        ),
        "delete_bucket": ActionSpec(
            id="delete_bucket",
            label="Delete bucket",
            handler=gcs.delete_bucket,
            destructive=True,
            confirm_field="name",
            fields=[
                {"name": "name", "label": "Bucket name", "type": "text", "required": True},
            ],
        ),
        "upload_object": ActionSpec(
            id="upload_object",
            label="Upload object",
            handler=gcs.upload_object,
            fields=[
                {"name": "bucket", "label": "Bucket", "type": "text", "required": True},
                {"name": "name", "label": "Object name", "type": "text", "required": True},
                {"name": "content", "label": "Content", "type": "textarea", "required": True},
            ],
        ),
        "delete_object": ActionSpec(
            id="delete_object",
            label="Delete object",
            handler=gcs.delete_object,
            destructive=True,
            confirm_field="name",
            fields=[
                {"name": "bucket", "label": "Bucket", "type": "text", "required": True},
                {"name": "name", "label": "Object name", "type": "text", "required": True},
            ],
        ),
    },
    "pubsub": {
        "create_topic": ActionSpec(
            id="create_topic",
            label="Create topic",
            handler=pubsub.create_topic,
            fields=[
                {"name": "name", "label": "Topic name", "type": "text", "required": True},
            ],
        ),
        "delete_topic": ActionSpec(
            id="delete_topic",
            label="Delete topic",
            handler=pubsub.delete_topic,
            destructive=True,
            confirm_field="name",
            fields=[
                {"name": "name", "label": "Topic name", "type": "text", "required": True},
            ],
        ),
        "create_subscription": ActionSpec(
            id="create_subscription",
            label="Create subscription",
            handler=pubsub.create_subscription,
            fields=[
                {"name": "name", "label": "Subscription name", "type": "text", "required": True},
                {"name": "topic", "label": "Topic (name or full path)", "type": "text", "required": True},
            ],
        ),
        "delete_subscription": ActionSpec(
            id="delete_subscription",
            label="Delete subscription",
            handler=pubsub.delete_subscription,
            destructive=True,
            confirm_field="name",
            fields=[
                {"name": "name", "label": "Subscription name", "type": "text", "required": True},
            ],
        ),
        "publish": ActionSpec(
            id="publish",
            label="Publish message",
            handler=pubsub.publish,
            fields=[
                {"name": "topic", "label": "Topic (name or full path)", "type": "text", "required": True},
                {"name": "data", "label": "Message data", "type": "textarea", "required": True},
            ],
        ),
    },
    "cloudtasks": {
        "create_queue": ActionSpec(
            id="create_queue",
            label="Create queue",
            handler=cloudtasks.create_queue,
            fields=[
                {"name": "queue", "label": "Queue name", "type": "text", "required": True},
            ],
        ),
        "purge_queue": ActionSpec(
            id="purge_queue",
            label="Purge queue",
            handler=cloudtasks.purge_queue,
            destructive=True,
            confirm_field="queue",
            fields=[
                {"name": "queue", "label": "Queue name", "type": "text", "required": True},
            ],
        ),
        "create_task": ActionSpec(
            id="create_task",
            label="Create HTTP task",
            handler=cloudtasks.create_task,
            fields=[
                {"name": "queue", "label": "Queue name", "type": "text", "required": True},
                {"name": "url", "label": "Target URL", "type": "text", "required": True},
                {"name": "body", "label": "HTTP body (optional)", "type": "textarea", "required": False},
            ],
        ),
        "delete_task": ActionSpec(
            id="delete_task",
            label="Delete task",
            handler=cloudtasks.delete_task,
            destructive=True,
            confirm_field="task",
            fields=[
                {"name": "task", "label": "Full task name", "type": "text", "required": True},
            ],
        ),
    },
}


def capabilities() -> dict[str, Any]:
    services: dict[str, Any] = {}
    for service_id in sorted(MANAGEABLE_IDS):
        actions = _ACTIONS.get(service_id, {})
        services[service_id] = {
            "actions": [
                {
                    "id": spec.id,
                    "label": spec.label,
                    "destructive": spec.destructive,
                    "confirmField": spec.confirm_field,
                    "fields": spec.fields,
                }
                for spec in actions.values()
            ],
        }
    return {"services": services}


def invoke(service_id: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if service_id not in MANAGEABLE_IDS:
        return {"ok": False, "error": "Service is not manageable from the control panel"}
    actions = _ACTIONS.get(service_id, {})
    spec = actions.get(action)
    if spec is None:
        return {"ok": False, "error": f"Unknown action: {action}"}
    if spec.destructive:
        confirm_field = spec.confirm_field or "name"
        expected = payload.get(confirm_field)
        typed = payload.get("confirm")
        if expected is None or str(typed) != str(expected):
            return {"ok": False, "error": "Confirmation does not match the required resource identifier"}
    try:
        result = spec.handler(payload)
        return {"ok": True, "result": result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
