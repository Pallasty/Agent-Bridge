"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const vscode = require("vscode");

let timer = undefined;
let recentTasks = [];

function activate(context) {
  const writeNow = () => writeSnapshot().catch((err) => {
    console.error("agent-bridge ide snapshot write failed", err);
  });
  const schedule = () => {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(writeNow, 200);
  };

  context.subscriptions.push(
    vscode.commands.registerCommand("agentBridge.writeSnapshot", writeNow),
    vscode.window.onDidChangeActiveTextEditor(schedule),
    vscode.window.onDidChangeTextEditorSelection(schedule),
    vscode.workspace.onDidOpenTextDocument(schedule),
    vscode.workspace.onDidCloseTextDocument(schedule),
    vscode.workspace.onDidSaveTextDocument(schedule),
    vscode.workspace.onDidChangeTextDocument(schedule),
    vscode.languages.onDidChangeDiagnostics(schedule),
    vscode.tasks.onDidEndTaskProcess((event) => {
      recentTasks.unshift({
        name: event.execution.task.name,
        status: event.exitCode === 0 ? "succeeded" : "failed",
        exit_code: event.exitCode,
        ended_at: new Date().toISOString()
      });
      recentTasks = recentTasks.slice(0, 20);
      schedule();
    })
  );

  schedule();
}

function deactivate() {
  if (timer) {
    clearTimeout(timer);
  }
}

async function writeSnapshot() {
  const target = snapshotPath();
  if (!target) {
    return;
  }

  const root = workspaceRoot();
  const active = vscode.window.activeTextEditor;
  const snapshot = {
    schema_version: 1,
    ide: ideInfo(),
    workspace_root: root || null,
    active_file: active ? uriPath(active.document.uri) : null,
    selection: selectionInfo(active),
    open_files: openFiles(),
    diagnostics: diagnostics(root),
    tasks: recentTasks,
    updated_at: new Date().toISOString()
  };

  await atomicWriteJson(target, snapshot);
}

function snapshotPath() {
  const configured = vscode.workspace
    .getConfiguration("agentBridge")
    .get("snapshotPath", "")
    .trim();
  if (configured) {
    return configured;
  }

  const root = workspaceRoot();
  if (root) {
    return path.join(root, ".agent-bridge", "ide-snapshot.json");
  }

  if (process.env.AGENT_BRIDGE_IDE_SNAPSHOT) {
    return process.env.AGENT_BRIDGE_IDE_SNAPSHOT;
  }

  if (process.env.XDG_RUNTIME_DIR) {
    return path.join(process.env.XDG_RUNTIME_DIR, "agent-bridge", "ide-snapshot.json");
  }

  return path.join(os.homedir(), ".local", "share", "agent-bridge", "ide-snapshot.json");
}

function workspaceRoot() {
  const active = vscode.window.activeTextEditor;
  if (active) {
    const folder = vscode.workspace.getWorkspaceFolder(active.document.uri);
    if (folder) {
      return folder.uri.fsPath;
    }
  }
  const first = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  return first ? first.uri.fsPath : null;
}

function ideInfo() {
  return {
    name: vscode.env.appName,
    remote_name: vscode.env.remoteName || null,
    ui_kind: vscode.env.uiKind === vscode.UIKind.Web ? "web" : "desktop",
    version: vscode.version
  };
}

function selectionInfo(editor) {
  if (!editor) {
    return null;
  }
  const cfg = vscode.workspace.getConfiguration("agentBridge");
  const maxChars = clampNumber(cfg.get("maxSelectionChars", 20000), 0, 50000);
  const selection = editor.selection;
  const rawText = editor.document.getText(selection);
  const text = rawText.length > maxChars ? rawText.slice(0, maxChars) + "..." : rawText;

  return {
    file: uriPath(editor.document.uri),
    language: editor.document.languageId,
    range: rangeInfo(selection),
    text,
    text_chars: rawText.length,
    text_truncated: rawText.length > maxChars
  };
}

function openFiles() {
  return vscode.workspace.textDocuments
    .filter((doc) => doc.uri.scheme === "file")
    .map((doc) => ({
      path: doc.uri.fsPath,
      uri: doc.uri.toString(),
      language: doc.languageId,
      is_dirty: doc.isDirty,
      is_untitled: doc.isUntitled,
      is_active: vscode.window.activeTextEditor
        ? doc.uri.toString() === vscode.window.activeTextEditor.document.uri.toString()
        : false
    }));
}

function diagnostics(root) {
  const cfg = vscode.workspace.getConfiguration("agentBridge");
  const maxDiagnostics = clampNumber(cfg.get("maxDiagnostics", 500), 0, 5000);
  const items = [];

  for (const [uri, diags] of vscode.languages.getDiagnostics()) {
    const file = uriPath(uri);
    if (!file || (root && !isInside(root, file))) {
      continue;
    }
    for (const diag of diags) {
      items.push({
        file,
        uri: uri.toString(),
        severity: severityName(diag.severity),
        message: diag.message,
        source: diag.source || null,
        code: diagnosticCode(diag.code),
        range: rangeInfo(diag.range)
      });
      if (items.length >= maxDiagnostics) {
        return items;
      }
    }
  }

  return items;
}

function rangeInfo(range) {
  return {
    start: {
      line: range.start.line,
      character: range.start.character
    },
    end: {
      line: range.end.line,
      character: range.end.character
    }
  };
}

function severityName(severity) {
  switch (severity) {
    case vscode.DiagnosticSeverity.Error:
      return "error";
    case vscode.DiagnosticSeverity.Warning:
      return "warning";
    case vscode.DiagnosticSeverity.Information:
      return "info";
    case vscode.DiagnosticSeverity.Hint:
      return "hint";
    default:
      return "unknown";
  }
}

function diagnosticCode(code) {
  if (code === undefined || code === null) {
    return null;
  }
  if (typeof code === "object") {
    return code.value === undefined ? null : String(code.value);
  }
  return String(code);
}

function uriPath(uri) {
  return uri && uri.scheme === "file" ? uri.fsPath : null;
}

function isInside(root, file) {
  const relative = path.relative(root, file);
  return relative === "" || (!!relative && !relative.startsWith("..") && !path.isAbsolute(relative));
}

function clampNumber(value, min, max) {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return min;
  }
  return Math.max(min, Math.min(max, Math.floor(n)));
}

async function atomicWriteJson(target, snapshot) {
  await fs.promises.mkdir(path.dirname(target), { recursive: true });
  const tmp = `${target}.${process.pid}.tmp`;
  await fs.promises.writeFile(tmp, `${JSON.stringify(snapshot, null, 2)}\n`, "utf8");
  await fs.promises.rename(tmp, target);
}

module.exports = {
  activate,
  deactivate
};
