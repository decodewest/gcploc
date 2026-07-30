#!/usr/bin/env python3
"""Lightweight gcploc dashboard backend with SSE and status snapshot endpoints."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import manage
import observe

HOST = "127.0.0.1"
PORT = 8787


SERVICE_META = {
    "gcploc_pubsub": {
        "id": "pubsub",
        "label": "Pub/Sub Emulator",
        "container": "pubsub",
        "port": 8085,
        "profile": "pubsub",
        "quickCmd": "gcploc logs pubsub",
    },
    "gcploc_fakegcs": {
        "id": "gcs",
        "label": "Fake GCS",
        "container": "fakegcs",
        "port": 4443,
        "profile": "gcs",
        "quickCmd": "gcploc logs gcs",
    },
    "gcploc_cloudtasks": {
        "id": "cloudtasks",
        "label": "Cloud Tasks Emulator",
        "container": "cloudtasks",
        "port": 8123,
        "profile": "cloudtasks",
        "quickCmd": "gcploc logs cloudtasks",
    },
    "gcploc_firestore": {
        "id": "firestore",
        "label": "Firestore Emulator",
        "container": "firestore",
        "port": 8080,
        "profile": "firestore",
        "quickCmd": "gcploc logs firestore",
    },
    "gcploc_spanner": {
        "id": "spanner",
        "label": "Cloud Spanner Emulator",
        "container": "spanner",
        "port": 9010,
        "profile": "spanner",
        "quickCmd": "gcploc logs spanner",
    },
    "gcploc_bigtable": {
        "id": "bigtable",
        "label": "Bigtable Emulator",
        "container": "bigtable",
        "port": 8086,
        "profile": "bigtable",
        "quickCmd": "gcploc logs bigtable",
    },
    "gcploc_secretmanager": {
        "id": "secretmanager",
        "label": "Secret Manager (Experimental)",
        "container": "secretmanager",
        "port": 4444,
        "profile": "secretmanager",
        "quickCmd": "gcploc logs secretmanager",
    },
}


def run_cmd(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, result.stdout.strip()


def run_cmd_merged(args: list[str]) -> tuple[int, str]:
    """Run a command merging stderr into stdout (needed for `docker logs`)."""
    result = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.returncode, (result.stdout or "").rstrip("\n")


def parse_status(status: str) -> str:
    lower = status.lower()
    if "unhealthy" in lower:
        return "degraded"
    if lower.startswith("up"):
        return "running"
    return "stopped"


def get_gcploc_services() -> list[dict]:
    code, output = run_cmd(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "label=com.docker.compose.project=gcploc",
            "--format",
            "{{.Names}}\t{{.Status}}",
        ]
    )

    rows: dict[str, str] = {}
    if code == 0 and output:
        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                rows[parts[0].strip()] = parts[1].strip()

    services = []
    for container_name, meta in SERVICE_META.items():
        status_text = rows.get(container_name, "not created")
        service = dict(meta)
        service["status"] = parse_status(status_text)
        service["dockerStatus"] = status_text
        services.append(service)
    return services


def get_dependents() -> list[str]:
    code, output = run_cmd(["docker", "network", "inspect", "gcploc_net", "--format", "{{json .Containers}}"])
    if code != 0 or not output or output == "null":
        return []

    try:
        raw = json.loads(output)
    except json.JSONDecodeError:
        return []

    names = []
    if isinstance(raw, dict):
        for data in raw.values():
            if isinstance(data, dict):
                name = data.get("Name")
                if isinstance(name, str):
                    names.append(name)

    gcploc_names = set(SERVICE_META.keys())
    return sorted(name for name in names if name not in gcploc_names)


def _running_inspectable_ids(services: list[dict]) -> set[str]:
    return {
        s["id"]
        for s in services
        if s.get("status") == "running" and s.get("id") in observe.INSPECTABLE_IDS
    }


def _service_running(service_id: str) -> bool:
    for service in get_gcploc_services():
        if service.get("id") == service_id:
            return service.get("status") == "running"
    return False


def snapshot() -> dict:
    services = get_gcploc_services()
    id_to_full = {meta["id"]: full for full, meta in SERVICE_META.items()}
    running_full = [
        id_to_full[s["id"]]
        for s in services
        if s.get("status") == "running" and s.get("id") in id_to_full
    ]
    docker_stats = observe.get_docker_stats(running_full)
    running_ids = _running_inspectable_ids(services)
    summaries = observe.observe_summaries(running_ids)
    return {
        "timestamp": int(time.time()),
        "services": services,
        "dependents": get_dependents(),
        "dockerStats": docker_stats,
        "summaries": summaries,
    }


def get_container_logs(container_id: str, tail: int = 100) -> tuple[int, str, str]:
    """Fetch logs for a container. Returns (status_code, container_full_name, logs_text)."""
    full_name = None
    for fname, meta in SERVICE_META.items():
        if meta["id"] == container_id or meta["container"] == container_id:
            full_name = fname
            break

    if not full_name:
        return 404, "", "Container not found"

    code, output = run_cmd_merged(["docker", "logs", "--tail", str(tail), full_name])
    if code != 0:
        return 500, full_name, f"Error fetching logs: {output or 'unknown error'}"

    return 200, full_name, output


def _query_flag(params: dict[str, list[str]], name: str) -> bool:
    raw = params.get(name, [""])[0].strip().lower()
    return raw in ("1", "true", "yes", "on")


def _observe_summaries_payload() -> dict:
    services = get_gcploc_services()
    running_ids = _running_inspectable_ids(services)
    return {
        "timestamp": int(time.time()),
        "summaries": observe.observe_summaries(running_ids),
    }


class Handler(BaseHTTPRequestHandler):
    def _json(self, status_code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self._json(200, {"ok": True})
            return

        if path == "/api/status":
            self._json(200, snapshot())
            return

        if path == "/api/events":
            self._stream_events()
            return

        if path == "/api/observe/summaries":
            self._json(200, _observe_summaries_payload())
            return

        if path == "/api/manage/capabilities":
            self._json(200, manage.capabilities())
            return

        if path == "/api/observe/gcs":
            params = urllib.parse.parse_qs(parsed.query)
            summary = _query_flag(params, "summary")
            bucket = params.get("bucket", [""])[0].strip() or None
            prefix = params.get("prefix", [""])[0]
            self._json(200, observe.observe_gcs(bucket=bucket, prefix=prefix, summary=summary))
            return

        if path == "/api/observe/pubsub":
            params = urllib.parse.parse_qs(parsed.query)
            summary = _query_flag(params, "summary")
            self._json(200, observe.observe_pubsub(summary=summary))
            return

        if path == "/api/observe/cloudtasks":
            params = urllib.parse.parse_qs(parsed.query)
            summary = _query_flag(params, "summary")
            self._json(200, observe.observe_cloudtasks(summary=summary))
            return

        if path.startswith("/api/logs/"):
            self._handle_logs(parsed)
            return

        self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/manage/"):
            self._handle_manage_post(parsed)
            return

        self._json(404, {"error": "not found"})

    def _handle_manage_post(self, parsed: urllib.parse.ParseResult):
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        # api, manage, {serviceId}, {action}
        if len(parts) < 4 or parts[0] != "api" or parts[1] != "manage":
            self._json(400, {"error": "invalid manage path"})
            return

        service_id = urllib.parse.unquote(parts[2])
        action = urllib.parse.unquote(parts[3])
        payload = self._read_json_body()

        if service_id not in manage.MANAGEABLE_IDS:
            self._json(404, {"ok": False, "error": "Service is not manageable"})
            return

        if not _service_running(service_id):
            self._json(409, {"ok": False, "error": "Service is not running"})
            return

        result = manage.invoke(service_id, action, payload)
        status = 200 if result.get("ok") else 400
        self._json(status, result)

    def _handle_logs(self, parsed: urllib.parse.ParseResult):
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 3:
            self._json(400, {"error": "invalid path"})
            return

        container_id = urllib.parse.unquote(path_parts[2])
        params = urllib.parse.parse_qs(parsed.query)
        tail = int(params.get("tail", ["100"])[0])

        status_code, container_name, logs = get_container_logs(container_id, tail)
        self._json(
            status_code,
            {
                "containerId": container_id,
                "containerName": container_name,
                "logs": logs,
                "timestamp": int(time.time()),
            },
        )

    def _stream_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        initial = json.dumps(snapshot())
        self.wfile.write(f"event: snapshot\ndata: {initial}\n\n".encode("utf-8"))
        self.wfile.flush()

        proc = subprocess.Popen(
            [
                "docker",
                "events",
                "--format",
                "{{json .}}",
                "--filter",
                "type=container",
                "--filter",
                "label=com.docker.compose.project=gcploc",
                "--filter",
                "event=start",
                "--filter",
                "event=stop",
                "--filter",
                "event=die",
                "--filter",
                "event=health_status",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        last_heartbeat = time.time()
        try:
            while True:
                line = proc.stdout.readline() if proc.stdout is not None else ""
                if line:
                    event_data = line.strip()
                    if event_data:
                        self.wfile.write(f"event: docker\ndata: {event_data}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    continue

                now = time.time()
                if now - last_heartbeat >= 15:
                    self.wfile.write(b"event: heartbeat\ndata: {}\n\n")
                    self.wfile.flush()
                    last_heartbeat = now
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()

    def log_message(self, fmt, *args):
        return


def main():
    observe.load_dotenv()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[gcploc-ui-api] Listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
