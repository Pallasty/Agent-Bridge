//! **C2 — First-Writer-Wins lockfile** (Collab Protocol v0, design §3.3).
//!
//! Sensitive operations on `state.db` (rescue, replace, daemon restart)
//! acquire an exclusive lock by atomically creating a JSON file in
//! `~/.cache/agent-bridge/locks/<resource>.lock`. A sibling racing in
//! on the same op sees the lock and attaches to the existing artifact
//! rather than producing a divergent snapshot.
//!
//! ## Concurrency primitive
//!
//! Uses `OpenOptions::new().create_new(true)`, i.e. `open(O_CREAT|O_EXCL)`,
//! which is atomic on POSIX filesystems. Two processes attempting to
//! acquire the same lock will see exactly one success.
//!
//! ## Stale lock policy (per §3.3)
//!
//! - lock `owner_pid` not alive → safe force-break + acquire
//! - past `ttl_secs` AND owner_pid still alive → warn + force-break with
//!   backup of old lock under `<lock>.bak-<ts>` (operator can inspect)
//! - **never deadlock** — no infinite wait paths
//!
//! See `lesson_proc_fd_rescue_for_zombie_inode` for the universal
//! `/proc/<pid>/fd` rescue technique these locks coordinate.

use std::fs;
use std::io;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

/// Default TTL for a `state.db.rescue` lock. 300s gives a slow rescue
/// (1+ GB state.db over slow disk) plenty of room while still capping
/// the impact of a crash-mid-rescue scenario.
pub const DEFAULT_RESCUE_TTL_SECS: u64 = 300;

/// One lock file. Serialized as JSON at
/// `~/.cache/agent-bridge/locks/<resource>.lock`.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LockFile {
    /// Logical resource name (e.g. `"state.db.rescue"`). One lock per
    /// resource; sibling op attaches to the same file.
    pub resource: String,
    /// PID that holds the lock. The kernel verifies aliveness via
    /// `kill(pid, 0)` so the value is trusted for liveness checks.
    pub owner_pid: u32,
    /// Human description of the holder's intent (e.g.
    /// `"agent-bridge rescue-snapshot"`). Surfaced to siblings.
    pub owner_cmd: String,
    /// Unix seconds when acquired.
    pub acquired_at: i64,
    /// TTL beyond which the lock is considered stale per §3.3 even
    /// when `owner_pid` is alive.
    pub ttl_secs: u64,
    /// Path to the canonical artifact produced under this lock (set
    /// post-rescue). `None` while still in-flight.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub artifact_path: Option<PathBuf>,
    /// SHA-256 of the canonical artifact. Updated when `artifact_path`
    /// is set. Hex string (no `0x` prefix).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub artifact_sha256: Option<String>,
}

/// Outcome of [`acquire`]. Callers branch on this to decide whether
/// to run the op or attach to the existing artifact.
#[derive(Clone)]
pub enum AcquireOutcome {
    /// Got the lock; caller owns the op + must call [`finalize`] +
    /// [`release`] (or rely on process exit + force-break for crashes).
    Acquired { lock_path: PathBuf, lock: LockFile },
    /// Another process holds a fresh lock. Caller should not duplicate
    /// the op; the artifact will appear at `lock.artifact_path` when
    /// the holder finishes.
    Attached { lock_path: PathBuf, lock: LockFile },
    /// Old lock was stale (owner_pid dead or TTL exceeded). We
    /// force-broke + acquired. `old_lock_backup` is the path of the
    /// preserved old lock JSON so the operator can post-mortem.
    ForceBroke {
        lock_path: PathBuf,
        lock: LockFile,
        old_lock_backup: PathBuf,
    },
}

