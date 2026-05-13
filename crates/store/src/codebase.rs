//! Pure-Rust symbol extractor — no C dependencies, no build scripts.
//!
//! Supports Rust, Python, TypeScript/JavaScript, and Go via line-based
//! pattern matching. Accurate enough for agent codebase navigation; a
//! tree-sitter backend can be swapped in later if precision is needed.

use crate::{CodebaseCall, CodebaseImport, CodebaseSymbol};
use std::path::Path;

/// Map a file extension to a canonical language name.
pub fn detect_language(path: &Path) -> Option<&'static str> {
    match path.extension()?.to_str()? {
        "rs" => Some("rust"),
        "py" | "pyw" => Some("python"),
        "ts" | "tsx" => Some("typescript"),
        "js" | "jsx" | "mjs" | "cjs" => Some("javascript"),
        "go" => Some("go"),
        _ => None,
    }
}

/// Extract top-level symbols from `content` for the given language.
pub fn extract_symbols(content: &str, file_path: &str, language: &str) -> Vec<CodebaseSymbol> {
    match language {
        "rust" => extract_rust(content, file_path),
        "python" => extract_python(content, file_path),
        "typescript" | "javascript" => extract_ts_js(content, file_path, language),
        "go" => extract_go(content, file_path),
        _ => vec![],
    }
}

/// Extract `use`/`import` statements from `content` for the given language.
/// Phase 2 #3 second slice covers Rust + Python + TS/JS + Go.
pub fn extract_imports(content: &str, file_path: &str, language: &str) -> Vec<CodebaseImport> {
    match language {
        "rust" => extract_rust_imports(content, file_path),
        "python" => extract_python_imports(content, file_path),
        "typescript" | "javascript" => extract_ts_imports(content, file_path, language),
        "go" => extract_go_imports(content, file_path),
        _ => vec![],
    }
}

/// Extract call sites from `content` for the given language. Phase 2 #3
/// third slice now covers Rust + Python + TS/JS + Go (all four).
/// Dispatch returns `vec![]` for unhandled languages so the table is
/// always queryable.
pub fn extract_calls(content: &str, file_path: &str, language: &str) -> Vec<CodebaseCall> {
    match language {
        "rust" => extract_rust_calls(content, file_path),
        "python" => extract_python_calls(content, file_path),
        "typescript" | "javascript" => extract_ts_calls(content, file_path, language),
        "go" => extract_go_calls(content, file_path),
        _ => vec![],
    }
}

// ── helpers ──────────────────────────────────────────────────────────────────

fn make(file: &str, line: u32, kind: &str, name: String, sig: &str, lang: &str) -> CodebaseSymbol {
    CodebaseSymbol {
        file_path: file.to_string(),
        line,
        col: 0,
        kind: kind.to_string(),
        name,
        signature: sig.chars().take(200).collect(),
        language: lang.to_string(),
        score: None,
    }
}

/// Strip a Rust visibility modifier from the start of a trimmed line.
fn strip_vis(s: &str) -> &str {
    if let Some(r) = s.strip_prefix("pub(crate)") {
        return r.trim_start();
    }
    if let Some(r) = s.strip_prefix("pub(super)") {
        return r.trim_start();
    }
    if let Some(r) = s.strip_prefix("pub(in ") {
        // skip to matching ')'
        if let Some(idx) = r.find(')') {
            return r[idx + 1..].trim_start();
        }
        return r;
    }
    if let Some(r) = s.strip_prefix("pub") {
        return r.trim_start();
    }
    s
}

/// Try to match one of the keyword patterns and extract the symbol name.
fn try_kw<'k>(s: &str, patterns: &[(&str, &'k str)]) -> Option<(&'k str, String)> {
    for (kw, kind) in patterns {
        if let Some(rest) = s.strip_prefix(kw) {
            let name: String = rest
                .chars()
                .take_while(|c| c.is_alphanumeric() || *c == '_')
                .collect();
            if name.len() > 1 || (name.len() == 1 && name != "_") {
                return Some((kind, name));
            }
        }
    }
    None
}

// ── Rust ─────────────────────────────────────────────────────────────────────

/// Parse the type-name (and optional trait-name) from an `impl …` header line.
///
/// Strips a leading `<…>` generics block on `impl` itself, then splits on the
/// first ` for ` to distinguish trait impls from inherent impls.  Within each
/// side, generics inside `<…>`, `where` clauses, and the opening `{` are also
/// stripped so the captured names are bare paths suitable for qualification.
///
/// Returns `None` when the line does not begin with `impl ` (after the caller's
/// visibility/qualifier strip pass).
fn parse_rust_impl_header(s: &str) -> Option<(String, Option<String>)> {
    let rest = s.strip_prefix("impl")?;
    // Must be followed by whitespace or '<'  — otherwise this is something
    // like `impls`, not the keyword.
    let first = rest.chars().next()?;
    if !first.is_whitespace() && first != '<' {
        return None;
    }
    // Strip an `impl<…>` generics block (balance angle brackets).
    let after_generics = strip_leading_angle_block(rest.trim_start());
    let body = after_generics.trim_start();

    // Split on the first top-level ` for ` (trait impls).
    let (head, tail) = split_top_level_for(body);
    let type_str = clean_impl_path(tail.unwrap_or(head));
    let trait_str = tail.map(|_| clean_impl_path(head));
    if type_str.is_empty() {
        return None;
    }
    Some((type_str, trait_str.filter(|s| !s.is_empty())))
}

/// Strip a leading `<…>` block, balancing angle brackets so generics like
/// `<T: Trait<U>>` consume correctly.  Returns the substring after the closing
/// `>`, or the original input if it doesn't start with `<`.
fn strip_leading_angle_block(s: &str) -> &str {
    if !s.starts_with('<') {
        return s;
    }
    let mut depth = 0;
    for (i, c) in s.char_indices() {
        match c {
            '<' => depth += 1,
            '>' => {
                depth -= 1;
                if depth == 0 {
                    return s[i + 1..].trim_start();
                }
            }
            _ => {}
        }
    }
    s
}

/// Split on the first top-level ` for ` token (not inside `<…>`).  Returns
/// `(left, Some(right))` if found, else `(input, None)`.
fn split_top_level_for(s: &str) -> (&str, Option<&str>) {
    let bytes = s.as_bytes();
    let mut depth = 0;
    let mut i = 0;
    while i + 5 <= bytes.len() {
        match bytes[i] {
            b'<' => depth += 1,
            b'>' => depth -= 1,
            b' ' if depth == 0 && &bytes[i..i + 5] == b" for " => {
                return (s[..i].trim(), Some(s[i + 5..].trim()));
            }
            _ => {}
        }
        i += 1;
    }
    (s.trim(), None)
}

/// Trim trailing generics, `where` clauses, and the opening `{` from an impl
/// path component, leaving the bare path (e.g. `Foo`, `crate::Bar`).  Also
/// trims trailing punctuation/whitespace.
fn clean_impl_path(s: &str) -> String {
    let mut end = s.len();
    for (i, c) in s.char_indices() {
        if c == '<' || c == '{' {
            end = i;
            break;
        }
        // ` where ` clause stops the path.
        if c == ' ' && s[i..].trim_start().starts_with("where") {
            end = i;
            break;
        }
    }
    s[..end].trim().trim_end_matches(',').trim().to_string()
}

/// Active impl scope tracked while line-scanning Rust source.
#[derive(Debug)]
struct RustImplScope {
    type_name: String,
    trait_name: Option<String>,
    /// Brace depth that was active when this impl's `{` opened.  When the
    /// running depth returns to this value, the impl block has closed and the
    /// scope is popped.
    open_depth: i32,
}

/// Count `{` and `}` outside of `//` line-comment regions and Rust string
/// literals.  Imperfect for raw strings and block comments but correct for
/// well-formed code; the goal is robust impl-scope detection, not a full
/// parser.
fn count_braces(line: &str) -> (i32, i32) {
    let mut opens = 0i32;
    let mut closes = 0i32;
    let mut in_str = false;
    let mut chars = line.chars().peekable();
    while let Some(c) = chars.next() {
        if in_str {
            if c == '\\' {
                chars.next(); // skip escaped char
            } else if c == '"' {
                in_str = false;
            }
            continue;
        }
        match c {
            '"' => in_str = true,
            '/' => {
                if let Some('/') = chars.peek() {
                    break; // line comment
                }
            }
            '{' => opens += 1,
            '}' => closes += 1,
            _ => {}
        }
    }
    (opens, closes)
}

/// Recognize Rust test-attribute lines. Used by `extract_rust` to tag
/// the following `fn` as `kind="test_fn"` so the codebase-report orphan
/// audit can flag macro-generated callers as known FPs.
///
/// Coverage:
///   - `#[test]` — built-in
///   - `#[tokio::test]` / `#[tokio::test(...)]` — async runtime
///   - `#[rstest]` — fixture framework
///   - `#[test_case(...)]` — parameterized tests
///   - `#[wasm_bindgen_test]` — wasm tests
///   - `#[async_std::test]` — async-std
///   - `#[actix_rt::test]` / `#[actix_web::test]` — actix
///   - `#[smol_potat::test]` — smol
///
/// Conservative — only matches at line start (after trim). False
/// negatives are acceptable (a missed test fn just shows as a real
/// orphan — annoying but recoverable); false positives would tag
/// real functions as tests (bad).
fn is_rust_test_attr_line(s: &str) -> bool {
    if !s.starts_with("#[") {
        return false;
    }
    // Match against common test attribute names. The `[` is fixed at
    // index 1; check the body for known patterns.
    let body = &s[2..]; // strip "#["
    // Drop trailing `]...` so we look only at the attribute payload.
    let body = body.split(']').next().unwrap_or(body).trim();
    // Strip arguments to get the bare attribute name.
    let name = body.split('(').next().unwrap_or(body).trim();
    matches!(
        name,
        "test"
            | "tokio::test"
            | "rstest"
            | "test_case"
            | "wasm_bindgen_test"
            | "async_std::test"
            | "actix_rt::test"
            | "actix_web::test"
            | "smol_potat::test"
            | "case"
    )
}

fn extract_rust(content: &str, file_path: &str) -> Vec<CodebaseSymbol> {
    let mut out = Vec::new();
    let mut depth: i32 = 0;
    let mut impl_stack: Vec<RustImplScope> = Vec::new();
    // When an `impl …` header has been parsed but the opening `{` lives on
    // a later line (typical with `where` clauses spanning multiple lines),
    // the scope is held here until the brace arrives.
    let mut pending_impl: Option<(String, Option<String>)> = None;
    // P22 — set when the most recent non-blank, non-comment line was a
    // test-attribute like `#[test]` / `#[tokio::test]` / `#[rstest]` /
    // `#[test_case]` / `#[wasm_bindgen_test]`. Consumed by the next `fn`
    // emit so the symbol kind becomes `test_fn` instead of `fn`. Allows
    // `dream codebase-report` to treat #[test] callers as known-FP
    // without the caller's macro-generated visibility being a problem.
    let mut pending_test_attr = false;

    for (i, raw) in content.lines().enumerate() {
        let t = raw.trim();
        let is_comment = t.starts_with("//") || t.starts_with("/*") || t.starts_with('*');
        if is_comment {
            // Comments still count braces (they generally don't contain unmatched
            // ones, but if they do the depth would skew indefinitely; the safer
            // default is to skip brace counting on comment-only lines).
            continue;
        }

        // P22 — detect test-attribute lines (`#[test]`, `#[tokio::test]`,
        // `#[rstest]`, `#[test_case]`, `#[wasm_bindgen_test]`, `#[case]`).
        // Set the pending flag and skip to brace counting — these lines
        // don't emit symbols themselves. We tolerate attribute-list rows
        // like `#[tokio::test(flavor = "multi_thread")]`.
        if is_rust_test_attr_line(t) {
            pending_test_attr = true;
            let (opens, closes) = count_braces(raw);
            depth += opens - closes;
            continue;
        }
        // Blank lines preserve the pending flag (attr+blank+fn is valid
        // formatting). Other code lines clear it.
        if t.is_empty() {
            // No depth change.
            continue;
        }

        let s = strip_vis(t);
        // Handle async/unsafe/const qualifiers
        let s2 = s
            .trim_start_matches("async ")
            .trim_start_matches("unsafe ")
            .trim_start_matches("const ");
        let s2 = strip_vis(s2); // second pass after qualifiers (e.g. `async pub fn`)

        // ── impl …{ — push a scope that qualifies inner method names.
        // Handle this BEFORE try_kw so we get the proper type/trait split
        // (try_kw with `("impl ", "impl")` would just grab the first ident,
        // which is wrong for `impl Trait for Type`).
        if let Some((type_name, trait_name)) = parse_rust_impl_header(s2) {
            // Emit the impl symbol itself.  Name carries the implementing
            // type; signature retains the original line so the trait info
            // (when present) is still searchable.
            out.push(make(file_path, (i + 1) as u32, "impl", type_name.clone(), t, "rust"));
            // Push scope only when the impl's body opens on this line.
            // Otherwise hold it as `pending_impl` until we see the `{` on a
            // subsequent line (multi-line `where` clauses).
            if t.contains('{') {
                impl_stack.push(RustImplScope {
                    type_name,
                    trait_name,
                    open_depth: depth,
                });
            } else {
                pending_impl = Some((type_name, trait_name));
            }
            // Fall through to brace counting below; the impl line's braces
            // need to update `depth` so the scope closes correctly.
        } else if pending_impl.is_some() && raw.contains('{') {
            // The pending impl's body opens here (typical: a bare `{` line
            // after a multi-line `where` clause).
            let (type_name, trait_name) = pending_impl.take().unwrap();
            impl_stack.push(RustImplScope {
                type_name,
                trait_name,
                open_depth: depth,
            });
            // Don't `continue` — the line could also start a method symbol
            // on the same row, though that's unusual after a `where` block.
        } else if let Some((kind, name)) = try_kw(
            s2,
            &[
                ("fn ", "fn"),
                ("struct ", "struct"),
                ("enum ", "enum"),
                ("trait ", "trait"),
                ("type ", "type"),
                ("const ", "const"),
                ("static ", "static"),
                ("mod ", "mod"),
                ("macro_rules! ", "macro"),
            ],
        ) {
            // Methods inside an impl get qualified `Type::method` (inherent)
            // or `<Type as Trait>::method` (trait impl).  Free functions and
            // other top-level items keep their bare name.
            let emit_name = if kind == "fn" && impl_stack.last().is_some() {
                let scope = impl_stack.last().unwrap();
                match &scope.trait_name {
                    Some(tr) => format!("<{} as {}>::{}", scope.type_name, tr, name),
                    None => format!("{}::{}", scope.type_name, name),
                }
            } else {
                name
            };
            // P22 — if the prior non-blank line was a test attribute,
            // emit as `test_fn` instead of `fn` so `dream codebase-report`
            // can mark these as likely-FP (the macro-generated caller is
            // invisible to the extractor, so they always look orphan).
            let final_kind = if kind == "fn" && pending_test_attr {
                "test_fn"
            } else {
                kind
            };
            pending_test_attr = false;
            out.push(make(file_path, (i + 1) as u32, final_kind, emit_name, t, "rust"));
        } else {
            // Any other code line clears the pending attribute flag —
            // attributes only apply to the immediately-following item.
            pending_test_attr = false;
        }

        // Update brace depth from this line's `{` / `}` (string-aware,
        // line-comment-aware).  Then pop any impl scopes whose body has closed.
        let (opens, closes) = count_braces(raw);
        depth += opens - closes;
        while let Some(scope) = impl_stack.last() {
            if depth <= scope.open_depth {
                impl_stack.pop();
            } else {
                break;
            }
        }
    }
    out
}

// ── Rust imports (Phase 2 #3 second slice) ───────────────────────────────────

/// Strip `pub`, `pub(crate)`, `pub(super)`, `pub(in path)` from the start.
fn strip_pub_for_use(s: &str) -> &str {
    let s = s.trim_start();
    if let Some(rest) = s.strip_prefix("pub(") {
        // Find the matching `)`.
        if let Some(close) = rest.find(')') {
            return rest[close + 1..].trim_start();
        }
    }
    s.strip_prefix("pub").map(str::trim_start).unwrap_or(s)
}

/// Drop a trailing line comment (`// …`) if present. String-aware so a
/// `//` inside a string literal isn't mistaken for a comment opener.
fn strip_line_comment(s: &str) -> &str {
    let bytes = s.as_bytes();
    let mut in_str = false;
    let mut prev_bs = false;
    let mut i = 0;
    while i < bytes.len() {
        let c = bytes[i];
        if in_str {
            if c == b'\\' && !prev_bs {
                prev_bs = true;
                i += 1;
                continue;
            }
            if c == b'"' && !prev_bs {
                in_str = false;
            }
            prev_bs = false;
        } else if c == b'"' {
            in_str = true;
        } else if c == b'/' && i + 1 < bytes.len() && bytes[i + 1] == b'/' {
            return &s[..i];
        }
        i += 1;
    }
    s
}

/// Split `s` on top-level commas (depth-0 with respect to nested `{ }`).
/// Used to break `Bar, baz::{Q, R}, Other` into three items.
fn split_top_level_commas(s: &str) -> Vec<&str> {
    let mut out = Vec::new();
    let mut depth: i32 = 0;
    let mut start = 0usize;
    for (i, ch) in s.char_indices() {
        match ch {
            '{' | '(' | '<' => depth += 1,
            '}' | ')' | '>' => depth -= 1,
            ',' if depth == 0 => {
                out.push(s[start..i].trim());
                start = i + ch.len_utf8();
            }
            _ => {}
        }
    }
    out.push(s[start..].trim());
    out.into_iter().filter(|p| !p.is_empty()).collect()
}

/// Parse one `as alias` suffix from `item`. Returns `(path_part, Some(alias))`
/// when present, or `(item, None)` otherwise. Recognizes the suffix only at
/// top-level brace depth so `{ a as b }` inside a group isn't matched out of
/// context (callers pass items that have already been split).
fn split_as_alias(item: &str) -> (String, Option<String>) {
    let trimmed = item.trim();
    // Search for ` as ` from the right; need the alias portion to be a
    // simple identifier (no `::` etc.).
    if let Some(idx) = trimmed.rfind(" as ") {
        let path = trimmed[..idx].trim();
        let alias = trimmed[idx + 4..].trim();
        if !alias.is_empty()
            && alias
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '_')
        {
            return (path.to_string(), Some(alias.to_string()));
        }
    }
    (trimmed.to_string(), None)
}

/// Expand the body of a `use`-statement (everything between `use ` and the
/// terminating `;`) into one (target, alias) per imported item. Handles
/// single paths, group `{…}` (one level recursion), wildcards, and aliases.
fn expand_use_body(body: &str) -> Vec<(String, Option<String>)> {
    let body = body.trim();
    if body.is_empty() {
        return vec![];
    }
    // Locate a top-level `{`.
    let mut depth = 0i32;
    let mut brace_start: Option<usize> = None;
    for (i, ch) in body.char_indices() {
        match ch {
            '{' if depth == 0 => {
                brace_start = Some(i);
                break;
            }
            '<' | '(' => depth += 1,
            '>' | ')' => depth -= 1,
            _ => {}
        }
    }
    let Some(bstart) = brace_start else {
        // No group — single path, possibly with `as alias`.
        let (path, alias) = split_as_alias(body);
        return vec![(path, alias)];
    };
    // Find matching `}`.
    let mut depth = 0i32;
    let mut bend: Option<usize> = None;
    for (i, ch) in body[bstart..].char_indices() {
        let abs = bstart + i;
        match ch {
            '{' => depth += 1,
            '}' => {
                depth -= 1;
                if depth == 0 {
                    bend = Some(abs);
                    break;
                }
            }
            _ => {}
        }
    }
    let Some(bend) = bend else {
        // Unbalanced — emit raw as a single fallback item.
        let (path, alias) = split_as_alias(body);
        return vec![(path, alias)];
    };
    let prefix = body[..bstart].trim_end_matches(':').trim();
    let inner = &body[bstart + 1..bend];
    let mut out = Vec::new();
    for item in split_top_level_commas(inner) {
        // `self` inside a group means the prefix itself.
        if item == "self" {
            out.push((prefix.to_string(), None));
            continue;
        }
        // Recurse into nested groups so `bar::{Baz, Qux}` inside the outer
        // brace expands properly.
        let sub = expand_use_body(item);
        for (sub_path, sub_alias) in sub {
            let combined = if prefix.is_empty() {
                sub_path
            } else if sub_path.is_empty() {
                prefix.to_string()
            } else {
                format!("{prefix}::{sub_path}")
            };
            out.push((combined, sub_alias));
        }
    }
    out
}

