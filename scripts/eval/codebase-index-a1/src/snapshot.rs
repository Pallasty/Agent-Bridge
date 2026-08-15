use std::{
    fs,
    io::Read,
    os::unix::fs::MetadataExt,
    path::{Path, PathBuf},
};

use rusqlite::Connection;
use sha2::{Digest, Sha256};
use thiserror::Error;

use crate::{
    workload::{bytes_hex, digest_hex, frame_str, frame_u64, SemanticAccumulator, WorkloadError},
    DatabaseEvidence, Mode, RollbackStateEvidence, StorageEvidence, WalHeaderLayoutEvidence,
    WalResetEvidence,
};

#[derive(Debug, Error)]
pub enum SnapshotError {
    #[error("SQLite evidence query failed: {0}")]
    Sqlite(#[from] rusqlite::Error),
    #[error("evidence filesystem operation failed: {0}")]
    Io(#[from] std::io::Error),
    #[error("database path is outside the frozen source root: {0}")]
    ForeignPath(String),
    #[error("database numeric field {field} is out of range: {value}")]
    NumericRange { field: &'static str, value: i64 },
    #[error("fresh trial WAL reset was busy")]
    WalResetBusy,
    #[error("fresh trial WAL reset did not produce an empty WAL")]
    WalResetNotEmpty,
    #[error("semantic digest failed: {0}")]
    Semantic(#[from] WorkloadError),
}

#[derive(Debug, Clone)]
pub struct CgroupMemorySnapshot {
    pub path: String,
    pub current_bytes: u64,
    pub peak_bytes: u64,
    pub max: String,
    pub process_count: u64,
    pub process_ids: Vec<u32>,
    pub anon_bytes: u64,
    pub file_bytes: u64,
    pub shmem_bytes: u64,
}

#[derive(Debug, Clone, Copy)]
pub struct ProcIoSnapshot {
    pub read_bytes: u64,
    pub write_bytes: u64,
}

#[derive(Debug, Clone, Copy)]
pub struct RusageSnapshot {
    pub minor_faults: u64,
    pub major_faults: u64,
    pub max_rss_bytes: u64,
}

#[derive(Debug, Clone)]
pub struct FixtureState {
    pub target_rows: u64,
    pub target_nonnull_embeddings: u64,
    pub target_generation_sha256: String,
    pub target_raw_sha256: String,
    pub other_root_sha256: String,
    pub non_codebase_sentinel_sha256: String,
}

pub const OTHER_ROOT: &str = "agent-bridge-a1://other-root";
pub const SENTINEL_KEY: &str = "eval:codebase-index-a1:non-codebase-sentinel";

pub fn database_evidence(
    database_path: &Path,
    source_root: &Path,
) -> Result<DatabaseEvidence, SnapshotError> {
    let connection = Connection::open(database_path)?;
    let page_size = pragma_u64(&connection, "page_size")?;
    let page_count = pragma_u64(&connection, "page_count")?;
    let freelist_count = pragma_u64(&connection, "freelist_count")?;
    let journal_mode: String = connection.query_row("PRAGMA journal_mode", [], |row| row.get(0))?;
    let wal_path = sqlite_sidecar_path(database_path, "-wal");
    let shm_path = sqlite_sidecar_path(database_path, "-shm");
    let database_bytes = fs::metadata(database_path)?.len();
    let wal_bytes = sqlite_sidecar_bytes(&wal_path)?;
    let shm_bytes = sqlite_sidecar_bytes(&shm_path)?;
    let wal_header_layout = wal_header_layout_evidence_for_path(&wal_path, wal_bytes, page_size)?;
    let (busy, checkpoint_log, checkpointed): (i64, i64, i64) =
        connection.query_row("PRAGMA wal_checkpoint(PASSIVE)", [], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?))
        })?;
    let schema_sha256 = schema_sha256(&connection)?;
    let semantic = semantic_digest(&connection, source_root)?;
    let generation_sha256 = root_generation_sha256(&connection, source_root)?;
    let symbols = count_root_rows(&connection, "codebase_symbols", source_root)?;
    let imports = count_root_rows(&connection, "codebase_imports", source_root)?;
    let calls = count_root_rows(&connection, "codebase_calls", source_root)?;
    let root_rows = symbols
        .checked_add(imports)
        .and_then(|value| value.checked_add(calls));
    let root = source_root.to_string_lossy();
    let null_embeddings = query_u64(
        &connection,
        "SELECT COUNT(*) FROM codebase_symbols WHERE root_path = ?1 AND embedding IS NULL",
        [&root.as_ref()],
    )?;
    let indexed_at_values = query_u64(
        &connection,
        "SELECT COUNT(DISTINCT indexed_at) FROM (\
             SELECT indexed_at FROM codebase_symbols WHERE root_path = ?1 \
             UNION ALL SELECT indexed_at FROM codebase_imports WHERE root_path = ?1 \
             UNION ALL SELECT indexed_at FROM codebase_calls WHERE root_path = ?1\
         )",
        [&root.as_ref()],
    )?;

    Ok(DatabaseEvidence {
        schema_sha256: Some(schema_sha256),
        semantic_sha256: Some(semantic.combined_sha256),
        page_count: Some(page_count),
        freelist_count: Some(freelist_count),
        wal_bytes: Some(wal_bytes),
        database_bytes: Some(database_bytes),
        shm_bytes: Some(shm_bytes),
        wal_frames: Some(wal_header_layout.frame_count),
        wal_checkpoint_log_frames: Some(nonnegative_u64("wal checkpoint log", checkpoint_log)?),
        wal_checkpointed_frames: Some(nonnegative_u64("wal checkpointed", checkpointed)?),
        wal_checkpoint_busy: Some(nonnegative_u64("wal checkpoint busy", busy)?),
        wal_layout_valid: Some(wal_header_layout.header_layout_valid),
        wal_header_layout: Some(wal_header_layout),
        page_size: Some(page_size),
        journal_mode: Some(journal_mode.to_ascii_lowercase()),
        root_rows,
        null_embeddings: Some(null_embeddings),
        indexed_at_values: Some(indexed_at_values),
        sqlite_version: Some(rusqlite::version().to_string()),
        sqlite_compile_options_sha256: Some(sqlite_compile_options_sha256(&connection)?),
        generation_sha256: Some(generation_sha256),
        integrity_check: Some(
            connection.query_row("PRAGMA integrity_check", [], |row| row.get(0))?,
        ),
        foreign_key_violations: Some(foreign_key_violation_count(&connection)?),
        schema_meta_version: connection
            .query_row(
                "SELECT value FROM schema_meta WHERE key = 'version'",
                [],
                |row| row.get(0),
            )
            .ok(),
        schema_meta_sha256: Some(schema_meta_sha256(&connection)?),
        schema_version: Some(pragma_u64(&connection, "schema_version")?),
        user_version: Some(pragma_u64(&connection, "user_version")?),
        synchronous: Some(pragma_i64(&connection, "synchronous")?),
        wal_autocheckpoint: Some(pragma_i64(&connection, "wal_autocheckpoint")?),
        cache_size: Some(pragma_i64(&connection, "cache_size")?),
        cache_spill: Some(pragma_i64(&connection, "cache_spill")?),
        temp_store: Some(pragma_i64(&connection, "temp_store")?),
        mmap_size: Some(pragma_i64(&connection, "mmap_size")?),
        foreign_keys: Some(pragma_i64(&connection, "foreign_keys")?),
        busy_timeout_ms: Some(pragma_i64(&connection, "busy_timeout")?),
        locking_mode: Some(connection.query_row("PRAGMA locking_mode", [], |row| row.get(0))?),
    })
}

/// Remove schema-initialization WAL bytes before the measured index operation.
/// This only touches the fresh isolated trial database.
pub fn reset_main_wal(database_path: &Path) -> Result<WalResetEvidence, SnapshotError> {
    let connection = Connection::open(database_path)?;
    let (busy, log, checkpointed): (i64, i64, i64) =
        connection.query_row("PRAGMA wal_checkpoint(TRUNCATE)", [], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?))
        })?;
    if busy != 0 {
        return Err(SnapshotError::WalResetBusy);
    }
    let wal_path = sqlite_sidecar_path(database_path, "-wal");
    let wal_bytes = sqlite_sidecar_bytes(&wal_path)?;
    let busy = nonnegative_u64("wal reset busy", busy)?;
    let log_frames = nonnegative_u64("wal reset log", log)?;
    let checkpointed_frames = nonnegative_u64("wal reset checkpointed", checkpointed)?;
    Ok(WalResetEvidence {
        busy,
        log_frames,
        checkpointed_frames,
        wal_bytes,
        proven_empty: busy == 0 && log_frames == 0 && checkpointed_frames == 0 && wal_bytes == 0,
    })
}

