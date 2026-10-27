#!/usr/bin/env bash
# Install the agent-swarm skill pack into an agent harness by symlinking it from this checkout.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

usage() {
  cat <<'EOF'
Usage: ./install.sh <target>

Targets:
  antigravity   Copy this checkout into the plugin ~/.gemini/config/plugins/agent-swarm
                (re-run after every update; runtime state in the plugin folder is kept)
  claude-code   Link each skill into ~/.claude/skills/<name>
  dir <path>    Link each skill into <path>/<name> (any harness that loads SKILL.md folders)

Existing files, links, or plugin folders not created by this script are never overwritten.
Skills in extras/ need personal infrastructure and are not installed (see extras/README.md).
EOF
}

skipped=0
home_hint="$REPO"

# link SRC DEST: create a symlink unless DEST already exists.
link() {
  local src="$1" dest="$2"
  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then
    echo "  ok       $dest"
  elif [ -e "$dest" ] || [ -L "$dest" ]; then
    echo "  SKIPPED  $dest (already exists; remove it to install from this checkout)" >&2
    skipped=$((skipped + 1))
  else
    ln -s "$src" "$dest"
    echo "  linked   $dest -> $src"
  fi
}

case "${1:-}" in
  antigravity)
    # Copy rather than symlink: Antigravity is not known to load skills from a symlinked plugin folder.
    dest="$HOME/.gemini/config/plugins/agent-swarm"
    if [ -e "$dest" ] && [ ! -f "$dest/.installed-from" ]; then
      echo "  SKIPPED  $dest (exists and was not installed by this script; move it aside first)" >&2
      exit 1
    fi
    command -v rsync >/dev/null || { echo "rsync is required for the antigravity target" >&2; exit 1; }
    mkdir -p "$dest"
    rsync -a --delete \
      --exclude .git/ --exclude .installed-from --exclude .swarm_global/ --exclude __pycache__/ \
      --exclude 'scripts/*.log' --exclude 'scripts/*.pid' --exclude scripts/swarm_tasks.json \
      "$REPO/" "$dest/"
    echo "$REPO" >"$dest/.installed-from"
    echo "  synced   $dest <- $REPO"
    echo "  Enable it once with: agy plugin enable agent-swarm (re-run this script after every update)"
    home_hint="$dest"
    ;;
  claude-code | dir)
    if [ "$1" = dir ]; then
      [ -n "${2:-}" ] || { usage; exit 2; }
      dest_dir="$2"
    else
      dest_dir="$HOME/.claude/skills"
    fi
    mkdir -p "$dest_dir"
    for skill in "$REPO"/skills/*/; do
      skill="${skill%/}"
      link "$skill" "$dest_dir/$(basename "$skill")"
    done
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    usage
    exit 2
    ;;
esac

if ! python3 -c 'import playwright' 2>/dev/null && [ -z "${AGENT_SWARM_UI_PYTHON:-}" ]; then
  echo
  echo "Note: python3 cannot import Playwright and AGENT_SWARM_UI_PYTHON is unset, so"
  echo "      web_ui_validator.py will report FAIL (browser-unavailable) until you run:"
  echo "        pip install playwright && python3 -m playwright install chromium"
fi

echo
echo "Add to your shell profile so skills can locate their scripts:"
echo "  export AGENT_SWARM_HOME=\"$home_hint\""

[ "$skipped" -eq 0 ] || exit 1
