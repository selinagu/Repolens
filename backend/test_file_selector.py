import unittest

from backend.file_selector import (
    MAX_CANDIDATE_FILES,
    MAX_FILE_CHARS,
    MAX_SELECTED_FILES,
    MAX_TOTAL_CHARS,
    is_test_path,
    rank_repository_files,
    score_file,
    select_file_contents,
)


class FileSelectorTests(unittest.TestCase):
    def test_test_path_classifier_handles_directories_and_filename_patterns(self):
        test_paths = (
            "tests/testserver/server.py",
            "src/widget_test.py",
            "src/widget.test.ts",
            "src/widget.spec.tsx",
            "src/widget.test.js",
            "src/widget.spec.js",
        )
        for path in test_paths:
            with self.subTest(path=path):
                self.assertTrue(is_test_path(path))

        self.assertFalse(is_test_path("src/requests/server.py"))
        self.assertFalse(is_test_path("src/requests/api.py"))

    def test_test_files_do_not_receive_production_bonuses(self):
        self.assertEqual(score_file("tests/testserver/server.py"), -8)
        self.assertEqual(score_file("src/requests/server.py"), 59)
        self.assertEqual(score_file("src/requests/api.py"), 29)

    def test_metadata_and_package_interface_signals(self):
        self.assertEqual(score_file("pyproject.toml"), 22)
        self.assertEqual(score_file("src/requests/__init__.py"), 27)

    def test_selection_budgets_remain_unchanged(self):
        self.assertEqual(MAX_CANDIDATE_FILES, 50)
        self.assertEqual(MAX_SELECTED_FILES, 25)
        self.assertEqual(MAX_FILE_CHARS, 10_000)
        self.assertEqual(MAX_TOTAL_CHARS, 100_000)

        ranked = rank_repository_files(
            [
                {"path": "README.md", "type": "blob"},
                {"path": "src/main.py", "type": "blob"},
            ]
        )
        selected = select_file_contents(
            [
                (ranked[0], "a" * 12_000),
                (ranked[1], "b" * 12_000),
            ]
        )
        self.assertLessEqual(len(selected), MAX_SELECTED_FILES)
        self.assertLessEqual(sum(item.included_chars for item in selected), MAX_TOTAL_CHARS)
        self.assertLessEqual(
            max(item.included_chars for item in selected),
            MAX_FILE_CHARS,
        )


if __name__ == "__main__":
    unittest.main()