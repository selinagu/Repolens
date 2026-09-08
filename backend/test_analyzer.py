import unittest

from backend.analyzer import (
    AnalysisContext,
    AnalysisDraft,
    AnswerDraft,
    GroundedText,
    GroundingValidationError,
    QuestionContext,
    RepositoryAnalyzer,
)
from backend.file_selector import SelectedFile
from backend.github_client import RepositoryMetadata


METADATA = RepositoryMetadata(
    owner="owner",
    repo="repo",
    description="A test repository",
    default_branch="main",
    language="Python",
    stars=3,
    html_url="https://github.com/owner/repo",
)


def selected(path: str, content: str, score: int = 10) -> SelectedFile:
    return SelectedFile(path, content, len(content), len(content), False, score)


class UngroundedModel:
    def analyze(self, context: AnalysisContext) -> AnalysisDraft:
        return AnalysisDraft(
            overview=GroundedText("Unsupported", ("invented.py",)),
            entry_points=(),
            key_files=(),
            architecture=(),
        )

    def answer(self, context: QuestionContext) -> AnswerDraft:
        return AnswerDraft("Unsupported", ("invented.py",))


class AnalyzerTests(unittest.TestCase):
    def test_default_analysis_only_references_selected_files(self):
        files = [
            selected("README.md", "Project documentation", score=50),
            selected("backend/main.py", "def main(): pass", score=45),
        ]

        result = RepositoryAnalyzer().analyze(METADATA, files)

        allowed = {file.path for file in files}
        cited = set(result.overview.sources)
        cited.update(source for item in result.architecture for source in item.sources)
        cited.update(source for item in result.key_files for source in item.sources)
        self.assertTrue(cited)
        self.assertLessEqual(cited, allowed)

    def test_question_sources_are_limited_to_retrieved_files(self):
        files = [
            selected("README.md", "Project documentation", score=50),
            selected("backend/auth.py", "def validate_token(): pass", score=20),
        ]

        result = RepositoryAnalyzer().answer(METADATA, files, "validate token")

        self.assertEqual(result.sources[0], "backend/auth.py")
        self.assertNotIn("invented.py", result.sources)

    def test_invalid_model_citations_are_rejected(self):
        analyzer = RepositoryAnalyzer(model=UngroundedModel())
        files = [selected("backend/main.py", "def main(): pass")]

        with self.assertRaises(GroundingValidationError):
            analyzer.analyze(METADATA, files)
        with self.assertRaises(GroundingValidationError):
            analyzer.answer(METADATA, files, "main")


if __name__ == "__main__":
    unittest.main()
