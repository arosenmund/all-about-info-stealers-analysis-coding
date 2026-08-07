from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hybrid_edge_classifier.stage_01_filesystem_crawl import (
    CRAWL_CONTRACT_VERSION,
    CrawlConfig,
    CrawlContractError,
    CrawlLimits,
    crawl_selected_root,
)


ROOT = Path(__file__).resolve().parents[2]


class FilesystemCrawlTests(unittest.TestCase):
    def test_contract_defaults_match_the_machine_readable_contract(self) -> None:
        contract = json.loads((ROOT / "contracts/crawl-001.json").read_text(encoding="utf-8"))
        limits = CrawlLimits()

        self.assertEqual(contract["crawl_contract_version"], CRAWL_CONTRACT_VERSION)
        self.assertFalse(contract["follow_symlinks"])
        self.assertFalse(contract["emit_paths_or_contents"])
        self.assertIsNone(contract["allowed_suffixes"])
        self.assertEqual(contract["limits"], {
            "max_files": limits.max_files,
            "max_file_bytes": limits.max_file_bytes,
            "max_total_bytes": limits.max_total_bytes,
        })

    def test_collects_all_eligible_utf8_files_including_hidden_and_key_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "nested" / ".cache").mkdir()
            (root / "a.txt").write_text("ALPHA", encoding="utf-8")
            (root / "nested" / "b.json").write_text('{"value":"BETA"}', encoding="utf-8")
            (root / "extensionless").write_text("extensionless", encoding="utf-8")
            (root / "ignored.bin").write_text("plain text", encoding="utf-8")
            (root / ".hidden.txt").write_text("hidden", encoding="utf-8")
            (root / "nested" / ".cache" / "c.txt").write_text("hidden", encoding="utf-8")
            (root / "certificate.key").write_text("key fixture", encoding="utf-8")
            (root / "invalid.txt").write_bytes(b"\xff")

            result = crawl_selected_root(CrawlConfig(root=root))

        self.assertEqual(result.contract_version, "crawl-001")
        self.assertEqual(
            [item.relative_path.as_posix() for item in result.items],
            [
                ".hidden.txt",
                "a.txt",
                "certificate.key",
                "extensionless",
                "ignored.bin",
                "nested/.cache/c.txt",
                "nested/b.json",
            ],
        )
        self.assertEqual(result.summary.files_collected, 7)
        self.assertEqual(result.summary.skipped_count("invalid_utf8"), 1)
        self.assertFalse(result.summary.stopped_by_file_limit)

    def test_caller_may_narrow_suffixes_or_add_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "skip-me").mkdir()
            (root / "a.txt").write_text("included", encoding="utf-8")
            (root / "b.json").write_text("suffix skipped", encoding="utf-8")
            (root / "skip-me" / "c.txt").write_text("excluded", encoding="utf-8")

            result = crawl_selected_root(
                CrawlConfig(
                    root=root,
                    allowed_suffixes=frozenset({".txt"}),
                    additional_excluded_components=frozenset({"skip-me"}),
                )
            )

        self.assertEqual([item.relative_path.as_posix() for item in result.items], ["a.txt"])
        self.assertEqual(result.summary.skipped_count("unsupported_suffix"), 1)
        self.assertEqual(result.summary.skipped_count("excluded"), 1)

    def test_does_not_follow_file_or_directory_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root = temporary_root / "root"
            outside = temporary_root / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "included.txt").write_text("included", encoding="utf-8")
            (outside / "outside.txt").write_text("outside", encoding="utf-8")
            try:
                (root / "linked-file.txt").symlink_to(outside / "outside.txt")
                (root / "linked-directory").symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable in this environment: {error}")

            result = crawl_selected_root(CrawlConfig(root=root))

        self.assertEqual([item.relative_path.as_posix() for item in result.items], ["included.txt"])
        self.assertEqual(result.summary.skipped_count("symlink"), 2)

    def test_enforces_file_and_total_byte_limits_without_retaining_oversized_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a-large.txt").write_text("123456", encoding="utf-8")
            (root / "b-small.txt").write_text("1234", encoding="utf-8")
            (root / "c-small.txt").write_text("5678", encoding="utf-8")
            result = crawl_selected_root(
                CrawlConfig(root=root, limits=CrawlLimits(max_files=10, max_file_bytes=5, max_total_bytes=7))
            )

        self.assertEqual([item.relative_path.as_posix() for item in result.items], ["b-small.txt"])
        self.assertEqual(result.summary.bytes_collected, 4)
        self.assertEqual(result.summary.skipped_count("file_size"), 1)
        self.assertEqual(result.summary.skipped_count("total_budget"), 1)

    def test_stops_deterministically_at_the_file_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.txt").write_text("one", encoding="utf-8")
            (root / "b.txt").write_text("two", encoding="utf-8")
            result = crawl_selected_root(
                CrawlConfig(root=root, limits=CrawlLimits(max_files=1, max_file_bytes=8, max_total_bytes=8))
            )

        self.assertEqual([item.relative_path.as_posix() for item in result.items], ["a.txt"])
        self.assertTrue(result.summary.stopped_by_file_limit)
        self.assertEqual(result.summary.skipped_count("file_limit"), 1)

    def test_rejects_missing_non_directory_or_filesystem_roots_without_echoing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "missing"
            file_path = root / "file.txt"
            file_path.write_text("text", encoding="utf-8")

            for selected in (missing, file_path, Path(Path(temporary).anchor)):
                with self.assertRaises(CrawlContractError) as caught:
                    crawl_selected_root(CrawlConfig(root=selected))
                self.assertEqual(caught.exception.code, "invalid_root")
                self.assertNotIn(str(selected), caught.exception.message)