pub fn seed_base_fixture(database_path: &Path, target_root: &Path) -> Result<(), SnapshotError> {
    let mut connection = Connection::open(database_path)?;
    let transaction = connection.transaction()?;
    let target = target_root.to_string_lossy();
    transaction.execute(
        "UPDATE codebase_symbols SET embedding = X'00010203' WHERE root_path = ?1",
        [&target.as_ref()],
    )?;
    transaction.execute(
        "INSERT INTO codebase_symbols \
         (file_path,line,col,kind,name,signature,language,root_path,indexed_at,embedding) \
         VALUES ('other-root.rs',1,0,'fn','other_symbol','fn other_symbol()','rust',?1,1,X'09')",
        [OTHER_ROOT],
    )?;
    transaction.execute(
        "INSERT INTO codebase_imports \
         (file_path,line,language,raw,target,alias,root_path,indexed_at) \
         VALUES ('other-root.rs',2,'rust','use other::x;','other::x',NULL,?1,1)",
        [OTHER_ROOT],
    )?;
    transaction.execute(
        "INSERT INTO codebase_calls \
         (file_path,line,language,caller,callee,root_path,indexed_at) \
         VALUES ('other-root.rs',3,'rust','other_symbol','other_call',?1,1)",
        [OTHER_ROOT],
    )?;
    transaction.execute(
        "INSERT INTO memories \
         (key,kind,content,tags,related_keys,created_at,updated_at,last_accessed_at,access_count) \
         VALUES (?1,'eval-sentinel','codebase-index-a1 sentinel','[]','[]',1,1,1,0)",
        [SENTINEL_KEY],
    )?;
    transaction.commit()?;
    drop(connection);
    let reset = reset_main_wal(database_path)?;
    if !reset.proven_empty {
        return Err(SnapshotError::WalResetNotEmpty);
    }
    Ok(())
}

