# Implementation Plan

Phased roadmap for building GitHub Repository Chat from scratch. Each phase ends with a demo-able milestone.

**Estimated total:** 3–4 weeks part-time for a single developer (Phases 0–4).

---

## Phase 0 — Project foundation

**Goal:** Runnable project skeleton with config and CLI stub.

### Tasks

- [x] Initialize `pyproject.toml` with dependencies:
  - `google-genai`, `chromadb`, `typer`, `pydantic-settings`, `python-dotenv`
  - Dev: `pytest`, `ruff`, `mypy` (optional)
- [x] Create `src/github_repo_chat/` package layout (see README)
- [x] Add `config.py` with `Settings` model and `.env.example`
- [x] Implement CLI skeleton: `index`, `ask`, `chat`, `list`, `delete` (stubs)
- [x] Add `data/` and `.chroma/` to `.gitignore`
- [x] Add basic `pytest` smoke test (`test_config_loads`)



### Milestone

```bash
github-repo-chat --help   # shows all commands
```



### Acceptance criteria

- `pip install -e .` succeeds
- Settings load from `.env` with validation errors for missing `GEMINI_API_KEY`

---



## Phase 1 — Repository ingestion

**Goal:** Clone a GitHub repo and produce structured file records.

### Tasks

- [x] `ingestion/github.py`
  - Parse `https://github.com/owner/repo` URLs
  - Shallow clone to `data/repos/{owner}_{repo}/`
  - Support `--branch`, `--local-path` (skip clone)
- [x] `ingestion/scanner.py`
  - Recursive file walk with extension allowlist
  - Respect `.gitignore` via `pathspec`
  - Skip binaries and files > 500 KB
  - Detect language from extension
- [x] Unit tests with a small fixture directory
- [ ] CLI: `index` prints file count and exits (no embedding yet)



### Milestone

```bash
github-repo-chat index https://github.com/psf/requests --dry-run
# → "Found 142 indexable files"
```



### Acceptance criteria

- Public repo clones without token
- `node_modules/`, `.git/`, `__pycache__/` excluded
- Returns stable file list across runs

---



## Phase 2 — Code chunking

**Goal:** Convert files into embeddable chunks with metadata.

### Tasks

- [ ] `ingestion/chunker.py`
  - Sliding-window splitter with overlap
  - Prepend file header (path, language, lines) to chunk text
  - Compute stable chunk IDs (SHA-256 prefix)
  - Token counting via `tiktoken` or character heuristic (~4 chars/token)
- [ ] Handle edge cases: empty files, single-line files, UTF-8 decode errors
- [ ] Tests: Python file with multiple functions → multiple chunks with correct line ranges



### Milestone

```bash
github-repo-chat index ... --chunks-only
# → writes chunks.jsonl for inspection
```



### Acceptance criteria

- No chunk exceeds `MAX_CHUNK_TOKENS`
- Adjacent chunks overlap by configured amount
- Metadata includes `file_path`, `start_line`, `end_line`, `language`

---



## Phase 3 — Embedding and ChromaDB indexing

**Goal:** Persist embedded chunks in ChromaDB.

### Tasks

- [ ] `indexing/embeddings.py`
  - Wrap `GoogleGeminiEmbeddingFunction` or custom `EmbeddingFunction`
  - Separate document vs query task types
  - Batch embed with retry/backoff
- [ ] `indexing/chroma_store.py`
  - `PersistentClient` initialization
  - `get_or_create_collection(repo_id)`
  - `upsert_chunks(chunks)` with metadata
  - `delete_collection(repo_id)`, `list_collections()`
- [ ] Wire `index` command end-to-end: clone → scan → chunk → embed → store
- [ ] Progress output (tqdm or rich): files processed, chunks upserted
- [ ] Integration test with mocked embedder writing to temp Chroma dir



### Milestone

```bash
github-repo-chat index https://github.com/psf/requests --name requests
github-repo-chat list
# → requests (1,247 chunks)
```



### Acceptance criteria

- Re-running `index` upserts without duplicate IDs
- Chroma data persists across process restarts
- Indexing 500-file repo completes without OOM (batch embed)

---



## Phase 4 — Retrieval and RAG generation

**Goal:** Answer natural language questions with grounded responses.

### Tasks

- [ ] `retrieval/retriever.py`
  - Embed query (`RETRIEVAL_QUERY`)
  - Query collection with `n_results=TOP_K` and repo filter
  - Deduplicate highly overlapping results
