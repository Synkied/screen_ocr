# screen-ocr

Press a hotkey, drag a box over anything on screen, and its text lands in your clipboard.
Everything runs locally with Tesseract. Works on Linux (X11 and Wayland) and macOS.

## Install

System packages:

```bash
# macOS
brew install tesseract python-tk

# Debian/Ubuntu
sudo apt install tesseract-ocr python3-tk python3-dev xclip libnotify-bin

# language packs (the app uses every installed one automatically)
sudo apt install tesseract-ocr-jpn tesseract-ocr-chi-sim tesseract-ocr-chi-tra tesseract-ocr-kor tesseract-ocr-fra
# macOS: brew install tesseract-lang   (all languages)
```

Then:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
```

On Linux, `pynput` builds `evdev`, which needs `python3-dev` and a C compiler.

## Use

```bash
screen-ocr                        # listens for Ctrl+Alt+O
screen-ocr --hotkey '<cmd>+<shift>+o' --lang jpn   # restrict to one language
screen-ocr --once                 # capture right away, then exit
```

Drag to select. Esc or right-click cancels. When it finishes, a notification shows what was copied.

### History
Every capture is saved with its cropped screenshot and a guessed category
(link, email, number, code, japanese, chinese, korean or text). To browse them:

```bash
screen-ocr --web                  # opens http://127.0.0.1:8765
```

On that page you can search (text, categories, labels, and Japanese, Chinese or Korean
by their reading in Latin letters: `tokyo` finds 東京, `annyeong` finds 안녕), filter by category, change or
bulk-set categories (type any name to make a new one), give each capture up to three labels
of your own (e.g. "minna no nihongo", "lesson 18") and filter by them, copy, and delete
single or selected captures; identical captures show once, with a ×N count. Japanese, Chinese
and Korean entries show their reading in Latin letters under the text. After updating
screen-ocr, run `pip install -e .` again (it may need new packages) and restart `--web`. Data lives in
`~/.local/share/screen-ocr/` (macOS: `~/Library/Application Support/screen-ocr/`).
Pass `--no-save` to keep a capture out of the history.

### macOS permissions
In **System Settings → Privacy & Security**, give your terminal (or whatever launches the app) these permissions:
- **Screen Recording**. Without it you get a screenshot of just the wallpaper.
- **Accessibility** and **Input Monitoring**, for the global hotkey.

If the hotkey listener misbehaves on your macOS version, bind `screen-ocr --once` to a key with the Shortcuts app instead.

### Wayland
Global hotkeys aren't possible on Wayland. Bind `/path/to/.venv/bin/screen-ocr --once`
to a custom shortcut in your desktop settings. Screenshots go through `grim`, `gnome-screenshot` or `spectacle`, whichever is installed.

## Tips
- Selecting a tight box around the text gives the best results.
- By default every installed language is enabled. If you mostly read one language, pass
  `--lang` (e.g. `--lang chi_sim`): it's faster and more accurate than mixing many.
- Dark-mode text is inverted automatically, and small UI text is upscaled before OCR.
