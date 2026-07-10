use std::env;
use std::path::PathBuf;
use std::process::Command;

fn git_output(args: &[&str]) -> Option<String> {
    let output = Command::new("git")
        .args(args)
        .current_dir(env::var_os("CARGO_MANIFEST_DIR")?)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let value = String::from_utf8(output.stdout).ok()?;
    let value = value.trim();
    (!value.is_empty()).then(|| value.to_string())
}

fn identity_value(env_name: &str, git_args: &[&str]) -> String {
    env::var(env_name)
        .ok()
        .filter(|value| !value.trim().is_empty())
        .map(|value| value.trim().to_string())
        .or_else(|| git_output(git_args))
        .unwrap_or_else(|| "unknown".to_string())
}

fn watch_git_head() {
    let Some(head_path) = git_output(&["rev-parse", "--git-path", "HEAD"]) else {
        return;
    };
    println!("cargo:rerun-if-changed={head_path}");

    let Ok(head) = std::fs::read_to_string(&head_path) else {
        return;
    };
    let Some(reference) = head.trim().strip_prefix("ref: ") else {
        return;
    };
    if let Some(reference_path) = git_output(&["rev-parse", "--git-path", reference]) {
        println!(
            "cargo:rerun-if-changed={}",
            PathBuf::from(reference_path).display()
        );
    }
}

fn main() {
    println!("cargo:rerun-if-env-changed=AGENT_BRIDGE_BUILD_SHA");
    println!("cargo:rerun-if-env-changed=AGENT_BRIDGE_BUILD_DESCRIBE");
    watch_git_head();

    let sha = identity_value(
        "AGENT_BRIDGE_BUILD_SHA",
        &["rev-parse", "--short=12", "HEAD"],
    );
    let describe = identity_value(
        "AGENT_BRIDGE_BUILD_DESCRIBE",
        &["describe", "--tags", "--always", "--dirty"],
    );
    println!("cargo:rustc-env=AGENT_BRIDGE_BUILD_SHA={sha}");
    println!("cargo:rustc-env=AGENT_BRIDGE_BUILD_DESCRIBE={describe}");
}
