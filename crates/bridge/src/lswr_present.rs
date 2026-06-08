//! Live Semantic World Runtime Step D expression packet conversion.
//!
//! Step C returns `agent_bridge.world_tool.v0` envelopes from world_* tools.
//! Step D turns those envelopes into human-presentable packets while preserving
//! the lower layer's verification semantics. This module does not register MCP
//! tools, call the `present` tool, launch a browser, or ingest memories; the
//! optional file-render gate writes the same self-describing HTML that `present`
//! would write so D1 can test the sink contract without opening runtime lanes.

use serde_json::{Value, json};
use std::fmt::Write as _;
use std::path::{Path, PathBuf};

pub const LSWR_PRESENT_PACKET_SCHEMA: &str = "agent_bridge.lswr.present_packet.v0";
pub const WORLD_TOOL_SCHEMA: &str = "agent_bridge.world_tool.v0";
pub const DEFAULT_INGESTION_BLOCK_REASON: &str = "step_d_expression_gate_not_accepted";

#[derive(Debug, Clone)]
pub struct PresentPacketOptions<'a> {
    pub adapter: &'a str,
    pub commit: Option<&'a str>,
    pub generated_at: &'a str,
}

impl<'a> PresentPacketOptions<'a> {
    pub fn new(generated_at: &'a str) -> Self {
        Self {
            adapter: "onsen",
            commit: None,
            generated_at,
        }
    }

    pub fn with_commit(mut self, commit: &'a str) -> Self {
        self.commit = Some(commit);
        self
    }
}

#[derive(Debug, Clone)]
pub struct PresentPacketReviewFile {
    pub id: String,
    pub artifact_path: PathBuf,
    pub bytes: u64,
    pub dual_encoding: bool,
    pub static_render_status: String,
}

pub fn world_envelope_to_present_packet(
    world_tool: &str,
    envelope: &Value,
    options: PresentPacketOptions<'_>,
) -> Value {
    let verified = envelope
        .get("verified")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let reason = string_value(envelope.get("reason"))
        .or_else(|| string_value(get_path(envelope, &["verify", "evidence", "host_reason"])));
    let verdict = verdict_for(verified, reason.as_deref());
    let verify = envelope.get("verify").cloned().unwrap_or_else(|| json!({}));
    let verify_method = string_value(get_path(&verify, &["method"]));
    let verified_to = if verified {
        get_path(&verify, &["verified_to"])
            .cloned()
            .unwrap_or(Value::Null)
    } else {
        Value::Null
    };
    let request = envelope
        .get("request")
        .cloned()
        .unwrap_or_else(|| json!({}));
    let selected_entities = selected_entities(envelope, &request);
    let patch_result = patch_result(envelope);
    let action_result = envelope
        .get("action_result")
        .cloned()
        .unwrap_or(Value::Null);
    let raw_host_response_present = envelope
        .get("host_response")
        .map(|v| !v.is_null())
        .unwrap_or(false);

    json!({
        "schema": LSWR_PRESENT_PACKET_SCHEMA,
        "source_schema": envelope
            .get("schema")
            .and_then(Value::as_str)
            .unwrap_or(WORLD_TOOL_SCHEMA),
        "world_tool": world_tool,
        "verdict": verdict,
        "reason": reason,
        "title": title_for(world_tool, verdict),
        "summary": summary_for(world_tool, verdict, reason.as_deref()),
        "human_readable": {
            "changed": changed_entities(&patch_result),
            "visible": visible_entities(&selected_entities, verdict),
            "warnings": warnings_for(verdict, reason.as_deref()),
            "reason": reason,
        },
        "machine_payload": {
            "request": request,
            "verify": verify,
            "selected_entities": selected_entities,
            "patch_result": patch_result,
            "action_result": action_result,
            "source_reason": reason,
            "raw_host_response_present": raw_host_response_present,
        },
        "provenance": {
            "commit": options.commit,
            "adapter": options.adapter,
            "verified_to": verified_to,
            "verify_method": verify_method,
            "generated_at": options.generated_at,
        },
        "ingestion": {
            "allowed": false,
            "reason": DEFAULT_INGESTION_BLOCK_REASON,
        },
    })
}

