import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/vision_grounding_ocr.py"


def run_grounding(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=False,
    )


class VisionGroundingOcrTests(unittest.TestCase):
    def test_engine_none_returns_structured_unavailable_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = pathlib.Path(tmp) / "screen.png"
            image.write_bytes(b"not really a png")

            proc = run_grounding(
                "--image",
                str(image),
                "--engine",
                "none",
                "--snapshot-id",
                "snap-1",
                "--snapshot-hash",
                "sha256:snapshot",
                "--window-id",
                "7",
                "--pid",
                "9209",
                "--app-id",
                "cursor",
                "--title-hash",
                "sha256:title",
                "--window-rect",
                "10,20,300,200",
                "--compact",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["schema"], "vision_grounding_result.v0")
            self.assertEqual(data["status"], "error")
            self.assertEqual(data["candidates"], [])
            self.assertEqual(data["source"]["engine"], "none")
            self.assertEqual(data["errors"][0]["code"], "engine_unavailable")
            self.assertEqual(data["request"]["target_window"]["window_id"], 7)

    def test_tesseract_tsv_fixture_maps_words_to_candidates_with_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            image = base / "window.png"
            image.write_bytes(b"fake image bytes")
            tsv = base / "ocr.tsv"
            tsv.write_text(
                "\t".join(
                    [
                        "level",
                        "page_num",
                        "block_num",
                        "par_num",
                        "line_num",
                        "word_num",
                        "left",
                        "top",
                        "width",
                        "height",
                        "conf",
                        "text",
                    ]
                )
                + "\n"
                + "5\t1\t1\t1\t1\t1\t12\t8\t40\t14\t92\tSave\n"
                + "5\t1\t1\t1\t1\t2\t70\t8\t60\t14\t55\tCancel\n"
                + "5\t1\t1\t1\t1\t3\t70\t8\t60\t14\t-1\tNoise\n",
                encoding="utf-8",
            )

            proc = run_grounding(
                "--image",
                str(image),
                "--engine",
                "fixture-tsv",
                "--fixture-tsv",
                str(tsv),
                "--snapshot-id",
                "snap-2",
                "--snapshot-hash",
                "sha256:snapshot2",
                "--image-hash",
                "sha256:image2",
                "--window-id",
                "42",
                "--pid",
                "1234",
                "--app-id",
                "demo",
                "--title-hash",
                "sha256:title2",
                "--window-rect",
                "100,200,640,480",
                "--crop-rect",
                "100,200,640,480",
                "--coordinate-space",
                "window",
                "--hint-text",
                "Save",
                "--hint-role",
                "button",
                "--compact",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["source"]["engine"], "fixture-tsv")
            self.assertEqual(data["source"]["image_hash"], "sha256:image2")
            self.assertEqual(len(data["candidates"]), 2)

            first = data["candidates"][0]
            self.assertEqual(first["candidate_id"], "vg-001")
            self.assertEqual(first["window_ref"]["window_id"], 42)
            self.assertEqual(first["bbox"], {"x": 12, "y": 8, "width": 40, "height": 14})
            self.assertEqual(first["center"], {"x": 32, "y": 15})
            self.assertEqual(first["label"], "Save")
            self.assertEqual(first["label_hash"][:7], "sha256:")
            self.assertEqual(first["role_guess"], "button")
            self.assertAlmostEqual(first["confidence"], 0.92)
            self.assertTrue(first["evidence"]["matched_hint"])
            self.assertEqual(first["coordinate_space"], "window")


if __name__ == "__main__":
    unittest.main()
