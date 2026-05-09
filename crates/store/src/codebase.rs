//! Pure-Rust symbol extractor — no C dependencies, no build scripts.
//!
//! Supports Rust, Python, TypeScript/JavaScript, and Go via line-based
//! pattern matching. Accurate enough for agent codebase navigation; a
//! tree-sitter backend can be swapped in later if precision is needed.

use crate::CodebaseSymbol;
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

fn extract_rust(content: &str, file_path: &str) -> Vec<CodebaseSymbol> {
    let mut out = Vec::new();
    for (i, raw) in content.lines().enumerate() {
        let t = raw.trim();
        if t.starts_with("//") || t.starts_with("/*") || t.starts_with('*') {
            continue;
        }
        let s = strip_vis(t);
        // Handle async/unsafe/const qualifiers
        let s2 = s
            .trim_start_matches("async ")
            .trim_start_matches("unsafe ")
            .trim_start_matches("const ");
        let s2 = strip_vis(s2); // second pass after qualifiers (e.g. `async pub fn`)

        if let Some((kind, name)) = try_kw(
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
                ("impl ", "impl"),
                ("macro_rules! ", "macro"),
            ],
        ) {
            out.push(make(file_path, (i + 1) as u32, kind, name, t, "rust"));
        }
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
}