pub fn present_packet_review_artifact(packet: &Value) -> String {
    let title = string_value(packet.get("title")).unwrap_or_else(|| "LSWR present packet".into());
    let summary = string_value(packet.get("summary")).unwrap_or_default();
    let verdict = string_value(packet.get("verdict")).unwrap_or_else(|| "not_verified".into());
    let reason = string_value(packet.get("reason")).unwrap_or_else(|| "none".into());
    let verdict_label = match verdict.as_str() {
        "verified" => "Verified",
        "blocked" => "Blocked",
        _ => "Unconfirmed",
    };
    let source_schema =
        string_value(packet.get("source_schema")).unwrap_or_else(|| "unknown".into());
    let world_tool = string_value(packet.get("world_tool")).unwrap_or_else(|| "unknown".into());
    let verify_method = string_value(get_path(packet, &["provenance", "verify_method"]))
        .unwrap_or_else(|| "unknown".into());
    let verified_to = value_label(get_path(packet, &["provenance", "verified_to"]))
        .unwrap_or_else(|| "none".into());
    let ingestion_allowed = get_path(packet, &["ingestion", "allowed"])
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let ingestion_reason =
        string_value(get_path(packet, &["ingestion", "reason"])).unwrap_or_else(|| "none".into());

    let mut html = String::new();
    let _ = write!(
        html,
        "<article class=\"lswr-review\" data-lswr-verdict=\"{}\">",
        html_escape(&verdict)
    );
    let _ = write!(
        html,
        "<header><p class=\"lswr-eyebrow\">Live Semantic World Runtime / Step D review packet</p><h1>{}</h1><p>{}</p></header>",
        html_escape(&title),
        html_escape(&summary)
    );
    let _ = write!(
        html,
        "<section><h2>Verification</h2>{}</section>",
        render_kv_table(&[
            ("verdict", verdict_label.to_string()),
            ("reason", reason),
            ("verified_to", verified_to),
            ("verify_method", verify_method),
            ("world_tool", world_tool),
            ("source_schema", source_schema),
        ])
    );
    let _ = write!(
        html,
        "<section><h2>Human-visible result</h2><h3>Visible</h3>{}<h3>Changed</h3>{}<h3>Warnings</h3>{}</section>",
        render_value_list(get_path(packet, &["human_readable", "visible"])),
        render_value_list(get_path(packet, &["human_readable", "changed"])),
        render_value_list(get_path(packet, &["human_readable", "warnings"]))
    );
    let _ = write!(
        html,
        "<section><h2>Ingestion gate</h2><p><strong>{}</strong></p><p>{}</p></section>",
        if ingestion_allowed {
            "Ingestion allowed"
        } else {
            "Ingestion blocked"
        },
        html_escape(&ingestion_reason)
    );
    let _ = write!(
        html,
        "<section><h2>Machine packet preview</h2><pre>{}</pre></section>",
        html_escape(&serde_json::to_string_pretty(packet).unwrap_or_default())
    );
    html.push_str("</article>");
    html
}

pub fn present_packet_review_args(packet: &Value, verify: bool) -> Value {
    let title = string_value(packet.get("title")).unwrap_or_else(|| "LSWR present packet".into());
    json!({
        "kind": "html",
        "artifact": present_packet_review_artifact(packet),
        "payload": packet,
        "title": title,
        "intent": "LSWR Step D present packet review",
        "channel": "file",
        "verify": verify,
        "interactive": false,
        "provenance": {
            "source_tool": "lswr_present",
            "source_schema": packet.get("schema").cloned().unwrap_or(Value::Null),
            "source_world_tool": packet.get("world_tool").cloned().unwrap_or(Value::Null),
            "verdict": packet.get("verdict").cloned().unwrap_or(Value::Null),
            "reason": packet.get("reason").cloned().unwrap_or(Value::Null),
            "verified_to": get_path(packet, &["provenance", "verified_to"]).cloned().unwrap_or(Value::Null),
            "verify_method": get_path(packet, &["provenance", "verify_method"]).cloned().unwrap_or(Value::Null),
        },
    })
}

