"""
DESNWORLD local development API server (stdlib only).

This is a *local convenience* backend for the web interface during development
(`python -m desnworld.server`). It is NOT the production backend: GitHub Pages
is a static host and cannot run this. For public, interactive, on-demand
simulations you must deploy a real backend service (see README
"Deployment architecture and limitations").

Endpoints:
    GET  /api/health               -> {"status": "ok", ...}
    POST /api/generate             -> run the full pipeline   (request JSON)
    POST /api/expand               -> expand a branch          ({"report", "scenario_id"})
    POST /api/validate             -> validate a report        (report JSON)

CORS is intentionally open (`Access-Control-Allow-Origin: *`) because this
server binds to localhost for development only. A production backend must
restrict origins and add authentication.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple

from .config import Config
from .engine import ScenarioEngine
from .errors import EngineError
from .schema import ENGINE_VERSION, SCHEMA_VERSION, assert_valid_report, validate_report

logger = logging.getLogger("desnworld.server")


def _make_engine() -> ScenarioEngine:
    if Config.LLM_API_KEY:
        from .providers import OpenAIProvider

        return ScenarioEngine(OpenAIProvider())
    from .providers import MockScenarioProvider

    logger.warning(
        "LLM_API_KEY is not configured - serving MOCK scenario output. "
        "Content is illustrative only."
    )
    return ScenarioEngine(MockScenarioProvider())


class Handler(BaseHTTPRequestHandler):
    server_version = "DESNWORLDDevServer/" + ENGINE_VERSION
    engine: ScenarioEngine

    # -- plumbing -------------------------------------------------------

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter logs
        logger.info("%s - %s", self.address_string(), fmt % args)

    def _send(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 (stdlib naming)
        self._send(204, {})

    def _read_json(self) -> Optional[Dict[str, Any]]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._send(400, {"error": "empty_request", "message": "Request body is required."})
            return None
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._send(400, {"error": "invalid_json", "message": f"Body is not valid JSON: {exc}"})
            return None
        if not isinstance(payload, dict):
            self._send(400, {"error": "invalid_json", "message": "Body must be a JSON object."})
            return None
        return payload

    # -- routes ---------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("", "/api/health"):
            self._send(
                200,
                {
                    "status": "ok",
                    "engine_version": ENGINE_VERSION,
                    "schema_version": SCHEMA_VERSION,
                    "llm_configured": bool(Config.LLM_API_KEY),
                },
            )
            return
        self._send(404, {"error": "not_found", "message": f"Unknown path {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json()
        if payload is None:
            return
        path = self.path.rstrip("/")
        try:
            if path == "/api/generate":
                report = self.engine.generate(payload)
                self._send(200, {"report": report})
            elif path == "/api/expand":
                report = payload.get("report")
                scenario_id = payload.get("scenario_id")
                problems = validate_report(report)
                if problems:
                    self._send(
                        422,
                        {
                            "error": "schema_validation_error",
                            "message": "The supplied report is not valid.",
                            "problems": problems[:20],
                        },
                    )
                    return
                if not isinstance(scenario_id, str) or not scenario_id:
                    self._send(
                        400,
                        {"error": "input_validation_error", "message": "scenario_id is required."},
                    )
                    return
                expanded = self.engine.expand_branch(report, scenario_id)
                self._send(200, {"report": expanded})
            elif path == "/api/validate":
                problems = validate_report(payload.get("report", payload))
                self._send(200, {"valid": not problems, "problems": problems})
            else:
                self._send(404, {"error": "not_found", "message": f"Unknown path {self.path}"})
        except EngineError as exc:
            status = 422 if exc.code in ("input_validation_error", "schema_validation_error") else 502
            if exc.code == "missing_credentials":
                status = 503
            self._send(status, exc.to_payload())
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unhandled error")
            self._send(500, {"error": "internal_error", "message": str(exc)})


def create_server(host: Optional[str] = None, port: Optional[int] = None) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"engine": _make_engine()})
    return ThreadingHTTPServer((host or Config.DESNWORLD_HOST, port or Config.DESNWORLD_PORT), handler)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    server = create_server()
    host, port = server.server_address[:2]
    print(f"DESNWORLD dev API listening on http://{host}:{port}")
    print("Endpoints: GET /api/health, POST /api/generate, POST /api/expand, POST /api/validate")
    if not Config.LLM_API_KEY:
        print("NOTE: LLM_API_KEY is not set - the server will return MOCK output.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
