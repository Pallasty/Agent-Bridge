//! Explicit, local observation experiment; no model, action, or task-success test.
//!
//! Run this ignored test alone with `--ignored --nocapture --test-threads=1`.
//! Required: JEV_SNAPSHOT_JS points to the pinned upstream file,
//! AGENT_BRIDGE_HEADLESS=1, and AGENT_BRIDGE_BROWSER_PROFILE is an absolute,
//! nonexistent directory whose parent exists. JEV_OBSERVATION_OUTPUT optionally
//! names a new JSON file. The caller owns cleanup of the dedicated Chrome process
//! and profile: BrowserBackend::close closes pages, not the persistent browser.

use std::{
    error::Error,
    fs::{self, OpenOptions},
    io::{self, Write},
    path::PathBuf,
    process::{Command, Stdio},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use ab_browser::{BrowserBackend, ChromiumCdpBackend};
use ab_core::PageId;
use serde_json::{json, Value};

type ProbeResult<T> = Result<T, Box<dyn Error + Send + Sync>>;

const UPSTREAM_COMMIT: &str = "1231850a0bf1a0c0341fe408ef1668dbbfdfac46";
const SNAPSHOT_SHA256: &str = "e50473501c8fb8e70f3b21866d987393e3f2315c639d638bd477d170e81ed78d";
const PAIRS: usize = 15;
const OBSERVATION_TIMEOUT: Duration = Duration::from_secs(10);

struct Target {
    id: &'static str,
    role: &'static str,
    name: &'static str,
    scope: &'static str,
    value: Option<&'static str>,
    checked: Option<bool>,
}

struct Fixture {
    id: &'static str,
    body: &'static str,
    targets: Vec<Target>,
}

fn target(id: &'static str, role: &'static str, name: &'static str) -> Target {
    Target {
        id,
        role,
        name,
        scope: "main_document",
        value: None,
        checked: None,
    }
}

fn fixtures() -> Vec<Fixture> {
    vec![
        Fixture {
            id: "ordinary_html",
            body: r##"<h1>Ordinary fixture</h1>
<button>Ordinary primary</button>
<label for="query">Ordinary query</label><input id="query" value="seed">
<a href="#local">Ordinary link</a>"##,
            targets: vec![
                target("primary", "button", "Ordinary primary"),
                Target {
                    value: Some("seed"),
                    ..target("query", "textbox", "Ordinary query")
                },
                target("link", "link", "Ordinary link"),
            ],
        },
        Fixture {
            id: "checkbox_and_native_select",
            body: r#"<h1>Control fixture</h1>
<label><input type="checkbox" checked>Control consent</label>
<label for="destination">Control destination</label>
<select id="destination"><option selected>London</option><option>Zurich</option>
<option disabled>Oslo</option></select>"#,
            targets: vec![
                Target {
                    checked: Some(true),
                    ..target("consent", "checkbox", "Control consent")
                },
                Target {
                    value: Some("London"),
                    ..target("destination", "combobox", "Control destination")
                },
            ],
        },
        Fixture {
            id: "open_shadow_root",
            body: r#"<h1>Shadow fixture</h1><button>Shadow light control</button>
<div id="shadow-host"></div><script>
document.getElementById('shadow-host').attachShadow({mode:'open'}).innerHTML =
'<button>Shadow primary</button><label for="shadow-query">Shadow query</label><input id="shadow-query" value="shadow seed">';
</script>"#,
            targets: vec![
                target("light_control", "button", "Shadow light control"),
                Target {
                    scope: "open_shadow_root",
                    ..target("shadow_primary", "button", "Shadow primary")
                },
                Target {
                    scope: "open_shadow_root",
                    value: Some("shadow seed"),
                    ..target("shadow_query", "textbox", "Shadow query")
                },
            ],
        },
        Fixture {
            id: "same_origin_srcdoc_iframe",
            body: r#"<h1>Frame fixture</h1><button>Frame outer control</button>
<iframe title="Embedded fixture" width="700" height="180" srcdoc="<!doctype html><html><body><button>Frame primary</button><label for='frame-query'>Frame query</label><input id='frame-query' value='frame seed'></body></html>"></iframe>"#,
            targets: vec![
                target("outer_control", "button", "Frame outer control"),
                Target {
                    scope: "same_origin_srcdoc_iframe",
                    ..target("frame_primary", "button", "Frame primary")
                },
                Target {
                    scope: "same_origin_srcdoc_iframe",
                    value: Some("frame seed"),
                    ..target("frame_query", "textbox", "Frame query")
                },
            ],
        },
    ]
}

fn data_url(body: &str) -> String {
    const HEX: &[u8] = b"0123456789ABCDEF";
    let html = format!(
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Jev local observation fixture</title>\
         <style>body{{font:16px sans-serif;margin:16px}} button,input,select,a,iframe{{margin:8px}}\
         iframe{{display:block}}</style></head><body>{body}\
         <script>window.__fixtureReady=true</script></body></html>"
    );
    let mut url = String::from("data:text/html;charset=utf-8,");
    for byte in html.bytes() {
        url.push('%');
        url.push(HEX[(byte >> 4) as usize] as char);
        url.push(HEX[(byte & 15) as usize] as char);
    }
    url
}

fn flatten_ax(node: &Value, nodes: &mut Vec<Value>) {
    nodes.push(json!({
        "role": node.get("role"), "name": node.get("name"),
        "value": node.get("value"), "ref": node.get("ref")
    }));
    if let Some(children) = node.get("children").and_then(Value::as_array) {
        for child in children {
            flatten_ax(child, nodes);
        }
    }
}

fn coverage(fixture: &Fixture, method: &str, observation: &Value) -> Value {
    let mut nodes = Vec::new();
    if method == "ax" {
        flatten_ax(observation, &mut nodes);
    } else if let Some(actions) = observation.get("actions").and_then(Value::as_array) {
        nodes.clone_from(actions);
    }
    let targets: Vec<Value> = fixture
        .targets
        .iter()
        .map(|target| {
            let matches: Vec<&Value> = nodes
                .iter()
                .filter(|node| {
                    if node.get("role").and_then(Value::as_str) != Some(target.role) {
                        return false;
                    }
                    let label = node
                        .get(if method == "ax" { "name" } else { "label" })
                        .and_then(Value::as_str)
                        .unwrap_or("");
                    label == target.name
                        || (method == "jev_dom"
                            && node.get("kind").and_then(Value::as_str) == Some("select")
                            && label.starts_with(&format!("{} → ", target.name)))
                })
                .collect();
            let mut missing_state = Vec::new();
            if let Some(expected) = target.value {
                let found = matches.iter().any(|node| {
                    let field = if method == "jev_dom"
                        && node.get("kind").and_then(Value::as_str) == Some("select")
                    {
                        "current_value"
                    } else {
                        "value"
                    };
                    node.get(field).and_then(Value::as_str) == Some(expected)
                });
                if !found {
                    missing_state.push("current_value");
                }
            }
            if let Some(expected) = target.checked {
                let found = matches.iter().any(|node| {
                    node.get("checked").and_then(Value::as_bool) == Some(expected)
                        || node.get("checked").and_then(Value::as_str)
                            == Some(if expected { "true" } else { "false" })
                });
                if !found {
                    missing_state.push("checked");
                }
            }
            json!({
                "id": target.id, "fixture_scope": target.scope,
                "expected_role": target.role, "expected_name": target.name,
                "expected_value": target.value, "expected_checked": target.checked,
                "present": !matches.is_empty(), "matching_records": matches,
                "missing_expected_state": missing_state
            })
        })
        .collect();
    let present = targets.iter().filter(|t| t["present"] == true).count();
    json!({
        "target_count": targets.len(), "targets_present": present,
        "targets_missing": targets.len() - present, "targets": targets,
        "matching_rule": "role plus exact accessible name; native-select action label may append option name; text/marker/guards are not target-recall evidence"
    })
}

async fn observe(
    backend: &ChromiumCdpBackend,
    page: &PageId,
    method: &str,
    source: &str,
) -> (f64, Result<Value, String>) {
    let start = Instant::now();
    if method == "ax" {
        let result = tokio::time::timeout(OBSERVATION_TIMEOUT, backend.snapshot_a11y(page)).await;
        let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
        let value = match result {
            Ok(Ok(tree)) => serde_json::to_value(tree).map_err(|e| e.to_string()),
            Ok(Err(error)) => Err(error.to_string()),
            Err(error) => Err(format!("observation timeout: {error}")),
        };
        (elapsed_ms, value)
    } else {
        let result = tokio::time::timeout(OBSERVATION_TIMEOUT, backend.eval(page, source)).await;
        let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
        let value = match result {
            Ok(Ok(value))
                if value.get("actions").and_then(Value::as_array).is_some()
                    && value.get("text").and_then(Value::as_str).is_some() =>
            {
                Ok(value)
            }
            Ok(Ok(_)) => Err("upstream snapshot did not return actions array and text".into()),
            Ok(Err(error)) => Err(error.to_string()),
            Err(error) => Err(format!("observation timeout: {error}")),
        };
        (elapsed_ms, value)
    }
}

fn latency_summary(samples: &[Value], method: &str) -> Value {
    let selected: Vec<&Value> = samples.iter().filter(|s| s["method"] == method).collect();
    let mut successful: Vec<f64> = selected
        .iter()
        .filter(|s| s["error"].is_null())
        .filter_map(|s| s["elapsed_ms"].as_f64())
        .collect();
    successful.sort_by(f64::total_cmp);
    let percentile = |p: f64| -> Option<f64> {
        if successful.is_empty() {
            None
        } else {
            successful
                .get((p * successful.len() as f64).ceil() as usize - 1)
                .copied()
        }
    };
    json!({
        "attempts": selected.len(), "successful": successful.len(),
        "failed": selected.len() - successful.len(),
        "p50_ms": percentile(0.5), "p95_ms": percentile(0.95),
        "percentile_rule": "nearest rank over successful calls only; failures retained separately; n=15 means p95 is the maximum"
    })
}

async fn measure_fixture(
    backend: &ChromiumCdpBackend,
    page: &PageId,
    fixture: &Fixture,
    source: &str,
    fixture_index: usize,
) -> ProbeResult<Value> {
    backend.set_viewport(page, 1120, 780, 1.0, false).await?;
    let readiness = backend
        .eval(
            page,
            r#"new Promise((resolve,reject)=>{
const deadline=performance.now()+5000;
const check=()=>{
  const frames=[...document.querySelectorAll('iframe')];
  if(window.__fixtureReady && frames.every(f=>f.contentDocument?.readyState==='complete' && f.contentDocument.querySelector('button'))){
    requestAnimationFrame(()=>requestAnimationFrame(()=>resolve({ready:true,user_agent:navigator.userAgent,width:innerWidth,height:innerHeight,frame_count:frames.length})));return;
  }
  if(performance.now()>deadline){reject(new Error('fixture readiness timed out'));return;}
  setTimeout(check,10);
};check();})"#,
        )
        .await?;
    let mut warmups = Vec::new();
    for method in ["ax", "jev_dom"] {
        let (elapsed_ms, result) = observe(backend, page, method, source).await;
        warmups.push(json!({"method": method, "elapsed_ms": elapsed_ms, "error": result.err()}));
    }
    let mut samples = Vec::new();
    let mut first_ax = None;
    let mut first_dom = None;
    for pair in 0..PAIRS {
        let order = if (pair + fixture_index) & 1 == 0 {
            ["ax", "jev_dom"]
        } else {
            ["jev_dom", "ax"]
        };
        for (position, method) in order.into_iter().enumerate() {
            let (elapsed_ms, result) = observe(backend, page, method, source).await;
            let sample = match result {
                Ok(observation) => {
                    let recall = coverage(fixture, method, &observation);
                    let raw = if method == "ax" {
                        &mut first_ax
                    } else {
                        &mut first_dom
                    };
                    if raw.is_none() {
                        *raw = Some(observation);
                    }
                    json!({"pair": pair + 1, "position": position + 1, "method": method,
                        "elapsed_ms": elapsed_ms, "error": null, "coverage": recall})
                }
                Err(error) => json!({"pair": pair + 1, "position": position + 1, "method": method,
                    "elapsed_ms": elapsed_ms, "error": error, "coverage": null}),
            };
            samples.push(sample);
        }
    }
    let has_errors = warmups
        .iter()
        .chain(samples.iter())
        .any(|s| !s["error"].is_null());
    Ok(json!({
        "fixture": fixture.id, "fixture_body": fixture.body, "readiness": readiness,
        "status": if has_errors { "observation_errors" } else { "observed" },
        "warmups": warmups,
        "latency": {"ax": latency_summary(&samples, "ax"), "jev_dom": latency_summary(&samples, "jev_dom")},
        "samples": samples,
        "first_successful_raw_observation": {"ax": first_ax, "jev_dom": first_dom}
    }))
}

