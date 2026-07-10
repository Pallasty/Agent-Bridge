//! Tiered embedding delegation — [`RemoteEmbedBackend`].
//!
//! An MCP (or CLI one-shot) process can delegate embedding to a shared backend
//! service instead of loading its own copy of the ONNX model. Measured: a local
//! gte load costs ~2.78GB private footprint per process (a hash-backend process
//! is ~13MB — the model is 99.5% of the weight). A process that delegates drops
//! to the ~15MB floor. With 8+ concurrent sessions this is the difference
//! between ~22GB (machine freeze) and ~3GB (one shared model in the daemon).
//!
//! This is the reference implementation of the tiered backend pattern: the same
//! [`ab_store::EmbeddingBackend`] trait abstracts WHERE the heavy work runs.
//! [`RemoteEmbedBackend::embed`] POSTs to a `/embed` endpoint — Tier 2 = the
//! localhost daemon-http service today (~0.24ms IPC overhead, dwarfed by the
//! 11–99ms inference that happens regardless of location); the same code reaches
//! a Tier 3 cloud endpoint by pointing the URL elsewhere. Per-tier graceful
//! degradation is built in: if the remote is unreachable, it falls back to a
//! local in-process embed, so correctness is never sacrificed for RAM sharing.
//!
//! Role-scoped install: delegating roles call [`install_if_configured`] — the MCP
//! arm always, and the `daemon` arm opt-in when AGENT_BRIDGE_EMBED_REMOTE_URL points
//! at the shared daemon-http /embed (so the writer shares one model copy instead of
//! loading its own ~1.2GB ONNX). daemon-http IS the embedding server and must NEVER
//! delegate — its arm does not call this, so even when it inherits the same env it
//! cannot self-loop into its own /embed.

use std::sync::{Arc, OnceLock};
use std::time::Duration;

use ab_store::EmbeddingBackend;

/// Env var holding the `/embed` endpoint URL to delegate to. When set in a
/// delegating (MCP) process, embedding is routed there instead of loading a
/// local model. Unset/blank = current behavior (local in-process embedding).
pub const REMOTE_URL_ENV: &str = "AGENT_BRIDGE_EMBED_REMOTE_URL";

const CONNECT_TIMEOUT: Duration = Duration::from_secs(1);
// embed() is sync and runs on a tokio worker thread (called from the async
// memory_save path); ureq blocks that thread for the request duration. The
// happy path is ~11–100ms (measured), so a short read timeout bounds how long a
// wedged daemon can block a worker before we fall back to local embedding.
const READ_TIMEOUT: Duration = Duration::from_secs(5);

/// A backend that delegates embedding to a remote `/embed` HTTP service,
/// falling back to a local in-process embed if the service is unreachable.
pub struct RemoteEmbedBackend {
    url: String,
    agent: ureq::Agent,
    /// Local backend used only when the remote is unreachable. `OnnxBackend` in
    /// production (zero-sized; loads the model lazily on first use, i.e. only in
    /// the degraded path). Injectable for tests.
    fallback: Arc<dyn EmbeddingBackend>,
    /// Daemon-reported model name + dim, learned from the first successful
    /// response. Until then [`name`]/[`dim`] mirror the compiled default, which
    /// matches the daemon by construction (both run the same compiled default).
    learned_name: OnceLock<String>,
    learned_dim: OnceLock<usize>,
    warned_fallback: OnceLock<()>,
}

impl RemoteEmbedBackend {
    /// Construct with the production fallback (`OnnxBackend` — local model load
    /// only if the remote is down).
    pub fn new(url: String) -> Self {
        Self::with_fallback(url, Arc::new(ab_store::OnnxBackend))
    }

