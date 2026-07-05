"""GitHub repository URL parsing and cloning.
  - Parse a variety of GitHub URL formats into a structured reference.
  - Shallow-clone the repo to a deterministic local path (or accept an
    existing --local-path to skip cloning entirely).
  - Be idempotent: re-running against an already-cloned repo should
    update it in place rather than fail or re-clone from scratch.
"""

from __future__ import annotations
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from git import GitCommandError, Repo

class GithubURLError(ValueError):
    """
    Raised when a url cannot be parsed as a GitHub repo reference.
    """

class RepoCloneError(RuntimeError):
    """
    Raised when cloning or updating a repo fails.
    """


@dataclass(frozen=True)

class GithubRepoRef:
    """
    A parsed reference to a GitHub repository
    """
    
    owner: str
    repo: str
    branch: str | None = None 
    
    @property
    def slug(self)->str:
        """e.g. 'psf/requests' — used for display and as a dedupe key."""
        return f"{self.owner}/{self.repo}"
    
    @property
    def dir_name(self)->str:
        """Filesystem-safe directory name, e.g. 'psf_requests'."""
        return f"{self.owner}_{self.repo}"
    
    @property
    def clone_url(self)->str:
        """Canonical HTTPS clone URL (works for public repos without a token)."""
        
        return f"https://github.com/{self.owner}/{self.repo}.git"
 

# Matches, after stripping a trailing "/" and optional ".git":
#   https://github.com/owner/repo
#   http://github.com/owner/repo
#   github.com/owner/repo
#   git@github.com:owner/repo
# Also tolerates a trailing /tree/<branch> or /blob/<branch>/... suffix

_HTTPS_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com[:/]"
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)"
    r"(?:\.git)?/?"
    r"(?:(?:/tree/|/blob/)(?P<branch>[^/]+)(?:/.*)?)?$"
)
_SSH_RE = re.compile(
    r"^git@github\.com:(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
 
def parse_github_url(url: str, branch: str | None = None) -> GitHubRepoRef:
    """Parse a GitHub URL into an owner/repo (+ optional branch) reference.
 
    `branch` (e.g. from a --branch CLI flag) always wins over anything
    inferred from a /tree/<branch> suffix in the URL.
 
    Raises GitHubURLError if the URL doesn't look like a GitHub repo.
    """
    url = url.strip()
    if not url:
        raise GitHubURLError("Empty URL provided.")
 
    match = _SSH_RE.match(url) or _HTTPS_RE.match(url)
    if not match:
        raise GitHubURLError(
            f"'{url}' doesn't look like a GitHub repo URL. "
            "Expected something like https://github.com/owner/repo"
        )
 
    owner = match.group("owner")
    repo = match.group("repo")
    inferred_branch = match.groupdict().get("branch")
 
    # Guard against grabbing a non-repo GitHub path, e.g. github.com/settings
    if repo in {"", "settings", "notifications", "marketplace"}:
        raise GitHubURLError(f"'{url}' doesn't look like a valid owner/repo URL.")
 
    return GitHubRepoRef(owner=owner, repo=repo, branch=branch or inferred_branch)
 
 
def clone_or_update(
    ref: GitHubRepoRef,
    dest_root: Path,
    *,
    force_fresh: bool = False,
) -> Path:
    """Ensure `ref` is present locally under dest_root, cloned shallowly.
 
    - If the target dir doesn't exist: shallow clone (depth=1).
    - If it already exists and looks like a valid git repo: fetch + reset
      to the target branch instead of re-cloning (idempotent re-runs).
    - If it exists but is corrupted/not a repo, or force_fresh=True:
      wipe it and clone fresh.
 
    Returns the path to the local repo checkout.
    """
    dest = dest_root / ref.dir_name
 
    if force_fresh and dest.exists():
        shutil.rmtree(dest)
 
    if dest.exists():
        try:
            repo = Repo(dest)
            if repo.bare:
                raise RepoCloneError(f"{dest} exists but is a bare repo; expected a checkout.")
            _update_existing(repo, ref)
            return dest
        except RepoCloneError:
            raise
        except Exception:
            # Not a valid repo (e.g. leftover partial clone) — start clean.
            shutil.rmtree(dest, ignore_errors=True)
 
    dest_root.mkdir(parents=True, exist_ok=True)
    try:
        clone_kwargs = {"depth": 1}
        if ref.branch:
            clone_kwargs["branch"] = ref.branch
        Repo.clone_from(ref.clone_url, dest, **clone_kwargs)
    except GitCommandError as exc:
        shutil.rmtree(dest, ignore_errors=True)
        raise RepoCloneError(
            f"Failed to clone {ref.slug} ({ref.clone_url}): {exc.stderr.strip() if exc.stderr else exc}"
        ) from exc
 
    return dest
 
 
def _update_existing(repo: Repo, ref: GitHubRepoRef) -> None:
    """Fetch latest and fast-forward the existing shallow clone in place."""
    try:
        origin = repo.remotes.origin
        target_branch = ref.branch or _default_branch(repo)
        origin.fetch(target_branch, depth=1)
        repo.git.checkout(target_branch)
        repo.git.reset("--hard", f"origin/{target_branch}")
    except GitCommandError as exc:
        raise RepoCloneError(
            f"Failed to update existing checkout for {ref.slug}: "
            f"{exc.stderr.strip() if exc.stderr else exc}"
        ) from exc
 
 
def _default_branch(repo: Repo) -> str:
    """Best-effort detection of the repo's default branch (main/master/etc)."""
    try:
        return repo.git.symbolic_ref("--short", "HEAD").strip()
    except GitCommandError:
        # Shallow clones sometimes leave HEAD undefined until a fetch happens.
        for candidate in ("main", "master"):
            if candidate in [h.name for h in repo.heads]:
                return candidate
        return "main"
 
 
def resolve_local_path(path: str) -> Path:
    """Validate a --local-path input (used to skip cloning entirely)."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise RepoCloneError(f"Local path does not exist: {p}")
    if not p.is_dir():
        raise RepoCloneError(f"Local path is not a directory: {p}")
    if not (p / ".git").exists():
        raise RepoCloneError(f"'{p}' does not look like a git repository (no .git dir).")
    return p
