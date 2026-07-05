from pathlib import Path

import pytest
from git import Repo

from github_repo_chat.ingestion.github import clone_or_update, parse_github_url
from github_repo_chat.ingestion.scanner import ScanError, scan_repository


def _make_fixture_repo(tmp_path: Path) -> Path:
    """Build a small real git repo on disk to test scanning against.

    Layout:
      main.py                - recognized, small, text -> included
      README.md               - recognized, small, text -> included
      Dockerfile               - special filename, no extension -> included
      data.xyz                 - unrecognized extension -> skipped
      corrupted.py              - has .py extension but binary content -> skipped
      huge.py                    - recognized but > size cap -> skipped
      node_modules/pkg.js         - gitignored -> never tracked, excluded
      .gitignore
    """
    repo_dir = tmp_path / "fixture_repo"
    repo_dir.mkdir()
    repo = Repo.init(repo_dir)

    (repo_dir / "main.py").write_text("def hello():\n    return 'hi'\n")
    (repo_dir / "README.md").write_text("# Fixture repo\n")
    (repo_dir / "Dockerfile").write_text("FROM python:3.12\n")
    (repo_dir / "data.xyz").write_text("some unrecognized format\n")

    # Binary content despite a .py extension (corrupted / non-text file).
    (repo_dir / "corrupted.py").write_bytes(b"\x00\x01\x02binarygarbage\xff\xfe")

    # A file over the 500 KB cap.
    (repo_dir / "huge.py").write_text("# padding line\n" * 60_000)  # ~840 KB

    # Should never be tracked because it's gitignored.
    node_modules = repo_dir / "node_modules"
    node_modules.mkdir()
    (node_modules / "pkg.js").write_text("module.exports = {};\n")

    (repo_dir / ".gitignore").write_text("node_modules/\n")

    repo.git.add(A=True)  # respects .gitignore
    repo.index.commit("initial commit")
    return repo_dir


def test_scan_fixture_repo_applies_all_filters(tmp_path):
    repo_dir = _make_fixture_repo(tmp_path)
    result = scan_repository(repo_dir)

    included_paths = {f.path for f in result.files}
    assert included_paths == {"main.py", "README.md", "Dockerfile"}

    languages = {f.path: f.language for f in result.files}
    assert languages == {
        "main.py": "python",
        "README.md": "markdown",
        "Dockerfile": "dockerfile",
    }

    # node_modules/pkg.js should never even be counted -- git never tracked it.
    # Tracked: main.py, README.md, Dockerfile, data.xyz, corrupted.py, huge.py, .gitignore
    assert result.total_tracked == 7

    # .gitignore itself is tracked but has no recognized extension, same as data.xyz.
    assert result.skipped["unrecognized_extension"] == 2  # data.xyz, .gitignore
    assert result.skipped["binary"] == 1  # corrupted.py
    assert result.skipped["too_large"] == 1  # huge.py
    assert result.indexable_count == 3


def test_scan_result_is_sorted_and_stable(tmp_path):
    repo_dir = _make_fixture_repo(tmp_path)
    result_a = scan_repository(repo_dir)
    result_b = scan_repository(repo_dir)

    paths_a = [f.path for f in result_a.files]
    paths_b = [f.path for f in result_b.files]
    assert paths_a == paths_b == sorted(paths_a)


def test_summary_string_reports_counts(tmp_path):
    repo_dir = _make_fixture_repo(tmp_path)
    result = scan_repository(repo_dir)
    summary = result.summary()
    assert "Found 3 indexable files" in summary
    assert "1 binary" in summary
    assert "1 too_large" in summary
    assert "2 unrecognized_extension" in summary


def test_scan_non_git_directory_raises(tmp_path):
    plain_dir = tmp_path / "not_a_repo"
    plain_dir.mkdir()
    (plain_dir / "file.py").write_text("print('hi')\n")
    with pytest.raises(ScanError):
        scan_repository(plain_dir)


def test_custom_size_cap_is_respected(tmp_path):
    repo_dir = _make_fixture_repo(tmp_path)
    # A tiny cap should push main.py and README.md into "too_large" too.
    result = scan_repository(repo_dir, max_file_size_bytes=5)
    assert result.indexable_count == 0
    assert result.skipped["too_large"] >= 2


@pytest.mark.network
def test_scan_real_cloned_repo(tmp_path):
    ref = parse_github_url("https://github.com/octocat/Hello-World")
    repo_path = clone_or_update(ref, tmp_path)
    result = scan_repository(repo_path)
    # Hello-World is a near-empty demo repo (basically just a README),
    # so we just assert scanning succeeds and returns a sane, stable result.
    assert result.total_tracked >= 1
    assert result.indexable_count <= result.total_tracked
    paths = [f.path for f in result.files]
    assert paths == sorted(paths)