    /// Construct with an explicit fallback backend (tests inject `HashBackend`
    /// to avoid loading the real model).
    pub fn with_fallback(url: String, fallback: Arc<dyn EmbeddingBackend>) -> Self {
        let agent = ureq::AgentBuilder::new()
            .timeout_connect(CONNECT_TIMEOUT)
            .timeout_read(READ_TIMEOUT)
            .build();
        Self {
            url,
            agent,
            fallback,
            learned_name: OnceLock::new(),
            learned_dim: OnceLock::new(),
            warned_fallback: OnceLock::new(),
        }
    }

    /// POST the text to the remote `/embed`; return the vector on success.
    /// Uses `send_string` + manual JSON so ureq's `json` feature isn't required.
    fn try_remote(&self, text: &str) -> Option<Vec<f32>> {
        let payload = serde_json::json!({ "text": text }).to_string();
        let resp = self
            .agent
            .post(&self.url)
            .set("Content-Type", "application/json")
            .send_string(&payload)
            .ok()?;
        let body = resp.into_string().ok()?;
        let (name, dim, vec) = parse_embed_response(&body)?;
        if vec.is_empty() {
            return None;
        }
        let _ = self.learned_name.set(name);
        let _ = self.learned_dim.set(dim);
        Some(vec)
    }

    /// Best-effort: probe the daemon once at startup so [`name`]/[`dim`] are
    /// authoritative (the daemon's actual model) from the FIRST `memory_save`,
    /// not the local compiled default. The tag-write path reads `name()` BEFORE
    /// the first real embed, so without this probe an early save in a process
    /// whose local default differs from the daemon would be mis-tagged. Silent
    /// no-op if the daemon is unreachable at startup — values are then learned
    /// lazily from the first real embed.
    pub fn learn_from_daemon_best_effort(&self) {
        let _ = self.try_remote("warmup");
    }

    fn warn_fallback_once(&self) {
        if self.warned_fallback.set(()).is_ok() {
            tracing::warn!(
                url = %self.url,
                "RemoteEmbedBackend: remote /embed unreachable — falling back to local \
                 in-process embedding (this process now loads the model locally). \
                 Embedding correctness preserved; RAM sharing degraded until the \
                 service returns."
            );
        }
    }
}

impl EmbeddingBackend for RemoteEmbedBackend {
    fn name(&self) -> &str {
        // Prefer the daemon's reported model name (so `embedding_backend` tags
        // match what actually produced the vector); fall back to the compiled
        // default, which equals the daemon's model by construction. (Explicit
        // match, not unwrap_or_else: the fallback's &'static must not over-
        // constrain the learned-name borrow to 'static.)
        match self.learned_name.get() {
            Some(s) => s.as_str(),
            None => ab_store::active_model_name(),
        }
    }

    fn dim(&self) -> usize {
        self.learned_dim
            .get()
            .copied()
            .unwrap_or_else(ab_store::vector_dim)
    }

    fn embed(&self, text: &str) -> Vec<f32> {
        if let Some(v) = self.try_remote(text) {
            return v;
        }
        // Per-tier graceful degradation: remote down → local in-process embed.
        // The fallback's model loads lazily here, ONLY in this degraded path; a
        // reachable remote never triggers a local model load.
        self.warn_fallback_once();
        self.fallback.embed(text)
    }

    fn embed_batch(&self, texts: &[&str]) -> Vec<Vec<f32>> {
        // No `/embed_batch` endpoint yet (v0 keeps the shape minimal). One POST
        // per row; the IPC (~0.24ms each) is noise vs inference. A future
        // `/embed_batch` can amortize the per-row inference. If ANY row falls
        // back, the whole batch goes local to keep the backend consistent.
        let mut out = Vec::with_capacity(texts.len());
        for t in texts {
            match self.try_remote(t) {
                Some(v) => out.push(v),
                None => {
                    self.warn_fallback_once();
                    return self.fallback.embed_batch(texts);
                }
            }
        }
        out
    }
}

