//! Response projection for the existing capabilities tool.
//! This changes response fields only; it does not skip probes or confer authority.
use serde_json::{json, Value};

pub const SECTION_NAMES: &[&str] = &[
    "mcp",
    "mobile",
    "terminal",
    "browser",
    "embodiment_p4",
    "memory",
    "agent_spawn",
    "hooks",
    "security",
    "oz_run_tools",
    "version",
    "build",
];
const REQUIRED: &[&str] = &["security", "version", "build"];

fn error(code: &str, detail: &str) -> Value {
    json!({"error": {"code":code,"detail":detail},
           "available_sections": SECTION_NAMES,
           "next_call":{"tool":"capabilities","arguments":{"compact":true}}})
}

/// Validate the opt-in before the existing tool performs any diagnostics.
/// An omitted selector preserves the legacy response verbatim.
pub fn parse_sections(args: &Value) -> Result<Option<Vec<String>>, Value> {
    let Some(value) = args.get("sections") else {
        return Ok(None);
    };
    let Some(values) = value.as_array().filter(|values| !values.is_empty()) else {
        return Err(error(
            "invalid_capability_sections",
            "sections must be a non-empty array of section names",
        ));
    };
    let mut names = Vec::new();
    for value in values {
        let Some(name) = value.as_str().filter(|name| SECTION_NAMES.contains(name)) else {
            return Err(error(
                "unknown_capability_section",
                "every sections entry must be one of available_sections",
            ));
        };
        if !names.iter().any(|existing| existing == name) {
            names.push(name.to_string());
        }
    }
    Ok(Some(names))
}

