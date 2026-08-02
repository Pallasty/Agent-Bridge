use ab_bridge::avatar_renderer::{
    renderer_payload_from_sources, renderer_payload_from_sources_with_aura_io_path,
    renderer_plan_from_state, select_renderer_state, validate_aura_io_manifest,
    validate_aura_io_sidecar_path, AuraIoReadCapability, RendererScope, RendererSource,
};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::error::Error;
use std::fs;
#[cfg(unix)]
use std::os::unix::fs::symlink;
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

fn scope() -> RendererScope {
    RendererScope {
        project: "agent-bridge".to_string(),
        cwd: Some("/Data/CascadeProjects/agent-bridge".to_string()),
    }
}

fn unique_temp_dir(name: &str) -> Result<PathBuf, Box<dyn Error>> {
    let nanos = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos();
    let path = std::env::temp_dir().join(format!(
        "agent-bridge-avatar-renderer-{name}-{}-{nanos}",
        std::process::id()
    ));
    fs::create_dir_all(&path)?;
    Ok(path)
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

fn write_valid_aura_io_fixture(dir: &Path) -> Result<PathBuf, Box<dyn Error>> {
    let uniform_path = dir.join("a2_working_uniform.bin");
    let digest_path = dir.join("a2_working_digest.json");
    let aura_io_path = dir.join("a2_working_aura_io.json");
    let uniform_bytes = vec![7_u8; 1024];
    let digest_bytes = br#"{"items":[{"title":"working"}]}"#;
    fs::write(&uniform_path, &uniform_bytes)?;
    fs::write(&digest_path, digest_bytes)?;
    let aura_io = json!({
        "schema_version": "lcc.aura_io.v1",
        "renderer_input": {
            "kind": "tfe_uniform_f32x256",
            "contract_version": 1,
            "path": uniform_path,
            "sha256": format!("sha256:{}", sha256_hex(&uniform_bytes)),
            "uniform_len": 256,
            "bin_bytes": 1024,
            "encoding": "little_endian_f32"
        },
        "source_digest": {
            "schema_version": "1.0",
            "item_count": 1,
            "json_path": digest_path,
            "json_sha256": format!("sha256:{}", sha256_hex(digest_bytes))
        },
        "visible_signal_source": "curated_digest_only",
        "shadow_signal_policy": "shadow_only_until_falsified",
        "source_state": {
            "mode": "working",
            "activity_state": "a2-preflight",
            "focus": "face-aura",
            "risk_level": "low"
        }
    });
    fs::write(&aura_io_path, serde_json::to_vec_pretty(&aura_io)?)?;
    Ok(aura_io_path)
}

#[cfg(unix)]
fn make_trusted_directory(path: &Path) -> Result<(), Box<dyn Error>> {
    fs::create_dir_all(path)?;
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))?;
    Ok(())
}

#[cfg(unix)]
fn write_trusted_file(path: &Path, bytes: &[u8]) -> Result<(), Box<dyn Error>> {
    fs::write(path, bytes)?;
    fs::set_permissions(path, fs::Permissions::from_mode(0o600))?;
    Ok(())
}

#[cfg(target_os = "linux")]
fn write_capability_fixture(root: &Path) -> Result<(), Box<dyn Error>> {
    let sidecar_dir = root.join("nested");
    let assets_dir = sidecar_dir.join("assets");
    make_trusted_directory(root)?;
    make_trusted_directory(&sidecar_dir)?;
    make_trusted_directory(&assets_dir)?;

    let uniform_bytes = vec![7_u8; 1024];
    let digest_bytes = br#"{"items":[{"title":"working"}]}"#;
    write_trusted_file(&assets_dir.join("uniform.bin"), &uniform_bytes)?;
    write_trusted_file(&sidecar_dir.join("digest.json"), digest_bytes)?;
    let sidecar = json!({
        "schema_version": "lcc.aura_io.v1",
        "renderer_input": {
            "kind": "tfe_uniform_f32x256",
            "contract_version": 1,
            "path": "assets/uniform.bin",
            "sha256": format!("sha256:{}", sha256_hex(&uniform_bytes)),
            "uniform_len": 256,
            "bin_bytes": 1024,
            "encoding": "little_endian_f32"
        },
        "source_digest": {
            "schema_version": "1.0",
            "item_count": 1,
            "json_path": "digest.json",
            "json_sha256": format!("sha256:{}", sha256_hex(digest_bytes))
        },
        "visible_signal_source": "curated_digest_only",
        "shadow_signal_policy": "shadow_only_until_falsified",
        "source_state": {
            "mode": "working",
            "activity_state": "a2-preflight",
            "focus": "face-aura",
            "risk_level": "low"
        }
    });
    write_trusted_file(
        &sidecar_dir.join("aura.json"),
        &serde_json::to_vec_pretty(&sidecar)?,
    )?;
    Ok(())
}

