# Install — clip-capture

No servers, no accounts, no API keys. ~2 minutes.

## 0. Prereqs

```bash
brew install ffmpeg
ffmpeg -version  # should print 6.x or 7.x
```

Python 3.10+ is all that's needed -- the helpers use only the standard
library, so there's nothing to `uv sync` beyond the dev tooling.

## 1. Skill install

### Local clone + symlink

```bash
git clone https://github.com/tosi-n/agentic-frame.git ~/Developer/agentic-frame
```

For Codex:
```bash
ln -s ~/Developer/agentic-frame/skills/clip-capture ~/.codex/skills/clip-capture
```

For Claude Code:
```bash
ln -s ~/Developer/agentic-frame/skills/clip-capture ~/.claude/skills/clip-capture
```

### `npx skills add`

```bash
npx skills add tosi-n/agentic-frame
```

## 2. macOS permission (one-time, manual)

Screen/camera/mic capture requires the terminal or app running `ffmpeg` to
be granted access under **System Settings -> Privacy & Security -> Screen
Recording** (and **Camera** / **Microphone** for those inputs). This cannot
be granted by any script -- open System Settings and add your terminal app
(or the agent host app) to the list, then restart it.

## 3. Verify

```bash
cd ~/Developer/agentic-frame/skills/clip-capture
python helpers/list_devices.py
python helpers/capture.py --selftest --out /tmp/clip-capture-selftest.mp4
```

If `capture.py --selftest` fails with a permission hint, go back to step 2 --
the terminal doesn't have the OS grant yet.

## 4. Linux notes

- Capture uses `x11grab` (whole display only) + `pulse` (mic). Install
  `pulseaudio-utils` for `pactl` if `list_devices.py`'s audio list is empty.
- **Wayland is not supported.** `x11grab` requires an X11 session.
