//! CJK embedding-quality comparison: MiniLM (default) vs multilingual-e5-small.
//!
//! Pure measurement — no state.db, no writes. Embeds real Chinese memory-corpus
//! queries against a labeled doc pool and reports rank-of-relevant + margin, so
//! the LEVER-3 reindex decision rests on numbers, not assertion.
//!
//!   cargo run -p ab-store --example cjk_embed_compare              # MiniLM (default)
//!   AGENT_BRIDGE_ONNX_MODEL=e5-small \
//!       cargo run -p ab-store --example cjk_embed_compare          # multilingual-e5-small
//!
//! Both models load from ~/.cache/agent-bridge/onnx-models/<name>/ (ModelScope
//! fetched). The harness DETECTS hash-fallback (model failed to load) and refuses
//! to report it as a model result — no green-laundering.

use ab_store::vector::{cosine_similarity, embed_text, embed_text_hash};

fn main() {
    let model = std::env::var("AGENT_BRIDGE_ONNX_MODEL")
        .unwrap_or_else(|_| "all-MiniLM-L6-v2(default)".into());
    eprintln!("[cjk-compare] active model selection: {model}");

    // Init runs on a background thread; embed_text falls to the hash backend
    // until the ONNX model is ready. Poll until the real model diverges from
    // the hash fallback, or give up after 60s.
    let probe = "语义检索质量探针 semantic readiness probe";
    let hash_probe = embed_text_hash(probe);
    let mut ready = false;
    for i in 0..120 {
        if embed_text(probe) != hash_probe {
            ready = true;
            eprintln!("[cjk-compare] model ready after ~{} ms", i * 500);
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(500));
    }
    if !ready {
        eprintln!(
            "[cjk-compare] !!! HASH FALLBACK after 60s — ONNX model did NOT load. \
             Numbers below are hash, NOT the model. !!!"
        );
    }

    // Labeled doc pool — real corpus snippets, paraphrased so queries are not
    // verbatim substrings (this tests SEMANTIC match, which is the whole point).
    let docs: Vec<(&str, &str)> = vec![
        ("db", "技术债 TD-02:blocking 池容量上限设为 256,合入 master 并部署 live,daemon/palace/daemon-http 三个服务 boot-smoke 通过。"),
        ("ssb", "SSB 语义系统总线是当前北极星,回路是 对象到可供性到动作到事件到验证再到记忆与呈现,Linux 优先 verify-first,禁止绿洗。"),
        ("sync", "记忆同步借鉴 syncthing,把冲突解决从 git 墙钟 LWW 下移到 SQLite 每记录版本向量,两节点跨网联测达到验证级通过。"),
        ("browser", "浏览器工具评估 camofox 与 agent-browser 都不采纳,只借鉴稳定元素引用按引用点击,修复了真实鼠标点击,合入 master 并部署。"),
        ("face", "桌面具身 Face 审查:stop 脚枪与双 Face 竞态已修,用 flock 互斥加 pidfile 组杀,头像渲染走透明 wlroots layer-shell。"),
        ("deploy", "部署竞争事故:陈旧分支的二进制覆盖了另一条 lane 刚部署的,诊断用 strings 查 lane 特征,根治是从 master 部署脚本的反退化门加备份。"),
        ("recall", "召回缺口诊断:FTS5 隐式 AND 太严格,多词中文查询返回空集,改成 AND 转 OR 的召回恢复回退,命中率约 0.82。"),
        ("embed", "嵌入后端对中文表示弱,余弦相似度只有 0.2 到 0.5,换用多语言 384 维模型直接替换,可提升中文检索质量。"),
    ];

    // Natural-language Chinese queries, each semantically matching ONE doc.
    let queries: Vec<(&str, &str)> = vec![
        ("数据库连接池的容量上限和阻塞排队问题怎么处理", "db"),
        ("语义系统总线的设计理念和验证闭环是怎样的", "ssb"),
        ("多台设备之间的记忆怎样同步并解决写入冲突", "sync"),
        ("为什么用好几个关键词搜中文笔记经常一条都搜不到", "recall"),
        ("中文语义召回效果差是不是因为嵌入模型不行", "embed"),
        ("怎么避免旧的构建把别人刚上线的二进制覆盖掉", "deploy"),
    ];

    let doc_vecs: Vec<(&str, Vec<f32>)> = docs.iter().map(|(k, t)| (*k, embed_text(t))).collect();

    let mut at1 = 0usize;
    let mut margins: Vec<f32> = Vec::new();
    let mut rel_coses: Vec<f32> = Vec::new();
    println!("\n=== per-query ranking (model: {model}) ===");
    for (q, want) in &queries {
        let qv = embed_text(q);
        let mut scored: Vec<(&str, f32)> = doc_vecs
            .iter()
            .map(|(k, v)| (*k, cosine_similarity(&qv, v)))
            .collect();
        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        let rank = scored.iter().position(|(k, _)| k == want).unwrap() + 1;
        let rel_cos = scored.iter().find(|(k, _)| k == want).unwrap().1;
        let best_distractor = scored
            .iter()
            .filter(|(k, _)| k != want)
            .map(|(_, s)| *s)
            .fold(f32::MIN, f32::max);
        let margin = rel_cos - best_distractor;
        if rank == 1 {
            at1 += 1;
        }
        margins.push(margin);
        rel_coses.push(rel_cos);
        let top3: Vec<String> = scored
            .iter()
            .take(3)
            .map(|(k, s)| format!("{k}:{s:.3}"))
            .collect();
        println!(
            "Q[{want:>7}] rank={rank} relcos={rel_cos:.3} margin={margin:+.3} | top3: {}",
            top3.join(" ")
        );
    }
    let n = queries.len() as f32;
    let mean_margin: f32 = margins.iter().sum::<f32>() / n;
    let mean_rel: f32 = rel_coses.iter().sum::<f32>() / n;
    println!("\n=== SUMMARY model={model} ready={ready} ===");
    println!(
        "relevant@rank1: {at1}/{}  mean_rel_cos={mean_rel:.3}  mean_margin={mean_margin:+.3}",
        queries.len()
    );
    if !ready {
        println!("(HASH FALLBACK — NOT a valid model result; ignore the numbers above)");
    }
}
