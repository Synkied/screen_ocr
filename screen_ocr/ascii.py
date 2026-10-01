"""Pictures with no text in them (faces, photos, icons) become ASCII art instead."""

from PIL import Image, ImageOps

# Darkest first: the art is meant for dark text on a light page.
RAMP = "@%#*+=-:. "
MAX_COLUMNS = 80
MIN_COLUMNS = 20
# Monospace glyphs are about twice as tall as they are wide.
CHAR_ASPECT = 0.5


def looks_like_text(text: str) -> bool:
    """Tesseract reads photos as scattered punctuation and stray letters.
    Real text is mostly letters and digits (any script) once spaces are dropped."""
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return False
    return sum(ch.isalnum() for ch in chars) / len(chars) >= 0.6


def render(image: Image.Image) -> str:
    gray = ImageOps.autocontrast(ImageOps.grayscale(image), cutoff=1)
    columns = max(MIN_COLUMNS, min(MAX_COLUMNS, gray.width // 4))
    rows = max(1, round(columns * gray.height / gray.width * CHAR_ASPECT))
    small = gray.resize((columns, rows), Image.LANCZOS)
    step = 256 / len(RAMP)
    pixels = list(small.getdata())
    lines = (
        "".join(RAMP[int(p // step)] for p in pixels[y * columns:(y + 1) * columns]).rstrip()
        for y in range(rows)
    )
    return "\n".join(lines).strip("\n")