/// Extract Rust `use` statements as one [`CodebaseImport`] per imported item.
/// Handles single-line and multi-line statements, groups (one level of
/// nesting), wildcards, and `as alias`. `extern crate` is recorded as a
/// single import with `target = "<crate-name>"`.
pub fn extract_rust_imports(content: &str, file_path: &str) -> Vec<CodebaseImport> {
    let mut out = Vec::new();
    let lines: Vec<&str> = content.lines().collect();
    let mut i = 0usize;
    while i < lines.len() {
        let raw = lines[i];
        let no_cmt = strip_line_comment(raw);
        let stripped = strip_pub_for_use(no_cmt.trim());
        let line_no = (i as u32) + 1;
        // `extern crate foo;` / `extern crate foo as bar;`
        if let Some(rest) = stripped.strip_prefix("extern crate ") {
            if let Some(end) = rest.find(';') {
                let body = &rest[..end];
                let (target, alias) = split_as_alias(body.trim());
                out.push(CodebaseImport {
                    file_path: file_path.to_string(),
                    line: line_no,
                    language: "rust".to_string(),
                    raw: raw.chars().take(200).collect(),
                    target,
                    alias,
                });
            }
            i += 1;
            continue;
        }
        if let Some(after_use) = stripped.strip_prefix("use ") {
            // Aggregate until we hit a `;` at top level (multi-line group).
            let mut buf = after_use.to_string();
            let mut end_line_idx = i;
            while !buf.contains(';') {
                end_line_idx += 1;
                if end_line_idx >= lines.len() {
                    break;
                }
                buf.push(' ');
                buf.push_str(strip_line_comment(lines[end_line_idx]).trim());
            }
            // Trim everything from the first top-level `;` onwards.
            if let Some(semi) = buf.find(';') {
                buf.truncate(semi);
            }
            let raw_full = if end_line_idx == i {
                raw.to_string()
            } else {
                lines[i..=end_line_idx.min(lines.len() - 1)].join(" ")
            };
            for (target, alias) in expand_use_body(&buf) {
                if target.is_empty() {
                    continue;
                }
                out.push(CodebaseImport {
                    file_path: file_path.to_string(),
                    line: line_no,
                    language: "rust".to_string(),
                    raw: raw_full.chars().take(200).collect(),
                    target,
                    alias,
                });
            }
            i = end_line_idx + 1;
            continue;
        }
        i += 1;
    }
    out
}

// ── Rust calls (Phase 2 #3 third slice — call graph) ─────────────────────────

/// Reserved keywords that appear in `ident(` positions but aren't calls.
fn is_rust_call_keyword(s: &str) -> bool {
    matches!(
        s,
        "if" | "while"
            | "for"
            | "match"
            | "loop"
            | "return"
            | "let"
            | "mut"
            | "const"
            | "static"
            | "pub"
            | "fn"
            | "struct"
            | "enum"
            | "impl"
            | "trait"
            | "mod"
            | "use"
            | "as"
            | "where"
            | "in"
            | "move"
            | "async"
            | "await"
            | "unsafe"
            | "extern"
            | "type"
            | "crate"
            | "super"
            | "Self"
            | "self"
            | "box"
            | "dyn"
            | "true"
            | "false"
            | "ref"
            | "else"
            | "break"
            | "continue"
    )
}

fn is_rust_ident_char(c: u8) -> bool {
    c.is_ascii_alphanumeric() || c == b'_'
}

/// Skip a turbofish `::<…>` starting at `i` (must point at the first
/// `:`). Returns the new index past the closing `>`. If the input
/// doesn't match `::<`, returns `i` unchanged.
fn skip_rust_turbofish(bytes: &[u8], i: usize) -> usize {
    if i + 2 >= bytes.len()
        || bytes[i] != b':'
        || bytes[i + 1] != b':'
        || bytes[i + 2] != b'<'
    {
        return i;
    }
    let mut k = i + 3;
    let mut depth = 1i32;
    while k < bytes.len() && depth > 0 {
        if bytes[k] == b'<' {
            depth += 1;
        } else if bytes[k] == b'>' {
            depth -= 1;
        }
        k += 1;
    }
    k
}

fn skip_rust_whitespace(bytes: &[u8], i: usize) -> usize {
    let mut k = i;
    while k < bytes.len() && (bytes[k] == b' ' || bytes[k] == b'\t') {
        k += 1;
    }
    k
}

/// Walk one line and emit one [`CodebaseCall`] per call expression seen.
/// Skips strings (`"…"`), char/lifetime tokens (`'x'`, `'a`), `//` line
/// comments, Rust keywords, and macro invocations (`name!(…)`). Recognizes
/// bare calls (`foo(`), qualified-path calls (`Foo::bar(`), and method
/// calls (`.method(`). Turbofish (`::<T>`) is skipped between path and
/// `(`. Inside a `fn`/`struct`/etc. declaration line, the symbol's own
/// header (e.g. `name(` after `fn `) is skipped by the caller — this
/// fn doesn't know about scope.
fn extract_rust_calls_from_line(
    line: &str,
    line_no: u32,
    caller: &str,
    file_path: &str,
    out: &mut Vec<CodebaseCall>,
) {
    let bytes = line.as_bytes();
    let mut i = 0usize;
    let mut in_str = false;
    let mut prev_bs = false;
    while i < bytes.len() {
        let c = bytes[i];
        if in_str {
            if c == b'\\' && !prev_bs {
                prev_bs = true;
                i += 1;
                continue;
            }
            if c == b'"' && !prev_bs {
                in_str = false;
            }
            prev_bs = false;
            i += 1;
            continue;
        }
        // Line comment terminator.
        if c == b'/' && i + 1 < bytes.len() && bytes[i + 1] == b'/' {
            break;
        }
        if c == b'"' {
            in_str = true;
            i += 1;
            continue;
        }
        // Char / byte / lifetime literal: skip the apostrophe + a small
        // window. Rust char literals are short (≤4 bytes for unicode
        // escapes); lifetimes are `'a` (apostrophe + ident, no close).
        if c == b'\'' {
            let mut k = i + 1;
            // Possibly `\` escape inside char literal.
            if k < bytes.len() && bytes[k] == b'\\' {
                k += 1;
                while k < bytes.len() && bytes[k] != b'\'' && k - i < 12 {
                    k += 1;
                }
                if k < bytes.len() && bytes[k] == b'\'' {
                    k += 1;
                }
            } else {
                // Read identifier-ish chars; if we then hit `'`, it's a
                // char literal — skip past it. Otherwise it's a lifetime.
                while k < bytes.len() && is_rust_ident_char(bytes[k]) {
                    k += 1;
                }
                if k < bytes.len() && bytes[k] == b'\'' {
                    k += 1;
                }
            }
            i = k;
            continue;
        }
        // Method call: `.NAME(` (also tolerates `.NAME::<T>(`).
        if c == b'.'
            && i + 1 < bytes.len()
            && (bytes[i + 1].is_ascii_alphabetic() || bytes[i + 1] == b'_')
        {
            let start = i + 1;
            let mut j = start;
            while j < bytes.len() && is_rust_ident_char(bytes[j]) {
                j += 1;
            }
            let name = &line[start..j];
            let mut k = skip_rust_turbofish(bytes, j);
            k = skip_rust_whitespace(bytes, k);
            if k < bytes.len() && bytes[k] == b'(' && !is_rust_call_keyword(name) {
                out.push(CodebaseCall {
                    file_path: file_path.to_string(),
                    line: line_no,
                    language: "rust".to_string(),
                    caller: caller.to_string(),
                    callee: format!(".{name}"),
                });
            }
            i = j;
            continue;
        }
        // Identifier / qualified path: must be at token boundary.
        if c.is_ascii_alphabetic() || c == b'_' {
            if i > 0 && (is_rust_ident_char(bytes[i - 1]) || bytes[i - 1] == b'.') {
                i += 1;
                continue;
            }
            let start_first = i;
            let mut j = i;
            while j < bytes.len() && is_rust_ident_char(bytes[j]) {
                j += 1;
            }
            // Accumulate path parts separately so an inline turbofish
            // (`Vec::<u8>::new`) doesn't leave generic chars in the callee.
            let mut parts: Vec<&str> = vec![&line[start_first..j]];
            loop {
                if j + 1 < bytes.len() && bytes[j] == b':' && bytes[j + 1] == b':' {
                    // Inline turbofish — skip it and keep extending the path.
                    if j + 2 < bytes.len() && bytes[j + 2] == b'<' {
                        j = skip_rust_turbofish(bytes, j);
                        continue;
                    }
                    let s = j + 2;
                    let mut t = s;
                    while t < bytes.len() && is_rust_ident_char(bytes[t]) {
                        t += 1;
                    }
                    if t == s {
                        break;
                    }
                    parts.push(&line[s..t]);
                    j = t;
                } else {
                    break;
                }
            }
            let path = parts.join("::");
            let mut k = skip_rust_turbofish(bytes, j);
            k = skip_rust_whitespace(bytes, k);
            if k < bytes.len() && bytes[k] == b'!' {
                // Macro invocation — skip.
                i = k + 1;
                continue;
            }
            if k < bytes.len() && bytes[k] == b'(' {
                let last_seg = path.rsplit("::").next().unwrap_or(path.as_str());
                if !is_rust_call_keyword(last_seg) && !is_rust_call_keyword(&path) {
                    out.push(CodebaseCall {
                        file_path: file_path.to_string(),
                        line: line_no,
                        language: "rust".to_string(),
                        caller: caller.to_string(),
                        callee: path,
                    });
                }
            }
            i = j;
            continue;
        }
        i += 1;
    }
}

