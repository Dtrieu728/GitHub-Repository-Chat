from pathlib import Path

import typer

from github_repo_chat.ingestion.github import (
    GitHubURLError,
    RepoCloneError,
    clone_or_update,
    parse_github_url,
    resolve_local_path,
)
from github_repo_chat.ingestion.scanner import ScanError, scan_repository

app = typer.Typer(
    name="github-repo-chat",
    help="Index GitHub repositories and query them with natural language.",
    no_args_is_help=True,
)

DEFAULT_REPOS_ROOT = Path("data/repos")


def _looks_like_local_path(source: str) -> bool:
    """Heuristic: does `source` look like a filesystem path rather than a URL?"""
    return not (
        source.startswith("http://")
        or source.startswith("https://")
        or source.startswith("git@")
        or "github.com" in source
    )


@app.command()
def index(
    source: str = typer.Argument(..., help="GitHub URL or local repository path."),
    name: str | None = typer.Option(None, "--name", "-n", help="Repository alias for queries."),
    branch: str | None = typer.Option(None, "--branch", "-b", help="Git branch to index."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Scan files without indexing."),
) -> None:
    """Clone a repository, chunk source files, and store embeddings in ChromaDB."""
    try:
        if _looks_like_local_path(source):
            repo_path = resolve_local_path(source)
            typer.echo(f"Using local repository: {repo_path}")
        else:
            ref = parse_github_url(source, branch=branch)
            typer.echo(f"Resolving {ref.slug}" + (f" (branch: {ref.branch})" if ref.branch else "") + "...")
            repo_path = clone_or_update(ref, DEFAULT_REPOS_ROOT)
            typer.echo(f"Cloned to {repo_path}")
    except GitHubURLError as exc:
        typer.secho(f"Invalid source: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    except RepoCloneError as exc:
        typer.secho(f"Clone failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    try:
        result = scan_repository(repo_path)
    except ScanError as exc:
        typer.secho(f"Scan failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    typer.echo(result.summary())

    if dry_run:
        typer.echo("(dry run -- no chunking or embedding performed)")
        raise typer.Exit(code=0)

    # Chunking (Phase 2) and embedding/storage (Phase 3) land here next.
    typer.secho(
        "[stub] chunking + embedding not implemented yet -- coming in Phase 2/3",
        fg=typer.colors.YELLOW,
    )


@app.command()
def ask(
    question: str = typer.Argument(..., help="Natural language question about the codebase."),
    repo: str | None = typer.Option(None, "--repo", "-r", help="Indexed repository name."),
    top_k: int | None = typer.Option(None, "--top-k", help="Number of chunks to retrieve."),
) -> None:
    """Ask a single question against an indexed repository."""
    typer.echo(f"[stub] ask question={question!r} repo={repo!r} top_k={top_k}")


@app.command()
def chat(
    repo: str = typer.Option(..., "--repo", "-r", help="Indexed repository name."),
) -> None:
    """Start an interactive chat session for an indexed repository."""
    typer.echo(f"[stub] chat repo={repo!r}")


@app.command("list")
def list_repos() -> None:
    """List indexed repositories."""
    typer.echo("[stub] list indexed repositories")


@app.command()
def delete(
    repo: str = typer.Argument(..., help="Indexed repository name to remove."),
) -> None:
    """Delete an indexed repository from ChromaDB."""
    typer.echo(f"[stub] delete repo={repo!r}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()