#[derive(thiserror::Error, Debug)]
pub enum LockError {
    #[error("mkdir failed at {path}: {source}")]
    MkDir {
        path: PathBuf,
        #[source]
        source: io::Error,
    },
    #[error("read lock at {path}: {source}")]
    Read {
        path: PathBuf,
        #[source]
        source: io::Error,
    },
    #[error("write lock at {path}: {source}")]
    Write {
        path: PathBuf,
        #[source]
        source: io::Error,
    },
    #[error("parse lock at {path}: {source}")]
    Parse {
        path: PathBuf,
        #[source]
        source: serde_json::Error,
    },
    #[error("serialize lock: {0}")]
    Serialize(#[from] serde_json::Error),
}

/// `~/.cache/agent-bridge/locks/`. Honours `AB_LOCKS_DIR` env override
/// (used by tests to point at a tmpdir).
pub fn default_locks_dir() -> PathBuf {
    if let Ok(p) = std::env::var("AB_LOCKS_DIR") {
        return PathBuf::from(p);
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home).join(".cache/agent-bridge/locks")
}

/// Path for a given resource under the default (or env-overridden) dir.
pub fn lock_path_for(resource: &str) -> PathBuf {
    default_locks_dir().join(format!("{resource}.lock"))
}

/// `kill(pid, 0)` — returns true if a process with this PID currently
/// exists in the OS table (we do NOT actually signal anything; signal
/// 0 is the standard liveness probe). On non-Unix this returns true
/// conservatively (we don't want to force-break locks on platforms
/// where we can't verify; better-safe-than-clobber).
pub fn is_pid_alive(pid: u32) -> bool {
    #[cfg(unix)]
    unsafe {
        // SAFETY: kill(2) with sig=0 does no work other than error
        // reporting; valid for any PID.
        libc::kill(pid as i32, 0) == 0
    }
    #[cfg(not(unix))]
    {
        let _ = pid;
        true
    }
}

fn now_unix() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

/// Try to read an existing lock. Returns `Ok(None)` when the file
/// doesn't exist (the normal "no lock held" case).
pub fn read_lock(path: &Path) -> Result<Option<LockFile>, LockError> {
    let bytes = match fs::read(path) {
        Ok(b) => b,
        Err(e) if e.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(e) => {
            return Err(LockError::Read {
                path: path.to_path_buf(),
                source: e,
            })
        }
    };
    let parsed = serde_json::from_slice::<LockFile>(&bytes).map_err(|e| LockError::Parse {
        path: path.to_path_buf(),
        source: e,
    })?;
    Ok(Some(parsed))
}

fn write_lock_atomic(path: &Path, lock: &LockFile) -> Result<(), LockError> {
    let payload = serde_json::to_vec_pretty(lock)?;
    let tmp = path.with_extension("lock.tmp");
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| LockError::MkDir {
            path: parent.to_path_buf(),
            source: e,
        })?;
    }
    let mut f = fs::File::create(&tmp).map_err(|e| LockError::Write {
        path: tmp.clone(),
        source: e,
    })?;
    f.write_all(&payload).map_err(|e| LockError::Write {
        path: tmp.clone(),
        source: e,
    })?;
    f.sync_all().map_err(|e| LockError::Write {
        path: tmp.clone(),
        source: e,
    })?;
    drop(f);
    fs::rename(&tmp, path).map_err(|e| LockError::Write {
        path: path.to_path_buf(),
        source: e,
    })?;
    Ok(())
}

/// Attempt exclusive create via `O_CREAT|O_EXCL`. Returns `Ok(true)`
/// if this caller won the race, `Ok(false)` if another process beat us.
fn try_exclusive_create(path: &Path, lock: &LockFile) -> Result<bool, LockError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| LockError::MkDir {
            path: parent.to_path_buf(),
            source: e,
        })?;
    }
    let payload = serde_json::to_vec_pretty(lock)?;
    let mut opts = fs::OpenOptions::new();
    opts.create_new(true).write(true);
    match opts.open(path) {
        Ok(mut f) => {
            f.write_all(&payload).map_err(|e| LockError::Write {
                path: path.to_path_buf(),
                source: e,
            })?;
            f.sync_all().map_err(|e| LockError::Write {
                path: path.to_path_buf(),
                source: e,
            })?;
            Ok(true)
        }
        Err(e) if e.kind() == io::ErrorKind::AlreadyExists => Ok(false),
        Err(e) => Err(LockError::Write {
            path: path.to_path_buf(),
            source: e,
        }),
    }
}

