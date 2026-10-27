# Cooking Recipe: Whisper STT via Right Control

## Overview
This setup creates a background Push-To-Talk (PTT) daemon that loads `faster-whisper`. Whenever you hold the `Right Control` key, it records your voice, transcribes it, and outputs the text.

## 1. Setup the Virtual Environment
```bash
mkdir -p ~/tools/whisper-dictate
cd ~/tools/whisper-dictate
python3 -m venv venv
source venv/bin/activate
```

## 2. Install Dependencies
You need system audio/input libraries and Python packages for CUDA, sound, and evdev.
```bash
pip install faster-whisper sounddevice numpy evdev
```

## 3. The Python Script (ptt_daemon.py)
Create `ptt_daemon.py`. Crucially, this script must dynamically load the Nvidia shared libraries from the venv so `faster-whisper` uses the GPU.

```python
import os
import sys

# Dynamic path to Nvidia shared libraries in the venv
venv_base = sys.prefix
nvidia_paths = [
    os.path.join(venv_base, "lib/python3.14/site-packages/nvidia/cublas/lib"),
    os.path.join(venv_base, "lib/python3.14/site-packages/nvidia/cudnn/lib"),
]
current_ld = os.environ.get("LD_LIBRARY_PATH", "")
os.environ["LD_LIBRARY_PATH"] = ":".join(nvidia_paths + ([current_ld] if current_ld else []))

import glob
import select
import tempfile
import subprocess
import sounddevice as sd
import numpy as np
from evdev import InputDevice, ecodes
from faster_whisper import WhisperModel

# ... [Rest of your PTT and typing logic] ...
```

## 4. Execution Script (run_stt.sh)
Create an executable bash script `run_stt.sh` to launch the daemon from within the venv:
```bash
#!/bin/bash
cd ~/tools/whisper-dictate
source venv/bin/activate
python ptt_daemon.py
```
*(Make sure to run `chmod +x run_stt.sh` and ensure your user is in the `input` group to use evdev!)*
