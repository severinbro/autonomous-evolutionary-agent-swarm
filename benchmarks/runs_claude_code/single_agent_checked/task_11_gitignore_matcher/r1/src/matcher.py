"""Decide which files Git ignores, given a single top-level .gitignore."""

from __future__ import annotations

from .patterns import parse_gitignore


class GitIgnore:
    """Matcher built from the full text of a repository-root .gitignore."""

    def __init__(self, text: str):
        self.patterns = parse_gitignore(text)

    def _last_match(self, path: str, is_dir: bool):
        """The last pattern matching ``path`` (later lines win), or None."""
        for pat in reversed(self.patterns):
            if pat.matches(path, is_dir):
                return pat
        return None

    def _excluded(self, path: str, is_dir: bool) -> bool:
        pat = self._last_match(path, is_dir)
        return pat is not None and not pat.negative

    def is_ignored(self, path: str) -> bool:
        """Whether Git ignores the (untracked) file at ``path``.

        Git walks the tree top-down and does not descend into an excluded
        directory, so a file inside an excluded directory is ignored no
        matter what later negation patterns say.
        """
        path = path.lstrip("/")
        while path.startswith("./"):
            path = path[2:]
        parts = path.split("/")
        for i in range(1, len(parts)):
            if self._excluded("/".join(parts[:i]), True):
                return True
        return self._excluded(path, False)

    def ignored_files(self, paths: list[str]) -> list[str]:
        """The ignored paths among ``paths``, sorted."""
        return sorted(p for p in paths if self.is_ignored(p))
