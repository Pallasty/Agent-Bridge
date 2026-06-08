//! Real-Chromium e2e for @eN click_by_ref (the acceptance test the adversarial
//! pre-deploy audit demanded — unit tests on `is_interactive` prove the role
//! table, NOT real click behavior). Marked `#[ignore]` because it launches a
//! real headless Chrome; run with:
//!   AGENT_BRIDGE_HEADLESS=1 cargo test -p ab-browser --test click_by_ref_e2e -- --ignored --nocapture

use ab_browser::{A11yNode, BrowserBackend, ChromiumCdpBackend};

fn find_ref(node: &A11yNode, role: &str, name_contains: &str) -> Option<String> {
    if node.role == role {
        if let Some(name) = &node.name {
            if name.contains(name_contains) {
                if let Some(r) = &node.node_ref {
                    return Some(r.clone());
                }
            }
        }
    }
    for c in &node.children {
        if let Some(r) = find_ref(c, role, name_contains) {
            return Some(r);
        }
    }
    None
}

#[tokio::test]
#[ignore = "launches a real headless Chrome; run with --ignored"]
async fn click_by_ref_real_chrome_e2e() {
    std::env::set_var("AGENT_BRIDGE_HEADLESS", "1");
    let b = ChromiumCdpBackend::new();

    // visible button records its click in document.title; disabled button would
    // record 'DIS' IF it ever fired (it must not).
    let html = "data:text/html,<html><body>\
        <button id=vis onclick=\"document.title='VIS'\">Click Visible</button>\
        <button id=dis disabled onclick=\"document.title='DIS'\">Disabled Btn</button>\
        </body></html>";

    let page = b.navigate(html).await.expect("navigate");
    let tree = b.snapshot_a11y(&page).await.expect("snapshot_a11y");

    // (1) positive control: a visible button gets a ref AND a real-mouse click fires it.
    let vis = find_ref(&tree, "button", "Click Visible").expect("visible button should have an @eN ref");
    b.click_by_ref(&page, &vis).await.expect("click_by_ref on visible button");
    let title = b.eval(&page, "document.title").await.expect("eval title");
    assert!(
        title.to_string().contains("VIS"),
        "real-mouse click_by_ref must actually fire the visible button (title={title})"
    );

    // (2) disabled button: click must be REFUSED loudly, never a false success.
    let _ = b.eval(&page, "document.title=''").await;
    if let Some(dis) = find_ref(&tree, "button", "Disabled") {
        let r = b.click_by_ref(&page, &dis).await;
        assert!(
            r.is_err(),
            "click_by_ref on a disabled button MUST error (no silent false success)"
        );
        let t2 = b.eval(&page, "document.title").await.expect("eval title");
        assert!(
            !t2.to_string().contains("DIS"),
            "disabled button must never fire (title={t2})"
        );
    }

    // (3) reload invalidates the page's refs: reusing a pre-reload ref must error
    // loudly (re-snapshot), not silently click whatever the backend id now maps to.
    b.reload(&page).await.expect("reload");
    let after = b.click_by_ref(&page, &vis).await;
    assert!(
        after.is_err(),
        "an @eN ref reused after reload MUST be invalidated (loud error, not a wrong-element click)"
    );

    let _ = b.close(&page).await;
}
