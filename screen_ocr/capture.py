"""Screenshot of the monitor under the cursor.

Returns the image in physical pixels plus the monitor rect in logical
(Tk) coordinates, so the overlay can map a selection back onto the image
on HiDPI / Retina screens.
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

from PIL import Image


class CaptureError(RuntimeError):
    pass


@dataclass
class Shot:
    image: Image.Image
    left: int
    top: int
    width: int
    height: int

    @property
    def scale(self) -> float:
        return self.image.width / self.width


def grab_at(x: int, y: int, screen_w: int, screen_h: int) -> Shot:
    if os.environ.get("WAYLAND_DISPLAY"):
        return _grab_wayland(screen_w, screen_h)
    return _grab_mss(x, y)


def _grab_mss(x: int, y: int) -> Shot:
    import mss

    with mss.mss() as sct:
        monitors = sct.monitors[1:] or sct.monitors
        mon = next(
            (
                m
                for m in monitors
                if m["left"] <= x < m["left"] + m["width"]
                and m["top"] <= y < m["top"] + m["height"]
            ),
            monitors[0],
        )
        raw = sct.grab(mon)
    image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    return Shot(image, mon["left"], mon["top"], mon["width"], mon["height"])


# X11-only libraries can't see Wayland windows; shell out to the
# compositor's screenshot tool instead.
_WAYLAND_TOOLS = [
    ("grim", lambda p: ["grim", p]),
    ("gnome-screenshot", lambda p: ["gnome-screenshot", "-f", p]),
    ("spectacle", lambda p: ["spectacle", "-b", "-n", "-f", "-o", p]),
]


def _grab_wayland(screen_w: int, screen_h: int) -> Shot:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "shot.png")
        for tool, cmd in _WAYLAND_TOOLS:
            if not shutil.which(tool):
                continue
            result = subprocess.run(cmd(path), capture_output=True)
            if result.returncode == 0 and os.path.exists(path):
                image = Image.open(path).convert("RGB")
                return Shot(image, 0, 0, screen_w, screen_h)
    raise CaptureError(
        "No working screenshot tool on Wayland. Install grim, gnome-screenshot or spectacle."
    )
