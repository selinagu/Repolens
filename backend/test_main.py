import json
import unittest
from unittest.mock import patch

from backend.file_selector import SelectedFile
from backend.github_client import RepositoryMetadata
from backend.main import (
    AnalyzeRepositoryInput,
    AskRepositoryInput,
    IngestedRepository,
    analyze_repository,
    ask_repository,
)


METADATA = RepositoryMetadata(
    owner="owner",
    repo="repo",
    description="A test repository",
    default_branch="main",
    language="Python",
    stars=3,
    html_url="https://github.com/owner/repo",
)
CONTENT = "def validate_token(token):\n    return bool(token)\n"
INGESTED = IngestedRepository(
    metadata=METADATA,
    selected_files=[
        SelectedFile(
            path="backend/main.py",
            content=CONTENT,
            original_chars=len(CONTENT),
            included_chars=len(CONTENT),
            truncated=False,
            score=48,
        )
    ],
)


class RouteIntegrationTests(unittest.TestCase):
    @patch("backend.main._ingest_repository", return_value=INGESTED)
    def test_analyze_uses_structured_analyzer_without_changing_contract(self, _ingest):
        response = analyze_repository(
            AnalyzeRepositoryInput(repositoryUrl="https://github.com/owner/repo")
        )
        body = json.loads(response.body)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["repositoryName"], "owner/repo")
        self.assertEqual(body["entryPoints"][0]["path"], "backend/main.py")
        self.assertEqual(body["selectedFileCount"], 1)

    @patch("backend.main._ingest_repository", return_value=INGESTED)
    def test_ask_retrieves_from_the_bounded_snapshot(self, _ingest):
        response = ask_repository(
            AskRepositoryInput(
                repositoryUrl="https://github.com/owner/repo",
                question="Where is token validation?",
            )
        )

        self.assertEqual(response["sources"], ["backend/main.py"])
        self.assertIn("token", response["answer"])


if __name__ == "__main__":
    unittest.main()
