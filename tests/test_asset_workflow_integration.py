"""Opt-in real Godot/Rust inspector tests; no model, network, or installed AB use."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


def indexed_cube() -> bytes:
    """Build an original indexed cube with a translated parent and child node."""
    positions = [
        (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5),
        (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5),
        (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5),
    ]
    indices = [
        0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7,
        0, 1, 5, 0, 5, 4, 3, 7, 6, 3, 6, 2,
        0, 4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5,
    ]
    binary = b"".join(struct.pack("<3f", *p) for p in positions)
    binary += struct.pack("<36H", *indices)
    document = {
        "asset": {"version": "2.0", "generator": "AB original integration fixture"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 96, "target": 34962},
            {"buffer": 0, "byteOffset": 96, "byteLength": 72, "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3",
             "min": [-0.5, -0.5, -0.5], "max": [0.5, 0.5, 0.5]},
            {"bufferView": 1, "componentType": 5123, "count": 36, "type": "SCALAR"},
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "nodes": [{"children": [1], "translation": [4, 2, -3]},
                  {"mesh": 0, "translation": [0.25, 0.5, 0]}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    encoded = json.dumps(document, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 28 + len(encoded) + len(binary))
            + struct.pack("<I4s", len(encoded), b"JSON") + encoded
            + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


@unittest.skipUnless(
    os.environ.get("AB_ASSET_GODOT") and os.environ.get("AB_ASSET_INSPECTOR"),
    "set AB_ASSET_GODOT and AB_ASSET_INSPECTOR for real rendering",
)
class AssetWorkflowIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        parent = os.environ.get("AB_ASSET_TEST_OUTPUT_ROOT")
        cls.root = Path(tempfile.mkdtemp(prefix="integration-", dir=parent))
        print(f"Real asset workflow artifacts: {cls.root}", flush=True)
        cls.source = cls.root / "indexed_cube.glb"
        cls.source.write_bytes(indexed_cube())

    def render(self, source: Path, name: str) -> tuple[subprocess.CompletedProcess[str], Path]:
        """Run the actual recipe and preserve the command and complete result."""
        output = self.root / name
        command = [
            sys.executable, "-B", str(REPO / "scripts/asset_workflow/render_glb.py"),
            "--input", str(source), "--output-dir", str(output),
            "--godot", os.environ["AB_ASSET_GODOT"],
            "--inspector", os.environ["AB_ASSET_INSPECTOR"], "--timeout-seconds", "30",
        ]
        for variable, flag in [
            ("AB_ASSET_XVFB", "--xvfb"),
            ("AB_ASSET_XVFB_LIBRARY_DIR", "--xvfb-library-dir"),
        ]:
            if os.environ.get(variable):
                command.extend([flag, os.environ[variable]])
        result = subprocess.run(command, capture_output=True, text=True, timeout=40)
        (self.root / f"{name}-invocation.json").write_text(json.dumps({
            "argv": command, "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
        }, indent=2) + "\n")
        return result, output

    def test_real_render_is_repeatable_and_pending_visual_review(self) -> None:
        hashes = []
        for name in ("first", "repeat"):
            result, output = self.render(self.source, name)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["status"], "rendered_pending_review")
            self.assertIs(report["visual_quality_reviewed"], False)
            rendering = json.loads((output / "rendering.json").read_text())
            self.assertEqual(rendering["mesh_count"], 1)
            self.assertEqual(rendering["material_policy"], "neutral_geometry")
            self.assertEqual(rendering["source_bounds"]["position"], [3.75, 2.0, -3.5])
            self.assertEqual(rendering["source_bounds"]["size"], [1.0, 1.0, 1.0])
            self.assertNotIn("dummy", rendering["renderer"].lower())
            png = output / "preview.png"
            digest = hashlib.sha256(png.read_bytes()).hexdigest()
            inspection = subprocess.run(
                [os.environ["AB_ASSET_INSPECTOR"], str(png), digest],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(inspection.returncode, 0, inspection.stderr)
            facts = json.loads(inspection.stdout)
            self.assertEqual((facts["details"]["width"], facts["details"]["height"]), (512, 512))
            self.assertGreater(facts["details"]["fully_transparent_pixels"], 0)
            self.assertGreater(facts["details"]["opaque_pixels"], 0)
            self.assertTrue((output / "preview.html").is_file())
            hashes.append(digest)
        self.assertEqual(hashes[0], hashes[1], "repeatability is scoped to this toolchain")

    def test_real_inspector_rejects_corrupt_glb_before_render(self) -> None:
        source = self.root / "corrupt.glb"
        source.write_bytes(b"glTF invalid and truncated")
        result, output = self.render(source, "rejected")
        self.assertNotEqual(result.returncode, 0)
        report = json.loads((output / "report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertFalse((output / "preview.png").exists())
        self.assertFalse((output / "rendering.json").exists())


if __name__ == "__main__":
    unittest.main()
