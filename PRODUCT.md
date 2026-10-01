# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

The history browser is a local web page. The capture overlay is a Tk desktop window (Linux X11/Wayland, macOS).

## Users

Language learners and readers who grab text, often CJK, from things they can't copy: games, videos, images, scanned pages and app UIs. They want it in the clipboard so they can look it up, translate it or save it. They switch away from what they're reading for a moment and want to get back to it right away. They come back to the history later to review, search and organize what they collected.

Today they install through the terminal (pip, Tesseract language packs, CLI flags), so they need to be comfortable with a short command-line setup.

## Product Purpose

Press a hotkey, drag a box over anything on screen, and its text lands in the clipboard. Every capture is kept with its cropped screenshot and a guessed category, so it can be found again later. Success means the user goes from seeing text to having it on the clipboard with no friction, and their collection of captures stays easy to search and organize.

## Positioning

- **Fully local and private.** OCR runs on-device with Tesseract. There is no cloud OCR, no network calls and no telemetry, and that never changes.
- **Speed is the product.** Hotkey, drag, then clipboard and a notification. Capture is the main path; the history must never slow it down.
- **The history can be searched.** Captures are a personal archive that can be searched, filtered by category, recategorized in bulk, copied and deleted.
- **Multilingual, CJK included.** All installed Tesseract languages are used by default. Mixed and Asian scripts are first-class.

## Operating Context

- Capture: global hotkey (default `Ctrl+Alt+O`), or `screen-ocr --once` bound to a desktop or Shortcuts key on Wayland and macOS. A dimmed fullscreen snapshot appears and the user drags to select; Esc or right-click cancels. A desktop notification confirms what was copied.
- History: `screen-ocr --web` serves `http://127.0.0.1:8765`. Data lives in `~/.local/share/screen-ocr/` (macOS: `~/Library/Application Support/screen-ocr/`). `--no-save` keeps a capture out of the history.
- Categories: auto-guessed as `link`, `email`, `number`, `code`, `japanese`, `chinese`, `korean` or `text`. Users can type any name to create a new one.

## Capabilities and Constraints

- The history page is one self-contained `screen_ocr/web.html`, served by a stdlib-only Python server (`web.py`). There are no dependencies, no build step, and no CDN, web fonts or other assets loaded from the network.
- It must work fully offline.
- It follows the system light/dark preference (`prefers-color-scheme`).
- The server binds to 127.0.0.1 and rejects foreign Host/Origin headers. Future work must keep these protections.
- Dark-mode text is inverted and small text is upscaled before OCR. A tight selection gives the best results.

## Evidence on Hand

- README.md covers install, usage and platform permissions.
- There are no screenshots, testimonials, user counts or benchmarks. Don't make any up.

## Product Principles

1. **Never interrupt the read.** Capture is instant and needs only a glance, so the user gets straight back to what they were doing.
2. **Local by construction.** No feature may need the network or send data off the machine.
3. **Every script is first-class.** CJK and mixed-language text must display, search and copy as well as Latin text.
4. **Collected text is worth returning to.** The history should feel like a usable personal archive, not a log dump.
5. **Zero-dependency simplicity.** Prefer stdlib and a single file over tooling.

## Accessibility & Inclusion

- The history page must be fully usable from the keyboard. The overlay already supports Esc to cancel.
- Light and dark themes must both follow the system setting.
- Fonts must render CJK correctly using the system's available fonts, since web fonts aren't allowed.
