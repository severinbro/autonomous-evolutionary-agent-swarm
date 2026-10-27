---
name: whisper-stt
description: Setup and operate a local, GPU-accelerated Push-To-Talk (PTT) speech-to-text daemon using faster-whisper and hardware keyboard triggers. Use when setting up voice input, transcribing audio, or fixing whisper daemon issues.
triggers: [user, model]
---

# Whisper Push-To-Talk (PTT) Speech-to-Text Skill

This skill guides the setup and management of a local, hardware-triggered Push-to-Talk (PTT) transcription daemon on Linux using `faster-whisper` and NVIDIA CUDA acceleration.

---

## 1. Prerequisites & Virtual Environment

Setup directory and isolated Python environment:
```bash
mkdir -p ~/tools/whisper-dictate
cd ~/tools/whisper-dictate
python3 -m venv venv
source venv/bin/activate
pip install faster-whisper sounddevice numpy evdev
```

*Permissions:* The user must be part of the `input` group to intercept keyboard events via `evdev`:
```bash
sudo usermod -aG input $USER
```

---

## 2. Dynamic CUDA Library Injection

When running inside virtual environments, `faster-whisper` requires NVIDIA cublas and cudnn shared libraries. Ensure the script sets `LD_LIBRARY_PATH` dynamically before importing:

```python
import os
import sys

venv_base = sys.prefix
nvidia_paths = [
    os.path.join(venv_base, "lib/python3.14/site-packages/nvidia/cublas/lib"),
    os.path.join(venv_base, "lib/python3.14/site-packages/nvidia/cudnn/lib"),
]
current_ld = os.environ.get("LD_LIBRARY_PATH", "")
os.environ["LD_LIBRARY_PATH"] = ":".join(nvidia_paths + ([current_ld] if current_ld else []))
```

---

## 3. Daemon Control

### Launching the Daemon
```bash
~/tools/whisper-dictate/run_stt.sh &
```

### Checking Daemon Status
```bash
pgrep -fl ptt_daemon.py
```

### Stopping the Daemon
```bash
pkill -f ptt_daemon.py
```