pub fn present_packet_review_html(packet: &Value) -> String {
    let args = present_packet_review_args(packet, false);
    let provenance = present_packet_review_provenance(&args);
    crate::present::build_html(
        crate::present::PresentKind::Html,
        args.get("artifact").and_then(Value::as_str).unwrap_or(""),
        args.get("title").and_then(Value::as_str),
        args.get("payload"),
        Some(&provenance),
    )
}

pub fn present_packet_review_id(packet: &Value) -> String {
    let args = present_packet_review_args(packet, false);
    present_packet_review_id_from_args(&args)
}

pub fn write_present_packet_review_file(
    packet: &Value,
    dir: &Path,
) -> std::io::Result<PresentPacketReviewFile> {
    let id = present_packet_review_id(packet);
    let html = present_packet_review_html(packet);
    let path = dir.join(format!("{id}.html"));
    crate::present::write_artifact_atomic(&path, &html)?;
    let bytes = std::fs::metadata(&path)?.len();
    let dual_encoding = crate::present::extract_ab_payload(&html).is_some();
    let static_render_status = if crate::present::render_region(&html)
        .map(str::trim)
        .unwrap_or_default()
        .is_empty()
    {
        "blank_static"
    } else {
        "rendered_static"
    }
    .to_string();
    Ok(PresentPacketReviewFile {
        id,
        artifact_path: path,
        bytes,
        dual_encoding,
        static_render_status,
    })
}

fn verdict_for(verified: bool, reason: Option<&str>) -> &'static str {
    if verified {
        return "verified";
    }
    match reason {
        Some("world_host_non_loopback_rejected") => "blocked",
        Some("world_patch_invalid") | Some("world_patch_blocked") => "blocked",
        _ => "not_verified",
    }
}

fn title_for(world_tool: &str, verdict: &str) -> String {
    let noun = match world_tool {
        "world_patch" => "World patch",
        "world_query" => "World query",
        "world_visibility_query" => "World visibility",
        _ => "World result",
    };
    match verdict {
        "verified" => format!("{noun} verified"),
        "blocked" => format!("{noun} blocked"),
        _ => format!("{noun} unconfirmed"),
    }
}

fn summary_for(world_tool: &str, verdict: &str, reason: Option<&str>) -> String {
    match verdict {
        "verified" => match world_tool {
            "world_patch" => {
                "The runtime verified the world patch against the live semantic world evidence."
                    .to_string()
            }
            "world_visibility_query" => {
                "The runtime verified visibility against the live Onsen root viewport.".to_string()
            }
            _ => "The runtime verified this world result.".to_string(),
        },
        "blocked" => format!(
            "The runtime blocked this world operation{}.",
            reason.map(|r| format!(" because {r}")).unwrap_or_default()
        ),
        _ => format!(
            "The runtime could not verify this world result{}.",
            reason.map(|r| format!(" because {r}")).unwrap_or_default()
        ),
    }
}

fn warnings_for(verdict: &str, reason: Option<&str>) -> Vec<Value> {
    if verdict == "verified" {
        return Vec::new();
    }
    reason
        .map(|r| vec![json!(r)])
        .unwrap_or_else(|| vec![json!("not_verified")])
}

fn visible_entities(selected_entities: &Value, verdict: &str) -> Vec<Value> {
    if verdict != "verified" {
        return Vec::new();
    }
    selected_entities
        .as_array()
        .map(|entities| {
            entities
                .iter()
                .filter_map(|entity| entity.get("id").and_then(Value::as_str))
                .map(|id| json!(id))
                .collect::<Vec<_>>()
        })
        .unwrap_or_default()
}

fn changed_entities(patch_result: &Value) -> Vec<Value> {
    patch_result
        .get("entity")
        .and_then(Value::as_str)
        .map(|entity| vec![json!(entity)])
        .unwrap_or_default()
}

fn patch_result(envelope: &Value) -> Value {
    for path in [
        &["host_response", "world.patch"][..],
        &["host_response", "world", "patch"][..],
        &["world.patch"][..],
    ] {
        if let Some(v) = get_path(envelope, path) {
            return v.clone();
        }
    }
    Value::Null
}

