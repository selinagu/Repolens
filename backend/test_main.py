import json
import unittest
from unittest.mock import patch

from backend.analyzer import (
    AnalysisModelInvalidResponse,
    AnalysisModelUnavailable,
    ArchitectureComponent,
    Citation,
    EntryPoint,
    GroundedSummary,
    KeyFile,
    RepositoryAnalysis,
    RepositoryAnalyzer,
    RepositoryAnswer,
)
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


class FakeModel:
    def analyze_repository(self, context):
        return RepositoryAnalysis(
            overview=GroundedSummary("Fake overview", ["backend/main.py"]),
            architecture=[
                ArchitectureComponent("API", "Handles requests", ["backend/main.py"])
            ],
            entry_points=[EntryPoint("backend/main.py", "FastAPI entry")],
            key_files=[KeyFile("backend/main.py", "Route module")],
        )

    def answer_question(self, question, snippets):
        snippet = snippets[0]
        return RepositoryAnswer(
            "Token validation is in the main module.",
            [Citation(snippet.path, snippet.start_line, snippet.end_line)],
        )


class FailingModel:
    def __init__(self, error):
        self.error = error

    def analyze_repository(self, context):
        raise self.error

    def answer_question(self, question, snippets):
        raise self.error


class RouteIntegrationTests(unittest.TestCase):
    @patch("backend.main._ingest_repository", return_value=INGESTED)
    @patch("backend.main.ANALYZER", new=RepositoryAnalyzer(FakeModel()))
    def test_analyze_uses_injected_model_without_changing_contract(self, _ingest):
        response = analyze_repository(
            AnalyzeRepositoryInput(repositoryUrl="https://github.com/owner/repo")
        )
        body = json.loads(response.body)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["overview"], "Fake overview")
        self.assertEqual(body["entryPoints"][0]["path"], "backend/main.py")
        self.assertEqual(body["architecture"], ["API: Handles requests"])

    @patch("backend.main._ingest_repository", return_value=INGESTED)
    @patch("backend.main.ANALYZER", new=RepositoryAnalyzer(FakeModel()))
    def test_ask_uses_injected_model_and_formats_line_citations(self, _ingest):
        response = ask_repository(
            AskRepositoryInput(
                repositoryUrl="https://github.com/owner/repo",
                question="Where is token validation?",
            )
        )

        self.assertEqual(response["sources"], ["backend/main.py:L1-L2"])
        self.assertIn("Token validation", response["answer"])

    @patch("backend.main._ingest_repository", return_value=INGESTED)
    def test_unavailable_model_becomes_clean_503(self, _ingest):
        analyzer = RepositoryAnalyzer(
            FailingModel(AnalysisModelUnavailable("provider details"))
        )
        with patch("backend.main.ANALYZER", analyzer):
            response = analyze_repository(
                AnalyzeRepositoryInput(repositoryUrl="https://github.com/owner/repo")
            )

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("provider details", response.body.decode())

    @patch("backend.main._ingest_repository", return_value=INGESTED)
    def test_invalid_model_output_becomes_clean_502(self, _ingest):
        analyzer = RepositoryAnalyzer(
            FailingModel(AnalysisModelInvalidResponse("schema details"))
        )
        with patch("backend.main.ANALYZER", analyzer):
            response = ask_repository(
                AskRepositoryInput(
                    repositoryUrl="https://github.com/owner/repo",
                    question="Where is token validation?",
                )
            )

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("schema details", response.body.decode())


if __name__ == "__main__":
    unittest.main()
