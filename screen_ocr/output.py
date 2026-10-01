import shutil
import subprocess
import sys

import pyperclip

APP_NAME = "Screen OCR"


def copy(text: str) -> None:
    pyperclip.copy(text)


def notify(title: str, body: str = "") -> None:
    body = body if len(body) <= 120 else body[:117] + "…"
    try:
        if sys.platform == "darwin":
            script = (
                f"display notification {_applescript_str(body)} "
                f"with title {_applescript_str(APP_NAME)} subtitle {_applescript_str(title)}"
            )
            subprocess.run(["osascript", "-e", script], check=False)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", "-a", APP_NAME, "-t", "3000", title, body], check=False)
        else:
            print(f"[{APP_NAME}] {title}: {body}")
    except OSError:
        print(f"[{APP_NAME}] {title}: {body}")


def _applescript_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
