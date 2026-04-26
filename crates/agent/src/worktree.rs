//! Git worktree manager — `git worktree {add,list,remove}` wrapper.
//!
//! Not a trait: there is exactly one implementation (git itself), and we
//! follow the project rule of "no abstraction without ≥2 implementations".

use ab_core::{Error, Result};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use tokio::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Worktree {
    pub path: String,
    pub branch: Option<String>,
    pub head: Option<String>,
    pub bare: bool,
    pub locked: bool,
}

#[derive(Clone)]
pub struct GitWorktreeManager {
    repo: PathBuf,
}

impl GitWorktreeManager {
    pub fn new(repo: impl Into<PathBuf>) -> Self {
        Self { repo: repo.into() }
    }

    /// `git worktree list --porcelain`
    pub async fn list(&self) -> Result<Vec<Worktree>> {
        let out = self.git(&["worktree", "list", "--porcelain"]).await?;
        Ok(parse_porcelain(&out))
    }

    /// `git worktree add -b <branch> <path> [base]`. If `base` is None, falls
    /// back to the repository's HEAD.
    pub async fn add(
        &self,
        path: &Path,
        branch: &str,
        base: Option<&str>,
    ) -> Result<Worktree> {
        let mut args: Vec<String> = vec![
            "worktree".into(), "add".into(),
            "-b".into(), branch.into(),
            path.display().to_string(),
        ];
        if let Some(b) = base {
            args.push(b.to_string());
        }
        let args_ref: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
        self.git(&args_ref).await?;

        // Re-fetch the entry from `worktree list` to get the resolved metadata.
        let all = self.list().await?;
        let want = path
            .canonicalize()
            .unwrap_or_else(|_| path.to_path_buf())
            .display()
            .to_string();
        Ok(all
            .into_iter()
            .find(|w| w.path == want || w.path == path.display().to_string())
            .unwrap_or(Worktree {
                path: path.display().to_string(),
                branch: Some(branch.to_string()),
                head: None,
                bare: false,
                locked: false,
            }))
    }

    /// `git worktree remove [-f] <path>`. Forces removal if `force` is true.
    pub async fn remove(&self, path: &Path, force: bool) -> Result<()> {
        let mut args: Vec<&str> = vec!["worktree", "remove"];
        if force { args.push("-f"); }
        let path_s = path.display().to_string();
        args.push(&path_s);
        self.git(&args).await?;
        Ok(())
    }

    async fn git(&self, args: &[&str]) -> Result<String> {
        let out = Command::new("git")
            .args(args)
            .current_dir(&self.repo)
            .output()
            .await
            .map_err(|e| Error::Backend(format!("spawn git: {e}")))?;
        if !out.status.success() {
            return Err(Error::Backend(format!(
                "git {} (in {}): {}",
                args.join(" "),
                self.repo.display(),
                String::from_utf8_lossy(&out.stderr).trim()
            )));
        }
        Ok(String::from_utf8_lossy(&out.stdout).into_owned())
    }
}

/// Parse `git worktree list --porcelain` output. Records are blank-line
/// separated; each begins with `worktree <path>` and may include `HEAD <sha>`,
/// `branch <ref>`, `bare`, `locked`, `prunable`.
fn parse_porcelain(text: &str) -> Vec<Worktree> {
    let mut out = Vec::new();
    let mut cur: Option<Worktree> = None;

    for line in text.lines() {
        let line = line.trim_end();
        if line.is_empty() {
            if let Some(w) = cur.take() {
                out.push(w);
            }
            continue;
        }
        let (key, rest) = line.split_once(' ').unwrap_or((line, ""));
        match key {
            "worktree" => {
                if let Some(w) = cur.take() {
                    out.push(w);
                }
                cur = Some(Worktree {
                    path: rest.to_string(),
                    branch: None,
                    head: None,
                    bare: false,
                    locked: false,
                });
            }
            "HEAD" => {
                if let Some(w) = cur.as_mut() { w.head = Some(rest.to_string()); }
            }
            "branch" => {
                if let Some(w) = cur.as_mut() { w.branch = Some(rest.to_string()); }
            }
            "bare" => {
                if let Some(w) = cur.as_mut() { w.bare = true; }
            }
            "locked" => {
                if let Some(w) = cur.as_mut() { w.locked = true; }
            }
            _ => {}
        }
    }
    if let Some(w) = cur.take() {
        out.push(w);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_basic_porcelain() {
        let txt = "\
worktree /tmp/main
HEAD abc123
branch refs/heads/main

worktree /tmp/feat-x
HEAD def456
branch refs/heads/feat-x
locked

worktree /tmp/bare
bare
";
        let v = parse_porcelain(txt);
        assert_eq!(v.len(), 3);
        assert_eq!(v[0].path, "/tmp/main");
        assert_eq!(v[0].branch.as_deref(), Some("refs/heads/main"));
        assert!(v[1].locked);
        assert!(v[2].bare);
    }
}
