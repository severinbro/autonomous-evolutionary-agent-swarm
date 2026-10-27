# Cooking Recipe: Google Drive Push & Pull with Rclone

## Overview
This recipe sets up [Rclone](https://rclone.org/) on Linux to push and pull files/directories to and from Google Drive via the CLI. It supports single-file transfers, batch directory copies with progress tracking (`-P`), mirror syncing, and mounting Drive directly into your filesystem.

---

## 1. Installation

Install Rclone using the system package manager:
```bash
sudo apt update && sudo apt install -y rclone
```

*(Optional: To install the latest upstream release directly from Rclone's official script)*:
```bash
sudo -v ; curl https://rclone.org/install.sh | sudo bash
```

Verify the installation:
```bash
rclone version
```

---

## 2. Connect Google Drive (`rclone config`)

Run the interactive setup wizard:
```bash
rclone config
```

Follow the configuration prompts:
1. **`n`** -> New remote
2. **`name`** -> `gdrive` (or your preferred alias)
3. **`Storage>`** -> `drive` (Google Drive)
4. **`client_id>`** -> Press **Enter** (leave blank for defaults, or supply GCP OAuth ID)
5. **`client_secret>`** -> Press **Enter** (leave blank)
6. **`scope>`** -> `1` (`drive` — full access to read and write files)
7. **`service_account_file>`** -> Press **Enter** (leave blank)
8. **`Edit advanced config?>`** -> `n` (No)
9. **`Use web browser to automatically authenticate?>`** -> `y` (Yes)
   - *A browser window (e.g. Brave) will open automatically.*
   - Log into your Google Account, grant permissions, and return to the terminal.
10. **`Configure this as a Shared Drive (Team Drive)?>`** -> `n` (unless using a Workspace Shared Drive)
11. **`Keep this "gdrive" remote?>`** -> `y` (Yes)
12. **`q`** -> Quit config

---

## 3. Core Commands Cheat Sheet

### Push (Upload to Google Drive)
```bash
# Push a single file to a Drive folder
rclone copy ./my_file.pdf gdrive:MyFolder/ -P

# Push an entire folder (only copies new or modified files)
rclone copy ./projects/ gdrive:Backup/projects/ -P
```

### Pull (Download from Google Drive)
```bash
# Pull a single file to current directory
rclone copy gdrive:MyFolder/my_file.pdf ./ -P

# Pull a folder to local disk
rclone copy gdrive:Backup/projects/ ./projects/ -P
```

### Explore Remote Storage
```bash
# List top-level folders
rclone lsd gdrive:

# List files inside a directory (recursive)
rclone ls gdrive:MyFolder

# Check total and used storage on Drive
rclone about gdrive:
```

### Mirror Sync (Caution: Deletes remote files if deleted locally)
```bash
rclone sync ./local_dir gdrive:remote_dir -P
```

---

## 4. Implementation Helper Script (`gdrive.sh`)

You can create an executable helper script to simplify everyday operations:

```bash
cat << 'EOF' > /mnt/sda/bash_scripts/gdrive.sh
#!/usr/bin/env bash
# Quick CLI helper for Rclone Google Drive operations
REMOTE="gdrive"

usage() {
    echo "Usage: $0 {push|pull|list|sync|status} [args...]"
    echo "  push <local_path> <remote_path>   Upload file/dir to Google Drive"
    echo "  pull <remote_path> <local_path>   Download file/dir from Google Drive"
    echo "  list [remote_path]                List directories/files in remote"
    echo "  sync <local_path> <remote_path>   Mirror local folder to remote (deletes extra files)"
    echo "  status                            Show Drive storage quota"
    exit 1
}

case "$1" in
    push)
        [ -z "$2" ] || [ -z "$3" ] && usage
        rclone copy "$2" "${REMOTE}:$3" -P
        ;;
    pull)
        [ -z "$2" ] || [ -z "$3" ] && usage
        rclone copy "${REMOTE}:$2" "$3" -P
        ;;
    list)
        TARGET="${2:-}"
        rclone lsf "${REMOTE}:$TARGET"
        ;;
    sync)
        [ -z "$2" ] || [ -z "$3" ] && usage
        rclone sync "$2" "${REMOTE}:$3" -P
        ;;
    status)
        rclone about "${REMOTE}:"
        ;;
    *)
        usage
        ;;
esac
EOF

chmod +x /mnt/sda/bash_scripts/gdrive.sh
```

---

## 5. Mounting Google Drive as a Local Folder (Optional)

To interact with Google Drive as if it were a local directory:

```bash
# Create mount point
mkdir -p ~/GoogleDrive

# Mount in background with write-caching enabled
rclone mount gdrive: ~/GoogleDrive --vfs-cache-mode writes --daemon

# Unmount when done
fusermount -u ~/GoogleDrive
```