- [ ] `generation/prompts.py` — system + context templates
- [ ] `generation/chat.py`
  - Build prompt from retrieved chunks
  - Call Gemini chat API
  - Parse/format response with source citations
- [ ] CLI: `ask "How does Session work?"`
- [ ] CLI: `chat` REPL with `--repo` flag; re-retrieve each turn



### Milestone

```bash
github-repo-chat ask "What HTTP adapters are supported?" --repo requests
# → Grounded answer citing requests/adapters.py
```



### Acceptance criteria

- Answers include at least one file path citation when relevant code exists
- Empty retrieval returns helpful message without LLM call
- `TOP_K` configurable via env/flag

---



## Phase 5 — Incremental indexing and polish

**Goal:** Production-quality developer experience.

### Tasks

- [ ] Incremental re-index: hash files; skip unchanged; delete chunks for removed files
- [ ] `--path` filter during index and query
- [ ] `rich` or `click` progress bars and colored output
- [ ] Logging (structured, configurable level)
- [ ] README quick start verified on clean machine
- [ ] GitHub Actions CI: lint + pytest
- [ ] Optional: tree-sitter chunking for Python and JavaScript



### Milestone

```bash
github-repo-chat reindex requests
# → "Updated 12 files, skipped 130 unchanged, removed 2 deleted"
```



### Acceptance criteria

- Second index run is significantly faster than first
- CI passes on PR
- Documentation matches actual CLI flags

---



## Phase 6 — Optional enhancements

Pick based on user need; not required for v1 release.


| Enhancement                            | Effort | Value                |
| -------------------------------------- | ------ | -------------------- |
| FastAPI + web chat UI                  | Medium | Non-CLI users        |
| Hybrid BM25 + vector search            | Medium | Symbol/name queries  |
| Multi-repo query (`--repo a --repo b`) | Low    | Compare libraries    |
| GitHub Action to pre-index on push     | Medium | Always-fresh index   |
| Docker Compose one-liner               | Low    | Easier onboarding    |
| Conversation export (JSON/Markdown)    | Low    | Share answers        |
| Reranker (Cohere or local)             | Medium | Better top-k quality |


---



## Dependency list (reference)

```toml
[project]
dependencies = [
    "google-genai>=1.0",
    "chromadb>=0.5",
    "typer>=0.12",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0",
    "gitpython>=3.1",
    "pathspec>=0.12",
    "rich>=13.0",
    "tiktoken>=0.7",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio", "ruff>=0.4"]
treesitter = ["tree-sitter>=0.22"]
```

---



## Risk register


| Risk                                  | Impact                | Mitigation                                              |
| ------------------------------------- | --------------------- | ------------------------------------------------------- |
| Gemini API rate limits on large repos | Index fails mid-run   | Batch + backoff; resume from last batch                 |
| Poor retrieval for exact symbol names | Wrong/missing answers | Phase 6 hybrid search; mention `--path` in docs         |
| Huge files skew chunks                | Noise in results      | Strict size cap; split large files carefully            |
| Embedding model deprecation           | Re-index required     | Pin model in config; document migration                 |
| Code sent to third-party API          | Compliance blockers   | Document in README; optional self-hosted embedder later |


---



## Definition of done (v1.0)

- [ ] Index public GitHub repo by URL
- [ ] Ask questions and receive cited answers via CLI
- [ ] Interactive chat session per repo
- [ ] List and delete indexed repos
- [ ] README quick start works end-to-end
- [ ] Architecture and plan docs reflect shipped behavior
- [ ] Basic test suite in CI

---



## Suggested build order (first sprint)

If starting today, implement in this sequence for fastest path to a working demo:

1. **Day 1–2:** Phase 0 + Phase 1 (clone + scan)
2. **Day 3:** Phase 2 (chunker)
3. **Day 4–5:** Phase 3 (Chroma + Gemini embed) — *first working index*
4. **Day 6–7:** Phase 4 (ask + chat) — *first working RAG demo*
5. **Week 2+:** Phase 5 polish and Phase 6 as needed

---



## Open questions

Resolve before or during implementation:

1. **Default chat model** — `gemini-2.0-flash` vs `gemini-2.5-pro` for quality/latency tradeoff?
2. **Chunk size** — 512 tokens default; tune on a real monorepo?
3. **Private repo priority** — Required for v1 or document as v1.1?
4. **License** — MIT assumed; confirm before publish.

