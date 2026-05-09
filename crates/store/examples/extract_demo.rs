//! One-shot validator for the codebase extractor.
//!
//! Usage: cargo run --example extract_demo -p ab-store -- <file>

use ab_store::codebase::{detect_language, extract_symbols};
use std::path::Path;

fn main() {
    let path = std::env::args().nth(1).expect("usage: extract_demo <file>");
    let p = Path::new(&path);
    let lang = detect_language(p).expect("unknown language");
    let content = std::fs::read_to_string(&path).unwrap();
    let syms = extract_symbols(&content, &path, lang);

    let mut by_kind: std::collections::BTreeMap<String, usize> = Default::default();
    for s in &syms {
        *by_kind.entry(s.kind.clone()).or_default() += 1;
    }
    println!("{} symbols ({}): {:?}", syms.len(), lang, by_kind);

    println!("\nclass / method entries (first 20):");
    for s in syms
        .iter()
        .filter(|s| s.kind == "method" || s.kind == "class")
        .take(20)
    {
        println!("  L{:>4} {:<7} {}", s.line, s.kind, s.name);
    }
}
