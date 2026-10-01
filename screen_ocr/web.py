"""Local web page to browse, classify and delete saved captures.

Stdlib only. Binds to 127.0.0.1, and rejects foreign Host/Origin headers so
other websites open in your browser can't read or wipe your history. To reach
it from other devices, put `tailscale serve` in front and pass its hostname as
--allow-host: only your tailnet can get through, and the same checks apply.
"""

import base64
import binascii
import io
import json
import os
import re
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image, UnidentifiedImageError

from . import romanize, store

PAGE = os.path.join(os.path.dirname(__file__), "web.html")
_IMAGE_NAME = re.compile(r"^\d+\.png$")
_CAPTURE_PATH = re.compile(r"^/api/captures/(\d+)$")
MAX_BODY = 32 * 1024 * 1024  # a capture with its screenshot, base64-encoded
LOCAL_HOSTS = ("127.0.0.1", "localhost")
# Bumped when the API changes, so a page newer than the running server can say
# "restart" instead of failing on endpoints the old process doesn't know.
API_VERSION = 3


class Handler(BaseHTTPRequestHandler):
    server_version = "screen-ocr"
    allowed_hosts = LOCAL_HOSTS  # serve() adds the --allow-host names

    def log_message(self, fmt, *args):  # quiet by default
        pass

    # --- guards -------------------------------------------------------------

    def _trusted(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        if host not in self.allowed_hosts:
            return False
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in self.allowed_hosts:
            return False
        return True

    def _json_body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return None
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return None
        try:
            return json.loads(self.rfile.read(length) or b"null")
        except ValueError:
            return None

    # --- responses ----------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200):
        self._send(status, json.dumps(data).encode(), "application/json")

    def _error(self, status: int, message: str):
        self._json({"error": message}, status)

    # --- routes -------------------------------------------------------------

    def do_GET(self):
        if not self._trusted():
            return self._error(403, "forbidden")
        url = urlparse(self.path)
        if url.path == "/":
            with open(PAGE, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if url.path == "/api/captures":
            qs = parse_qs(url.query)
            query = qs.get("q", [""])[0]
            category = qs["category"][0] if "category" in qs else None
            label = qs["label"][0] if "label" in qs else None
            return self._json({
                "api": API_VERSION,
                "captures": store.search(query, category, label),
                "categories": store.categories(),
                "labels": store.labels(),
                "missing": romanize.missing(),
            })
        if url.path.startswith("/images/"):
            name = url.path[len("/images/"):]
            path = os.path.join(store.IMAGE_DIR, name)
            if _IMAGE_NAME.match(name) and os.path.isfile(path):
                with open(path, "rb") as f:
                    return self._send(200, f.read(), "image/png")
        self._error(404, "not found")

    def do_PATCH(self):
        if not self._trusted():
            return self._error(403, "forbidden")
        m = _CAPTURE_PATH.match(urlparse(self.path).path)
        body = self._json_body()
        if not m or not isinstance(body, dict) or not isinstance(body.get("category"), str):
            return self._error(400, "expected {\"category\": str}")
        store.set_category(int(m.group(1)), body["category"].strip())
        self._json({"ok": True})

    def do_POST(self):
        if not self._trusted():
            return self._error(403, "forbidden")
        body = self._json_body()
        path = urlparse(self.path).path
        if not isinstance(body, dict):
            return self._error(400, "expected a JSON object")
        if path == "/api/captures":  # from `screen-ocr --server` on another machine
            return self._add(body)
        if path == "/api/captures/delete":
            ids = [i for i in body.get("ids", []) if isinstance(i, int)]
            return self._json({"deleted": store.delete(ids)})
        if path == "/api/captures/category":
            changes = body.get("changes")
            if not isinstance(changes, list) or not all(
                    isinstance(c, dict) and isinstance(c.get("id"), int) and isinstance(c.get("category"), str)
                    for c in changes):
                return self._error(400, "expected {\"changes\": [{\"id\": int, \"category\": str}]}")
            store.set_categories([(c["id"], c["category"].strip()) for c in changes])
            return self._json({"ok": True})
        if path == "/api/captures/labels":
            changes = body.get("changes")
            if not isinstance(changes, list) or not all(
                    isinstance(c, dict) and isinstance(c.get("id"), int) and isinstance(c.get("labels"), list)
                    and all(isinstance(label, str) for label in c["labels"])
                    for c in changes):
                return self._error(400, "expected {\"changes\": [{\"id\": int, \"labels\": [str]}]}")
            try:
                cleaned = [(c["id"], store.clean_labels(c["labels"])) for c in changes]
            except ValueError as err:
                return self._error(400, str(err))
            store.set_labels(cleaned)
            return self._json({"ok": True})
        if path == "/api/categories/rename":
            old, new = body.get("from"), body.get("to")
            if not isinstance(old, str) or not isinstance(new, str):
                return self._error(400, "expected {\"from\": str, \"to\": str}")
            return self._json({"ids": store.rename_category(old, new.strip())})
        self._error(404, "not found")

    def _add(self, body: dict):
        text, category, created_at = body.get("text"), body.get("category", ""), body.get("created_at")
        if (not isinstance(text, str) or not text.strip() or not isinstance(category, str)
                or not isinstance(created_at, (int, float)) or isinstance(created_at, bool)):
            return self._error(400, "expected {\"text\": str, \"category\": str, \"created_at\": number, \"image\": base64 PNG or null}")
        image = None
        if body.get("image"):
            try:
                image = Image.open(io.BytesIO(base64.b64decode(body["image"], validate=True)))
                image.load()
            except (binascii.Error, TypeError, UnidentifiedImageError, OSError):
                return self._error(400, "image is not a base64 PNG")
        self._json({"id": store.add(text, image, category.strip(), float(created_at))})


def serve(port: int, open_browser: bool = True, allow_hosts: tuple = ()) -> None:
    Handler.allowed_hosts = LOCAL_HOSTS + tuple(h.lower().rstrip(".") for h in allow_hosts)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"screen-ocr history at {url}  (data in {store.DATA_DIR}), Ctrl+C to quit")
    for host in allow_hosts:
        print(f"  also answering as {host} (e.g. through `tailscale serve {port}`)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
