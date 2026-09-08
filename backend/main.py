"""RepoLens FastAPI application."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.file_selector import SelectedFile, rank_repository_files, select_file_contents
from backend.github_client import (
    GitHubClient,
    GitHubClientError,
    parse_repository_url,
)

logger = logging.getLogger("repolens")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="RepoLens API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRepositoryInput(BaseModel):
    repositoryUrl: str = Field(min_length=1)


class AskRepositoryInput(BaseModel):
    repositoryUrl: str = Field(min_length=1)
    question: str = Field(min_length=1)


class ErrorResponse(BaseModel):
    error: str


def _file_description(selected_file: SelectedFile) -> str:
    if selected_file.path.lower().endswith("readme.md"):
        return "Repository documentation and the fastest starting point for understanding the project."
    if selected_file.score >= 40:
        return "A high-signal entry or project metadata file selected early in the repository reading path."
    if selected_file.score >= 25:
        return "A likely application entry point or core module selected by the deterministic file ranking."
    return "A supporting source file selected because it adds useful context to the repository structure."


def _placeholder_analysis(
    metadata: Any, selected_files: list[SelectedFile], repository_url: str
) -> dict[str, Any]:
    entrypoint_names = {
        "main.py",
        "app.py",
        "server.py",
        "cli.py",
        "train.py",
        "run.py",
        "index.js",
        "index.ts",
        "index.tsx",
        "main.js",
        "main.ts",
        "main.tsx",
    }
    entry_points = [
        file
        for file in selected_files
        if file.path.rsplit("/", 1)[-1].lower() in entrypoint_names
    ][:5]
    if not entry_points:
        entry_points = selected_files[: min(3, len(selected_files))]

    key_files = selected_files[:8]
    description = metadata.description.strip()
    overview = description or (
        f"A public {metadata.language} repository with {len(selected_files)} high-signal "
        "files selected for a bounded first read. The initial analysis is deterministic "
        "and intentionally stops before LLM interpretation."
    )
    architecture = [
        f"GitHub metadata and the {metadata.default_branch} branch define the repository snapshot.",
        f"The deterministic selector ranked {len(selected_files)} files from the public repository tree.",
        "Entry points, project metadata, and shallow core modules are prioritized before deeper files.",
        "The next analysis stage can use the bounded file context without downloading the whole repository.",
    ]
    return {
        "repositoryUrl": repository_url,
        "owner": metadata.owner,
        "repositoryName": f"{metadata.owner}/{metadata.repo}",
        "description": description,
        "defaultBranch": metadata.default_branch,
        "overview": overview,
        "language": metadata.language,
        "stars": metadata.stars,
        "entryPoints": [
            {
                "path": file.path,
                "kind": "entry",
                "description": _file_description(file),
            }
            for file in entry_points
        ],
        "keyFiles": [
            {
                "path": file.path,
                "kind": _file_kind(file.path),
                "description": _file_description(file),
            }
            for file in key_files
        ],
        "architecture": architecture,
        "analyzedAt": datetime.now(timezone.utc).isoformat(),
        "selectedFileCount": len(selected_files),
        "selectedTotalChars": sum(file.included_chars for file in selected_files),
        "selectedFiles": [
            {
                "path": file.path,
                "score": file.score,
                "includedChars": file.included_chars,
                "truncated": file.truncated,
            }
            for file in selected_files
        ],
    }


def _file_kind(path: str) -> str:
    lowered = path.lower()
    filename = lowered.rsplit("/", 1)[-1]
    if filename.endswith(".md"):
        return "docs"
    if filename in {"package.json", "pyproject.toml", "requirements.txt", "go.mod"}:
        return "config"
    if "test" in filename or "/test" in lowered or "/tests" in lowered:
        return "test"
    return "module"


def _error_response(error: GitHubClientError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": error.message})


@app.get("/api/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", responses={400: {"model": ErrorResponse}})
def analyze_repository(payload: AnalyzeRepositoryInput) -> JSONResponse:
    try:
        repository = parse_repository_url(payload.repositoryUrl)
        client = GitHubClient()
        metadata = client.get_repository_metadata(repository)
        tree = client.get_recursive_tree(repository, metadata.default_branch)
        ranked_candidates = rank_repository_files(tree)

        logger.info(
            "ranked candidates:\n%s",
            "\n".join(f"{candidate.score:>3}  {candidate.path}" for candidate in ranked_candidates),
        )

        fetched_files: list[tuple[Any, str]] = []
        for candidate in ranked_candidates:
            try:
                content = client.fetch_file(
                    repository, metadata.default_branch, candidate.path
                )
            except GitHubClientError as error:
                logger.info("skipping %s: %s", candidate.path, error.message)
                continue
            fetched_files.append((candidate, content))

        selected_files = select_file_contents(fetched_files)
        total_chars = sum(file.included_chars for file in selected_files)
        logger.info(
            "selected files=%s total_included_chars=%s",
            len(selected_files),
            total_chars,
        )
        return JSONResponse(
            content=_placeholder_analysis(
                metadata, selected_files, payload.repositoryUrl.strip()
            )
        )
    except GitHubClientError as error:
        return _error_response(error)
    except Exception:
        logger.exception("unexpected repository analysis failure")
        return JSONResponse(
            status_code=502,
            content={"error": "The repository could not be analyzed right now. Try again."},
        )


@app.post("/api/ask", responses={400: {"model": ErrorResponse}})
def ask_repository(payload: AskRepositoryInput) -> dict[str, Any]:
    try:
        repository = parse_repository_url(payload.repositoryUrl)
    except GitHubClientError as error:
        return JSONResponse(status_code=400, content={"error": error.message})

    if len(payload.question.strip()) < 3:
        return JSONResponse(
            status_code=400,
            content={"error": "Ask a question with a little more detail."},
        )

    return {
        "answer": (
            f"For {repository.owner}/{repository.repo}, start with the highest-ranked "
            "entry point and follow its imports into the core module. RepoLens has "
            "ingested a bounded snapshot for this repository, but the answer stage is "
            "still deterministic placeholder output until an LLM is added."
        ),
        "sources": ["README.md", "package.json", "src/index.ts"],
    }