fn invalid(message: &str) -> Box<dyn Error + Send + Sync> {
    io::Error::new(io::ErrorKind::InvalidInput, message).into()
}

#[tokio::test]
#[ignore = "explicit local observation experiment; requires pinned JS and a new exclusive headless profile"]
async fn jev_observation_probe() -> ProbeResult<()> {
    let source_path = PathBuf::from(std::env::var("JEV_SNAPSHOT_JS")?).canonicalize()?;
    // Hash the exact bytes read, before passing them to any browser. This avoids
    // a second path read between verification and execution and needs no new crate.
    let source = fs::read_to_string(&source_path)?;
    let mut hasher = Command::new("sha256sum")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()?;
    hasher
        .stdin
        .take()
        .ok_or_else(|| invalid("sha256sum stdin missing"))?
        .write_all(source.as_bytes())?;
    let hash_output = hasher.wait_with_output()?;
    let hash_text = String::from_utf8(hash_output.stdout)?;
    if !hash_output.status.success() || hash_text.split_whitespace().next() != Some(SNAPSHOT_SHA256)
    {
        return Err(invalid(
            "snapshot.js does not match the pinned upstream SHA-256",
        ));
    }
    let headless = std::env::var("AGENT_BRIDGE_HEADLESS")?;
    if headless != "1" && !headless.eq_ignore_ascii_case("true") {
        return Err(invalid("AGENT_BRIDGE_HEADLESS must be 1 or true"));
    }
    let profile = PathBuf::from(std::env::var("AGENT_BRIDGE_BROWSER_PROFILE")?);
    if !profile.is_absolute() {
        return Err(invalid(
            "AGENT_BRIDGE_BROWSER_PROFILE must be an absolute new path",
        ));
    }
    let mut output = std::env::var_os("JEV_OBSERVATION_OUTPUT")
        .map(|path| OpenOptions::new().write(true).create_new(true).open(path))
        .transpose()?;
    // create_dir refuses any existing directory/symlink: the backend cannot adopt
    // a user browser from an already-populated profile via DevToolsActivePort.
    fs::create_dir(&profile)?;
    let backend = ChromiumCdpBackend::new();
    let mut results = Vec::new();
    for (index, fixture) in fixtures().iter().enumerate() {
        let url = data_url(fixture.body);
        match backend.navigate(&url).await {
            Ok(page) => {
                let measured = measure_fixture(&backend, &page, fixture, &source, index).await;
                let close_error = backend.close(&page).await.err().map(|e| e.to_string());
                let mut result = match measured {
                    Ok(value) => value,
                    Err(error) => json!({"fixture": fixture.id, "status": "fixture_error", "error": error.to_string()}),
                };
                result["page_close_error"] = json!(close_error);
                results.push(result);
            }
            Err(error) => results.push(json!({"fixture": fixture.id, "status": "navigation_error", "error": error.to_string()})),
        }
    }
    let has_errors = results
        .iter()
        .any(|r| r["status"] != "observed" || !r["page_close_error"].is_null());
    let report = json!({
        "schema": "jev-local-observation-probe-v1",
        "status": if has_errors { "infrastructure_or_observation_errors" } else { "completed_observation_only" },
        "created_unix_ms": SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis(),
        "upstream": {"commit": UPSTREAM_COMMIT, "snapshot_path": source_path, "snapshot_sha256": SNAPSHOT_SHA256, "source_modified": false},
        "profile": profile, "headless": true,
        "methods": {"ax": "existing ChromiumCdpBackend::snapshot_a11y projection", "jev_dom": "existing ChromiumCdpBackend::eval with unchanged pinned snapshot.js"},
        "timing": {"pairs_per_fixture": PAIRS, "order": "alternating, first method reversed between fixtures", "warmups_per_method_per_fixture": 1,
            "boundary": "wall time around one awaited backend observation, including CDP transport and backend conversion; excludes setup, navigation, readiness, model calls, actions, scoring and report serialization",
            "cdp_call_counts": null, "cdp_call_counts_reason": "not instrumented"},
        "evidence_limits": [
            "Controlled synthetic pages only; no natural-task or model benefit was measured.",
            "Recall is over manually enumerated fixture targets, not general web accessibility.",
            "Both methods use their existing top-level entrypoints; no added frame/shadow traversal or fallback.",
            "AX means the existing A11yNode projection, not every raw CDP AX property; it has no checked field.",
            "Jev selection actions encode non-selected choices; presence of a combobox action is not proof that all options were recalled.",
            "Neither action validity nor click-by-ref equivalence is measured.",
            "Warm-cache local observation latency does not establish end-to-end speed, cost or production value.",
            "Target omissions are findings, not harness success assertions; zero test exit means observations completed without recorded runtime errors.",
            "Only fixture tabs were closed; caller must terminate the dedicated browser and retire the dedicated profile."
        ],
        "fixtures": results
    });
    let serialized = serde_json::to_string_pretty(&report)?;
    if let Some(file) = output.as_mut() {
        file.write_all(serialized.as_bytes())?;
        file.write_all(b"\n")?;
        file.sync_all()?;
    }
    println!("JEV_OBSERVATION_REPORT_BEGIN\n{serialized}\nJEV_OBSERVATION_REPORT_END");
    if has_errors {
        return Err(invalid(
            "probe retained infrastructure/observation errors in its report",
        ));
    }
    Ok(())
}
