use std::{
    env,
    fs::File,
    io::{self, Read},
    path::{Path, PathBuf},
    process::Command,
};

use sha2::{Digest, Sha256};

fn main() {
    let manifest_dir = env::var_os("CARGO_MANIFEST_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    let repository = manifest_dir
        .join("../../..")
        .canonicalize()
        .unwrap_or_else(|_| manifest_dir.join("../../.."));
    let lock_path = manifest_dir.join("Cargo.lock");

    let tracked_paths = git_tracked_paths(&repository).unwrap_or_default();
    let revision = git_text(&repository, &["rev-parse", "HEAD"])
        .filter(|value| is_lower_hex(value, 40))
        .unwrap_or_else(|| "UNBOUND".to_string());
    let tree_clean = git_text(
        &repository,
        &["status", "--porcelain=v1", "--untracked-files=all"],
    )
    .is_some_and(|value| value.is_empty());
    let profile = env::var("PROFILE").unwrap_or_else(|_| "UNBOUND".to_string());
    let lock_sha256 = sha256_file(&lock_path).unwrap_or_else(|_| "UNBOUND".to_string());
    let tracked_source_sha256 =
        sha256_git_index(&repository).unwrap_or_else(|| "UNBOUND".to_string());
    let target = env::var("TARGET").unwrap_or_else(|_| "UNBOUND".to_string());
    let opt_level = env::var("OPT_LEVEL").unwrap_or_else(|_| "UNBOUND".to_string());
    let debug_assertions = env::var("DEBUG").is_ok_and(|value| value == "true");
    let encoded_rustflags = env::var("CARGO_ENCODED_RUSTFLAGS").unwrap_or_default();
    let encoded_rustflags_sha256 = sha256_bytes(encoded_rustflags.as_bytes());
    let profile_overrides_present = env::vars().any(|(key, value)| {
        (!value.is_empty() && key.starts_with("CARGO_PROFILE_RELEASE_"))
            || (!value.is_empty()
                && matches!(
                    key.as_str(),
                    "RUSTFLAGS"
                        | "CARGO_BUILD_RUSTFLAGS"
                        | "RUSTC_WRAPPER"
                        | "RUSTC_WORKSPACE_WRAPPER"
                ))
    });
    let rustc_version = rustc_version().unwrap_or_else(|| "UNBOUND".to_string());

    println!("cargo:rustc-env=AB_ARROW_A0_BUILD_REVISION={revision}");
    println!("cargo:rustc-env=AB_ARROW_A0_BUILD_TREE_CLEAN={tree_clean}");
    println!("cargo:rustc-env=AB_ARROW_A0_BUILD_PROFILE={profile}");
    println!("cargo:rustc-env=AB_ARROW_A0_CARGO_LOCK_SHA256={lock_sha256}");
    println!("cargo:rustc-env=AB_ARROW_A0_TRACKED_SOURCE_SHA256={tracked_source_sha256}");
    println!("cargo:rustc-env=AB_ARROW_A0_BUILD_TARGET={target}");
    println!("cargo:rustc-env=AB_ARROW_A0_BUILD_OPT_LEVEL={opt_level}");
    println!("cargo:rustc-env=AB_ARROW_A0_BUILD_DEBUG_ASSERTIONS={debug_assertions}");
    println!("cargo:rustc-env=AB_ARROW_A0_ENCODED_RUSTFLAGS_SHA256={encoded_rustflags_sha256}");
    println!("cargo:rustc-env=AB_ARROW_A0_PROFILE_OVERRIDES_PRESENT={profile_overrides_present}");
    println!("cargo:rustc-env=AB_ARROW_A0_RUSTC_VERSION={rustc_version}");
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed={}", lock_path.display());
    println!("cargo:rerun-if-env-changed=PROFILE");
    println!("cargo:rerun-if-env-changed=OPT_LEVEL");
    println!("cargo:rerun-if-env-changed=DEBUG");
    println!("cargo:rerun-if-env-changed=CARGO_ENCODED_RUSTFLAGS");
    println!("cargo:rerun-if-env-changed=RUSTFLAGS");
    println!("cargo:rerun-if-env-changed=CARGO_BUILD_RUSTFLAGS");
    println!("cargo:rerun-if-env-changed=RUSTC");
    println!("cargo:rerun-if-env-changed=RUSTC_WRAPPER");
    println!("cargo:rerun-if-env-changed=RUSTC_WORKSPACE_WRAPPER");
    for profile_key in [
        "CARGO_PROFILE_RELEASE_CODEGEN_UNITS",
        "CARGO_PROFILE_RELEASE_DEBUG",
        "CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS",
        "CARGO_PROFILE_RELEASE_INCREMENTAL",
        "CARGO_PROFILE_RELEASE_LTO",
        "CARGO_PROFILE_RELEASE_OPT_LEVEL",
        "CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS",
        "CARGO_PROFILE_RELEASE_PANIC",
        "CARGO_PROFILE_RELEASE_RPATH",
        "CARGO_PROFILE_RELEASE_SPLIT_DEBUGINFO",
        "CARGO_PROFILE_RELEASE_STRIP",
    ] {
        println!("cargo:rerun-if-env-changed={profile_key}");
    }
    for path in &tracked_paths {
        println!("cargo:rerun-if-changed={}", repository.join(path).display());
    }
    emit_git_rerun_path(&repository, "HEAD");
    emit_git_rerun_path(&repository, "index");
}

fn git_text(repository: &Path, args: &[&str]) -> Option<String> {
    let output = Command::new("git")
        .arg("-C")
        .arg(repository)
        .args(args)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    String::from_utf8(output.stdout)
        .ok()
        .map(|value| value.trim().to_string())
}

fn git_tracked_paths(repository: &Path) -> Option<Vec<PathBuf>> {
    let output = Command::new("git")
        .arg("-C")
        .arg(repository)
        .args(["ls-files", "-z"])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    output
        .stdout
        .split(|byte| *byte == 0)
        .filter(|path| !path.is_empty())
        .map(|path| String::from_utf8(path.to_vec()).ok().map(PathBuf::from))
        .collect()
}

fn emit_git_rerun_path(repository: &Path, name: &str) {
    let Some(raw_path) = git_text(repository, &["rev-parse", "--git-path", name]) else {
        return;
    };
    let path = PathBuf::from(raw_path);
    let resolved = if path.is_absolute() {
        path
    } else {
        repository.join(path)
    };
    println!("cargo:rerun-if-changed={}", resolved.display());
}

fn sha256_file(path: &Path) -> io::Result<String> {
    let mut file = File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn sha256_git_index(repository: &Path) -> Option<String> {
    let output = Command::new("git")
        .arg("-C")
        .arg(repository)
        .args(["ls-files", "-s", "-z"])
        .output()
        .ok()?;
    if !output.status.success() || output.stdout.is_empty() {
        return None;
    }
    Some(sha256_bytes(&output.stdout))
}

fn sha256_bytes(value: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(value);
    format!("{:x}", hasher.finalize())
}

fn rustc_version() -> Option<String> {
    let rustc = env::var_os("RUSTC").unwrap_or_else(|| "rustc".into());
    let output = Command::new(rustc).arg("--version").output().ok()?;
    if !output.status.success() {
        return None;
    }
    String::from_utf8(output.stdout)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn is_lower_hex(value: &str, expected_len: usize) -> bool {
    value.len() == expected_len
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}
