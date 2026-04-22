#!/usr/bin/env python3
"""Lightweight gcploc dashboard backend with SSE and status snapshot endpoints."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
        "quickCmd": "gcploc logs fakegcs",
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


def snapshot() -> dict:
    return {
        "timestamp": int(time.time()),
        "services": get_gcploc_services(),
        "dependents": get_dependents(),
    }


def get_container_logs(container_id: str, tail: int = 100) -> tuple[int, str, str]:
    """Fetch logs for a container. Returns (status_code, container_full_name, logs_text)."""
    # Find full container name from SERVICE_META by container id
    full_name = None
    for fname, meta in SERVICE_META.items():
        if meta["id"] == container_id or meta["container"] == container_id:
            full_name = fname
            break
    
    if not full_name:
        return 404, "", "Container not found"
    
    code, output = run_cmd(["docker", "logs", "--tail", str(tail), full_name])
    if code != 0:
        return 500, full_name, f"Error fetching logs: {output}"
    
    return 200, full_name, output


class Handler(BaseHTTPRequestHandler):
    def _json(self, status_code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True})
            return

        if self.path == "/api/status":
            self._json(200, snapshot())
            return

        if self.path == "/api/events":
            self._stream_events()
            return

        # Handle /api/logs/{container_id}
        if self.path.startswith("/api/logs/"):
            self._handle_logs()
            return

        self._json(404, {"error": "not found"})

    def _handle_logs(self):
        # Parse path: /api/logs/{container_id}?tail=100
        parsed_url = urllib.parse.urlparse(self.path)
        path_parts = parsed_url.path.strip("/").split("/")
        if len(path_parts) < 3:
            self._json(400, {"error": "invalid path"})
            return
        
        container_id = urllib.parse.unquote(path_parts[2])
        
        # Parse query params
        params = urllib.parse.parse_qs(parsed_url.query)
        tail = int(params.get("tail", ["100"])[0])
        
        status_code, container_name, logs = get_container_logs(container_id, tail)
        self._json(status_code, {
            "containerId": container_id,
            "containerName": container_name,
            "logs": logs,
            "timestamp": int(time.time()),
        })


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
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[gcploc-ui-api] Listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