/// Parse a `/embed` JSON response `{embedding:[..], backend:"..", dim:N}`.
/// Returns `(backend_name, dim, vector)`. Pure — unit-tested.
pub fn parse_embed_response(body: &str) -> Option<(String, usize, Vec<f32>)> {
    let v: serde_json::Value = serde_json::from_str(body).ok()?;
    let arr = v.get("embedding")?.as_array()?;
    let vec: Vec<f32> = arr
        .iter()
        .filter_map(|x| x.as_f64().map(|f| f as f32))
        .collect();
    if vec.len() != arr.len() {
        return None; // a non-numeric element snuck in → reject the whole response
    }
    let dim = v
        .get("dim")
        .and_then(|d| d.as_u64())
        .map(|d| d as usize)
        .unwrap_or(vec.len());
    // Reject a response whose declared dim disagrees with the actual vector
    // length — storing such a vector would mislabel its dimension and corrupt
    // dim-guard / cosine math. A mismatch falls back to local embedding.
    if dim != vec.len() {
        return None;
    }
    let name = match v.get("backend").and_then(|b| b.as_str()) {
        Some(s) => s.to_string(),
        None => ab_store::active_model_name().to_string(),
    };
    Some((name, dim, vec))
}

/// Trim/normalize a raw URL value: `None` for unset/blank. Pure — unit-tested.
fn normalize_url(raw: Option<String>) -> Option<String> {
    raw.map(|s| s.trim().to_string()).filter(|s| !s.is_empty())
}

/// Resolve the delegation target from [`REMOTE_URL_ENV`]. `None` = delegation off.
pub fn remote_url_from_env() -> Option<String> {
    normalize_url(std::env::var(REMOTE_URL_ENV).ok())
}

/// Set ONLY when delegation is actively installed in THIS process (via
/// [`install_if_configured`] from the MCP startup path). Role-safe gate for
/// other local-embedding entry points (e.g. the `embed_text` tool's raw
/// encoder): it is never set in daemon / daemon-http processes, so delegating
/// off this flag cannot self-loop into the daemon's own `/embed`.
static ACTIVE_URL: OnceLock<String> = OnceLock::new();

/// The active delegation URL, or `None` if this process embeds locally. Used by
/// other raw-encoder entry points to delegate consistently without re-reading
/// the env (which would NOT be role-scoped and could self-loop in the daemon).
pub fn active_remote_url() -> Option<String> {
    ACTIVE_URL.get().cloned()
}

/// Outcome of [`install_if_configured`], for caller logging.
pub enum InstallOutcome {
    /// Delegation installed; the daemon `/embed` URL.
    Installed(String),
    /// `AGENT_BRIDGE_EMBED_REMOTE_URL` unset/blank — local embedding (default).
    NotConfigured,
    /// A default backend was already installed (e.g. substrate) — delegation skipped.
    AlreadyInitialized,
}

