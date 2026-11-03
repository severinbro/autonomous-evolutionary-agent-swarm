"""Decide which files Git ignores given a single top-level ``.gitignore``."""

from __future__ import annotations

from .patterns import Pattern, parse


class GitIgnore:
    """Matcher built from the full text of a repository-root ``.gitignore``."""

    def __init__(self, text: str):
        if isinstance(text, bytes):
            text = text.decode("utf-8", "surrogateescape")
        self.text = text
        self.patterns: list[Pattern] = parse(text)

    def _excluded(self, path: str, is_dir: bool) -> bool:
        """Result of the last pattern matching ``path`` (False if none)."""
        for pattern in reversed(self.patterns):
            if pattern.match(path, is_dir):
                return not pattern.negated
        return False

    def is_ignored(self, path: str) -> bool:
        """Whether Git ignores the untracked file at ``path``.

        Git walks the tree top-down: if a leading directory is excluded it
        does not descend into it, so everything inside is ignored and no
        negation can re-include it. Otherwise the file itself is checked.
        """
        parts = path.split("/")
        for i in range(1, len(parts)):
            if self._excluded("/".join(parts[:i]), True):
                return True
        return self._excluded(path, False)

    def ignored_files(self, paths: list[str]) -> list[str]:
        """The ignored paths among ``paths``, sorted."""
        return sorted(p for p in paths if self.is_ignored(p))
