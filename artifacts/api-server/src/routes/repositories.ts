import { Router, type IRouter } from "express";
import {
  AnalyzeRepositoryBody,
  AnalyzeRepositoryResponse,
  AskRepositoryBody,
  AskRepositoryResponse,
} from "@workspace/api-zod";

const router: IRouter = Router();

const githubUrlPattern =
  /^https?:\/\/(?:www\.)?github\.com\/([^/]+)\/([^/#?]+?)(?:\.git)?\/?(?:[#?].*)?$/i;

const mockRepository = {
  language: "TypeScript",
  stars: 24800,
  overview:
    "A production-minded React framework focused on fast local development and predictable deployment. The repository is organized as a pnpm monorepo, with the application shell, build tooling, and shared packages kept separate so they can evolve independently.",
  entryPoints: [
    {
      path: "packages/create-app/src/index.ts",
      kind: "entry" as const,
      description:
        "CLI entry that parses project options, selects a template, and starts the scaffolding flow.",
    },
    {
      path: "packages/runtime/src/server.ts",
      kind: "entry" as const,
      description:
        "Runtime bootstrap for the development server; wires middleware, routing, and the file watcher.",
    },
  ],
  keyFiles: [
    {
      path: "pnpm-workspace.yaml",
      kind: "config" as const,
      description:
        "Defines workspace package boundaries and keeps the repository's dependency graph centralized.",
    },
    {
      path: "packages/runtime/src/server.ts",
      kind: "module" as const,
      description:
        "Coordinates the request lifecycle and hands application code to the framework runtime.",
    },
    {
      path: "packages/compiler/src/transform.ts",
      kind: "module" as const,
      description:
        "Transforms source files before they reach the runtime, including fast refresh metadata.",
    },
    {
      path: "tests/runtime/server.test.ts",
      kind: "test" as const,
      description:
        "High-signal integration coverage for the runtime's request handling and error boundaries.",
    },
  ],
  architecture: [
    "A CLI package creates projects and delegates to shared templates.",
    "The compiler transforms source modules and emits build artifacts consumed by the runtime.",
    "The runtime owns development-server concerns while application packages stay framework-focused.",
    "Shared utilities and types live in isolated packages to keep the dependency graph directional.",
  ],
};

function getRepositoryName(repositoryUrl: string) {
  const match = githubUrlPattern.exec(repositoryUrl.trim());
  return match ? `${match[1]}/${match[2]}` : null;
}

router.post("/analyze", (req, res) => {
  const parsed = AnalyzeRepositoryBody.safeParse(req.body);

  if (!parsed.success) {
    res.status(400).json({ error: "Enter a public GitHub repository URL." });
    return;
  }

  const repositoryName = getRepositoryName(parsed.data.repositoryUrl);

  if (!repositoryName) {
    res.status(400).json({
      error: "Enter a public GitHub URL like https://github.com/owner/repository.",
    });
    return;
  }

  const data = AnalyzeRepositoryResponse.parse({
    repositoryUrl: parsed.data.repositoryUrl.trim(),
    repositoryName,
    ...mockRepository,
    analyzedAt: new Date().toISOString(),
  });

  res.json(data);
});

router.post("/ask", (req, res) => {
  const parsed = AskRepositoryBody.safeParse(req.body);

  if (!parsed.success || !getRepositoryName(parsed.data.repositoryUrl)) {
    res.status(400).json({
      error: "Add a valid public GitHub repository URL before asking a question.",
    });
    return;
  }

  if (parsed.data.question.trim().length < 3) {
    res.status(400).json({
      error: "Ask a question with a little more detail.",
    });
    return;
  }

  const data = AskRepositoryResponse.parse({
    answer:
      "The main flow starts at the CLI entry point, then hands work to the runtime server. From there, source files move through the compiler before the runtime serves the application. For a first read, follow the path from the package entry to the server bootstrap, then inspect the transform module to understand what happens between source and execution.",
    sources: [
      "packages/create-app/src/index.ts",
      "packages/runtime/src/server.ts",
      "packages/compiler/src/transform.ts",
    ],
  });

  res.json(data);
});

export default router;