//! Probe a store's semantic recall with the ACTIVE embedding model.
//!
//! Opens the store at <path>, embeds each query with the active model, runs the
//! production `memory_search_semantic`, and prints top-K {cosine, score, key}.
//! The LEVER-3 falsifier: does a candidate model surface the RIGHT memories on
//! the real corpus — e.g. recover SSB memories that e5 buried under its ~0.86
//! cosine compression? Read-only (no writes).
//!
//!   AGENT_BRIDGE_ONNX_MODEL=para-ml \
//!     cargo run -p ab-store --example search_probe -- /path/to/copy.db

use ab_store::vector::{embed_text, embed_text_hash};
use ab_store::{SqliteStore, StateStore};

#[tokio::main]
async fn main() {
    let db = std::env::args()
        .nth(1)
        .expect("usage: search_probe <state.db path>");
    let model = std::env::var("AGENT_BRIDGE_ONNX_MODEL").unwrap_or_else(|_| "default".into());
    eprintln!("[probe] db={db} model={model}");

    // Warm the model (hash fallback during bg init; hash dim may differ → also
    // treat a length change as "ready").
    let p = "预热 warmup";
    let h = embed_text_hash(p);
    let mut ready = false;
    for i in 0..240 {
        let v = embed_text(p);
        if v.len() != h.len() || v != h {
            ready = true;
            eprintln!("[probe] model ready ~{}ms", i * 500);
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(500));
    }
    if !ready {
        eprintln!("[probe] HASH FALLBACK — model didn't load. Abort.");
        std::process::exit(2);
    }

    let store = SqliteStore::open(std::path::Path::new(&db))
        .await
        .expect("open store");

    let queries = [
        "如何修复数据库连接超时和锁竞争问题",
        "语义系统总线的设计与验证回路",
        "跨节点记忆同步的版本向量冲突解决",
    ];
    for q in queries {
        let hits = store
            .memory_search_semantic(q, 25, 0.0)
            .await
            .unwrap_or_default();
        let show = hits.len().min(12);
        println!("\n=== query: {q}  (showing {show}/{}) ===", hits.len());
        for (i, hh) in hits.iter().take(show).enumerate() {
            let k = &hh.record.key;
            let mark = if k.contains("semantic_system_bus") {
                "  <<< SSB"
            } else if k.contains("sync") || k.contains("memory_sync") {
                "  <sync>"
            } else if k.contains("db") || k.contains("sqlx") || k.contains("blocking") {
                "  <db>"
            } else {
                ""
            };
            let cos = hh
                .cosine
                .map(|c| format!("{c:.3}"))
                .unwrap_or_else(|| "—".into());
            println!(
                " {:2}. cos={cos} score={:.3} {}{}",
                i + 1,
                hh.score,
                &k[..k.len().min(56)],
                mark
            );
        }
    }
}
