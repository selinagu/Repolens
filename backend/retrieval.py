"""Small deterministic lexical retrieval over already-selected repository files."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from backend.file_selector import SelectedFile

DEFAULT_CHUNK_CHARS = 2_000
DEFAULT_RESULT_LIMIT = 6

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "what",
    "where",
    "which",
    "with",
}


@dataclass(frozen=True)
class SourceChunk:
    """A line-addressable piece of a selected file."""

    chunk_id: str
    path: str
    content: str
    start_line: int
    end_line: int
    selector_score: int


@dataclass(frozen=True)
class RetrievalResult:
    chunk: SourceChunk
    score: int
    matched_terms: tuple[str, ...]


def tokenize(value: str) -> tuple[str, ...]:
    """Return normalized lexical terms while preserving code identifiers."""

    terms: list[str] = []
    for match in _TOKEN_PATTERN.finditer(value):
        identifier = match.group(0)
        candidates = [identifier, *_CAMEL_BOUNDARY.sub("_", identifier).split("_")]
        seen_candidates: set[str] = set()
        for candidate in candidates:
            token = candidate.lower()
            if token and token not in _STOP_WORDS and token not in seen_candidates:
                terms.append(token)
                seen_candidates.add(token)
    return tuple(terms)


def chunk_selected_files(
    selected_files: list[SelectedFile], max_chunk_chars: int = DEFAULT_CHUNK_CHARS
) -> list[SourceChunk]:
    if max_chunk_chars <= 0:
        raise ValueError("max_chunk_chars must be positive")

    chunks: list[SourceChunk] = []
    for selected_file in selected_files:
        lines = selected_file.content.splitlines(keepends=True) or [
            selected_file.content
        ]
        start = 0
        current: list[str] = []
        current_chars = 0

        def append_chunk(end: int) -> None:
            content = "".join(current).rstrip()
            if not content:
                return
            start_line = start + 1
            chunks.append(
                SourceChunk(
                    chunk_id=(
                        f"{selected_file.path}:L{start_line}-L{end}:C{len(chunks) + 1}"
                    ),
                    path=selected_file.path,
                    content=content,
                    start_line=start_line,
                    end_line=end,
                    selector_score=selected_file.score,
                )
            )

        for line_index, line in enumerate(lines):
            if current and current_chars + len(line) > max_chunk_chars:
                append_chunk(line_index)
                start = line_index
                current = []
                current_chars = 0

            # A single long line is split so chunk size remains bounded.
            while len(line) > max_chunk_chars:
                if current:
                    append_chunk(line_index)
                    current = []
                    current_chars = 0
                piece, line = line[:max_chunk_chars], line[max_chunk_chars:]
                current = [piece]
                append_chunk(line_index + 1)
                current = []
                start = line_index

            if line:
                current.append(line)
                current_chars += len(line)

        if current:
            append_chunk(len(lines))

    return chunks


def retrieve(
    query: str,
    selected_files: list[SelectedFile],
    limit: int = DEFAULT_RESULT_LIMIT,
    max_chunk_chars: int = DEFAULT_CHUNK_CHARS,
) -> list[RetrievalResult]:
    """Rank source chunks using deterministic path/content term overlap."""

    if limit <= 0:
        return []

    query_terms = tuple(dict.fromkeys(tokenize(query)))
    results: list[RetrievalResult] = []
    for chunk in chunk_selected_files(selected_files, max_chunk_chars=max_chunk_chars):
        path_counts = Counter(tokenize(chunk.path.replace("/", " ")))
        content_counts = Counter(tokenize(chunk.content))
        matched_terms = tuple(
            term for term in query_terms if path_counts[term] or content_counts[term]
        )
        lexical_score = sum(
            min(content_counts[term], 4) + (3 if path_counts[term] else 0)
            for term in matched_terms
        )
        results.append(
            RetrievalResult(
                chunk=chunk,
                score=lexical_score,
                matched_terms=matched_terms,
            )
        )

    results.sort(
        key=lambda result: (
            -result.score,
            -result.chunk.selector_score,
            result.chunk.path,
            result.chunk.start_line,
        )
    )
    return results[:limit]
