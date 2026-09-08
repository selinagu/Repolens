import unittest

from backend.file_selector import SelectedFile
from backend.retrieval import chunk_selected_files, retrieve


def selected(path: str, content: str, score: int = 10) -> SelectedFile:
    return SelectedFile(path, content, len(content), len(content), False, score)


class RetrievalTests(unittest.TestCase):
    def test_lexical_matches_rank_before_selector_fallback(self):
        files = [
            selected("README.md", "general project notes", score=100),
            selected(
                "backend/auth_service.py",
                "def validate_token(token):\n    return token_is_valid(token)",
                score=20,
            ),
        ]

        results = retrieve("Where does code validate token?", files)

        self.assertEqual(results[0].chunk.path, "backend/auth_service.py")
        self.assertEqual(results[0].matched_terms, ("validate", "token"))
        self.assertGreater(results[0].score, results[1].score)

    def test_results_are_stable_when_scores_tie(self):
        files = [
            selected("z.py", "unrelated", score=5),
            selected("a.py", "unrelated", score=5),
        ]

        first = retrieve("missing term", files)
        second = retrieve("missing term", files)

        self.assertEqual(first, second)
        self.assertEqual([item.chunk.path for item in first], ["a.py", "z.py"])

    def test_chunks_are_line_addressable_and_bounded(self):
        chunks = chunk_selected_files(
            [selected("src/main.py", "one\ntwo\nthree\n")], max_chunk_chars=8
        )

        self.assertEqual(
            [(chunk.start_line, chunk.end_line) for chunk in chunks], [(1, 2), (3, 3)]
        )
        self.assertTrue(all(len(chunk.content) <= 8 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
