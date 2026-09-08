"""Deterministic, bounded selection of high-signal repository files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

MAX_SELECTED_FILES = 25
MAX_FILE_CHARS = 10_000
MAX_TOTAL_CHARS = 100_000
MAX_CANDIDATE_FILES = 50

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".cpp",
    ".cc",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".rs",
}

DOCUMENT_EXTENSIONS = {
    ".md",
}

SOURCE_EXTENSIONS = CODE_EXTENSIONS | DOCUMENT_EXTENSIONS

SPECIAL_FILES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "makefile",
    "dockerfile",
}

IGNORED_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".next",
    "coverage",
    "__pycache__",
    "venv",
    ".venv",
    "vendor",
    "target",
    ".idea",
    ".vscode",
}

ENTRYPOINT_NAMES = {
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

IMPORTANT_PREFIXES = (
    "model",
    "train",
    "config",
    "server",
    "client",
    "router",
    "api",
    "database",
    "storage",
    "index",
    "parser",
    "tokenizer",
    "route",
    "service",
    "controller",
    "session",
    "adapter",
)

CORE_DIRS = {
    "src",
    "app",
    "lib",
    "backend",
    "server",
    "core",
    "pkg",
    "cmd",
}

TEST_DIR_NAMES = {
    "test",
    "tests",
    "__tests__",
    "spec",
    "specs",
}

PACKAGE_INTERFACE_NAMES = {
    "__init__.py",
    "__main__.py",
}


@dataclass(frozen=True)
class RankedFile:
    path: str
    score: int


@dataclass(frozen=True)
class SelectedFile:
    path: str
    content: str
    original_chars: int
    included_chars: int
    truncated: bool
    score: int


def _path_parts(path: str) -> list[str]:
    return [part for part in PurePosixPath(path).parts if part not in {"", "."}]


def _has_ignored_directory(path: str) -> bool:
    return any(part.lower() in IGNORED_DIRS for part in _path_parts(path)[:-1])


def is_test_path(path: str) -> bool:
    parts = _path_parts(path)
    if not parts:
        return False

    filename = parts[-1].lower()
    return (
        any(part.lower() in TEST_DIR_NAMES for part in parts[:-1])
        or (filename.startswith("test_") and filename.endswith(".py"))
        or filename.endswith("_test.py")
        or filename.endswith(
            (
                ".test.ts",
                ".test.tsx",
                ".spec.ts",
                ".spec.tsx",
                ".test.js",
                ".spec.js",
            )
        )
    )


def is_eligible_file(path: str, item_type: str = "blob") -> bool:
    if item_type != "blob" or not path or _has_ignored_directory(path):
        return False

    filename = _path_parts(path)[-1]
    lowered_filename = filename.lower()
    extension = PurePosixPath(lowered_filename).suffix
    return extension in SOURCE_EXTENSIONS or lowered_filename in SPECIAL_FILES


def score_file(path: str) -> int:
    """Score an eligible path using the repository file-selection policy."""

    parts = _path_parts(path)
    filename = parts[-1]
    lowered_path = path.lower()
    lowered_filename = filename.lower()
    stem = PurePosixPath(lowered_filename).stem
    depth = max(len(parts) - 1, 0)
    score = 0

    if lowered_filename == "readme.md":
        score += 40
        if depth == 0:
            score += 10

    if lowered_filename in SPECIAL_FILES:
        score += 12

    test_path = is_test_path(path)
    if not test_path:
        if lowered_filename in ENTRYPOINT_NAMES:
            score += 30

        if stem.startswith(IMPORTANT_PREFIXES):
            score += 14

    if lowered_filename in PACKAGE_INTERFACE_NAMES:
        score += 12

    if any(part.lower() in CORE_DIRS for part in parts[:-1]):
        score += 8

    if depth == 0:
        score += 10
    elif depth == 1:
        score += 6
    elif depth == 2:
        score += 3

    if PurePosixPath(lowered_filename).suffix in CODE_EXTENSIONS:
        score += 4

    if test_path:
        score -= 15

    if "generated" in lowered_path:
        score -= 15
    if ".min.js" in lowered_path:
        score -= 25

    return score


def rank_repository_files(tree: list[dict[str, object]]) -> list[RankedFile]:
    ranked = [
        RankedFile(path=str(item["path"]), score=score_file(str(item["path"])))
        for item in tree
        if isinstance(item.get("path"), str)
        and is_eligible_file(str(item["path"]), str(item.get("type", "")))
    ]
    return sorted(
        ranked,
        key=lambda item: (
            -item.score,
            len(_path_parts(item.path)) - 1,
            item.path,
        ),
    )[:MAX_CANDIDATE_FILES]


def select_file_contents(
    fetched_files: list[tuple[RankedFile, str]],
    max_files: int = MAX_SELECTED_FILES,
    max_file_chars: int = MAX_FILE_CHARS,
    max_total_chars: int = MAX_TOTAL_CHARS,
) -> list[SelectedFile]:
    selected: list[SelectedFile] = []
    total_chars = 0

    for ranked_file, content in fetched_files:
        if len(selected) >= max_files or total_chars >= max_total_chars:
            break
        if not content.strip():
            continue

        original_chars = len(content)
        remaining_chars = max_total_chars - total_chars
        included_chars = min(original_chars, max_file_chars, remaining_chars)
        if included_chars <= 0:
            break

        selected_content = content[:included_chars]
        selected.append(
            SelectedFile(
                path=ranked_file.path,
                content=selected_content,
                original_chars=original_chars,
                included_chars=included_chars,
                truncated=included_chars < original_chars,
                score=ranked_file.score,
            )
        )
        total_chars += included_chars

    return selected