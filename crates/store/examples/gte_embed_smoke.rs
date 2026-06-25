//! Read-only smoke test for the local gte-multilingual-base ONNX bundle.
//!
//! This example does not open state.db, reindex rows, or write memory. It only
//! verifies that `AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base` loads the local
//! ONNX model and returns real 768-dim vectors instead of the hash fallback.
//!
//!   AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
//!     cargo run -p ab-store --example gte_embed_smoke

use ab_store::vector::{cosine_similarity, embed_text, embed_text_hash, vector_dim};

fn main() {
    let model = std::env::var("AGENT_BRIDGE_ONNX_MODEL").unwrap_or_else(|_| "default".into());
    if model != "gte" && model != "gte-ml" && model != "gte-multilingual-base" {
        eprintln!(
            "[gte-smoke] ABORT: set AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base (got {model})"
        );
        std::process::exit(2);
    }

    let expected_dim = vector_dim();
    if expected_dim != 768 {
        eprintln!("[gte-smoke] ABORT: expected vector_dim=768, got {expected_dim}");
        std::process::exit(3);
    }

    let timeout_secs = std::env::var("AB_GTE_SMOKE_TIMEOUT_SECS")
        .ok()
        .and_then(|s| s.parse::<u64>().ok())
        .filter(|n| *n > 0)
        .unwrap_or(180);
    let attempts = timeout_secs * 2;

    let probe = "中文语义检索模型加载探针 semantic readiness probe";
    let hash_probe = embed_text_hash(probe);
    let mut ready_after_ms = None;
    for i in 0..attempts {
        let v = embed_text(probe);
        if v != hash_probe {
            ready_after_ms = Some(i * 500);
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(500));
    }

    let Some(ms) = ready_after_ms else {
        eprintln!("[gte-smoke] ABORT: hash fallback after {timeout_secs}s; ONNX did not load");
        std::process::exit(4);
    };

    let q = embed_text("如何提升中文语义检索召回质量");
    let para = embed_text("怎样改善中文向量搜索的匹配效果");
    let unrelated = embed_text("厨房里正在烤面包");

    if q.len() != 768 || para.len() != 768 || unrelated.len() != 768 {
        eprintln!(
            "[gte-smoke] ABORT: expected 768-dim embeddings, got q={} para={} unrelated={}",
            q.len(),
            para.len(),
            unrelated.len()
        );
        std::process::exit(5);
    }

    let para_sim = cosine_similarity(&q, &para);
    let unrelated_sim = cosine_similarity(&q, &unrelated);
    let gap = para_sim - unrelated_sim;

    println!("[gte-smoke] model={model}");
    println!("[gte-smoke] ready_after_ms={ms}");
    println!("[gte-smoke] dim={}", q.len());
    println!("[gte-smoke] para_sim={para_sim:.3}");
    println!("[gte-smoke] unrelated_sim={unrelated_sim:.3}");
    println!("[gte-smoke] gap={gap:.3}");

    if para_sim < 0.2 || gap < 0.05 {
        eprintln!("[gte-smoke] ABORT: weak semantic sanity check");
        std::process::exit(6);
    }
}