/// Replace the interior of string literals (`"…"`, raw `r#"…"#`),
/// char literals (`'x'`, `'\n'`), and comment bodies (`// …`,
/// `/* … */`) with spaces, preserving newlines + the delimiters
/// themselves. Used by the call extractor to neutralise Rust-looking
/// text that lives inside literals or comments — most importantly
/// multi-line strings, where per-line scanning would otherwise treat
/// the interior lines as real code.
///
/// Limitations:
/// - Char-literal recognition handles `'x'` and `'\<single>'` only;
///   `'\u{1F600}'`-style unicode escapes leak (rare in import sections
///   and call-graph-relevant code).
fn mask_strings_and_comments(content: &str) -> String {
    enum State {
        Normal,
        Str,
        RawStr,
        LineCmt,
        BlockCmt,
    }
    let mut state = State::Normal;
    let mut raw_hashes = 0usize;
    let mut prev_bs = false;
    let mut out = String::with_capacity(content.len());
    let bytes = content.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        let c = bytes[i];
        match state {
            State::Normal => {
                // Raw string: `r"…"`, `r#"…"#`, `r##"…"##`, etc., or
                // byte raw `br"…"`, `br#"…"#`. Check word boundary.
                let before_ok = i == 0
                    || (!bytes[i - 1].is_ascii_alphanumeric() && bytes[i - 1] != b'_');
                if before_ok && (c == b'r' || (c == b'b' && i + 1 < bytes.len() && bytes[i + 1] == b'r')) {
                    let r_start = if c == b'b' { i + 1 } else { i };
                    let mut k = r_start + 1;
                    let mut hashes = 0;
                    while k < bytes.len() && bytes[k] == b'#' {
                        hashes += 1;
                        k += 1;
                    }
                    if k < bytes.len() && bytes[k] == b'"' {
                        // Confirmed raw string opener.
                        for j in i..=k {
                            out.push(bytes[j] as char);
                        }
                        raw_hashes = hashes;
                        state = State::RawStr;
                        i = k + 1;
                        continue;
                    }
                }
                if c == b'\'' {
                    // Char literal: `'x'` (3 chars) or `'\x'` (4 chars).
                    // Lifetime: `'a` followed by ident chars, no close.
                    if i + 2 < bytes.len() && bytes[i + 2] == b'\'' && bytes[i + 1] != b'\\' {
                        out.push('\'');
                        out.push(' ');
                        out.push('\'');
                        i += 3;
                        continue;
                    }
                    if i + 3 < bytes.len()
                        && bytes[i + 1] == b'\\'
                        && bytes[i + 3] == b'\''
                    {
                        out.push('\'');
                        out.push(' ');
                        out.push(' ');
                        out.push('\'');
                        i += 4;
                        continue;
                    }
                    // Lifetime — keep as-is.
                    out.push('\'');
                    i += 1;
                    continue;
                }
                if c == b'"' {
                    state = State::Str;
                    out.push('"');
                    i += 1;
                } else if c == b'/' && i + 1 < bytes.len() && bytes[i + 1] == b'/' {
                    state = State::LineCmt;
                    out.push(' ');
                    out.push(' ');
                    i += 2;
                } else if c == b'/' && i + 1 < bytes.len() && bytes[i + 1] == b'*' {
                    state = State::BlockCmt;
                    out.push(' ');
                    out.push(' ');
                    i += 2;
                } else {
                    out.push(c as char);
                    i += 1;
                }
            }
            State::Str => {
                if c == b'\\' && !prev_bs {
                    prev_bs = true;
                    out.push('\\');
                    i += 1;
                    continue;
                }
                if c == b'"' && !prev_bs {
                    state = State::Normal;
                    out.push('"');
                    prev_bs = false;
                    i += 1;
                    continue;
                }
                prev_bs = false;
                if c == b'\n' {
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
            State::RawStr => {
                // Closing is `"` followed by `raw_hashes` `#`s.
                if c == b'"' {
                    let mut all_hash = true;
                    for hi in 1..=raw_hashes {
                        if i + hi >= bytes.len() || bytes[i + hi] != b'#' {
                            all_hash = false;
                            break;
                        }
                    }
                    if all_hash {
                        // Push closing delimiter as-is.
                        for j in i..=i + raw_hashes {
                            if j < bytes.len() {
                                out.push(bytes[j] as char);
                            }
                        }
                        state = State::Normal;
                        i = i + raw_hashes + 1;
                        continue;
                    }
                }
                if c == b'\n' {
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
            State::LineCmt => {
                if c == b'\n' {
                    state = State::Normal;
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
            State::BlockCmt => {
                if c == b'*' && i + 1 < bytes.len() && bytes[i + 1] == b'/' {
                    state = State::Normal;
                    out.push(' ');
                    out.push(' ');
                    i += 2;
                    continue;
                }
                if c == b'\n' {
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
        }
    }
    out
}

/// Extract call sites from a Rust file. Tracks the enclosing function
/// (mirroring [`extract_rust`]'s `impl_stack` so trait methods resolve
/// to `<Type as Trait>::method`) and emits one [`CodebaseCall`] per
/// call expression. Declaration lines (`fn`, `struct`, `enum`, …) are
/// skipped so the symbol's header isn't mis-attributed as a call.
pub fn extract_rust_calls(content: &str, file_path: &str) -> Vec<CodebaseCall> {
    let content = mask_strings_and_comments(content);
    let content = content.as_str();
    let mut out = Vec::new();
    let mut depth: i32 = 0;
    let mut impl_stack: Vec<RustImplScope> = Vec::new();
    let mut pending_impl: Option<(String, Option<String>)> = None;
    // (qualified_caller_name, depth_at_body_open)
    let mut fn_stack: Vec<(String, i32)> = Vec::new();
    let mut pending_fn: Option<String> = None;

    for (i, raw) in content.lines().enumerate() {
        let line_no = (i as u32) + 1;
        let t = raw.trim();
        let is_comment = t.starts_with("//") || t.starts_with("/*") || t.starts_with('*');
        if is_comment {
            continue;
        }

        let s = strip_vis(t);
        let s2 = s
            .trim_start_matches("async ")
            .trim_start_matches("unsafe ")
            .trim_start_matches("const ");
        let s2 = strip_vis(s2);

        let mut is_decl_line = false;

        // Item declarations like `const X = …` / `static Y = …` / `type Z =`
        // never count as call sites — but the `const ` modifier trim above
        // also eats the standalone `const` keyword. Check the raw
        // (visibility-stripped) line so item decls aren't mis-scanned.
        if s.starts_with("const ")
            || s.starts_with("static ")
            || s.starts_with("type ")
            || s.starts_with("use ")
            || s.starts_with("mod ")
            || s.starts_with("extern crate ")
        {
            is_decl_line = true;
        }

        // Track impl scopes (same logic as extract_rust).
        if let Some((type_name, trait_name)) = parse_rust_impl_header(s2) {
            is_decl_line = true;
            if t.contains('{') {
                impl_stack.push(RustImplScope {
                    type_name,
                    trait_name,
                    open_depth: depth,
                });
            } else {
                pending_impl = Some((type_name, trait_name));
            }
        } else if pending_impl.is_some() && raw.contains('{') {
            let (type_name, trait_name) = pending_impl.take().unwrap();
            impl_stack.push(RustImplScope {
                type_name,
                trait_name,
                open_depth: depth,
            });
        } else if let Some((kind, name)) = try_kw(
            s2,
            &[
                ("fn ", "fn"),
                ("struct ", "struct"),
                ("enum ", "enum"),
                ("trait ", "trait"),
                ("type ", "type"),
                ("const ", "const"),
                ("static ", "static"),
                ("mod ", "mod"),
                ("macro_rules! ", "macro"),
            ],
        ) {
            is_decl_line = true;
            if kind == "fn" {
                let qualified = if let Some(scope) = impl_stack.last() {
                    match &scope.trait_name {
                        Some(tr) => format!("<{} as {}>::{}", scope.type_name, tr, name),
                        None => format!("{}::{}", scope.type_name, name),
                    }
                } else {
                    name
                };
                if raw.contains('{') {
                    fn_stack.push((qualified, depth));
                } else {
                    pending_fn = Some(qualified);
                }
            }
        } else if pending_fn.is_some() && raw.contains('{') {
            fn_stack.push((pending_fn.take().unwrap(), depth));
            // Don't mark as decl-line; subsequent body could start here.
        }

        if !is_decl_line {
            let caller = fn_stack.last().map(|(n, _)| n.as_str()).unwrap_or("");
            extract_rust_calls_from_line(raw, line_no, caller, file_path, &mut out);
        }

        // Update brace depth from this line's `{` / `}`.
        let (opens, closes) = count_braces(raw);
        depth += opens - closes;
        // Pop fn scopes whose body has closed.
        while let Some((_, open_depth)) = fn_stack.last() {
            if depth <= *open_depth {
                fn_stack.pop();
            } else {
                break;
            }
        }
        // Pop impl scopes whose body has closed.
        while let Some(scope) = impl_stack.last() {
            if depth <= scope.open_depth {
                impl_stack.pop();
            } else {
                break;
            }
        }
    }
    out
}

// ── Python imports (Phase 2 #3 second slice — Python side) ───────────────────

/// Drop a trailing `# …` line comment. String-aware for `'…'` and `"…"`
/// so a `#` inside a string literal isn't mistaken for a comment opener.
/// Triple-quoted / raw / byte string prefixes aren't handled — import
/// lines almost never contain them.
fn strip_python_line_comment(s: &str) -> &str {
    let bytes = s.as_bytes();
    let mut in_str = false;
    let mut quote: u8 = b' ';
    let mut prev_bs = false;
    let mut i = 0;
    while i < bytes.len() {
        let c = bytes[i];
        if in_str {
            if c == b'\\' && !prev_bs {
                prev_bs = true;
                i += 1;
                continue;
            }
            if c == quote && !prev_bs {
                in_str = false;
            }
            prev_bs = false;
        } else if c == b'"' || c == b'\'' {
            in_str = true;
            quote = c;
        } else if c == b'#' {
            return &s[..i];
        }
        i += 1;
    }
    s
}

/// Parse `path as alias` → `(path, Some(alias))` for one item already split
/// out of a comma list. Mirror of [`split_as_alias`] but for Python's `as`.
fn split_python_as(item: &str) -> (String, Option<String>) {
    let trimmed = item.trim();
    if let Some(idx) = trimmed.rfind(" as ") {
        let path = trimmed[..idx].trim();
        let alias = trimmed[idx + 4..].trim();
        if !alias.is_empty()
            && alias
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '_')
        {
            return (path.to_string(), Some(alias.to_string()));
        }
    }
    (trimmed.to_string(), None)
}

/// Join a `from MODULE import NAME` pair into a single canonical target.
/// Handles relative imports (`.foo`, `..bar`, `.pkg.mod`) without
/// duplicating dots.
fn join_python_import_path(module: &str, name: &str) -> String {
    if name.is_empty() {
        return module.to_string();
    }
    if module.is_empty() || module.ends_with('.') {
        format!("{module}{name}")
    } else {
        format!("{module}.{name}")
    }
}

/// Extract Python `import` and `from … import …` statements as one
/// [`CodebaseImport`] per imported item. Multi-item forms (`import a, b`,
/// `from x import y, z`, parenthesized multi-line imports) all expand to
/// one row each. Wildcard `from x import *` records `target = "x.*"`.
/// Convention for `from`: target is the canonical absolute path
/// `MODULE.NAME` so the same query "who imports `os.path`" works whether
/// the call site wrote `import os.path` or `from os import path`.
pub fn extract_python_imports(content: &str, file_path: &str) -> Vec<CodebaseImport> {
    let mut out = Vec::new();
    let lines: Vec<&str> = content.lines().collect();
    let mut i = 0usize;
    while i < lines.len() {
        let raw = lines[i];
        let no_cmt = strip_python_line_comment(raw);
        let stripped = no_cmt.trim();
        let line_no = (i as u32) + 1;

        // `import a` / `import a.b` / `import a as x` / `import a, b as y`
        if let Some(rest) = stripped.strip_prefix("import ") {
            let body = rest.trim_end_matches(';').trim();
            for item in split_top_level_commas(body) {
                let (target, alias) = split_python_as(item);
                if target.is_empty() {
                    continue;
                }
                out.push(CodebaseImport {
                    file_path: file_path.to_string(),
                    line: line_no,
                    language: "python".to_string(),
                    raw: raw.chars().take(200).collect(),
                    target,
                    alias,
                });
            }
            i += 1;
            continue;
        }

        // `from MODULE import a, b as x` (possibly multi-line with parens)
        if let Some(rest) = stripped.strip_prefix("from ") {
            if let Some(imp_idx) = rest.find(" import ") {
                let module = rest[..imp_idx].trim().to_string();
                let mut after = rest[imp_idx + " import ".len()..].to_string();
                let mut end_line_idx = i;
                // Multi-line: aggregate lines until the open paren closes.
                if after.contains('(') && !after.contains(')') {
                    while end_line_idx + 1 < lines.len() {
                        end_line_idx += 1;
                        let next = strip_python_line_comment(lines[end_line_idx]).trim();
                        after.push(' ');
                        after.push_str(next);
                        if after.contains(')') {
                            break;
                        }
                    }
                }
                let after = after
                    .trim()
                    .trim_end_matches(';')
                    .trim()
                    .trim_start_matches('(')
                    .trim_end_matches(')')
                    .trim();
                for item in split_top_level_commas(after) {
                    let item = item.trim();
                    if item.is_empty() {
                        continue;
                    }
                    if item == "*" {
                        out.push(CodebaseImport {
                            file_path: file_path.to_string(),
                            line: line_no,
                            language: "python".to_string(),
                            raw: raw.chars().take(200).collect(),
                            target: format!("{module}.*"),
                            alias: None,
                        });
                        continue;
                    }
                    let (name, alias) = split_python_as(item);
                    out.push(CodebaseImport {
                        file_path: file_path.to_string(),
                        line: line_no,
                        language: "python".to_string(),
                        raw: raw.chars().take(200).collect(),
                        target: join_python_import_path(&module, &name),
                        alias,
                    });
                }
                i = end_line_idx + 1;
                continue;
            }
        }
        i += 1;
    }
    out
}

// ── TS/JS imports (Phase 2 #3 second slice — TS/JS side) ─────────────────────

/// Drop trailing `// …` line comment. String-aware for `'…'`, `"…"`, and
/// template literals `` `…` `` so a `//` inside a string isn't taken as a
/// comment opener. Template literal `${…}` interpolation is not parsed —
/// imports almost never appear inside template strings.
fn strip_ts_line_comment(s: &str) -> &str {
    let bytes = s.as_bytes();
    let mut in_str = false;
    let mut quote: u8 = b' ';
    let mut prev_bs = false;
    let mut i = 0;
    while i < bytes.len() {
        let c = bytes[i];
        if in_str {
            if c == b'\\' && !prev_bs {
                prev_bs = true;
                i += 1;
                continue;
            }
            if c == quote && !prev_bs {
                in_str = false;
            }
            prev_bs = false;
        } else if c == b'"' || c == b'\'' || c == b'`' {
            in_str = true;
            quote = c;
        } else if c == b'/' && i + 1 < bytes.len() && bytes[i + 1] == b'/' {
            return &s[..i];
        }
        i += 1;
    }
    s
}

/// Strip same-line `/* … */` block comments. Multi-line block comments
/// inside import sections are rare; we leave any unterminated `/*` to
/// truncate the rest of the line.
fn strip_ts_block_comments(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if i + 1 < bytes.len() && bytes[i] == b'/' && bytes[i + 1] == b'*' {
            if let Some(rel) = s[i + 2..].find("*/") {
                i = i + 2 + rel + 2;
                out.push(' ');
                continue;
            }
            break;
        }
        out.push(bytes[i] as char);
        i += 1;
    }
    out
}

fn is_ts_ident_char(c: u8) -> bool {
    c.is_ascii_alphanumeric() || c == b'_' || c == b'$'
}

/// Read the string literal starting at `bytes[start]` (must be a quote).
/// Returns `(content, end_exclusive)` or `None` if unterminated.
fn read_ts_string_literal(bytes: &[u8], start: usize) -> Option<(String, usize)> {
    let quote = *bytes.get(start)?;
    if quote != b'"' && quote != b'\'' && quote != b'`' {
        return None;
    }
    let mut j = start + 1;
    let mut prev_bs = false;
    let mut buf = String::new();
    while j < bytes.len() {
        let c = bytes[j];
        if c == b'\\' && !prev_bs {
            prev_bs = true;
            j += 1;
            continue;
        }
        if c == quote && !prev_bs {
            return Some((buf, j + 1));
        }
        prev_bs = false;
        buf.push(c as char);
        j += 1;
    }
    None
}

/// Find the next string literal in `s` starting at byte index `from`.
fn find_ts_next_string(s: &str, from: usize) -> Option<(String, usize)> {
    let bytes = s.as_bytes();
    let mut i = from;
    while i < bytes.len() {
        let c = bytes[i];
        if c == b'"' || c == b'\'' || c == b'`' {
            return read_ts_string_literal(bytes, i);
        }
        i += 1;
    }
    None
}

/// Parse `name as alias` for one item already split out of a brace list.
fn split_ts_as(item: &str) -> (String, Option<String>) {
    let trimmed = item.trim();
    if let Some(idx) = trimmed.rfind(" as ") {
        let name = trimmed[..idx].trim();
        let alias = trimmed[idx + 4..].trim();
        if !alias.is_empty() {
            return (name.to_string(), Some(alias.to_string()));
        }
    }
    (trimmed.to_string(), None)
}

/// Find the `from` keyword as a standalone word, string-aware. Returns the
/// last occurrence so `import { from } from 'x'` resolves to the second `from`.
fn find_ts_from_keyword(s: &str) -> Option<usize> {
    let bytes = s.as_bytes();
    let mut i = 0;
    let mut last = None;
    let mut in_str = false;
    let mut quote: u8 = b' ';
    let mut prev_bs = false;
    while i + 4 <= bytes.len() {
        let c = bytes[i];
        if in_str {
            if c == b'\\' && !prev_bs {
                prev_bs = true;
                i += 1;
                continue;
            }
            if c == quote && !prev_bs {
                in_str = false;
            }
            prev_bs = false;
            i += 1;
            continue;
        }
        if c == b'"' || c == b'\'' || c == b'`' {
            in_str = true;
            quote = c;
            i += 1;
            continue;
        }
        if &bytes[i..i + 4] == b"from" {
            let before_ok = i == 0 || !is_ts_ident_char(bytes[i - 1]);
            let after_ok = i + 4 == bytes.len() || !is_ts_ident_char(bytes[i + 4]);
            if before_ok && after_ok {
                last = Some(i);
            }
        }
        i += 1;
    }
    last
}

/// If `bytes[i..]` starts with `kw` followed by optional whitespace + `(`,
/// return the index just after `(`. Boundary-checked so `.require(` and
/// `xrequire(` don't match.
fn match_ts_call_keyword(bytes: &[u8], i: usize, kw: &str) -> Option<usize> {
    let kb = kw.as_bytes();
    if i + kb.len() > bytes.len() {
        return None;
    }
    if &bytes[i..i + kb.len()] != kb {
        return None;
    }
    if i > 0 {
        let prev = bytes[i - 1];
        if is_ts_ident_char(prev) || prev == b'.' {
            return None;
        }
    }
    let mut j = i + kb.len();
    while j < bytes.len() && (bytes[j] == b' ' || bytes[j] == b'\t') {
        j += 1;
    }
    if j < bytes.len() && bytes[j] == b'(' {
        Some(j + 1)
    } else {
        None
    }
}

/// Emit one row per importable item from a clause body. The clause body
/// is what sits between `import`/`export` and `from` (e.g. `foo`,
/// `* as ns`, `{ a, b as x }`, `foo, { a, b }`).
fn emit_ts_clause_rows(
    clause: &str,
    module: &str,
    raw_full: &str,
    line_no: u32,
    language: &str,
    file_path: &str,
    out: &mut Vec<CodebaseImport>,
) {
    let clause = clause.trim();
    if clause.is_empty() {
        return;
    }
    for part in split_top_level_commas(clause) {
        let p = part.trim();
        if p.is_empty() {
            continue;
        }
        if p.starts_with('{') && p.ends_with('}') {
            let inner = &p[1..p.len() - 1];
            for item in split_top_level_commas(inner) {
                let item = item.trim().trim_start_matches("type ").trim();
                if item.is_empty() {
                    continue;
                }
                let (name, alias) = split_ts_as(item);
                if name.is_empty() {
                    continue;
                }
                out.push(CodebaseImport {
                    file_path: file_path.to_string(),
                    line: line_no,
                    language: language.to_string(),
                    raw: raw_full.chars().take(200).collect(),
                    target: join_python_import_path(module, &name),
                    alias,
                });
            }
        } else if let Some(rest) = p.strip_prefix('*') {
            let after = rest.trim();
            let alias = after.strip_prefix("as ").map(|a| a.trim().to_string());
            out.push(CodebaseImport {
                file_path: file_path.to_string(),
                line: line_no,
                language: language.to_string(),
                raw: raw_full.chars().take(200).collect(),
                target: format!("{module}.*"),
                alias: alias.filter(|a| !a.is_empty()),
            });
        } else {
            let p = p.trim_end_matches(';').trim();
            if p.is_empty() {
                continue;
            }
            out.push(CodebaseImport {
                file_path: file_path.to_string(),
                line: line_no,
                language: language.to_string(),
                raw: raw_full.chars().take(200).collect(),
                target: module.to_string(),
                alias: Some(p.to_string()),
            });
        }
    }
}

/// Match `import …`, `export … from …`, and side-effect `import 'mod';`.
fn try_ts_static_form(
    buf: &str,
    raw_full: &str,
    line_no: u32,
    language: &str,
    file_path: &str,
    out: &mut Vec<CodebaseImport>,
) {
    let is_import = buf.starts_with("import ") || buf.starts_with("import\t");
    let is_export = buf.starts_with("export ") || buf.starts_with("export\t");
    if !is_import && !is_export {
        return;
    }

    // Side-effect-only: `import 'mod';`. Has no `from` keyword and the
    // body after `import ` is a single string literal.
    if is_import && find_ts_from_keyword(buf).is_none() {
        let rest = buf["import".len()..].trim_start().trim_end_matches(';').trim();
        if !rest.is_empty() {
            let rb = rest.as_bytes();
            if matches!(rb[0], b'"' | b'\'' | b'`') {
                if let Some((module, _)) = read_ts_string_literal(rb, 0) {
                    if !module.is_empty() {
                        out.push(CodebaseImport {
                            file_path: file_path.to_string(),
                            line: line_no,
                            language: language.to_string(),
                            raw: raw_full.chars().take(200).collect(),
                            target: module,
                            alias: None,
                        });
                    }
                }
            }
        }
        return;
    }

    let from_idx = match find_ts_from_keyword(buf) {
        Some(idx) => idx,
        None => return,
    };
    let clause = buf[..from_idx].trim_end();
    let after_from = buf[from_idx + 4..].trim_start();
    let module = match find_ts_next_string(after_from, 0) {
        Some((s, _)) if !s.is_empty() => s,
        _ => return,
    };

    let kw = if is_import { "import" } else { "export" };
    let clause_body = clause[kw.len()..].trim();
    let clause_body = clause_body
        .strip_prefix("type ")
        .map(|s| s.trim())
        .unwrap_or(clause_body);

    emit_ts_clause_rows(
        clause_body, &module, raw_full, line_no, language, file_path, out,
    );
}

/// Emit rows for `require('mod')` and dynamic `import('mod')` calls
/// occurring anywhere in the (possibly aggregated) buffer.
fn emit_ts_call_imports(
    buf: &str,
    raw_full: &str,
    line_no: u32,
    language: &str,
    file_path: &str,
    out: &mut Vec<CodebaseImport>,
) {
    let bytes = buf.as_bytes();
    let mut in_str = false;
    let mut quote: u8 = b' ';
    let mut prev_bs = false;
    let mut i = 0;
    while i < bytes.len() {
        let c = bytes[i];
        if in_str {
            if c == b'\\' && !prev_bs {
                prev_bs = true;
                i += 1;
                continue;
            }
            if c == quote && !prev_bs {
                in_str = false;
            }
            prev_bs = false;
            i += 1;
            continue;
        }
        if c == b'"' || c == b'\'' || c == b'`' {
            in_str = true;
            quote = c;
            i += 1;
            continue;
        }
        if let Some(after) = match_ts_call_keyword(bytes, i, "require")
            .or_else(|| match_ts_call_keyword(bytes, i, "import"))
        {
            if let Some((module, end)) = find_ts_next_string(&buf[after..], 0) {
                if !module.is_empty() {
                    out.push(CodebaseImport {
                        file_path: file_path.to_string(),
                        line: line_no,
                        language: language.to_string(),
                        raw: raw_full.chars().take(200).collect(),
                        target: module,
                        alias: None,
                    });
                }
                i = after + end;
                continue;
            }
        }
        i += 1;
    }
}

/// Extract TS/JS ESM `import … from …`, `export … from …`,
/// side-effect `import '…';`, dynamic `import('…')`, and CJS
/// `require('…')` calls. Convention mirrors Python: named imports become
/// `module.name`, namespace imports become `module.*`, default and
/// side-effect imports use the bare module specifier.
pub fn extract_ts_imports(
    content: &str,
    file_path: &str,
    language: &str,
) -> Vec<CodebaseImport> {
    let mut out = Vec::new();
    let lines: Vec<&str> = content.lines().collect();
    let mut i = 0usize;
    while i < lines.len() {
        let raw = lines[i];
        let working = strip_ts_block_comments(raw);
        let no_cmt = strip_ts_line_comment(&working);
        let stripped = no_cmt.trim();
        let line_no = (i as u32) + 1;

        // Multi-line aggregation: keep reading until braces balance.
        // Only aggregate when the line opens a static `import`/`export`
        // statement — a `{` on a function/object literal line would
        // otherwise sweep require()/import() calls inside the body and
        // mis-attribute their line number to the function declaration.
        let mut buf = stripped.to_string();
        let mut end_line_idx = i;
        let needs_aggregation =
            stripped.starts_with("import") || stripped.starts_with("export");
        if needs_aggregation {
            while buf.matches('{').count() > buf.matches('}').count()
                && end_line_idx + 1 < lines.len()
            {
                end_line_idx += 1;
                let nw = strip_ts_block_comments(lines[end_line_idx]);
                let next = strip_ts_line_comment(&nw).trim().to_string();
                buf.push(' ');
                buf.push_str(&next);
            }
        }

        let raw_full = if end_line_idx == i {
            raw.to_string()
        } else {
            lines[i..=end_line_idx.min(lines.len() - 1)].join(" ")
        };

        try_ts_static_form(&buf, &raw_full, line_no, language, file_path, &mut out);
        emit_ts_call_imports(&buf, &raw_full, line_no, language, file_path, &mut out);

        i = end_line_idx + 1;
    }
    out
}

// ── Go imports (Phase 2 #3 second slice — Go side) ───────────────────────────

/// Parse one Go import spec: `[NAME] "PATH"` or `` [NAME] `PATH` ``.
/// NAME may be an identifier, `_` (blank import), or `.` (dot import).
/// Returns None when no string literal is found.
fn parse_go_import_spec(s: &str) -> Option<(String, Option<String>)> {
    let s = s.trim();
    if s.is_empty() {
        return None;
    }
    let bytes = s.as_bytes();
    let mut i = 0usize;
    let mut alias: Option<String> = None;
    // Optional NAME prefix — not starting with a quote.
    if bytes[0] != b'"' && bytes[0] != b'`' {
        let mut j = 0;
        while j < bytes.len()
            && bytes[j] != b' '
            && bytes[j] != b'\t'
            && bytes[j] != b'"'
            && bytes[j] != b'`'
        {
            j += 1;
        }
        let name = &s[..j];
        if !name.is_empty() {
            alias = Some(name.to_string());
        }
        i = j;
        while i < bytes.len() && (bytes[i] == b' ' || bytes[i] == b'\t') {
            i += 1;
        }
    }
    if i >= bytes.len() {
        return None;
    }
    let quote = bytes[i];
    if quote != b'"' && quote != b'`' {
        return None;
    }
    let start = i + 1;
    let mut j = start;
    let mut prev_bs = false;
    while j < bytes.len() {
        let c = bytes[j];
        // Interpreted strings (") support escapes; raw strings (`) don't.
        if quote == b'"' && c == b'\\' && !prev_bs {
            prev_bs = true;
            j += 1;
            continue;
        }
        if c == quote && !prev_bs {
            return Some((s[start..j].to_string(), alias));
        }
        prev_bs = false;
        j += 1;
    }
    None
}

/// Extract Go `import "path"` (single, named, blank `_`, dot `.`) and
/// `import ( … )` block forms. Aggregation is line-aware: each spec
/// inside a block reports its own line. Reuses the TS comment
/// strippers since Go uses the same `//` and `/* … */` syntax.
pub fn extract_go_imports(content: &str, file_path: &str) -> Vec<CodebaseImport> {
    let mut out = Vec::new();
    let lines: Vec<&str> = content.lines().collect();
    let mut i = 0usize;
    while i < lines.len() {
        let raw = lines[i];
        let working = strip_ts_block_comments(raw);
        let no_cmt = strip_ts_line_comment(&working);
        let stripped = no_cmt.trim();
        let line_no = (i as u32) + 1;

        if let Some(rest) = stripped.strip_prefix("import") {
            let rest_trim = rest.trim_start();
            // Word boundary: `import` must be a standalone keyword (so
            // identifiers like `important` don't match).
            let next_byte = rest.as_bytes().first().copied().unwrap_or(b' ');
            let is_keyword = matches!(next_byte, b' ' | b'\t' | b'(' | b'"' | b'`');
            if !is_keyword {
                i += 1;
                continue;
            }

            // Block form: `import (` aggregates each interior line.
            if let Some(after_paren) = rest_trim.strip_prefix('(') {
                let leftover = after_paren.trim();
                if !leftover.is_empty() && !leftover.starts_with(')') {
                    // Same-line spec after `import (` — rare. Parse it.
                    if let Some((path, alias)) = parse_go_import_spec(leftover) {
                        out.push(CodebaseImport {
                            file_path: file_path.to_string(),
                            line: line_no,
                            language: "go".to_string(),
                            raw: raw.chars().take(200).collect(),
                            target: path,
                            alias,
                        });
                    }
                }
                let mut k = i + 1;
                let mut closed = false;
                while k < lines.len() {
                    let inner_raw = lines[k];
                    let inner_strip = strip_ts_line_comment(
                        &strip_ts_block_comments(inner_raw),
                    )
                    .trim()
                    .to_string();
                    if inner_strip.starts_with(')') {
                        closed = true;
                        i = k + 1;
                        break;
                    }
                    // Defensive: a `)` at end of line means this is the
                    // last spec line. Parse everything before it.
                    let spec = if let Some(idx) = inner_strip.find(')') {
                        closed = true;
                        inner_strip[..idx].trim().to_string()
                    } else {
                        inner_strip
                    };
                    if let Some((path, alias)) = parse_go_import_spec(&spec) {
                        out.push(CodebaseImport {
                            file_path: file_path.to_string(),
                            line: (k as u32) + 1,
                            language: "go".to_string(),
                            raw: inner_raw.chars().take(200).collect(),
                            target: path,
                            alias,
                        });
                    }
                    if closed {
                        i = k + 1;
                        break;
                    }
                    k += 1;
                }
                if !closed {
                    i = k;
                }
                continue;
            }

            // Single-line form: `import "path"` or `import NAME "path"`.
            if let Some((path, alias)) = parse_go_import_spec(rest_trim) {
                out.push(CodebaseImport {
                    file_path: file_path.to_string(),
                    line: line_no,
                    language: "go".to_string(),
                    raw: raw.chars().take(200).collect(),
                    target: path,
                    alias,
                });
            }
            i += 1;
            continue;
        }
        i += 1;
    }
    out
}

// ── Python ───────────────────────────────────────────────────────────────────

fn extract_python(content: &str, file_path: &str) -> Vec<CodebaseSymbol> {
    let mut out = Vec::new();
    // Stack of (indent_cols, qualified_class_name) for enclosing class scopes.
    let mut class_stack: Vec<(usize, String)> = Vec::new();

    for (i, raw) in content.lines().enumerate() {
        // Count leading whitespace cols (tabs count as 1 — close enough for
        // scope detection; Python forbids mixing in real code).
        let indent = raw.chars().take_while(|c| *c == ' ' || *c == '\t').count();
        let t = raw.trim();
        if t.is_empty() || t.starts_with('#') {
            continue;
        }
        // Pop class scopes whose body has ended (current line dedented to <= scope indent).
        while let Some(&(ind, _)) = class_stack.last() {
            if indent <= ind {
                class_stack.pop();
            } else {
                break;
            }
        }

        // `def` / `async def`
        let def_rest = t
            .strip_prefix("async def ")
            .or_else(|| t.strip_prefix("def "));
        if let Some(rest) = def_rest {
            let name: String = rest
                .chars()
                .take_while(|c| c.is_alphanumeric() || *c == '_')
                .collect();
            if !name.is_empty() {
                let (kind, emit_name) = if let Some((_, cls)) = class_stack.last() {
                    ("method", format!("{cls}.{name}"))
                } else {
                    ("def", name)
                };
                out.push(make(file_path, (i + 1) as u32, kind, emit_name, t, "python"));
            }
            continue;
        }
        // `class`
        if let Some(rest) = t.strip_prefix("class ") {
            let name: String = rest
                .chars()
                .take_while(|c| c.is_alphanumeric() || *c == '_')
                .collect();
            if !name.is_empty() {
                let qualified = if let Some((_, parent)) = class_stack.last() {
                    format!("{parent}.{name}")
                } else {
                    name.clone()
                };
                out.push(make(
                    file_path,
                    (i + 1) as u32,
                    "class",
                    qualified.clone(),
                    t,
                    "python",
                ));
                class_stack.push((indent, qualified));
            }
        }
    }
    out
}

// ── Python calls (Phase 2 #3 third slice — Python side) ──────────────────────

/// Python keywords / soft keywords that can appear in `ident(` shape but
/// are not function calls (e.g. `if (cond):`, `return(x)`, `yield (x)`).
/// Mirrors [`is_rust_call_keyword`]'s policy: language keywords are
/// filtered out; built-ins (`print`, `len`, `range`, …) are emitted as
/// real calls because they ARE function calls at runtime and are useful
/// as graph leaves. `True`/`False`/`None` are reserved but won't appear
/// before `(` in valid code; included defensively.
fn is_python_call_keyword(s: &str) -> bool {
    matches!(
        s,
        "if" | "elif"
            | "else"
            | "while"
            | "for"
            | "in"
            | "not"
            | "and"
            | "or"
            | "is"
            | "lambda"
            | "return"
            | "yield"
            | "await"
            | "raise"
            | "assert"
            | "del"
            | "from"
            | "import"
            | "as"
            | "pass"
            | "break"
            | "continue"
            | "global"
            | "nonlocal"
            | "with"
            | "try"
            | "except"
            | "finally"
            | "class"
            | "def"
            | "async"
            | "True"
            | "False"
            | "None"
    )
}

fn is_python_ident_char(c: u8) -> bool {
    c.is_ascii_alphanumeric() || c == b'_'
}

fn skip_python_whitespace(bytes: &[u8], i: usize) -> usize {
    let mut k = i;
    while k < bytes.len() && (bytes[k] == b' ' || bytes[k] == b'\t') {
        k += 1;
    }
    k
}

/// Python equivalent of [`mask_strings_and_comments`]. Replaces the
/// interior of string literals (`'…'`, `"…"`, triple-quoted `"""…"""`
/// and `'''…'''`, plus their `r`/`b`/`f`/`rb`/`br`/`u` prefixes) and
/// `# …` line comments with spaces. Preserves newlines + the delimiters
/// themselves so per-line scanning sees a string-like shell but no
/// code-like interior.
///
/// Limitations:
/// - `f"…{expr}…"` f-string interpolations: the interior including the
///   `{expr}` is masked out, so calls inside f-strings won't be
///   detected. Acceptable: such calls are rare in normal code.
/// - String concatenation across lines via `\` line continuation is
///   handled by the parser naturally because we mask per-character.
fn mask_python_strings_and_comments(content: &str) -> String {
    enum State {
        Normal,
        // Single-quoted string with given delimiter byte (`'` or `"`).
        Str(u8),
        // Triple-quoted string with given delimiter byte (`'` or `"`).
        Triple(u8),
        LineCmt,
    }
    let mut state = State::Normal;
    let mut prev_bs = false;
    let bytes = content.as_bytes();
    let mut out = String::with_capacity(content.len());
    let mut i = 0usize;
    while i < bytes.len() {
        let c = bytes[i];
        match state {
            State::Normal => {
                // Detect string prefix (r, b, f, u, rb, br, fr, rf, …).
                // We only need to know where the quote starts — the
                // prefix chars themselves are passed through unchanged.
                let mut k = i;
                while k < bytes.len()
                    && matches!(
                        bytes[k],
                        b'r' | b'R' | b'b' | b'B' | b'f' | b'F' | b'u' | b'U'
                    )
                    && k - i < 2
                {
                    k += 1;
                }
                // Word-boundary: chars before `i` must not be ident chars,
                // otherwise `er"foo"` isn't actually a string prefix.
                let before_ok = i == 0
                    || (!bytes[i - 1].is_ascii_alphanumeric() && bytes[i - 1] != b'_');
                if k > i
                    && before_ok
                    && k < bytes.len()
                    && (bytes[k] == b'"' || bytes[k] == b'\'')
                {
                    // Emit prefix chars verbatim, fall through with i = k.
                    for j in i..k {
                        out.push(bytes[j] as char);
                    }
                    i = k;
                    continue;
                }
                if c == b'#' {
                    state = State::LineCmt;
                    out.push(' ');
                    i += 1;
                    continue;
                }
                // Triple-quoted detection — `"""` or `'''`.
                if (c == b'"' || c == b'\'')
                    && i + 2 < bytes.len()
                    && bytes[i + 1] == c
                    && bytes[i + 2] == c
                {
                    out.push(c as char);
                    out.push(c as char);
                    out.push(c as char);
                    state = State::Triple(c);
                    i += 3;
                    continue;
                }
                if c == b'"' || c == b'\'' {
                    state = State::Str(c);
                    out.push(c as char);
                    i += 1;
                    continue;
                }
                out.push(c as char);
                i += 1;
            }
            State::Str(quote) => {
                if c == b'\\' && !prev_bs {
                    prev_bs = true;
                    out.push('\\');
                    i += 1;
                    continue;
                }
                if c == quote && !prev_bs {
                    state = State::Normal;
                    out.push(c as char);
                    prev_bs = false;
                    i += 1;
                    continue;
                }
                if c == b'\n' {
                    // Unterminated single-quoted string: drop back to
                    // Normal at newline (Python forbids raw newline in
                    // non-triple strings).
                    state = State::Normal;
                    out.push('\n');
                    prev_bs = false;
                    i += 1;
                    continue;
                }
                prev_bs = false;
                out.push(' ');
                i += 1;
            }
            State::Triple(quote) => {
                // Closing is three consecutive `quote` bytes.
                if c == quote
                    && i + 2 < bytes.len()
                    && bytes[i + 1] == quote
                    && bytes[i + 2] == quote
                {
                    out.push(c as char);
                    out.push(c as char);
                    out.push(c as char);
                    state = State::Normal;
                    i += 3;
                    continue;
                }
                if c == b'\n' {
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
            State::LineCmt => {
                if c == b'\n' {
                    state = State::Normal;
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
        }
    }
    out
}

/// Walk one Python line and emit one [`CodebaseCall`] per call expression.
/// Recognises bare calls (`foo(`), dotted-path calls (`Foo.bar(`,
/// `mod.Cls.method(`), and method calls on an expression (`obj.method(`,
/// `self.foo(`). Subscripts (`func[int](`) are stripped so the callee
/// path is the bare identifier path. Skips Python keywords.
///
/// Output convention (mirrors the Rust extractor):
/// - Bare or dotted-path call ending in an upper-case-irrelevant ident:
///   callee = full path (e.g. `foo`, `Foo.bar`, `os.path.join`).
/// - Single-segment method call on a non-trivial expression that we
///   can't reduce to a path: callee = `.method` (e.g. `result.bar()`
///   after `result = something()`).
/// - `self.NAME(…)` is treated as a method-style call → `.NAME` so
///   "who calls `.bar`" lights up both `self.bar()` and `obj.bar()`.
///   `Cls.NAME(…)` keeps the class prefix so it doesn't blur with
///   instance-method calls.
fn extract_python_calls_from_line(
    line: &str,
    line_no: u32,
    caller: &str,
    file_path: &str,
    out: &mut Vec<CodebaseCall>,
) {
    let bytes = line.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() {
        let c = bytes[i];
        // Identifier (start of bare or dotted path). Must be at word boundary.
        if c.is_ascii_alphabetic() || c == b'_' {
            if i > 0 && (is_python_ident_char(bytes[i - 1]) || bytes[i - 1] == b'.') {
                i += 1;
                continue;
            }
            let start_first = i;
            let mut j = i;
            while j < bytes.len() && is_python_ident_char(bytes[j]) {
                j += 1;
            }
            let first_seg = &line[start_first..j];
            let mut parts: Vec<String> = vec![first_seg.to_string()];
            // Extend through `.ident` chains. Also tolerate `[…]` subscript
            // (`func[int](…)`) between path and `(`.
            loop {
                let mut k = j;
                if k < bytes.len() && bytes[k] == b'[' {
                    // Skip balanced `[…]`.
                    let mut depth = 1i32;
                    k += 1;
                    while k < bytes.len() && depth > 0 {
                        if bytes[k] == b'[' {
                            depth += 1;
                        } else if bytes[k] == b']' {
                            depth -= 1;
                        }
                        k += 1;
                    }
                    j = k;
                    continue;
                }
                if k < bytes.len() && bytes[k] == b'.' {
                    let s = k + 1;
                    let mut t = s;
                    while t < bytes.len() && is_python_ident_char(bytes[t]) {
                        t += 1;
                    }
                    if t == s {
                        break;
                    }
                    parts.push(line[s..t].to_string());
                    j = t;
                    continue;
                }
                break;
            }
            let k = skip_python_whitespace(bytes, j);
            if k < bytes.len() && bytes[k] == b'(' {
                // Check for `def`/`class` header on this line — caller
                // logic in the outer loop already skips declaration lines,
                // so we don't need to re-check here.
                let last_seg = parts.last().cloned().unwrap_or_default();
                if !is_python_call_keyword(&last_seg) {
                    let callee = if parts.len() == 1 {
                        // Bare identifier call.
                        parts[0].clone()
                    } else if parts[0] == "self" || parts[0] == "cls" {
                        // `self.foo(…)` → `.foo`. For longer chains like
                        // `self.a.b()`, keep the trailing-segment shape:
                        // we can't tell from a single line whether `a`
                        // is a sub-attr or a re-binding, so collapse to
                        // `.b` (the final call) — matches Rust's policy
                        // of emitting `.method` for unresolved receivers.
                        format!(".{last_seg}")
                    } else {
                        // Qualified path: `Foo.bar`, `os.path.join`, etc.
                        parts.join(".")
                    };
                    out.push(CodebaseCall {
                        file_path: file_path.to_string(),
                        line: line_no,
                        language: "python".to_string(),
                        caller: caller.to_string(),
                        callee,
                    });
                }
            }
            i = j;
            continue;
        }
        // Dotted method call on a non-ident receiver (e.g. `x.y().bar()`
        // — after consuming `x.y` as a path, the `.bar` is left over).
        // Same pattern as Rust's method-call branch.
        if c == b'.'
            && i + 1 < bytes.len()
            && (bytes[i + 1].is_ascii_alphabetic() || bytes[i + 1] == b'_')
            && (i == 0 || !is_python_ident_char(bytes[i - 1]))
        {
            let start = i + 1;
            let mut j = start;
            while j < bytes.len() && is_python_ident_char(bytes[j]) {
                j += 1;
            }
            let name = &line[start..j];
            let mut k = j;
            // Tolerate subscript before `(`.
            if k < bytes.len() && bytes[k] == b'[' {
                let mut depth = 1i32;
                k += 1;
                while k < bytes.len() && depth > 0 {
                    if bytes[k] == b'[' {
                        depth += 1;
                    } else if bytes[k] == b']' {
                        depth -= 1;
                    }
                    k += 1;
                }
            }
            k = skip_python_whitespace(bytes, k);
            if k < bytes.len() && bytes[k] == b'(' && !is_python_call_keyword(name) {
                out.push(CodebaseCall {
                    file_path: file_path.to_string(),
                    line: line_no,
                    language: "python".to_string(),
                    caller: caller.to_string(),
                    callee: format!(".{name}"),
                });
            }
            i = j;
            continue;
        }
        i += 1;
    }
}

/// Python scope record. Indent col is the column the `def`/`class`
/// keyword started at; the body lives at strictly greater indent.
#[derive(Debug, Clone)]
struct PythonScope {
    indent: usize,
    /// Qualified name as it should appear in the `caller` column.
    /// For `def foo` at file scope: `foo`. Inside `class Foo:`: `Foo.foo`.
    /// Nested defs: `outer.inner` (or `Foo.outer.inner` inside a class).
    qualified: String,
    /// Whether this scope is a class (so we don't list it as a caller —
    /// callers are only `def`s).
    is_class: bool,
}

/// Extract call sites from a Python file. Tracks the enclosing function
/// via indent-based scope stack: each `def`/`async def`/`class` line
/// pushes a scope at the indent it sits at, and a non-blank line at
/// indent <= scope.indent pops it. Mirrors [`extract_python`]'s class-
/// scope logic but adds `def`-scopes for caller attribution.
///
/// Python differs from Rust in three structural ways:
/// 1. **Indent vs braces**: no `{`/`}` to count, so scope pop is keyed
///    on the first non-blank line at indent ≤ the scope's indent (rather
///    than `depth <= open_depth`). Blank/comment lines are skipped so
///    they don't trigger spurious pops.
/// 2. **No turbofish**: Python uses `[T]` subscript for generics. The
///    extractor strips `[…]` between path and `(` so `func[int]()`
///    normalises to `func` — analogous to Rust's `Vec::<u8>::new` →
///    `Vec::new`.
/// 3. **Class scopes contribute to caller name, not to call sites**.
///    A `class Foo:` line is NOT a caller (calls at class-body scope
///    that AREN'T inside a `def` are emitted with the surrounding
///    `def`'s name if any, otherwise empty — mirroring Rust's file-
///    scope policy).
pub fn extract_python_calls(content: &str, file_path: &str) -> Vec<CodebaseCall> {
    let masked = mask_python_strings_and_comments(content);
    let mut out = Vec::new();
    let mut scope_stack: Vec<PythonScope> = Vec::new();

    for (i, raw) in masked.lines().enumerate() {
        let line_no = (i as u32) + 1;
        // Compute indent (tabs counted as 1 column — same convention as
        // extract_python). Blank / comment lines don't affect scope.
        let indent = raw.chars().take_while(|c| *c == ' ' || *c == '\t').count();
        let t = raw.trim();
        if t.is_empty() {
            continue;
        }
        // After masking, a `#`-line becomes spaces but the trimmed
        // result will be empty (handled above). A leading `#` only
        // appears if the masker didn't reach it, which shouldn't happen.

        // Pop scopes whose body has ended (current line dedented to <= scope indent).
        while let Some(scope) = scope_stack.last() {
            if indent <= scope.indent {
                scope_stack.pop();
            } else {
                break;
            }
        }

        // Strip a leading `@decorator` line — decorators are not call
        // sites for the function they decorate, but their argument list
        // (if any) IS a call expression. Treat the whole `@…` line as
        // a declaration line to mirror Rust's `is_decl_line` skip.
        let is_decorator = t.starts_with('@');

        // Detect `def` / `async def` / `class` headers.
        let def_rest = t
            .strip_prefix("async def ")
            .or_else(|| t.strip_prefix("def "));
        let mut is_decl_line = is_decorator;

        if let Some(rest) = def_rest {
            is_decl_line = true;
            let name: String = rest
                .chars()
                .take_while(|c| c.is_alphanumeric() || *c == '_')
                .collect();
            if !name.is_empty() {
                // Build qualified caller from current scope chain.
                let prefix: Vec<&str> = scope_stack
                    .iter()
                    .map(|s| s.qualified.as_str())
                    .collect();
                let qualified = if let Some(last) = prefix.last() {
                    format!("{last}.{name}")
                } else {
                    name.clone()
                };
                scope_stack.push(PythonScope {
                    indent,
                    qualified,
                    is_class: false,
                });
            }
        } else if let Some(rest) = t.strip_prefix("class ") {
            is_decl_line = true;
            let name: String = rest
                .chars()
                .take_while(|c| c.is_alphanumeric() || *c == '_')
                .collect();
            if !name.is_empty() {
                // Class qualified name mirrors extract_python: nested
                // class inside another class joins with `.`.
                let prefix: Vec<&str> = scope_stack
                    .iter()
                    .filter(|s| s.is_class)
                    .map(|s| s.qualified.as_str())
                    .collect();
                let qualified = if let Some(last) = prefix.last() {
                    format!("{last}.{name}")
                } else {
                    name.clone()
                };
                scope_stack.push(PythonScope {
                    indent,
                    qualified,
                    is_class: true,
                });
            }
        }

        if !is_decl_line {
            // Caller is the innermost `def` scope (skip class scopes —
            // a call directly inside a class body but not in a method
            // is at module-init time and should attribute to the
            // enclosing def, or empty if none).
            let caller = scope_stack
                .iter()
                .rev()
                .find(|s| !s.is_class)
                .map(|s| s.qualified.as_str())
                .unwrap_or("");
            extract_python_calls_from_line(raw, line_no, caller, file_path, &mut out);
        }
    }
    out
}

// ── TypeScript / JavaScript ──────────────────────────────────────────────────

fn extract_ts_js(content: &str, file_path: &str, lang: &str) -> Vec<CodebaseSymbol> {
    let mut out = Vec::new();
    for (i, raw) in content.lines().enumerate() {
        let t = raw.trim();
        if t.starts_with("//") || t.starts_with("/*") || t.starts_with('*') {
            continue;
        }
        // Strip common prefixes
        let s = t
            .trim_start_matches("export default ")
            .trim_start_matches("export ")
            .trim_start_matches("declare ");

        if let Some((kind, name)) = try_kw(
            s,
            &[
                ("async function ", "function"),
                ("function ", "function"),
                ("class ", "class"),
                ("interface ", "interface"),
                ("type ", "type"),
                ("enum ", "enum"),
                ("abstract class ", "class"),
            ],
        ) {
            out.push(make(file_path, (i + 1) as u32, kind, name, t, lang));
            continue;
        }

        // `const/let/var NAME = ...` — only capture arrow functions and class expressions
        for prefix in &["const ", "let "] {
            if let Some(rest) = s.strip_prefix(prefix) {
                let name: String = rest
                    .chars()
                    .take_while(|c| c.is_alphanumeric() || *c == '_' || *c == '$')
                    .collect();
                if name.is_empty() {
                    continue;
                }
                let after_name = rest[name.len()..].trim_start();
                // Only emit if assigned to an arrow function or class expression
                if after_name.starts_with("= (")
                    || after_name.starts_with("= async (")
                    || after_name.starts_with("= () =>")
                    || after_name.starts_with("= class")
                {
                    out.push(make(file_path, (i + 1) as u32, "const", name, t, lang));
                }
                break;
            }
        }
    }
    out
}

// ── Go ───────────────────────────────────────────────────────────────────────

fn extract_go(content: &str, file_path: &str) -> Vec<CodebaseSymbol> {
    let mut out = Vec::new();
    for (i, raw) in content.lines().enumerate() {
        let t = raw.trim();
        if t.starts_with("//") {
            continue;
        }
        if let Some((kind, name)) = try_kw(
            t,
            &[
                ("func (", "method"),
                ("func ", "func"),
                ("type ", "type"),
                ("var ", "var"),
                ("const ", "const"),
            ],
        ) {
            // For method receivers `func (r Type) Name(...)`, extract `Name`
            let actual_name = if kind == "method" {
                let paren_close = name.find(')').unwrap_or(name.len());
                let after = t[t.find("func (").unwrap_or(0) + 6..]
                    .get(paren_close + 1..)
                    .unwrap_or("")
                    .trim()
                    .trim_start_matches(')')
                    .trim();
                after
                    .chars()
                    .take_while(|c| c.is_alphanumeric() || *c == '_')
                    .collect::<String>()
            } else {
                name.clone()
            };
            if !actual_name.is_empty() {
                out.push(make(file_path, (i + 1) as u32, kind, actual_name, t, "go"));
            }
        }
    }
    out
}

// ── Go calls (Phase 2 #3 third slice — Go side) ──────────────────────────────

fn is_go_call_keyword(s: &str) -> bool {
    // Keywords and control-flow constructs that can sit just before `(`
    // (e.g. `if (cond)` is uncommon but legal-looking; `for (init; cond;
    // post)` is invalid Go but a defensive filter keeps the extractor
    // robust to malformed snippets).
    //
    // `panic`, `recover`, `print`, `println` are filtered here (control-
    // flow / debug builtins). `make`, `new`, `len`, `cap`, `append`,
    // `copy`, `delete` are NOT filtered — they're real function calls
    // useful in a call graph.
    //
    // `defer X()` and `go X()` are handled specially in the call extractor
    // (the inner call `X` is recorded, not the keyword itself), so `defer`
    // / `go` appear here so they aren't mis-recorded if they ever land
    // before `(` directly.
    matches!(
        s,
        "if" | "else"
            | "for"
            | "switch"
            | "case"
            | "default"
            | "select"
            | "return"
            | "break"
            | "continue"
            | "goto"
            | "fallthrough"
            | "defer"
            | "go"
            | "chan"
            | "range"
            | "type"
            | "var"
            | "const"
            | "package"
            | "import"
            | "func"
            | "interface"
            | "struct"
            | "map"
            | "panic"
            | "recover"
            | "print"
            | "println"
            | "true"
            | "false"
            | "nil"
    )
}

fn is_go_ident_char(c: u8) -> bool {
    c.is_ascii_alphanumeric() || c == b'_'
}

fn skip_go_whitespace(bytes: &[u8], i: usize) -> usize {
    let mut k = i;
    while k < bytes.len() && (bytes[k] == b' ' || bytes[k] == b'\t') {
        k += 1;
    }
    k
}

/// Skip a balanced `[…]` instantiation (Go generics: `F[int]`, `M[T, U]`).
/// Returns the index past the closing `]`. If `bytes[i] != '['`, returns
/// `i` unchanged.
fn skip_go_type_params(bytes: &[u8], i: usize) -> usize {
    if i >= bytes.len() || bytes[i] != b'[' {
        return i;
    }
    let mut k = i + 1;
    let mut depth = 1i32;
    while k < bytes.len() && depth > 0 {
        if bytes[k] == b'[' {
            depth += 1;
        } else if bytes[k] == b']' {
            depth -= 1;
        }
        k += 1;
    }
    k
}

/// Replace the interior of Go string literals (`"…"`, raw `` `…` ``), rune
/// literals (`'x'`, `'\n'`), and comment bodies (`// …`, `/* … */`) with
/// spaces, preserving newlines + the delimiters themselves. Raw strings
/// can span multiple lines and do NOT process escapes — critical because
/// a raw string with `{` inside would otherwise corrupt brace counting.
fn mask_go_strings_and_comments(content: &str) -> String {
    enum State {
        Normal,
        Str,
        RawStr,
        LineCmt,
        BlockCmt,
    }
    let mut state = State::Normal;
    let mut prev_bs = false;
    let bytes = content.as_bytes();
    let mut out = String::with_capacity(content.len());
    let mut i = 0usize;
    while i < bytes.len() {
        let c = bytes[i];
        match state {
            State::Normal => {
                if c == b'"' {
                    state = State::Str;
                    out.push('"');
                    i += 1;
                    continue;
                }
                if c == b'`' {
                    state = State::RawStr;
                    out.push('`');
                    i += 1;
                    continue;
                }
                if c == b'\'' {
                    // Rune literal: scan to the matching `'`. Bounded so
                    // a lone `'` won't run away (Go has no apostrophe-
                    // identifier syntax like Rust lifetimes).
                    out.push('\'');
                    let mut k = i + 1;
                    let mut esc = false;
                    while k < bytes.len() {
                        let cc = bytes[k];
                        if cc == b'\n' {
                            break;
                        }
                        if esc {
                            esc = false;
                            out.push(' ');
                            k += 1;
                            continue;
                        }
                        if cc == b'\\' {
                            esc = true;
                            out.push(' ');
                            k += 1;
                            continue;
                        }
                        if cc == b'\'' {
                            out.push('\'');
                            k += 1;
                            break;
                        }
                        out.push(' ');
                        k += 1;
                    }
                    i = k;
                    continue;
                }
                if c == b'/' && i + 1 < bytes.len() && bytes[i + 1] == b'/' {
                    state = State::LineCmt;
                    out.push(' ');
                    out.push(' ');
                    i += 2;
                    continue;
                }
                if c == b'/' && i + 1 < bytes.len() && bytes[i + 1] == b'*' {
                    state = State::BlockCmt;
                    out.push(' ');
                    out.push(' ');
                    i += 2;
                    continue;
                }
                out.push(c as char);
                i += 1;
            }
            State::Str => {
                if c == b'\\' && !prev_bs {
                    prev_bs = true;
                    out.push('\\');
                    i += 1;
                    continue;
                }
                if c == b'"' && !prev_bs {
                    state = State::Normal;
                    out.push('"');
                    prev_bs = false;
                    i += 1;
                    continue;
                }
                if c == b'\n' {
                    // Unterminated interpreted string: drop back to Normal
                    // (Go forbids raw newlines in "..." strings).
                    state = State::Normal;
                    out.push('\n');
                    prev_bs = false;
                    i += 1;
                    continue;
                }
                prev_bs = false;
                out.push(' ');
                i += 1;
            }
            State::RawStr => {
                if c == b'`' {
                    state = State::Normal;
                    out.push('`');
                    i += 1;
                    continue;
                }
                // Raw strings can span lines; preserve newlines so per-
                // line scanning still produces the right number of lines.
                if c == b'\n' {
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
            State::LineCmt => {
                if c == b'\n' {
                    state = State::Normal;
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
            State::BlockCmt => {
                if c == b'*' && i + 1 < bytes.len() && bytes[i + 1] == b'/' {
                    state = State::Normal;
                    out.push(' ');
                    out.push(' ');
                    i += 2;
                    continue;
                }
                if c == b'\n' {
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
        }
    }
    out
}

/// Parse a Go function/method declaration header into its qualified caller
/// name and report whether the line opens a body (`{` on this line).
///
/// Returns `Some((qualified, opens_body))` when the line starts with `func `
/// (possibly with a receiver group). Examples:
///   `func Name(...)`            → `("Name", _)`
///   `func Name[T any](...)`     → `("Name", _)`
///   `func (r T) Method(...)`    → `("T.Method", _)`
///   `func (r *T) Method(...)`   → `("T.Method", _)`
///   `func (r T[U]) Method(...)` → `("T.Method", _)`
///   `func() { … }`              → `None` (anonymous func — transparent
///                                  to scope; caller of inner calls
///                                  remains the enclosing scope).
///
/// `opens_body` is `true` if the line contains an unmatched `{` at the
/// top level (after masking strings/comments — caller passes a masked
/// line). For headers spanning multiple lines (`func F(\n  a int,\n) {`)
/// the caller waits for the brace by checking subsequent lines.
fn parse_go_func_header(line: &str) -> Option<(String, bool)> {
    let t = line.trim_start();
    let rest = t.strip_prefix("func")?;
    // Must be followed by a token boundary: space, tab, or `(` (receiver
    // group, or anonymous-func like `func()`).
    let first = rest.as_bytes().first().copied()?;
    if !matches!(first, b' ' | b'\t' | b'(') {
        return None;
    }
    let after = rest.trim_start();
    let bytes = after.as_bytes();

    // Anonymous func: `func(` (no name, no receiver-then-name).
    if bytes.first().copied() == Some(b'(') {
        // Could be either (a) receiver group `func (r T) Name(...)`
        // or (b) anonymous `func(... ) { ... }`. Distinguish by what
        // follows the matched `)`:
        //   - identifier → receiver group, this is a method
        //   - `{` / nothing / type-keywords → anonymous func
        let close = match_balanced(bytes, 0, b'(', b')');
        let close = match close {
            Some(k) => k,
            None => return None,
        };
        // Look at what follows the `)`.
        let mut k = close + 1;
        while k < bytes.len() && (bytes[k] == b' ' || bytes[k] == b'\t') {
            k += 1;
        }
        if k < bytes.len() && (bytes[k].is_ascii_alphabetic() || bytes[k] == b'_') {
            // Method declaration: parse receiver group, then name.
            let recv_inner = &after[1..close];
            let receiver_type = parse_go_receiver_type(recv_inner)?;
            let mut j = k;
            while j < bytes.len() && is_go_ident_char(bytes[j]) {
                j += 1;
            }
            let name = &after[k..j];
            let opens = line_opens_body(line);
            return Some((format!("{receiver_type}.{name}"), opens));
        }
        // Anonymous function — no caller name to push.
        return None;
    }

    // Plain function: `func Name`. Read identifier.
    let mut j = 0usize;
    while j < bytes.len() && is_go_ident_char(bytes[j]) {
        j += 1;
    }
    if j == 0 {
        return None;
    }
    let name = &after[..j];
    let opens = line_opens_body(line);
    Some((name.to_string(), opens))
}

/// Parse a Go method receiver group's inner content (the part between
/// `(` and `)`) and return the bare type name. Strips pointer `*` and
/// generic type parameters `[T]`.
///
/// Examples:
///   `r T`           → `Some("T")`
///   `r *T`          → `Some("T")`
///   `T`             → `Some("T")` (unnamed receiver)
///   `*T`            → `Some("T")`
///   `r T[U]`        → `Some("T")`
///   `r *T[U, V]`    → `Some("T")`
fn parse_go_receiver_type(inner: &str) -> Option<String> {
    let s = inner.trim();
    // Split on whitespace; receiver may be `name Type` or just `Type`.
    // We want the last whitespace-separated token (the type), then strip
    // leading `*` and trailing `[…]`.
    let last = s.rsplit(|c: char| c.is_whitespace()).next()?;
    let last = last.trim_start_matches('*');
    // Cut at the first `[` (type parameters).
    let bare = last.split('[').next().unwrap_or(last);
    if bare.is_empty() {
        return None;
    }
    Some(bare.to_string())
}

/// Find the matching `close` for an `open` at `bytes[start]`, with simple
/// nesting (no string awareness — caller should pass already-masked input).
/// Returns the index of the matching close, or None if unbalanced.
fn match_balanced(bytes: &[u8], start: usize, open: u8, close: u8) -> Option<usize> {
    if start >= bytes.len() || bytes[start] != open {
        return None;
    }
    let mut depth = 0i32;
    let mut k = start;
    while k < bytes.len() {
        if bytes[k] == open {
            depth += 1;
        } else if bytes[k] == close {
            depth -= 1;
            if depth == 0 {
                return Some(k);
            }
        }
        k += 1;
    }
    None
}

/// True if `line` (already masked) has a net-positive brace balance, i.e.
/// at least one `{` more than `}`. Used to detect "this line opens the
/// function body" without re-scanning.
fn line_opens_body(line: &str) -> bool {
    let (opens, closes) = count_braces(line);
    opens > closes
}

/// Walk one masked Go line and emit one [`CodebaseCall`] per call site.
/// Recognises bare calls (`foo(`), package-qualified calls (`pkg.Func(`),
/// method calls (`obj.Method(`), and generic instantiations
/// (`F[int](…)` / `M.Method[T, U](…)`). Skips Go keywords / control-flow
/// constructs, and skips immediate-invocation of anonymous funcs
/// (`func() {...}()` — the trailing `()` has no identifier callee).
fn extract_go_calls_from_line(
    line: &str,
    line_no: u32,
    caller: &str,
    file_path: &str,
    out: &mut Vec<CodebaseCall>,
) {
    let bytes = line.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() {
        let c = bytes[i];
        // Method-call on a non-ident receiver: `.Name(` after consuming
        // a path. Must NOT be glued to the preceding identifier (that
        // case is handled by the path walker below); only fire when
        // the previous byte is non-ident (e.g. `)`, `]`, whitespace).
        if c == b'.'
            && i + 1 < bytes.len()
            && (bytes[i + 1].is_ascii_alphabetic() || bytes[i + 1] == b'_')
            && (i == 0 || !is_go_ident_char(bytes[i - 1]))
        {
            let start = i + 1;
            let mut j = start;
            while j < bytes.len() && is_go_ident_char(bytes[j]) {
                j += 1;
            }
            let name = &line[start..j];
            let mut k = skip_go_type_params(bytes, j);
            k = skip_go_whitespace(bytes, k);
            if k < bytes.len() && bytes[k] == b'(' && !is_go_call_keyword(name) {
                out.push(CodebaseCall {
                    file_path: file_path.to_string(),
                    line: line_no,
                    language: "go".to_string(),
                    caller: caller.to_string(),
                    callee: format!(".{name}"),
                });
            }
            i = j;
            continue;
        }
        if c.is_ascii_alphabetic() || c == b'_' {
            // Must be at a word boundary.
            if i > 0 && (is_go_ident_char(bytes[i - 1]) || bytes[i - 1] == b'.') {
                i += 1;
                continue;
            }
            let start_first = i;
            let mut j = i;
            while j < bytes.len() && is_go_ident_char(bytes[j]) {
                j += 1;
            }
            let first_seg = &line[start_first..j];
            let mut parts: Vec<&str> = vec![first_seg];
            // Extend through `.Ident` chains. (Go has no `::`.)
            loop {
                if j < bytes.len() && bytes[j] == b'.' {
                    let s = j + 1;
                    let mut t = s;
                    while t < bytes.len() && is_go_ident_char(bytes[t]) {
                        t += 1;
                    }
                    if t == s {
                        break;
                    }
                    parts.push(&line[s..t]);
                    j = t;
                    continue;
                }
                break;
            }
            // Strip trailing generic instantiation `[T, U]` then whitespace.
            let mut k = skip_go_type_params(bytes, j);
            k = skip_go_whitespace(bytes, k);
            let last_seg = parts.last().copied().unwrap_or("");
            if k < bytes.len() && bytes[k] == b'(' {
                if !is_go_call_keyword(last_seg) && !is_go_call_keyword(parts[0]) {
                    let callee = if parts.len() == 1 {
                        parts[0].to_string()
                    } else {
                        // `pkg.Func` / `obj.Method` / `pkg.sub.Func` — keep
                        // dotted path so package-qualified calls survive.
                        // Receiver-vs-package can't be distinguished
                        // without type info; we record the literal text.
                        parts.join(".")
                    };
                    out.push(CodebaseCall {
                        file_path: file_path.to_string(),
                        line: line_no,
                        language: "go".to_string(),
                        caller: caller.to_string(),
                        callee,
                    });
                }
            }
            i = j;
            continue;
        }
        i += 1;
    }
}

/// Scope record for the enclosing function during Go call extraction.
/// `open_depth` is the brace depth just before the function's opening
/// `{` — when depth drops back to this value, the scope pops.
#[derive(Debug, Clone)]
struct GoFnScope {
    qualified: String,
    open_depth: i32,
}

/// Extract call sites from a Go file.
///
/// Scope tracking is brace-counted (mirrors [`extract_rust_calls`]):
/// each `func …` declaration ending with `{` (or whose `{` lands on a
/// later line) pushes a [`GoFnScope`]; the scope pops when the brace
/// depth drops back below `open_depth`.
///
/// Method receivers (`func (r Type) M`) and pointer receivers
/// (`func (r *Type) M`) are normalised to `Type.M`. Generic functions
/// (`func F[T any]()`) and generic receivers (`func (r T[U]) M()`) are
/// also normalised (type parameters stripped).
///
/// Anonymous function literals (`func() { ... }`) are treated as
/// *transparent* to scope: they do NOT push a new caller, and calls
/// inside them attribute to the surrounding function. This is the
/// commonly useful policy for `defer func() { cleanup() }()` and
/// `go func() { work() }()` patterns where the closure exists to
/// capture the outer function's work.
///
/// Known limitations:
/// - **Interface method dispatch**: `iface.Method()` is recorded as
///   `.Method` with no way to resolve the concrete implementing type.
///   Same as Rust's trait-object dispatch.
/// - **`init()` and `main()` module-level work**: calls inside `var x
///   = compute()` at file scope record an empty caller. Mirrors Rust
///   const-init policy.
/// - **Inline functions**: `func F() { call() }` declared and closed
///   on one line emits the call with caller `F` only if the brace
///   balance lands on that same line — which it does, since both
///   `{` and `}` count and `F` is pushed before the call walker runs.
pub fn extract_go_calls(content: &str, file_path: &str) -> Vec<CodebaseCall> {
    let masked = mask_go_strings_and_comments(content);
    let mut out = Vec::new();
    let mut depth: i32 = 0;
    let mut fn_stack: Vec<GoFnScope> = Vec::new();
    // When a `func …` header doesn't have `{` on the same line, hold
    // its qualified name here until the brace arrives.
    let mut pending_fn: Option<String> = None;

    for (i, raw) in masked.lines().enumerate() {
        let line_no = (i as u32) + 1;
        let t = raw.trim();
        if t.is_empty() {
            continue;
        }

        let mut is_decl_line = false;

        // Top-level item declarations that never count as call sites.
        // Note `var x = foo()` IS a call site (we don't filter), but
        // `package p` / `import …` are not.
        if t.starts_with("package ") || t.starts_with("import ") {
            is_decl_line = true;
        }

        // `func` header detection. `parse_go_func_header` returns None
        // for anonymous funcs — we want anonymous funcs to be
        // transparent, so calls inside them are STILL attributed.
        // However, the anonymous func still contributes `{` / `}` to
        // the brace count, which means its body opens push depth but
        // there's no scope to pop. This is fine: only `fn_stack` pops
        // based on `open_depth`, and a transparent anonymous func
        // never pushed, so it never pops.
        if let Some((qualified, opens)) = parse_go_func_header(t) {
            is_decl_line = true;
            if opens {
                fn_stack.push(GoFnScope {
                    qualified,
                    open_depth: depth,
                });
            } else {
                pending_fn = Some(qualified);
            }
        } else if pending_fn.is_some() && line_opens_body(raw) {
            // Header from a previous line + this line carries the `{`.
            let qualified = pending_fn.take().unwrap();
            fn_stack.push(GoFnScope {
                qualified,
                open_depth: depth,
            });
            // Don't mark as a decl line — the body could start with code
            // on the same line, though by convention Go puts `{` at the
            // end of the signature line.
        }

        if !is_decl_line {
            // `defer X()` and `go X()` — the inner call IS a call site.
            // The path walker treats `defer`/`go` as keywords (so they
            // won't be emitted as callees), but to find the inner
            // identifier we need to start scanning AFTER the keyword.
            // The walker already does this naturally: word-boundary
            // detection allows `defer foo()` to walk past `defer`
            // (which is keyword-filtered) and then re-enter at `foo`.
            // No special handling needed beyond the keyword filter.
            let caller = fn_stack
                .last()
                .map(|s| s.qualified.as_str())
                .unwrap_or("");
            extract_go_calls_from_line(raw, line_no, caller, file_path, &mut out);
        }

        // Update brace depth from this line's `{` / `}`.
        let (opens, closes) = count_braces(raw);
        depth += opens - closes;
        // Pop fn scopes whose body has closed.
        while let Some(scope) = fn_stack.last() {
            if depth <= scope.open_depth {
                fn_stack.pop();
            } else {
                break;
            }
        }
    }
    out
}

// ── TS/JS calls (Phase 2 #3 third slice — TS/JS side) ───────────────────────

/// Replace string and comment interiors with spaces. Handles all three
/// TS/JS quote styles (`"…"`, `'…'`, `` `…` ``), `//` line comments,
/// and multi-line `/* … */` block comments. Template literals are
/// masked wholesale — `${…}` interpolation calls are NOT extracted
/// (V1 limit; rare in practice).
fn mask_ts_strings_and_comments(content: &str) -> String {
    enum State {
        Normal,
        Str(u8),
        LineCmt,
        BlockCmt,
    }
    let mut state = State::Normal;
    let mut prev_bs = false;
    let mut out = String::with_capacity(content.len());
    let bytes = content.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        let c = bytes[i];
        match state {
            State::Normal => {
                if c == b'"' || c == b'\'' || c == b'`' {
                    out.push(c as char);
                    state = State::Str(c);
                    i += 1;
                } else if c == b'/' && i + 1 < bytes.len() && bytes[i + 1] == b'/' {
                    out.push(' ');
                    out.push(' ');
                    state = State::LineCmt;
                    i += 2;
                } else if c == b'/' && i + 1 < bytes.len() && bytes[i + 1] == b'*' {
                    out.push(' ');
                    out.push(' ');
                    state = State::BlockCmt;
                    i += 2;
                } else {
                    out.push(c as char);
                    i += 1;
                }
            }
            State::Str(quote) => {
                if c == b'\\' && !prev_bs {
                    prev_bs = true;
                    out.push('\\');
                    i += 1;
                    continue;
                }
                if c == quote && !prev_bs {
                    out.push(c as char);
                    state = State::Normal;
                    prev_bs = false;
                    i += 1;
                    continue;
                }
                prev_bs = false;
                if c == b'\n' {
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
            State::LineCmt => {
                if c == b'\n' {
                    state = State::Normal;
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
            State::BlockCmt => {
                if c == b'*' && i + 1 < bytes.len() && bytes[i + 1] == b'/' {
                    out.push(' ');
                    out.push(' ');
                    state = State::Normal;
                    i += 2;
                    continue;
                }
                if c == b'\n' {
                    out.push('\n');
                } else {
                    out.push(' ');
                }
                i += 1;
            }
        }
    }
    out
}

fn is_ts_call_keyword(s: &str) -> bool {
    matches!(
        s,
        "if" | "else"
            | "for"
            | "while"
            | "do"
            | "switch"
            | "case"
            | "default"
            | "break"
            | "continue"
            | "return"
            | "throw"
            | "try"
            | "catch"
            | "finally"
            | "function"
            | "class"
            | "const"
            | "let"
            | "var"
            | "async"
            | "await"
            | "yield"
            | "typeof"
            | "instanceof"
            | "in"
            | "of"
            | "delete"
            | "void"
            | "true"
            | "false"
            | "null"
            | "undefined"
            | "import"
            | "export"
            | "from"
            | "this"
            | "super"
            | "enum"
            | "interface"
            | "type"
            | "namespace"
            | "module"
            | "public"
            | "private"
            | "protected"
            | "readonly"
            | "static"
            | "abstract"
            | "override"
            | "declare"
            | "as"
            | "is"
            | "new"
    )
}

fn extract_ts_calls_from_line(
    line: &str,
    line_no: u32,
    caller: &str,
    language: &str,
    file_path: &str,
    out: &mut Vec<CodebaseCall>,
) {
    let bytes = line.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() {
        let c = bytes[i];
        // Method call: `.NAME(` (or `?.NAME(` optional chain).
        if c == b'.'
            && i + 1 < bytes.len()
            && (bytes[i + 1].is_ascii_alphabetic()
                || bytes[i + 1] == b'_'
                || bytes[i + 1] == b'$')
        {
            let start = i + 1;
            let mut j = start;
            while j < bytes.len() && is_ts_ident_char(bytes[j]) {
                j += 1;
            }
            let name = &line[start..j];
            let mut k = j;
            while k < bytes.len() && (bytes[k] == b' ' || bytes[k] == b'\t') {
                k += 1;
            }
            if k + 1 < bytes.len() && bytes[k] == b'?' && bytes[k + 1] == b'.' {
                k += 2;
                while k < bytes.len() && (bytes[k] == b' ' || bytes[k] == b'\t') {
                    k += 1;
                }
            }
            if k < bytes.len() && bytes[k] == b'(' && !is_ts_call_keyword(name) {
                out.push(CodebaseCall {
                    file_path: file_path.to_string(),
                    line: line_no,
                    language: language.to_string(),
                    caller: caller.to_string(),
                    callee: format!(".{name}"),
                });
            }
            i = j;
            continue;
        }
        if c.is_ascii_alphabetic() || c == b'_' || c == b'$' {
            if i > 0 && (is_ts_ident_char(bytes[i - 1]) || bytes[i - 1] == b'.') {
                i += 1;
                continue;
            }
            let start = i;
            let mut j = i;
            while j < bytes.len() && is_ts_ident_char(bytes[j]) {
                j += 1;
            }
            loop {
                if j < bytes.len()
                    && bytes[j] == b'.'
                    && j + 1 < bytes.len()
                    && (bytes[j + 1].is_ascii_alphabetic()
                        || bytes[j + 1] == b'_'
                        || bytes[j + 1] == b'$')
                {
                    let s = j + 1;
                    let mut t = s;
                    while t < bytes.len() && is_ts_ident_char(bytes[t]) {
                        t += 1;
                    }
                    j = t;
                } else {
                    break;
                }
            }
            let path = &line[start..j];
            let mut k = j;
            while k < bytes.len() && (bytes[k] == b' ' || bytes[k] == b'\t') {
                k += 1;
            }
            if k < bytes.len() && bytes[k] == b'(' {
                let last_seg = path.rsplit('.').next().unwrap_or(path);
                let first_seg = path.split('.').next().unwrap_or(path);
                if !is_ts_call_keyword(last_seg) && !is_ts_call_keyword(first_seg) {
                    out.push(CodebaseCall {
                        file_path: file_path.to_string(),
                        line: line_no,
                        language: language.to_string(),
                        caller: caller.to_string(),
                        callee: path.to_string(),
                    });
                }
            }
            i = j;
            continue;
        }
        i += 1;
    }
}

/// Extract call sites from a TS/JS file. Tracks brace depth to maintain
/// a stack of enclosing function declarations + class scopes. Class
/// methods qualify as `ClassName.method`. V1 known limits:
///   • Arrow-function assignments (`const f = () => …`) don't push to
///     the fn stack — caller for body lines remains the outer scope.
///   • Object-literal methods (`{ method() {} }`) likewise.
///   • Decorator lines (`@decorator(args)`) emit calls but don't gate
///     the following declaration.
pub fn extract_ts_calls(
    content: &str,
    file_path: &str,
    language: &str,
) -> Vec<CodebaseCall> {
    let masked = mask_ts_strings_and_comments(content);
    let content = masked.as_str();
    let mut out = Vec::new();
    let mut depth: i32 = 0;
    let mut scope_stack: Vec<(String, i32, bool)> = Vec::new();

    for (i, raw) in content.lines().enumerate() {
        let line_no = (i as u32) + 1;
        let t = raw.trim();
        if t.is_empty() {
            continue;
        }

        let mut is_decl_line = false;

        let pre = t
            .strip_prefix("export default ")
            .or_else(|| t.strip_prefix("export "))
            .unwrap_or(t);
        let fn_rest = pre
            .strip_prefix("async function ")
            .or_else(|| pre.strip_prefix("function "));
        if let Some(rest) = fn_rest {
            is_decl_line = true;
            let name: String = rest
                .chars()
                .take_while(|c| c.is_alphanumeric() || *c == '_' || *c == '$')
                .collect();
            if !name.is_empty() && raw.contains('{') {
                let qualified = if let Some((cls, _, true)) = scope_stack.last() {
                    format!("{cls}.{name}")
                } else {
                    name
                };
                scope_stack.push((qualified, depth, false));
            }
        }
        if let Some(rest) = pre.strip_prefix("class ") {
            is_decl_line = true;
            let name: String = rest
                .chars()
                .take_while(|c| c.is_alphanumeric() || *c == '_' || *c == '$')
                .collect();
            if !name.is_empty() && raw.contains('{') {
                scope_stack.push((name, depth, true));
            }
        }
        if !is_decl_line {
            if let Some((cls_name, _, true)) = scope_stack.last().cloned() {
                let stripped = t
                    .trim_start_matches("public ")
                    .trim_start_matches("private ")
                    .trim_start_matches("protected ")
                    .trim_start_matches("static ")
                    .trim_start_matches("readonly ")
                    .trim_start_matches("abstract ")
                    .trim_start_matches("override ")
                    .trim_start_matches("async ")
                    .trim_start_matches("get ")
                    .trim_start_matches("set ");
                let head: String = stripped
                    .chars()
                    .take_while(|c| c.is_alphanumeric() || *c == '_' || *c == '$')
                    .collect();
                if !head.is_empty()
                    && !is_ts_call_keyword(&head)
                    && stripped[head.len()..].trim_start().starts_with('(')
                    && raw.contains('{')
                {
                    is_decl_line = true;
                    let qualified = format!("{cls_name}.{head}");
                    scope_stack.push((qualified, depth, false));
                }
            }
        }

        if !is_decl_line {
            let caller = scope_stack
                .iter()
                .rev()
                .find(|(_, _, is_class)| !*is_class)
                .map(|(n, _, _)| n.as_str())
                .unwrap_or("");
            extract_ts_calls_from_line(raw, line_no, caller, language, file_path, &mut out);
        }

        let (opens, closes) = count_braces(raw);
        depth += opens - closes;
        while let Some((_, open_depth, _)) = scope_stack.last() {
            if depth <= *open_depth {
                scope_stack.pop();
            } else {
                break;
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rust_fn_pub() {
        let src = "pub fn hello_world(x: i32) -> i32 { x }";
        let syms = extract_rust(src, "foo.rs");
        assert_eq!(syms.len(), 1);
        assert_eq!(syms[0].kind, "fn");
        assert_eq!(syms[0].name, "hello_world");
    }

    #[test]
    fn rust_async_fn() {
        let src = "    pub async fn fetch(&self) -> Result<()> {}";
        let syms = extract_rust(src, "f.rs");
        assert_eq!(syms[0].kind, "fn");
        assert_eq!(syms[0].name, "fetch");
    }

    #[test]
    fn rust_struct_enum_trait() {
        let src = "pub struct Foo;\npub enum Bar {}\npub trait Baz {}";
        let syms = extract_rust(src, "f.rs");
        assert_eq!(syms.len(), 3);
        assert_eq!(syms[0].kind, "struct");
        assert_eq!(syms[1].kind, "enum");
        assert_eq!(syms[2].kind, "trait");
    }

    // ── impl scope tracking (Phase 2 #3 deepening) ──

    #[test]
    fn rust_inherent_impl_qualifies_methods() {
        let src = "\
struct Foo;

impl Foo {
    pub fn bar(&self) -> i32 { 42 }
    fn baz() {}
}

fn free_fn() {}
";
        let syms = extract_rust(src, "f.rs");
        // struct + impl + 2 methods + free fn = 5
        assert_eq!(syms.len(), 5, "got {syms:#?}");
        assert_eq!(syms[1].kind, "impl");
        assert_eq!(syms[1].name, "Foo");
        assert_eq!(syms[2].kind, "fn");
        assert_eq!(syms[2].name, "Foo::bar", "inherent impl method gets Type::method");
        assert_eq!(syms[3].name, "Foo::baz");
        // Free fn after the impl block closes must not be qualified.
        assert_eq!(syms[4].name, "free_fn", "free fn after impl must not inherit scope");
    }

    #[test]
    fn rust_trait_impl_qualifies_with_trait() {
        let src = "\
impl Display for Foo {
    fn fmt(&self, f: &mut Formatter) -> Result {}
}
";
        let syms = extract_rust(src, "f.rs");
        assert_eq!(syms.len(), 2, "got {syms:#?}");
        assert_eq!(syms[0].kind, "impl");
        assert_eq!(syms[0].name, "Foo", "type goes in name (not the trait)");
        assert_eq!(syms[1].kind, "fn");
        assert_eq!(syms[1].name, "<Foo as Display>::fmt");
    }

    // P22 — `#[test]` / `#[tokio::test]` attributes flip the next fn to
    // kind="test_fn" so codebase-report orphan audit can mark them as
    // known FPs (macro-generated callers are invisible to the extractor).
    #[test]
    fn rust_test_attr_promotes_fn_to_test_fn() {
        let src = "\
#[test]
fn unit_check() {}

#[tokio::test]
async fn async_check() {}

#[tokio::test(flavor = \"multi_thread\")]
async fn async_check_with_args() {}

#[rstest]
fn fixture_check() {}

fn regular_fn() {}
";
        let syms = extract_rust(src, "t.rs");
        let by_name: std::collections::HashMap<&str, &CodebaseSymbol> =
            syms.iter().map(|s| (s.name.as_str(), s)).collect();
        assert_eq!(by_name["unit_check"].kind, "test_fn");
        assert_eq!(by_name["async_check"].kind, "test_fn");
        assert_eq!(by_name["async_check_with_args"].kind, "test_fn");
        assert_eq!(by_name["fixture_check"].kind, "test_fn");
        assert_eq!(
            by_name["regular_fn"].kind, "fn",
            "no preceding test attr → plain fn"
        );
    }

    // Blank line between attribute and fn is valid Rust formatting
    // (rustfmt sometimes inserts one). The pending-test-attr flag must
    // survive blank lines.
    #[test]
    fn rust_test_attr_survives_blank_line() {
        let src = "\
#[tokio::test]

async fn async_check() {}
";
        let syms = extract_rust(src, "t.rs");
        assert_eq!(syms[0].kind, "test_fn");
    }

    // Doc comments between attribute and fn ARE allowed by the language
    // but the extractor currently skips them — confirm this still tags
    // the following fn as test_fn (comment skip preserves the flag).
    #[test]
    fn rust_test_attr_survives_doc_comment() {
        let src = "\
#[test]
// Verify the foo behavior
fn unit_check() {}
";
        let syms = extract_rust(src, "t.rs");
        assert_eq!(syms[0].kind, "test_fn");
    }

    // Non-test code line between attribute and fn clears the flag.
    #[test]
    fn rust_unrelated_code_clears_test_attr() {
        let src = "\
#[test]
let x = 1;
fn regular_fn() {}
";
        let syms = extract_rust(src, "t.rs");
        assert_eq!(syms[0].kind, "fn", "intervening stmt clears test flag");
    }

    #[test]
    fn rust_generic_impl_strips_brackets() {
        let src = "\
impl<T: Clone> Repository<T> for SqliteStore<T> {
    fn store(&self, item: T) {}
}
";
        let syms = extract_rust(src, "g.rs");
        assert_eq!(syms.len(), 2);
        assert_eq!(syms[0].name, "SqliteStore", "type generics stripped");
        assert_eq!(syms[1].name, "<SqliteStore as Repository>::store");
    }

    #[test]
    fn rust_impl_with_where_clause() {
        let src = "\
impl<T> MyTrait for Foo<T>
where
    T: Send + Sync,
{
    fn method(&self) {}
}
";
        let syms = extract_rust(src, "w.rs");
        // impl emits with type=Foo (where stripped), method qualified.
        assert_eq!(syms.len(), 2, "got {syms:#?}");
        assert_eq!(syms[0].name, "Foo");
        assert_eq!(syms[1].name, "<Foo as MyTrait>::method");
    }

    #[test]
    fn rust_impl_scope_pops_on_closing_brace() {
        // Two consecutive impls — methods of the second must not carry the
        // first's type name. Uses the realistic multi-line layout; single-
        // line `impl A { fn a_method() {} }` is a known limitation of the
        // line-based scanner (try_kw runs once per line; the impl branch
        // wins, so the inline `fn` is missed).
        let src = "\
impl A {
    fn a_method() {}
}

impl B {
    fn b_method() {}
}
";
        let syms = extract_rust(src, "ab.rs");
        assert_eq!(syms.len(), 4, "got {syms:#?}");
        assert_eq!(syms[0].name, "A");
        assert_eq!(syms[1].name, "A::a_method");
        assert_eq!(syms[2].name, "B");
        assert_eq!(syms[3].name, "B::b_method", "second impl methods qualified by B, not A");
    }

    #[test]
    fn rust_method_with_inner_brace_block_keeps_scope() {
        // The method body has its own `{ }`, but we shouldn't pop the impl
        // scope until the impl's own `}` arrives.
        let src = "\
impl Foo {
    fn complicated(&self) {
        let x = { 1 + 2 };
        if x > 0 { println!(\"yes\"); }
    }
    fn simple() {}
}
";
        let syms = extract_rust(src, "c.rs");
        assert_eq!(syms.len(), 3, "got {syms:#?}");
        assert_eq!(syms[1].name, "Foo::complicated");
        assert_eq!(syms[2].name, "Foo::simple", "second method still qualified despite intervening braces");
    }

    #[test]
    fn rust_string_with_brace_doesnt_break_scope() {
        // Brace counter ignores `{` inside string literals.
        let src = "\
impl Foo {
    fn render() { let s = \"{not a brace}\"; }
    fn other() {}
}
";
        let syms = extract_rust(src, "s.rs");
        assert_eq!(syms[1].name, "Foo::render");
        assert_eq!(syms[2].name, "Foo::other");
    }

    #[test]
    fn python_def_class() {
        let src = "def foo(x):\n    pass\nclass Bar:\n    pass";
        let syms = extract_python(src, "f.py");
        assert_eq!(syms[0].kind, "def");
        assert_eq!(syms[0].name, "foo");
        assert_eq!(syms[1].kind, "class");
        assert_eq!(syms[1].name, "Bar");
    }

    #[test]
    fn python_class_methods() {
        let src = "\
class Greeter:
    def __init__(self, name):
        self.name = name

    async def greet(self):
        return f'hi {self.name}'

def top_level():
    pass
";
        let syms = extract_python(src, "g.py");
        // class + 2 methods + top-level def = 4
        assert_eq!(syms.len(), 4, "got {syms:#?}");
        assert_eq!(syms[0].kind, "class");
        assert_eq!(syms[0].name, "Greeter");
        assert_eq!(syms[1].kind, "method");
        assert_eq!(syms[1].name, "Greeter.__init__");
        assert_eq!(syms[2].kind, "method");
        assert_eq!(syms[2].name, "Greeter.greet");
        assert_eq!(syms[3].kind, "def");
        assert_eq!(syms[3].name, "top_level");
    }

    #[test]
    fn python_nested_class_qualifies_methods() {
        let src = "\
class Outer:
    class Inner:
        def deep(self):
            pass

    def outer_method(self):
        pass
";
        let syms = extract_python(src, "n.py");
        assert_eq!(syms.len(), 4, "got {syms:#?}");
        assert_eq!(syms[0].name, "Outer");
        assert_eq!(syms[1].kind, "class");
        assert_eq!(syms[1].name, "Outer.Inner");
        assert_eq!(syms[2].kind, "method");
        assert_eq!(syms[2].name, "Outer.Inner.deep");
        assert_eq!(syms[3].kind, "method");
        assert_eq!(syms[3].name, "Outer.outer_method");
    }

    #[test]
    fn python_dedent_pops_class_scope() {
        // Sibling classes at the same indent — second class's methods must
        // not be qualified by the first class.
        let src = "\
class A:
    def a_m(self):
        pass

class B:
    def b_m(self):
        pass
";
        let syms = extract_python(src, "ab.py");
        assert_eq!(syms.len(), 4, "got {syms:#?}");
        assert_eq!(syms[1].name, "A.a_m");
        assert_eq!(syms[2].name, "B");
        assert_eq!(syms[3].name, "B.b_m");
    }

    // ── Phase 2 #3 second slice — Rust import extractor ─────────────────────

    #[test]
    fn rust_import_single_path() {
        let src = "use crate::store::SqliteStore;";
        let imps = extract_rust_imports(src, "f.rs");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "crate::store::SqliteStore");
        assert!(imps[0].alias.is_none());
        assert_eq!(imps[0].language, "rust");
    }

    #[test]
    fn rust_import_with_alias() {
        let src = "use std::collections::HashMap as Map;";
        let imps = extract_rust_imports(src, "f.rs");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "std::collections::HashMap");
        assert_eq!(imps[0].alias.as_deref(), Some("Map"));
    }

    #[test]
    fn rust_import_group_expands_to_one_per_item() {
        let src = "use crate::{CodebaseImport, CodebaseSymbol};";
        let imps = extract_rust_imports(src, "f.rs");
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, "crate::CodebaseImport");
        assert_eq!(imps[1].target, "crate::CodebaseSymbol");
    }

    #[test]
    fn rust_import_group_with_per_item_alias() {
        let src = "use foo::{Bar, Baz as Z};";
        let imps = extract_rust_imports(src, "f.rs");
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, "foo::Bar");
        assert!(imps[0].alias.is_none());
        assert_eq!(imps[1].target, "foo::Baz");
        assert_eq!(imps[1].alias.as_deref(), Some("Z"));
    }

    #[test]
    fn rust_import_wildcard() {
        let src = "use foo::bar::*;";
        let imps = extract_rust_imports(src, "f.rs");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "foo::bar::*");
    }

    #[test]
    fn rust_import_pub_use_stripped() {
        let src = "pub use crate::api::Endpoint;";
        let imps = extract_rust_imports(src, "f.rs");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "crate::api::Endpoint");
        // pub(crate) form
        let src2 = "pub(crate) use crate::api::Internal;";
        let imps2 = extract_rust_imports(src2, "f.rs");
        assert_eq!(imps2.len(), 1);
        assert_eq!(imps2[0].target, "crate::api::Internal");
    }

    #[test]
    fn rust_import_multi_line_group() {
        // Real codebase pattern: long import lists wrapped across lines.
        let src = "\
use crate::{
    CoactivationStats, CodebaseIndexStats, CodebaseSymbol,
    ForumExportResult,
};
";
        let imps = extract_rust_imports(src, "f.rs");
        assert_eq!(imps.len(), 4, "got {imps:#?}");
        assert_eq!(imps[0].target, "crate::CoactivationStats");
        assert_eq!(imps[1].target, "crate::CodebaseIndexStats");
        assert_eq!(imps[2].target, "crate::CodebaseSymbol");
        assert_eq!(imps[3].target, "crate::ForumExportResult");
        // All four should report the line where `use` started.
        assert!(imps.iter().all(|i| i.line == 1));
    }

    #[test]
    fn rust_import_nested_group_recurses() {
        let src = "use foo::{bar::{Baz, Qux}, Other};";
        let imps = extract_rust_imports(src, "f.rs");
        assert_eq!(imps.len(), 3, "got {imps:#?}");
        let targets: Vec<&str> = imps.iter().map(|i| i.target.as_str()).collect();
        assert!(targets.contains(&"foo::bar::Baz"));
        assert!(targets.contains(&"foo::bar::Qux"));
        assert!(targets.contains(&"foo::Other"));
    }

    #[test]
    fn rust_import_self_inside_group_means_prefix() {
        // `use foo::bar::{self, Baz};` imports both `foo::bar` and `foo::bar::Baz`.
        let src = "use foo::bar::{self, Baz};";
        let imps = extract_rust_imports(src, "f.rs");
        assert_eq!(imps.len(), 2);
        let targets: Vec<&str> = imps.iter().map(|i| i.target.as_str()).collect();
        assert!(targets.contains(&"foo::bar"));
        assert!(targets.contains(&"foo::bar::Baz"));
    }

    #[test]
    fn rust_extern_crate_recorded_as_import() {
        let src = "extern crate serde;\nextern crate serde_json as sj;";
        let imps = extract_rust_imports(src, "f.rs");
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, "serde");
        assert!(imps[0].alias.is_none());
        assert_eq!(imps[1].target, "serde_json");
        assert_eq!(imps[1].alias.as_deref(), Some("sj"));
    }

    #[test]
    fn rust_import_skips_lines_not_starting_with_use() {
        // The word "use" appears inside an identifier; must not match.
        let src = "fn use_this() {}\nstruct UseFoo;\n// use foo;\n";
        let imps = extract_rust_imports(src, "f.rs");
        assert!(imps.is_empty(), "spurious matches: {imps:#?}");
    }

    // ── Phase 2 #3 second slice — Python import extractor ──────────────────

    #[test]
    fn py_import_simple_module() {
        let imps = extract_python_imports("import os\n", "f.py");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "os");
        assert!(imps[0].alias.is_none());
        assert_eq!(imps[0].language, "python");
    }

    #[test]
    fn py_import_dotted_path() {
        let imps = extract_python_imports("import os.path\n", "f.py");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "os.path");
    }

    #[test]
    fn py_import_with_alias() {
        let imps = extract_python_imports("import numpy as np\n", "f.py");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "numpy");
        assert_eq!(imps[0].alias.as_deref(), Some("np"));
    }

    #[test]
    fn py_import_multiple_with_per_item_alias() {
        let imps =
            extract_python_imports("import a, b as x, c.d\n", "f.py");
        assert_eq!(imps.len(), 3);
        assert_eq!(imps[0].target, "a");
        assert_eq!(imps[1].target, "b");
        assert_eq!(imps[1].alias.as_deref(), Some("x"));
        assert_eq!(imps[2].target, "c.d");
    }

    #[test]
    fn py_from_module_import_name() {
        let imps = extract_python_imports("from os import path\n", "f.py");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "os.path");
    }

    #[test]
    fn py_from_module_import_multiple() {
        let imps = extract_python_imports(
            "from os import path, getcwd, mkdir\n",
            "f.py",
        );
        assert_eq!(imps.len(), 3);
        let targets: Vec<&str> = imps.iter().map(|i| i.target.as_str()).collect();
        assert_eq!(targets, ["os.path", "os.getcwd", "os.mkdir"]);
    }

    #[test]
    fn py_from_with_per_name_alias() {
        let imps = extract_python_imports("from os import path as p\n", "f.py");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "os.path");
        assert_eq!(imps[0].alias.as_deref(), Some("p"));
    }

    #[test]
    fn py_from_relative_single_dot() {
        let imps = extract_python_imports("from . import foo\n", "f.py");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, ".foo");
    }

    #[test]
    fn py_from_relative_dotted_package() {
        let imps =
            extract_python_imports("from .pkg.sub import bar, baz\n", "f.py");
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, ".pkg.sub.bar");
        assert_eq!(imps[1].target, ".pkg.sub.baz");
    }

    #[test]
    fn py_from_wildcard() {
        let imps = extract_python_imports("from os import *\n", "f.py");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "os.*");
    }

    #[test]
    fn py_from_paren_multiline() {
        let src = "\
from typing import (
    Any,
    Dict,
    List,
    Optional as Opt,
)
";
        let imps = extract_python_imports(src, "f.py");
        assert_eq!(imps.len(), 4, "got {imps:#?}");
        let targets: Vec<&str> = imps.iter().map(|i| i.target.as_str()).collect();
        assert_eq!(
            targets,
            ["typing.Any", "typing.Dict", "typing.List", "typing.Optional"]
        );
        assert_eq!(imps[3].alias.as_deref(), Some("Opt"));
        // All four should report the line where `from` started.
        assert!(imps.iter().all(|i| i.line == 1));
    }

    #[test]
    fn py_import_skips_comments_and_lookalikes() {
        // The word "import" appears inside identifiers / comments / strings.
        let src = "\
# import os
def import_helper():
    return import_lib  # not a real import
x = 'from os import path'
";
        let imps = extract_python_imports(src, "f.py");
        assert!(imps.is_empty(), "spurious matches: {imps:#?}");
    }

    // ── Phase 2 #3 second slice — TS/JS import extractor ───────────────────

    #[test]
    fn ts_import_side_effect_only() {
        let imps = extract_ts_imports("import 'reflect-metadata';\n", "f.ts", "typescript");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "reflect-metadata");
        assert!(imps[0].alias.is_none());
        assert_eq!(imps[0].language, "typescript");
    }

    #[test]
    fn ts_import_default() {
        let imps = extract_ts_imports("import React from 'react';\n", "f.ts", "typescript");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "react");
        assert_eq!(imps[0].alias.as_deref(), Some("React"));
    }

    #[test]
    fn ts_import_namespace() {
        let imps = extract_ts_imports(
            "import * as path from 'node:path';\n",
            "f.ts",
            "typescript",
        );
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "node:path.*");
        assert_eq!(imps[0].alias.as_deref(), Some("path"));
    }

    #[test]
    fn ts_import_named() {
        let imps = extract_ts_imports(
            "import { useState, useEffect } from 'react';\n",
            "f.tsx",
            "typescript",
        );
        assert_eq!(imps.len(), 2);
        let targets: Vec<&str> = imps.iter().map(|i| i.target.as_str()).collect();
        assert_eq!(targets, ["react.useState", "react.useEffect"]);
    }

    #[test]
    fn ts_import_named_with_alias() {
        let imps = extract_ts_imports(
            "import { Component as C, Fragment } from 'react';\n",
            "f.ts",
            "typescript",
        );
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, "react.Component");
        assert_eq!(imps[0].alias.as_deref(), Some("C"));
        assert_eq!(imps[1].target, "react.Fragment");
        assert!(imps[1].alias.is_none());
    }

    #[test]
    fn ts_import_default_plus_named() {
        let imps = extract_ts_imports(
            "import React, { useState } from 'react';\n",
            "f.tsx",
            "typescript",
        );
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, "react");
        assert_eq!(imps[0].alias.as_deref(), Some("React"));
        assert_eq!(imps[1].target, "react.useState");
    }

    #[test]
    fn ts_import_default_plus_namespace() {
        let imps = extract_ts_imports(
            "import fs, * as fsAll from 'fs';\n",
            "f.ts",
            "typescript",
        );
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, "fs");
        assert_eq!(imps[0].alias.as_deref(), Some("fs"));
        assert_eq!(imps[1].target, "fs.*");
        assert_eq!(imps[1].alias.as_deref(), Some("fsAll"));
    }

    #[test]
    fn ts_import_type_prefix_stripped() {
        let imps = extract_ts_imports(
            "import type { Foo, Bar } from './types';\n",
            "f.ts",
            "typescript",
        );
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, "./types.Foo");
        assert_eq!(imps[1].target, "./types.Bar");
    }

    #[test]
    fn ts_import_inline_type_stripped() {
        let imps = extract_ts_imports(
            "import { type Foo, Bar } from './types';\n",
            "f.ts",
            "typescript",
        );
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, "./types.Foo");
        assert_eq!(imps[1].target, "./types.Bar");
    }

    #[test]
    fn ts_import_multi_line_braces() {
        let src = "\
import {
  useState,
  useEffect as useFx,
  Fragment,
} from 'react';
";
        let imps = extract_ts_imports(src, "f.tsx", "typescript");
        assert_eq!(imps.len(), 3, "got {imps:#?}");
        let targets: Vec<&str> = imps.iter().map(|i| i.target.as_str()).collect();
        assert_eq!(targets, ["react.useState", "react.useEffect", "react.Fragment"]);
        assert_eq!(imps[1].alias.as_deref(), Some("useFx"));
        // All three should report the line where `import` started.
        assert!(imps.iter().all(|i| i.line == 1));
    }

    #[test]
    fn ts_export_named_from() {
        let imps = extract_ts_imports(
            "export { Foo, Bar as B } from './mod';\n",
            "f.ts",
            "typescript",
        );
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, "./mod.Foo");
        assert_eq!(imps[1].target, "./mod.Bar");
        assert_eq!(imps[1].alias.as_deref(), Some("B"));
    }

    #[test]
    fn ts_export_star_from() {
        let imps = extract_ts_imports("export * from './mod';\n", "f.ts", "typescript");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "./mod.*");
        assert!(imps[0].alias.is_none());
    }

    #[test]
    fn ts_export_star_as_from() {
        let imps = extract_ts_imports(
            "export * as utils from './utils';\n",
            "f.ts",
            "typescript",
        );
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "./utils.*");
        assert_eq!(imps[0].alias.as_deref(), Some("utils"));
    }

    #[test]
    fn ts_require_cjs() {
        let imps = extract_ts_imports(
            "const lodash = require('lodash');\n",
            "f.js",
            "javascript",
        );
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "lodash");
        assert_eq!(imps[0].language, "javascript");
    }

    #[test]
    fn ts_dynamic_import() {
        let imps = extract_ts_imports(
            "const m = await import('./lazy');\n",
            "f.ts",
            "typescript",
        );
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "./lazy");
    }

    #[test]
    fn ts_skips_lookalikes_and_method_calls() {
        // `.require(` / `xrequire(` / strings / comments must not match.
        let src = "\
// import { ignored } from 'no'
/* import { also } from 'nope' */
const x = self.require('not-cjs');
const s = 'import foo from \"bar\"';
function require_helper() {}
const y = xrequire('mod');
";
        let imps = extract_ts_imports(src, "f.js", "javascript");
        assert!(imps.is_empty(), "spurious matches: {imps:#?}");
    }

    #[test]
    fn ts_require_inside_function_keeps_correct_line() {
        // Regression: brace aggregation must not sweep function bodies
        // and mis-attribute require() lines to the function header.
        let src = "\
function isWSL(): boolean {
    if (process.platform !== \"linux\") return false;
    try {
        const { readFileSync } = require(\"node:fs\");
        return true;
    } catch { return false; }
}
";
        let imps = extract_ts_imports(src, "f.ts", "typescript");
        assert_eq!(imps.len(), 1, "got {imps:#?}");
        assert_eq!(imps[0].target, "node:fs");
        assert_eq!(imps[0].line, 4, "require should be on its own line");
    }

    #[test]
    fn ts_static_and_call_in_same_buffer() {
        // Two statements on one line: static + dynamic should both be seen.
        let imps = extract_ts_imports(
            "import foo from 'a'; const b = require('b');\n",
            "f.js",
            "javascript",
        );
        assert_eq!(imps.len(), 2, "got {imps:#?}");
        assert_eq!(imps[0].target, "a");
        assert_eq!(imps[0].alias.as_deref(), Some("foo"));
        assert_eq!(imps[1].target, "b");
        assert!(imps[1].alias.is_none());
    }

    // ── Phase 2 #3 second slice — Go import extractor ──────────────────────

    #[test]
    fn go_import_single() {
        let imps = extract_go_imports("import \"fmt\"\n", "f.go");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "fmt");
        assert!(imps[0].alias.is_none());
        assert_eq!(imps[0].language, "go");
    }

    #[test]
    fn go_import_with_alias() {
        let imps = extract_go_imports("import logger \"log\"\n", "f.go");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "log");
        assert_eq!(imps[0].alias.as_deref(), Some("logger"));
    }

    #[test]
    fn go_import_blank_side_effect() {
        let imps =
            extract_go_imports("import _ \"github.com/lib/pq\"\n", "f.go");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "github.com/lib/pq");
        assert_eq!(imps[0].alias.as_deref(), Some("_"));
    }

    #[test]
    fn go_import_dot() {
        let imps = extract_go_imports("import . \"math\"\n", "f.go");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "math");
        assert_eq!(imps[0].alias.as_deref(), Some("."));
    }

    #[test]
    fn go_import_raw_string() {
        let imps = extract_go_imports("import `fmt`\n", "f.go");
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "fmt");
    }

    #[test]
    fn go_import_block_basic() {
        let src = "\
import (
    \"fmt\"
    \"os\"
    \"path/filepath\"
)
";
        let imps = extract_go_imports(src, "f.go");
        assert_eq!(imps.len(), 3, "got {imps:#?}");
        assert_eq!(imps[0].target, "fmt");
        assert_eq!(imps[0].line, 2);
        assert_eq!(imps[1].target, "os");
        assert_eq!(imps[1].line, 3);
        assert_eq!(imps[2].target, "path/filepath");
        assert_eq!(imps[2].line, 4);
    }

    #[test]
    fn go_import_block_mixed_forms() {
        let src = "\
import (
    \"fmt\"
    logger \"log\"
    _ \"github.com/lib/pq\"
    . \"math\"
)
";
        let imps = extract_go_imports(src, "f.go");
        assert_eq!(imps.len(), 4, "got {imps:#?}");
        assert_eq!(imps[0].target, "fmt");
        assert!(imps[0].alias.is_none());
        assert_eq!(imps[1].target, "log");
        assert_eq!(imps[1].alias.as_deref(), Some("logger"));
        assert_eq!(imps[2].target, "github.com/lib/pq");
        assert_eq!(imps[2].alias.as_deref(), Some("_"));
        assert_eq!(imps[3].target, "math");
        assert_eq!(imps[3].alias.as_deref(), Some("."));
    }

    #[test]
    fn go_import_block_with_comments_and_blank_lines() {
        let src = "\
import (
    // standard library
    \"fmt\"

    // external
    \"github.com/spf13/cobra\"
)
";
        let imps = extract_go_imports(src, "f.go");
        assert_eq!(imps.len(), 2, "got {imps:#?}");
        assert_eq!(imps[0].target, "fmt");
        assert_eq!(imps[0].line, 3);
        assert_eq!(imps[1].target, "github.com/spf13/cobra");
        assert_eq!(imps[1].line, 6);
    }

    #[test]
    fn go_import_block_trailing_comment_on_spec_line() {
        // `// comment` after the spec should be stripped before parsing.
        let src = "\
import (
    \"fmt\"        // formatter
    \"os\"
)
";
        let imps = extract_go_imports(src, "f.go");
        assert_eq!(imps.len(), 2);
        assert_eq!(imps[0].target, "fmt");
        assert_eq!(imps[1].target, "os");
    }

    #[test]
    fn go_import_skips_lookalikes() {
        // The keyword `import` must stand alone; `important` etc. don't match.
        let src = "\
// import \"fake\"
package main

var important = 1
func importHandler() {}
";
        let imps = extract_go_imports(src, "f.go");
        assert!(imps.is_empty(), "spurious matches: {imps:#?}");
    }

    #[test]
    fn go_import_url_with_path_segments() {
        let imps = extract_go_imports(
            "import \"github.com/user/repo/sub/pkg\"\n",
            "f.go",
        );
        assert_eq!(imps.len(), 1);
        assert_eq!(imps[0].target, "github.com/user/repo/sub/pkg");
    }

    // ── Phase 2 #3 third slice — Rust call extractor ───────────────────────

    #[test]
    fn rust_call_bare_function() {
        let src = "\
fn outer() {
    foo();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "foo");
        assert_eq!(calls[0].caller, "outer");
        assert_eq!(calls[0].line, 2);
        assert_eq!(calls[0].language, "rust");
    }

    #[test]
    fn rust_call_qualified_path() {
        let src = "\
fn outer() {
    crate::store::SqliteStore::new();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "crate::store::SqliteStore::new");
        assert_eq!(calls[0].caller, "outer");
    }

    #[test]
    fn rust_call_method_dot() {
        let src = "\
fn outer() {
    obj.method();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, ".method");
        assert_eq!(calls[0].caller, "outer");
    }

    #[test]
    fn rust_call_skips_macros_and_keywords() {
        let src = "\
fn outer() {
    println!(\"hi\");
    if cond() { return; }
    while true { break; }
    match val { _ => () }
}
";
        let calls = extract_rust_calls(src, "f.rs");
        // Only `cond()` should be a real call.
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "cond");
    }

    #[test]
    fn rust_call_skips_strings_and_comments() {
        let src = "\
fn outer() {
    let s = \"foo()\";        // not a call
    // bar();
    real_call();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "real_call");
    }

    #[test]
    fn rust_call_skips_declaration_lines() {
        // The `fn outer()` header should NOT emit a self-call.
        let src = "\
fn outer() {
    inner();
}

