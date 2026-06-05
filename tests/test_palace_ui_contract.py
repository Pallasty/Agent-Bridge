import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PALACE_HTML = ROOT / "crates" / "bridge" / "assets" / "palace.html"


def palace_html():
    return PALACE_HTML.read_text(encoding="utf-8")


class PalaceUiContractTests(unittest.TestCase):
    def test_atlas_observatory_workbench_shells_exist(self):
        html = palace_html()

        self.assertIn('id="atlas-panel"', html)
        self.assertIn('id="breadcrumb"', html)
        self.assertIn('id="view-presets"', html)
        self.assertIn("workbench-shell", html)
        self.assertIn("workbench-toolbar", html)

    def test_view_presets_cover_graph_maintenance_modes(self):
        html = palace_html()
        presets = set(re.findall(r'data-view-preset="([^"]+)"', html))

        self.assertEqual(
            presets,
            {
                "overview",
                "fresh",
                "stale",
                "hubs",
                "orphans",
                "coactivation",
            },
        )

    def test_atlas_region_logic_is_explicit_and_stateful(self):
        html = palace_html()

        self.assertIn("activeRegion: null", html)
        self.assertIn("viewPreset: \"overview\"", html)
        self.assertIn("function computeAtlasRegions(data)", html)
        self.assertIn("function renderAtlasPanel()", html)
        self.assertIn("function selectAtlasRegion(regionId)", html)
        self.assertIn("function clearAtlasRegion()", html)


if __name__ == "__main__":
    unittest.main()