/// Preserve selected values exactly, including false, null, and nested caveats.
/// Security stays complete, even for a browser-only or version-only query.
pub fn project_report(
    report: Value,
    selection: Option<&[String]>,
    compact: bool,
    include_instinct_sessions: bool,
) -> Result<Value, Value> {
    let Some(selection) = selection else {
        return Ok(report);
    };
    let Some(source) = report.as_object() else {
        return Err(error(
            "capability_report_invalid",
            "capabilities did not produce an object",
        ));
    };
    for name in selection
        .iter()
        .map(String::as_str)
        .chain(REQUIRED.iter().copied())
    {
        if !source.contains_key(name) {
            return Err(error(
                "capability_section_missing",
                &format!("requested or required section is missing from the report: {name}"),
            ));
        }
    }
    let mut result = serde_json::Map::new();
    let mut omitted = Vec::new();
    for (name, value) in source {
        if REQUIRED.contains(&name.as_str()) || selection.contains(name) {
            result.insert(name.clone(), value.clone());
        } else {
            omitted.push(name.clone());
        }
    }
    result.insert("_selection".into(), json!({
        "schema":"agent_bridge.capabilities_selection.v0",
        "requested_sections":selection,
        "always_included":REQUIRED,
        "available_sections":SECTION_NAMES,
        "omitted_sections":omitted,
        "omission_scope":"response_fields_only",
        "diagnostics":"all existing probes still run; omitted does not mean unavailable or unchecked",
        "follow_up":{
            "omitted_sections":{"tool":"capabilities","arguments":{
                "sections":omitted,"compact":compact,"include_instinct_sessions":include_instinct_sessions
            }},
            "full_response":{"tool":"capabilities","arguments":{
                "compact":compact,"include_instinct_sessions":include_instinct_sessions
            }}
        },
        "nested_omissions":"compact section values retain their own omission and detail hints; selecting a section does not expand them",
        "authority":"report projection only; existing security restrictions and runtime checks remain applicable"
    }));
    // No empty sections request is advertised when the caller selects everything.
    if omitted.is_empty() {
        result["_selection"]["follow_up"]["omitted_sections"] = Value::Null;
    }
    Ok(Value::Object(result))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn report() -> Value {
        json!({
            "browser":{"available":true,"backend":"chromium-cdp"},
            "memory":{"available":false},"mobile":null,
            "security":{"browser":false,"invocation_lease":{"mode":"hold","production_grants_authority":false}},
            "version":"0.14.0","build":{"git_sha":"example"}
        })
    }
    #[test]
    fn legacy_response_is_unchanged() {
        let source = report();
        assert_eq!(
            project_report(
                source.clone(),
                parse_sections(&json!({})).unwrap().as_deref(),
                true,
                false
            )
            .unwrap(),
            source
        );
    }
    #[test]
    fn selection_keeps_full_security_and_reports_omissions() {
        let source = report();
        let selection = parse_sections(&json!({"sections":["browser"]})).unwrap();
        let projected = project_report(source.clone(), selection.as_deref(), true, false).unwrap();
        assert_eq!(projected["browser"], source["browser"]);
        assert_eq!(projected["security"], source["security"]);
        assert_eq!(projected["security"]["browser"], false);
        assert!(projected.get("memory").is_none());
        assert!(projected["_selection"]["omitted_sections"]
            .as_array()
            .unwrap()
            .contains(&json!("memory")));
        assert_eq!(
            projected["_selection"]["omission_scope"],
            "response_fields_only"
        );
    }
    #[test]
    fn unknown_empty_or_wrong_type_is_rejected() {
        for args in [
            json!({"sections":["browzer"]}),
            json!({"sections":[]}),
            json!({"sections":"browser"}),
            json!({"sections":[4]}),
            json!({"sections":null}),
        ] {
            assert!(parse_sections(&args).is_err());
        }
    }
    #[test]
    fn selected_false_and_null_are_preserved() {
        let selection = parse_sections(&json!({"sections":["memory","mobile"]})).unwrap();
        let projected = project_report(report(), selection.as_deref(), true, false).unwrap();
        assert_eq!(projected["memory"]["available"], false);
        assert!(projected.as_object().unwrap().contains_key("mobile"));
        assert!(projected["mobile"].is_null());
    }
    #[test]
    fn missing_requested_or_required_values_are_errors() {
        let selection = parse_sections(&json!({"sections":["hooks"]})).unwrap();
        assert!(project_report(report(), selection.as_deref(), true, false).is_err());
        let selection = parse_sections(&json!({"sections":["browser"]})).unwrap();
        let mut source = report();
        source.as_object_mut().unwrap().remove("security");
        assert!(project_report(source, selection.as_deref(), true, false).is_err());
    }
    #[test]
    fn duplicate_names_do_not_duplicate_output() {
        assert_eq!(
            parse_sections(&json!({"sections":["browser","browser"]})).unwrap(),
            Some(vec!["browser".into()])
        );
    }
    #[test]
    fn all_sections_has_no_invalid_followup() {
        let source = report();
        let selection = source
            .as_object()
            .unwrap()
            .keys()
            .cloned()
            .collect::<Vec<_>>();
        let projected = project_report(source, Some(&selection), true, false).unwrap();
        assert_eq!(projected["_selection"]["omitted_sections"], json!([]));
        assert!(projected["_selection"]["follow_up"]["omitted_sections"].is_null());
    }
    #[test]
    fn followup_preserves_detail_preferences() {
        let selection = parse_sections(&json!({"sections":["browser"]})).unwrap();
        let projected = project_report(report(), selection.as_deref(), false, true).unwrap();
        assert_eq!(
            projected["_selection"]["follow_up"]["full_response"]["arguments"],
            json!({"compact":false,"include_instinct_sessions":true})
        );
    }

    #[test]
    fn returned_followup_reconstructs_the_same_snapshot_exactly() {
        let mut source = report();
        source["hooks"] = json!({"per_session_omitted":true,"per_session_count":3});
        let selected = parse_sections(&json!({"sections":["browser"]})).unwrap();
        let mut first = project_report(source.clone(), selected.as_deref(), true, false).unwrap();
        let args = &first["_selection"]["follow_up"]["omitted_sections"]["arguments"];
        let selected = parse_sections(args).unwrap();
        let mut second = project_report(source.clone(), selected.as_deref(), true, false).unwrap();
        first.as_object_mut().unwrap().remove("_selection");
        second.as_object_mut().unwrap().remove("_selection");
        first
            .as_object_mut()
            .unwrap()
            .extend(second.as_object().unwrap().clone());
        assert_eq!(first, source);
    }
}
