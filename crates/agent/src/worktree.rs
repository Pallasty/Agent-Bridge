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
    pub async fn add(&self, path: &Path, branch: &str, base: Option<&str>) -> Result<Worktree> {
        let mut args: Vec<String> = vec![
            "worktree".into(),
            "add".into(),
            "-b".into(),
            branch.into(),
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
    ///
    /// Before delegating to git, applies two guards that hold even under
    /// `force=true` (which otherwise hands `git worktree remove -f` an
    /// unchecked path):
    ///   1. path-safety — refuse the filesystem root, `$HOME`, the main repo
    ///      worktree, or an empty path (catastrophic targets git would happily
    ///      clobber under force);
    ///   2. registration — the path must be a worktree of *this* repo, not an
    ///      arbitrary directory.
    /// The dirty-tree clobber semantics of `force` are unchanged — that is
    /// git's own contract. See OB-1 in docs/design/ORCA_BORROW_PLAN_2026_06_19.md.
    pub async fn remove(&self, path: &Path, force: bool) -> Result<()> {
        let target = path.canonicalize().unwrap_or_else(|_| path.to_path_buf());
        let repo_root = self
            .repo
            .canonicalize()
            .unwrap_or_else(|_| self.repo.clone());
        let home = std::env::var_os("HOME").map(|h| {
            let h = PathBuf::from(h);
            h.canonicalize().unwrap_or(h)
        });
        if let Some(reason) = unsafe_removal_reason(&target, &repo_root, home.as_deref()) {
            return Err(Error::InvalidArgument(reason));
        }
        let listed = self.list().await?;
        if !registered_match(&target, path, &listed) {
            return Err(Error::InvalidArgument(format!(
                "refusing to remove '{}': not a registered worktree of {}",
                path.display(),
                self.repo.display()
            )));
        }

        let mut args: Vec<&str> = vec!["worktree", "remove"];
        if force {
            args.push("-f");
        }
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
                if let Some(w) = cur.as_mut() {
                    w.head = Some(rest.to_string());
                }
            }
            "branch" => {
                if let Some(w) = cur.as_mut() {
                    w.branch = Some(rest.to_string());
                }
            }
            "bare" => {
                if let Some(w) = cur.as_mut() {
                    w.bare = true;
                }
            }
            "locked" => {
                if let Some(w) = cur.as_mut() {
                    w.locked = true;
                }
            }
            _ => {}
        }
    }
    if let Some(w) = cur.take() {
        out.push(w);
    }
    out
}

/// Pure path-safety classifier for worktree removal. Given already-resolved
/// paths, returns `Some(reason)` if removing `target` must be refused outright
/// — independent of git state and regardless of `force`. Guards against
/// catastrophic targets (filesystem root, `$HOME`, the main repo worktree, an
/// empty path) that `git worktree remove -f` would otherwise clobber.
fn unsafe_removal_reason(target: &Path, repo_root: &Path, home: Option<&Path>) -> Option<String> {
    if target.as_os_str().is_empty() {
        return Some("refusing to remove worktree: empty path".to_string());
    }
    if target.parent().is_none() {
        return Some(format!(
            "refusing to remove worktree at filesystem root: {}",
            target.display()
        ));
    }
    if target == repo_root {
        return Some(format!(
            "refusing to remove the main repository worktree: {}",
            target.display()
        ));
    }
    if let Some(h) = home {
        if target == h {
            return Some(format!(
                "refusing to remove worktree at home directory: {}",
                target.display()
            ));
        }
    }
    None
}

/// Pure check: does `target` (canonicalized) or `raw` (un-resolved, as passed)
/// correspond to an entry in this repo's `git worktree list`? Matching the raw
/// path too covers prunable worktrees whose directory no longer resolves. A
/// path absent from the list is not a worktree of this repo. Mirrors the
/// resolved-or-raw matching `add` uses to re-find a freshly created worktree.
fn registered_match(target: &Path, raw: &Path, listed: &[Worktree]) -> bool {
    let raw_s = raw.display().to_string();
    let target_s = target.display().to_string();
    listed.iter().any(|w| w.path == raw_s || w.path == target_s)
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

    fn wt(path: &str) -> Worktree {
        Worktree {
            path: path.to_string(),
            branch: None,
            head: None,
            bare: false,
            locked: false,
        }
    }

    #[test]
    fn refuses_filesystem_root() {
        let repo = Path::new("/repo/main");
        assert!(unsafe_removal_reason(Path::new("/"), repo, None).is_some());
    }

    #[test]
    fn refuses_empty_path() {
        let repo = Path::new("/repo/main");
        assert!(unsafe_removal_reason(Path::new(""), repo, None).is_some());
    }

    #[test]
    fn refuses_main_repo_worktree() {
        let repo = Path::new("/repo/main");
        assert!(unsafe_removal_reason(Path::new("/repo/main"), repo, None).is_some());
    }

    #[test]
    fn refuses_home_directory() {
        let repo = Path::new("/repo/main");
        let home = Path::new("/home/alice");
        assert!(unsafe_removal_reason(Path::new("/home/alice"), repo, Some(home)).is_some());
    }

    #[test]
    fn allows_legit_worktree_path() {
        let repo = Path::new("/repo/main");
        let home = Path::new("/home/alice");
        assert!(unsafe_removal_reason(Path::new("/repo/wt-feature"), repo, Some(home)).is_none());
    }

    #[test]
    fn registration_matches_listed_path() {
        let listed = vec![wt("/repo/main"), wt("/repo/wt-x")];
        assert!(registered_match(
            Path::new("/repo/wt-x"),
            Path::new("/repo/wt-x"),
            &listed
        ));
    }

    #[test]
    fn registration_refuses_unlisted_path() {
        let listed = vec![wt("/repo/main"), wt("/repo/wt-x")];
        assert!(!registered_match(
            Path::new("/tmp/random"),
            Path::new("/tmp/random"),
            &listed
        ));
    }

    #[test]
    fn registration_matches_via_raw_when_resolved_differs() {
        // Prunable worktree: its dir is gone so canonicalize fell back, but the
        // raw path still matches the listed entry.
        let listed = vec![wt("/repo/wt-gone")];
        assert!(registered_match(
            Path::new("/elsewhere"),
            Path::new("/repo/wt-gone"),
            &listed
        ));
    }
}
