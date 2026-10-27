---
name: google-drive-sync
description: Transfer files and synchronize directories to and from Google Drive via Rclone CLI. Use when the user asks to push/pull files, backup folders, mirror sync, or mount Google Drive on Linux.
triggers: [user, model]
---

# Google Drive Sync via Rclone

This skill provides step-by-step instructions and command references to upload, download, synchronize, and mount Google Drive folders on Linux using Rclone.

---

## 1. Quick Installation & Verification

Verify or install Rclone:
```bash
which rclone || sudo apt update && sudo apt install -y rclone
rclone version
```

---

## 2. Interactive Setup (`rclone config`)

If `rclone listremotes` does not show a configured remote (e.g. `gdrive:`):
```bash
rclone config
```
1. `n` -> New remote.
2. Name: `gdrive`
3. Storage Type: `drive` (Google Drive)
4. Client ID / Client Secret: Press **Enter** (leave blank for defaults).
5. Scope: `1` (Full access to read/write).
6. Edit advanced config: `n` (No).
7. Authenticate via web browser: `y` (Yes) -> Log into Google Account in the opened browser window.
8. Shared Drive: `n` (unless using a team drive).
9. Confirm and save (`y` -> `q`).

Verify connection:
```bash
rclone lsd gdrive:
```

---

## 3. Core Commands Cheat Sheet

### Push (Local to Google Drive)
```bash
# Push a single file:
rclone copy ./my_file.pdf gdrive:MyFolder/ -P

# Push an entire folder (only transfers new/changed files):
rclone copy ./projects/ gdrive:Backup/projects/ -P
```

### Pull (Google Drive to Local)
```bash
# Pull a single file:
rclone copy gdrive:MyFolder/remote_file.pdf ./local_dir/ -P

# Pull an entire folder:
rclone copy gdrive:Backup/projects/ ./projects/ -P
```

### True Mirror Sync (`sync`)
> [!WARNING]
> `rclone sync` deletes destination files that do not exist at the source to ensure exact mirroring. Always test with `--dry-run` first!

```bash
# Dry run to preview changes:
rclone sync ./local_dir/ gdrive:Backup/ --dry-run -P

# Execute live sync:
rclone sync ./local_dir/ gdrive:Backup/ -P
```

### Mount as Local Filesystem
```bash
mkdir -p ~/GoogleDrive
rclone mount gdrive: ~/GoogleDrive --vfs-cache-mode writes --daemon
```
*To unmount:* `fusermount -u ~/GoogleDrive`
