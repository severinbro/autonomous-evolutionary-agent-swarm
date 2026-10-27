#!/usr/bin/env python3
"""Worktree Sandbox Manager for Autonomous Subagents.

Provides automated provisioning, environment copying, diff inspection,
and teardown for Git worktree-based agent sandboxes.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys


def get_git_root() -> str:
    res = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError("Not inside a git repository.")
    return res.stdout.strip()


def create_worktree(branch_name: str, base_branch: str = "main") -> str:
    root = get_git_root()
    repo_name = os.path.basename(root)
    parent_dir = os.path.dirname(root)
    worktree_path = os.path.join(parent_dir, f"{repo_name}-{branch_name}")

    if os.path.exists(worktree_path):
        print(f"Worktree path {worktree_path} already exists.")
        return worktree_path

    print(f"Creating worktree at: {worktree_path} (Branch: {branch_name} off {base_branch})...")
    res = subprocess.run(["git", "worktree", "add", worktree_path, "-b", branch_name, base_branch],
                         check=False)
    if res.returncode != 0:
        # Try checking out existing branch if it exists
        res = subprocess.run(["git", "worktree", "add", worktree_path, branch_name], check=False)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create git worktree for {branch_name}")

    # Copy untracked configuration / secret files if present
    for env_file in [".env", ".env.local", ".env.development"]:
        src_env = os.path.join(root, env_file)
        dst_env = os.path.join(worktree_path, env_file)
        if os.path.exists(src_env) and not os.path.exists(dst_env):
            shutil.copy2(src_env, dst_env)
            print(f"Copied {env_file} to worktree sandbox.")

    print(f"Worktree sandbox ready at: {worktree_path}")
    return worktree_path


def list_worktrees() -> None:
    subprocess.run(["git", "worktree", "list"], check=False)


def diff_worktree(branch_name: str, base_branch: str = "main") -> None:
    res = subprocess.run(["git", "diff", f"{base_branch}...{branch_name}"], check=False)


def cleanup_worktree(branch_name: str) -> None:
    root = get_git_root()
    repo_name = os.path.basename(root)
    parent_dir = os.path.dirname(root)
    worktree_path = os.path.join(parent_dir, f"{repo_name}-{branch_name}")

    if os.path.exists(worktree_path):
        print(f"Removing worktree directory: {worktree_path}...")
        subprocess.run(["git", "worktree", "remove", "--force", worktree_path], check=False)

    print("Pruning stale worktree references...")
    subprocess.run(["git", "worktree", "prune"], check=False)
    print("Cleanup complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Git Worktree Sandbox Manager for Subagents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create an isolated worktree for a task")
    create_parser.add_argument("branch", help="Task branch name (e.g. feat/player-physics)")
    create_parser.add_argument("--base", default="main", help="Base branch (default: main)")

    subparsers.add_parser("list", help="List all registered worktrees")

    diff_parser = subparsers.add_parser("diff", help="View diff between base and worktree branch")
    diff_parser.add_argument("branch", help="Task branch name")
    diff_parser.add_argument("--base", default="main", help="Base branch")

    cleanup_parser = subparsers.add_parser("cleanup", help="Remove worktree and prune")
    cleanup_parser.add_argument("branch", help="Task branch name to clean up")

    args = parser.parse_args()

    if args.command == "create":
        create_worktree(args.branch, args.base)
    elif args.command == "list":
        list_worktrees()
    elif args.command == "diff":
        diff_worktree(args.branch, args.base)
    elif args.command == "cleanup":
        cleanup_worktree(args.branch)


if __name__ == "__main__":
    main()
