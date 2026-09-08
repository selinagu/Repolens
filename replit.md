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
- API: Express 5 with Zod validation
- Frontend: React + TypeScript + Vite + TanStack Query
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `artifacts/repolens/src/App.tsx` — main RepoLens workspace and API-backed interaction states
- `artifacts/repolens/src/index.css` — RepoLens visual theme, typography, and responsive styles
- `artifacts/api-server/src/routes/repositories.ts` — mock `/api/analyze` and `/api/ask` handlers
- `lib/api-spec/openapi.yaml` — source of truth for request and response contracts
- `lib/api-client-react/src/generated/` — generated React Query hooks

## Architecture decisions

- The first version intentionally uses realistic backend mock data; no GitHub API or LLM integration is configured.
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
- The backend remains mock-only until a future request explicitly adds external GitHub or AI integrations.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
