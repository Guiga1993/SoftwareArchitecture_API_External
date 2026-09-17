"""Maintenance contracts for external integration source documentation."""

import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_DIRECTORIES = frozenset({".git", ".pytest_cache", "__pycache__", "venv"})
PLACEHOLDER_DOCSTRINGS = frozenset({"todo", "fixme", "tbd", "placeholder"})


def iter_python_files():
    """Yield tracked source and test modules while excluding generated trees."""
    for source_file in sorted(PROJECT_ROOT.rglob("*.py")):
        relative_path = source_file.relative_to(PROJECT_ROOT)
        if not EXCLUDED_DIRECTORIES.intersection(relative_path.parts):
            yield source_file


class DocumentationTests(unittest.TestCase):
    """Require responsibility descriptions throughout integration source files."""

    def test_modules_classes_functions_and_methods_have_docstrings(self):
        """Report every undocumented repository module or symbol at once."""
        undocumented = []

        for source_file in iter_python_files():
            module = ast.parse(
                source_file.read_text(encoding="utf-8"),
                filename=str(source_file),
            )
            relative_path = source_file.relative_to(PROJECT_ROOT)
            if not ast.get_docstring(module):
                undocumented.append(str(relative_path))
            for node in ast.walk(module):
                if isinstance(
                    node,
                    (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
                ) and not ast.get_docstring(node):
                    undocumented.append(f"{relative_path}:{node.name}")

        self.assertEqual(undocumented, [])

    def test_docstrings_are_descriptive(self):
        """Reject placeholder or fragmentary documentation across the repository."""
        uninformative = []

        for source_file in iter_python_files():
            module = ast.parse(
                source_file.read_text(encoding="utf-8"),
                filename=str(source_file),
            )
            relative_path = source_file.relative_to(PROJECT_ROOT)
            documented_nodes = [(str(relative_path), module)]
            documented_nodes.extend(
                (f"{relative_path}:{node.name}", node)
                for node in ast.walk(module)
                if isinstance(
                    node,
                    (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
                )
            )

            for location, node in documented_nodes:
                docstring = (ast.get_docstring(node) or "").strip()
                normalized = docstring.lower().rstrip(".")
                if (
                    normalized in PLACEHOLDER_DOCSTRINGS
                    or len(docstring.split()) < 4
                ):
                    uninformative.append(location)

        self.assertEqual(uninformative, [])


if __name__ == "__main__":
    unittest.main()