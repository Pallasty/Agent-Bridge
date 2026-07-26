import importlib.util
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fh_l8_public_source_monitor",
    HERE / "fh_l8_public_source_monitor.py",
)
MONITOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MONITOR)


def arxiv_feed(mmd_version=3, dynamic_version=1):
    return f"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>http://arxiv.org/abs/2605.12600v{dynamic_version}</id></entry>
  <entry><id>http://arxiv.org/abs/2505.10513v{mmd_version}</id></entry>
</feed>""".encode()


def native_xml(statement="All study data are included in the main text."):
    return (
        '<article><sec sec-type="data-availability-statement">'
        f"<title>Data Availability Statement</title><p>{statement}</p>"
        "</sec></article>"
    ).encode()


def fetcher(*, arxiv=None, github_count=0, native=None):
    payloads = {
        MONITOR.ARXIV_API: arxiv if arxiv is not None else arxiv_feed(),
        MONITOR.GITHUB_API: json.dumps({"total_count": github_count}).encode(),
        MONITOR.NATIVE_FULL_TEXT: native if native is not None else native_xml(),
    }
    return payloads.__getitem__


class FHExternalSourceMonitorTests(unittest.TestCase):
    def test_unchanged_baseline(self):
        result = MONITOR.evaluate(fetcher())
        self.assertEqual(result["status"], "UNCHANGED")
        self.assertEqual(result["review_reasons"], [])
        self.assertEqual(
            result["observations"]["arxiv_versions"],
            {"2605.12600": 1, "2505.10513": 3},
        )

    def test_new_arxiv_version_requires_review(self):
        result = MONITOR.evaluate(fetcher(arxiv=arxiv_feed(dynamic_version=2)))
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertIn("2605.12600: v1 -> v2", result["review_reasons"][0])

    def test_repository_candidate_requires_review(self):
        result = MONITOR.evaluate(fetcher(github_count=2))
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("2 candidate repositories" in reason for reason in result["review_reasons"]))

    def test_data_statement_change_requires_review(self):
        result = MONITOR.evaluate(fetcher(native=native_xml("Data are deposited elsewhere.")))
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("data-availability" in reason for reason in result["review_reasons"]))

    def test_missing_arxiv_identifier_requires_review(self):
        result = MONITOR.evaluate(
            fetcher(
                arxiv=b"""<feed xmlns="http://www.w3.org/2005/Atom">
                  <entry><id>http://arxiv.org/abs/2505.10513v3</id></entry>
                </feed>"""
            )
        )
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertTrue(any("omitted tracked identifiers" in reason for reason in result["review_reasons"]))

    def test_check_failure_is_not_unchanged(self):
        original_evaluate = MONITOR.evaluate
        try:
            MONITOR.evaluate = lambda: (_ for _ in ()).throw(OSError("temporary DNS failure"))
            result = MONITOR.check()
        finally:
            MONITOR.evaluate = original_evaluate
        self.assertEqual(result["status"], "CHECK_FAILED")
        self.assertEqual(result["failure"]["error_type"], "OSError")
        self.assertNotIn("observations", result)


if __name__ == "__main__":
    unittest.main()
