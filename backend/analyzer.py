"""Structured repository analysis with validation at the model boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol

from backend.file_selector import SelectedFile
from backend.github_client import RepositoryMetadata
from backend.retrieval import (
    RetrievalResult,
    SourceChunk,
    chunk_selected_files,
    retrieve,
)


class GroundingValidationError(ValueError):
    """Raised when generated output cites sources outside the supplied context."""


@dataclass(frozen=True)
class GroundedText:
    text: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class RepositoryFileAnalysis:
    path: str
    kind: str
    description: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class AnalysisDraft:
    overview: GroundedText
    entry_points: tuple[RepositoryFileAnalysis, ...]
    key_files: tuple[RepositoryFileAnalysis, ...]
    architecture: tuple[GroundedText, ...]


@dataclass(frozen=True)
class AnswerDraft:
    answer: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class AnalysisContext:
    metadata: RepositoryMetadata
    sources: tuple[SourceChunk, ...]


@dataclass(frozen=True)
class QuestionContext:
    metadata: RepositoryMetadata
    question: str
    matches: tuple[RetrievalResult, ...]


class AnalysisModel(Protocol):
    """Narrow interface for a future LLM adapter or the local deterministic model."""

    def analyze(self, context: AnalysisContext) -> AnalysisDraft: ...

    def answer(self, context: QuestionContext) -> AnswerDraft: ...


def source_context_payload(sources: tuple[SourceChunk, ...]) -> list[dict[str, object]]:
    """Build a JSON-serializable, source-labelled input for an LLM adapter."""

    return [
        {
            "id": source.chunk_id,
            "path": source.path,
            "startLine": source.start_line,
            "endLine": source.end_line,
            "content": source.content,
        }
        for source in sources
    ]


def _file_kind(path: str) -> str:
    lowered = path.lower()
    filename = lowered.rsplit("/", 1)[-1]
    if filename.endswith(".md"):
        return "docs"
    if filename in {
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "go.mod",
        "cargo.toml",
        "dockerfile",
    }:
        return "config"
    if "test" in filename or "/test" in lowered or "/tests" in lowered:
        return "test"
    return "module"


def _file_description(path: str, score: int) -> str:
    filename = PurePosixPath(path).name.lower()
    if filename == "readme.md":
        return "Repository documentation and the fastest starting point for understanding the project."
    if score >= 40:
        return "A high-signal entry or project metadata file selected early in the reading path."
    if score >= 25:
        return "A likely application entry point or core module prioritized by file selection."
    return "A supporting source file that adds context to the repository structure."


class DeterministicAnalysisModel:
    """Safe local baseline implementing the same contract expected from an LLM."""

    _ENTRYPOINT_NAMES = {
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

    def analyze(self, context: AnalysisContext) -> AnalysisDraft:
        files: dict[str, SourceChunk] = {}
        for source in context.sources:
            files.setdefault(source.path, source)
        ordered = list(files.values())
        if not ordered:
            return AnalysisDraft(
                overview=GroundedText("No readable source files were selected.", ()),
                entry_points=(),
                key_files=(),
                architecture=(),
            )

        entry_sources = [
            source
            for source in ordered
            if PurePosixPath(source.path).name.lower() in self._ENTRYPOINT_NAMES
        ][:5]
        if not entry_sources:
            entry_sources = ordered[: min(3, len(ordered))]

        description = context.metadata.description.strip()
        overview = description or (
            f"A public {context.metadata.language} repository. RepoLens selected "
            f"{len(ordered)} high-signal files for a bounded first read."
        )
        architecture: list[GroundedText] = []
        for source in ordered[:4]:
            kind = _file_kind(source.path)
            architecture.append(
                GroundedText(
                    f"{source.path} is a selected {kind} source in the repository reading path.",
                    (source.path,),
                )
            )

        def file_analysis(
            source: SourceChunk, kind: str | None = None
        ) -> RepositoryFileAnalysis:
            return RepositoryFileAnalysis(
                path=source.path,
                kind=kind or _file_kind(source.path),
                description=_file_description(source.path, source.selector_score),
                sources=(source.path,),
            )

        return AnalysisDraft(
            overview=GroundedText(overview, (ordered[0].path,)),
            entry_points=tuple(
                file_analysis(source, "entry") for source in entry_sources
            ),
            key_files=tuple(file_analysis(source) for source in ordered[:8]),
            architecture=tuple(architecture),
        )

    def answer(self, context: QuestionContext) -> AnswerDraft:
        if not context.matches:
            return AnswerDraft(
                "No readable selected source was available to answer this question.", ()
            )

        matched = [result for result in context.matches if result.score > 0]
        evidence = matched or list(context.matches[:3])
        paths = tuple(dict.fromkeys(result.chunk.path for result in evidence))
        if matched:
            terms = tuple(
                dict.fromkeys(
                    term for result in matched for term in result.matched_terms
                )
            )
            answer = (
                f"The strongest lexical evidence for this question is in {', '.join(paths)}. "
                f"The selected passages match these query terms: {', '.join(terms)}. "
                "Read those passages in the listed order, then follow their imports or calls "
                "to confirm the runtime flow."
            )
        else:
            answer = (
                "No selected passage contains the question terms directly. The listed files are "
                "the highest-signal fallback sources from the bounded repository snapshot."
            )
        return AnswerDraft(answer=answer, sources=paths)


class RepositoryAnalyzer:
    def __init__(self, model: AnalysisModel | None = None):
        self.model = model or DeterministicAnalysisModel()

    def analyze(
        self, metadata: RepositoryMetadata, selected_files: list[SelectedFile]
    ) -> AnalysisDraft:
        sources = tuple(chunk_selected_files(selected_files))
        draft = self.model.analyze(AnalysisContext(metadata=metadata, sources=sources))
        self._validate_analysis(draft, {source.path for source in sources})
        return draft

    def answer(
        self,
        metadata: RepositoryMetadata,
        selected_files: list[SelectedFile],
        question: str,
    ) -> AnswerDraft:
        matches = tuple(retrieve(question, selected_files))
        draft = self.model.answer(
            QuestionContext(metadata=metadata, question=question, matches=matches)
        )
        allowed_paths = {result.chunk.path for result in matches}
        self._validate_sources(draft.sources, allowed_paths, "answer")
        if matches and not draft.sources:
            raise GroundingValidationError(
                "answer must cite at least one retrieved source"
            )
        return draft

    @classmethod
    def _validate_analysis(cls, draft: AnalysisDraft, allowed_paths: set[str]) -> None:
        cls._validate_sources(draft.overview.sources, allowed_paths, "overview")
        if allowed_paths and not draft.overview.sources:
            raise GroundingValidationError(
                "overview must cite at least one selected source"
            )
        for item in (*draft.entry_points, *draft.key_files):
            cls._validate_sources(item.sources, allowed_paths, item.path)
            if item.path not in allowed_paths:
                raise GroundingValidationError(
                    f"analysis references an unselected file: {item.path}"
                )
        for index, claim in enumerate(draft.architecture):
            cls._validate_sources(
                claim.sources, allowed_paths, f"architecture[{index}]"
            )
            if not claim.sources:
                raise GroundingValidationError(
                    f"architecture[{index}] must cite at least one selected source"
                )

    @staticmethod
    def _validate_sources(
        sources: tuple[str, ...], allowed_paths: set[str], label: str
    ) -> None:
        invalid = sorted(set(sources) - allowed_paths)
        if invalid:
            raise GroundingValidationError(
                f"{label} cites sources outside the supplied context: {', '.join(invalid)}"
            )