/// Acquire — try once, classify the outcome per §3.3 stale lock policy.
///
/// `ttl_secs` is recorded in the new lock; existing locks are evaluated
/// against THEIR own recorded `ttl_secs`, not this one — siblings can
/// honestly report mismatched configurations rather than the new caller
/// imposing its TTL on a holder it didn't spawn.
pub fn acquire(
    resource: &str,
    owner_pid: u32,
    owner_cmd: impl Into<String>,
    ttl_secs: u64,
) -> Result<AcquireOutcome, LockError> {
    let path = lock_path_for(resource);
    let new_lock = LockFile {
        resource: resource.to_string(),
        owner_pid,
        owner_cmd: owner_cmd.into(),
        acquired_at: now_unix(),
        ttl_secs,
        artifact_path: None,
        artifact_sha256: None,
    };

    // Fast path: exclusive create wins → done.
    if try_exclusive_create(&path, &new_lock)? {
        return Ok(AcquireOutcome::Acquired {
            lock_path: path,
            lock: new_lock,
        });
    }

    // Slow path: someone holds the lock. Read it, classify.
    let existing = match read_lock(&path)? {
        Some(l) => l,
        None => {
            // Lock vanished between the create attempt and the read —
            // race window with the holder. Retry once.
            if try_exclusive_create(&path, &new_lock)? {
                return Ok(AcquireOutcome::Acquired {
                    lock_path: path,
                    lock: new_lock,
                });
            }
            // If it still exists now, read again; if still gone treat
            // as a phantom and surface as a synthetic "not stale" so the
            // caller can re-try.
            match read_lock(&path)? {
                Some(l) => l,
                None => {
                    return Err(LockError::Read {
                        path: path.clone(),
                        source: io::Error::new(io::ErrorKind::Other, "lock vanished mid-race"),
                    })
                }
            }
        }
    };

    let alive = is_pid_alive(existing.owner_pid);
    let age = (now_unix() - existing.acquired_at).max(0) as u64;
    let stale_by_pid = !alive;
    let stale_by_ttl = age > existing.ttl_secs;

    if stale_by_pid || stale_by_ttl {
        // Force-break: rename existing lock to a backup, write the new
        // lock atomically into place.
        let backup = path.with_extension(format!("lock.bak-{}", now_unix()));
        fs::rename(&path, &backup).map_err(|e| LockError::Write {
            path: backup.clone(),
            source: e,
        })?;
        write_lock_atomic(&path, &new_lock)?;
        return Ok(AcquireOutcome::ForceBroke {
            lock_path: path,
            lock: new_lock,
            old_lock_backup: backup,
        });
    }

    // Fresh lock, real holder — caller must attach.
    Ok(AcquireOutcome::Attached {
        lock_path: path,
        lock: existing,
    })
}

/// Update an existing lock with artifact metadata. Idempotent (atomic
/// rewrite). Caller invokes this after producing the artifact + sha so
/// later attachers can find the artifact directly.
pub fn finalize(
    lock_path: &Path,
    artifact_path: PathBuf,
    artifact_sha256: String,
) -> Result<LockFile, LockError> {
    let mut lock = read_lock(lock_path)?.ok_or_else(|| LockError::Read {
        path: lock_path.to_path_buf(),
        source: io::Error::new(io::ErrorKind::NotFound, "lock missing for finalize"),
    })?;
    lock.artifact_path = Some(artifact_path);
    lock.artifact_sha256 = Some(artifact_sha256);
    write_lock_atomic(lock_path, &lock)?;
    Ok(lock)
}

