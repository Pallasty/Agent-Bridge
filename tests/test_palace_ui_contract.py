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

    def test_region_navigation_has_zoom_and_layered_breadcrumbs(self):
        html = palace_html()

        self.assertIn("function zoomToAtlasRegion(regionId)", html)
        self.assertIn("function zoomToVisibleGraph()", html)
        self.assertIn("zoomToAtlasRegion(regionId);", html)
        self.assertIn("zoomToVisibleGraph();", html)
        self.assertIn("data-clear-region", html)
        self.assertIn("data-focus-region", html)
        self.assertIn("Region", html)
        self.assertIn("Node", html)

    def test_view_state_persists_to_url_and_local_storage(self):
        html = palace_html()

        self.assertIn("const PALACE_VIEW_STATE_KEY", html)
        self.assertIn("function saveViewState()", html)
        self.assertIn("function restoreViewStateFromUrlOrStorage()", html)
        self.assertIn("function syncUrlState()", html)
        self.assertIn("localStorage.setItem(PALACE_VIEW_STATE_KEY", html)
        self.assertIn("new URLSearchParams(window.location.search)", html)
        self.assertIn("history.replaceState", html)

    def test_workbench_surfaces_neighbors_and_source_stack(self):
        html = palace_html()

        self.assertIn('id="workbench-neighbors"', html)
        self.assertIn('id="workbench-sources"', html)
        self.assertIn("function renderWorkbenchNeighbors(memory, graphNode)", html)
        self.assertIn("function renderWorkbenchSourceStack(memory, graphData, region)", html)
        self.assertIn("neighbor-link", html)
        self.assertIn("source-stack", html)

    def test_focused_nodes_sync_their_region_context(self):
        html = palace_html()

        self.assertIn("function syncRegionToFocusedNode(id)", html)
        self.assertIn("syncRegionToFocusedNode(id);", html)
        self.assertIn("const graphRegion = node.data(\"region\");", html)
        self.assertIn("state.activeRegion = graphRegion;", html)
        self.assertIn("renderAtlasPanel();", html)

    def test_neighbor_jump_uses_the_full_workbench_focus_flow(self):
        html = palace_html()

        self.assertIn("function jumpToWorkbenchNeighbor(key)", html)
        self.assertIn("jumpToWorkbenchNeighbor(key);", html)
        self.assertIn("focusOnNode(key);", html)
        self.assertIn("showSidePanel(key);", html)
        self.assertIn("saveViewState();", html)

    def test_region_selection_opens_a_workbench_drilldown(self):
        html = palace_html()

        self.assertIn("function showRegionWorkbench(regionId)", html)
        self.assertIn("function renderRegionNodeList(regionId)", html)
        self.assertIn('id="workbench-region-nodes"', html)
        self.assertIn("region-node-link", html)
        self.assertIn("showRegionWorkbench(regionId);", html)
        self.assertIn("jumpToRegionNode(key);", html)
        self.assertIn("focusOnNode(key);", html)
        self.assertIn("showSidePanel(key);", html)
        self.assertIn("saveViewState();", html)

    def test_region_workbench_filters_and_sorts_nodes(self):
        html = palace_html()

        self.assertIn("regionNodeFilter: \"all\"", html)
        self.assertIn("regionNodeSort: \"rank\"", html)
        self.assertIn("function filteredRegionNodesFor(regionId)", html)
        self.assertIn("function sortRegionNodes(nodes)", html)
        self.assertIn("function renderRegionNodeControls()", html)
        self.assertIn('id="region-node-controls"', html)
        self.assertIn("data-region-node-filter", html)
        self.assertIn("data-region-node-sort", html)
        self.assertIn("state.regionNodeFilter = filter;", html)
        self.assertIn("state.regionNodeSort = sort;", html)


if __name__ == "__main__":
    unittest.main()
