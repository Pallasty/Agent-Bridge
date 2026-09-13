//! Completed Avatar result presentation. No acquisition or execution authority.
use ab_bridge::avatar_asset_audit::{FocusFollowAssetContract, SpriteAssetAudit};
use ab_bridge::avatar_asset_compile::SpriteCompileReport;
use anyhow::Result;
use serde_json::Value;

pub(crate) fn render_sprite_asset_audit(report: &SpriteAssetAudit, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&report)?);
    } else {
        println!(
            "Xiao Shu sprite asset: {} ({}, {}x{}, expected {}x{})",
            if report.accepted {
                "accepted"
            } else {
                "rejected"
            },
            report.color_type,
            report.width,
            report.height,
            report.expected_width,
            report.expected_height,
        );
        for failure in &report.failures {
            println!("- {failure}");
        }
    }
    Ok(())
}

pub(crate) fn render_sprite_asset_contract(
    contract: &FocusFollowAssetContract,
    as_json: bool,
) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&contract)?);
    } else {
        println!(
            "Xiao Shu focus-follow assets: {}/{} accepted, {} missing, {} rejected",
            contract.accepted,
            contract.assets.len(),
            contract.missing,
            contract.rejected,
        );
        for item in &contract.assets {
            println!("- {}: {} ({})", item.spec.action, item.status, item.path);
        }
    }
    Ok(())
}

pub(crate) fn render_sprite_asset_compile(
    report: &SpriteCompileReport,
    as_json: bool,
) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&report)?);
    } else {
        println!(
            "Xiao Shu sprite compile: {} {}x{} -> {}x{} ({} frames)",
            if report.executed {
                "written"
            } else {
                "preview"
            },
            report.source_width,
            report.source_height,
            report.output_width,
            report.output_height,
            report.frame_count,
        );
        println!("output: {}", report.output);
    }
    Ok(())
}

pub(crate) fn render_focus_follow_plan(plan: &Value, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&plan)?);
    } else {
        println!(
            "Xiao Shu focus-follow plan: {}",
            plan.get("status")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("unknown")
        );
        println!("  read_only: true");
        println!("  movement_authorized: false");
        if let Some(edge) = plan
            .pointer("/docking/edge")
            .and_then(serde_json::Value::as_str)
        {
            println!("  proposed_edge: {}", edge);
        }
        if let Some(points) = plan
            .pointer("/path/point_count")
            .and_then(serde_json::Value::as_u64)
        {
            println!("  path_points: {}", points);
        }
    }
    Ok(())
}

pub(crate) fn render_focus_follow_recommendation(
    recommendation: &Value,
    as_json: bool,
) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&recommendation)?);
    } else {
        println!(
            "Xiao Shu focus-follow recommendation: {} ({})",
            recommendation
                .get("decision")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("suppress"),
            recommendation
                .get("reason")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("unknown")
        );
        println!("  read_only: true");
        println!("  dispatch: none");
    }
    Ok(())
}

pub(crate) fn render_focus_follow_prompt(prompt: &Value, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&prompt)?);
    } else {
        println!(
            "Xiao Shu focus-follow prompt: {}",
            prompt
                .get("status")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("unknown")
        );
        println!("  emits_audio: false");
        println!("  executes_recommendation: false");
    }
    Ok(())
}

pub(crate) fn render_focus_follow_action(action: &Value, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&action)?);
    } else {
        println!(
            "Xiao Shu focus-follow action: {}",
            action
                .get("status")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("unknown")
        );
        println!(
            "  ready: {}",
            action
                .get("ready")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(false)
        );
        println!(
            "  executed_steps: {}",
            action
                .get("executed_steps")
                .and_then(serde_json::Value::as_u64)
                .unwrap_or(0)
        );
        println!("  moves_pointer: false");
        println!("  changes_focus: false");
    }
    Ok(())
}

pub(crate) fn render_focus_observer_json(payload: &serde_json::Value, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(payload)?);
    } else {
        println!(
            "Xiao Shu bounded focus observer: {}",
            payload
                .get("status")
                .and_then(serde_json::Value::as_str)
                .unwrap_or("unknown")
        );
        if let Some(reason) = payload
            .get("terminal_reason")
            .and_then(serde_json::Value::as_str)
        {
            println!("  terminal_reason: {reason}");
        }
        println!(
            "  attempts: {}",
            payload
                .get("attempt_count")
                .and_then(serde_json::Value::as_u64)
                .unwrap_or(0)
        );
        println!("  moves_pointer: false");
        println!("  changes_focus: false");
        println!("  emits_input: false");
    }
    Ok(())
}