fn selected_entities(envelope: &Value, request: &Value) -> Value {
    let mut entities = Vec::new();
    if let Some(arr) = get_path(
        envelope,
        &[
            "host_response",
            "world.visibility.query",
            "after",
            "entities",
        ],
    )
    .and_then(Value::as_array)
    {
        for entity in arr {
            entities.push(normalize_entity(entity));
        }
    }
    if entities.is_empty() {
        for id in requested_entities(request) {
            entities.push(json!({
                "id": id,
                "screen_area": get_path(envelope, &["verify", "evidence", "screen_area"]).cloned().unwrap_or(Value::Null),
                "bounds_screen_area": get_path(envelope, &["verify", "evidence", "bounds_screen_area"]).cloned().unwrap_or(Value::Null),
                "occluded": Value::Null,
            }));
        }
    }
    Value::Array(entities)
}

fn normalize_entity(entity: &Value) -> Value {
    json!({
        "id": entity
            .get("id")
            .or_else(|| entity.get("entity"))
            .cloned()
            .unwrap_or(Value::Null),
        "screen_area": entity.get("screen_area").cloned().unwrap_or(Value::Null),
        "bounds_screen_area": entity
            .get("bounds_screen_area")
            .cloned()
            .unwrap_or(Value::Null),
        "occluded": entity.get("occluded").cloned().unwrap_or(Value::Null),
    })
}

fn requested_entities(request: &Value) -> Vec<String> {
    get_path(request, &["world.visibility.query", "entities"])
        .and_then(Value::as_array)
        .map(|arr| {
            arr.iter()
                .filter_map(Value::as_str)
                .map(ToString::to_string)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default()
}

fn string_value(value: Option<&Value>) -> Option<String> {
    value.and_then(Value::as_str).and_then(|s| {
        let trimmed = s.trim();
        if trimmed.is_empty() {
            None
        } else {
            Some(trimmed.to_string())
        }
    })
}

fn value_label(value: Option<&Value>) -> Option<String> {
    match value {
        Some(Value::String(s)) if !s.trim().is_empty() => Some(s.trim().to_string()),
        Some(Value::Null) | None => None,
        Some(other) => Some(other.to_string()),
    }
}

fn render_kv_table(rows: &[(&str, String)]) -> String {
    let rows = rows
        .iter()
        .map(|(key, value)| {
            format!(
                "<tr><th>{}</th><td>{}</td></tr>",
                html_escape(key),
                html_escape(value)
            )
        })
        .collect::<Vec<_>>()
        .join("");
    format!("<table><tbody>{rows}</tbody></table>")
}

fn render_value_list(value: Option<&Value>) -> String {
    let Some(items) = value.and_then(Value::as_array) else {
        return "<p class=\"lswr-empty\">none</p>".to_string();
    };
    if items.is_empty() {
        return "<p class=\"lswr-empty\">none</p>".to_string();
    }
    let items = items
        .iter()
        .map(|item| {
            format!(
                "<li>{}</li>",
                html_escape(&value_label(Some(item)).unwrap_or_else(|| "null".into()))
            )
        })
        .collect::<Vec<_>>()
        .join("");
    format!("<ul>{items}</ul>")
}

fn present_packet_review_provenance(args: &Value) -> Value {
    let mut provenance = args.get("provenance").cloned().unwrap_or_else(|| json!({}));
    if let Some(obj) = provenance.as_object_mut() {
        obj.entry("generated_by")
            .or_insert_with(|| json!(crate::present::PRESENT_SCHEMA));
        obj.insert("kind".into(), json!("html"));
        obj.insert("ts".into(), json!(crate::present::now_unix()));
    }
    provenance
}

fn present_packet_review_id_from_args(args: &Value) -> String {
    let kind = args.get("kind").and_then(Value::as_str).unwrap_or("html");
    let title = args.get("title").and_then(Value::as_str).unwrap_or("");
    let artifact = args.get("artifact").and_then(Value::as_str).unwrap_or("");
    let payload = args
        .get("payload")
        .map(Value::to_string)
        .unwrap_or_default();
    let enhanced = false;
    crate::present::derive_id(&format!(
        "{kind}\u{0}{title}\u{0}{artifact}\u{0}{payload}\u{0}{enhanced}"
    ))
}

fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}

fn get_path<'a>(value: &'a Value, path: &[&str]) -> Option<&'a Value> {
    let mut cur = value;
    for key in path {
        cur = cur.get(*key)?;
    }
    Some(cur)
}

