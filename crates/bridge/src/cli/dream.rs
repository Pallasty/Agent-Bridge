use std::path::Path;

/// Immutable audit row produced by the authority-bearing promote executor.
#[derive(Debug, Clone)]
pub(crate) struct PromoteDecision {
    pub(crate) key_a: String,
    pub(crate) key_b: String,
    pub(crate) count: u64,
    pub(crate) weight: f64,
    pub(crate) status: PromoteStatus,
}

/// Completed status of one promote candidate.
#[derive(Debug, Clone)]
pub(crate) enum PromoteStatus {
    Promoted,
    WouldPromote,
    Skipped,
    Failed(String),
}

pub(crate) fn short_key(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let truncated: String = s.chars().take(max - 1).collect();
        format!("{truncated}…")
    }
}

pub(crate) fn truncate_chars(s: &str, n: usize) -> String {
    if s.chars().count() <= n {
        s.to_string()
    } else {
        let prefix: String = s.chars().take(n.saturating_sub(1)).collect();
        format!("{prefix}…")
    }
}

/// Render a self-contained HTML audit report for a completed `dream promote` run.
pub(crate) fn render_promote_html(
    min_count: u64,
    limit: u32,
    dry_run: bool,
    db_path: &Path,
    decisions: &[PromoteDecision],
    generated_at: &str,
) -> String {
    let total = decisions.len();
    let promoted = decisions
        .iter()
        .filter(|d| {
            matches!(
                d.status,
                PromoteStatus::Promoted | PromoteStatus::WouldPromote
            )
        })
        .count();
    let skipped = decisions
        .iter()
        .filter(|d| matches!(d.status, PromoteStatus::Skipped))
        .count();
    let errors = decisions
        .iter()
        .filter(|d| matches!(d.status, PromoteStatus::Failed(_)))
        .count();

    let dry_badge = if dry_run {
        r#"<span class="badge badge-dry">DRY RUN — NO WRITES</span>"#
    } else {
        r#"<span class="badge badge-live">LIVE RUN</span>"#
    };

    let mut strength_map = String::new();
    for (i, d) in decisions.iter().enumerate() {
        let cls = chip_class(&d.status, d.weight);
        let label = format!("{} ↔ {}", short_key(&d.key_a, 24), short_key(&d.key_b, 24));
        let title = format!(
            "{} ↔ {} — {} fires, w={:.2}",
            d.key_a, d.key_b, d.count, d.weight
        );
        strength_map.push_str(&format!(
            r##"<a class="chip {cls}" href="#pair-{i}" title="{title}">{label} <span class="chip-count">{count}</span></a>"##,
            cls = cls,
            i = i,
            title = html_escape(&title),
            label = html_escape(&label),
            count = d.count,
        ));
    }

    let mut cards = String::new();
    for (i, d) in decisions.iter().enumerate() {
        let (status_text, status_cls) = match &d.status {
            PromoteStatus::Promoted => ("PROMOTED", "status-promoted"),
            PromoteStatus::WouldPromote => ("WOULD PROMOTE", "status-would"),
            PromoteStatus::Skipped => ("SKIPPED — cofires already exists", "status-skipped"),
            PromoteStatus::Failed(_) => ("FAILED", "status-failed"),
        };
        let err_block = match &d.status {
            PromoteStatus::Failed(msg) => {
                format!(r#"<div class="error-msg">{}</div>"#, html_escape(msg))
            }
            _ => String::new(),
        };
        let weight_pct = (d.weight * 100.0).round() as u32;
        cards.push_str(&format!(
            r##"<div id="pair-{i}" class="card">
  <div class="card-head">
    <span class="card-num">#{n}</span>
    <span class="badge {status_cls}">{status_text}</span>
    <span class="card-meta">{count} fires · w={weight:.2}</span>
  </div>
  <div class="card-pair">
    <a class="key" href="http://localhost:7979/?focus={key_a_url}" title="{key_a_full}">{key_a_disp}</a>
    <span class="sep">↔</span>
    <a class="key" href="http://localhost:7979/?focus={key_b_url}" title="{key_b_full}">{key_b_disp}</a>
  </div>
  <div class="weight-bar"><div class="weight-fill" style="width:{weight_pct}%"></div></div>
  {err_block}
</div>
"##,
            i = i,
            n = i + 1,
            status_text = status_text,
            status_cls = status_cls,
            count = d.count,
            weight = d.weight,
            weight_pct = weight_pct,
            key_a_url = url_escape(&d.key_a),
            key_b_url = url_escape(&d.key_b),
            key_a_full = html_escape(&d.key_a),
            key_b_full = html_escape(&d.key_b),
            key_a_disp = html_escape(&d.key_a),
            key_b_disp = html_escape(&d.key_b),
            err_block = err_block,
        ));
    }

    let empty_msg = if decisions.is_empty() {
        r#"<p class="empty">No co-activation pairs at or above the threshold. Either the system is quiet (try lowering <code>--min-count</code>) or all strong pairs are already structurally wired.</p>"#
    } else {
        ""
    };

    format!(
        r##"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>dream promote — {timestamp}</title>
<style>
  :root {{
    --bg: #0f0f14;
    --panel: #1a1a22;
    --border: #2a2a38;
    --text: #e0e0e8;
    --dim: #8a8a96;
    --cyan-strong: #5cc8c8;
    --cyan-mid: #4a8b9c;
    --amber: #d4a64a;
    --purple: #7a4ba8;
    --red: #c8505c;
    --green: #5cc88a;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font: 14px/1.55 -apple-system, "Segoe UI", system-ui, sans-serif;
    padding: 28px 36px 60px;
    max-width: 1200px;
    margin: 0 auto;
  }}
  h1 {{ margin: 0 0 8px; font-size: 22px; font-weight: 600; }}
  h2 {{ margin: 32px 0 12px; font-size: 14px; font-weight: 600; color: var(--dim);
        text-transform: uppercase; letter-spacing: 0.08em; }}
  code, .key, .weight-bar {{ font-family: "JetBrains Mono", "SF Mono", Menlo, monospace; }}
  a {{ color: inherit; text-decoration: none; }}
  .header {{ display: flex; flex-direction: column; gap: 6px; padding-bottom: 18px;
            border-bottom: 1px solid var(--border); }}
  .meta-row {{ display: flex; gap: 14px; flex-wrap: wrap; color: var(--dim); font-size: 12px; }}
  .meta-row code {{ color: var(--text); }}
  .stats {{ display: flex; gap: 18px; margin-top: 6px; }}
  .stat {{ font-size: 13px; }}
  .stat .num {{ font-size: 18px; font-weight: 600; margin-right: 4px; }}
  .stat-promoted .num {{ color: var(--cyan-strong); }}
  .stat-skipped  .num {{ color: var(--purple); }}
  .stat-failed   .num {{ color: var(--red); }}

  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px;
           font-size: 11px; font-weight: 600; letter-spacing: 0.05em; }}
  .badge-dry  {{ background: #2a2316; color: var(--amber); border: 1px solid var(--amber); }}
  .badge-live {{ background: #16241e; color: var(--green);  border: 1px solid var(--green);  }}
  .status-promoted {{ background: #16242a; color: var(--cyan-strong); border: 1px solid var(--cyan-strong); }}
  .status-would    {{ background: #16242a; color: var(--cyan-mid);    border: 1px solid var(--cyan-mid); }}
  .status-skipped  {{ background: #1f1830; color: var(--purple);      border: 1px solid var(--purple); }}
  .status-failed   {{ background: #2a161a; color: var(--red);         border: 1px solid var(--red); }}

  .strength-map {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 8px; }}
  .chip {{ display: inline-flex; align-items: center; gap: 6px;
          padding: 4px 9px; border-radius: 3px; font-size: 12px;
          border: 1px solid var(--border); background: var(--panel);
          font-family: "JetBrains Mono", "SF Mono", Menlo, monospace; }}
  .chip:hover {{ filter: brightness(1.25); }}
  .chip-count {{ font-size: 10px; padding: 1px 5px; border-radius: 2px;
                background: rgba(255,255,255,0.08); color: var(--dim); }}
  .chip-strong  {{ border-color: var(--cyan-strong); color: var(--cyan-strong); }}
  .chip-mid     {{ border-color: var(--cyan-mid);    color: var(--cyan-mid); }}
  .chip-weak    {{ border-color: var(--amber);       color: var(--amber); }}
  .chip-skipped {{ border-color: var(--purple);      color: var(--purple); }}
  .chip-failed  {{ border-color: var(--red);         color: var(--red); }}

  .card {{ background: var(--panel); border: 1px solid var(--border);
          border-radius: 4px; padding: 14px 16px; margin: 10px 0; }}
  .card-head {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
  .card-num {{ color: var(--dim); font-size: 12px; }}
  .card-meta {{ color: var(--dim); font-size: 12px; margin-left: auto; }}
  .card-pair {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
               font-size: 13px; padding: 4px 0; }}
  .card-pair .key {{ color: var(--text); border-bottom: 1px dotted var(--dim);
                     padding: 1px 2px; }}
  .card-pair .key:hover {{ color: var(--cyan-strong); border-bottom-color: var(--cyan-strong); }}
  .card-pair .sep {{ color: var(--dim); }}
  .weight-bar {{ height: 4px; background: rgba(255,255,255,0.04);
                border-radius: 2px; overflow: hidden; margin-top: 8px; }}
  .weight-fill {{ height: 100%; background: linear-gradient(90deg, var(--amber), var(--cyan-strong)); }}
  .error-msg {{ margin-top: 8px; padding: 6px 10px; background: #2a161a;
               border-left: 3px solid var(--red); border-radius: 2px;
               font-family: monospace; font-size: 12px; color: var(--red); }}

  .footer {{ margin-top: 36px; padding-top: 18px; border-top: 1px solid var(--border);
            color: var(--dim); font-size: 12px; }}
  .empty {{ color: var(--dim); padding: 16px; background: var(--panel);
           border-radius: 4px; border: 1px dashed var(--border); }}
</style>
</head>
<body>
<div class="header">
  <h1>dream promote — Hebbian crystallization</h1>
  <div class="meta-row">
    {dry_badge}
    <span>min_count <code>{min_count}</code></span>
    <span>limit <code>{limit}</code></span>
    <span>generated <code>{timestamp}</code></span>
  </div>
  <div class="stats">
    <span class="stat stat-promoted"><span class="num">{promoted}</span>{promoted_label}</span>
    <span class="stat stat-skipped"><span class="num">{skipped}</span>skipped</span>
    {errors_stat}
    <span class="stat" style="color: var(--dim);"><span class="num">{total}</span>candidates</span>
  </div>
</div>

<h2>Strength Map</h2>
<div class="strength-map">{strength_map}</div>

<h2>Decisions</h2>
{empty_msg}
{cards}

<div class="footer">
  DB: <code>{db_display}</code><br>
  Pairs link to Palace at <code>http://localhost:7979/?focus=KEY</code> — start with <code>agent-bridge palace serve</code> if not running.<br>
  Generated by <code>agent-bridge dream promote</code> · cyan = co-activation strength · purple = structural · red = error
</div>

</body>
</html>
"##,
        timestamp = html_escape(generated_at),
        dry_badge = dry_badge,
        min_count = min_count,
        limit = limit,
        total = total,
        promoted = promoted,
        skipped = skipped,
        promoted_label = if dry_run { "would promote" } else { "promoted" },
        errors_stat = if errors > 0 {
            format!(
                r#"<span class="stat stat-failed"><span class="num">{}</span>failed</span>"#,
                errors
            )
        } else {
            String::new()
        },
        strength_map = strength_map,
        empty_msg = empty_msg,
        cards = cards,
        db_display = html_escape(&db_path.display().to_string()),
    )
}

/// Render a self-contained HTML report for a completed `dream codebase-report` run.
pub(crate) fn render_codebase_report_html(
    stats: &ab_store::CodebaseCallStats,
    db_path: &Path,
    generated_at: &str,
) -> String {
    let lang_pills = if stats.per_language.is_empty() {
        r#"<span class="empty-inline">no calls</span>"#.to_string()
    } else {
        stats
            .per_language
            .iter()
            .map(|l| {
                format!(
                    r#"<span class="lang-pill"><b>{lang}</b> <span class="num">{calls}</span> calls · <span class="num">{files}</span> files</span>"#,
                    lang = html_escape(&l.language),
                    calls = l.call_count,
                    files = l.distinct_files,
                )
            })
            .collect::<Vec<_>>()
            .join("\n")
    };

    let callee_peak = stats.hot_callees.first().map(|x| x.call_count).unwrap_or(1);
    let hot_callee_rows = stats
        .hot_callees
        .iter()
        .enumerate()
        .map(|(i, h)| {
            format!(
                r##"<tr>
  <td class="rank">{rank}</td>
  <td class="callee"><code>{callee}</code></td>
  <td class="num"><span class="bar" style="width:{bar_pct}%"></span>{count}</td>
  <td class="num">{callers}</td>
  <td class="langs">{langs}</td>
</tr>"##,
                rank = i + 1,
                callee = html_escape(&h.callee),
                bar_pct = bar_pct(h.call_count, callee_peak),
                count = h.call_count,
                callers = h.distinct_callers,
                langs = h
                    .languages
                    .iter()
                    .map(|l| format!(r#"<span class="lang-chip">{}</span>"#, html_escape(l)))
                    .collect::<Vec<_>>()
                    .join(" "),
            )
        })
        .collect::<String>();

    let caller_peak = stats
        .hot_callers
        .first()
        .map(|x| x.distinct_callees)
        .unwrap_or(1);
    let hot_caller_rows = stats
        .hot_callers
        .iter()
        .enumerate()
        .map(|(i, c)| {
            format!(
                r##"<tr>
  <td class="rank">{rank}</td>
  <td class="caller"><code>{caller}</code></td>
  <td class="file"><code>{file}</code></td>
  <td class="num"><span class="bar bar-purple" style="width:{bar_pct}%"></span>{fanout}</td>
  <td class="num">{total}</td>
  <td class="langs"><span class="lang-chip">{lang}</span></td>
</tr>"##,
                rank = i + 1,
                caller = html_escape(&c.caller),
                file = html_escape(&c.file_path),
                bar_pct = bar_pct(c.distinct_callees, caller_peak),
                fanout = c.distinct_callees,
                total = c.total_calls,
                lang = html_escape(&c.language),
            )
        })
        .collect::<String>();

    let file_peak = stats
        .fan_out_files
        .first()
        .map(|x| x.distinct_callees)
        .unwrap_or(1);
    let fan_file_rows = stats
        .fan_out_files
        .iter()
        .enumerate()
        .map(|(i, f)| {
            format!(
                r##"<tr>
  <td class="rank">{rank}</td>
  <td class="file"><code>{file}</code></td>
  <td class="num"><span class="bar bar-purple" style="width:{bar_pct}%"></span>{fanout}</td>
  <td class="num">{total}</td>
  <td class="langs"><span class="lang-chip">{lang}</span></td>
</tr>"##,
                rank = i + 1,
                file = html_escape(&f.file_path),
                bar_pct = bar_pct(f.distinct_callees, file_peak),
                fanout = f.distinct_callees,
                total = f.total_calls,
                lang = html_escape(&f.language),
            )
        })
        .collect::<String>();

    let (orphan_real, orphan_fp): (Vec<_>, Vec<_>) =
        stats.orphan_functions.iter().partition(|o| !o.likely_fp);
    let orphan_rows = orphan_real
        .iter()
        .enumerate()
        .map(|(i, o)| {
            format!(
                r##"<tr>
  <td class="rank">{rank}</td>
  <td class="kind"><span class="kind-chip">{kind}</span></td>
  <td class="name"><code>{name}</code></td>
  <td class="file"><code>{file}:{line}</code></td>
  <td class="langs"><span class="lang-chip">{lang}</span></td>
</tr>"##,
                rank = i + 1,
                kind = html_escape(&o.kind),
                name = html_escape(&o.name),
                file = html_escape(&o.file_path),
                line = o.line,
                lang = html_escape(&o.language),
            )
        })
        .collect::<String>();
    let orphan_fp_rows = orphan_fp
        .iter()
        .enumerate()
        .map(|(i, o)| {
            format!(
                r##"<tr class="fp-row">
  <td class="rank">{rank}</td>
  <td class="kind"><span class="kind-chip">{kind}</span></td>
  <td class="name"><code>{name}</code></td>
  <td class="fp-reason"><span class="fp-chip">{reason}</span></td>
  <td class="file"><code>{file}:{line}</code></td>
  <td class="langs"><span class="lang-chip">{lang}</span></td>
</tr>"##,
                rank = i + 1,
                kind = html_escape(&o.kind),
                name = html_escape(&o.name),
                reason = html_escape(&o.likely_fp_reason),
                file = html_escape(&o.file_path),
                line = o.line,
                lang = html_escape(&o.language),
            )
        })
        .collect::<String>();

    let empty_state = if stats.total_calls == 0 {
        r#"<p class="empty">No calls indexed for this root. Run <code>agent-bridge codebase index &lt;root&gt;</code> first, or check that the root path matches the indexed one (canonical form).</p>"#
    } else {
        ""
    };

    format!(
        r##"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>codebase report — {timestamp}</title>
<style>
  :root {{
    --bg: #0f0f14;
    --panel: #1a1a22;
    --border: #2a2a38;
    --text: #e0e0e8;
    --dim: #8a8a96;
    --cyan-strong: #5cc8c8;
    --cyan-mid: #4a8b9c;
    --amber: #d4a64a;
    --purple: #7a4ba8;
    --red: #c8505c;
    --green: #5cc88a;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font: 14px/1.55 -apple-system, "Segoe UI", system-ui, sans-serif;
    padding: 28px 36px 60px;
    max-width: 1280px;
    margin: 0 auto;
  }}
  h1 {{ margin: 0 0 8px; font-size: 22px; font-weight: 600; }}
  h2 {{ margin: 32px 0 12px; font-size: 14px; font-weight: 600; color: var(--dim);
        text-transform: uppercase; letter-spacing: 0.08em; }}
  code {{ font-family: "JetBrains Mono", "SF Mono", Menlo, monospace; color: var(--text); }}
  a {{ color: inherit; text-decoration: none; }}
  .header {{ display: flex; flex-direction: column; gap: 6px; padding-bottom: 18px;
            border-bottom: 1px solid var(--border); }}
  .meta-row {{ display: flex; gap: 14px; flex-wrap: wrap; color: var(--dim); font-size: 12px; }}
  .meta-row code {{ color: var(--text); }}
  .stats {{ display: flex; gap: 18px; margin-top: 6px; }}
  .stat .num {{ font-size: 18px; font-weight: 600; margin-right: 4px; }}
  .stat-calls .num {{ color: var(--cyan-strong); }}
  .stat-files .num {{ color: var(--cyan-mid); }}

  .lang-pills {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 8px; }}
  .lang-pill {{ padding: 6px 12px; border-radius: 4px;
               background: var(--panel); border: 1px solid var(--border);
               font-size: 13px; color: var(--cyan-mid); }}
  .lang-pill b {{ color: var(--text); }}
  .lang-pill .num {{ color: var(--cyan-strong); font-weight: 600; }}

  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 0;
          font-size: 13px; }}
  th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--dim); font-weight: 600; font-size: 11px;
       text-transform: uppercase; letter-spacing: 0.06em; }}
  tr:hover td {{ background: rgba(255,255,255,0.025); }}
  td.rank {{ color: var(--dim); width: 36px; }}
  td.num {{ font-family: "JetBrains Mono", "SF Mono", Menlo, monospace;
           font-variant-numeric: tabular-nums; white-space: nowrap;
           position: relative; }}
  td.callee code, td.caller code, td.name code {{ color: var(--cyan-strong); }}
  td.file code {{ color: var(--dim); font-size: 12px; }}

  .bar {{ display: inline-block; height: 100%;
         position: absolute; left: 0; top: 0;
         background: linear-gradient(90deg, var(--cyan-mid), var(--cyan-strong));
         opacity: 0.18; }}
  .bar-purple {{ background: linear-gradient(90deg, var(--purple), #b07ed0); }}

  .lang-chip {{ display: inline-block; padding: 1px 6px; border-radius: 2px;
               background: rgba(92,200,200,0.1); color: var(--cyan-mid);
               font-size: 11px; font-family: "JetBrains Mono", monospace;
               margin-right: 3px; }}
  .kind-chip {{ display: inline-block; padding: 1px 6px; border-radius: 2px;
               background: rgba(122,75,168,0.12); color: var(--purple);
               font-size: 11px; font-family: "JetBrains Mono", monospace; }}
  .fp-chip {{ display: inline-block; padding: 1px 6px; border-radius: 2px;
             background: rgba(212,166,74,0.10); color: var(--amber);
             font-size: 11px; font-family: "JetBrains Mono", monospace; }}
  .fp-table tr.fp-row td {{ color: var(--dim); }}
  .fp-table tr.fp-row td.name code,
  .fp-table tr.fp-row td.file code {{ color: var(--dim); }}

  .caveat {{ margin: 10px 0; padding: 8px 12px;
            background: #2a2316; border-left: 3px solid var(--amber);
            border-radius: 2px; color: var(--amber); font-size: 12px; }}
  .caveat b {{ color: #f0c468; }}

  .empty {{ color: var(--dim); padding: 16px; background: var(--panel);
           border-radius: 4px; border: 1px dashed var(--border); }}
  .empty-inline {{ color: var(--dim); font-style: italic; }}

  .footer {{ margin-top: 36px; padding-top: 18px; border-top: 1px solid var(--border);
            color: var(--dim); font-size: 12px; }}
</style>
</head>
<body>
<div class="header">
  <h1>codebase call-graph audit</h1>
  <div class="meta-row">
    <span>root <code>{root}</code></span>
    <span>generated <code>{timestamp}</code></span>
  </div>
  <div class="stats">
    <span class="stat stat-calls"><span class="num">{total_calls}</span>calls</span>
    <span class="stat stat-files"><span class="num">{files}</span>files with calls</span>
  </div>
</div>

{empty_state}

<h2>Per-language</h2>
<div class="lang-pills">{lang_pills}</div>

<h2>Hot callees — top {hc_n}</h2>
<table>
<thead><tr>
  <th></th><th>callee (raw)</th><th>calls</th><th>callers</th><th>langs</th>
</tr></thead>
<tbody>{hot_callee_rows}</tbody>
</table>

<h2>Fan-out callers — top {hcr_n}</h2>
<table>
<thead><tr>
  <th></th><th>caller</th><th>file</th><th>fan-out</th><th>total</th><th>lang</th>
</tr></thead>
<tbody>{hot_caller_rows}</tbody>
</table>

<h2>Fan-out files — top {ff_n}</h2>
<table>
<thead><tr>
  <th></th><th>file</th><th>fan-out</th><th>total</th><th>lang</th>
</tr></thead>
<tbody>{fan_file_rows}</tbody>
</table>

<h2>Orphan function candidates — {orphan_real_n} high-confidence</h2>
<div class="caveat">
  <b>Best-effort, alias-blind.</b> Last-segment matching only — false positives include trait dispatch, dyn dispatch, reflection / string-key dispatch, FFI exports, and macro-generated callers. Use as a starting list, not a verdict.
</div>
<table>
<thead><tr>
  <th></th><th>kind</th><th>name</th><th>file:line</th><th>lang</th>
</tr></thead>
<tbody>{orphan_rows}</tbody>
</table>

<h2>Likely false positives — {orphan_fp_n}</h2>
<div class="caveat" style="background: #1f1a2a; border-left-color: var(--purple); color: var(--dim);">
  Rows tagged with known false-positive heuristics: test-file paths (callers via <code>#[test]</code> / pytest macros are invisible to the extractor), <code>main</code> entries (runtime-called), pytest <code>test_*</code> naming convention. Shown for completeness — verify before acting.
</div>
<table class="fp-table">
<thead><tr>
  <th></th><th>kind</th><th>name</th><th>reason</th><th>file:line</th><th>lang</th>
</tr></thead>
<tbody>{orphan_fp_rows}</tbody>
</table>

<div class="footer">
  DB: <code>{db_display}</code><br>
  Generated by <code>dream codebase-report</code> at <code>{timestamp}</code>.
</div>

</body>
</html>
"##,
        timestamp = html_escape(generated_at),
        root = html_escape(&stats.root_path),
        total_calls = stats.total_calls,
        files = stats.distinct_caller_files,
        lang_pills = lang_pills,
        hc_n = stats.hot_callees.len(),
        hot_callee_rows = hot_callee_rows,
        hcr_n = stats.hot_callers.len(),
        hot_caller_rows = hot_caller_rows,
        ff_n = stats.fan_out_files.len(),
        fan_file_rows = fan_file_rows,
        orphan_real_n = orphan_real.len(),
        orphan_rows = orphan_rows,
        orphan_fp_n = orphan_fp.len(),
        orphan_fp_rows = orphan_fp_rows,
        empty_state = empty_state,
        db_display = html_escape(&db_path.display().to_string()),
    )
}

fn chip_class(status: &PromoteStatus, weight: f64) -> &'static str {
    match status {
        PromoteStatus::Skipped => "chip-skipped",
        PromoteStatus::Failed(_) => "chip-failed",
        PromoteStatus::Promoted | PromoteStatus::WouldPromote => {
            if weight >= 0.8 {
                "chip-strong"
            } else if weight >= 0.65 {
                "chip-mid"
            } else {
                "chip-weak"
            }
        }
    }
}

fn html_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(c),
        }
    }
    out
}

fn url_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        let safe =
            b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.' | b'~' | b':' | b'/');
        if safe {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{:02X}", b));
        }
    }
    out
}

fn bar_pct(count: u64, peak: u64) -> u32 {
    if peak == 0 {
        return 0;
    }
    let raw = (count as f64 / peak as f64) * 100.0;
    raw.round().clamp(0.0, 100.0) as u32
}