/// Release the lock by deleting the file. Idempotent (missing file is
/// not an error — caller may have already exited).
pub fn release(lock_path: &Path) -> Result<(), LockError> {
    match fs::remove_file(lock_path) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(LockError::Write {
            path: lock_path.to_path_buf(),
            source: e,
        }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn with_tmp_locks_dir<R>(f: impl FnOnce(&Path) -> R) -> R {
        let tmp = TempDir::new().expect("tmpdir");
        std::env::set_var("AB_LOCKS_DIR", tmp.path());
        let out = f(tmp.path());
        std::env::remove_var("AB_LOCKS_DIR");
        out
    }

    static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    #[test]
    fn acquire_creates_lock_and_returns_acquired() {
        let _g = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        with_tmp_locks_dir(|dir| {
            let pid = std::process::id();
            let out = acquire("test.resource.a", pid, "test/a", 60).expect("acquire");
            match out {
                AcquireOutcome::Acquired { lock_path, lock } => {
                    assert_eq!(lock.resource, "test.resource.a");
                    assert_eq!(lock.owner_pid, pid);
                    assert!(lock_path.starts_with(dir));
                    assert!(lock_path.exists());
                }
                other => panic!("expected Acquired, got {other:?}"),
            }
        });
    }

    #[test]
    fn second_acquire_returns_attached_when_holder_is_alive() {
        let _g = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        with_tmp_locks_dir(|_| {
            let pid = std::process::id();
            let _ = acquire("test.resource.b", pid, "test/b1", 600).expect("first");
            let out = acquire("test.resource.b", pid, "test/b2", 600).expect("second");
            match out {
                AcquireOutcome::Attached { lock, .. } => {
                    // Reports the FIRST holder's owner_cmd — that's the
                    // useful field for the second caller.
                    assert_eq!(lock.owner_cmd, "test/b1");
                }
                other => panic!("expected Attached, got {other:?}"),
            }
        });
    }

    #[test]
    fn second_acquire_force_breaks_dead_pid() {
        let _g = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        with_tmp_locks_dir(|_| {
            // Seed a lock with a PID that is overwhelmingly unlikely
            // to exist on any host (kernel max is typically 2^22).
            let dead_pid: u32 = 9_999_999;
            let _ = acquire("test.resource.c", dead_pid, "test/dead", 600).expect("seed");
            let live_pid = std::process::id();
            let out = acquire("test.resource.c", live_pid, "test/live", 600).expect("second");
            match out {
                AcquireOutcome::ForceBroke {
                    lock,
                    old_lock_backup,
                    ..
                } => {
                    assert_eq!(lock.owner_pid, live_pid);
                    assert!(old_lock_backup.exists(), "backup must persist");
                }
                other => panic!("expected ForceBroke, got {other:?}"),
            }
        });
    }

    #[test]
    fn second_acquire_force_breaks_ttl_exceeded_lock() {
        let _g = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        with_tmp_locks_dir(|_| {
            // Write a lock with ttl=1 and acquired_at way back in time.
            let path = lock_path_for("test.resource.d");
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            let aged = LockFile {
                resource: "test.resource.d".into(),
                owner_pid: std::process::id(),
                owner_cmd: "test/aged".into(),
                acquired_at: now_unix() - 3600, // 1h ago
                ttl_secs: 1,
                artifact_path: None,
                artifact_sha256: None,
            };
            write_lock_atomic(&path, &aged).unwrap();

            let out =
                acquire("test.resource.d", std::process::id(), "test/fresh", 600).expect("second");
            match out {
                AcquireOutcome::ForceBroke {
                    lock,
                    old_lock_backup,
                    ..
                } => {
                    assert_eq!(lock.owner_cmd, "test/fresh");
                    assert!(old_lock_backup.exists());
                }
                other => panic!("expected ForceBroke, got {other:?}"),
            }
        });
    }

    #[test]
    fn finalize_attaches_artifact_metadata() {
        let _g = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        with_tmp_locks_dir(|_| {
            let pid = std::process::id();
            let out = acquire("test.resource.e", pid, "test/e", 60).expect("acquire");
            let lock_path = match out {
                AcquireOutcome::Acquired { lock_path, .. } => lock_path,
                _ => panic!("expected Acquired"),
            };
            let lock = finalize(
                &lock_path,
                PathBuf::from("/tmp/artifact"),
                "deadbeef".into(),
            )
            .expect("finalize");
            assert_eq!(lock.artifact_path, Some(PathBuf::from("/tmp/artifact")));
            assert_eq!(lock.artifact_sha256, Some("deadbeef".to_string()));

            // Re-read from disk to confirm persistence.
            let from_disk = read_lock(&lock_path).expect("read").expect("present");
            assert_eq!(from_disk.artifact_sha256.as_deref(), Some("deadbeef"));
        });
    }

    #[test]
    fn release_removes_lock_file_and_is_idempotent() {
        let _g = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        with_tmp_locks_dir(|_| {
            let pid = std::process::id();
            let out = acquire("test.resource.f", pid, "test/f", 60).expect("acquire");
            let lock_path = match out {
                AcquireOutcome::Acquired { lock_path, .. } => lock_path,
                _ => panic!("expected Acquired"),
            };
            release(&lock_path).expect("release");
            assert!(!lock_path.exists());
            // Second release is a no-op.
            release(&lock_path).expect("idempotent release");
        });
    }

    #[test]
    fn is_pid_alive_self_is_alive() {
        assert!(is_pid_alive(std::process::id()));
    }

    #[test]
    fn is_pid_alive_high_pid_is_dead() {
        // 9_999_999 is above typical Linux pid_max (default 32768 or
        // 2^22). This may occasionally collide on extreme systems; if
        // it does, bump the value rather than weakening the assertion.
        assert!(!is_pid_alive(9_999_999));
    }
}

impl std::fmt::Debug for AcquireOutcome {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AcquireOutcome::Acquired { lock, .. } => {
                write!(
                    f,
                    "Acquired(resource={}, pid={})",
                    lock.resource, lock.owner_pid
                )
            }
            AcquireOutcome::Attached { lock, .. } => {
                write!(
                    f,
                    "Attached(resource={}, pid={})",
                    lock.resource, lock.owner_pid
                )
            }
            AcquireOutcome::ForceBroke { lock, .. } => write!(
                f,
                "ForceBroke(resource={}, new_pid={})",
                lock.resource, lock.owner_pid
            ),
        }
    }
}
