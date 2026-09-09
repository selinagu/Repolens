import unittest

from backend.analyzer import (
    ArchitectureComponent,
    Citation,
    EntryPoint,
    GroundedSummary,
    KeyFile,
    RepositoryAnalysis,
    RepositoryAnswer,
    UNVERIFIED_ANSWER,
    UNVERIFIED_OVERVIEW,
    citation_is_allowed,
    validate_repository_analysis,
    validate_repository_answer,
)
from backend.file_selector import SelectedFile
from backend.retrieval import SourceChunk


def selected(path: str, content: str = "content", score: int = 10) -> SelectedFile:
    return SelectedFile(path, content, len(content), len(content), False, score)


SNIPPETS = [
    SourceChunk(
        chunk_id="backend/main.py:L10-L20:C1",
        path="backend/main.py",
        content="def main(): pass",
        start_line=10,
        end_line=20,
        selector_score=40,
    )
]


class AnalysisGroundingTests(unittest.TestCase):
    def test_filters_analysis_to_selected_paths(self):
        analysis = RepositoryAnalysis(
            overview=GroundedSummary("Grounded overview", ["README.md", "invented.md"]),
            architecture=[
                ArchitectureComponent(
                    "API", "Valid component", ["backend/main.py", "invented.py"]
                ),
                ArchitectureComponent("Ghost", "Invalid", ["invented.py"]),
            ],
            entry_points=[
                EntryPoint("backend/main.py", "valid"),
                EntryPoint("invented.py", "invalid"),
            ],
            key_files=[
                KeyFile("README.md", "valid"),
                KeyFile("invented.md", "invalid"),
            ],
        )

        result = validate_repository_analysis(
            analysis, [selected("README.md"), selected("backend/main.py")]
        )

        self.assertEqual(result.overview.sources, ["README.md"])
        self.assertEqual(len(result.architecture), 1)
        self.assertEqual(result.architecture[0].sources, ["backend/main.py"])
        self.assertEqual(
            [item.path for item in result.entry_points], ["backend/main.py"]
        )
        self.assertEqual([item.path for item in result.key_files], ["README.md"])

    def test_replaces_overview_when_no_valid_source_remains(self):
        analysis = RepositoryAnalysis(
            overview=GroundedSummary("Ungrounded claim", ["invented.py"]),
            architecture=[],
            entry_points=[],
            key_files=[],
        )

        result = validate_repository_analysis(analysis, [selected("README.md")])

        self.assertEqual(result.overview.text, UNVERIFIED_OVERVIEW)
        self.assertEqual(result.overview.sources, [])


class CitationGroundingTests(unittest.TestCase):
    def test_valid_citation_is_retained(self):
        citation = Citation("backend/main.py", 12, 18)
        result = validate_repository_answer(
            RepositoryAnswer("Grounded answer", [citation]), SNIPPETS
        )
        self.assertEqual(result.citations, [citation])

    def test_invalid_citations_are_removed(self):
        invalid = [
            Citation("wrong.py", 12, 18),
            Citation("backend/main.py", 8, 18),
            Citation("backend/main.py", 12, 22),
            Citation("backend/main.py", 8, 22),
            Citation("backend/main.py", 18, 12),
            Citation("backend/main.py", 0, 12),
        ]
        for citation in invalid:
            with self.subTest(citation=citation):
                self.assertFalse(citation_is_allowed(citation, SNIPPETS))

        valid = Citation("backend/main.py", 12, 18)
        result = validate_repository_answer(
            RepositoryAnswer("Grounded answer", [*invalid, valid]), SNIPPETS
        )
        self.assertEqual(result.citations, [valid])

    def test_all_invalid_citations_produce_safe_answer(self):
        result = validate_repository_answer(
            RepositoryAnswer("Unsupported claim", [Citation("wrong.py", 1, 2)]),
            SNIPPETS,
        )
        self.assertEqual(result, RepositoryAnswer(UNVERIFIED_ANSWER, []))

    def test_explicit_insufficient_context_without_citations_is_accepted(self):
        answer = "The available source context is insufficient to answer this question."
        result = validate_repository_answer(RepositoryAnswer(answer, []), SNIPPETS)
        self.assertEqual(result, RepositoryAnswer(answer, []))


if __name__ == "__main__":
    unittest.main()
