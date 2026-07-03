# GitHub Repository Chat

Retrieval-Augmented Generation (RAG) application that indexes GitHub repositories using **Gemini embeddings** and **ChromaDB**, enabling developers to query large codebases through natural language with semantic code retrieval.

## What it does

1. **Index** — Clone or fetch a GitHub repository, parse source files, and split them into code-aware chunks.
2. **Embed** — Generate vector embeddings with Google's Gemini embedding models.
3. **Store** — Persist embeddings and metadata in ChromaDB for fast similarity search.
4. **Query** — Ask questions in plain English; retrieve the most relevant code snippets and generate grounded answers with Gemini.

```
Developer question
       │
       ▼
┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│ Query embed  │────▶│  ChromaDB   │────▶│ Top-k chunks │
│ (Gemini)     │     │  similarity │     │ + metadata   │
└──────────────┘     └─────────────┘     └──────┬───────┘
                                                 │
                                                 ▼
                                          ┌──────────────┐
                                          │ Gemini LLM   │
                                          │ (grounded    │
                                          │  answer)     │
                                          └──────────────┘
```

## Features (planned)

| Feature | Description |
|---------|-------------|
| GitHub indexing | Index public repos by URL or local clone; optional private repos via token |
| Code-aware chunking | Split by functions/classes where possible; fallback to sliding windows |
| Semantic search | Find relevant code by meaning, not just keywords |
| Grounded answers | Responses cite file paths and line ranges from retrieved chunks |
| Multi-repo support | Separate Chroma collections per repository |
| Incremental re-index | Re-index only changed files on subsequent runs |

## Documentation

| Document | Contents |
|----------|----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, components, and tech choices |
| [docs/PLAN.md](docs/PLAN.md) | Phased implementation plan with milestones and tasks |

## Tech stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ |
| Embeddings | Google Gemini (`gemini-embedding-001`) via `google-genai` |
| Vector DB | ChromaDB (persistent local storage) |
| Generation | Gemini (`gemini-2.0-flash` or latest stable) |
| GitHub access | `PyGithub` or `gitpython` + GitHub REST API |
| Code parsing | `tree-sitter` (optional Phase 2+) or regex/heuristic chunking |
| CLI | `typer` or `click` |
| Config | `.env` + `pydantic-settings` |

## Prerequisites

- Python 3.11 or newer
- [Google AI Studio API key](https://aistudio.google.com/apikey) (`GEMINI_API_KEY`)
- Git installed (for cloning repositories)
- Optional: [GitHub personal access token](https://github.com/settings/tokens) for private repos or higher rate limits

## Quick start (once implemented)

```bash
# Clone this project
git clone https://github.com/<you>/GitHub-Repository-Chat.git
cd GitHub-Repository-Chat

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=...

# Index a repository
github-repo-chat index https://github.com/psf/requests --name requests

# Ask a question
github-repo-chat ask "How does retry logic work in this codebase?"

# Interactive chat session
github-repo-chat chat --repo requests
```

## Project structure (target)

```
GitHub-Repository-Chat/
├── src/
│   └── github_repo_chat/
│       ├── __init__.py
│       ├── cli.py                 # CLI entry point
│       ├── config.py              # Settings from env
│       ├── ingestion/
│       │   ├── github.py          # Clone / fetch repo
│       │   ├── scanner.py         # Walk files, apply ignore rules
│       │   └── chunker.py         # Split source into chunks
│       ├── indexing/
│       │   ├── embeddings.py      # Gemini embedding function
│       │   └── chroma_store.py    # ChromaDB collection management
│       ├── retrieval/
│       │   └── retriever.py       # Query + filter + rerank
│       └── generation/
│           ├── prompts.py         # System / user prompt templates
│           └── chat.py              # RAG answer generation
├── tests/
├── data/                          # ChromaDB persistence (gitignored)
├── docs/
│   ├── ARCHITECTURE.md
│   └── PLAN.md
├── pyproject.toml
├── .env.example
└── README.md
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `GITHUB_TOKEN` | No | PAT for private repos / higher API limits |
| `CHROMA_PERSIST_DIR` | No | Path for ChromaDB storage (default: `./data/chroma`) |
| `GEMINI_EMBED_MODEL` | No | Embedding model (default: `gemini-embedding-001`) |
| `GEMINI_CHAT_MODEL` | No | Chat model (default: `gemini-2.0-flash`) |
| `MAX_CHUNK_TOKENS` | No | Max tokens per code chunk (default: `512`) |
| `TOP_K` | No | Chunks retrieved per query (default: `8`) |

## Example queries

- "Where is authentication handled?"
- "Explain the data flow from API request to database write."
- "What tests cover the payment module?"
- "Find all places that call `embed_content`."

## Limitations

- Embedding and generation require network access to Google APIs.
- Very large monorepos may need selective path indexing and batching.
- Answers are only as good as retrieved chunks; obscure or unindexed files won't appear.
- Private repo support depends on a valid GitHub token with `repo` scope.

## Contributing

See [docs/PLAN.md](docs/PLAN.md) for the current implementation roadmap. Pick an unclaimed milestone or open an issue before starting substantial work.

## License

MIT (recommended — add `LICENSE` file when ready)
