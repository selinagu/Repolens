"""Small GitHub API client used by the RepoLens ingestion pipeline."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

GITHUB_API_ROOT = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "RepoLens/0.1"

_OWNER_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class GitHubClientError(Exception):
    """A clean, user-facing error from GitHub or the GitHub API."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class RepositoryRef:
    owner: str
    repo: str


@dataclass(frozen=True)
class RepositoryMetadata:
    owner: str
    repo: str
    description: str
    default_branch: str
    language: str
    stars: int
    html_url: str


def parse_repository_url(repository_url: str) -> RepositoryRef:
    """Parse only https://github.com/{owner}/{repo} URLs."""

    try:
        parsed = urlparse(repository_url.strip())
    except ValueError as error:
        raise GitHubClientError(
            "Enter a public GitHub URL like https://github.com/owner/repository."
        ) from error

    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise GitHubClientError(
            "Only public https://github.com/owner/repository URLs are supported."
        )

    if parsed.query or parsed.fragment:
        raise GitHubClientError(
            "Use a repository URL without query parameters or fragments."
        )

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) != 2:
        raise GitHubClientError(
            "Enter a public GitHub URL like https://github.com/owner/repository."
        )

    owner, repo = path_parts
    if (
        not _OWNER_PATTERN.fullmatch(owner)
        or not _REPOSITORY_PATTERN.fullmatch(repo)
        or owner in {".", ".."}
        or repo in {".", ".."}
    ):
        raise GitHubClientError(
            "The GitHub owner or repository name is not valid."
        )

    return RepositoryRef(owner=owner, repo=repo)


class GitHubClient:
    """Fetch only the GitHub resources needed for bounded repository ingestion."""

    def __init__(self, api_root: str = GITHUB_API_ROOT):
        self.api_root = api_root.rstrip("/")

    def get_repository_metadata(self, repository: RepositoryRef) -> RepositoryMetadata:
        payload = self._get_json(
            f"/repos/{quote(repository.owner)}/{quote(repository.repo)}"
        )
        if payload.get("private") is True:
            raise GitHubClientError("This repository is private or inaccessible.")

        default_branch = payload.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            raise GitHubClientError(
                "GitHub did not return a default branch for this repository."
            )

        return RepositoryMetadata(
            owner=repository.owner,
            repo=repository.repo,
            description=payload.get("description") or "",
            default_branch=default_branch,
            language=payload.get("language") or "Unknown",
            stars=int(payload.get("stargazers_count") or 0),
            html_url=payload.get(
                "html_url",
                f"https://github.com/{repository.owner}/{repository.repo}",
            ),
        )

    def get_recursive_tree(
        self, repository: RepositoryRef, default_branch: str
    ) -> list[dict[str, Any]]:
        path = (
            f"/repos/{quote(repository.owner)}/{quote(repository.repo)}"
            f"/git/trees/{quote(default_branch, safe='')}?"
            f"{urlencode({'recursive': '1'})}"
        )
        payload = self._get_json(path)
        if payload.get("truncated") is True:
            raise GitHubClientError(
                "GitHub returned a truncated repository tree. Try a smaller repository."
            )

        tree = payload.get("tree")
        if not isinstance(tree, list):
            raise GitHubClientError("GitHub returned an invalid repository tree.")
        return [item for item in tree if isinstance(item, dict)]

    def fetch_file(
        self, repository: RepositoryRef, default_branch: str, path: str
    ) -> str:
        endpoint = (
            f"/repos/{quote(repository.owner)}/{quote(repository.repo)}/contents/"
            f"{quote(path, safe='/')}?"
            f"{urlencode({'ref': default_branch})}"
        )
        payload = self._get_json(endpoint)
        if payload.get("type") != "file" or payload.get("encoding") != "base64":
            raise GitHubClientError(f"{path} is not a text file.")

        encoded_content = payload.get("content")
        if not isinstance(encoded_content, str):
            raise GitHubClientError(f"GitHub did not return content for {path}.")

        try:
            raw_content = base64.b64decode(
                encoded_content.replace("\n", ""), validate=True
            )
            return raw_content.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as error:
            raise GitHubClientError(f"{path} is not UTF-8 text.") from error

    def _get_json(self, path: str) -> dict[str, Any]:
        request = Request(
            f"{self.api_root}{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT,
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            self._raise_http_error(error)
        except (URLError, TimeoutError) as error:
            raise GitHubClientError(
                "GitHub could not be reached right now. Try again in a moment."
            ) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GitHubClientError("GitHub returned an invalid response.") from error

        if not isinstance(payload, dict):
            raise GitHubClientError("GitHub returned an invalid response.")
        return payload

    @staticmethod
    def _raise_http_error(error: HTTPError) -> None:
        if error.code == 404:
            raise GitHubClientError(
                "Repository not found. Check the owner, repository name, and visibility.",
                error.code,
            ) from error
        if error.code in {401, 403}:
            remaining = error.headers.get("X-RateLimit-Remaining")
            if remaining == "0":
                message = "GitHub API rate limit reached. Try again later."
            else:
                message = "This repository is private or inaccessible."
            raise GitHubClientError(message, error.code) from error
        if 500 <= error.code < 600:
            raise GitHubClientError(
                "GitHub is temporarily unavailable. Try again in a moment.",
                error.code,
            ) from error
        raise GitHubClientError(
            f"GitHub rejected the request ({error.code}).",
            error.code,
        ) from error