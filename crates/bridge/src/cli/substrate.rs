use crate::seed_substrate as ab_seed_bridge;
use anyhow::{Context, Result};
use clap::Subcommand;
use serde_json::json;
use std::path::PathBuf;

#[derive(Subcommand, Debug)]
pub(crate) enum SubstrateOp {
    /// Print substrate config + (if installed) live stats. Output
    /// shows N / D / outer_dim / step_count / surprise / connection
    /// mean. JSON mode is machine-readable for forum / dream pipeline
    /// integration.
    ///
    /// **Phase 3 (C)**: also reads `substrate.parquet` when available
    /// (installed-substrate's configured path, or `--snapshot-path`
    /// override, or `default_snapshot_path()`) and reports total rows,
    /// hot vs long counts, latest Long/Hot step + ts + fingerprint, and
    /// file size — useful for cross-process determinism / freshness
    /// checks without needing `AB_SUBSTRATE=1` in the inspecting process.
    Stats {
        /// Override snapshot file path. Default: installed substrate's
        /// path, falling back to `default_snapshot_path()`.
        #[arg(long)]
        snapshot_path: Option<PathBuf>,
        /// Emit raw JSON instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **v22 Phase 3 (B)** — Replay a JSONL event log against a fresh
    /// in-process substrate, write the resulting `substrate.parquet`, and
    /// emit the SHA256 fingerprint of the latest Long row. Tool for v22
    /// §4 P5 (cross-machine determinism) — note that `NeuronGrid` currently
    /// uses `rand::thread_rng()` internally, so fingerprints differ across
    /// machines until the AiOT crate ships a seeded variant; `--seed` is
    /// reserved + logged but not yet effective.
    ///
    /// Event log: one JSON object per line, e.g.
    /// `{"text": "hello", "ts": 1700000000}`. Only `text` is required.
    /// `ts` and `kind` are informational; parse errors / empty lines are
    /// skipped with a warning.
    Replay {
        /// JSONL event log file. Each line `{text, ts?, kind?}`.
        #[arg(long)]
        log: PathBuf,
        /// RNG seed (reserved; logged but not yet effective — pending
        /// upstream AiOT seed_neuron::NeuronGrid::new_seeded support).
        #[arg(long, default_value_t = 0)]
        seed: u64,
        /// Grid size N. Default 256 (memo §3.3).
        #[arg(long, default_value_t = 256)]
        n: usize,
        /// Substrate dim D. Default 192 (memo §3.3 + post 56 PCA).
        #[arg(long, default_value_t = 192)]
        d: usize,
        /// Force HashBackend (deterministic encoder, no ONNX load).
        /// Default false → ONNX (encoder is deterministic on same hw).
        #[arg(long)]
        use_hash: bool,
        /// Output path for substrate.parquet. Default temp file.
        #[arg(long)]
        output: Option<PathBuf>,
        /// Emit JSON summary instead of pretty text.
        #[arg(long)]
        json: bool,
    },
    /// **v22 Phase 3 (A)** — Query substrate topology: for `--key K`,
    /// return up to `--k` other keys that the substrate's neuron(s)
    /// which fired on K connect to most strongly. Reads the latest Long
    /// snapshot row from `substrate.parquet` (no live install_default
    /// required) so short-lived CLI invocations get useful answers.
    Neighbors {
        /// Memory key to look up (must have been perceived by the
        /// substrate process that wrote the snapshot file).
        #[arg(long)]
        key: String,
        /// Max number of distinct neighbor keys to return.
        #[arg(long, default_value_t = 20)]
        k: usize,
        /// Override file path (default: `$HOME/.local/share/agent-bridge/substrate.parquet`).
        #[arg(long)]
        path: Option<PathBuf>,
        /// Emit raw JSON `[{"key":..., "score":...}]` for scripts.
        #[arg(long)]
        json: bool,
    },
    /// **Phase 2.2 read side** — Read rows from `substrate.parquet`
    /// without touching the in-process substrate (no install_default
    /// required). Useful for cross-process inspection, forum/dream
    /// pipeline, and G4 fingerprint comparisons across machines.
    Snapshot {
        /// Override file path (default: `$HOME/.local/share/agent-bridge/substrate.parquet`).
        #[arg(long)]
        path: Option<PathBuf>,
        /// Number of trailing rows to show (0 = all). Default 5.
        #[arg(long, default_value_t = 5)]
        limit: usize,
        /// Filter by tier (`hot` or `long`).
        #[arg(long)]
        tier: Option<String>,
        /// Print only the SHA256 fingerprint per row (one per line) —
        /// for cross-machine determinism compare (G4).
        #[arg(long)]
        fingerprint_only: bool,
        /// Emit JSON summary (omits bulk per-neuron arrays).
        #[arg(long)]
        json: bool,
    },
}

pub(crate) async fn run_substrate(op: &SubstrateOp) -> Result<()> {
    match op {
        SubstrateOp::Stats {
            snapshot_path,
            json,
        } => run_substrate_stats(snapshot_path.clone(), *json).await,
        SubstrateOp::Neighbors { key, k, path, json } => {
            run_substrate_neighbors(key.clone(), *k, path.clone(), *json).await
        }
        SubstrateOp::Replay {
            log,
            seed,
            n,
            d,
            use_hash,
            output,
            json,
        } => {
            run_substrate_replay(log.clone(), *seed, *n, *d, *use_hash, output.clone(), *json).await
        }
        SubstrateOp::Snapshot {
            path,
            limit,
            tier,
            fingerprint_only,
            json,
        } => {
            run_substrate_snapshot(path.clone(), *limit, tier.clone(), *fingerprint_only, *json)
                .await
        }
    }
}

/// **v22** — Substrate stats CLI. Reads the in-process global installed by
/// `ab_seed_bridge::install_default()`. If substrate is not installed (env
/// not set, or process didn't install), reports config + the disabled state
/// — useful for confirming env var spelling.
///
/// **Phase 3 (C)**: in addition, attempts to read `substrate.parquet`
/// from `path_override` → installed-substrate's path →
/// `default_snapshot_path()`, and reports row counts / latest fingerprints
/// / file size. Snapshot section appears in both pretty and JSON output
/// when a readable file is found.
async fn run_substrate_stats(path_override: Option<PathBuf>, as_json: bool) -> Result<()> {
    use ab_seed_bridge::snapshot;
    let env_on = ab_seed_bridge::env_enabled();
    let installed = ab_seed_bridge::current();
    let stats = installed.as_ref().map(|s| s.stats());

    let resolved_path: Option<PathBuf> = path_override
        .or_else(|| installed.as_ref().and_then(|s| s.snapshot_path()))
        .or_else(snapshot::default_snapshot_path);

    let snapshot_summary = match resolved_path.as_ref() {
        Some(p) if p.exists() => match snapshot::read_all(p) {
            Ok(rows) => {
                let bytes = std::fs::metadata(p).ok().map(|m| m.len());
                Some(summarize_snapshot_rows(p, bytes, &rows))
            }
            Err(e) => {
                eprintln!("warn: read substrate snapshot {}: {}", p.display(), e);
                None
            }
        },
        _ => None,
    };

    if as_json {
        let payload = json!({
            "env_var": ab_seed_bridge::SUBSTRATE_ENV_VAR,
            "env_enabled": env_on,
            "installed": stats.is_some(),
            "stats": stats,
            "snapshot_path": resolved_path.as_ref().map(|p| p.to_string_lossy()),
            "snapshot": snapshot_summary,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# v22 substrate stats");
    println!(
        "env: {var}={state}",
        var = ab_seed_bridge::SUBSTRATE_ENV_VAR,
        state = if env_on {
            "enabled"
        } else {
            "unset (substrate disabled)"
        }
    );
    match stats {
        Some(s) => {
            println!("backend (inner) : {}", s.backend_name);
            println!("projection      : {}", s.projection);
            println!("N (neurons)     : {}", s.n);
            println!("D (substrate)   : {}", s.d);
            println!("outer_dim       : {}", s.outer_dim);
            println!("step_count      : {}", s.step_count);
            println!(
                "last surprise   : mean={:.4} max={:.4}",
                s.last_surprise_mean, s.last_surprise_max
            );
            println!("|conn| mean     : {:.6}", s.connection_mean_abs);
            match resolved_path.as_ref() {
                Some(p) => println!("snapshot path   : {}", p.display()),
                None => println!("snapshot path   : (no path configured)"),
            }
            if s.step_count == 0 {
                println!();
                println!("(no perception events yet — substrate is opt-in to this process only;");
                println!(" trigger via memory_save / memory_search inside an MCP session with");
                println!(" `AB_SUBSTRATE=1` in env — phase 2.2 will append snapshot rows once");
                println!(" the cadence triggers (every 20 events / every 100 events or 6h))");
            }
        }
        None => {
            println!("not installed");
            match resolved_path.as_ref() {
                Some(p) => println!("(snapshot probe path: {})", p.display()),
                None => println!(),
            }
            if snapshot_summary.is_none() {
                println!("(set `AB_SUBSTRATE=1` in env and re-launch the long-lived process;");
                println!(" phase 2.2 ships snapshot persistence to");
                println!(" `$HOME/.local/share/agent-bridge/substrate.parquet`)");
            }
        }
    }
    if let Some(sum) = &snapshot_summary {
        println!();
        println!("# snapshot file");
        println!("file size       : {}", human_bytes(sum.file_bytes));
        println!(
            "rows            : total={} hot={} long={}",
            sum.total_rows, sum.hot_rows, sum.long_rows
        );
        match &sum.latest_long {
            Some(li) => println!(
                "latest Long     : step={} ts={} fp={}",
                li.step, li.cycle_ts, li.fingerprint
            ),
            None => println!("latest Long     : (none)"),
        }
        match &sum.latest_hot {
            Some(hi) => println!(
                "latest Hot      : step={} ts={} fp={}",
                hi.step, hi.cycle_ts, hi.fingerprint
            ),
            None => println!("latest Hot      : (none)"),
        }
    }
    Ok(())
}

/// Phase 3 (C) snapshot summary returned from `summarize_snapshot_rows`.
/// Exposed as serde for the JSON payload of `substrate stats`.
#[derive(Debug, Clone, serde::Serialize)]
struct SnapshotSummary {
    path: String,
    file_bytes: Option<u64>,
    total_rows: usize,
    hot_rows: usize,
    long_rows: usize,
    latest_hot: Option<SnapshotEntry>,
    latest_long: Option<SnapshotEntry>,
}

#[derive(Debug, Clone, serde::Serialize)]
struct SnapshotEntry {
    step: i64,
    cycle_ts: i64,
    fingerprint: String,
}

/// Build a [`SnapshotSummary`] from `read_all` rows. Pure helper, tested.
fn summarize_snapshot_rows(
    path: &std::path::Path,
    file_bytes: Option<u64>,
    rows: &[ab_seed_bridge::SnapshotRow],
) -> SnapshotSummary {
    use ab_seed_bridge::{snapshot, SnapshotTier};
    let mut hot_rows = 0usize;
    let mut long_rows = 0usize;
    for r in rows {
        match r.tier {
            SnapshotTier::Hot => hot_rows += 1,
            SnapshotTier::Long => long_rows += 1,
        }
    }
    let latest_hot = rows
        .iter()
        .rev()
        .find(|r| matches!(r.tier, SnapshotTier::Hot))
        .map(|r| SnapshotEntry {
            step: r.step,
            cycle_ts: r.cycle_ts,
            fingerprint: snapshot::fingerprint(r),
        });
    let latest_long = rows
        .iter()
        .rev()
        .find(|r| matches!(r.tier, SnapshotTier::Long))
        .map(|r| SnapshotEntry {
            step: r.step,
            cycle_ts: r.cycle_ts,
            fingerprint: snapshot::fingerprint(r),
        });
    SnapshotSummary {
        path: path.to_string_lossy().to_string(),
        file_bytes,
        total_rows: rows.len(),
        hot_rows,
        long_rows,
        latest_hot,
        latest_long,
    }
}

/// Human-readable byte size for `Option<u64>`. Returns `"(unknown)"` for None.
fn human_bytes(b: Option<u64>) -> String {
    match b {
        None => "(unknown)".to_string(),
        Some(n) if n < 1024 => format!("{} B", n),
        Some(n) if n < 1024 * 1024 => format!("{:.1} KiB", n as f64 / 1024.0),
        Some(n) if n < 1024 * 1024 * 1024 => {
            format!("{:.1} MiB", n as f64 / (1024.0 * 1024.0))
        }
        Some(n) => format!("{:.2} GiB", n as f64 / (1024.0 * 1024.0 * 1024.0)),
    }
}

/// **v22 Phase 3 (A)** — `substrate neighbors` CLI. Loads the most recent
/// Long-tier row from `substrate.parquet` and runs
/// [`ab_seed_bridge::neighbors_from_snapshot`] against it. Pure disk read,
/// no `install_default()` — CLI is short-lived so a fresh in-process grid
/// would always be empty; reading the snapshot is the only way to answer.
///
/// When the snapshot file is missing or has no Long row yet, output is
/// empty (still exit 0). MCP `substrate_neighbors_of` is the live-grid
/// counterpart for in-daemon queries.
async fn run_substrate_neighbors(
    key: String,
    k: usize,
    path_override: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    use ab_seed_bridge::snapshot::{self, SnapshotTier};
    let path = match path_override.or_else(snapshot::default_snapshot_path) {
        Some(p) => p,
        None => {
            if as_json {
                println!(
                    "{}",
                    serde_json::json!({"neighbors": [], "reason": "no snapshot path"})
                );
            } else {
                println!("# v22 substrate neighbors");
                println!("(no snapshot path configured; rerun with --path)");
            }
            return Ok(());
        }
    };
    if !path.exists() {
        if as_json {
            println!(
                "{}",
                serde_json::json!({
                    "neighbors": [],
                    "reason": "snapshot file missing",
                    "path": path.to_string_lossy(),
                })
            );
        } else {
            println!("# v22 substrate neighbors");
            println!("(snapshot file not found at {})", path.to_string_lossy());
        }
        return Ok(());
    }
    let rows = snapshot::read_all(&path)
        .with_context(|| format!("read substrate snapshot {}", path.display()))?;
    let latest_long = rows
        .iter()
        .rev()
        .find(|r| matches!(r.tier, SnapshotTier::Long));
    let neighbors = match latest_long {
        Some(row) => ab_seed_bridge::neighbors_from_snapshot(row, &key, k),
        None => Vec::new(),
    };
    if as_json {
        let payload: Vec<_> = neighbors
            .iter()
            .map(|(k_text, score)| serde_json::json!({"key": k_text, "score": score}))
            .collect();
        println!(
            "{}",
            serde_json::to_string_pretty(&serde_json::json!({
                "key": key,
                "k": k,
                "row_step": latest_long.map(|r| r.step),
                "row_ts": latest_long.map(|r| r.cycle_ts),
                "neighbors": payload,
            }))?
        );
        return Ok(());
    }
    println!("# v22 substrate neighbors of {}", key);
    match latest_long {
        Some(row) => println!("(source: snapshot step={} ts={})", row.step, row.cycle_ts),
        None => {
            println!("(no Long-tier snapshot row yet — substrate needs ≥100 perception events)")
        }
    }
    if neighbors.is_empty() {
        println!("(no neighbors)");
    } else {
        for (i, (k_text, score)) in neighbors.iter().enumerate() {
            println!("{:>3}. {:.6}  {}", i + 1, score, k_text);
        }
    }
    Ok(())
}

/// **v22 Phase 3 (B)** — `substrate replay` CLI. Reads a JSONL event log,
/// runs each event through a fresh in-process `SeedBackend`, force-writes
/// a final Long-tier snapshot, and emits the SHA256 fingerprint of that
/// row. Tool for v22 §4 P5 cross-machine determinism.
///
/// **Determinism caveat**: `seed_neuron::NeuronGrid::new` and `step` both
/// use `rand::thread_rng()`, so fingerprints will differ across runs (and
/// across machines) until the AiOT crate exposes a seeded variant.
/// `--seed` is reserved and emitted in the JSON output so once the
/// upstream supports it, this CLI becomes a true determinism gate.
async fn run_substrate_replay(
    log_path: PathBuf,
    seed: u64,
    n: usize,
    d: usize,
    use_hash: bool,
    output_override: Option<PathBuf>,
    as_json: bool,
) -> Result<()> {
    use ab_seed_bridge::snapshot::{self, SnapshotTier};
    use ab_seed_bridge::{SeedBackend, SubstrateConfig};
    use ab_store::embedding::{EmbeddingBackend, HashBackend, OnnxBackend};
    use std::sync::Arc;

    // --- 1. Parse event log ---
    // P-γ: each event is (text_to_embed, key_to_perceive_opt). When key
    // is None we fall back to text (backward-compat with pre-P-γ replay
    // JSONL that only carried `text`). Production-style replays should
    // include `key` so substrate.neighbors_of(memory_key) is queryable.
    let raw = std::fs::read_to_string(&log_path)
        .with_context(|| format!("read event log {}", log_path.display()))?;
    let mut events: Vec<(String, String)> = Vec::new();
    let mut parse_skips = 0u64;
    for line in raw.lines() {
        match parse_event_line(line) {
            Some((text, key_opt)) => {
                let key = key_opt.unwrap_or_else(|| text.clone());
                events.push((text, key));
            }
            None => parse_skips += 1,
        }
    }

    // --- 2. Prepare output path ---
    let output: PathBuf = match output_override {
        Some(p) => p,
        None => {
            let mut p = std::env::temp_dir();
            p.push(format!(
                "agent-bridge-replay-{}.parquet",
                std::process::id()
            ));
            p
        }
    };
    if output.exists() {
        std::fs::remove_file(&output)
            .with_context(|| format!("clearing prior replay output at {}", output.display()))?;
    }

    // --- 3. Build SeedBackend on chosen inner backend ---
    let inner: Arc<dyn EmbeddingBackend> = if use_hash {
        Arc::new(HashBackend)
    } else {
        Arc::new(OnnxBackend)
    };
    let cfg = SubstrateConfig {
        n,
        d,
        state_noise: 0.01,
        lr: 0.01,
    };
    let backend = SeedBackend::wrap_with(inner, cfg);
    backend.set_snapshot_path(Some(output.clone()));

    // --- 4. Replay ---
    // P-γ: perceive(text, key) lets the substrate index by key while
    // embedding text — falls back to embed-equivalent behaviour when
    // event omitted `key` (key=text via the parse step above).
    for (text, key) in &events {
        let _ = backend.perceive(text, key);
    }
    let stats = backend.stats();

    // --- 5. Force a final Long snapshot (so cross-machine compare always has a target) ---
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let final_fp = match backend.build_row(SnapshotTier::Long, now) {
        Some(row) => match snapshot::append_row(&output, row) {
            Ok(fp) => Some(fp),
            Err(e) => {
                eprintln!("warn: forced Long snapshot append failed: {e}");
                None
            }
        },
        None => None,
    };

    // --- 6. Re-read snapshot to count rows + latest fingerprint ---
    let rows = snapshot::read_all(&output).unwrap_or_default();
    let latest_long = rows
        .iter()
        .rev()
        .find(|r| matches!(r.tier, SnapshotTier::Long));
    let latest_long_fp = latest_long.map(snapshot::fingerprint);

    let warnings = vec![
        "NeuronGrid::new / step use rand::thread_rng() — cross-machine sha256 will differ"
            .to_string(),
        format!("--seed {seed} logged but not yet effective (AiOT crate pending)"),
    ];

    if as_json {
        let payload = serde_json::json!({
            "log_path": log_path.to_string_lossy(),
            "events_parsed": events.len(),
            "events_skipped": parse_skips,
            "step_count_final": stats.step_count,
            "seed": seed,
            "n": n,
            "d": d,
            "encoder": if use_hash { "hash" } else { "onnx" },
            "snapshot_path": output.to_string_lossy(),
            "snapshot_rows": rows.len(),
            "latest_long_fingerprint": latest_long_fp,
            "forced_final_fingerprint": final_fp,
            "rng_determinism": false,
            "warnings": warnings,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# v22 Phase 3 (B) — substrate replay");
    println!("log              : {}", log_path.display());
    println!(
        "events           : parsed={} skipped={}",
        events.len(),
        parse_skips
    );
    println!(
        "config           : n={n}  d={d}  encoder={}",
        if use_hash { "hash" } else { "onnx" }
    );
    println!("seed (reserved)  : {seed}");
    println!("snapshot         : {}", output.display());
    println!("snapshot rows    : {}", rows.len());
    match (&latest_long_fp, &final_fp) {
        (Some(fp), _) => println!("latest Long fp   : {}", fp),
        (None, Some(fp)) => println!("forced final fp  : {}", fp),
        (None, None) => println!("(no Long row produced)"),
    }
    println!("step_count       : {}", stats.step_count);
    println!();
    println!("Warnings:");
    for w in &warnings {
        println!("  - {w}");
    }
    Ok(())
}

/// Parse one JSONL event line. Returns `Some((text, key_opt))` when the
/// line is a JSON object with a non-empty `text` string field; `None`
/// for blank lines, parse errors, or missing-field lines.
///
/// **P-γ** — optional `key` field carries the perception identifier
/// (memory key in production semantics). When absent, falls back to
/// `text` as both embedded content AND perceived identifier, matching
/// pre-P-γ replay behaviour for backward compat.
///
/// Pure helper, used by `run_substrate_replay`.
fn parse_event_line(line: &str) -> Option<(String, Option<String>)> {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return None;
    }
    let v: serde_json::Value = serde_json::from_str(trimmed).ok()?;
    let text = v.get("text")?.as_str()?;
    if text.is_empty() {
        return None;
    }
    let key = v
        .get("key")
        .and_then(|k| k.as_str())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());
    Some((text.to_string(), key))
}

/// **v22 Phase 2.2 read side** — `substrate snapshot` CLI. Reads the
/// Parquet file written by long-lived substrate-enabled processes. Pure
/// disk read, no `install_default()` needed — this is the asymmetric
/// counterpart to `substrate stats` (which queries the in-process global).
///
/// Use cases:
/// 1. Inspect what a *different* process has been learning ("forum
///    pipeline can read what MCP saw").
/// 2. Cross-machine fingerprint compare for G4 determinism gate
///    (`--fingerprint-only` then `diff` two outputs).
/// 3. Forum/dream offline analysis of trailing surprise trends.
async fn run_substrate_snapshot(
    path_override: Option<PathBuf>,
    limit: usize,
    tier_filter: Option<String>,
    fingerprint_only: bool,
    as_json: bool,
) -> Result<()> {
    use anyhow::anyhow;

    let path = path_override
        .or_else(ab_seed_bridge::snapshot::default_snapshot_path)
        .ok_or_else(|| anyhow!("no $HOME — pass --path explicitly"))?;

    let mut rows = ab_seed_bridge::snapshot::read_all(&path)
        .map_err(|e| anyhow!("read {}: {}", path.display(), e))?;

    if let Some(t) = tier_filter.as_deref() {
        let want = ab_seed_bridge::snapshot::SnapshotTier::from_str(t)
            .ok_or_else(|| anyhow!("unknown tier '{t}' — expected hot|long"))?;
        rows.retain(|r| r.tier == want);
    }

    if limit > 0 && rows.len() > limit {
        let skip = rows.len() - limit;
        rows = rows.into_iter().skip(skip).collect();
    }

    if fingerprint_only {
        for row in &rows {
            println!("{}", ab_seed_bridge::snapshot::fingerprint(row));
        }
        return Ok(());
    }

    if as_json {
        let payload: Vec<_> = rows
            .iter()
            .map(|r| {
                json!({
                    "step": r.step,
                    "cycle_ts": r.cycle_ts,
                    "tier": r.tier.as_str(),
                    "n_alive": r.n_alive,
                    "trailing_surprise_mean_short": r.trailing_surprise_mean_short,
                    "trailing_surprise_mean_long": r.trailing_surprise_mean_long,
                    "connection_logits_len": r.connection_logits.len(),
                    "in_strengths_mean": mean_f32(&r.in_strengths),
                    "fingerprint": ab_seed_bridge::snapshot::fingerprint(r),
                })
            })
            .collect();
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "path": path.display().to_string(),
                "rows_shown": payload.len(),
                "rows": payload,
            }))?
        );
        return Ok(());
    }

    println!("# v22 substrate snapshot");
    println!("path : {}", path.display());
    if rows.is_empty() {
        println!("(no rows yet — file absent or empty)");
        return Ok(());
    }
    println!("rows : {} shown", rows.len());
    println!();
    for r in &rows {
        let fp = ab_seed_bridge::snapshot::fingerprint(r);
        let fp_short = if fp.len() >= 16 {
            &fp[..16]
        } else {
            fp.as_str()
        };
        println!(
            "step={:<6} ts={} tier={:<4} n_alive={:<4} surprise(s/l)={:.4}/{:.4} logits={:<6} fp={}",
            r.step,
            r.cycle_ts,
            r.tier.as_str(),
            r.n_alive,
            r.trailing_surprise_mean_short,
            r.trailing_surprise_mean_long,
            r.connection_logits.len(),
            fp_short,
        );
    }
    Ok(())
}

fn mean_f32(xs: &[f32]) -> f32 {
    if xs.is_empty() {
        0.0
    } else {
        xs.iter().sum::<f32>() / xs.len() as f32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Phase 3 (C): summarize_snapshot_rows + human_bytes ──────────────

    use ab_seed_bridge::{SnapshotRow, SnapshotTier};
    use std::path::Path;

    fn make_row(step: i64, ts: i64, tier: SnapshotTier) -> SnapshotRow {
        SnapshotRow {
            step,
            cycle_ts: ts,
            tier,
            n_alive: 2,
            in_strengths: vec![0.1, 0.2],
            last_perceived_key: vec!["a".into(), "b".into()],
            last_perceived_ts: vec![ts, ts],
            trailing_surprise_mean_short: 0.5,
            trailing_surprise_mean_long: 0.5,
            connection_logits: if matches!(tier, SnapshotTier::Long) {
                vec![0.0, 0.0]
            } else {
                Vec::new()
            },
        }
    }

    fn assert_snapshot_fingerprint_contract(fingerprint: &str) {
        let is_sha256_hex = fingerprint.len() == 64
            && fingerprint
                .chars()
                .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase());
        let is_disabled_stub = fingerprint.starts_with("seed-substrate-disabled-");
        assert!(
            is_sha256_hex || is_disabled_stub,
            "unexpected snapshot fingerprint shape: {fingerprint}"
        );
    }

    #[test]
    fn summarize_snapshot_rows_empty_returns_zero_counts() {
        let p = Path::new("/tmp/none.parquet");
        let sum = summarize_snapshot_rows(p, Some(0), &[]);
        assert_eq!(sum.total_rows, 0);
        assert_eq!(sum.hot_rows, 0);
        assert_eq!(sum.long_rows, 0);
        assert!(sum.latest_hot.is_none());
        assert!(sum.latest_long.is_none());
        assert_eq!(sum.path, "/tmp/none.parquet");
    }

    #[test]
    fn summarize_snapshot_rows_mixed_counts_and_latest_per_tier() {
        // 5 rows interleaved hot/long. Latest hot at step=80; latest long at step=100.
        let p = Path::new("/tmp/x.parquet");
        let rows = vec![
            make_row(20, 1000, SnapshotTier::Hot),
            make_row(40, 2000, SnapshotTier::Hot),
            make_row(60, 3000, SnapshotTier::Hot),
            make_row(80, 4000, SnapshotTier::Hot),
            make_row(100, 5000, SnapshotTier::Long),
        ];
        let sum = summarize_snapshot_rows(p, Some(12345), &rows);
        assert_eq!(sum.total_rows, 5);
        assert_eq!(sum.hot_rows, 4);
        assert_eq!(sum.long_rows, 1);
        assert_eq!(sum.file_bytes, Some(12345));
        let latest_hot = sum.latest_hot.expect("latest hot");
        assert_eq!(latest_hot.step, 80);
        assert_eq!(latest_hot.cycle_ts, 4000);
        assert_snapshot_fingerprint_contract(&latest_hot.fingerprint);
        let latest_long = sum.latest_long.expect("latest long");
        assert_eq!(latest_long.step, 100);
        assert_eq!(latest_long.cycle_ts, 5000);
        assert_snapshot_fingerprint_contract(&latest_long.fingerprint);
    }

    #[test]
    fn summarize_snapshot_rows_picks_last_per_tier_not_first() {
        // Two Long rows; latest_long must be the later one (rev iteration).
        let p = Path::new("/tmp/y.parquet");
        let rows = vec![
            make_row(100, 5000, SnapshotTier::Long),
            make_row(200, 6000, SnapshotTier::Long),
        ];
        let sum = summarize_snapshot_rows(p, None, &rows);
        assert_eq!(sum.long_rows, 2);
        let latest = sum.latest_long.expect("latest");
        assert_eq!(latest.step, 200);
    }

    #[test]
    fn human_bytes_renders_units_correctly() {
        assert_eq!(human_bytes(None), "(unknown)");
        assert_eq!(human_bytes(Some(0)), "0 B");
        assert_eq!(human_bytes(Some(512)), "512 B");
        assert_eq!(human_bytes(Some(1024)), "1.0 KiB");
        assert_eq!(human_bytes(Some(2048)), "2.0 KiB");
        assert_eq!(human_bytes(Some(1024 * 1024)), "1.0 MiB");
        assert_eq!(human_bytes(Some(3 * 1024 * 1024 * 1024)), "3.00 GiB");
    }

    // ── Phase 3 (B): parse_event_line unit tests ─────────────────────────

    #[test]
    fn parse_event_line_happy_path_returns_text() {
        let got = parse_event_line(r#"{"text":"hello world"}"#);
        assert_eq!(got, Some(("hello world".to_string(), None)));
    }

    #[test]
    fn parse_event_line_with_ts_and_kind_ignores_extras() {
        let got = parse_event_line(r#"{"text":"foo","ts":1700000000,"kind":"save"}"#);
        assert_eq!(got, Some(("foo".to_string(), None)));
    }

    #[test]
    fn parse_event_line_blank_returns_none() {
        assert!(parse_event_line("").is_none());
        assert!(parse_event_line("   \t  ").is_none());
    }

    #[test]
    fn parse_event_line_malformed_returns_none() {
        // Garbage JSON, missing text field, text=null, text="" all → None.
        assert!(parse_event_line("not json").is_none());
        assert!(parse_event_line(r#"{"ts":1}"#).is_none());
        assert!(parse_event_line(r#"{"text":null}"#).is_none());
        assert!(parse_event_line(r#"{"text":""}"#).is_none());
        // text not a string
        assert!(parse_event_line(r#"{"text":42}"#).is_none());
    }

    // P-γ: optional `key` field carries perception identifier.
    #[test]
    fn parse_event_line_with_key_returns_text_and_key() {
        let got = parse_event_line(r#"{"text":"content body","key":"memory_key_42"}"#);
        assert_eq!(
            got,
            Some((
                "content body".to_string(),
                Some("memory_key_42".to_string())
            ))
        );
    }

    #[test]
    fn parse_event_line_empty_key_falls_back_to_none() {
        // Empty key string is treated as absent so caller defaults to text.
        let got = parse_event_line(r#"{"text":"hello","key":""}"#);
        assert_eq!(got, Some(("hello".to_string(), None)));
    }
}
