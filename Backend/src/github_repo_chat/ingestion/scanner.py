"""Repository file scanning.

Phase 1 responsibilities:
  - Walk a cloned/local repo and produce a stable, filtered list of
    "indexable" files: recognized source/doc extensions, under the size
    cap, not binary.
  - Respect .gitignore (see design note below) so node_modules/, .git/,
    __pycache__/, build artifacts, etc. never make it into the index.

Design note on .gitignore handling
-----------------------------------
Rather than re-implementing gitignore pattern matching (nested
.gitignore files, negation, directory-only rules, etc. are genuinely
fiddly to get right with `pathspec`), this scanner asks git itself
which files are tracked via `git ls-files`. A file that's gitignored,
or simply never committed, won't show up there — so we get correct
.gitignore semantics for free, at every directory level, without
maintaining any pattern-matching code.

Trade-off to be aware of: this means we only index *tracked* files.
An uncommitted-but-not-ignored file in a working directory (e.g. someone
passed --local-path to a repo with uncommitted changes) won't be picked
up. For a "chat with this repo" tool that's indexing a specific clone/
commit, that's the right behavior in the common case -- but flag it if
you want --local-path to also pick up dirty/untracked changes; that
would need a supplementary os.walk + pathspec pass just for that mode.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, Repo

DEFAULT_MAX_FILE_SIZE_BYTES = 500 * 1024  # 500 KB, per Phase 1 spec

# Extension -> language name. Extend as needed; anything not listed here
# is treated as "unrecognized" and skipped (counted, not silently dropped).
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".scala": "scala",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".vue": "vue",
    ".md": "markdown",
    ".mdx": "markdown",
    ".rst": "restructuredtext",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".ini": "ini",
    ".cfg": "ini",
    ".dart": "dart",
    ".lua": "lua",
    ".r": "r",
    ".pl": "perl",
    ".m": "objective-c",
    ".ex": "elixir",
    ".exs": "elixir",
    ".clj": "clojure",
    ".hs": "haskell",
    ".tf": "terraform",
    ".txt": "text",
}

# Files without an extension that we still want to recognize.
SPECIAL_FILENAMES: dict[str, str] = {
    "Dockerfile": "dockerfile",
    "Makefile": "makefile",
    "Rakefile": "ruby",
    "Gemfile": "ruby",
    "CMakeLists.txt": "cmake",
}


class ScanError(RuntimeError):
    """Raised when a repository can't be scanned (not a git repo, etc.)."""


@dataclass(frozen=True)
class FileRecord:
    """A single file selected for indexing."""

    path: str  # POSIX-style path relative to repo root
    absolute_path: Path
    language: str
    size_bytes: int


@dataclass
class ScanResult:
    files: list[FileRecord]
    skipped: dict[str, int]  # reason -> count, e.g. {"binary": 3, "too_large": 1}
    total_tracked: int

    @property
    def indexable_count(self) -> int:
        return len(self.files)

    def summary(self) -> str:
        parts = [f"Found {self.indexable_count} indexable files"]
        if self.skipped:
            reasons = ", ".join(f"{count} {reason}" for reason, count in sorted(self.skipped.items()))
            parts.append(f"(skipped: {reasons})")
        return " ".join(parts)


def _tracked_files(repo_root: Path) -> list[str]:
    """List git-tracked files, relative to repo_root, POSIX-style."""
    try:
        repo = Repo(repo_root)
    except InvalidGitRepositoryError as exc:
        raise ScanError(f"'{repo_root}' is not a git repository.") from exc

    try:
        output = repo.git.ls_files()
    except GitCommandError as exc:
        raise ScanError(f"Failed to list tracked files in '{repo_root}': {exc}") from exc

    return [line for line in output.splitlines() if line.strip()]


def _detect_language(path: Path) -> str | None:
    if path.name in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[path.name]
    return EXTENSION_LANGUAGE_MAP.get(path.suffix.lower()) or None


def _is_probably_binary(path: Path, sample_size: int = 8192) -> bool:
    """Cheap binary sniff: null bytes or invalid UTF-8 in the first chunk."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(sample_size)
    except OSError:
        return True

    if b"\x00" in chunk:
        return True
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def scan_repository(
    repo_root: Path,
    *,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
) -> ScanResult:
    """Scan a cloned/local repo and return the indexable file list.

    Files are skipped (and counted, not silently dropped) if they are:
      - not git-tracked (includes anything covered by .gitignore)
      - an unrecognized extension
      - larger than max_file_size_bytes
      - binary

    Empty files are NOT skipped here -- that's a chunking-time decision
    (Phase 2 handles the empty-file edge case explicitly).
    """
    repo_root = repo_root.resolve()
    tracked = _tracked_files(repo_root)

    files: list[FileRecord] = []
    skipped: Counter[str] = Counter()

    for rel_path in tracked:
        abs_path = repo_root / rel_path

        # Tracked but missing from disk -- e.g. a submodule gitlink entry,
        # or a symlink whose target doesn't exist in a shallow clone.
        if not abs_path.is_file():
            skipped["missing"] += 1
            continue

        language = _detect_language(abs_path)
        if language is None:
            skipped["unrecognized_extension"] += 1
            continue

        try:
            size = abs_path.stat().st_size
        except OSError:
            skipped["unreadable"] += 1
            continue

        if size > max_file_size_bytes:
            skipped["too_large"] += 1
            continue

        if _is_probably_binary(abs_path):
            skipped["binary"] += 1
            continue

        files.append(
            FileRecord(path=rel_path, absolute_path=abs_path, language=language, size_bytes=size)
        )

    files.sort(key=lambda f: f.path)  # stable order across runs
    return ScanResult(files=files, skipped=dict(skipped), total_tracked=len(tracked))