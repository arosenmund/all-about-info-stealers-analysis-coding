from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "python/phase_90_scripts/phase_01_generate_corpus_cohorts.py"
SPEC = importlib.util.spec_from_file_location("phase_01_generate_corpus_cohorts", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Phase01CorpusCohortTests(unittest.TestCase):
    def test_write_then_check_creates_the_versioned_balanced_cohorts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label in MODULE.PRIMARY_LABELS:
                (root / label).mkdir()

            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(MODULE.run(["--root", str(root), "--write"], stdout, stderr), 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(
                json.loads(stdout.getvalue()),
                {
                    "candidates": 840,
                    "contract_version": "corpus-cohorts-002",
                    "families": 24,
                    "files": 24,
                    "mode": "write",
                },
            )

            expected = MODULE.expected_documents(root)
            self.assertEqual(len(expected), 24)
            self.assertEqual(sum(len(value.splitlines()) for value in expected.values()), 840)
            self.assertTrue(all(path.read_text(encoding="utf-8") == content for path, content in expected.items()))

            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(MODULE.run(["--root", str(root), "--check"], stdout, stderr), 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(json.loads(stdout.getvalue())["mode"], "check")

    def test_mismatched_document_fails_closed_without_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label in MODULE.PRIMARY_LABELS:
                (root / label).mkdir()
            expected_path = next(iter(MODULE.expected_documents(root)))
            expected_path.parent.mkdir(parents=True)
            expected_path.write_text("different=value\n", encoding="utf-8")

            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(MODULE.run(["--root", str(root), "--write"], stdout, stderr), 1)

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(), "generated cohort document differs from its deterministic contract\n"
        )
        self.assertNotIn("different=value", stderr.getvalue())

    def test_write_safely_migrates_only_verified_experimental_generator_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label in MODULE.PRIMARY_LABELS:
                (root / label).mkdir()
            for path, content in MODULE._legacy_documents(root).items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(MODULE.run(["--root", str(root), "--write"], stdout, stderr), 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(len(MODULE.expected_documents(root)), 24)
            self.assertTrue(all(path.exists() for path in MODULE.expected_documents(root)))
            self.assertFalse(any(path.exists() for path in MODULE._legacy_documents(root) if path.name != "cohort-01.conf"))
