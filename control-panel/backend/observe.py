"""Read-only observation helpers for gcploc emulator resources and docker stats."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HTTP_TIMEOUT_SEC = 2.0

INSPECTABLE_IDS = frozenset({"gcs", "pubsub", "cloudtasks"})

_ENV_LOADED = False


def _gcploc_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def load_dotenv() -> None:
    """Load gcploc/.env into os.environ without overriding existing values."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_path = _gcploc_root() / ".env"
    if not env_path.is_file():
        _ENV_LOADED = True
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[key] = value
    _ENV_LOADED = True


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def project_id() -> str:
    return os.environ.get("GCPLOC_PROJECT_ID", "gcploc-local").strip() or "gcploc-local"


def tasks_location() -> str:
    return os.environ.get("GCPLOC_TASKS_LOCATION", "us-central1").strip() or "us-central1"


def gcs_host_port() -> int:
    return _env_int("GCPLOC_GCS_HOST_PORT", 4443)


def pubsub_host_port() -> int:
    return _env_int("GCPLOC_PUBSUB_HOST_PORT", 8085)


def cloudtasks_host_port() -> int:
    return _env_int("GCPLOC_CLOUDTASKS_HOST_PORT", 8123)


def http_json(url: str, timeout: float = HTTP_TIMEOUT_SEC) -> tuple[bool, Any, str | None]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except OSError:
            detail = str(exc)
        return False, None, f"HTTP {exc.code}: {detail}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, None, str(exc)
    if not body.strip():
        return True, None, None
    try:
        return True, json.loads(body), None
    except json.JSONDecodeError as exc:
        return False, None, f"Invalid JSON: {exc}"


def format_bytes(num: float | int) -> str:
    n = float(num)
    if n < 0:
        n = 0.0
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    idx = 0
    while n >= 1024.0 and idx < len(units) - 1:
        n /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(n)} {units[idx]}"
    return f"{n:.1f} {units[idx]}"


