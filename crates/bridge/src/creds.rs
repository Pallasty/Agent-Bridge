//! Credential loader — read API tokens from a plaintext notebook file at
//! startup and inject them into process env vars.
//!
//! This is the in-binary replacement for the shell wrapper at
//! `~/.local/bin/agent-bridge`. The wrapper still works (and is harmless
//! when env is already set), but a plain `cargo install` overwriting the
//! wrapper used to silently break Tailscale / GitHub auth. With this
//! loader baked in, the binary self-heals after install.
//!
//! Lookup order for each var:
//! 1. Already set in process env → leave alone
//! 2. Found in creds file → set_var (single-threaded startup, safe)
//! 3. Not found → leave unset (the relevant tool errors with "env not set")
//!
//! Creds file path resolution:
//! 1. `$AGENT_BRIDGE_CREDS_FILE` if set
//! 2. `/Media/Ubuntu/Documents/ClaudeCode.txt` (aio2 / Linux primary host)
//! 3. `~/Documents/ClaudeCode.txt` (macOS / cross-host fallback)
//! 4. silently skip
//!
//! Format expected:
//!   `# <Section Name>` (e.g. `# Tailscale API`, `# Github PAT Token`)
//!   key/value lines OR a bare token line follow until the next `#` header.

use std::fs;
use std::path::PathBuf;

const PRIMARY_PATH: &str = "/Media/Ubuntu/Documents/ClaudeCode.txt";

/// Load credentials from the default file and set process env vars for any
/// var that is not already set. Safe to call once at the top of `main()`.
pub fn load_at_startup() {
    let path = match resolve_creds_path() {
        Some(p) => p,
        None => return,
    };
    let content = match fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => return, // file path resolved but unreadable — silent skip
    };

    set_if_unset("TAILSCALE_OAUTH_CLIENT_ID", || {
        extract_kv(&content, "Tailscale API", &["Client ID", "Client id"])
    });
    set_if_unset("TAILSCALE_OAUTH_CLIENT_SECRET", || {
        extract_kv(&content, "Tailscale API", &["Client secret", "Client Secret"])
    });
    set_if_unset("GITHUB_TOKEN", || {
        extract_bare_token(&content, "Github PAT", &["github_pat_", "ghp_", "gho_"])
    });
    set_if_unset("GITLAB_TOKEN", || {
        extract_bare_token(&content, "GitLab PAT", &["glpat-"])
    });
    set_if_unset("NOTION_TOKEN", || {
        extract_bare_token(&content, "Notion API", &["ntn_", "secret_"])
    });
    set_if_unset("BRAVE_SEARCH_TOKEN", || {
        extract_bare_token(&content, "Brave Search API", &["BSA"])
    });
}

fn resolve_creds_path() -> Option<PathBuf> {
    if let Ok(custom) = std::env::var("AGENT_BRIDGE_CREDS_FILE") {
        let p = PathBuf::from(custom);
        if p.is_file() {
            return Some(p);
        }
    }
    let primary = PathBuf::from(PRIMARY_PATH);
    if primary.is_file() {
        return Some(primary);
    }
    if let Ok(home) = std::env::var("HOME") {
        let mac_default = PathBuf::from(home).join("Documents/ClaudeCode.txt");
        if mac_default.is_file() {
            return Some(mac_default);
        }
    }
    None
}

fn set_if_unset<F: FnOnce() -> Option<String>>(var: &str, extractor: F) {
    if std::env::var_os(var).is_some() {
        return;
    }
    if let Some(val) = extractor() {
        // SAFETY: `set_var` is sound here because `load_at_startup` is
        // documented to be called once at the top of `main()` before any
        // worker threads are spawned. No concurrent reads of env are
        // possible at this point.
        unsafe {
            std::env::set_var(var, val);
        }
    }
}

/// Extract `key: value` (or `key = value`) line from within a `# <Section>`
/// block. Returns the trimmed value or None.
fn extract_kv(content: &str, section_marker: &str, keys: &[&str]) -> Option<String> {
    let mut in_section = false;
    for line in content.lines() {
        let trimmed = line.trim_start();
        if let Some(rest) = trimmed.strip_prefix('#') {
            let rest = rest.trim_start();
            in_section = rest.starts_with(section_marker);
            continue;
        }
        if !in_section {
            continue;
        }
        for key in keys {
            if let Some(after) = trimmed.strip_prefix(key) {
                let val = after
                    .trim_start_matches(|c: char| c == ':' || c == '=' || c.is_whitespace())
                    .trim_end();
                if !val.is_empty() {
                    return Some(val.to_string());
                }
            }
        }
    }
    None
}

/// Extract bare-token line (e.g. `github_pat_…`) following a `# <Section>`
/// header. Skips blank lines; first matching prefix wins.
fn extract_bare_token(content: &str, section_marker: &str, prefixes: &[&str]) -> Option<String> {
    let mut in_section = false;
    for line in content.lines() {
        let trimmed = line.trim();
        if let Some(rest) = line.trim_start().strip_prefix('#') {
            let rest = rest.trim_start();
            in_section = rest.starts_with(section_marker);
            continue;
        }
        if !in_section || trimmed.is_empty() {
            continue;
        }
        for p in prefixes {
            if trimmed.starts_with(p) {
                return Some(trimmed.to_string());
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = "\
# Random earlier section
something: ignored

# Tailscale API
Client ID: ts-id-abc
Client secret: ts-secret-xyz

# Github PAT Token
github_pat_11ABCDEF123

# GitLab PAT token
glpat-AbCdEf12345

# Notion API
ntn_NotionTokenABC

# Brave Search API
BSAFakeBraveTokenXYZ
";

    #[test]
    fn extract_tailscale_kv() {
        assert_eq!(
            extract_kv(SAMPLE, "Tailscale API", &["Client ID", "Client id"]),
            Some("ts-id-abc".to_string())
        );
        assert_eq!(
            extract_kv(SAMPLE, "Tailscale API", &["Client secret", "Client Secret"]),
            Some("ts-secret-xyz".to_string())
        );
    }

    #[test]
    fn extract_github_bare_token() {
        assert_eq!(
            extract_bare_token(SAMPLE, "Github PAT", &["github_pat_", "ghp_"]),
            Some("github_pat_11ABCDEF123".to_string())
        );
    }

    #[test]
    fn extract_gitlab_bare_token() {
        assert_eq!(
            extract_bare_token(SAMPLE, "GitLab PAT", &["glpat-"]),
            Some("glpat-AbCdEf12345".to_string())
        );
    }

    #[test]
    fn extract_notion_bare_token() {
        assert_eq!(
            extract_bare_token(SAMPLE, "Notion API", &["ntn_", "secret_"]),
            Some("ntn_NotionTokenABC".to_string())
        );
    }

    #[test]
    fn extract_brave_bare_token() {
        assert_eq!(
            extract_bare_token(SAMPLE, "Brave Search API", &["BSA"]),
            Some("BSAFakeBraveTokenXYZ".to_string())
        );
    }

    #[test]
    fn missing_section_returns_none() {
        assert_eq!(
            extract_kv(SAMPLE, "Nonexistent", &["x"]),
            None
        );
        assert_eq!(
            extract_bare_token(SAMPLE, "Nonexistent", &["x_"]),
            None
        );
    }

    #[test]
    fn section_boundary_respected() {
        // "Random earlier section" doesn't have Tailscale keys
        let just_random = "\
# Random earlier section
Client ID: should-not-match
";
        assert_eq!(
            extract_kv(just_random, "Tailscale API", &["Client ID"]),
            None
        );
    }
}
