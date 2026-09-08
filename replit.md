# RepoLens

RepoLens helps developers understand an unfamiliar public GitHub repository quickly through structured mock analysis and source-cited questions.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server
- `pnpm --filter @workspace/repolens run dev` — run the RepoLens web app
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Python FastAPI with bounded GitHub ingestion
- Frontend: React + TypeScript + Vite + TanStack Query
- API codegen: Orval (from OpenAPI spec)
- Python dependencies: FastAPI + Uvicorn, managed through `pyproject.toml` and `uv.lock`

## Where things live

- `artifacts/repolens/src/App.tsx` — main RepoLens workspace and API-backed interaction states
- `artifacts/repolens/src/index.css` — RepoLens visual theme, typography, and responsive styles
- `backend/github_client.py` — safe GitHub URL parsing, metadata/tree/file fetches, and GitHub API errors
- `backend/file_selector.py` — deterministic eligibility, ranking, and bounded content selection
- `backend/main.py` — FastAPI routes and deterministic placeholder analysis response
- `lib/api-spec/openapi.yaml` — source of truth for request and response contracts
- `lib/api-client-react/src/generated/` — generated React Query hooks

## Architecture decisions

- GitHub ingestion is real, but analysis and Q&A output remain deterministic placeholders until a future LLM stage.
- The app uses the shared `/api` service path, so the frontend can call relative API URLs through the workspace proxy.
- Repository analysis is returned as a structured reading path: overview, architecture, key files, and entry points.

## Product

- Paste a public GitHub repository URL and analyze it.
- Review a concise overview, entry points, key files, and architecture summary.
- Ask a follow-up repository question and see source filenames cited in the answer.
- See loading, invalid URL, backend failure, empty, and responsive states.

## User preferences

- Keep the product compact, precise, and developer-tool oriented; avoid chatbot-like presentation and flashy AI branding.

## Gotchas

- After changing `lib/api-spec/openapi.yaml`, run `pnpm --filter @workspace/api-spec run codegen` before changing frontend or server consumers.
- GitHub calls are unauthenticated and public-only; no user credentials or OAuth are required.
- File ingestion is bounded to 50 ranked candidates, 25 selected files, 10,000 characters per file, and 100,000 characters total.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
