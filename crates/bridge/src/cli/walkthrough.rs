/// Return whether a rendered walkthrough's `#ab-render` region carries actual
/// summary, heading, narrative, or evidence content rather than only wrappers.
pub(crate) fn walkthrough_region_has_content(html: &str) -> bool {
    ab_bridge::present::render_region(html)
        .map(|region| {
            region.contains("wt-summary")
                || region.contains("wt-heading")
                || region.contains("wt-narrative")
                || region.contains("wt-ev")
        })
        .unwrap_or(false)
}