#[cfg(test)]
mod tests {
    use super::*;

    const GENERATED_AT: &str = "2026-06-06T00:00:00Z";
    const COMMIT: &str = "5037e01";

    fn opts() -> PresentPacketOptions<'static> {
        PresentPacketOptions::new(GENERATED_AT).with_commit(COMMIT)
    }

    #[test]
    fn verified_visibility_maps_to_verified_packet() {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": true,
            "reason": null,
            "request": {
                "request_id": "fixture-verified-visibility",
                "world.visibility.query": {"entities": ["bath"]}
            },
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": "onsen_live_root_viewport",
                "evidence": {
                    "screen_area": 0.005815625,
                    "bounds_screen_area": 0.0186224985122681,
                    "host_reason": null
                }
            },
            "host_response": {
                "verified": true,
                "world.visibility.query": {
                    "after": {
                        "entities": [{
                            "id": "bath",
                            "screen_area": 0.005815625,
                            "bounds_screen_area": 0.0186224985122681,
                            "occluded": false
                        }]
                    }
                }
            }
        });
        let packet = world_envelope_to_present_packet("world_visibility_query", &envelope, opts());
        assert_eq!(packet["schema"], LSWR_PRESENT_PACKET_SCHEMA);
        assert_eq!(packet["source_schema"], WORLD_TOOL_SCHEMA);
        assert_eq!(packet["verdict"], "verified");
        assert!(packet["reason"].is_null());
        assert_eq!(packet["human_readable"]["visible"], json!(["bath"]));
        assert_eq!(
            packet["provenance"]["verified_to"],
            "onsen_live_root_viewport"
        );
        assert_eq!(packet["machine_payload"]["raw_host_response_present"], true);
        assert_eq!(packet["ingestion"]["allowed"], false);
    }

    #[test]
    fn alpha_zero_reason_survives_without_raw_host_response() {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": false,
            "reason": "pixel_coverage_zero",
            "request": {
                "request_id": "fixture-alpha-zero",
                "world.visibility.query": {"entities": ["bath"]}
            },
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": null,
                "evidence": {
                    "screen_area": 0.0,
                    "bounds_screen_area": 0.0186224985122681,
                    "host_reason": "pixel_coverage_zero"
                }
            }
        });
        let packet = world_envelope_to_present_packet("world_visibility_query", &envelope, opts());
        assert_eq!(packet["verdict"], "not_verified");
        assert_eq!(packet["reason"], "pixel_coverage_zero");
        assert_eq!(
            packet["machine_payload"]["verify"]["evidence"]["host_reason"],
            "pixel_coverage_zero"
        );
        assert_eq!(
            packet["human_readable"]["warnings"],
            json!(["pixel_coverage_zero"])
        );
        assert_eq!(
            packet["machine_payload"]["raw_host_response_present"],
            false
        );
        assert_eq!(
            packet["machine_payload"]["selected_entities"][0]["id"],
            "bath"
        );
        assert_eq!(packet["ingestion"]["allowed"], false);
    }

    #[test]
    fn host_unreachable_remains_not_verified_not_success() {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": false,
            "verified": false,
            "reason": "world_host_unreachable",
            "request": {
                "request_id": "fixture-host-unreachable",
                "world.visibility.query": {"entities": ["bath"]}
            },
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": null,
                "evidence": {"host_reason": "world_host_unreachable"}
            },
            "host_response": null
        });
        let packet = world_envelope_to_present_packet("world_query", &envelope, opts());
        assert_eq!(packet["verdict"], "not_verified");
        assert_eq!(packet["reason"], "world_host_unreachable");
        assert!(
            packet["summary"]
                .as_str()
                .expect("summary")
                .contains("could not verify")
        );
        assert!(packet["provenance"]["verified_to"].is_null());
        assert_eq!(packet["ingestion"]["allowed"], false);
    }

    #[test]
    fn non_loopback_rejection_is_blocked() {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": false,
            "verified": false,
            "reason": "world_host_non_loopback_rejected",
            "request": {
                "request_id": "fixture-blocked-non-loopback",
                "world.visibility.query": {"entities": ["bath"]}
            },
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": null,
                "evidence": {"host_reason": "world_host_non_loopback_rejected"}
            }
        });
        let packet = world_envelope_to_present_packet("world_visibility_query", &envelope, opts());
        assert_eq!(packet["verdict"], "blocked");
        assert_eq!(packet["reason"], "world_host_non_loopback_rejected");
        assert!(
            packet["summary"]
                .as_str()
                .expect("summary")
                .contains("blocked")
        );
        assert_eq!(
            packet["machine_payload"]["source_reason"],
            "world_host_non_loopback_rejected"
        );
        assert_eq!(packet["ingestion"]["allowed"], false);
    }

    #[test]
    fn lower_layer_not_verified_is_not_laundered_by_title() {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": false,
            "reason": "pixel_coverage_zero",
            "request": {"world.visibility.query": {"entities": ["bath"]}},
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": null,
                "evidence": {"host_reason": "pixel_coverage_zero"}
            }
        });
        let packet = world_envelope_to_present_packet("world_visibility_query", &envelope, opts());
        let title = packet["title"].as_str().expect("title");
        assert!(title.contains("unconfirmed"));
        assert!(!title.contains("verified successfully"));
        assert!(!title.contains("not verified"));
        assert!(!title.ends_with(" verified"));
    }

    #[test]
    fn lower_layer_not_verified_drops_verified_to_even_if_present() {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": false,
            "reason": "pixel_coverage_zero",
            "request": {"world.visibility.query": {"entities": ["bath"]}},
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": "onsen_live_root_viewport",
                "evidence": {"host_reason": "pixel_coverage_zero"}
            }
        });
        let packet = world_envelope_to_present_packet("world_visibility_query", &envelope, opts());
        assert!(packet["provenance"]["verified_to"].is_null());
    }

    #[test]
    fn review_artifact_wraps_with_present_dual_encoding() {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": true,
            "request": {"world.visibility.query": {"entities": ["bath"]}},
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": "onsen_live_root_viewport",
                "evidence": {"host_reason": null}
            },
            "host_response": {
                "world.visibility.query": {
                    "after": {
                        "entities": [{"id": "bath", "screen_area": 0.1, "bounds_screen_area": 0.2}]
                    }
                }
            }
        });
        let packet = world_envelope_to_present_packet("world_visibility_query", &envelope, opts());
        let artifact = present_packet_review_artifact(&packet);
        let html = crate::present::build_html(
            crate::present::PresentKind::Html,
            &artifact,
            packet["title"].as_str(),
            Some(&packet),
            Some(&packet["provenance"]),
        );
        let payload = crate::present::extract_ab_payload(&html).expect("payload");
        let region = crate::present::render_region(&html).expect("render region");
        assert_eq!(payload["schema"], LSWR_PRESENT_PACKET_SCHEMA);
        assert_eq!(payload["verdict"], "verified");
        assert!(region.contains("Verified"));
        assert!(region.contains("bath"));
        assert!(region.contains("Ingestion blocked"));
    }

    #[test]
    fn review_args_are_ready_for_present_tool_without_ingestion() {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": true,
            "request": {"world.visibility.query": {"entities": ["bath"]}},
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": "onsen_live_root_viewport",
                "evidence": {"host_reason": null}
            }
        });
        let packet = world_envelope_to_present_packet("world_visibility_query", &envelope, opts());
        let args = present_packet_review_args(&packet, false);
        assert_eq!(args["kind"], "html");
        assert_eq!(args["verify"], false);
        assert_eq!(args["interactive"], false);
        assert_eq!(args["payload"]["schema"], LSWR_PRESENT_PACKET_SCHEMA);
        assert_eq!(
            args["provenance"]["source_schema"],
            LSWR_PRESENT_PACKET_SCHEMA
        );
        assert_eq!(args["payload"]["ingestion"]["allowed"], false);

        let html = crate::present::build_html(
            crate::present::PresentKind::Html,
            args["artifact"].as_str().expect("artifact"),
            args["title"].as_str(),
            Some(&args["payload"]),
            Some(&args["provenance"]),
        );
        let payload = crate::present::extract_ab_payload(&html).expect("payload");
        assert_eq!(payload["ingestion"]["allowed"], false);
    }

    #[test]
    fn review_file_gate_writes_present_artifact_and_lists_it() {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": true,
            "request": {"world.visibility.query": {"entities": ["bath"]}},
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": "onsen_live_root_viewport",
                "evidence": {"host_reason": null}
            },
            "host_response": {
                "world.visibility.query": {
                    "after": {
                        "entities": [{"id": "bath", "screen_area": 0.1, "bounds_screen_area": 0.2}]
                    }
                }
            }
        });
        let packet = world_envelope_to_present_packet("world_visibility_query", &envelope, opts());
        let dir = std::env::temp_dir().join(format!(
            "agent-bridge-lswr-review-file-{}-{}",
            std::process::id(),
            crate::present::now_unix()
        ));
        let file = write_present_packet_review_file(&packet, &dir).expect("write");
        let html = std::fs::read_to_string(&file.artifact_path).expect("read html");
        let payload = crate::present::extract_ab_payload(&html).expect("payload");
        let region = crate::present::render_region(&html).expect("render region");
        assert_eq!(file.id, present_packet_review_id(&packet));
        assert!(file.artifact_path.ends_with(format!("{}.html", file.id)));
        assert!(file.bytes > 0);
        assert!(file.dual_encoding);
        assert_eq!(file.static_render_status, "rendered_static");
        assert_eq!(payload["schema"], LSWR_PRESENT_PACKET_SCHEMA);
        assert!(region.contains("World visibility verified"));
        assert!(region.contains("bath"));

        let listed = crate::present::list_artifacts(&dir, 10, Some("html"));
        assert_eq!(listed.len(), 1);
        assert_eq!(listed[0].id, file.id);
        assert_eq!(listed[0].kind.as_deref(), Some("html"));
        assert!(listed[0].dual_encoding);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn review_artifact_keeps_not_verified_human_surface_honest() {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": false,
            "reason": "pixel_coverage_zero",
            "request": {"world.visibility.query": {"entities": ["bath"]}},
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": null,
                "evidence": {"host_reason": "pixel_coverage_zero"}
            }
        });
        let packet = world_envelope_to_present_packet("world_visibility_query", &envelope, opts());
        let artifact = present_packet_review_artifact(&packet);
        let html = crate::present::build_html(
            crate::present::PresentKind::Html,
            &artifact,
            packet["title"].as_str(),
            Some(&packet),
            Some(&packet["provenance"]),
        );
        let payload = crate::present::extract_ab_payload(&html).expect("payload");
        let region = crate::present::render_region(&html).expect("render region");
        assert_eq!(payload["verdict"], "not_verified");
        assert_eq!(payload["reason"], "pixel_coverage_zero");
        assert!(region.contains("Unconfirmed"));
        assert!(region.contains("pixel_coverage_zero"));
        assert!(region.contains("Ingestion blocked"));
        assert!(!region.contains("verified successfully"));
        assert!(!region.contains("World visibility verified"));
    }

    #[test]
    fn review_artifact_escapes_packet_text() {
        let packet = json!({
            "schema": LSWR_PRESENT_PACKET_SCHEMA,
            "source_schema": WORLD_TOOL_SCHEMA,
            "world_tool": "world_query",
            "verdict": "not_verified",
            "reason": "</script><script>alert(1)</script>",
            "title": "<script>alert(2)</script>",
            "summary": "could not verify <b>host</b>",
            "human_readable": {"visible": [], "changed": [], "warnings": ["</script>"]},
            "machine_payload": {},
            "provenance": {"verified_to": null, "verify_method": "fixture"},
            "ingestion": {"allowed": false, "reason": "step_d_expression_gate_not_accepted"}
        });
        let artifact = present_packet_review_artifact(&packet);
        assert!(!artifact.contains("<script>alert"));
        assert!(artifact.contains("&lt;script&gt;alert"));
        assert!(artifact.contains("&lt;/script&gt;"));
    }
}
