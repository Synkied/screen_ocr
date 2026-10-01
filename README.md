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
pip install -e '.[desktop]'
```

(Plain `pip install -e .` installs only the history page; that's what a [history server](#history-on-a-raspberry-pi) needs.)

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
and Korean entries show their reading in Latin letters under the text, and Japanese
shows furigana (hiragana) over the kanji. After updating
screen-ocr, run `pip install -e '.[desktop]'` again (it may need new packages) and restart `--web`. Data lives in
`~/.local/share/screen-ocr/` (macOS: `~/Library/Application Support/screen-ocr/`).
Pass `--no-save` to keep a capture out of the history.

### History on a Raspberry Pi
To reach the history from your phone, wherever you are, keep it on an always-on machine such
as a Raspberry Pi and reach it over [Tailscale](https://tailscale.com). Captures are still
taken on your computer and then sent to the Pi. When the Pi can't be reached, they wait on
your computer (in `outbox/` next to the history) and go out with the next capture, or within
5 minutes while `screen-ocr` is running.

1. Install Tailscale on the Pi, your computer and your phone, and sign them in to the same
   account. In the Tailscale admin console, under DNS, turn on MagicDNS and HTTPS certificates.
2. On the Pi:
   ```bash
   git clone <this repo> ~/screen_ocr && cd ~/screen_ocr
   python3 -m venv .venv && .venv/bin/pip install -e .
   sudo tailscale serve --bg 8765       # https://<pi>.<tailnet>.ts.net -> the page; tailnet only
   tailscale status --self              # shows the Pi's name, e.g. pi.tail1234.ts.net
   ```
   Then run the page as a service: edit the venv path and the Pi's name in
   `contrib/screen-ocr-web.service` and follow the steps at the top of that file.
3. To keep your existing history, copy it over once before the first capture is sent:
   `rsync -a ~/.local/share/screen-ocr/ pi:.local/share/screen-ocr/` (macOS: from
   `~/Library/Application Support/screen-ocr/`), then restart the service.
4. On your computer, send captures to the Pi:
   ```bash
   screen-ocr --server https://pi.tail1234.ts.net     # or set SCREEN_OCR_SERVER
   ```
   With `--server` (or `SCREEN_OCR_SERVER`) set, `screen-ocr --web` opens the Pi's page. On your phone, open the same
   address and use "Add to Home Screen".

The page only listens on the Pi itself. `tailscale serve` is the only way in, so only your
own devices can reach it, and other websites still can't read or change it.

### macOS permissions
In **System Settings → Privacy & Security**, give your terminal (or whatever launches the app) these permissions:
- **Screen Recording**. Without it you get a screenshot of just the wallpaper.
- **Accessibility** and **Input Monitoring**, for the global hotkey.

If the hotkey listener misbehaves on your macOS version, bind `screen-ocr --once` to a key with the Shortcuts app instead.

### Wayland
Global hotkeys aren't possible on Wayland. Bind `/path/to/.venv/bin/screen-ocr --once`
(plus `--server <url>` if you use a [history server](#history-on-a-raspberry-pi)) to a custom shortcut in your desktop settings. Screenshots go through `grim`, `gnome-screenshot` or `spectacle`, whichever is installed.

## Tips
- Selecting a tight box around the text gives the best results.
- By default every installed language is enabled. If you mostly read one language, pass
  `--lang` (e.g. `--lang chi_sim`): it's faster and more accurate than mixing many.
- Dark-mode text is inverted automatically, and small UI text is upscaled before OCR.
