"""Fullscreen dimmed snapshot where the user drags a box."""

import os
import subprocess
import sys
import tkinter as tk
from typing import Callable, Optional

from PIL import Image, ImageEnhance, ImageTk

from .capture import Shot

ACCENT = "#4cc2ff"
MIN_SIZE = 4


class RegionSelector:
    def __init__(self, root: tk.Tk, shot: Shot, on_done: Callable[[Optional[Image.Image]], None]):
        self.shot = shot
        self.on_done = on_done
        self.start = None
        self.rect = None
        self.label = None
        self.done = False

        win = self.win = tk.Toplevel(root)
        win.overrideredirect(True)
        # Any frame shown without the snapshot (mapping, teardown) is dark, not Tk's light grey.
        win.configure(bg="black")
        win.geometry(f"{shot.width}x{shot.height}+{shot.left}+{shot.top}")
        win.attributes("-topmost", True)

        preview = shot.image
        if preview.size != (shot.width, shot.height):
            preview = preview.resize((shot.width, shot.height), Image.BILINEAR)
        self.photo = ImageTk.PhotoImage(ImageEnhance.Brightness(preview).enhance(0.5))

        c = self.canvas = tk.Canvas(
            win, width=shot.width, height=shot.height, highlightthickness=0, cursor="crosshair",
            bg="black",
        )
        c.pack(fill="both", expand=True)
        c.create_image(0, 0, anchor="nw", image=self.photo)
        c.create_text(
            shot.width // 2, 28,
            text="Drag to select text  ·  Esc to cancel",
            fill="white", font=("Helvetica", 14),
        )

        c.bind("<ButtonPress-1>", self._press)
        c.bind("<B1-Motion>", self._drag)
        c.bind("<ButtonRelease-1>", self._release)
        c.bind("<ButtonPress-3>", lambda _e: self._finish(None))
        win.bind("<Escape>", lambda _e: self._finish(None))

        win.after(30, self._take_focus)

    def _take_focus(self):
        self.win.lift()
        self.win.focus_force()
        self.canvas.focus_set()
        if sys.platform == "darwin":
            # A freshly spawned python process isn't the frontmost app, so the
            # overlay wouldn't get key events (Esc) without this nudge.
            script = (
                'tell application "System Events" to set frontmost of '
                f"(first process whose unix id is {os.getpid()}) to true"
            )
            subprocess.Popen(["osascript", "-e", script],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.win.grab_set_global()
        except tk.TclError:
            pass

    def _press(self, e):
        self.start = (e.x, e.y)
        self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline=ACCENT, width=2)
        self.label = self.canvas.create_text(e.x, e.y - 10, anchor="sw", fill=ACCENT,
                                             font=("Helvetica", 11))

    def _drag(self, e):
        if not self.start:
            return
        x0, y0 = self.start
        self.canvas.coords(self.rect, x0, y0, e.x, e.y)
        self.canvas.coords(self.label, min(x0, e.x), min(y0, e.y) - 4)
        self.canvas.itemconfigure(self.label, text=f"{abs(e.x - x0)} × {abs(e.y - y0)}")

    def _release(self, e):
        if not self.start:
            return
        x0, y0 = self.start
        left, right = sorted((x0, e.x))
        top, bottom = sorted((y0, e.y))
        if right - left < MIN_SIZE or bottom - top < MIN_SIZE:
            self._finish(None)
            return
        s = self.shot.scale
        box = (int(left * s), int(top * s), int(right * s), int(bottom * s))
        self._finish(self.shot.image.crop(box))

    def _finish(self, image: Optional[Image.Image]):
        if self.done:  # update() below can deliver a queued Esc/click
            return
        self.done = True
        try:
            self.win.grab_release()
        except tk.TclError:
            pass
        # Unmap the whole overlay in one go and flush it to the display before
        # tearing down widgets or blocking on OCR. Otherwise the canvas can be
        # destroyed first, exposing the bare toplevel (or the compositor keeps a
        # stale frame) while recognize() holds the event loop.
        self.win.withdraw()
        self.win.update()
        self.win.destroy()
        self.on_done(image)
