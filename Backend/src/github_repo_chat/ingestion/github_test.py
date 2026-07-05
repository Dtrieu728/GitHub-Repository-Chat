import pytest

from github_repo_chat.ingestion.github import (
    GitHubURLError,
    RepoCloneError,
    clone_or_update,
    parse_github_url,
    resolve_local_path,
)


# ---- URL parsing -----------------------------------------------------

@pytest.mark.parametrize(
    "url,expected_owner,expected_repo,expected_branch",
    [
        ("https://github.com/psf/requests", "psf", "requests", None),
        ("https://github.com/psf/requests/", "psf", "requests", None),
        ("https://github.com/psf/requests.git", "psf", "requests", None),
        ("http://github.com/psf/requests", "psf", "requests", None),
        ("github.com/psf/requests", "psf", "requests", None),
        ("www.github.com/psf/requests", "psf", "requests", None),
        ("git@github.com:psf/requests.git", "psf", "requests", None),
        ("https://github.com/psf/requests/tree/main", "psf", "requests", "main"),
        (
            "https://github.com/psf/requests/blob/main/setup.py",
            "psf",
            "requests",
            "main",
        ),
    ],
)
def test_parse_valid_urls(url, expected_owner, expected_repo, expected_branch):
    ref = parse_github_url(url)
    assert ref.owner == expected_owner
    assert ref.repo == expected_repo
    assert ref.branch == expected_branch
    assert ref.slug == f"{expected_owner}/{expected_repo}"
    assert ref.dir_name == f"{expected_owner}_{expected_repo}"


def test_explicit_branch_overrides_url_inferred_branch():
    ref = parse_github_url(
        "https://github.com/psf/requests/tree/main", branch="v2.31.0"
    )
    assert ref.branch == "v2.31.0"


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "   ",
        "https://gitlab.com/owner/repo",
        "https://github.com/",
        "not-a-url-at-all",
        "https://github.com/settings",
    ],
)
def test_parse_invalid_urls_raise(bad_url):
    with pytest.raises(GitHubURLError):
        parse_github_url(bad_url)


# ---- local path resolution --------------------------------------------

def test_resolve_local_path_missing_raises(tmp_path):
    with pytest.raises(RepoCloneError):
        resolve_local_path(str(tmp_path / "does-not-exist"))


def test_resolve_local_path_not_a_repo_raises(tmp_path):
    d = tmp_path / "plain_dir"
    d.mkdir()
    with pytest.raises(RepoCloneError):
        resolve_local_path(str(d))


# ---- real network clone (uses a tiny public repo) ----------------------

@pytest.mark.network
def test_clone_and_reclone_is_idempotent(tmp_path):
    ref = parse_github_url("https://github.com/octocat/Hello-World")
    dest = clone_or_update(ref, tmp_path)
    assert dest.exists()
    assert (dest / ".git").exists()

    # Re-running should update in place, not fail or duplicate.
    dest2 = clone_or_update(ref, tmp_path)
    assert dest2 == dest