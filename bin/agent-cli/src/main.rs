use ab_bridge::default_socket_path;
use ab_core::{RpcRequest, RpcResponse};
use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use serde_json::{json, Value};
use std::path::PathBuf;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::UnixStream;

#[derive(Parser, Debug)]
#[command(version, about = "agent-bridge command line client")]
struct Cli {
    /// Override the bridge socket path.
    #[arg(long, env = "AGENT_BRIDGE_SOCKET")]
    socket: Option<PathBuf>,

    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// Health check — round-trips system.ping.
    Ping,

    /// Print the bridge's advertised methods.
    Capabilities,

    /// Send a desktop notification.
    Notify {
        /// Notification title.
        #[arg(short, long, default_value = "agent-bridge")]
        title: String,

        /// Notification body (positional).
        body: String,

        /// info | success | warning | error | attention
        #[arg(short, long, default_value = "info")]
        severity: String,
    },

    /// Show recent notifications from the persistent store.
    History {
        /// How many entries to print (most recent first).
        #[arg(short = 'n', long, default_value_t = 20)]
        limit: u32,

        /// Print raw JSON instead of the human-readable table.
        #[arg(long)]
        json: bool,
    },

    /// OSC sequence helpers (parse arbitrary text or emit a demo sequence).
    Osc {
        #[command(subcommand)]
        cmd: OscCmd,
    },

    /// Terminal multiplexer commands (requires WezTerm).
    Term {
        #[command(subcommand)]
        cmd: TermCmd,
    },
}

#[derive(Subcommand, Debug)]
enum OscCmd {
    /// Parse a string for OSC notification sequences and dispatch them.
    /// Use `\\x1b` / `\\a` / `\\\\` etc. — backslash escapes are decoded.
    Parse {
        /// Raw text containing one or more OSC sequences.
        raw: String,
    },
    /// Emit a sample OSC 9 / 777 / 99 sequence and dispatch it.
    Demo {
        /// 9 | 777 | 99
        #[arg(default_value = "9")]
        code: String,
    },
}

#[derive(Subcommand, Debug)]
enum TermCmd {
    /// List panes from the active terminal backend.
    List,
    /// Send keystrokes to a pane.
    SendKeys {
        /// Pane id.
        pane: String,
        /// Text to send.
        keys: String,
    },
    /// Split a pane horizontally or vertically.
    Split {
        /// Pane id.
        pane: String,
        /// horizontal | vertical
        #[arg(default_value = "vertical")]
        dir: String,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let socket = cli.socket.unwrap_or_else(default_socket_path);

    // History has its own renderer; everything else just dumps JSON-RPC response.
    if let Cmd::History { limit, json: as_json } = cli.cmd {
        let req = RpcRequest::new(1, "notifications.recent", Some(json!({ "limit": limit })));
        let resp = call(&socket, req).await?;
        if !resp.ok {
            println!("{}", serde_json::to_string_pretty(&resp)?);
            std::process::exit(1);
        }
        if as_json {
            println!("{}", serde_json::to_string_pretty(&resp)?);
        } else {
            render_history(&resp.result.unwrap_or(Value::Null));
        }
        return Ok(());
    }

    let (method, params) = match cli.cmd {
        Cmd::Ping => ("system.ping", None),
        Cmd::Capabilities => ("system.capabilities", None),
        Cmd::Notify { title, body, severity } => (
            "notify.send",
            Some(json!({ "title": title, "body": body, "severity": severity })),
        ),
        Cmd::Osc { cmd: OscCmd::Parse { raw } } => (
            "osc.parse",
            Some(json!({ "raw": decode_escapes(&raw) })),
        ),
        Cmd::Osc { cmd: OscCmd::Demo { code } } => (
            "osc.parse",
            Some(json!({ "raw": demo_payload(&code) })),
        ),
        Cmd::Term { cmd: TermCmd::List } => ("terminal.list", None),
        Cmd::Term { cmd: TermCmd::SendKeys { pane, keys } } => (
            "terminal.send_keys",
            Some(json!({ "pane": pane, "keys": keys })),
        ),
        Cmd::Term { cmd: TermCmd::Split { pane, dir } } => (
            "terminal.split",
            Some(json!({ "pane": pane, "dir": dir })),
        ),
        Cmd::History { .. } => unreachable!(),
    };

    let req = RpcRequest::new(1, method, params);
    let resp = call(&socket, req).await?;

    println!("{}", serde_json::to_string_pretty(&resp)?);
    if !resp.ok {
        std::process::exit(1);
    }
    Ok(())
}

fn render_history(result: &Value) {
    let empty = Vec::new();
    let rows = result
        .get("notifications")
        .and_then(|v| v.as_array())
        .unwrap_or(&empty);

    if rows.is_empty() {
        println!("(no notifications yet)");
        return;
    }

    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);

