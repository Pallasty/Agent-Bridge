//! Pure-Rust symbol extractor — no C dependencies, no build scripts.
//!
//! Supports Rust, Python, TypeScript/JavaScript, and Go via line-based
//! pattern matching. Accurate enough for agent codebase navigation; a
//! tree-sitter backend can be swapped in later if precision is needed.

use crate::{CodebaseImport, CodebaseSymbol};
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
/// Phase 2 #3 second slice ships Rust + Python; TS/JS/Go to follow.
pub fn extract_imports(content: &str, file_path: &str, language: &str) -> Vec<CodebaseImport> {
    match language {
        "rust" => extract_rust_imports(content, file_path),
        "python" => extract_python_imports(content, file_path),
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

fn extract_rust(content: &str, file_path: &str) -> Vec<CodebaseSymbol> {
    let mut out = Vec::new();
    let mut depth: i32 = 0;
    let mut impl_stack: Vec<RustImplScope> = Vec::new();
    // When an `impl …` header has been parsed but the opening `{` lives on
    // a later line (typical with `where` clauses spanning multiple lines),
    // the scope is held here until the brace arrives.
    let mut pending_impl: Option<(String, Option<String>)> = None;

    for (i, raw) in content.lines().enumerate() {
        let t = raw.trim();
        let is_comment = t.starts_with("//") || t.starts_with("/*") || t.starts_with('*');
        if is_comment {
            // Comments still count braces (they generally don't contain unmatched
            // ones, but if they do the depth would skew indefinitely; the safer
            // default is to skip brace counting on comment-only lines).
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
            out.push(make(file_path, (i + 1) as u32, kind, emit_name, t, "rust"));
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
}