pub fn fixture_state(
    database_path: &Path,
    target_root: &Path,
) -> Result<FixtureState, SnapshotError> {
    let connection = Connection::open(database_path)?;
    let root = target_root.to_string_lossy();
    let symbols = query_u64(
        &connection,
        "SELECT COUNT(*) FROM codebase_symbols WHERE root_path = ?1",
        [&root.as_ref()],
    )?;
    let imports = query_u64(
        &connection,
        "SELECT COUNT(*) FROM codebase_imports WHERE root_path = ?1",
        [&root.as_ref()],
    )?;
    let calls = query_u64(
        &connection,
        "SELECT COUNT(*) FROM codebase_calls WHERE root_path = ?1",
        [&root.as_ref()],
    )?;
    Ok(FixtureState {
        target_rows: symbols.saturating_add(imports).saturating_add(calls),
        target_nonnull_embeddings: query_u64(
            &connection,
            "SELECT COUNT(*) FROM codebase_symbols WHERE root_path = ?1 AND embedding IS NOT NULL",
            [&root.as_ref()],
        )?,
        target_generation_sha256: root_generation_sha256(&connection, target_root)?,
        target_raw_sha256: raw_target_sha256(&connection, target_root)?,
        other_root_sha256: other_root_sha256(&connection)?,
        non_codebase_sentinel_sha256: sentinel_sha256(&connection)?,
    })
}

pub fn rollback_state(
    database_path: &Path,
    target_root: &Path,
) -> Result<RollbackStateEvidence, SnapshotError> {
    let connection = Connection::open(database_path)?;
    Ok(RollbackStateEvidence {
        database_sha256: crate::provenance::sha256_file(database_path)?,
        all_codebase_sha256: all_codebase_sha256(&connection)?,
        sqlite_sequence_sha256: sqlite_sequence_sha256(&connection)?,
        target_raw_sha256: raw_target_sha256(&connection, target_root)?,
        other_root_sha256: other_root_sha256(&connection)?,
        non_codebase_sentinel_sha256: sentinel_sha256(&connection)?,
        schema_sha256: schema_sha256(&connection)?,
        schema_meta_sha256: schema_meta_sha256(&connection)?,
        schema_version: pragma_u64(&connection, "schema_version")?,
        user_version: pragma_u64(&connection, "user_version")?,
        page_count: pragma_u64(&connection, "page_count")?,
        freelist_count: pragma_u64(&connection, "freelist_count")?,
        integrity_check: connection.query_row("PRAGMA integrity_check", [], |row| row.get(0))?,
        foreign_key_violations: foreign_key_violation_count(&connection)?,
    })
}

pub fn sidecars_absent(database_path: &Path) -> Result<bool, SnapshotError> {
    Ok(
        sqlite_sidecar_absent(&sqlite_sidecar_path(database_path, "-wal"))?
            && sqlite_sidecar_absent(&sqlite_sidecar_path(database_path, "-shm"))?,
    )
}

fn sqlite_sidecar_path(database_path: &Path, suffix: &str) -> PathBuf {
    let mut sidecar = database_path.as_os_str().to_os_string();
    sidecar.push(suffix);
    PathBuf::from(sidecar)
}