    println!("{:>6}  {:<10}  {:<10}  {}", "AGE", "SEVERITY", "SOURCE", "TITLE — BODY");
    println!("{}", "-".repeat(78));
    for row in rows {
        let ts = row.get("ts").and_then(|v| v.as_i64()).unwrap_or(0);
        let age = format_age(now - ts);
        let event = row.get("event").cloned().unwrap_or(Value::Null);
        let severity = event.get("severity").and_then(|v| v.as_str()).unwrap_or("?");
        let source = event.get("source").and_then(|v| v.as_str()).unwrap_or("?");
        let title = event.get("title").and_then(|v| v.as_str()).unwrap_or("");
        let body = event.get("body").and_then(|v| v.as_str()).unwrap_or("");
        let line = if body.is_empty() {
            title.to_string()
        } else {
            format!("{title} — {body}")
        };
        println!("{:>6}  {:<10}  {:<10}  {}", age, severity, source, truncate(&line, 50));
    }
}

fn format_age(secs: i64) -> String {
    if secs < 0 {
        return "now".into();
    }
    if secs < 60 {
        return format!("{secs}s");
    }
    if secs < 3600 {
        return format!("{}m", secs / 60);
    }
    if secs < 86400 {
        return format!("{}h", secs / 3600);
    }
    format!("{}d", secs / 86400)
}

/// Decode common backslash escape sequences (`\x1b`, `\a`, `\n`, `\\`) so users
/// can paste OSC payloads directly on the command line without shell heroics.
fn decode_escapes(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if c != '\\' {
            out.push(c);
            continue;
        }
        match chars.next() {
            Some('x') => {
                let h1 = chars.next();
                let h2 = chars.next();
                if let (Some(a), Some(b)) = (h1, h2) {
                    if let Ok(byte) = u8::from_str_radix(&format!("{a}{b}"), 16) {
                        out.push(byte as char);
                        continue;
                    }
                }
                out.push('\\');
                out.push('x');
                if let Some(a) = h1 { out.push(a); }
                if let Some(b) = h2 { out.push(b); }
            }
            Some('a') => out.push('\x07'),
            Some('n') => out.push('\n'),
            Some('t') => out.push('\t'),
            Some('r') => out.push('\r'),
            Some('e') | Some('E') => out.push('\x1b'),
            Some('\\') => out.push('\\'),
            Some(other) => {
                out.push('\\');
                out.push(other);
            }
            None => out.push('\\'),
        }
    }
    out
}

fn demo_payload(code: &str) -> String {
    match code {
        "9" => "\x1b]9;Hello from OSC 9 demo\x07".into(),
        "777" => "\x1b]777;notify;agent-bridge demo;OSC 777 round-trip\x07".into(),
        "99" => {
            "\x1b]99;{\"title\":\"OSC 99 demo\",\"body\":\"json payload + severity\",\"severity\":\"warning\"}\x07".into()
        }
        _ => format!("\x1b]9;unknown demo code: {code}\x07"),
    }
}

fn truncate(s: &str, max: usize) -> String {
    let chars: Vec<char> = s.chars().collect();
    if chars.len() <= max {
        s.to_string()
    } else {
        let head: String = chars.iter().take(max - 1).collect();
        format!("{head}…")
    }
}

async fn call(socket: &std::path::Path, req: RpcRequest) -> Result<RpcResponse> {
    let stream = UnixStream::connect(socket)
        .await
        .with_context(|| format!("connect {socket:?} (is the daemon running?)"))?;
    let (read_half, mut write_half) = stream.into_split();

    let mut bytes = serde_json::to_vec(&req)?;
    bytes.push(b'\n');
    write_half.write_all(&bytes).await?;
    write_half.flush().await?;
    write_half.shutdown().await.ok();

    let mut reader = BufReader::new(read_half).lines();
    let line = match reader.next_line().await? {
        Some(l) => l,
        None => bail!("daemon closed connection without responding"),
    };
    let resp: RpcResponse = serde_json::from_str(&line)?;
    let _: Option<Value> = None;
    Ok(resp)
}
