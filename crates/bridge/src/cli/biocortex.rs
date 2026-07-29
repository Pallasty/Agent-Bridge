use ab_bridge::biocortex_capability_ledger::{
    build_biocortex_capability_ledger_report_packet, consume_biocortex_capability_ledger,
};
use ab_bridge::biocortex_shadow::{
    biocortex_shadow_digest, supported_benchmarks, BioCortexShadowOptions,
};
use anyhow::Result;
use serde_json::Value;
use std::path::PathBuf;

pub(crate) async fn run_biocortex_shadow_digest(
    checkout: Option<PathBuf>,
    benchmark: String,
    timeout_ms: u64,
    include_raw: bool,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_shadow_digest(BioCortexShadowOptions {
        checkout,
        benchmark,
        timeout_ms,
        include_raw,
        fixture_projection: None,
    })
    .await;

    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex shadow digest");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!("status={}", shadow_json_display(payload.get("status"), "-"));
    println!(
        "benchmark={} example={}",
        shadow_json_display(payload.get("benchmark"), "-"),
        shadow_json_display(payload.get("example"), "-")
    );
    if let Some(path) = payload.get("checkout_path") {
        println!("checkout={}", shadow_json_display(Some(path), "-"));
    }
    if let Some(reason) = payload.get("reason").or_else(|| payload.get("error")) {
        println!("reason={}", shadow_json_display(Some(reason), "-"));
    }

    let summary = payload.get("summary").unwrap_or(&Value::Null);
    println!(
        "verdict={} demonstrated={}",
        shadow_json_display(summary.get("verdict"), "-"),
        shadow_json_display(summary.get("demonstrated"), "false")
    );
    println!(
        "demonstrated_keys={}",
        shadow_json_display(summary.get("demonstrated_keys"), "[]")
    );
    println!(
        "failed_predicates={}",
        shadow_json_display(summary.get("failed_predicates"), "[]")
    );
    println!(
        "open_limitations={}",
        shadow_json_display(summary.get("open_limitations"), "[]")
    );
    println!("supported_benchmarks={}", supported_benchmarks().join(","));

    let boundary = payload.get("boundary").unwrap_or(&Value::Null);
    println!(
        "boundary=shadow_only links_runtime={} mutates_ab_memory={} mutates_retrieval={}",
        shadow_json_display(boundary.get("links_biocortex_into_ab_runtime"), "false"),
        shadow_json_display(boundary.get("mutates_ab_memory"), "false"),
        shadow_json_display(boundary.get("changes_retrieval_vector"), "false")
    );
    Ok(())
}

pub(crate) async fn run_biocortex_capability_ledger_report_packet(
    ledger: &std::path::Path,
    as_json: bool,
) -> Result<()> {
    let ledger_body = std::fs::read_to_string(ledger)
        .map_err(|e| anyhow::anyhow!("read BioCortex capability ledger at {ledger:?}: {e}"))?;
    let summary = consume_biocortex_capability_ledger(&ledger_body);
    let packet = build_biocortex_capability_ledger_report_packet(&summary);

    if as_json {
        println!("{}", serde_json::to_string_pretty(&packet)?);
        return Ok(());
    }

    println!("# BioCortex capability ledger report packet");
    println!("schema={}", packet.schema);
    println!("input_schema={}", packet.input_schema);
    println!(
        "input_schema_version={}",
        packet.input_schema_version.as_deref().unwrap_or("-")
    );
    println!("verdict={}", packet.verdict);
    println!("read_only_confirmed={}", packet.read_only_confirmed);
    println!("downstream_action={}", packet.downstream_action);
    println!("integration_decision={}", packet.integration_decision);
    println!(
        "static_artifact_only={} memory_write_attempted={} retrieval_order_change_attempted={} runtime_authority_observed={}",
        packet.safety.static_artifact_only,
        packet.safety.memory_write_attempted,
        packet.safety.retrieval_order_change_attempted,
        packet.safety.runtime_authority_observed
    );
    println!(
        "executor_enablement_observed={} mcp_tool_registration={} language_generation_observed={} cognition_claim_observed={}",
        packet.safety.executor_enablement_observed,
        packet.safety.mcp_tool_registration,
        packet.safety.language_generation_observed,
        packet.safety.cognition_claim_observed
    );
    Ok(())
}

pub(crate) fn shadow_json_display(value: Option<&Value>, default: &str) -> String {
    match value {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Bool(b)) => b.to_string(),
        Some(Value::Number(n)) => n.to_string(),
        Some(Value::Array(items)) => {
            if items.is_empty() {
                "[]".to_string()
            } else {
                items
                    .iter()
                    .map(|v| shadow_json_display(Some(v), "null"))
                    .collect::<Vec<_>>()
                    .join(",")
            }
        }
        Some(Value::Null) | None => default.to_string(),
        Some(other) => other.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn shadow_json_display_preserves_scalar_rendering() {
        assert_eq!(
            shadow_json_display(Some(&Value::String("ready".into())), "-"),
            "ready"
        );
        assert_eq!(shadow_json_display(Some(&json!(true)), "-"), "true");
        assert_eq!(shadow_json_display(Some(&json!(42)), "-"), "42");
    }

    #[test]
    fn shadow_json_display_flattens_arrays_and_uses_defaults() {
        assert_eq!(
            shadow_json_display(Some(&json!(["a", 2, false])), "-"),
            "a,2,false"
        );
        assert_eq!(shadow_json_display(Some(&json!([])), "-"), "[]");
        assert_eq!(shadow_json_display(Some(&Value::Null), "-"), "-");
        assert_eq!(shadow_json_display(None, "missing"), "missing");
    }
}
