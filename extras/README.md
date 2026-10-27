# Extras

These skills are not installed by `install.sh`. Most are tied to one workstation's local services and paths, so treat them as worked examples and adapt the paths before use. To install one, link its folder into your harness's skills directory:

```bash
ln -s "$PWD/extras/piper-tts" ~/.claude/skills/piper-tts
```

| Extra | Needs | Notes |
| :--- | :--- | :--- |
| [`autonomous-agent-swarm`](autonomous-agent-swarm/SKILL.md) | Bundled `scripts/` | Earlier, simpler predecessor of `/invoke-swarm`. Do not install it next to `skills/`: both trigger on multi-agent requests, and their rules conflict (a 2-attempt limit versus the 5-round fix loop). |
| [`google-drive-sync`](google-drive-sync/SKILL.md) | `rclone` | Generic. `RECIPE.md` writes a helper script to `/mnt/sda/bash_scripts/`; change that path. |
| [`knowledge-wiki`](knowledge-wiki/SKILL.md) | Wiki.js 2.x plus sync tooling under `/mnt/sda/wiki` | Replace the `/mnt/sda/wiki` paths and URL with your own wiki. |
| [`math-reasoning`](math-reasoning/SKILL.md) | A local math model behind `/mnt/sda/development/scripts/math_eval.py` | Core skills already fall back to SymPy; this only adds a local model as a cross-check. |
| [`piper-tts`](piper-tts/SKILL.md) | `piper-tts`, `paplay` or `aplay` | Spoken task-completion notifications. Install `scripts/piper-notify` to `~/.local/bin/` and replace `/home/<you>` in the config examples. |
| [`whisper-stt`](whisper-stt/SKILL.md) | `faster-whisper`, CUDA, `evdev`, membership in the `input` group | Push-to-talk dictation daemon. |

Each `RECIPE.md` is the longer setup write-up for its skill.
