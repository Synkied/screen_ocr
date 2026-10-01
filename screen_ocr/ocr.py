"""Tesseract with a little preprocessing tuned for screen text."""

import re

import pytesseract
from PIL import Image, ImageOps, ImageStat

# Tesseract was trained on ~30px-tall glyphs; UI text is often 10-14px.
SMALL_TEXT_HEIGHT = 300


# Not real languages (orientation, math, digits) or vertical-only models.
_NOT_TEXT = {"osd", "equ", "snum"}

# Tesseract puts spaces between CJK glyphs; those languages don't use them.
_CJK = r"\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef"
_CJK_GAP = re.compile(rf"(?<=[{_CJK}])[ \t]+(?=[{_CJK}])")


class LanguageError(RuntimeError):
    pass


def check_installed() -> str:
    return str(pytesseract.get_tesseract_version())


def installed_languages() -> list:
    return [
        lang for lang in pytesseract.get_languages(config="")
        if lang not in _NOT_TEXT and not lang.endswith("_vert")
    ]


def resolve_lang(lang: str) -> str:
    """'auto' means every installed language pack, English first."""
    installed = installed_languages()
    if lang == "auto":
        return "+".join(sorted(installed, key=lambda l: l != "eng")) or "eng"
    missing = [l for l in lang.split("+") if l not in installed and not l.endswith("_vert")]
    if missing:
        pkgs = " ".join("tesseract-ocr-" + l.replace("_", "-") for l in missing)
        raise LanguageError(
            f"Language pack not installed: {', '.join(missing)}. "
            f"Install with `sudo apt install {pkgs}` (macOS: `brew install tesseract-lang`)."
        )
    return lang


def recognize(image: Image.Image, lang: str = "eng") -> str:
    gray = ImageOps.grayscale(image)

    # Light-on-dark (dark mode, terminals) reads much better inverted.
    if ImageStat.Stat(gray).mean[0] < 110:
        gray = ImageOps.invert(gray)

    if gray.height < 40:
        factor = 3
    elif gray.height < SMALL_TEXT_HEIGHT:
        factor = 2
    else:
        factor = 1
    if factor > 1:
        gray = gray.resize((gray.width * factor, gray.height * factor), Image.LANCZOS)

    gray = ImageOps.expand(gray, border=20, fill=255)

    single_line = image.height < 60 and image.width > image.height * 3
    psm = 7 if single_line else 3
    text = pytesseract.image_to_string(gray, lang=lang, config=f"--psm {psm}")

    text = _CJK_GAP.sub("", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()
