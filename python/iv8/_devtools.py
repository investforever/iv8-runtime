"""M9-1 internal DevTools / Inspector attach server (Python stdlib only).

A lazily-started, per-``Page`` localhost server providing the minimal Chrome
DevTools Protocol *discovery* endpoints (``/json/version``, ``/json``,
``/json/list``) plus a WebSocket endpoint that bridges CDP frames to the page's V8
Inspector session through the native dispatch callback. It is deliberately minimal:
a single page target, no message loop (only the synchronously-produced CDP
responses are relayed back), best-effort. It is NOT a public API — reached only
through ``Page.devtools_url()``. No third-party dependency; stdlib ``http.server``
+ a hand-rolled WebSocket handshake/frame codec.
"""

import base64
import hashlib
import json
import struct
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# RFC 6455 handshake GUID.
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _ws_recv(rfile):
    """Read one WebSocket frame. Returns (opcode, payload_bytes) or (None, None)."""
    header = rfile.read(2)
    if len(header) < 2:
        return None, None
    b2 = header[1]
    opcode = header[0] & 0x0F
    masked = bool(b2 & 0x80)
    length = b2 & 0x7F
    if length == 126:
        length = struct.unpack(">H", rfile.read(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", rfile.read(8))[0]
    mask = rfile.read(4) if masked else b""
    payload = rfile.read(length) if length else b""
    if masked:
        payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    return opcode, payload


def _ws_send(wfile, opcode, data):
    """Write one (unmasked, server->client) WebSocket frame."""
    header = bytearray([0x80 | opcode])
    n = len(data)
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header += struct.pack(">H", n)
    else:
        header.append(127)
        header += struct.pack(">Q", n)
    wfile.write(bytes(header) + data)
    wfile.flush()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence stderr access logging
        pass

    def _send_json(self, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=UTF-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        server = self.server.iv8_devtools
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self._handle_ws(server)
            return
        path = self.path.split("?", 1)[0].rstrip("/")
        ws_url = server.ws_url()
        if path == "/json/version":
            self._send_json(
                {
                    "Browser": "iv8/inspector",
                    "Protocol-Version": "1.3",
                    "webSocketDebuggerUrl": ws_url,
                }
            )
        elif path in ("/json", "/json/list"):
            self._send_json(
                [
                    {
                        "id": server.target_id,
                        "type": "page",
                        "title": "iv8 page",
                        "url": "about:blank",
                        "webSocketDebuggerUrl": ws_url,
                    }
                ]
            )
        else:
            self.send_error(404)

    def _handle_ws(self, server):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400)
            return
        accept = base64.b64encode(
            hashlib.sha1((key + _WS_GUID).encode("utf-8")).digest()
        ).decode("ascii")
        self.wfile.write(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode("ascii")
        )
        self.wfile.flush()
        self.close_connection = True  # we own the socket for the WS lifetime
        while True:
            try:
                opcode, payload = _ws_recv(self.rfile)
            except OSError:
                break
            if opcode is None or opcode == 0x8:  # EOF or close
                break
            if opcode == 0x1:  # text frame: a CDP message
                try:
                    frames = server.dispatch(payload.decode("utf-8"))
                except Exception:
                    break  # disposed / busy / bad message -> drop the connection
                try:
                    for frame in frames:
                        _ws_send(self.wfile, 0x1, frame.encode("utf-8"))
                except OSError:
                    break
            elif opcode == 0x9:  # ping -> pong
                try:
                    _ws_send(self.wfile, 0xA, payload)
                except OSError:
                    break


class DevToolsServer:
    """Owns the localhost discovery/WS server for one Page (daemon thread)."""

    def __init__(self, dispatch):
        # dispatch: callable(cdp_message_str) -> list[str] (native Inspector bridge)
        self._dispatch = dispatch
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._httpd.iv8_devtools = self
        self._port = self._httpd.server_address[1]
        self._target_id = uuid.uuid4().hex
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="iv8-devtools", daemon=True
        )
        self._thread.start()

    @property
    def target_id(self):
        return self._target_id

    def ws_url(self):
        return f"ws://127.0.0.1:{self._port}/devtools/page/{self._target_id}"

    def dispatch(self, message):
        return self._dispatch(message)

    def shutdown(self):
        try:
            self._httpd.shutdown()
            self._httpd.server_close()
        except Exception:
            pass