/// Install [`RemoteEmbedBackend`] as the process default IFF [`REMOTE_URL_ENV`]
/// is set. Call from delegating roles (MCP / CLI one-shot, and the opt-in `daemon`
/// arm) BEFORE the first `default_backend()` / `warmup()`. daemon-http MUST NOT
/// call this — it is the embedding server and would self-delegate into a loop.
pub fn install_if_configured() -> InstallOutcome {
    let Some(url) = remote_url_from_env() else {
        return InstallOutcome::NotConfigured;
    };
    let backend = RemoteEmbedBackend::new(url.clone());
    // Learn the daemon's model name/dim now, so the first memory_save tags
    // correctly (name() is read before the first real embed).
    backend.learn_from_daemon_best_effort();
    match ab_store::set_default_backend(Arc::new(backend)) {
        Ok(()) => {
            let _ = ACTIVE_URL.set(url.clone());
            InstallOutcome::Installed(url)
        }
        Err(_) => InstallOutcome::AlreadyInitialized,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_store::{EmbeddingBackend, HashBackend};

    #[test]
    fn parse_embed_response_extracts_vector_name_dim() {
        let body = r#"{"embedding":[0.1,0.2,0.3],"backend":"gte-multilingual-base","dim":3}"#;
        let (name, dim, vec) = parse_embed_response(body).expect("parse");
        assert_eq!(name, "gte-multilingual-base");
        assert_eq!(dim, 3);
        assert_eq!(vec.len(), 3);
        assert!((vec[0] - 0.1).abs() < 1e-6);
    }

    #[test]
    fn parse_embed_response_rejects_malformed() {
        assert!(parse_embed_response("not json").is_none());
        assert!(parse_embed_response("{}").is_none());
        // embedding present but a non-numeric element → reject (don't silently drop)
        assert!(parse_embed_response(r#"{"embedding":[0.1,"x"]}"#).is_none());
    }

    #[test]
    fn parse_embed_response_defaults_dim_to_vec_len() {
        let (_, dim, vec) =
            parse_embed_response(r#"{"embedding":[0.1,0.2],"backend":"m"}"#).unwrap();
        assert_eq!(dim, 2);
        assert_eq!(vec.len(), 2);
    }

    #[test]
    fn parse_embed_response_rejects_dim_length_mismatch() {
        // Declared dim disagrees with the actual vector length → reject (→ fallback),
        // never store a vector whose dimension is mislabeled.
        assert!(
            parse_embed_response(r#"{"embedding":[0.1,0.2,0.3],"backend":"m","dim":768}"#)
                .is_none()
        );
    }

    #[test]
    fn active_remote_url_unset_until_installed() {
        // daemon-http (and a non-delegating daemon) never call install_if_configured,
        // so the process-global ACTIVE_URL stays None and the dim-guard warms the
        // local model as before. Guards against a regression that would make every
        // process believe it is delegating (and wrongly skip the dim-guard probe).
        // No test calls install_if_configured(), so this OnceLock stays unset.
        assert!(active_remote_url().is_none());
    }

    #[test]
    fn normalize_url_trims_and_filters_blank() {
        assert_eq!(
            normalize_url(Some("  http://127.0.0.1:7878/embed ".into())),
            Some("http://127.0.0.1:7878/embed".into())
        );
        assert_eq!(normalize_url(Some("   ".into())), None);
        assert_eq!(normalize_url(Some(String::new())), None);
        assert_eq!(normalize_url(None), None);
    }

    #[test]
    fn embed_falls_back_when_remote_unreachable() {
        // Point at a closed port; embed() must still return a dim-sized vector
        // via the injected local fallback (hash here, to avoid loading the model).
        let b = RemoteEmbedBackend::with_fallback(
            "http://127.0.0.1:1/embed".to_string(),
            Arc::new(HashBackend),
        );
        let v = b.embed("hello world");
        assert_eq!(
            v.len(),
            ab_store::vector_dim(),
            "fallback must return a dim-sized vector, never panic/empty"
        );
    }

    #[test]
    fn embed_batch_falls_back_whole_batch_when_remote_unreachable() {
        let b = RemoteEmbedBackend::with_fallback(
            "http://127.0.0.1:1/embed".to_string(),
            Arc::new(HashBackend),
        );
        let vs = b.embed_batch(&["alpha", "beta", "gamma"]);
        assert_eq!(vs.len(), 3);
        for v in &vs {
            assert_eq!(v.len(), ab_store::vector_dim());
        }
    }

    #[test]
    fn name_and_dim_default_to_compiled_model_before_any_response() {
        let b = RemoteEmbedBackend::with_fallback(
            "http://127.0.0.1:1/embed".to_string(),
            Arc::new(HashBackend),
        );
        // Before any successful /embed response, mirror the compiled default so
        // early `memory_save` rows get the correct `embedding_backend` tag.
        assert_eq!(b.dim(), ab_store::vector_dim());
        assert_eq!(b.name(), ab_store::active_model_name());
    }
}
