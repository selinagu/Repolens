# RepoLens

RepoLens is a source-grounded AI developer tool for quickly understanding unfamiliar public GitHub repositories.

**[Live Demo](https://repo-lens-developer-tool--sulingu2025.replit.app)**

## What it does

- Paste a public GitHub repository URL.
- Generate a concise repository overview.
- Identify architecture components.
- Surface likely entry points and key files.
- Ask natural-language questions about the codebase.
- Receive answers with validated file- and line-level source citations.

RepoLens is a focused repository-reading tool, not a general-purpose chatbot.

## How it works

Repository analysis follows a bounded pipeline:

```text
GitHub repository
  → metadata + recursive tree
  → deterministic file ranking
  → bounded repository ingestion
  → structured LLM repository analysis
```

Questions use a narrower, query-specific path:

```text
question
  → lexical snippet retrieval
  → bounded source snippets
  → structured LLM answer
  → exact citation validation
```

The LLM does not choose which repository content it sees. RepoLens controls file selection, ingestion budgets, retrieval, and citation validation. The model only interprets context that RepoLens has already selected and bounded.

## Key engineering decisions

### Bounded ingestion

- Considers at most 50 ranked candidates.
- Selects at most 25 files.
- Includes at most 10,000 characters per file.
- Includes at most 100,000 characters in total.
- Never blindly clones a repository and dumps its contents into model context.

### Explainable file ranking

- Uses deterministic heuristic ranking.
- Prioritizes README files, entry points, package interfaces, core source directories, and architecture-relevant filenames.
- Keeps tests eligible at a lower priority.
- Ignores or penalizes generated code, dependencies, and build artifacts.

### Question-specific retrieval

- Uses deterministic lexical retrieval rather than semantic search.
- Matches paths, `snake_case`, `camelCase`, and content tokens.
- Produces line-bounded source snippets.
- Uses no embeddings or vector database in v0.

### Source grounding

- Validates repository-analysis citations against the selected files.
- Validates Q&A citations against the exact snippets supplied to the model.
- Requires cited line ranges to fall entirely within the supplied context.
- Rejects unsupported or hallucinated paths and citation ranges.

### Structured LLM outputs

- Uses a provider-neutral `AnalysisModel` abstraction.
- Uses the OpenAI Responses API with structured outputs in production.
- Retains a deterministic offline implementation for tests and credential-free local development.
- Returns a clean service error when a configured provider fails; it does not silently substitute offline output.

### Untrusted repository content

- Treats source files and documentation as data, never as instructions.
- Explicitly tells the model not to follow instructions embedded in README or source files.

## Architecture

```text
GitHub API
   ↓
github_client.py
   ↓
file_selector.py
   ↓
bounded SelectedFile context
   ├──→ analyzer.py → structured repository analysis
   └──→ retrieval.py → source snippets → grounded Q&A
                              ↓
                     citation validation
                              ↓
                           FastAPI
                              ↓
                     React + TypeScript
```

## Tech stack

- React
- TypeScript
- FastAPI
- Python
- OpenAI API
- GitHub API
- Replit
- Orval and OpenAPI typed client generation

## Reliability and testing

The current suite includes 22 passing Python tests, Ruff static and formatting checks, and a full TypeScript workspace typecheck. Automated model tests use fakes and stubs; unit tests never call the live OpenAI API.

Manual production smoke tests cover:

- Repository analysis.
- Top-p implementation lookup.
- RoPE insufficient-context behavior.
- Checkpoint save/load explanation.
- A nonexistent OAuth feature.
- Invalid provider credentials and clean HTTP 503 handling.

These checks validate representative grounding and failure behavior; they are not presented as a large benchmark suite.

## Example questions

- Where is top-p sampling implemented?
- How is checkpointing handled?
- Where is authentication implemented?
- What files should I read first to understand the model architecture?

## Local development

Sync Python dependencies:

```powershell
uv sync
```

Run the FastAPI backend:

```powershell
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open the interactive API documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Optional environment variables:

- `OPENAI_API_KEY` selects the production OpenAI-backed analysis model.
- `OPENAI_MODEL` overrides the configured OpenAI model.

If `OPENAI_API_KEY` is absent, RepoLens uses the deterministic offline model. Do not commit secrets or local environment files containing credentials.

The frontend workspace command is:

```powershell
pnpm --filter @workspace/repolens run dev
```

The frontend expects its host environment to provide `PORT`, `BASE_PATH`, and routing for the shared `/api` path. Replit supplies this routing for the deployed application.

Regenerate the typed API clients after changing the OpenAPI specification:

```powershell
pnpm --filter @workspace/api-spec run codegen
```

Run the full TypeScript workspace typecheck:

```powershell
pnpm run typecheck
```

## Limitations

These are deliberate v0 tradeoffs:

- Public GitHub repositories only.
- Heuristic file selection rather than full dependency analysis.
- Lexical retrieval can miss semantic matches.
- No AST or dependency-graph analysis yet.
- No embeddings or vector database in v0.
- Large repositories are intentionally sampled under fixed context budgets.
