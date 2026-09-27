//! Observation refs must never alias another snapshot or page.
//!
//! Run explicitly with:
//! `cargo test -p ab-browser --test observation_ref_e2e -- --ignored --nocapture`
//! This test owns a fresh profile and Chrome child; it never adopts a user profile.

use std::{
    ffi::OsString,
    path::PathBuf,
    process::{Child, Command, Stdio},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use ab_browser::{A11yNode, BrowserBackend, ChromiumCdpBackend};
use ab_core::PageId;
use futures::StreamExt;

struct OwnedChrome {
    profile: PathBuf,
    child: Option<Child>,
    previous_profile: Option<OsString>,
    previous_headless: Option<OsString>,
}

impl OwnedChrome {
    fn launch() -> Self {
        let parent = std::env::var_os("HOME")
            .map(|home| PathBuf::from(home).join(".cache"))
            .unwrap_or_else(std::env::temp_dir);
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock after epoch")
            .as_nanos();
        let profile = parent.join(format!(
            "ab-observation-ref-e2e-{}-{nonce}",
            std::process::id()
        ));
        let mut builder = std::fs::DirBuilder::new();
        #[cfg(unix)]
        {
            use std::os::unix::fs::DirBuilderExt;
            builder.mode(0o700);
        }
        builder.create(&profile).expect("create exclusive profile");
        let mut owned = Self {
            profile,
            child: None,
            previous_profile: std::env::var_os("AGENT_BRIDGE_BROWSER_PROFILE"),
            previous_headless: std::env::var_os("AGENT_BRIDGE_HEADLESS"),
        };
        // This integration-test binary contains one test, so these environment
        // changes cannot race another test in the same process.
        std::env::set_var("AGENT_BRIDGE_BROWSER_PROFILE", &owned.profile);
        std::env::set_var("AGENT_BRIDGE_HEADLESS", "1");
        let executable = std::env::var_os("AGENT_BRIDGE_CHROME")
            .unwrap_or_else(|| OsString::from("google-chrome"));
        owned.child = Some(
            Command::new(executable)
                .args([
                    "--headless=new",
                    "--remote-debugging-port=0",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                ])
                .arg(format!("--user-data-dir={}", owned.profile.display()))
                .arg("about:blank")
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .expect("launch owned Chrome (set AGENT_BRIDGE_CHROME if needed)"),
        );
        eprintln!("owned Chrome profile: {}", owned.profile.display());
        owned
    }

    async fn wait_ready(&mut self) -> u16 {
        tokio::time::timeout(Duration::from_secs(20), async {
            loop {
                let status = self
                    .child
                    .as_mut()
                    .expect("owned Chrome child")
                    .try_wait()
                    .expect("poll owned Chrome");
                assert!(status.is_none(), "owned Chrome exited early: {status:?}");
                if let Ok(raw) = std::fs::read_to_string(self.profile.join("DevToolsActivePort")) {
                    if let Some(port) = raw.lines().next().and_then(|line| line.parse::<u16>().ok())
                    {
                        if port != 0 {
                            return port;
                        }
                    }
                }
                tokio::time::sleep(Duration::from_millis(25)).await;
            }
        })
        .await
        .expect("owned Chrome startup deadline")
    }

    async fn close_browser(&mut self, port: u16) {
        // Only the endpoint read from this test's exclusive profile is used.
        // Drop below still owns kill/wait if graceful shutdown times out.
        let _ = tokio::time::timeout(Duration::from_secs(3), async {
            if let Ok((mut browser, mut handler)) =
                chromiumoxide::Browser::connect(format!("http://127.0.0.1:{port}")).await
            {
                let pump = tokio::spawn(async move { while handler.next().await.is_some() {} });
                let _ = browser.close().await;
                pump.abort();
            }
        })
        .await;
        // Browser.close acknowledges the request before Chrome has necessarily
        // flushed its profile and reaped its children. Give our child a bounded
        // chance to exit normally before Drop's kill fallback.
        let deadline = Instant::now() + Duration::from_secs(2);
        while let Some(child) = self.child.as_mut() {
            match child.try_wait() {
                Ok(Some(_)) | Err(_) => break,
                Ok(None) if Instant::now() >= deadline => break,
                Ok(None) => tokio::time::sleep(Duration::from_millis(25)).await,
            }
        }
    }
}

impl Drop for OwnedChrome {
    fn drop(&mut self) {
        if let Some(child) = self.child.as_mut() {
            if !matches!(child.try_wait(), Ok(Some(_))) {
                // Child handles identify only the Chrome we spawned, never a
                // process found by name or a PID from another browser profile.
                let _ = child.kill();
            }
            let _ = child.wait();
        }
        // A Chrome child can briefly finish a profile write after its parent
        // exits. Retry only our exclusive directory, with a fixed deadline.
        let deadline = Instant::now() + Duration::from_secs(2);
        loop {
            match std::fs::remove_dir_all(&self.profile) {
                Ok(()) => break,
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => break,
                Err(error) if Instant::now() >= deadline => {
                    eprintln!(
                        "owned profile cleanup failed ({}): {error}",
                        self.profile.display()
                    );
                    break;
                }
                Err(_) => std::thread::sleep(Duration::from_millis(50)),
            }
        }
        for (name, previous) in [
            ("AGENT_BRIDGE_BROWSER_PROFILE", &self.previous_profile),
            ("AGENT_BRIDGE_HEADLESS", &self.previous_headless),
        ] {
            match previous {
                Some(value) => std::env::set_var(name, value),
                None => std::env::remove_var(name),
            }
        }
    }
}

fn find_ref(node: &A11yNode, name: &str) -> Option<String> {
    if node.role == "button" && node.name.as_deref() == Some(name) {
        return node.node_ref.clone();
    }
    node.children.iter().find_map(|child| find_ref(child, name))
}

fn fixture_url() -> String {
    let html = r#"<html><body>
        <script>
        window.good_click=0; window.wrong_click=0; window.trusted_click=0;
        window.phase='reject'; window.document_id=Math.random();
        function record(event) {
            if (window.phase === 'reject') window.wrong_click++;
            else window.good_click++;
            if (event.isTrusted) window.trusted_click++;
        }
        </script>
        <button id="subject" onclick="record(event)">Original</button>
        </body></html>"#;
    let encoded: String = html.bytes().map(|byte| format!("%{byte:02X}")).collect();
    format!("data:text/html,{encoded}")
}

async fn check_click(
    backend: &ChromiumCdpBackend,
    page: &PageId,
    node_ref: &str,
    should_accept: bool,
    case: &str,
    failures: &mut Vec<String>,
) {
    let phase = if should_accept { "accept" } else { "reject" };
    backend
        .eval(page, &format!("window.good_click=0; window.wrong_click=0; window.trusted_click=0; window.phase='{phase}';"))
        .await
        .expect("reset fixture counters");
    let result = backend.click_by_ref(page, node_ref).await;
    let counts = backend
        .eval(
            page,
            "[window.good_click, window.wrong_click, window.trusted_click]",
        )
        .await
        .expect("read fixture counters after action");
    let expected = if should_accept {
        serde_json::json!([1, 0, 1])
    } else {
        serde_json::json!([0, 0, 0])
    };
    if result.is_ok() != should_accept || counts != expected {
        failures.push(format!(
            "{case}: ref={node_ref}, result={result:?}, counts={counts}, expected={expected}"
        ));
    }
}

async fn exercise_refs(backend: &ChromiumCdpBackend) -> Vec<String> {
    let mut failures = Vec::new();
    let page = backend
        .navigate(&fixture_url())
        .await
        .expect("open fixture");
    let first = backend.snapshot_a11y(&page).await.expect("snapshot A");
    let old_ref = find_ref(&first, "Original").expect("original ref");

    backend.eval(&page, r#"document.getElementById('subject').outerHTML='<button id="replacement" onclick="record(event)">Replacement</button>'"#)
        .await.expect("replace original DOM node");
    let second = backend.snapshot_a11y(&page).await.expect("snapshot B");
    let new_ref = find_ref(&second, "Replacement").expect("replacement ref");
    check_click(
        backend,
        &page,
        &old_ref,
        false,
        "replacement rejects snapshot A ref",
        &mut failures,
    )
    .await;
    check_click(
        backend,
        &page,
        &new_ref,
        true,
        "fresh replacement ref clicks",
        &mut failures,
    )
    .await;

    let third = backend
        .snapshot_a11y(&page)
        .await
        .expect("same node snapshot C");
    let current_ref = find_ref(&third, "Replacement").expect("same node fresh ref");
    check_click(
        backend,
        &page,
        &new_ref,
        false,
        "same node new snapshot rejects prior ref",
        &mut failures,
    )
    .await;
    check_click(
        backend,
        &page,
        &current_ref,
        true,
        "same node fresh ref clicks",
        &mut failures,
    )
    .await;

    backend.reload(&page).await.expect("reload fixture");
    let reloaded = backend
        .snapshot_a11y(&page)
        .await
        .expect("snapshot after reload");
    let reload_ref = find_ref(&reloaded, "Original").expect("reloaded original ref");
    check_click(
        backend,
        &page,
        &current_ref,
        false,
        "reload plus snapshot cannot revive old ref",
        &mut failures,
    )
    .await;
    check_click(
        backend,
        &page,
        &reload_ref,
        true,
        "fresh post-reload ref clicks",
        &mut failures,
    )
    .await;

    let other_page = backend
        .navigate(&fixture_url())
        .await
        .expect("open second fixture");
    let other_tree = backend
        .snapshot_a11y(&other_page)
        .await
        .expect("second page snapshot");
    let other_ref = find_ref(&other_tree, "Original").expect("second page ref");
    check_click(
        backend,
        &other_page,
        &reload_ref,
        false,
        "cross-page ref is rejected",
        &mut failures,
    )
    .await;
    check_click(
        backend,
        &other_page,
        &other_ref,
        true,
        "second page fresh ref clicks",
        &mut failures,
    )
    .await;

    let clone = backend.clone();
    let cloned_tree = clone
        .snapshot_a11y(&page)
        .await
        .expect("snapshot through clone");
    let cloned_ref = find_ref(&cloned_tree, "Original").expect("clone fresh ref");
    check_click(
        backend,
        &page,
        &reload_ref,
        false,
        "clone snapshot invalidates old shared ref",
        &mut failures,
    )
    .await;
    check_click(
        backend,
        &page,
        &cloned_ref,
        true,
        "clone-issued fresh ref works on original backend",
        &mut failures,
    )
    .await;
    check_click(
        &clone,
        &other_page,
        &other_ref,
        true,
        "snapshot on first page preserves other page ref",
        &mut failures,
    )
    .await;

    backend
        .close(&other_page)
        .await
        .expect("close second fixture");
    backend.close(&page).await.expect("close first fixture");
    failures
}

#[tokio::test]
#[ignore = "launches an isolated real headless Chrome; run with --ignored"]
async fn observation_refs_never_alias_across_snapshots_or_pages() {
    let mut chrome = OwnedChrome::launch();
    let port = chrome.wait_ready().await;
    let backend = ChromiumCdpBackend::new();
    let outcome = tokio::time::timeout(Duration::from_secs(60), exercise_refs(&backend)).await;
    drop(backend);
    chrome.close_browser(port).await;
    let failures = outcome.expect("fixture sequence deadline");
    assert!(failures.is_empty(), "{}", failures.join("\n"));
}
