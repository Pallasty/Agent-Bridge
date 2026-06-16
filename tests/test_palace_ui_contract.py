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

    def test_depth_rail_exposes_three_level_navigation(self):
        html = palace_html()

        self.assertIn('id="depth-rail"', html)
        self.assertIn("function renderDepthRail()", html)
        self.assertIn("function depthRailStepState(step)", html)
        self.assertIn("function handleDepthRailClick(step)", html)
        self.assertIn('data-depth-step="atlas"', html)
        self.assertIn('data-depth-step="region"', html)
        self.assertIn('data-depth-step="node"', html)
        self.assertIn("Atlas", html)
        self.assertIn("Region", html)
        self.assertIn("Node", html)
        self.assertIn("renderDepthRail();", html)
        self.assertIn("handleDepthRailClick(step);", html)
        self.assertIn("state.focused ? \"active\"", html)
        self.assertIn("state.activeRegion ? \"available\"", html)

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

    def test_atlas_overview_declutters_to_district_anchors(self):
        html = palace_html()

        self.assertIn("function isAtlasDistrictOverview()", html)
        self.assertIn("function computeAtlasDistrictAnchors(data, degInfo)", html)
        self.assertIn("function panAtlasOverviewAwayFromPanels()", html)
        self.assertIn("atlasDistrictAnchor", html)
        self.assertIn("districtLabel", html)
        self.assertIn("node.atlas-district-anchor", html)
        self.assertIn("node.atlas-detail-muted", html)
        self.assertIn("edge.atlas-detail-muted", html)
        self.assertIn("atlas-district-overview", html)
        self.assertIn("const districtRegionIds = new Set((state.atlasRegions || []).map(r => r.id));", html)
        self.assertIn("if (districtRegionIds.size && !districtRegionIds.has(region)) continue;", html)
        self.assertIn("districtLabelSize", html)
        self.assertIn("districtLabelOutlineWidth", html)
        self.assertIn("districtLabelMaxWidth", html)
        self.assertIn('"display": "none"', html)
        self.assertIn('"font-size": "data(districtLabelSize)"', html)
        self.assertIn('"text-max-width": "data(districtLabelMaxWidth)"', html)
        self.assertIn('"text-outline-width": "data(districtLabelOutlineWidth)"', html)
        self.assertIn("if (atlasOverview) window.setTimeout(panAtlasOverviewAwayFromPanels, 390);", html)
        self.assertIn('n.addClass("atlas-district-anchor")', html)
        self.assertIn('n.addClass("atlas-detail-muted")', html)
        self.assertIn('e.addClass("atlas-detail-muted")', html)
        self.assertIn('if (isAtlasDistrictOverview() && evt.target.data("atlasDistrictAnchor"))', html)
        self.assertIn('selectAtlasRegion(evt.target.data("region"));', html)

    def test_region_drilldown_restores_node_detail_from_atlas_overview(self):
        html = palace_html()

        self.assertIn('state.viewPreset === "overview"', html)
        self.assertIn("!state.activeRegion", html)
        self.assertIn("!state.focused", html)
        self.assertIn('state.search.trim() === ""', html)
        self.assertIn("updateZoomScaledNodeMetrics();", html)
        self.assertIn('cy.elements().removeClass("faded match focus-center focus-neighbor focus-edge atlas-detail-muted atlas-district-anchor")', html)
        self.assertIn('const visible = state.cy.nodes().filter(n => !n.hasClass("faded") && !n.hasClass("atlas-detail-muted"));', html)
        self.assertIn('!n.hasClass("faded") && !n.hasClass("atlas-detail-muted")', html)
        self.assertIn('!e.hasClass("faded") && !e.hasClass("atlas-detail-muted")', html)
        self.assertIn("labelForZoom(node, zoom)", html)
        self.assertIn("return node.data(\"districtLabel\") || node.data(\"label\") || node.id();", html)

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

    def test_region_workbench_surfaces_entry_nodes_on_canvas(self):
        html = palace_html()

        self.assertIn("function regionEntryNodes(regionId)", html)
        self.assertIn("function renderRegionEntryNodes(regionId)", html)
        self.assertIn('id="region-entry-nodes"', html)
        self.assertIn("region-entry-node", html)
        self.assertIn("region-entry-link", html)
        self.assertIn('n.addClass("region-entry-node")', html)
        self.assertIn('cy.elements().removeClass("region-entry-node")', html)
        self.assertIn("renderRegionEntryNodes(regionId)", html)

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

    def test_node_workbench_explains_store_edges_hidden_from_current_view(self):
        html = palace_html()

        self.assertIn("function storeNeighborSummary(memory)", html)
        self.assertIn("function renderHiddenStoreRelations(memory, visibleSummary)", html)
        self.assertIn('id="workbench-hidden-store-relations"', html)
        self.assertIn("memory.store_neighbors", html)
        self.assertIn("outside the current graph view", html)
        self.assertIn("renderHiddenStoreRelations(memory, summary)", html)

    def test_node_detail_lens_surfaces_dossier_evidence(self):
        html = palace_html()

        self.assertIn("function nodeRoleLabel(graphData)", html)
        self.assertIn("function nodeEvidenceRows(memory, graphData, region, relationSummary)", html)
        self.assertIn("function renderNodeDossier(memory, graphNode, region)", html)
        self.assertIn('id="workbench-node-dossier"', html)
        self.assertIn("node-dossier", html)
        self.assertIn("node-dossier-facts", html)
        self.assertIn("node-dossier-signal", html)
        self.assertIn("data-node-detail-lens", html)
        self.assertIn("evidenceRows.map", html)
        self.assertIn("renderNodeDossier(m, graphNode, region)", html)

    def test_node_detail_lens_surfaces_signal_lane(self):
        html = palace_html()

        self.assertIn("function renderNodeSignalLane(memory, graphNode, region)", html)
        self.assertIn('id="workbench-node-signal-lane"', html)
        self.assertIn("node-signal-lane", html)
        self.assertIn("node-signal-card", html)
        self.assertIn("node-signal-hop", html)
        self.assertIn("data-node-signal-hop", html)
        self.assertIn("function inspectWorkbenchRelation(panel, memory, key)", html)
        self.assertIn("inspectWorkbenchRelation(panel, memory, key);", html)
        self.assertIn("renderNodeSignalLane(m, graphNode, region)", html)

    def test_orphan_node_detail_embeds_edge_repair_console(self):
        html = palace_html()

        self.assertIn("function renderNodeEdgeRepair(memory, graphNode, region)", html)
        self.assertIn('id="workbench-node-edge-repair"', html)
        self.assertIn("node-edge-repair", html)
        self.assertIn("graphData.orphan", html)
        self.assertIn("renderRegionOrphanCandidateShell(region)", html)
        self.assertIn("loadRegionOrphanCandidates(region.id);", html)
        self.assertIn("function bindNodeEdgeRepairActions(panel, regionId)", html)
        self.assertIn("handleOrphanRepairClick(e, regionId)", html)
        self.assertIn("renderNodeEdgeRepair(m, graphNode, region)", html)

    def test_orphan_candidate_empty_state_explains_guardrail_buckets(self):
        html = palace_html()

        self.assertIn("function renderOrphanCandidateDiagnostics(result)", html)
        self.assertIn("orphan-candidate-diagnostics", html)
        self.assertIn("orphan-candidate-diagnostic", html)
        self.assertIn("skipped_existing_edges", html)
        self.assertIn("store-linked", html)
        self.assertIn("renderOrphanCandidateDiagnostics(result || {})", html)
        self.assertIn("no eligible orphan candidates under current guardrails", html)

    def test_node_workbench_derives_region_for_deep_linked_orphans(self):
        html = palace_html()

        self.assertIn("function nodeWorkbenchRegionFor(graphData)", html)
        self.assertIn("if (!graphData.region && !graphData.id && !graphData.kind)", html)
        self.assertIn("graphData.region || atlasRegionForNode(graphData)", html)
        self.assertIn("label: atlasLabel(regionId)", html)
        self.assertIn("orphans: graphData.orphan ? 1 : 0", html)
        self.assertIn("nodeWorkbenchRegionFor(graphData)", html)

    def test_node_detail_lens_body_state_is_scoped_to_node_workbench(self):
        html = palace_html()

        self.assertIn("node-detail-lens", html)
        self.assertIn('document.body.classList.add("node-detail-lens");', html)
        self.assertIn('document.body.classList.remove("node-detail-lens");', html)
        self.assertIn('document.body.classList.remove("atlas-district-overview");', html)
        self.assertIn('"overlay-color": "#ffffff"', html)
        self.assertIn('"overlay-opacity": 0.34', html)

    def test_node_glyphs_use_half_scale_screen_size(self):
        html = palace_html()

        self.assertIn("const NODE_GLYPH_SCREEN_SCALE = 0.07;", html)
        self.assertIn("const NODE_GLYPH_SCREEN_MIN = 2;", html)
        self.assertIn("const NODE_GLYPH_SCREEN_MAX = 4;", html)
        self.assertIn("nodeGlyphScreenSizeFromSize(size)", html)
        self.assertIn('"width": "data(displaySize)", "height": "data(displaySize)"', html)

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

    def test_neighbor_relation_selection_highlights_graph_path(self):
        html = palace_html()

        self.assertIn("function applyRelationFocus(memoryKey, neighborKey)", html)
        self.assertIn("function clearRelationFocus()", html)
        self.assertIn("relation-focus-node", html)
        self.assertIn("relation-focus-edge", html)
        self.assertIn('cy.elements().removeClass("relation-focus-node relation-focus-edge")', html)
        self.assertIn('edge.addClass("relation-focus-edge")', html)
        self.assertIn('neighbor.addClass("relation-focus-node")', html)
        self.assertIn("applyRelationFocus(memory.key, key);", html)
        self.assertIn("clearRelationFocus();", html)

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

    def test_approved_plan_surfaces_human_confirmed_write_gate(self):
        html = palace_html()

        self.assertIn("function renderOrphanApprovedPlanApplyGate(plan, regionId)", html)
        self.assertIn("function runOrphanApprovedPlanApply(regionId, dryRun)", html)
        self.assertIn("/api/orphan-approved-link-apply", html)
        self.assertIn("data-orphan-approved-apply", html)
        self.assertIn("data-orphan-approved-confirm", html)
        self.assertIn("APPLY APPROVED LINKS", html)

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

    def test_graph_reports_screen_space_overlap(self):
        html = palace_html()

        self.assertIn("lastScreenOverlapCount: 0", html)
        self.assertIn("lastScreenOverlapRatio: 0", html)
        self.assertIn("function graphScreenNodeRadius(node)", html)
        self.assertIn("function countScreenNodeOverlaps(nodes", html)
        self.assertIn("screenOverlapCount", html)
        self.assertIn("screenOverlapRatio", html)
        self.assertIn("screen-overlap", html)

    def test_region_layout_uses_spacious_shells_before_cose(self):
        html = palace_html()

        self.assertIn("const ATLAS_REGION_RADIUS_SCALE", html)
        self.assertIn("const ATLAS_REGION_Y_SCALE", html)
        self.assertIn("const REGION_SHELL_BASE_SPACING", html)
        self.assertIn("const REGION_SHELL_DENSITY_SPACING", html)
        self.assertIn("const REGION_SHELL_Y_SCALE", html)
        self.assertIn("Math.sqrt(group.length) * REGION_SHELL_DENSITY_SPACING", html)
        self.assertIn("Math.sqrt(idx) * shellSpacing", html)
        self.assertIn("Math.sin(regionAngle) * atlasRadius * ATLAS_REGION_Y_SCALE", html)
        self.assertIn("Math.sin(localAngle) * shellRadius * REGION_SHELL_Y_SCALE", html)
        self.assertIn("const GRAPH_VERTICAL_COMPRESSION", html)
        self.assertIn("function compressGraphVerticalRange(cy", html)
        self.assertIn("compressGraphVerticalRange(cy);", html)
        self.assertIn("nodeOverlap: clampNumber(72 + scale", html)

    def test_zoom_keeps_node_glyphs_screen_sized(self):
        html = palace_html()

        self.assertIn("screenGlyphSize", html)
        self.assertIn("screenHaloPad", html)
        self.assertIn("displaySize", html)
        self.assertIn("displayHaloPad", html)
        self.assertIn("function nodeGlyphScreenSize(node)", html)
        self.assertIn("function nodeHaloScreenPad(node)", html)
        self.assertIn("function updateZoomScaledNodeMetrics()", html)
        self.assertIn("function scheduleZoomScaledNodeMetrics()", html)
        self.assertIn('state.cy.on("zoom"', html)
        self.assertIn("screenGlyphSize / zoom", html)
        self.assertIn("screenHaloPad / zoom", html)
        self.assertIn('"width": "data(displaySize)"', html)
        self.assertIn('"height": "data(displaySize)"', html)

    def test_overview_and_close_zoom_use_the_same_screen_glyph_size(self):
        html = palace_html()

        self.assertIn("const NODE_GLYPH_SCREEN_SCALE", html)
        self.assertIn("const NODE_GLYPH_SCREEN_MIN", html)
        self.assertIn("const NODE_GLYPH_SCREEN_MAX", html)
        self.assertNotIn("NODE_GLYPH_LOCK_ZOOM", html)
        self.assertNotIn("glyphMetricZoom(zoom)", html)

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
