"""Cloud Tasks emulator manage actions (local gRPC)."""

from __future__ import annotations

from typing import Any

import observe


def _client():
    try:
        import grpc
        from google.cloud import tasks_v2
        from google.cloud.tasks_v2.services.cloud_tasks.transports import CloudTasksGrpcTransport
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-tasks is not installed; install it to manage Cloud Tasks from the control panel"
        ) from exc

    port = observe.cloudtasks_host_port()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    transport = CloudTasksGrpcTransport(channel=channel)
    return tasks_v2.CloudTasksClient(transport=transport), channel


def _parent_queue(payload: dict[str, Any]) -> str:
    queue = str(payload.get("queue", "")).strip()
    if not queue:
        raise ValueError("Queue name is required")
    if queue.startswith("projects/"):
        return queue
    pid = observe.project_id()
    location = observe.tasks_location()
    return f"projects/{pid}/locations/{location}/queues/{queue}"


def create_queue(payload: dict[str, Any]) -> dict[str, Any]:
    queue = str(payload.get("queue", "")).strip()
    if not queue:
        raise ValueError("Queue name is required")
    client, channel = _client()
    try:
        pid = observe.project_id()
        location = observe.tasks_location()
        parent = f"projects/{pid}/locations/{location}"
        short = queue.split("/")[-1]
        created = client.create_queue(
            request={
                "parent": parent,
                "queue": {"name": f"{parent}/queues/{short}"},
            }
        )
        return {"name": created.name}
    finally:
        channel.close()


def purge_queue(payload: dict[str, Any]) -> dict[str, Any]:
    queue_name = _parent_queue(payload)
    client, channel = _client()
    try:
        client.purge_queue(request={"name": queue_name})
        return {"purged": queue_name}
    finally:
        channel.close()


def create_task(payload: dict[str, Any]) -> dict[str, Any]:
    queue_name = _parent_queue(payload)
    url = str(payload.get("url", "")).strip()
    body = payload.get("body")
    if not url:
        raise ValueError("HTTP target URL is required")
    client, channel = _client()
    try:
        from google.cloud import tasks_v2

        http_request: dict[str, Any] = {"http_method": tasks_v2.HttpMethod.POST, "url": url}
        if body is not None:
            http_request["body"] = str(body).encode("utf-8")
        task = client.create_task(
            request={
                "parent": queue_name,
                "task": {"http_request": http_request},
            }
        )
        return {"name": task.name}
    finally:
        channel.close()


def delete_task(payload: dict[str, Any]) -> dict[str, Any]:
    task_name = str(payload.get("task", "")).strip()
    if not task_name:
        raise ValueError("Full task name is required")
    client, channel = _client()
    try:
        client.delete_task(request={"name": task_name})
        return {"deleted": task_name}
    finally:
        channel.close()