struct Foo;
const N: usize = 10;
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "inner");
        assert_eq!(calls[0].caller, "outer");
    }

    #[test]
    fn rust_call_caller_qualified_in_impl() {
        let src = "\
impl Foo {
    fn bar(&self) {
        helper();
    }
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "helper");
        assert_eq!(calls[0].caller, "Foo::bar");
    }

    #[test]
    fn rust_call_caller_qualified_in_trait_impl() {
        let src = "\
impl Bar for Foo {
    fn baz(&self) {
        helper();
    }
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "helper");
        assert_eq!(calls[0].caller, "<Foo as Bar>::baz");
    }

    #[test]
    fn rust_call_with_turbofish() {
        let src = "\
fn outer() {
    Vec::<u8>::new();
    parse::<u32>(s);
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        assert_eq!(calls[0].callee, "Vec::new");
        assert_eq!(calls[1].callee, "parse");
    }

    #[test]
    fn rust_call_method_with_turbofish() {
        let src = "\
fn outer() {
    iter.collect::<Vec<_>>();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, ".collect");
    }

    #[test]
    fn rust_call_multiple_per_line() {
        let src = "\
fn outer() {
    foo(bar(baz()));
}
";
        let calls = extract_rust_calls(src, "f.rs");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["foo", "bar", "baz"]);
        assert!(calls.iter().all(|c| c.caller == "outer"));
    }

    #[test]
    fn rust_call_nested_fns_track_caller() {
        let src = "\
fn outer() {
    fn inner() {
        helper();
    }
    inner();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        // `helper()` inside `inner`, `inner()` inside `outer`.
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        let helper = calls.iter().find(|c| c.callee == "helper").unwrap();
        assert_eq!(helper.caller, "inner");
        let inner = calls.iter().find(|c| c.callee == "inner").unwrap();
        assert_eq!(inner.caller, "outer");
    }

    #[test]
    fn rust_call_file_scope_caller_is_empty() {
        // `lazy_static!` etc. live at file scope. A bare call there
        // shouldn't crash — caller is empty.
        let src = "\
const X: u32 = compute(42);
";
        let calls = extract_rust_calls(src, "f.rs");
        // `const X` is a decl line so call extraction is skipped — no rows.
        // Move the call to a non-decl context (let at fn scope):
        let src2 = "\
fn x() {
    let y = compute(42);
}
";
        let calls2 = extract_rust_calls(src2, "f.rs");
        assert_eq!(calls2.len(), 1);
        assert_eq!(calls2[0].callee, "compute");
        assert_eq!(calls2[0].caller, "x");
        // And the const case: should produce no rows (skipped).
        assert!(calls.is_empty(), "got {calls:#?}");
    }

    #[test]
    fn rust_call_chained_method() {
        let src = "\
fn outer() {
    x.foo().bar().baz();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, [".foo", ".bar", ".baz"]);
    }

    #[test]
    fn rust_call_lifetime_not_misread_as_char() {
        // `'a` in lifetime context shouldn't make us read past the
        // following call.
        let src = "\
fn outer<'a>() {
    do_thing();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "do_thing");
    }

    #[test]
    fn rust_call_multiline_string_does_not_leak() {
        // Wet-run finding: multi-line string literals that contain
        // Rust-looking code were being parsed as real calls because
        // string state didn't persist across lines. The
        // mask_strings_and_comments preprocess pass should neutralise
        // the interior so only the OUTER real call is detected.
        let src = r###"
fn test_helper() {
    let src = "\
fn outer() {
    crate::store::SqliteStore::new();
}
";
    let _ = src;
    real_call();
}
"###;
        let calls = extract_rust_calls(src, "f.rs");
        // Only `real_call()` should be detected; SqliteStore::new is
        // inside the multi-line string literal and must not leak.
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
        assert_eq!(calls[0].caller, "test_helper");
    }

    #[test]
    fn rust_call_block_comment_does_not_leak() {
        let src = "\
fn outer() {
    /* fake_call(); also_fake(); */
    real_call();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "real_call");
    }

    #[test]
    fn rust_call_multiline_block_comment_does_not_leak() {
        let src = "\
fn outer() {
    /* multi
       line
       fake_call();
       another_fake();
    */
    real_call();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "real_call");
    }

    #[test]
    fn rust_call_raw_string_does_not_leak() {
        // Wet-run finding 2: `r###"..."###` raw strings were not masked,
        // so any `"..."` inside leaked through and the masker's plain-
        // string state machine fell out of sync, mistreating subsequent
        // code as real Rust.
        let src = r####"
fn test_fn() {
    let frag = r###"
        let nested = "\
fn fake() {
    SqliteStore::new();
}
";
    "###;
    let _ = frag;
    real_call();
}
"####;
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
    }

    #[test]
    fn rust_call_char_literal_with_quote_does_not_open_string() {
        // `'"'` (apostrophe + quote + apostrophe) is a char literal —
        // not the start of a string. The masker must skip past it.
        let src = "\
fn outer() {
    let _ = '\"';
    let _ = ' ';
    real_call();
}
";
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "real_call");
    }

    #[test]
    fn rust_call_byte_string_and_byte_raw_string_handled() {
        // `b"…"` is a plain byte string; `br"…"` and `br#"…"#` are raw.
        // For the masker, `b` before `"` is just an ident-ish char —
        // the `"` still enters Str state. For `br"…"`, we need raw
        // detection to fire on the `b…r…"` pair.
        let src = r#"
fn outer() {
    let a = b"foo";
    let b = br"bar/baz";
    real_call();
}
"#;
        let calls = extract_rust_calls(src, "f.rs");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
    }

    // ── Phase 2 #3 third slice (cont.) — Python call extractor ─────────────

    #[test]
    fn python_call_bare_function() {
        let src = "\
def outer():
    foo()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "foo");
        assert_eq!(calls[0].caller, "outer");
        assert_eq!(calls[0].line, 2);
        assert_eq!(calls[0].language, "python");
    }

    #[test]
    fn python_call_qualified_path() {
        let src = "\
def outer():
    os.path.join(a, b)
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "os.path.join");
        assert_eq!(calls[0].caller, "outer");
    }

    #[test]
    fn python_call_method_in_class_self() {
        // `self.foo()` collapses to `.foo` (mirrors Rust method-call
        // policy: receiver unknown, callee normalised to `.NAME`).
        let src = "\
class Foo:
    def bar(self):
        self.helper()
    def helper(self):
        pass
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, ".helper");
        assert_eq!(calls[0].caller, "Foo.bar", "method caller is qualified");
    }

    #[test]
    fn python_call_class_static_qualified() {
        // `Foo.bar()` at call site keeps the class prefix because it's
        // a path call, not a receiver-method call.
        let src = "\
class Foo:
    @staticmethod
    def bar():
        pass

def caller():
    Foo.bar()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "Foo.bar");
        assert_eq!(calls[0].caller, "caller");
    }

    #[test]
    fn python_call_factory_method_chain() {
        // `Foo().bar()` — `Foo` is a constructor call AND `.bar` is a
        // method call. Both should be detected.
        let src = "\
def caller():
    Foo().bar()
";
        let calls = extract_python_calls(src, "f.py");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["Foo", ".bar"], "got {calls:#?}");
        assert!(calls.iter().all(|c| c.caller == "caller"));
    }

    #[test]
    fn python_call_nested_fn_caller_qualified() {
        // `outer.inner` mirrors Rust nested-fn convention but with `.`
        // separator (Python doesn't have `::`).
        let src = "\
def outer():
    def inner():
        helper()
    inner()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        let helper = calls.iter().find(|c| c.callee == "helper").unwrap();
        assert_eq!(helper.caller, "outer.inner");
        let inner = calls.iter().find(|c| c.callee == "inner").unwrap();
        assert_eq!(inner.caller, "outer");
    }

    #[test]
    fn python_call_keyword_filter() {
        // Python control-flow keywords with paren shapes don't emit calls.
        // Built-ins (`print`, `len`) DO emit — same policy as Rust.
        let src = "\
def outer():
    if (cond):
        return (x)
    while (running):
        pass
    print(\"hello\")
    n = len(items)
";
        let calls = extract_python_calls(src, "f.py");
        // Only `cond`, `running`, `print`, `len` are real calls in syntactic
        // shape. But `if (cond):` etc. — `cond` here IS a bare identifier
        // call shape because `if (` puts a `(` right after `if`. Our
        // keyword filter rejects `if`, but `cond` itself is bare ident
        // followed by no `(` (it's followed by `)` and `:`). So `cond`
        // is NOT a call. Same for `running`. So we expect exactly
        // `print`, `len`.
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["print", "len"], "got {calls:#?}");
    }

    #[test]
    fn python_call_skips_strings_and_comments() {
        let src = "\
def outer():
    s = \"foo()\"          # not a call
    # bar()
    t = 'baz()'
    real_call()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
    }

    #[test]
    fn python_call_triple_quoted_string_masked() {
        // Triple-quoted docstring with call-looking content shouldn't leak.
        let src = "\
def outer():
    \"\"\"This is a docstring with fake_call() inside.\"\"\"
    real_call()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
    }

    #[test]
    fn python_call_multiline_triple_string_does_not_leak() {
        // Same as the Rust multi-line string regression test: triple-
        // quoted strings span lines and per-line scanning would
        // otherwise treat their interior as real code.
        let src = "\
def outer():
    doc = \"\"\"
    fake_call()
    another_fake()
    \"\"\"
    real_call()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
    }

    #[test]
    fn python_call_decorator_line_not_a_call() {
        // `@app.route(...)` is a decorator — the wrapped function is
        // not a call here; but the decorator argument IS a call.
        // Conservative policy: skip the entire decorator line, mirroring
        // Rust's `is_decl_line` skip for `use`/`const`/etc.
        let src = "\
@app.route(\"/foo\")
def handler():
    real_call()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
        assert_eq!(calls[0].caller, "handler");
    }

    #[test]
    fn python_call_async_def_is_caller() {
        let src = "\
async def outer():
    await something()
";
        let calls = extract_python_calls(src, "f.py");
        // `await` is a keyword → filtered. `something()` is a real call.
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "something");
        assert_eq!(calls[0].caller, "outer");
    }

    #[test]
    fn python_call_multiple_per_line() {
        let src = "\
def outer():
    foo(bar(baz()))
";
        let calls = extract_python_calls(src, "f.py");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["foo", "bar", "baz"], "got {calls:#?}");
        assert!(calls.iter().all(|c| c.caller == "outer"));
    }

    #[test]
    fn python_call_module_scope_caller_is_empty() {
        // Free-floating call at module top level: caller is empty,
        // mirroring Rust's file-scope policy.
        let src = "\
configure_logging()

def real_def():
    inside_def()
";
        let calls = extract_python_calls(src, "f.py");
        // `configure_logging()` at module scope → caller="".
        // `inside_def()` at function scope → caller="real_def".
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        let cfg = calls.iter().find(|c| c.callee == "configure_logging").unwrap();
        assert_eq!(cfg.caller, "");
        let inside = calls.iter().find(|c| c.callee == "inside_def").unwrap();
        assert_eq!(inside.caller, "real_def");
    }

    #[test]
    fn python_call_outside_class_after_dedent() {
        // After a class block closes, a subsequent def must not inherit
        // the class qualifier. Mirrors Rust's `rust_impl_scope_pops_on_closing_brace`.
        let src = "\
class Foo:
    def bar(self):
        helper()

def free():
    other_helper()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        let helper = calls.iter().find(|c| c.callee == "helper").unwrap();
        assert_eq!(helper.caller, "Foo.bar");
        let other = calls.iter().find(|c| c.callee == "other_helper").unwrap();
        assert_eq!(other.caller, "free", "free() must not inherit Foo.");
    }

    #[test]
    fn python_call_subscript_normalises_to_path() {
        // `func[int](…)` → callee="func". Python equivalent of Rust
        // turbofish normalisation (`Vec::<u8>::new` → `Vec::new`).
        let src = "\
def outer():
    typing_thing[int](x)
    obj.method[str]()
";
        let calls = extract_python_calls(src, "f.py");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["typing_thing", "obj.method"], "got {calls:#?}");
    }

    #[test]
    fn python_call_chained_method() {
        let src = "\
def outer():
    x.foo().bar().baz()
";
        let calls = extract_python_calls(src, "f.py");
        // `x.foo` is dotted path → callee="x.foo".
        // `.bar` and `.baz` are unresolved method calls → ".bar", ".baz".
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["x.foo", ".bar", ".baz"], "got {calls:#?}");
    }

    #[test]
    fn python_call_skips_def_header_self_call() {
        // The `def outer(arg):` header should NOT emit a `outer(` call
        // self-attribution. Same as Rust's decl-line skip.
        let src = "\
def outer(arg):
    inner_call()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "inner_call");
    }

    #[test]
    fn python_call_class_method_calls_module_func() {
        // `Foo().bar()` from outside the class → caller="user" (top-level
        // def), callee includes both the constructor `Foo` and method
        // `.bar`. The factory-method-chain test covers this; here we add
        // the asymmetric variant: inside another class, calling a module
        // function.
        let src = "\
def util():
    pass

class Foo:
    def bar(self):
        util()
        other_mod.helper()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        let u = calls.iter().find(|c| c.callee == "util").unwrap();
        assert_eq!(u.caller, "Foo.bar");
        let h = calls.iter().find(|c| c.callee == "other_mod.helper").unwrap();
        assert_eq!(h.caller, "Foo.bar");
    }

    #[test]
    fn python_call_nested_class_method() {
        // `class Outer: class Inner: def m(self):` → caller="Outer.Inner.m".
        let src = "\
class Outer:
    class Inner:
        def m(self):
            helper()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "helper");
        assert_eq!(calls[0].caller, "Outer.Inner.m");
    }

    #[test]
    fn python_call_decorator_argument_not_emitted_as_call() {
        // The decorator line `@app.route("/x")` is skipped entirely:
        // - `app.route` is NOT recorded as a call (decorator, not invocation).
        // - The decorated `def handler` becomes the caller scope.
        let src = "\
@app.route(\"/x\")
@cached(ttl=60)
def handler():
    real_call()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
        assert_eq!(calls[0].caller, "handler");
    }

    #[test]
    fn python_call_f_string_interior_does_not_leak() {
        // f-string interpolation `f"{fake_call()}"` is masked.
        let src = "\
def outer():
    msg = f\"hello {fake_call()} world\"
    real_call()
";
        let calls = extract_python_calls(src, "f.py");
        // `msg`, `fake_call` inside f-string masked → only real_call.
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
    }

    #[test]
    fn python_call_dotted_attr_access_without_paren_not_a_call() {
        // `x.attr` without `(` is not a call — only emits when followed by `(`.
        let src = "\
def outer():
    val = obj.attr
    real_call()
";
        let calls = extract_python_calls(src, "f.py");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
    }

    // ── Go call-graph extraction (Phase 2 #3 third slice — Go side) ──

    #[test]
    fn go_call_bare_function() {
        let src = "\
package main

func main() {
    greet()
}

func greet() {}
";
        let calls = extract_go_calls(src, "main.go");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "greet");
        assert_eq!(calls[0].caller, "main");
        assert_eq!(calls[0].language, "go");
        assert_eq!(calls[0].line, 4);
    }

    #[test]
    fn go_call_value_receiver_method() {
        // `func (r T) M(...)` — caller of inner calls is `T.M`.
        let src = "\
package p

type Greeter struct{}

func (g Greeter) Hello() {
    fmt.Println(\"hi\")
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "fmt.Println");
        assert_eq!(calls[0].caller, "Greeter.Hello");
    }

    #[test]
    fn go_call_pointer_receiver_collapses_star() {
        // Pointer-receiver methods qualify identically to value-receiver
        // methods — extraction doesn't care about pointer vs value.
        let src = "\
package p

func (g *Greeter) Hello() {
    log.Print(\"hi\")
}

func (g Greeter) Other() {
    helper()
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        let hello = calls.iter().find(|c| c.callee == "log.Print").unwrap();
        assert_eq!(hello.caller, "Greeter.Hello");
        let other = calls.iter().find(|c| c.callee == "helper").unwrap();
        assert_eq!(other.caller, "Greeter.Other");
    }

    #[test]
    fn go_call_generic_function_declaration() {
        // `func F[T any](...)` — caller is `F`, type-param list stripped.
        let src = "\
package p

func Map[T, U any](xs []T, f func(T) U) []U {
    inner()
    return nil
}
";
        let calls = extract_go_calls(src, "g.go");
        // Note `func(T) U` is an anonymous function *type* (not a literal).
        // The walker should not record it as a call site — `func` is a
        // keyword. Only `inner()` should be emitted.
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "inner");
        assert_eq!(calls[0].caller, "Map");
    }

    #[test]
    fn go_call_generic_call_site_strips_brackets() {
        // `F[int]()` and `M.Method[T, U](...)` — type-param brackets
        // between path and `(` are stripped from the callee.
        let src = "\
package p

func main() {
    Cast[int](42)
    container.Get[string](\"k\")
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        let cast = calls.iter().find(|c| c.callee == "Cast").unwrap();
        assert_eq!(cast.caller, "main");
        let get = calls.iter().find(|c| c.callee == "container.Get").unwrap();
        assert_eq!(get.caller, "main");
    }

    #[test]
    fn go_call_defer_records_inner_call() {
        // `defer X()` — `defer` is filtered, `X` is emitted as callee.
        let src = "\
package p

func main() {
    defer cleanup()
    defer fmt.Println(\"bye\")
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        assert!(calls.iter().any(|c| c.callee == "cleanup"));
        assert!(calls.iter().any(|c| c.callee == "fmt.Println"));
        // `defer` itself must NOT appear.
        assert!(
            !calls.iter().any(|c| c.callee == "defer"),
            "defer keyword should be filtered, got {calls:#?}"
        );
    }

    #[test]
    fn go_call_go_keyword_records_inner_call() {
        // `go X()` — `go` is filtered, `X` is emitted as callee.
        let src = "\
package p

func spawn() {
    go worker()
    go pool.Submit(task)
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        assert!(calls.iter().any(|c| c.callee == "worker"));
        assert!(calls.iter().any(|c| c.callee == "pool.Submit"));
        assert!(
            !calls.iter().any(|c| c.callee == "go"),
            "go keyword should be filtered, got {calls:#?}"
        );
    }

    #[test]
    fn go_call_builtin_filter_policy() {
        // Policy:
        //   make / new / len / cap / append / copy / delete  → RECORDED
        //   panic / recover / print / println               → FILTERED
        let src = "\
package p

func work() {
    s := make([]int, 0)
    p := new(int)
    n := len(s)
    c := cap(s)
    s = append(s, 1)
    copy(dst, src)
    delete(m, k)
    panic(\"x\")
    recover()
    println(\"x\")
    print(\"x\")
    real_call()
}
";
        let calls = extract_go_calls(src, "g.go");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        // Recorded builtins:
        for kept in &["make", "new", "len", "cap", "append", "copy", "delete"] {
            assert!(
                names.contains(kept),
                "expected {kept} to be recorded, got {names:?}"
            );
        }
        // Filtered builtins:
        for filtered in &["panic", "recover", "println", "print"] {
            assert!(
                !names.contains(filtered),
                "expected {filtered} to be filtered, got {names:?}"
            );
        }
        // And real_call must also be there.
        assert!(names.contains(&"real_call"));
    }

    #[test]
    fn go_call_string_and_comment_masking() {
        // Calls inside strings / comments must NOT be recorded.
        let src = "\
package p

func main() {
    s := \"foo() bar()\"
    // ignored() also
    /* block_call() too */
    real()
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real");
        assert_eq!(calls[0].caller, "main");
    }

    #[test]
    fn go_call_raw_string_with_braces_doesnt_break_scope() {
        // A raw string `\`...\`` can span lines AND contain `{` — these
        // must NOT count toward brace depth, otherwise the function
        // scope would close mid-body.
        let src = "\
package p

func main() {
    q := `SELECT { a } FROM t WHERE { b }`
    later()
}

func other() {
    elsewhere()
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        let later = calls.iter().find(|c| c.callee == "later").unwrap();
        assert_eq!(later.caller, "main");
        let elsewhere = calls.iter().find(|c| c.callee == "elsewhere").unwrap();
        assert_eq!(elsewhere.caller, "other");
    }

    #[test]
    fn go_call_multiline_raw_string_with_braces() {
        // Same as above but the raw string actually spans multiple lines.
        let src = "\
package p

func main() {
    q := `line1 {
multi { line }
end }`
    later()
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "later");
        assert_eq!(calls[0].caller, "main", "scope must survive multi-line raw string");
    }

    #[test]
    fn go_call_anonymous_func_transparent_to_scope() {
        // Calls inside `func() { … }()` literals attribute to the outer
        // function — anonymous func is transparent. Most common in
        // `defer func() { … }()` and `go func() { … }()`.
        let src = "\
package p

func outer() {
    defer func() {
        cleanup()
    }()
    go func() {
        worker()
    }()
    direct()
}
";
        let calls = extract_go_calls(src, "g.go");
        // cleanup + worker + direct = 3
        assert_eq!(calls.len(), 3, "got {calls:#?}");
        for c in &calls {
            assert_eq!(
                c.caller, "outer",
                "anonymous func should be transparent — caller stays `outer`"
            );
        }
    }

    #[test]
    fn go_call_module_scope_call() {
        // A call inside a top-level `var x = compute()` has caller="".
        let src = "\
package p

var x = compute()

func F() {
    inside()
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        let c1 = calls.iter().find(|c| c.callee == "compute").unwrap();
        assert_eq!(c1.caller, "", "module-scope call gets empty caller");
        let c2 = calls.iter().find(|c| c.callee == "inside").unwrap();
        assert_eq!(c2.caller, "F");
    }

    #[test]
    fn go_call_keyword_filter() {
        // `if`, `for`, `switch` look like calls but aren't. `for cond {`
        // doesn't have `(`, but `for (cond) {` (rare) shouldn't fire
        // either, nor should patterns like `if cond {`.
        let src = "\
package p

func main() {
    if cond {
        real_a()
    }
    for i := 0; i < n; i++ {
        real_b()
    }
    switch x {
    case 1:
        real_c()
    }
}
";
        let calls = extract_go_calls(src, "g.go");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        for filtered in &["if", "for", "switch", "case"] {
            assert!(
                !names.contains(filtered),
                "expected {filtered} to be filtered, got {names:?}"
            );
        }
        // The three real calls must be there.
        assert!(names.contains(&"real_a"));
        assert!(names.contains(&"real_b"));
        assert!(names.contains(&"real_c"));
        for c in &calls {
            assert_eq!(c.caller, "main");
        }
    }

    #[test]
    fn go_call_multiple_calls_per_line() {
        // Several calls on a single line — all recorded, same caller / line.
        let src = "\
package p

func main() {
    a(); b(); c.D(e())
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 4, "got {calls:#?}");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert!(names.contains(&"a"));
        assert!(names.contains(&"b"));
        assert!(names.contains(&"c.D"));
        assert!(names.contains(&"e"));
        for c in &calls {
            assert_eq!(c.line, 4);
            assert_eq!(c.caller, "main");
        }
    }

    #[test]
    fn go_call_nested_function_scope_pops_correctly() {
        // After the first function closes, calls in the next function
        // must NOT carry the previous caller.
        let src = "\
package p

func A() {
    one()
}

func B() {
    two()
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        let one = calls.iter().find(|c| c.callee == "one").unwrap();
        assert_eq!(one.caller, "A");
        let two = calls.iter().find(|c| c.callee == "two").unwrap();
        assert_eq!(two.caller, "B", "scope must pop after A's `}}`");
    }

    #[test]
    fn go_call_method_on_call_result() {
        // `f().Method()` — `f` is one call, `.Method` is another (the
        // receiver is a non-identifier expression so the dotted-method
        // branch fires).
        let src = "\
package p

func main() {
    f().Method()
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 2, "got {calls:#?}");
        assert!(calls.iter().any(|c| c.callee == "f"));
        assert!(calls.iter().any(|c| c.callee == ".Method"));
        for c in &calls {
            assert_eq!(c.caller, "main");
        }
    }

    #[test]
    fn go_call_immediate_invocation_anonymous_func_skips() {
        // `func() { x() }()` — the trailing `()` after `}` has no
        // identifier prefix, so no call is emitted FOR the IIFE itself.
        // The inner `x()` IS emitted, attributed to the outer caller.
        let src = "\
package p

func outer() {
    func() {
        x()
    }()
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "x");
        assert_eq!(calls[0].caller, "outer");
    }

    #[test]
    fn go_call_generic_receiver_normalises() {
        // `func (r T[U]) Method()` — receiver type params stripped, so
        // caller becomes `T.Method` (not `T[U].Method`).
        let src = "\
package p

func (c Container[T]) Get(k string) T {
    return c.lookup(k)
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        // `c.lookup` — path walker keeps the literal text; we don't
        // attempt receiver-vs-package disambiguation.
        assert_eq!(calls[0].callee, "c.lookup");
        assert_eq!(calls[0].caller, "Container.Get");
    }

    #[test]
    fn go_call_multiline_signature() {
        // Signature that wraps with `{` on a later line.
        let src = "\
package p

func LongName(
    a int,
    b string,
) {
    body_call()
}
";
        let calls = extract_go_calls(src, "g.go");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "body_call");
        assert_eq!(calls[0].caller, "LongName");
    }

    // ── Phase 2 #3 third slice (cont.) — TS/JS call extractor ──────────────

    #[test]
    fn ts_call_bare_function() {
        let src = "\
function outer() {
    foo();
}
";
        let calls = extract_ts_calls(src, "f.ts", "typescript");
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, "foo");
        assert_eq!(calls[0].caller, "outer");
        assert_eq!(calls[0].language, "typescript");
    }

    #[test]
    fn ts_call_qualified_path() {
        let src = "\
function outer() {
    React.useState(0);
    Object.keys(map);
}
";
        let calls = extract_ts_calls(src, "f.tsx", "typescript");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["React.useState", "Object.keys"]);
    }

    #[test]
    fn ts_call_method_via_qualified_path() {
        // TS/JS uses `.` for both qualified calls and method calls,
        // so `arr.push(1)` becomes callee=`arr.push` (not `.push`).
        let src = "\
function outer() {
    arr.push(1);
    arr.map(x => x);
}
";
        let calls = extract_ts_calls(src, "f.ts", "typescript");
        assert_eq!(calls.len(), 2);
        assert_eq!(calls[0].callee, "arr.push");
        assert_eq!(calls[1].callee, "arr.map");
    }

    #[test]
    fn ts_call_method_dot_after_call_expression() {
        // The leading-`.` method form fires when there's no preceding
        // identifier — typically after a `)` from a chained call.
        let src = "\
function outer() {
    foo().bar();
    arr.filter(x => x).map(y => y);
}
";
        let calls = extract_ts_calls(src, "f.ts", "typescript");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["foo", ".bar", "arr.filter", ".map"]);
    }

    #[test]
    fn ts_call_skips_keywords() {
        let src = "\
function outer() {
    if (cond()) return;
    while (more()) { break; }
    const x = new Foo();
    return foo();
}
";
        let calls = extract_ts_calls(src, "f.ts", "typescript");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["cond", "more", "Foo", "foo"]);
    }

    #[test]
    fn ts_call_skips_strings_and_comments() {
        let src = "\
function outer() {
    const s = \"foo()\";
    const t = 'bar()';
    const u = `template ${baz()}`;
    /* multi
       line fake_call();
       another();
    */
    real_call();
}
";
        let calls = extract_ts_calls(src, "f.ts", "typescript");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
    }

    #[test]
    fn ts_call_class_method_qualifies_caller() {
        let src = "\
class Foo {
    bar() {
        helper();
    }
    static factory() {
        Foo.bar();
    }
}
";
        let calls = extract_ts_calls(src, "f.ts", "typescript");
        let helper = calls.iter().find(|c| c.callee == "helper").unwrap();
        assert_eq!(helper.caller, "Foo.bar");
        let factory_call = calls.iter().find(|c| c.callee == "Foo.bar").unwrap();
        assert_eq!(factory_call.caller, "Foo.factory");
    }

    #[test]
    fn ts_call_async_function() {
        let src = "\
async function outer() {
    await fetch(url);
    return data();
}
";
        let calls = extract_ts_calls(src, "f.ts", "typescript");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["fetch", "data"]);
        assert!(calls.iter().all(|c| c.caller == "outer"));
    }

    #[test]
    fn ts_call_constructor_emits_class_name() {
        let src = "\
function outer() {
    const a = new Foo(1);
    const b = new pkg.Bar();
}
";
        let calls = extract_ts_calls(src, "f.ts", "typescript");
        let names: Vec<&str> = calls.iter().map(|c| c.callee.as_str()).collect();
        assert_eq!(names, ["Foo", "pkg.Bar"]);
    }

    #[test]
    fn ts_call_optional_chain_method() {
        let src = "\
function outer() {
    obj?.method?.();
    arr?.length;
}
";
        let calls = extract_ts_calls(src, "f.ts", "typescript");
        // `?.length` is a property access (no `(` after), not a call.
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].callee, ".method");
    }

    #[test]
    fn ts_call_multiline_template_string_does_not_leak() {
        let src = "\
function outer() {
    const t = `multi
        line template
        with fake_call();`;
    real_call();
}
";
        let calls = extract_ts_calls(src, "f.ts", "typescript");
        assert_eq!(calls.len(), 1, "got {calls:#?}");
        assert_eq!(calls[0].callee, "real_call");
    }
}
