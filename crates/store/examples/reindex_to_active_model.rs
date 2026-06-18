//! One-shot reindex of a store to the ACTIVE embedding model.
//!
//! Re-embeds every row whose embedding is NULL or was produced by a different
//! backend (only_stale=true), onto the currently-selected model's vector space.
//! Used to migrate the prod store MiniLM → multilingual-e5-small (#1485 / LEVER 3).
//!
//!   AGENT_BRIDGE_ONNX_MODEL=e5-small \
//!     cargo run -p ab-store --example reindex_to_active_model -- [state.db path]
//!
//! Path defaults to ab_store::default_db_path() (the real prod store). Pass an
//! explicit path to target a copy.
//!
//! No-laundering: the model is WARMED first (init runs on a bg thread and falls
//! to hash until ready), and memory_reindex_embeddings itself refuses to write a
//! hash-fallback vector — so a half-loaded model aborts rather than corrupting
//! the store with garbage vectors tagged as the real model.

use ab_store::vector::{embed_text, embed_text_hash};
use ab_store::{default_db_path, SqliteStore, StateStore};

#[tokio::main]
async fn main() {
    let db = std::env::args()
        .nth(1)
        .map(std::path::PathBuf::from)
        .unwrap_or_else(default_db_path);
    let model = std::env::var("AGENT_BRIDGE_ONNX_MODEL").unwrap_or_else(|_| "all-MiniLM-L6-v2(default)".into());
    eprintln!("[reindex] db={}  model={model}", db.display());

    // Warm the ONNX model so reindex never trips the hash-fallback guard.
    let probe = "嵌入模型预热 warmup probe for reindex";
    let hash = embed_text_hash(probe);
    let mut ready = false;
    for i in 0..240 {
        if embed_text(probe) != hash {
            ready = true;
            eprintln!("[reindex] model ready after ~{} ms", i * 500);
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(500));
    }
    if !ready {
        eprintln!("[reindex] ABORT: ONNX model never loaded (would write hash). No rows touched.");
        std::process::exit(2);
    }

    let store = SqliteStore::open(&db).await.expect("open state.db");
    let mut total = 0usize;
    loop {
        let n = store
            .memory_reindex_embeddings(1000, true)
            .await
            .expect("memory_reindex_embeddings batch");
        total += n;
        eprintln!("[reindex] batch reindexed {n} (running total {total})");
        if n == 0 {
            break;
        }
    }
    eprintln!("[reindex] DONE — reindexed {total} rows onto {model}");
}
