use std::{
    fs::File,
    io::{self, Read},
    path::{Path, PathBuf},
    process::Command,
};

use sha2::{Digest, Sha256};

use crate::BuildIdentity;

pub fn repository_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()
        .unwrap_or_else(|_| Path::new(env!("CARGO_MANIFEST_DIR")).join("../../.."))
}

pub fn embedded_build_identity(executable_sha256: Option<String>) -> BuildIdentity {
    BuildIdentity {
        revision: env!("AB_CODEBASE_A1_BUILD_REVISION").to_string(),
        tree_clean: env!("AB_CODEBASE_A1_BUILD_TREE_CLEAN") == "true",
        profile: env!("AB_CODEBASE_A1_BUILD_PROFILE").to_string(),
        cargo_lock_sha256: env!("AB_CODEBASE_A1_CARGO_LOCK_SHA256").to_string(),
        tracked_source_sha256: env!("AB_CODEBASE_A1_TRACKED_SOURCE_SHA256").to_string(),
        executable_sha256,
        target: env!("AB_CODEBASE_A1_BUILD_TARGET").to_string(),
        opt_level: env!("AB_CODEBASE_A1_BUILD_OPT_LEVEL").to_string(),
        debug_assertions: env!("AB_CODEBASE_A1_BUILD_DEBUG_ASSERTIONS") == "true",
        encoded_rustflags_sha256: env!("AB_CODEBASE_A1_ENCODED_RUSTFLAGS_SHA256").to_string(),
        profile_overrides_present: env!("AB_CODEBASE_A1_PROFILE_OVERRIDES_PRESENT") == "true",
        rustc_version: env!("AB_CODEBASE_A1_RUSTC_VERSION").to_string(),
        build_features: env!("AB_CODEBASE_A1_BUILD_FEATURES").to_string(),
    }
}

pub fn runtime_identity(executable_sha256: String) -> BuildIdentity {
    let repository = repository_dir();
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let mut identity = embedded_build_identity(Some(executable_sha256));
    identity.revision =
        git_text(&repository, &["rev-parse", "HEAD"]).unwrap_or_else(|| "UNBOUND".to_string());
    identity.tree_clean = git_text(
        &repository,
        &["status", "--porcelain=v1", "--untracked-files=all"],
    )
    .is_some_and(|value| value.is_empty());
    identity.cargo_lock_sha256 =
        sha256_file(&manifest_dir.join("Cargo.lock")).unwrap_or_else(|_| "UNBOUND".to_string());
    identity.tracked_source_sha256 =
        sha256_git_index(&repository).unwrap_or_else(|| "UNBOUND".to_string());
    identity
}

pub fn executable_sha256() -> io::Result<String> {
    sha256_file(&std::env::current_exe()?)
}

pub fn sha256_file(path: &Path) -> io::Result<String> {
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
    let mut hasher = Sha256::new();
    hasher.update(output.stdout);
    Some(format!("{:x}", hasher.finalize()))
}
