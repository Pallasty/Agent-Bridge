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

    def test_node_workbench_filters_and_sorts_neighbors(self):
        html = palace_html()

        self.assertIn("neighborFilter: \"all\"", html)
        self.assertIn("neighborSort: \"weight\"", html)
        self.assertIn("function filteredWorkbenchNeighbors(memory, graphNode)", html)
        self.assertIn("function sortWorkbenchNeighbors(rows)", html)
        self.assertIn("function renderWorkbenchNeighborControls()", html)
        self.assertIn('id="neighbor-lens-controls"', html)
        self.assertIn("data-neighbor-filter", html)
        self.assertIn("data-neighbor-sort", html)
        self.assertIn("state.neighborFilter = filter;", html)
        self.assertIn("state.neighborSort = sort;", html)

    def test_node_workbench_summarizes_relation_context(self):
        html = palace_html()

        self.assertIn("function summarizeWorkbenchRelations(memory, graphNode)", html)
        self.assertIn("function renderWorkbenchRelationSummary(memory, graphNode)", html)
        self.assertIn('id="workbench-relation-summary"', html)
        self.assertIn("relation-summary", html)
        self.assertIn("relation-lede", html)
        self.assertIn("relation-chip structural", html)
        self.assertIn("relation-chip coactivation", html)
        self.assertIn("strongest neighbor", html)
        self.assertIn("renderWorkbenchRelationSummary(m, graphNode)", html)

    def test_neighbor_relation_detail_drills_into_edges(self):
        html = palace_html()

        self.assertIn("relationDetailKey: null", html)
        self.assertIn("function renderWorkbenchRelationDetail(memory, graphNode, selectedKey)", html)
        self.assertIn('id="workbench-relation-detail"', html)
        self.assertIn("relation-detail", html)
        self.assertIn("data-relation-detail-key", html)
        self.assertIn("data-open-neighbor-key", html)
        self.assertIn("state.relationDetailKey = key;", html)
        self.assertIn("jumpToWorkbenchNeighbor(key);", html)
        self.assertIn("open node", html)

    def test_node_workbench_content_reader_has_scan_and_full_modes(self):
        html = palace_html()

        self.assertIn("contentReaderMode: \"scan\"", html)
        self.assertIn("function contentReaderStats(content)", html)
        self.assertIn("function contentReaderText(content, mode)", html)
        self.assertIn("function renderWorkbenchContentReader(memory)", html)
        self.assertIn('id="workbench-content-reader"', html)
        self.assertIn("content-reader-controls", html)
        self.assertIn("data-content-reader-mode", html)
        self.assertIn("state.contentReaderMode = mode;", html)
        self.assertIn("renderWorkbenchContentReader(m)", html)

    def test_atlas_regions_surface_health_scores(self):
        html = palace_html()

        self.assertIn("function atlasRegionHealth(region)", html)
        self.assertIn("healthScore", html)
        self.assertIn("healthTier", html)
        self.assertIn("healthReason", html)
        self.assertIn("region-health", html)
        self.assertIn("health-bar", html)
        self.assertIn("region.healthScore", html)

    def test_region_workbench_offers_maintenance_actions(self):
        html = palace_html()

        self.assertIn("function regionMaintenanceActions(region)", html)
        self.assertIn("function renderRegionMaintenanceActions(region)", html)
        self.assertIn('id="region-maintenance-actions"', html)
        self.assertIn("maintenance-action", html)
        self.assertIn("data-maintenance-filter", html)
        self.assertIn("state.regionNodeFilter = filter;", html)
        self.assertIn("showRegionWorkbench(regionId);", html)

    def test_region_workbench_previews_maintenance_candidates_read_only(self):
        html = palace_html()

        self.assertIn("function regionMaintenancePreviewRows(regionId)", html)
        self.assertIn("function renderRegionMaintenancePreview(regionId)", html)
        self.assertIn('id="region-maintenance-preview"', html)
        self.assertIn("maintenance-preview-row", html)
        self.assertIn("data-preview-node-key", html)
        self.assertIn("state.maintenancePreviewFilter = filter;", html)
        self.assertIn("read-only", html)

    def test_search_surfaces_result_navigation(self):
        html = palace_html()

        self.assertIn('id="search-nav"', html)
        self.assertIn("searchCursor: 0", html)
        self.assertIn("function searchResultRows(term)", html)
        self.assertIn("function renderSearchNavigator()", html)
        self.assertIn("function jumpToSearchResult(key)", html)
        self.assertIn("data-search-result-key", html)
        self.assertIn("state.searchCursor = nextCursor;", html)
        self.assertIn("jumpToSearchResult(row.key);", html)

    def test_visual_performance_health_is_observable(self):
        html = palace_html()

        self.assertIn('id="view-health"', html)
        self.assertIn("lastVisualPassMs: 0", html)
        self.assertIn("function graphViewportStats()", html)
        self.assertIn("function renderViewHealth(stats)", html)
        self.assertIn("performance.now()", html)
        self.assertIn("visibleCount", html)
        self.assertIn("matchCount", html)

    def test_graph_layout_spreads_dense_regions_and_reports_overlap(self):
        html = palace_html()

        self.assertIn("function seededGraphPositions(data)", html)
        self.assertIn("function palaceLayoutOptions(data)", html)
        self.assertIn("function relaxNodeOverlaps(cy", html)
        self.assertIn("lastLayoutOverlapCount", html)
        self.assertIn("layoutstop", html)
        self.assertIn("overlap", html)

    def test_zoom_keeps_node_glyphs_screen_sized(self):
        html = palace_html()

        self.assertIn("displaySize", html)
        self.assertIn("displayHaloPad", html)
        self.assertIn("function updateZoomScaledNodeMetrics()", html)
        self.assertIn("function scheduleZoomScaledNodeMetrics()", html)
        self.assertIn('state.cy.on("zoom"', html)
        self.assertIn('"width": "data(displaySize)"', html)
        self.assertIn('"height": "data(displaySize)"', html)

    def test_zoom_declutters_labels_until_the_user_moves_closer(self):
        html = palace_html()

        self.assertIn("const LABEL_SHOW_ANCHOR_ZOOM", html)
        self.assertIn("const LABEL_SHOW_ALL_ZOOM", html)
        self.assertIn("function labelForZoom(node, zoom)", html)
        self.assertIn("displayLabel", html)
        self.assertIn("labelOpacity", html)
        self.assertIn('"label": "data(displayLabel)"', html)
        self.assertIn('"text-opacity": "data(labelOpacity)"', html)
        self.assertIn('"label": "data(label)"', html)


if __name__ == "__main__":
    unittest.main()
