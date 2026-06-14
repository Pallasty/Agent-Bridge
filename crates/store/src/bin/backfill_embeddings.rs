use ab_store::vector::{embed_text, encode_embedding};
use std::path::PathBuf;
use tokio_rusqlite::rusqlite::{params, Connection};

fn db_path() -> PathBuf {
    let base = std::env::var("XDG_DATA_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            let home = std::env::var("HOME").expect("HOME not set");
            PathBuf::from(home).join(".local").join("share")
        });
    base.join("agent-bridge").join("state.db")
}

fn main() {
    let path = db_path();
    println!("DB: {}", path.display());

    let conn = Connection::open(&path).expect("open db");

    let rows: Vec<(String, String)> = {
        let mut stmt = conn
            .prepare(
                "SELECT key, content FROM memories \
                 WHERE embedding IS NULL AND status = 'active' \
                 ORDER BY created_at DESC",
            )
            .expect("prepare select");
        stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?)))
            .expect("query")
            .filter_map(|r| r.ok())
            .collect()
    };

    let total = rows.len();
    println!("Found {} memories without embeddings", total);

    let mut updated = 0usize;
    for (key, content) in &rows {
        let vec = embed_text(content);
        let bytes = encode_embedding(&vec);
        conn.execute(
            "UPDATE memories SET embedding = ?1 WHERE key = ?2",
            params![bytes, key],
        )
        .expect("update");
        updated += 1;
        if updated % 50 == 0 || updated == total {
            println!("  {}/{}", updated, total);
        }
    }

    println!("Done. Updated {} memories.", updated);
}
