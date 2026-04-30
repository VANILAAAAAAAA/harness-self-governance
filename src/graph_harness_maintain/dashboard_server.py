from __future__ import annotations

import json
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from .dashboard import build_dashboard_data, build_dashboard


class LiveDashboardHandler(SimpleHTTPRequestHandler):
    """Local read-only dashboard server with live graph refresh endpoints."""

    repo_root: Path = Path.cwd()
    dashboard_out: Path = Path("artifacts/v2/dashboard/index.html")

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        try:
            if parsed.path in {"/", "/index.html", "/dashboard", "/dashboard/"}:
                result = build_dashboard(self.repo_root, self.dashboard_out)
                html = self.dashboard_out.read_text(encoding="utf-8")
                self._send_html(html, HTTPStatus.OK if result.get("status") == "PASS" else HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            if parsed.path == "/api/dashboard-data":
                data = build_dashboard_data(self.repo_root)
                self._send_json(data)
                return
            if parsed.path == "/api/status":
                data = build_dashboard_data(self.repo_root)
                self._send_json({
                    "status": "PASS",
                    "dashboard_signature": data.get("dashboard_signature"),
                    "node_count": len(data.get("graph", {}).get("nodes", [])),
                    "edge_count": len(data.get("graph", {}).get("edges", [])),
                    "projects": [
                        {"profile_id": item.get("profile_id"), "project_id": item.get("project_id"), "title": item.get("title")}
                        for item in data.get("projects", {}).get("manifests", [])
                    ],
                })
                return
        except Exception as exc:  # keep server observable instead of crashing request thread
            self._send_json({"status": "FAIL", "error": type(exc).__name__, "message": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        super().do_GET()


def serve_dashboard(repo_root: Path | str, host: str = "127.0.0.1", port: int = 8767, out: Path | str | None = None) -> ThreadingHTTPServer:
    repo_root = Path(repo_root).resolve()
    dashboard_out = Path(out).resolve() if out else repo_root / "artifacts" / "v2" / "dashboard" / "index.html"
    handler = type(
        "RepoLiveDashboardHandler",
        (LiveDashboardHandler,),
        {"repo_root": repo_root, "dashboard_out": dashboard_out, "directory": str(repo_root)},
    )
    server = ThreadingHTTPServer((host, port), handler)
    return server


def run_dashboard_server(repo_root: Path | str, host: str = "127.0.0.1", port: int = 8767, out: Path | str | None = None) -> None:
    server = serve_dashboard(repo_root, host=host, port=port, out=out)
    url = f"http://{host}:{port}/"
    print(json.dumps({"status": "PASS", "url": url, "api": f"{url}api/dashboard-data", "mode": "live_read_only"}, sort_keys=True))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
