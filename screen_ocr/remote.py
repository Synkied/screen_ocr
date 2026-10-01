"""Send captures to a history kept on another machine (e.g. a Raspberry Pi on Tailscale).

A capture that can't be sent waits in an outbox next to the local history and goes
out, oldest first, with the next capture or the hotkey listener's periodic retry.
The server ignores a capture it already has, so sending one twice is harmless.
"""

import base64
import io
import json
import os
import sys
import time
import urllib.request
import uuid
from typing import Optional

from .store import data_dir

OUTBOX = os.path.join(data_dir(), "outbox")
TIMEOUT = 10  # seconds; runs after the clipboard copy, so nobody is waiting on it


def server_url(server: str) -> str:
    """rpi.tailnet.ts.net -> https://rpi.tailnet.ts.net: a bare name means HTTPS, as tailscale serve speaks."""
    server = server.strip().rstrip("/")
    return server if "://" in server else "https://" + server


def _post(server: str, payload: dict) -> None:
    req = urllib.request.Request(
        server_url(server) + "/api/captures",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        resp.read()


def flush(server: str) -> int:
    """Send what's waiting in the outbox; stops at the first failure. Returns how many went."""
    try:
        names = sorted(n for n in os.listdir(OUTBOX) if n.endswith(".json"))
    except FileNotFoundError:
        return 0
    sent = 0
    for name in names:
        path = os.path.join(OUTBOX, name)
        claimed = path + ".sending"  # another screen-ocr process may be flushing too
        try:
            os.rename(path, claimed)
        except FileNotFoundError:
            continue
        try:
            with open(claimed, encoding="utf-8") as f:
                _post(server, json.load(f))
        except Exception as e:  # noqa: BLE001 - leave it for next time
            os.rename(claimed, path)
            print(f"history server unreachable, {len(names) - sent} capture(s) waiting: {e}", file=sys.stderr)
            break
        os.remove(claimed)
        sent += 1
    return sent


def send(server: str, text: str, image, category: str) -> None:
    """Send one capture, after anything older still waiting; queue it if that fails."""
    payload = {"text": text, "category": category, "created_at": time.time(), "image": _png(image)}
    os.makedirs(OUTBOX, exist_ok=True)
    name = f"{payload['created_at']:017.6f}-{uuid.uuid4().hex[:8]}.json"
    tmp = os.path.join(OUTBOX, name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(OUTBOX, name))
    flush(server)


def _png(image) -> Optional[str]:
    if image is None:
        return None
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