def _run_cmd(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(args, capture_output=True, text=True)
    out = (result.stdout or "").strip()
    if not out and result.stderr:
        out = result.stderr.strip()
    return result.returncode, out


def get_docker_stats(container_names: list[str]) -> dict[str, dict[str, str]]:
    docker = shutil.which("docker")
    if not docker or not container_names:
        return {}
    fmt = "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
    code, output = _run_cmd([docker, "stats", "--no-stream", "--format", fmt, *container_names])
    stats: dict[str, dict[str, str]] = {}
    if code != 0 or not output:
        return stats
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        name, cpu, mem = (p.strip() for p in parts)
        stats[name] = {"cpu": cpu, "memory": mem}
    return stats


def _err(summary: str = "—", **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "summary": summary}
    payload.update(extra)
    return payload


def observe_gcs(bucket: str | None = None, prefix: str = "", summary: bool = False) -> dict[str, Any]:
    port = gcs_host_port()
    base = f"http://127.0.0.1:{port}/storage/v1"
    if bucket is None:
        ok, data, err = http_json(f"{base}/b")
        if not ok:
            return _err("—", error=err)
        items = data.get("items") if isinstance(data, dict) else None
        buckets = [b.get("name") for b in items or [] if isinstance(b, dict) and b.get("name")]
        if summary:
            total_objects = 0
            total_bytes = 0
            for name in buckets:
                bq = urllib.parse.quote(name, safe="")
                ok_o, data_o, _err_o = http_json(f"{base}/b/{bq}/o")
                if not ok_o or not isinstance(data_o, dict):
                    continue
                for item in data_o.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    total_objects += 1
                    try:
                        total_bytes += int(item.get("size") or 0)
                    except (TypeError, ValueError):
                        pass
            n = len(buckets)
            summary_line = f"{n} bucket{'s' if n != 1 else ''} · {format_bytes(total_bytes)}"
            if total_objects:
                summary_line = (
                    f"{n} bucket{'s' if n != 1 else ''} · {total_objects} obj · {format_bytes(total_bytes)}"
                )
            return {
                "ok": True,
                "summary": summary_line,
                "bucketCount": n,
                "objectCount": total_objects,
                "totalBytes": total_bytes,
            }
        return {"ok": True, "summary": f"{len(buckets)} bucket(s)", "buckets": buckets}

    bucket_quoted = urllib.parse.quote(bucket, safe="")
    query = urllib.parse.urlencode({"prefix": prefix, "delimiter": "/"})
    ok, data, err = http_json(f"{base}/b/{bucket_quoted}/o?{query}")
    if not ok:
        return _err("—", error=err, bucket=bucket)
    items = data.get("items") if isinstance(data, dict) else None
    prefixes = data.get("prefixes") if isinstance(data, dict) else None
    objects = []
    for item in items or []:
        if isinstance(item, dict) and item.get("name"):
            objects.append(
                {
                    "name": item.get("name"),
                    "size": item.get("size"),
                    "updated": item.get("updated"),
                }
            )
    if summary:
        return {
            "ok": True,
            "summary": f"{len(objects)} object(s)",
            "bucket": bucket,
            "prefix": prefix,
            "objectCount": len(objects),
        }
    return {
        "ok": True,
        "summary": f"{len(objects)} object(s)",
        "bucket": bucket,
        "prefix": prefix,
        "objects": objects,
        "prefixes": list(prefixes or []),
    }


def observe_pubsub(summary: bool = False) -> dict[str, Any]:
    pid = project_id()
    port = pubsub_host_port()
    pid_quoted = urllib.parse.quote(pid, safe="")
    base = f"http://127.0.0.1:{port}/v1/projects/{pid_quoted}"
    ok_t, topics_data, err_t = http_json(f"{base}/topics")
    ok_s, subs_data, err_s = http_json(f"{base}/subscriptions")
    if not ok_t and not ok_s:
        return _err("—", error=err_t or err_s)
    topic_names = []
    if ok_t and isinstance(topics_data, dict):
        for t in topics_data.get("topics") or []:
            if isinstance(t, dict) and t.get("name"):
                topic_names.append(t["name"])
    sub_rows = []
    if ok_s and isinstance(subs_data, dict):
        for s in subs_data.get("subscriptions") or []:
            if isinstance(s, dict) and s.get("name"):
                sub_rows.append({"name": s["name"], "topic": s.get("topic") or ""})
    ns = len(sub_rows)
    nt = len(topic_names)
    summary_line = f"{nt} topic{'s' if nt != 1 else ''} · {ns} sub{'s' if ns != 1 else ''}"
    if summary:
        return {
            "ok": True,
            "summary": summary_line,
            "topicCount": nt,
            "subscriptionCount": ns,
        }
    return {
        "ok": True,
        "summary": summary_line,
        "topics": topic_names,
        "subscriptions": sub_rows,
        "partial": not (ok_t and ok_s),
    }


def _seeded_cloudtasks_queues() -> list[str]:
    defaults = ("default", "ai", "notifications-dispatch")
    keys = (
        "GCPLOC_TASKS_QUEUE_PRIMARY",
        "GCPLOC_TASKS_QUEUE_SECONDARY",
        "GCPLOC_TASKS_QUEUE_TERTIARY",
    )
    queues = []
    for key, default in zip(keys, defaults):
        val = os.environ.get(key, default).strip()
        queues.append(val or default)
    return queues


def _format_schedule_time(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    if isinstance(value, dict):
        secs = value.get("seconds")
        if secs is not None:
            return str(secs)
    return str(value)


def observe_cloudtasks(summary: bool = False) -> dict[str, Any]:
    port = cloudtasks_host_port()
    pid = project_id()
    location = tasks_location()
    parent = f"projects/{pid}/locations/{location}"

    try:
        import grpc
        from google.cloud import tasks_v2
        from google.cloud.tasks_v2.services.cloud_tasks.transports import CloudTasksGrpcTransport
    except ImportError:
        queues = _seeded_cloudtasks_queues()
        if summary:
            return {
                "ok": True,
                "summary": f"{len(queues)} queue(s) (seeded)",
                "queueCount": len(queues),
                "partial": True,
            }
        return {
            "ok": True,
            "summary": f"{len(queues)} queue(s) (seeded)",
            "queues": [{"name": q, "taskCount": None} for q in queues],
            "partial": True,
        }

    channel = None
    try:
        channel = grpc.insecure_channel(f"127.0.0.1:{port}")
        transport = CloudTasksGrpcTransport(channel=channel)
        client = tasks_v2.CloudTasksClient(transport=transport)
        queue_rows: list[dict[str, Any]] = []
        total_tasks = 0
        for queue in client.list_queues(request={"parent": parent}):
            qname = queue.name.rsplit("/", 1)[-1] if queue.name else ""
            task_rows: list[dict[str, Any]] = []
            q_count = 0
            if queue.name:
                try:
                    for task in client.list_tasks(request={"parent": queue.name}):
                        q_count += 1
                        if not summary:
                            task_rows.append(
                                {
                                    "name": task.name,
                                    "scheduleTime": _format_schedule_time(task.schedule_time),
                                    "dispatchCount": getattr(task, "dispatch_count", None),
                                }
                            )
                except Exception:
                    pass
            total_tasks += q_count
            queue_rows.append(
                {
                    "name": qname or queue.name,
                    "taskCount": q_count,
                    "tasks": None if summary else task_rows,
                }
            )
        nq = len(queue_rows)
        mid = "·"
        summary_line = f"{nq} queue{'s' if nq != 1 else ''} {mid} {total_tasks} task{'s' if total_tasks != 1 else ''}"
        if summary:
            return {
                "ok": True,
                "summary": summary_line,
                "queueCount": nq,
                "taskCount": total_tasks,
                "partial": False,
            }
        return {
            "ok": True,
            "summary": summary_line,
            "queues": queue_rows,
            "partial": False,
        }

    except Exception as exc:
        queues = _seeded_cloudtasks_queues()
        if summary:
            return {
                "ok": False,
                "summary": "—",
                "queueCount": len(queues),
                "partial": True,
                "error": str(exc),
            }
        return {
            "ok": False,
            "summary": "—",
            "queues": [{"name": q, "taskCount": None} for q in queues],
            "partial": True,
            "error": str(exc),
        }
    finally:
        if channel is not None:
            channel.close()


def observe_summaries(running_ids: set[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if "gcs" in running_ids:
        out["gcs"] = observe_gcs(summary=True)
    if "pubsub" in running_ids:
        out["pubsub"] = observe_pubsub(summary=True)
    if "cloudtasks" in running_ids:
        out["cloudtasks"] = observe_cloudtasks(summary=True)
    return out