"""Entry point.

`screen-ocr` runs a hotkey listener. Each press spawns `screen-ocr --once`
in a fresh process, which keeps pynput and Tk out of each other's way
(both are picky about threads on macOS). `--once` can also be bound
directly to a desktop shortcut, which is the way to go on Wayland.

Every capture is also saved to a local history; `screen-ocr --web` opens a
page to browse, classify and delete it.
"""

import argparse
import os
import subprocess
import sys

DEFAULT_HOTKEY = "<ctrl>+<alt>+o"
DEFAULT_PORT = 8765
LOG_PATH = os.path.expanduser("~/.cache/screen-ocr.log")


def main() -> None:
    parser = argparse.ArgumentParser(prog="screen-ocr", description="Drag a box on screen, get its text in your clipboard.")
    parser.add_argument("--once", action="store_true",
                        help="select a region right now, OCR it, then exit")
    parser.add_argument("--hotkey", default=DEFAULT_HOTKEY,
                        help=f"global hotkey in pynput syntax (default: {DEFAULT_HOTKEY})")
    parser.add_argument("--lang", default="auto",
                        help="tesseract languages, e.g. eng+jpn or chi_sim "
                             "(default: auto = every installed language pack)")
    parser.add_argument("--no-save", action="store_true",
                        help="don't keep captures in the history")
    parser.add_argument("--web", action="store_true",
                        help="open the capture history in your browser")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"port for --web (default: {DEFAULT_PORT})")
    args = parser.parse_args()

    if args.web:
        from . import web
        web.serve(args.port)
        return

    # Launched from a desktop shortcut there's no terminal: keep errors somewhere.
    if not sys.stderr.isatty():
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        sys.stderr = open(LOG_PATH, "a", buffering=1)
        print(f"--- {' '.join(sys.argv)} | session={os.environ.get('XDG_SESSION_TYPE')}",
              file=sys.stderr)

    from . import ocr

    try:
        ocr.check_installed()
    except Exception:
        sys.exit("tesseract not found. Install it: `brew install tesseract` / `sudo apt install tesseract-ocr`")

    try:
        lang = ocr.resolve_lang(args.lang)
    except ocr.LanguageError as e:
        from . import output
        output.notify("Missing language pack", str(e))
        sys.exit(str(e))

    if args.once:
        run_once(lang, save=not args.no_save)
    else:
        run_daemon(args.hotkey, lang, save=not args.no_save)


def run_daemon(hotkey: str, lang: str, save: bool = True) -> None:
    if os.environ.get("WAYLAND_DISPLAY"):
        print("Wayland detected: global hotkeys don't work here.\n"
              "Bind `screen-ocr --once` to a shortcut in your desktop settings instead.",
              file=sys.stderr)

    from pynput import keyboard

    current = None

    def trigger():
        nonlocal current
        if current and current.poll() is None:
            return
        cmd = [sys.executable, "-m", "screen_ocr", "--once", "--lang", lang]
        if not save:
            cmd.append("--no-save")
        current = subprocess.Popen(cmd)

    print(f"screen-ocr ready: press {hotkey} to capture, Ctrl+C to quit")
    with keyboard.GlobalHotKeys({hotkey: trigger}) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            pass


def run_once(lang: str, save: bool = True) -> None:
    try:
        import tkinter as tk
    except ImportError:
        sys.exit("tkinter not found. Install it: `sudo apt install python3-tk` / `brew install python-tk`")

    from . import output
    from .capture import grab_at
    from .ocr import recognize
    from .overlay import RegionSelector

    root = tk.Tk()
    root.withdraw()

    def on_selected(image):
        try:
            if image is None:
                return
            text = recognize(image, lang)
            if text:
                output.copy(text)
                output.notify(f"Copied {len(text)} characters", text)
                print(text)
                if save:
                    _save(text, image)
            else:
                output.notify("No text found")
        finally:
            root.quit()

    def start():
        x, y = root.winfo_pointerxy()
        try:
            shot = grab_at(x, y, root.winfo_screenwidth(), root.winfo_screenheight())
        except Exception as e:  # noqa: BLE001 - surface anything to the user
            output.notify("Screenshot failed", str(e))
            root.quit()
            return
        RegionSelector(root, shot, on_selected)

    root.after(0, start)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


def _save(text, image) -> None:
    # The clipboard copy already happened; a broken history must not undo that.
    try:
        from . import classify, store
        store.add(text, image, classify.guess(text))
    except Exception as e:  # noqa: BLE001
        print(f"could not save to history: {e}", file=sys.stderr)
