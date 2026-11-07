"""Standard-library HTTP server: a small JSON API plus the static web client.

Every write command runs under one lock, so the game has a single writer.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from prototype.engine import Game, NotFound
from prototype.llm import LLMError

STATIC_DIR = Path(__file__).with_name("static")
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
}
MAX_BODY_BYTES = 64 * 1024
LETTER_READ_PATH = re.compile(r"/api/letters/([\w-]+)/read")


def make_handler(game: Game, *, dev: bool = False) -> type[BaseHTTPRequestHandler]:
    """Build the request handler.

    The developer view carries every NPC's secret, so it needs both a server started
    with `dev=True` and a request that asks for it with `?debug=1`. A client cannot
    turn it on by itself.
    """
    write_lock = threading.Lock()

    def snapshot(debug: bool) -> dict:
        return game.snapshot(game.current_world(), include_debug=debug)

    def with_state(result: Any, debug: bool) -> dict:
        return {"result": result, "state": snapshot(debug)}

    class Handler(BaseHTTPRequestHandler):
        server_version = "MarginaliaPrototype/0.1"
        dev_enabled = dev

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/state":
                debug = self._wants_debug()
                self._run(lambda: snapshot(debug), write=False)
            elif path in ("/", "/index.html"):
                self._static("index.html")
            elif path.startswith("/static/"):
                self._static(path[len("/static/") :])
            else:
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            world = game.current_world
            debug = self._wants_debug()
            letter = LETTER_READ_PATH.fullmatch(path)
            if path == "/api/session":
                action = lambda: with_state(game.open_session(world()), debug)
            elif path == "/api/message":
                action = lambda: with_state(
                    game.send_message(world(), str(body.get("text", "")), body.get("client_id")), debug
                )
            elif path == "/api/advance":
                action = lambda: with_state(game.advance_slot(world()), debug)
            elif path == "/api/dev/away":
                action = lambda: with_state(game.simulate_absence(world(), _int(body.get("days"), 1)), debug)
            elif path == "/api/world/new":
                action = lambda: with_state({"world_id": game.new_world()}, debug)
            elif letter is not None:
                action = lambda: with_state(game.read_letter(world(), letter.group(1)), debug)
            else:
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            self._run(action, write=True)

        def _wants_debug(self) -> bool:
            return dev and parse_qs(urlparse(self.path).query).get("debug") == ["1"]

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

        def _run(self, action: Callable[[], Any], *, write: bool) -> None:
            try:
                if write:
                    with write_lock:
                        payload = action()
                else:
                    payload = action()
            except LLMError as exc:
                self._send_json({"error": f"模型调用失败：{exc}"}, HTTPStatus.BAD_GATEWAY)
            except NotFound as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception:
                traceback.print_exc()
                self._send_json({"error": "服务器内部错误，详见终端日志"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                self._send_json(payload)

        def _read_json(self) -> dict:
            length = int(self.headers.get("content-length") or 0)
            if length > MAX_BODY_BYTES:
                raise ValueError("request body is too large")
            if length == 0:
                return {}
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("request body must be a JSON object")
            return value

        def _static(self, name: str) -> None:
            root = STATIC_DIR.resolve()
            target = (root / name).resolve()
            if root not in target.parents or not target.is_file():
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            self._send(target.read_bytes(), CONTENT_TYPES.get(target.suffix, "application/octet-stream"))

        def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8", status)

        def _send(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(body)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def serve(game: Game, host: str = "127.0.0.1", port: int = 8765, *, dev: bool = False) -> None:
    game.current_world()
    httpd = ThreadingHTTPServer((host, port), make_handler(game, dev=dev))
    print(f"Marginalia prototype: http://{host}:{port}  (model: {game.provider.label})", flush=True)
    if dev:
        print("developer view enabled: ?debug=1 responses include NPC secrets", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
