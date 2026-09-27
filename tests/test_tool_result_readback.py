"""Boundary checks for offline, hash-bound UTF-8 artifact reading."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Any


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/eval/tool_result_readback.py"


class ToolResultReadbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SCRIPT.is_file(), "readback feature is not implemented")
        spec = importlib.util.spec_from_file_location("tool_result_readback", SCRIPT)
        assert spec is not None and spec.loader is not None
        self.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.api)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "artifact.txt"
        self.data = "start 中文🙂\n".encode() + b"x" * 20000 + "\n尾声".encode()
        self.path.write_bytes(self.data)
        self.digest = hashlib.sha256(self.data).hexdigest()

    def test_load_exact_hash_and_no_writes(self) -> None:
        before = self.path.stat()
        self.assertEqual(self.api.load_artifact(self.path, self.digest), self.data)
        self.assertEqual(self.path.read_bytes(), self.data)
        self.assertEqual(self.path.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_load_missing_or_changed_file(self) -> None:
        with self.assertRaises((ValueError, OSError)):
            self.api.load_artifact(self.path.with_name("missing"), self.digest)
        with self.assertRaisesRegex(ValueError, "SHA256|sha256|hash"):
            self.api.load_artifact(self.path, "0" * 64)
        for digest in ("", "xyz", "g" * 64, "0" * 63):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                self.api.load_artifact(self.path, digest)

    def test_load_rejects_bad_utf8(self) -> None:
        self.path.write_bytes(b"ok\xff")
        with self.assertRaisesRegex(ValueError, "UTF-8|utf-8"):
            self.api.load_artifact(self.path, hashlib.sha256(b"ok\xff").hexdigest())

    def test_load_rejects_symlink_directory_and_fifo(self) -> None:
        link = self.path.with_name("link")
        link.symlink_to(self.path)
        fifo = self.path.with_name("fifo")
        os.mkfifo(fifo)
        for path in (link, self.path.parent, fifo):
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                self.api.load_artifact(path, self.digest)

    def test_load_size_limit(self) -> None:
        data = b"a" * (8 * 1024 * 1024)
        self.path.write_bytes(data)
        self.assertEqual(self.api.load_artifact(self.path, hashlib.sha256(data).hexdigest()), data)
        self.path.write_bytes(data + b"a")
        with self.assertRaises(ValueError):
            self.api.load_artifact(self.path, hashlib.sha256(data + b"a").hexdigest())

    def test_pages_roundtrip_multibyte_and_long_line(self) -> None:
        for budget in (4, 5, 7, 1024, 16000):
            offset = 0
            chunks = []
            while True:
                page = self.api.read_page(self.data, offset, budget)
                raw = page["text"].encode("utf-8")
                self.assertLessEqual(len(raw), budget)
                self.assertEqual(page["start"], offset)
                self.assertEqual(page["total_bytes"], len(self.data))
                self.assertEqual(raw, self.data[offset:offset + len(raw)])
                chunks.append(raw)
                if page["next_start"] is None:
                    self.assertFalse(page["truncated"])
                    break
                self.assertTrue(page["truncated"])
                self.assertGreater(page["next_start"], offset)
                self.assertEqual(page["next_start"], offset + len(raw))
                offset = page["next_start"]
            self.assertEqual(b"".join(chunks), self.data)

    def test_empty_and_eof_pages(self) -> None:
        for data, start in ((b"", 0), (self.data, len(self.data))):
            page = self.api.read_page(data, start, 4)
            self.assertEqual(page["text"], "")
            self.assertIsNone(page["next_start"])
            self.assertFalse(page["truncated"])

    def test_preview_matches_first_page(self) -> None:
        self.assertEqual(self.api.preview(self.data), self.api.read_page(self.data, 0, 1024))

    def test_page_rejects_invalid_offsets_budgets_and_encoding(self) -> None:
        data = "中🙂".encode()
        for start in (-1, 1, 2, 4, 5, 6, 8, True, 0.5):
            with self.subTest(start=start), self.assertRaises(ValueError):
                self.api.read_page(data, start)
        for budget in (0, 3, 16001, True, 4.5):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                self.api.read_page(data, 0, budget)
        with self.assertRaises(ValueError):
            self.api.read_page(b"\xff")

    def test_search_is_literal_and_offsets_are_bytes(self) -> None:
        data = "中.*中🙂.*".encode()
        result = self.api.search(data, ".*")
        self.assertEqual(result["matches"], [
            {"start": 3, "end": 5, "text": ".*"},
            {"start": 12, "end": 14, "text": ".*"},
        ])
        self.assertTrue(result["search_complete"])
        self.assertIsNone(result["next_start"])

    def test_search_paging_preserves_first_and_last_match(self) -> None:
        data = "🙂🙂🙂 x 🙂".encode()
        offset = 0
        matches = []
        while True:
            result = self.api.search(data, "🙂", offset, budget=4, max_matches=2)
            self.assertLessEqual(sum(len(m["text"].encode()) for m in result["matches"]), 4)
            matches.extend(result["matches"])
            if result["search_complete"]:
                self.assertIsNone(result["next_start"])
                break
            self.assertGreater(result["next_start"], offset)
            offset = result["next_start"]
        self.assertEqual([match["start"] for match in matches], [0, 4, 8, 15])

    def test_search_count_limit_and_non_overlapping_matches(self) -> None:
        result = self.api.search(b"aaaaa", "aa", budget=16, max_matches=1)
        self.assertEqual(result["matches"], [{"start": 0, "end": 2, "text": "aa"}])
        self.assertEqual(result["next_start"], 2)
        result = self.api.search(b"aaaaa", "aa", start=2, budget=16)
        self.assertEqual([m["start"] for m in result["matches"]], [2])

    def test_search_no_match_and_empty_artifact(self) -> None:
        for data in (b"", self.data):
            result = self.api.search(data, "absent")
            self.assertEqual(result["matches"], [])
            self.assertTrue(result["search_complete"])
            self.assertIsNone(result["next_start"])

    def test_search_rejects_invalid_parameters(self) -> None:
        cases: list[dict[str, Any]] = [
            {"query": ""}, {"query": "中" * 86}, {"query": "abcde", "budget": 4},
            {"query": "a", "max_matches": 0}, {"query": "a", "max_matches": 101},
            {"query": "a", "max_matches": True}, {"query": "a", "start": 1},
            {"query": "a", "budget": 16001},
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.api.search("中文".encode(), **kwargs)

    def test_cli_json_success_and_errors(self) -> None:
        base = [sys.executable, str(SCRIPT), "--file", str(self.path), "--sha256", self.digest]
        success = subprocess.run(base + ["read", "--start", "0", "--budget", "16"], capture_output=True, text=True, check=False)
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertEqual(json.loads(success.stdout)["text"].encode(), self.data[:16])
        for args in (["read", "--start", "7"], ["search", "--query", ""], ["read", "--budget", "bad"]):
            failure = subprocess.run(base + args, capture_output=True, text=True, check=False)
            self.assertEqual(failure.returncode, 2)
            self.assertIn("error", json.loads(failure.stdout))
        self.path.unlink()
        failure = subprocess.run(base + ["preview"], capture_output=True, text=True, check=False)
        self.assertEqual(failure.returncode, 2)
        self.assertIn("error", json.loads(failure.stdout))


if __name__ == "__main__":
    unittest.main()
