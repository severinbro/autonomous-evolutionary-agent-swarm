---
name: piper-tts
description: Configure and operate local, neural text-to-speech task completion notifications and CLI voice alerts using Piper TTS with dynamically synthesized task titles. Use when setting up voice alerts, managing Piper voice models, configuring Antigravity task completion hooks, or troubleshooting speech synthesis and debouncing.
triggers: [user, model]
---

# PiperTTS Voice Notifications Skill

This skill guides the setup, configuration, and operation of a high-speed, local neural text-to-speech (TTS) notification system using **Piper TTS**. It is designed to notify developers when autonomous tasks or agent turns finish by announcing a dynamic, fitting title for the task (e.g., *"Task Fix dormer geometry finished"*).

---

## 1. Architecture & Components

The system consists of five decoupled layers:
1. **Piper TTS Engine**: Offline ONNX-based neural speech synthesizer (`piper-tts`) running locally without cloud APIs or network latency.
2. **High-Fidelity Voice Models**: ONNX model checkpoints and JSON phoneme mappings stored in `~/.local/share/piper/voices/`.
3. **Notification Daemon & CLI (`piper-notify`)**: Python utility handling dynamic task title extraction, text formatting, voice synthesis, audio playback via PipeWire/PulseAudio (`paplay`) or ALSA (`aplay`), file locking, and background execution.
4. **Dynamic Title Synthesis**: Natural language processing logic that cleans prompts, strips polite filler ("can you please", "could you"), trims trailing prepositions, and falls back to Antigravity conversation titles to generate a crisp 2–5 word spoken title.
5. **Agent & Lifecycle Hook Integration**:
   - **Agent Rule (`AGENTS.md`)**: Instructs the agent to execute `piper-notify "<XYZ>"` as its final tool action before writing out its concluding response.
   - **Lifecycle Hook (`hooks.json`)**: Listens to the `Stop` event to trigger notifications on session completion.

---

## 2. Installation & Model Setup

### Install Piper via `uv`
```bash
uv tool install piper-tts
```
This installs the `piper` binary into `~/.local/bin/piper`.

### Download Voices
Create the voice storage directory and fetch high-quality voice checkpoints (e.g., `en_US-lessac-medium` or `en_US-amy-medium`):
```bash
mkdir -p ~/.local/share/piper/voices

# Download via piper's built-in voice downloader
~/.local/share/uv/tools/piper-tts/bin/python -m piper.download_voices \
  --download-dir ~/.local/share/piper/voices en_US-lessac-medium
```

---

## 3. Configuration (`~/.config/piper-tts/config.json`)

Configure voice, volume, playback speed, and notification format:
```json
{
  "voice": "en_US-lessac-medium",
  "voices_dir": "/home/<you>/.local/share/piper/voices",
  "enabled": true,
  "format": "Task {title} finished",
  "volume": 1.0,
  "length_scale": 1.0,
  "notify_on_stop": true,
  "notify_on_error": false,
  "player": "paplay"
}
```

---

## 4. CLI Usage Reference (`piper-notify`)

The `piper-notify` utility is installed in `~/.local/bin/piper-notify` (ensure `~/.local/bin` is in `$PATH`):

```bash
# Announce a custom task completion
piper-notify "Mainz 3D city model export"

# Speak custom raw text
piper-notify --say "Build succeeded and tests passed"

# Test speech synthesis and audio playback
piper-notify --test

# List installed voice models
piper-notify --voices

# Download and switch voices
piper-notify --download-voice en_US-amy-medium
piper-notify --set-voice en_US-amy-medium

# Tune volume (0.0 to 1.0+) and speed (e.g., 0.9 = faster, 1.1 = slower)
piper-notify --set-volume 0.85
piper-notify --set-speed 0.95

# Enable or disable voice notifications
piper-notify --disable
piper-notify --enable

# Inspect current configuration
piper-notify --config
```

---

## 5. Integrating with Antigravity & Agent Harnesses

### Method A: Global Agent Rule (`AGENTS.md`)
Place this directive in `~/.gemini/config/rules/AGENTS.md` and `~/.gemini/config/plugins/piper-tts/rules/AGENTS.md`:

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

### Method B: Antigravity Lifecycle Hook (`hooks.json`)
Configure `~/.gemini/config/plugins/piper-tts/hooks.json` (and `~/.gemini/config/hooks.json`):
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

## 6. Debouncing & Process Concurrency

To ensure audio playback does not block the agent or UI:
- **Detached Execution**: The caller spawns a detached background worker (`start_new_session=True`), outputting immediate confirmation (< 1ms).
- **Audio Lock**: Playback acquires an exclusive lock via `/tmp/piper_notify_playback.lock` so overlapping notifications do not talk over each other.
- **Debouncing**: Calls within 2.5 seconds or duplicate requests within 8.0 seconds are dropped by the parent process. *Crucial:* Internal background workers (`--sync`) skip debounce checking so the worker does not debounce its own parent.

---

## 7. Troubleshooting

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **No audio output** | Missing audio player or permissions | Ensure `paplay` (PipeWire/PulseAudio) or `aplay` (ALSA) is installed (`which paplay aplay`). |
| **Log says `Debounced: triggered too soon`** | Worker checking parent debounce file | Ensure the background worker `--sync` path bypasses `should_notify()`. |
| **Agent doesn't notify on final turn** | Rule missing from active agent context | Verify `~/.gemini/config/rules/AGENTS.md` exists and contains the required directive. |
| **Model synthesis fails** | Voice ONNX file missing or corrupt | Re-download model with `piper-notify --download-voice en_US-lessac-medium`. |