fn sqlite_sidecar_bytes(sidecar_path: &Path) -> Result<u64, SnapshotError> {
    match fs::metadata(sidecar_path) {
        Ok(metadata) => Ok(metadata.len()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(0),
        Err(error) => Err(SnapshotError::Io(error)),
    }
}

fn sqlite_sidecar_absent(sidecar_path: &Path) -> Result<bool, SnapshotError> {
    match fs::metadata(sidecar_path) {
        Ok(_) => Ok(false),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(true),
        Err(error) => Err(SnapshotError::Io(error)),
    }
}

pub fn storage_evidence(
    trial_root: &Path,
    database_path: &Path,
    staging_dir: &Path,
    mode: Mode,
) -> StorageEvidence {
    let canonical_trial = trial_root
        .canonicalize()
        .unwrap_or_else(|_| trial_root.to_path_buf());
    let mount = mount_for_path(&canonical_trial);
    StorageEvidence {
        trial_root: canonical_trial.clone(),
        mount_point: mount.as_ref().map(|value| value.0.clone()),
        filesystem_type: mount.map(|value| value.1),
        trial_device: fs::metadata(&canonical_trial).ok().map(|value| value.dev()),
        database_device: fs::metadata(database_path).ok().map(|value| value.dev()),
        staging_device: (mode == Mode::StagedNative)
            .then(|| fs::metadata(staging_dir).ok().map(|value| value.dev()))
            .flatten(),
    }
}

pub fn peak_rss_bytes() -> Option<u64> {
    let status = fs::read_to_string("/proc/self/status").ok()?;
    let kib: u64 = status
        .lines()
        .find(|line| line.starts_with("VmHWM:"))?
        .split_whitespace()
        .nth(1)?
        .parse()
        .ok()?;
    kib.checked_mul(1024)
}

pub fn cgroup_memory_snapshot() -> Option<CgroupMemorySnapshot> {
    let cgroup = fs::read_to_string("/proc/self/cgroup").ok()?;
    let relative = cgroup.lines().find_map(|line| line.strip_prefix("0::"))?;
    let relative = relative.trim();
    let relative = relative.strip_prefix('/').unwrap_or(relative);
    let directory = Path::new("/sys/fs/cgroup").join(relative);
    let memory_stat = fs::read_to_string(directory.join("memory.stat")).ok()?;
    let process_ids = fs::read_to_string(directory.join("cgroup.procs"))
        .ok()?
        .lines()
        .map(str::parse::<u32>)
        .collect::<Result<Vec<_>, _>>()
        .ok()?;
    Some(CgroupMemorySnapshot {
        path: format!("/{relative}"),
        current_bytes: read_u64_file(&directory.join("memory.current"))?,
        peak_bytes: read_u64_file(&directory.join("memory.peak"))?,
        max: fs::read_to_string(directory.join("memory.max"))
            .ok()?
            .trim()
            .to_string(),
        process_count: process_ids.len() as u64,
        process_ids,
        anon_bytes: keyed_u64(&memory_stat, "anon")?,
        file_bytes: keyed_u64(&memory_stat, "file")?,
        shmem_bytes: keyed_u64(&memory_stat, "shmem")?,
    })
}

pub fn proc_io_snapshot() -> Option<ProcIoSnapshot> {
    let contents = fs::read_to_string("/proc/self/io").ok()?;
    Some(ProcIoSnapshot {
        read_bytes: proc_io_value(&contents, "read_bytes:")?,
        write_bytes: proc_io_value(&contents, "write_bytes:")?,
    })
}

pub fn rusage_snapshot() -> Option<RusageSnapshot> {
    let mut usage = std::mem::MaybeUninit::<libc::rusage>::zeroed();
    // SAFETY: getrusage initializes the supplied rusage on success.
    if unsafe { libc::getrusage(libc::RUSAGE_SELF, usage.as_mut_ptr()) } != 0 {
        return None;
    }
    // SAFETY: guarded by the successful getrusage call above.
    let usage = unsafe { usage.assume_init() };
    Some(RusageSnapshot {
        minor_faults: u64::try_from(usage.ru_minflt).ok()?,
        major_faults: u64::try_from(usage.ru_majflt).ok()?,
        max_rss_bytes: u64::try_from(usage.ru_maxrss).ok()?.checked_mul(1024)?,
    })
}

fn proc_io_value(contents: &str, key: &str) -> Option<u64> {
    contents
        .lines()
        .find(|line| line.starts_with(key))?
        .split_whitespace()
        .nth(1)?
        .parse()
        .ok()
}

fn keyed_u64(contents: &str, key: &str) -> Option<u64> {
    let line = contents
        .lines()
        .find(|line| line.split_whitespace().next() == Some(key))?;
    line.split_whitespace().nth(1)?.parse().ok()
}

fn read_u64_file(path: &Path) -> Option<u64> {
    fs::read_to_string(path).ok()?.trim().parse().ok()
}

fn mount_for_path(path: &Path) -> Option<(PathBuf, String)> {
    let mountinfo = fs::read_to_string("/proc/self/mountinfo").ok()?;
    let mut best: Option<(PathBuf, String)> = None;
    for line in mountinfo.lines() {
        let fields: Vec<&str> = line.split_whitespace().collect();
        let separator = fields.iter().position(|field| *field == "-")?;
        if fields.len() <= separator + 1 || fields.len() <= 4 {
            continue;
        }
        let mount_point = PathBuf::from(unescape_mount_field(fields[4]));
        if !path.starts_with(&mount_point) {
            continue;
        }
        let filesystem_type = fields[separator + 1].to_string();
        if best
            .as_ref()
            .is_none_or(|(current, _)| mount_point.as_os_str().len() > current.as_os_str().len())
        {
            best = Some((mount_point, filesystem_type));
        }
    }
    best
}

fn unescape_mount_field(value: &str) -> String {
    value
        .replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
}

fn pragma_u64(connection: &Connection, name: &'static str) -> Result<u64, SnapshotError> {
    let value: i64 = connection.query_row(&format!("PRAGMA {name}"), [], |row| row.get(0))?;
    nonnegative_u64(name, value)
}

fn pragma_i64(connection: &Connection, name: &'static str) -> Result<i64, SnapshotError> {
    Ok(connection.query_row(&format!("PRAGMA {name}"), [], |row| row.get(0))?)
}

pub fn wal_header_layout_evidence(
    database_path: &Path,
    page_size: u64,
) -> Result<WalHeaderLayoutEvidence, SnapshotError> {
    let wal_path = sqlite_sidecar_path(database_path, "-wal");
    let wal_bytes = sqlite_sidecar_bytes(&wal_path)?;
    wal_header_layout_evidence_for_path(&wal_path, wal_bytes, page_size)
}

fn wal_header_layout_evidence_for_path(
    wal_path: &Path,
    wal_bytes: u64,
    page_size: u64,
) -> Result<WalHeaderLayoutEvidence, SnapshotError> {
    if wal_bytes == 0 {
        return Ok(WalHeaderLayoutEvidence {
            bytes: 0,
            header_hex: None,
            magic: None,
            format_version: None,
            encoded_page_size: None,
            frame_count: 0,
            header_layout_valid: true,
        });
    }
    if wal_bytes < 32 || page_size == 0 {
        return Ok(WalHeaderLayoutEvidence {
            bytes: wal_bytes,
            header_hex: None,
            magic: None,
            format_version: None,
            encoded_page_size: None,
            frame_count: 0,
            header_layout_valid: false,
        });
    }
    let mut header = [0_u8; 32];
    fs::File::open(wal_path)?.read_exact(&mut header)?;
    let magic = u32::from_be_bytes([header[0], header[1], header[2], header[3]]);
    let format_version = u32::from_be_bytes([header[4], header[5], header[6], header[7]]);
    let encoded_page_size = u32::from_be_bytes([header[8], header[9], header[10], header[11]]);
    let encoded_page_size = if encoded_page_size == 1 {
        65_536
    } else {
        u64::from(encoded_page_size)
    };
    let frame_size = page_size.saturating_add(24);
    let payload = wal_bytes - 32;
    let layout_valid = matches!(magic, 0x377f_0682 | 0x377f_0683)
        && format_version == 3_007_000
        && encoded_page_size == page_size
        && frame_size > 24
        && payload % frame_size == 0;
    Ok(WalHeaderLayoutEvidence {
        bytes: wal_bytes,
        header_hex: Some(bytes_hex(&header)),
        magic: Some(magic),
        format_version: Some(format_version),
        encoded_page_size: Some(encoded_page_size),
        frame_count: payload / frame_size,
        header_layout_valid: layout_valid,
    })
}

fn count_root_rows(
    connection: &Connection,
    table: &str,
    source_root: &Path,
) -> Result<u64, SnapshotError> {
    let root = source_root.to_string_lossy();
    query_u64(
        connection,
        &format!("SELECT COUNT(*) FROM {table} WHERE root_path = ?1"),
        [&root.as_ref()],
    )
}

fn query_u64<P: rusqlite::Params>(
    connection: &Connection,
    sql: &str,
    params: P,
) -> Result<u64, SnapshotError> {
    let value: i64 = connection.query_row(sql, params, |row| row.get(0))?;
    nonnegative_u64("query result", value)
}

fn nonnegative_u64(field: &'static str, value: i64) -> Result<u64, SnapshotError> {
    u64::try_from(value).map_err(|_| SnapshotError::NumericRange { field, value })
}

fn schema_sha256(connection: &Connection) -> Result<String, SnapshotError> {
    let mut digest = Sha256::new();
    frame_str(&mut digest, "agent_bridge.authoritative_sqlite_schema.v0");
    let mut statement = connection.prepare(
        "SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_schema \
         WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name, tbl_name, sql",
    )?;
    let mut rows = statement.query([])?;
    while let Some(row) = rows.next()? {
        frame_str(&mut digest, &row.get::<_, String>(0)?);
        frame_str(&mut digest, &row.get::<_, String>(1)?);
        frame_str(&mut digest, &row.get::<_, String>(2)?);
        frame_str(&mut digest, &row.get::<_, String>(3)?);
    }
    Ok(digest_hex(digest))
}

fn schema_meta_sha256(connection: &Connection) -> Result<String, SnapshotError> {
    let mut digest = Sha256::new();
    frame_str(&mut digest, "agent_bridge.schema_meta.v0");
    let mut statement = connection.prepare("SELECT key, value FROM schema_meta ORDER BY key")?;
    let mut rows = statement.query([])?;
    while let Some(row) = rows.next()? {
        frame_str(&mut digest, &row.get::<_, String>(0)?);
        frame_str(&mut digest, &row.get::<_, String>(1)?);
    }
    Ok(digest_hex(digest))
}

fn foreign_key_violation_count(connection: &Connection) -> Result<u64, SnapshotError> {
    let mut statement = connection.prepare("PRAGMA foreign_key_check")?;
    let mut rows = statement.query([])?;
    let mut count = 0_u64;
    while rows.next()?.is_some() {
        count = count.saturating_add(1);
    }
    Ok(count)
}

fn root_generation_sha256(
    connection: &Connection,
    source_root: &Path,
) -> Result<String, SnapshotError> {
    let root = source_root.to_string_lossy();
    let mut digest = Sha256::new();
    frame_str(&mut digest, "agent_bridge.authoritative_root_generation.v0");
    for (table, has_embedding) in [
        ("codebase_symbols", true),
        ("codebase_imports", false),
        ("codebase_calls", false),
    ] {
        frame_str(&mut digest, table);
        let sql = if has_embedding {
            format!(
                "SELECT id, root_path, indexed_at, embedding FROM {table} WHERE root_path = ?1 ORDER BY id"
            )
        } else {
            format!(
                "SELECT id, root_path, indexed_at, NULL FROM {table} WHERE root_path = ?1 ORDER BY id"
            )
        };
        let mut statement = connection.prepare(&sql)?;
        let mut rows = statement.query([&root.as_ref()])?;
        let mut generation = None;
        let mut count = 0_u64;
        while let Some(row) = rows.next()? {
            let id: i64 = row.get(0)?;
            let row_root: String = row.get(1)?;
            let indexed_at: i64 = row.get(2)?;
            let embedding: Option<Vec<u8>> = row.get(3)?;
            frame_u64(&mut digest, nonnegative_u64("row id", id)?);
            frame_str(&mut digest, &row_root);
            let expected_generation = generation.get_or_insert(indexed_at);
            digest.update([u8::from(*expected_generation == indexed_at)]);
            match embedding {
                Some(value) => {
                    digest.update([1]);
                    frame_u64(&mut digest, value.len() as u64);
                    digest.update(value);
                }
                None => digest.update([0]),
            }
            count = count.saturating_add(1);
        }
        frame_u64(&mut digest, count);
    }
    Ok(digest_hex(digest))
}

fn raw_target_sha256(connection: &Connection, source_root: &Path) -> Result<String, SnapshotError> {
    let root = source_root.to_string_lossy();
    let mut digest = Sha256::new();
    frame_str(&mut digest, "agent_bridge.authoritative_root_raw_rows.v0");
    for (table, columns) in [
        (
            "codebase_symbols",
            "id,file_path,line,col,kind,name,signature,language,root_path,indexed_at,embedding",
        ),
        (
            "codebase_imports",
            "id,file_path,line,language,raw,target,alias,root_path,indexed_at",
        ),
        (
            "codebase_calls",
            "id,file_path,line,language,caller,callee,root_path,indexed_at",
        ),
    ] {
        frame_str(&mut digest, table);
        let sql = format!("SELECT {columns} FROM {table} WHERE root_path = ?1 ORDER BY id");
        let mut statement = connection.prepare(&sql)?;
        let column_count = statement.column_count();
        let mut rows = statement.query([&root.as_ref()])?;
        let mut count = 0_u64;
        while let Some(row) = rows.next()? {
            hash_typed_row(&mut digest, row, column_count)?;
            count = count.saturating_add(1);
        }
        frame_u64(&mut digest, count);
    }
    Ok(digest_hex(digest))
}

fn all_codebase_sha256(connection: &Connection) -> Result<String, SnapshotError> {
    let mut digest = Sha256::new();
    frame_str(
        &mut digest,
        "agent_bridge.authoritative_all_codebase_raw_rows.v0",
    );
    for (table, columns) in [
        (
            "codebase_symbols",
            "id,file_path,line,col,kind,name,signature,language,root_path,indexed_at,embedding",
        ),
        (
            "codebase_imports",
            "id,file_path,line,language,raw,target,alias,root_path,indexed_at",
        ),
        (
            "codebase_calls",
            "id,file_path,line,language,caller,callee,root_path,indexed_at",
        ),
    ] {
        frame_str(&mut digest, table);
        let sql = format!("SELECT {columns} FROM {table} ORDER BY id");
        let mut statement = connection.prepare(&sql)?;
        let column_count = statement.column_count();
        let mut rows = statement.query([])?;
        let mut count = 0_u64;
        while let Some(row) = rows.next()? {
            hash_typed_row(&mut digest, row, column_count)?;
            count = count.saturating_add(1);
        }
        frame_u64(&mut digest, count);
    }
    Ok(digest_hex(digest))
}

fn sqlite_sequence_sha256(connection: &Connection) -> Result<String, SnapshotError> {
    let mut digest = Sha256::new();
    frame_str(&mut digest, "agent_bridge.sqlite_sequence.v0");
    let exists: i64 = connection.query_row(
        "SELECT COUNT(*) FROM sqlite_schema WHERE type='table' AND name='sqlite_sequence'",
        [],
        |row| row.get(0),
    )?;
    if exists == 0 {
        digest.update([0]);
        return Ok(digest_hex(digest));
    }
    digest.update([1]);
    let mut statement =
        connection.prepare("SELECT name, seq FROM sqlite_sequence ORDER BY name")?;
    let mut rows = statement.query([])?;
    let mut count = 0_u64;
    while let Some(row) = rows.next()? {
        frame_str(&mut digest, &row.get::<_, String>(0)?);
        let sequence: i64 = row.get(1)?;
        frame_u64(&mut digest, nonnegative_u64("sqlite_sequence", sequence)?);
        count = count.saturating_add(1);
    }
    frame_u64(&mut digest, count);
    Ok(digest_hex(digest))
}

fn hash_typed_row(
    digest: &mut Sha256,
    row: &rusqlite::Row<'_>,
    column_count: usize,
) -> Result<(), rusqlite::Error> {
    use rusqlite::types::ValueRef;

    for index in 0..column_count {
        match row.get_ref(index)? {
            ValueRef::Null => digest.update([0]),
            ValueRef::Integer(value) => {
                digest.update([1]);
                digest.update(value.to_be_bytes());
            }
            ValueRef::Real(value) => {
                digest.update([2]);
                digest.update(value.to_bits().to_be_bytes());
            }
            ValueRef::Text(value) => {
                digest.update([3]);
                frame_u64(digest, value.len() as u64);
                digest.update(value);
            }
            ValueRef::Blob(value) => {
                digest.update([4]);
                frame_u64(digest, value.len() as u64);
                digest.update(value);
            }
        }
    }
    Ok(())
}

fn other_root_sha256(connection: &Connection) -> Result<String, SnapshotError> {
    let mut digest = Sha256::new();
    frame_str(&mut digest, "agent_bridge.other_root_sentinel.v0");
    for (table, columns) in [
        (
            "codebase_symbols",
            "id,file_path,line,col,kind,name,signature,language,root_path,indexed_at,hex(embedding)",
        ),
        (
            "codebase_imports",
            "id,file_path,line,language,raw,target,COALESCE(alias,'<NULL>'),root_path,indexed_at",
        ),
        (
            "codebase_calls",
            "id,file_path,line,language,caller,callee,root_path,indexed_at",
        ),
    ] {
        frame_str(&mut digest, table);
        let sql = format!(
            "SELECT concat_ws('|',{columns}) FROM {table} WHERE root_path = ?1 ORDER BY id"
        );
        let mut statement = connection.prepare(&sql)?;
        let mut rows = statement.query([OTHER_ROOT])?;
        let mut count = 0_u64;
        while let Some(row) = rows.next()? {
            frame_str(&mut digest, &row.get::<_, String>(0)?);
            count = count.saturating_add(1);
        }
        frame_u64(&mut digest, count);
    }
    Ok(digest_hex(digest))
}

fn sentinel_sha256(connection: &Connection) -> Result<String, SnapshotError> {
    let value: String = connection.query_row(
        "SELECT concat_ws('|',key,kind,content,tags,related_keys,created_at,updated_at,last_accessed_at,access_count) \
         FROM memories WHERE key = ?1",
        [SENTINEL_KEY],
        |row| row.get(0),
    )?;
    let mut digest = Sha256::new();
    frame_str(&mut digest, "agent_bridge.non_codebase_sentinel.v0");
    frame_str(&mut digest, &value);
    Ok(digest_hex(digest))
}

fn sqlite_compile_options_sha256(connection: &Connection) -> Result<String, SnapshotError> {
    let mut options = Vec::new();
    let mut statement = connection.prepare("PRAGMA compile_options")?;
    let mut rows = statement.query([])?;
    while let Some(row) = rows.next()? {
        options.push(row.get::<_, String>(0)?);
    }
    options.sort();
    let mut digest = Sha256::new();
    frame_str(&mut digest, "agent_bridge.sqlite_compile_options.v0");
    frame_u64(&mut digest, options.len() as u64);
    for option in options {
        frame_str(&mut digest, &option);
    }
    Ok(digest_hex(digest))
}

fn semantic_digest(
    connection: &Connection,
    source_root: &Path,
) -> Result<crate::workload::SemanticReceipt, SnapshotError> {
    let mut semantic = SemanticAccumulator::new();
    let root = source_root.to_string_lossy();

    let mut symbols = connection.prepare(
        "SELECT file_path, line, col, kind, name, signature, language \
         FROM codebase_symbols WHERE root_path = ?1 \
         ORDER BY CAST(substr(file_path, length(file_path) - 10, 8) AS INTEGER), id",
    )?;
    let mut rows = symbols.query([&root.as_ref()])?;
    while let Some(row) = rows.next()? {
        let file_path: String = row.get(0)?;
        let virtual_path = virtual_path(source_root, &file_path)?;
        semantic.push_symbol_fields(
            &virtual_path,
            checked_u32("symbol line", row.get(1)?)?,
            checked_u32("symbol col", row.get(2)?)?,
            &row.get::<_, String>(3)?,
            &row.get::<_, String>(4)?,
            &row.get::<_, String>(5)?,
            &row.get::<_, String>(6)?,
        )?;
    }
    drop(rows);
    drop(symbols);

    let mut imports = connection.prepare(
        "SELECT file_path, line, language, raw, target, alias \
         FROM codebase_imports WHERE root_path = ?1 \
         ORDER BY CAST(substr(file_path, length(file_path) - 10, 8) AS INTEGER), id",
    )?;
    let mut rows = imports.query([&root.as_ref()])?;
    while let Some(row) = rows.next()? {
        let file_path: String = row.get(0)?;
        let virtual_path = virtual_path(source_root, &file_path)?;
        let alias: Option<String> = row.get(5)?;
        semantic.push_import_fields(
            &virtual_path,
            checked_u32("import line", row.get(1)?)?,
            &row.get::<_, String>(2)?,
            &row.get::<_, String>(3)?,
            &row.get::<_, String>(4)?,
            alias.as_deref(),
        )?;
    }
    drop(rows);
    drop(imports);

    let mut calls = connection.prepare(
        "SELECT file_path, line, language, caller, callee \
         FROM codebase_calls WHERE root_path = ?1 \
         ORDER BY CAST(substr(file_path, length(file_path) - 10, 8) AS INTEGER), id",
    )?;
    let mut rows = calls.query([&root.as_ref()])?;
    while let Some(row) = rows.next()? {
        let file_path: String = row.get(0)?;
        let virtual_path = virtual_path(source_root, &file_path)?;
        semantic.push_call_fields(
            &virtual_path,
            checked_u32("call line", row.get(1)?)?,
            &row.get::<_, String>(2)?,
            &row.get::<_, String>(3)?,
            &row.get::<_, String>(4)?,
        )?;
    }
    Ok(semantic.finish())
}

fn virtual_path(source_root: &Path, database_path: &str) -> Result<String, SnapshotError> {
    let relative = Path::new(database_path)
        .strip_prefix(source_root)
        .map_err(|_| SnapshotError::ForeignPath(database_path.to_string()))?;
    Ok(relative.to_string_lossy().replace('\\', "/"))
}

fn checked_u32(field: &'static str, value: i64) -> Result<u32, SnapshotError> {
    u32::try_from(value).map_err(|_| SnapshotError::NumericRange { field, value })
}

#[cfg(test)]
mod tests {
    use std::{
        ffi::OsString,
        os::unix::{ffi::OsStringExt, fs::symlink},
    };

    use super::*;

    #[test]
    fn sidecars_absent_preserves_non_utf8_database_path() -> Result<(), Box<dyn std::error::Error>>
    {
        let directory = tempfile::tempdir()?;
        let database_path = directory
            .path()
            .join(OsString::from_vec(b"state-\xff.db".to_vec()));
        let mut wal_path = database_path.as_os_str().to_os_string();
        wal_path.push("-wal");
        fs::write(PathBuf::from(wal_path), b"wal")?;

        assert!(!sidecars_absent(&database_path)?);
        Ok(())
    }

    #[test]
    fn sidecars_absent_propagates_metadata_errors() -> Result<(), Box<dyn std::error::Error>> {
        let directory = tempfile::tempdir()?;
        let blocking_file = directory.path().join("blocking-file");
        fs::write(&blocking_file, b"not a directory")?;
        let database_path = blocking_file.join("state.db");

        match sidecars_absent(&database_path) {
            Err(SnapshotError::Io(error)) if error.kind() == std::io::ErrorKind::NotADirectory => {
                Ok(())
            }
            outcome => panic!("expected ENOTDIR metadata error, got {outcome:?}"),
        }
    }

    #[test]
    fn reset_main_wal_propagates_sidecar_metadata_errors() -> Result<(), Box<dyn std::error::Error>>
    {
        let directory = tempfile::tempdir()?;
        let database_path = directory.path().join("state.db");
        let connection = Connection::open(&database_path)?;
        connection.execute_batch("CREATE TABLE witness (value INTEGER);")?;
        drop(connection);
        let wal_path = sqlite_sidecar_path(&database_path, "-wal");
        symlink(&wal_path, &wal_path)?;

        match reset_main_wal(&database_path) {
            Err(SnapshotError::Io(error)) if error.raw_os_error() == Some(libc::ELOOP) => Ok(()),
            outcome => panic!("expected ELOOP metadata error, got {outcome:?}"),
        }
    }
}
