"""Cheap offline first guess at a category. You can always change it in the web UI."""

import re

_URL = re.compile(r"^\s*(https?://|www\.)\S+\s*$", re.I)
_EMAIL = re.compile(r"^\s*[\w.+-]+@[\w-]+\.[\w.-]+\s*$")
_NUMBER = re.compile(r"^[\s\d.,:/+\-()%$€£¥]+$")
_CODE_HINTS = re.compile(
    r"[{};]\s*$|^\s*(def|class|import|from|function|const|let|var|return|if|for|#include)\b"
    r"|=>|::|\$ \w|^\s*[\w.-]+\s*=\s*\S", re.M)
_KANA = re.compile(r"[぀-ヿ]")
_HANGUL = re.compile(r"[가-힯]")
_HAN = re.compile(r"[㐀-䶿一-鿿]")


def guess(text: str) -> str:
    if _URL.match(text):
        return "link"
    if _EMAIL.match(text):
        return "email"
    if _NUMBER.match(text):
        return "number"
    lines = [l for l in text.splitlines() if l.strip()]
    if lines and len(_CODE_HINTS.findall(text)) >= max(1, len(lines) // 3):
        return "code"
    # Learners think in languages, not scripts. Kanji-only text can't be told
    # apart from Chinese offline, so it lands in "chinese"; rename it if needed.
    if _KANA.search(text):
        return "japanese"
    if _HANGUL.search(text):
        return "korean"
    if _HAN.search(text):
        return "chinese"
    return "text"
