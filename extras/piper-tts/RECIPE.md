# Cooking Recipe: PiperTTS Local Voice Notifications

## Overview
This setup equips your Linux workstation and Antigravity agents with local, neural text-to-speech (TTS) notifications. Whenever an autonomous task or conversation turn finishes, Piper announces a dynamic spoken notification (e.g. *"Task Export LOD2 building mesh finished"*), allowing you to step away and return when notified.

---

## 1. Ingredients & Dependencies

| Component | Purpose | Requirement |
| :--- | :--- | :--- |
| **`piper-tts`** | High-speed neural speech engine | Python 3.10+ or `uv tool` |
| **Voice Checkpoints** | ONNX models & JSON config | Downloaded locally (e.g., `en_US-lessac-medium`) |
| **Audio Server** | Playback backend | PipeWire / PulseAudio (`paplay`) or ALSA (`aplay`) |
| **`piper-notify`** | Dynamic title resolver & audio daemon | `~/.local/bin/piper-notify` |
| **Antigravity Rule** | Agent instruction trigger | `~/.gemini/config/rules/AGENTS.md` |

---

## 2. Step 1: Install Piper & Fetch Voice Checkpoints

Install `piper-tts` using `uv`:
```bash
uv tool install piper-tts
```

Create the local voice library and download default voices:
```bash
mkdir -p ~/.local/share/piper/voices

# Download English voice models
~/.local/share/uv/tools/piper-tts/bin/python -m piper.download_voices \
  --download-dir ~/.local/share/piper/voices en_US-lessac-medium en_US-amy-medium
```

---

## 3. Step 2: The `piper-notify` Utility Script

The executable script `~/.local/bin/piper-notify` (source: [`scripts/piper-notify`](scripts/piper-notify)) provides:
- Dynamic prompt cleaning and task title extraction (stripping filler phrases, formatting into 2–5 word titles).
- Native audio server routing (`paplay` priority, falling back to `aplay`).
- Playback locking via `/tmp/piper_notify_playback.lock` to prevent overlapping audio.
- Intelligent debounce logic (2.5s window) while allowing decoupled `--sync` background workers to speak immediately.

Make sure it is executable:
```bash
chmod +x ~/.local/bin/piper-notify
```

Test it in your terminal:
```bash
piper-notify "Workspace compilation"
```

---

## 4. Step 3: Configure Agent Behavior in `AGENTS.md`

To ensure agents in Antigravity or other harnesses always trigger the notification upon finishing their turn, add the following directive to `~/.gemini/config/rules/AGENTS.md`:

```markdown
# PiperTTS Task Notifications

PiperTTS is configured to notify the user with local neural text-to-speech whenever the agent completes a task and writes out the final response, allowing the user to step away and return when notified.

## Agent Requirement (MUST ALWAYS FOLLOW)
Whenever you are about to output your final response to the user for any turn or task:
- As your final tool action before writing your concluding response, run:
  `piper-notify "<XYZ>"`
  where `<XYZ>` is a fitting, dynamic 2–5 word descriptive title for the task (e.g., `piper-notify "Setup Piper notifications"`, `piper-notify "Fix lint errors"`, etc.).
- Never invoke `piper-notify` during intermediate tool calls—ONLY on the final tool execution immediately before concluding your response.
- Even if a turn is purely conversational or answers a question, execute `piper-notify "<XYZ>"` before providing the answer so the user receives their audible notification that the response is ready.
```

---

## 5. Step 4: Antigravity Lifecycle Hook (Optional Headless Mode)

For automated runs where no tools are invoked or for CLI workflows, configure `~/.gemini/config/plugins/piper-tts/hooks.json`:

```json
{
  "piper-tts-task-notify": {
    "enabled": true,
    "Stop": [
      {
        "type": "command",
        "command": "/home/<you>/.local/bin/piper-notify --hook",
        "timeout": 15
      }
    ]
  }
}
```

---

## 6. Step 5: Verification & Customization

```bash
# Test audio playback
piper-notify --test

# Change the voice
piper-notify --set-voice en_US-amy-medium

# Tune volume or speed
piper-notify --set-volume 0.85
piper-notify --set-speed 0.95

# Review speech logs
tail -n 20 ~/.local/state/piper-tts/notify.log
```
