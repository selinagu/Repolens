"""RepoLens FastAPI application."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.analyzer import (
    AnalysisModelInvalidResponse,
    AnalysisModelUnavailable,
    Citation,
    RepositoryAnalyzer,
    create_analysis_model,
)
from backend.file_selector import (
    SelectedFile,
    rank_repository_files,
    select_file_contents,
)
from backend.github_client import (
    GitHubClient,
    GitHubClientError,
    RepositoryMetadata,
    parse_repository_url,
)

logger = logging.getLogger("repolens")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="RepoLens API", version="0.3.0")
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


MODEL_ROUTE_RESPONSES = {
    400: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@dataclass(frozen=True)
class IngestedRepository:
    metadata: RepositoryMetadata
    selected_files: list[SelectedFile]


ANALYZER = RepositoryAnalyzer(create_analysis_model())


def _ingest_repository(repository_url: str) -> IngestedRepository:
    repository = parse_repository_url(repository_url)
    client = GitHubClient()
    metadata = client.get_repository_metadata(repository)
    tree = client.get_recursive_tree(repository, metadata.default_branch)
    ranked_candidates = rank_repository_files(tree)

    logger.info(
        "ranked candidates:\n%s",
        "\n".join(
            f"{candidate.score:>3}  {candidate.path}" for candidate in ranked_candidates
        ),
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
    logger.info(
        "selected files=%s total_included_chars=%s",
        len(selected_files),
        sum(file.included_chars for file in selected_files),
    )
    return IngestedRepository(metadata=metadata, selected_files=selected_files)


def _error_response(error: GitHubClientError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": error.message})


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


def _format_citation(citation: Citation) -> str:
    return f"{citation.path}:L{citation.start_line}-L{citation.end_line}"


@app.get("/api/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", responses=MODEL_ROUTE_RESPONSES)
def analyze_repository(payload: AnalyzeRepositoryInput) -> JSONResponse:
    try:
        ingested = _ingest_repository(payload.repositoryUrl)
        analysis = ANALYZER.analyze(ingested.metadata, ingested.selected_files)
        return JSONResponse(
            content={
                "repositoryUrl": payload.repositoryUrl.strip(),
                "owner": ingested.metadata.owner,
                "repositoryName": f"{ingested.metadata.owner}/{ingested.metadata.repo}",
                "description": ingested.metadata.description.strip(),
                "defaultBranch": ingested.metadata.default_branch,
                "overview": analysis.overview.text,
                "language": ingested.metadata.language,
                "stars": ingested.metadata.stars,
                "entryPoints": [
                    {
                        "path": item.path,
                        "kind": "entry",
                        "description": item.reason,
                    }
                    for item in analysis.entry_points
                ],
                "keyFiles": [
                    {
                        "path": item.path,
                        "kind": _file_kind(item.path),
                        "description": item.reason,
                    }
                    for item in analysis.key_files
                ],
                "architecture": [
                    f"{item.name}: {item.description}" for item in analysis.architecture
                ],
                "analyzedAt": datetime.now(timezone.utc).isoformat(),
                "selectedFileCount": len(ingested.selected_files),
                "selectedTotalChars": sum(
                    file.included_chars for file in ingested.selected_files
                ),
                "selectedFiles": [
                    {
                        "path": file.path,
                        "score": file.score,
                        "includedChars": file.included_chars,
                        "truncated": file.truncated,
                    }
                    for file in ingested.selected_files
                ],
            }
        )
    except GitHubClientError as error:
        return _error_response(error)
    except AnalysisModelUnavailable:
        logger.exception("repository analysis provider unavailable")
        return JSONResponse(
            status_code=503,
            content={"error": "The analysis service is temporarily unavailable."},
        )
    except AnalysisModelInvalidResponse:
        logger.exception("repository analysis provider returned invalid output")
        return JSONResponse(
            status_code=502,
            content={"error": "The analysis service returned an invalid response."},
        )
    except Exception:
        logger.exception("unexpected repository analysis failure")
        return JSONResponse(
            status_code=502,
            content={
                "error": "The repository could not be analyzed right now. Try again."
            },
        )


@app.post("/api/ask", responses=MODEL_ROUTE_RESPONSES)
def ask_repository(payload: AskRepositoryInput) -> dict[str, Any]:
    try:
        parse_repository_url(payload.repositoryUrl)
    except GitHubClientError as error:
        return JSONResponse(status_code=400, content={"error": error.message})

    if len(payload.question.strip()) < 3:
        return JSONResponse(
            status_code=400,
            content={"error": "Ask a question with a little more detail."},
        )

    try:
        ingested = _ingest_repository(payload.repositoryUrl)
        answer = ANALYZER.answer(
            ingested.metadata, ingested.selected_files, payload.question.strip()
        )
        return {
            "answer": answer.answer,
            "sources": [_format_citation(citation) for citation in answer.citations],
        }
    except GitHubClientError as error:
        return _error_response(error)
    except AnalysisModelUnavailable:
        logger.exception("repository answer provider unavailable")
        return JSONResponse(
            status_code=503,
            content={"error": "The analysis service is temporarily unavailable."},
        )
    except AnalysisModelInvalidResponse:
        logger.exception("repository answer provider returned invalid output")
        return JSONResponse(
            status_code=502,
            content={"error": "The analysis service returned an invalid response."},
        )
    except Exception:
        logger.exception("unexpected repository answer failure")
        return JSONResponse(
            status_code=502,
            content={
                "error": "The repository could not be queried right now. Try again."
            },
        )
