import typer

app = typer.Typer(
    name="github-repo-chat",
    help="Index GitHub repositories and query them with natural language.",
    no_args_is_help=True,
)


@app.command()
def index(
    source: str = typer.Argument(..., help="GitHub URL or local repository path."),
    name: str | None = typer.Option(None, "--name", "-n", help="Repository alias for queries."),
    branch: str | None = typer.Option(None, "--branch", "-b", help="Git branch to index."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Scan files without indexing."),
) -> None:
    """Clone a repository, chunk source files, and store embeddings in ChromaDB."""
    typer.echo(f"[stub] index source={source!r} name={name!r} branch={branch!r} dry_run={dry_run}")


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
