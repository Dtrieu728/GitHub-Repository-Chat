# GitHub Repository Chat — Backend

Python backend for indexing GitHub repositories and answering questions with RAG (Gemini + ChromaDB).

## Setup

```bash
cd Backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -e ".[dev]"

cp .env.example .env
# Set GEMINI_API_KEY in .env (or use ../.env at repo root)
```

## CLI

```bash
github-repo-chat --help
github-repo-chat index https://github.com/psf/requests --name requests
github-repo-chat ask "How does retry work?" --repo requests
github-repo-chat chat --repo requests
github-repo-chat list
github-repo-chat delete requests
```

## Tests

```bash
pytest
```