#[cfg(target_os = "linux")]
fn mutate_capability_sidecar(
    root: &Path,
    mutate: impl FnOnce(&mut serde_json::Value),
) -> Result<(), Box<dyn Error>> {
    let path = root.join("nested/aura.json");
    let mut sidecar: serde_json::Value = serde_json::from_slice(&fs::read(&path)?)?;
    mutate(&mut sidecar);
    write_trusted_file(&path, &serde_json::to_vec_pretty(&sidecar)?)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_absolute_sidecar_before_parse() -> Result<(), Box<dyn Error>> {
    let parent = unique_temp_dir("capability-absolute-sidecar")?;
    let trusted = parent.join("trusted");
    let outside = parent.join("outside");
    make_trusted_directory(&trusted)?;
    fs::create_dir_all(&outside)?;
    let outside_sidecar = outside.join("invalid.json");
    fs::write(&outside_sidecar, b"not-json")?;

    let capability = AuraIoReadCapability::open(&trusted)?;
    let err = capability.parse_entry(&outside_sidecar).unwrap_err();

    assert_eq!(err.code(), "aura_io_sidecar_not_relative");
    fs::remove_dir_all(parent)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_accepts_regular_relative_files_inside_trusted_root(
) -> Result<(), Box<dyn Error>> {
    let parent = unique_temp_dir("capability-valid-snapshot")?;
    let trusted = parent.join("trusted");
    write_capability_fixture(&trusted)?;

    let capability = AuraIoReadCapability::open(&trusted)?;
    let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
    let report = capability.load_snapshot(&entry)?;
    let value = report.to_json_value();

    assert_eq!(value["ok"], true);
    assert_eq!(value["schema_version"], "lcc.aura_io.v1");
    assert_eq!(value["renderer_input_kind"], "tfe_uniform_f32x256");
    assert_eq!(value["uniform_file_sha256_matches"], true);
    assert_eq!(value["digest_file_sha256_matches"], true);
    assert!(value.get("sidecar_path").is_none());
    assert!(value.get("uniform_path").is_none());
    assert!(value.get("digest_path").is_none());

    fs::remove_dir_all(parent)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_parent_sidecar_before_parse() -> Result<(), Box<dyn Error>> {
    let parent = unique_temp_dir("capability-parent-sidecar")?;
    let trusted = parent.join("trusted");
    make_trusted_directory(&trusted)?;
    write_trusted_file(&parent.join("invalid.json"), b"not-json")?;

    let capability = AuraIoReadCapability::open(&trusted)?;
    let err = capability
        .parse_entry(Path::new("../invalid.json"))
        .unwrap_err();

    assert_eq!(err.code(), "aura_io_sidecar_parent_component");
    fs::remove_dir_all(parent)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_empty_uniform_logical_path_by_role() -> Result<(), Box<dyn Error>> {
    let parent = unique_temp_dir("capability-empty-uniform")?;
    let trusted = parent.join("trusted");
    write_capability_fixture(&trusted)?;
    mutate_capability_sidecar(&trusted, |sidecar| {
        sidecar["renderer_input"]["path"] = json!("");
    })?;

    let capability = AuraIoReadCapability::open(&trusted)?;
    let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
    let err = capability.load_snapshot(&entry).unwrap_err();

    assert_eq!(err.code(), "aura_io_uniform_empty");
    fs::remove_dir_all(parent)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_sidecar_logical_path_component_matrix() -> Result<(), Box<dyn Error>>
{
    let parent = unique_temp_dir("capability-sidecar-path-matrix")?;
    let trusted = parent.join("trusted");
    make_trusted_directory(&trusted)?;
    let capability = AuraIoReadCapability::open(&trusted)?;
    let too_long = "a".repeat(4_097);
    let cases = [
        ("", "aura_io_sidecar_empty"),
        (".", "aura_io_sidecar_dot_component"),
        ("../outside", "aura_io_sidecar_parent_component"),
        ("/outside", "aura_io_sidecar_not_relative"),
        ("a//b", "aura_io_sidecar_invalid_component"),
        (too_long.as_str(), "aura_io_sidecar_path_too_long"),
    ];

    for (raw, expected) in cases {
        let err = capability.parse_entry(Path::new(raw)).unwrap_err();
        assert_eq!(err.code(), expected, "raw={raw:?}");
    }
    fs::remove_dir_all(parent)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_uniform_and_digest_logical_path_matrix() -> Result<(), Box<dyn Error>>
{
    let parent = unique_temp_dir("capability-reference-path-matrix")?;
    let trusted = parent.join("trusted");
    write_capability_fixture(&trusted)?;
    let capability = AuraIoReadCapability::open(&trusted)?;
    let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
    let too_long = "a".repeat(4_097);
    let cases = [
        ("", "empty"),
        (".", "dot_component"),
        ("../outside", "parent_component"),
        ("/outside", "not_relative"),
        (too_long.as_str(), "path_too_long"),
    ];

    for role in ["uniform", "digest"] {
        for (raw, reason) in cases.iter().copied() {
            write_capability_fixture(&trusted)?;
            mutate_capability_sidecar(&trusted, |sidecar| {
                if role == "uniform" {
                    sidecar["renderer_input"]["path"] = json!(raw);
                } else {
                    sidecar["source_digest"]["json_path"] = json!(raw);
                }
            })?;
            let err = capability.load_snapshot(&entry).unwrap_err();
            assert_eq!(err.code(), format!("aura_io_{role}_{reason}"));
        }
    }
    fs::remove_dir_all(parent)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_symlinks_and_intermediate_symlinks() -> Result<(), Box<dyn Error>> {
    for (name, swap, expected) in [
        ("sidecar", "nested/aura.json", "aura_io_sidecar_symlink"),
        (
            "uniform",
            "nested/assets/uniform.bin",
            "aura_io_uniform_symlink",
        ),
        ("digest", "nested/digest.json", "aura_io_digest_symlink"),
    ] {
        let parent = unique_temp_dir(&format!("capability-{name}-symlink"))?;
        let trusted = parent.join("trusted");
        write_capability_fixture(&trusted)?;
        let capability = AuraIoReadCapability::open(&trusted)?;
        let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
        let outside = parent.join("outside");
        write_trusted_file(&outside, b"outside")?;
        fs::remove_file(trusted.join(swap))?;
        symlink(&outside, trusted.join(swap))?;

        let err = capability.load_snapshot(&entry).unwrap_err();
        assert_eq!(err.code(), expected);
        fs::remove_dir_all(parent)?;
    }

    let parent = unique_temp_dir("capability-intermediate-symlink")?;
    let trusted = parent.join("trusted");
    write_capability_fixture(&trusted)?;
    let capability = AuraIoReadCapability::open(&trusted)?;
    let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
    let outside = parent.join("outside-assets");
    make_trusted_directory(&outside)?;
    write_trusted_file(&outside.join("uniform.bin"), &[7_u8; 1024])?;
    fs::remove_dir_all(trusted.join("nested/assets"))?;
    symlink(&outside, trusted.join("nested/assets"))?;

    let err = capability.load_snapshot(&entry).unwrap_err();
    assert_eq!(err.code(), "aura_io_directory_safe_open");
    fs::remove_dir_all(parent)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_non_regular_files_for_each_role() -> Result<(), Box<dyn Error>> {
    for (name, swap, expected) in [
        ("sidecar", "nested/aura.json", "aura_io_sidecar_not_regular"),
        (
            "uniform",
            "nested/assets/uniform.bin",
            "aura_io_uniform_not_regular",
        ),
        ("digest", "nested/digest.json", "aura_io_digest_not_regular"),
    ] {
        let parent = unique_temp_dir(&format!("capability-{name}-non-regular"))?;
        let trusted = parent.join("trusted");
        write_capability_fixture(&trusted)?;
        let capability = AuraIoReadCapability::open(&trusted)?;
        let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
        fs::remove_file(trusted.join(swap))?;
        make_trusted_directory(&trusted.join(swap))?;

        let err = capability.load_snapshot(&entry).unwrap_err();
        assert_eq!(err.code(), expected);
        fs::remove_dir_all(parent)?;
    }
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_hard_links_for_each_role() -> Result<(), Box<dyn Error>> {
    for (name, target, expected) in [
        (
            "sidecar",
            "nested/aura.json",
            "aura_io_sidecar_multiple_links",
        ),
        (
            "uniform",
            "nested/assets/uniform.bin",
            "aura_io_uniform_multiple_links",
        ),
        (
            "digest",
            "nested/digest.json",
            "aura_io_digest_multiple_links",
        ),
    ] {
        let parent = unique_temp_dir(&format!("capability-{name}-hard-link"))?;
        let trusted = parent.join("trusted");
        write_capability_fixture(&trusted)?;
        let capability = AuraIoReadCapability::open(&trusted)?;
        let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
        fs::hard_link(trusted.join(target), trusted.join(format!("{name}.alias")))?;

        let err = capability.load_snapshot(&entry).unwrap_err();
        assert_eq!(err.code(), expected);
        fs::remove_dir_all(parent)?;
    }
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_untrusted_writable_root_directory_and_files(
) -> Result<(), Box<dyn Error>> {
    let cases = [
        ("root", "", "aura_io_root_untrusted_writable"),
        (
            "directory",
            "nested/assets",
            "aura_io_directory_untrusted_writable",
        ),
        (
            "sidecar",
            "nested/aura.json",
            "aura_io_sidecar_untrusted_writable",
        ),
        (
            "uniform",
            "nested/assets/uniform.bin",
            "aura_io_uniform_untrusted_writable",
        ),
        (
            "digest",
            "nested/digest.json",
            "aura_io_digest_untrusted_writable",
        ),
    ];
    for (name, target, expected) in cases {
        let parent = unique_temp_dir(&format!("capability-{name}-writable"))?;
        let trusted = parent.join("trusted");
        write_capability_fixture(&trusted)?;
        let capability = AuraIoReadCapability::open(&trusted)?;
        let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
        let target = if target.is_empty() {
            trusted.clone()
        } else {
            trusted.join(target)
        };
        fs::set_permissions(&target, fs::Permissions::from_mode(0o720))?;

        let err = capability.load_snapshot(&entry).unwrap_err();
        assert_eq!(err.code(), expected);
        fs::remove_dir_all(parent)?;
    }
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_size_bounds_before_parse_or_hash() -> Result<(), Box<dyn Error>> {
    for (name, target, bytes, expected) in [
        (
            "sidecar",
            "nested/aura.json",
            vec![b' '; 65_537],
            "aura_io_sidecar_oversize",
        ),
        (
            "uniform-short",
            "nested/assets/uniform.bin",
            vec![7_u8; 1_023],
            "aura_io_uniform_wrong_size",
        ),
        (
            "uniform-long",
            "nested/assets/uniform.bin",
            vec![7_u8; 1_025],
            "aura_io_uniform_wrong_size",
        ),
        (
            "digest",
            "nested/digest.json",
            vec![b' '; 1_048_577],
            "aura_io_digest_oversize",
        ),
    ] {
        let parent = unique_temp_dir(&format!("capability-{name}-bound"))?;
        let trusted = parent.join("trusted");
        write_capability_fixture(&trusted)?;
        let capability = AuraIoReadCapability::open(&trusted)?;
        let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
        write_trusted_file(&trusted.join(target), &bytes)?;

        let err = capability.load_snapshot(&entry).unwrap_err();
        assert_eq!(err.code(), expected);
        fs::remove_dir_all(parent)?;
    }
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_retains_root_across_ambient_path_replacement() -> Result<(), Box<dyn Error>> {
    let parent = unique_temp_dir("capability-root-replacement")?;
    let trusted = parent.join("trusted");
    let retained = parent.join("retained");
    write_capability_fixture(&trusted)?;
    let capability = AuraIoReadCapability::open(&trusted)?;
    let entry = capability.parse_entry(Path::new("nested/aura.json"))?;

    fs::rename(&trusted, &retained)?;
    make_trusted_directory(&trusted)?;
    write_trusted_file(&trusted.join("nested-aura.json"), b"not-json")?;

    let report = capability.load_snapshot(&entry)?;
    assert_eq!(report.to_json_value()["ok"], true);
    fs::remove_dir_all(parent)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_reports_and_errors_are_redacted() -> Result<(), Box<dyn Error>> {
    let parent = unique_temp_dir("capability-redaction")?;
    let trusted = parent.join("trusted-secret-root");
    write_capability_fixture(&trusted)?;
    let capability = AuraIoReadCapability::open(&trusted)?;
    let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
    let report_text = serde_json::to_string(&capability.load_snapshot(&entry)?.to_json_value())?;

    assert!(!report_text.contains(&trusted.display().to_string()));
    assert!(!report_text.contains("assets/uniform.bin"));
    assert!(!report_text.contains("digest.json"));
    assert!(!report_text.contains("working"));

    let secret_outside = parent.join("outside-secret-name.json");
    let error = capability.parse_entry(&secret_outside).unwrap_err();
    assert_eq!(error.to_string(), "aura_io_sidecar_not_relative");
    assert!(!error.to_string().contains("outside-secret-name"));
    fs::remove_dir_all(parent)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_parse_schema_and_hash_failures_by_role() -> Result<(), Box<dyn Error>>
{
    for (name, mutate, expected) in [
        ("schema", 0_u8, "aura_io_sidecar_schema"),
        ("uniform-hash", 1_u8, "aura_io_uniform_hash_mismatch"),
        ("digest-hash", 2_u8, "aura_io_digest_hash_mismatch"),
    ] {
        let parent = unique_temp_dir(&format!("capability-{name}"))?;
        let trusted = parent.join("trusted");
        write_capability_fixture(&trusted)?;
        mutate_capability_sidecar(&trusted, |sidecar| match mutate {
            0 => sidecar["schema_version"] = json!("unexpected"),
            1 => sidecar["renderer_input"]["sha256"] = json!("sha256:00"),
            _ => sidecar["source_digest"]["json_sha256"] = json!("sha256:00"),
        })?;
        let capability = AuraIoReadCapability::open(&trusted)?;
        let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
        let err = capability.load_snapshot(&entry).unwrap_err();
        assert_eq!(err.code(), expected);
        fs::remove_dir_all(parent)?;
    }

    let parent = unique_temp_dir("capability-parse")?;
    let trusted = parent.join("trusted");
    write_capability_fixture(&trusted)?;
    write_trusted_file(&trusted.join("nested/aura.json"), b"not-json")?;
    let capability = AuraIoReadCapability::open(&trusted)?;
    let entry = capability.parse_entry(Path::new("nested/aura.json"))?;
    let err = capability.load_snapshot(&entry).unwrap_err();
    assert_eq!(err.code(), "aura_io_sidecar_parse");
    fs::remove_dir_all(parent)?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[test]
fn aura_io_capability_rejects_unsafe_root_acquisition() -> Result<(), Box<dyn Error>> {
    let parent = unique_temp_dir("capability-root-acquisition")?;
    let trusted = parent.join("trusted");
    let root_link = parent.join("trusted-link");
    make_trusted_directory(&trusted)?;
    symlink(&trusted, &root_link)?;

    let relative = AuraIoReadCapability::open(Path::new("relative-root")).unwrap_err();
    assert_eq!(relative.code(), "aura_io_root_not_absolute");
    let linked = AuraIoReadCapability::open(&root_link).unwrap_err();
    assert_eq!(linked.code(), "aura_io_root_safe_open");

    fs::set_permissions(&trusted, fs::Permissions::from_mode(0o720))?;
    let writable = AuraIoReadCapability::open(&trusted).unwrap_err();
    assert_eq!(writable.code(), "aura_io_root_untrusted_writable");
    fs::remove_dir_all(parent)?;
    Ok(())
}

#[test]
fn aura_io_capability_loader_owns_descriptor_relative_reads_without_legacy_validator() {
    let source = include_str!("../src/avatar_renderer/aura_io_capability.rs");
    let loader = source
        .split("fn load_aura_io_snapshot(")
        .nth(1)
        .and_then(|tail| tail.split("#[cfg(not(target_os = \"linux\"))]").next())
        .expect("linux capability loader");
    assert!(loader.contains("open_aura_io_regular_file"));
    assert!(loader.contains("read_aura_io_bounded"));
    assert!(!loader.contains("validate_aura_io_sidecar_path"));
    assert!(!loader.contains("validate_aura_io_manifest_inner"));
    assert!(!loader.contains("fs::read"));

    let safe_open = source
        .split("fn open_aura_io_regular_file(")
        .nth(1)
        .and_then(|tail| tail.split("fn verify_aura_io_directory").next())
        .expect("descriptor-relative safe open");
    for required in [
        "openat2",
        "ResolveFlags::BENEATH",
        "ResolveFlags::NO_MAGICLINKS",
        "ResolveFlags::NO_SYMLINKS",
        "ResolveFlags::NO_XDEV",
        "OFlags::CLOEXEC",
    ] {
        assert!(safe_open.contains(required), "missing {required}");
    }
}

#[test]
fn projected_avatar_state_wins_over_cross_project_raw_pet_state() {
    let projected = json!({
        "agent_avatar_protocol": 1,
        "project": "agent-bridge",
        "cwd": "/Data/CascadeProjects/agent-bridge",
        "mode": "reviewing",
        "activity_state": "documenting-and-validating"
    });
    let raw_pet = json!({
        "project": "s15-audit",
        "cwd": "/Data/CascadeProjects/biocortex-rs/.claude/worktrees/s15-audit",
        "mode": "handoff",
        "updated_at": "2026-06-01T05:51:29Z"
    });

    let selected = select_renderer_state(&scope(), Some(&projected), Some(&raw_pet));

    assert_eq!(selected.source, RendererSource::ProjectedAvatar);
    assert_eq!(selected.state["mode"], "reviewing");
    assert_eq!(selected.fallback_reason, None);
}

#[test]
fn matching_raw_pet_state_can_be_used_when_projected_state_is_absent() {
    let raw_pet = json!({
        "project": "agent-bridge",
        "cwd": "/Data/CascadeProjects/agent-bridge",
        "mode": "working",
        "activity_state": "implementing",
        "updated_at": "2026-06-01T05:53:20Z"
    });

    let selected = select_renderer_state(&scope(), None, Some(&raw_pet));

    assert_eq!(selected.source, RendererSource::ScopedRawPet);
    assert_eq!(selected.state["mode"], "working");
    assert_eq!(selected.fallback_reason, None);
}

#[test]
fn cross_project_raw_pet_state_falls_back_to_idle() {
    let raw_pet = json!({
        "project": "s15-audit",
        "cwd": "/Data/CascadeProjects/biocortex-rs/.claude/worktrees/s15-audit",
        "mode": "handoff"
    });

    let selected = select_renderer_state(&scope(), None, Some(&raw_pet));

    assert_eq!(selected.source, RendererSource::IdleFallback);
    assert_eq!(selected.state["mode"], "idle");
    assert_eq!(
        selected.fallback_reason.as_deref(),
        Some("raw_pet_scope_mismatch")
    );
}

#[test]
fn renderer_plan_maps_lifecycle_mode_to_calm_track() {
    let state = json!({
        "mode": "verified",
        "activity_state": "documenting",
        "avatar_id": "xiao-shu-v2"
    });

    let plan = renderer_plan_from_state(&state);

    assert_eq!(plan.track, "completion_nod");
    assert_eq!(plan.renderer_token, "xiao_shu::completion_nod::low");
    assert_eq!(plan.fallback_reason, None);
}

#[test]
fn renderer_plan_unknown_mode_uses_idle_fallback() {
    let state = json!({
        "mode": "teleporting",
        "avatar_id": "xiao-shu-v2"
    });

    let plan = renderer_plan_from_state(&state);

    assert_eq!(plan.track, "idle_breathe");
    assert_eq!(plan.renderer_token, "xiao_shu::idle_breathe::low");
    assert_eq!(plan.fallback_reason.as_deref(), Some("unknown_mode"));
}

#[test]
fn renderer_payload_combines_selected_state_and_plan() {
    let projected = json!({
        "agent_avatar_protocol": 1,
        "project": "agent-bridge",
        "cwd": "/Data/CascadeProjects/agent-bridge",
        "mode": "working",
        "avatar_id": "xiao-shu-v2"
    });
    let raw_pet = json!({
        "project": "s15-audit",
        "cwd": "/Data/CascadeProjects/biocortex-rs/.claude/worktrees/s15-audit",
        "mode": "handoff"
    });

    let payload = renderer_payload_from_sources(&scope(), Some(&projected), Some(&raw_pet));

    assert_eq!(payload["surface"], "linux_codex_avatar_renderer_state");
    assert_eq!(payload["read_only"], true);
    assert_eq!(payload["selection"]["source"], "projected_avatar");
    assert_eq!(payload["state"]["mode"], "working");
    assert_eq!(payload["plan"]["track"], "sorting_glow");
    assert_eq!(
        payload["plan"]["renderer_token"],
        "xiao_shu::sorting_glow::medium"
    );
    assert_eq!(payload["safety"]["codex_pet_package_mutation"], false);
    assert_eq!(payload["safety"]["emits_audio"], false);
}

#[test]
fn renderer_payload_validates_aura_io_sidecar_when_path_is_supplied() -> Result<(), Box<dyn Error>>
{
    let dir = unique_temp_dir("payload-aura-io")?;
    let aura_io_path = write_valid_aura_io_fixture(&dir)?;
    let projected = json!({
        "agent_avatar_protocol": 1,
        "project": "agent-bridge",
        "cwd": "/Data/CascadeProjects/agent-bridge",
        "mode": "working",
        "avatar_id": "xiao-shu-v2"
    });

    let payload = renderer_payload_from_sources_with_aura_io_path(
        &scope(),
        Some(&projected),
        None,
        Some(&aura_io_path),
    )?;

    assert_eq!(payload["aura_io"]["surface"], "lcc_aura_io_intake");
    assert_eq!(payload["aura_io"]["ok"], true);
    assert_eq!(payload["aura_io"]["schema_version"], "lcc.aura_io.v1");
    assert_eq!(
        payload["aura_io"]["renderer_input_kind"],
        "tfe_uniform_f32x256"
    );
    assert_eq!(
        payload["aura_io"]["sidecar_path"],
        aura_io_path.display().to_string()
    );
    assert_eq!(payload["aura_io"]["uniform_file_sha256_matches"], true);
    assert_eq!(payload["aura_io"]["digest_file_sha256_matches"], true);
    assert_eq!(payload["aura_io"]["safety"]["shadow_visible_state"], false);

    fs::remove_dir_all(dir)?;
    Ok(())
}

#[test]
fn aura_io_sidecar_validates_renderer_input_hashes() -> Result<(), Box<dyn Error>> {
    let dir = unique_temp_dir("valid-aura-io")?;
    let aura_io_path = write_valid_aura_io_fixture(&dir)?;

    let report = validate_aura_io_sidecar_path(&aura_io_path, true)?;

    assert_eq!(report["ok"], true);
    assert_eq!(report["schema_version"], "lcc.aura_io.v1");
    assert_eq!(report["renderer_input_kind"], "tfe_uniform_f32x256");
    assert_eq!(report["uniform_len"], 256);
    assert_eq!(report["bin_bytes"], 1024);
    assert_eq!(report["uniform_file_sha256_matches"], true);
    assert_eq!(report["digest_file_sha256_matches"], true);
    assert_eq!(report["uniform_sha256"], sha256_hex(&[7_u8; 1024]));
    assert_eq!(
        report["digest_sha256"],
        sha256_hex(br#"{"items":[{"title":"working"}]}"#)
    );
    assert_eq!(report["visible_signal_source"], "curated_digest_only");
    assert_eq!(
        report["shadow_signal_policy"],
        "shadow_only_until_falsified"
    );

    fs::remove_dir_all(dir)?;
    Ok(())
}

#[test]
fn aura_io_manifest_rejects_shadow_driven_visible_source() -> Result<(), Box<dyn Error>> {
    let dir = unique_temp_dir("shadow-aura-io")?;
    let aura_io_path = write_valid_aura_io_fixture(&dir)?;
    let mut aura_io: serde_json::Value = serde_json::from_slice(&fs::read(&aura_io_path)?)?;
    aura_io["visible_signal_source"] = json!("biocortex_state");

    let err = validate_aura_io_manifest(&aura_io, false).unwrap_err();

    assert!(err.to_string().contains("visible_signal_source"));
    fs::remove_dir_all(dir)?;
    Ok(())
}
