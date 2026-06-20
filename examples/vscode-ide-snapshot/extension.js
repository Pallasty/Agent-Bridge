"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const vscode = require("vscode");

let timer = undefined;
let commandTimer = undefined;
let recentTasks = [];
const processedCommandIds = new Set();
let processingCommands = false;
let refreshTimer = undefined;
let lastStableJson = undefined;

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
  const processCommandsNow = () => processCommandQueue().catch((err) => {
    console.error("agent-bridge ide command processing failed", err);
  });

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

  if (vscode.window.tabGroups) {
    context.subscriptions.push(
      vscode.window.tabGroups.onDidChangeTabs(schedule),
      vscode.window.tabGroups.onDidChangeTabGroups(schedule)
    );
  }

  loadProcessedCommandIds().finally(() => {
    processCommandsNow();
    commandTimer = setInterval(processCommandsNow, 500);
  });
  context.subscriptions.push(new vscode.Disposable(() => {
    if (commandTimer) {
      clearInterval(commandTimer);
    }
  }));

  const refreshMs = clampNumber(
    vscode.workspace.getConfiguration("agentBridge").get("refreshIntervalMs", 10000),
    0,
    600000
  );
  if (refreshMs > 0) {
    refreshTimer = setInterval(writeNow, refreshMs);
    context.subscriptions.push(new vscode.Disposable(() => {
      if (refreshTimer) {
        clearInterval(refreshTimer);
      }
    }));
  }

  schedule();
}

function deactivate() {
  if (timer) {
    clearTimeout(timer);
  }
  if (commandTimer) {
    clearInterval(commandTimer);
  }
  if (refreshTimer) {
    clearInterval(refreshTimer);
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

  // Change-gate: periodic refreshes keep the snapshot mtime fresh so the
  // ide_snapshot MCP tool does not flag it stale during agent-panel focus,
  // when no editor events fire. If the meaningful content is unchanged, just
  // bump the mtime instead of rewriting the full payload on every tick.
  const stable = JSON.stringify({ ...snapshot, updated_at: undefined });
  if (stable === lastStableJson) {
    try {
      const now = new Date();
      await fs.promises.utimes(target, now, now);
      return target;
    } catch (err) {
      if (!err || err.code !== "ENOENT") {
        throw err;
      }
      // File vanished — fall through to a full write.
    }
  }
  lastStableJson = stable;
  await atomicWriteJson(target, snapshot);
  return target;
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

function bridgeDir() {
  const configured = vscode.workspace
    .getConfiguration("agentBridge")
    .get("commandDir", "")
    .trim();
  if (configured) {
    return configured;
  }
  return path.dirname(snapshotPath());
}

function commandQueuePath() {
  return path.join(bridgeDir(), "ide-commands.jsonl");
}

function commandResponsePath() {
  return path.join(bridgeDir(), "ide-responses.jsonl");
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
  const activeUri = vscode.window.activeTextEditor
    ? vscode.window.activeTextEditor.document.uri.toString()
    : null;

  // Index loaded documents so we can enrich tabs with language/dirty state.
  const docByUri = new Map();
  for (const doc of vscode.workspace.textDocuments) {
    if (doc.uri.scheme === "file") {
      docByUri.set(doc.uri.toString(), doc);
    }
  }

  const seen = new Set();
  const items = [];

  // Primary source: real editor tabs. Survives agent-panel focus, where
  // vscode.workspace.textDocuments can be empty even with files open.
  const groups = (vscode.window.tabGroups && vscode.window.tabGroups.all) || [];
  for (const group of groups) {
    for (const tab of group.tabs) {
      const input = tab.input;
      const uri = input && input.uri ? input.uri : null; // TabInputText
      if (!uri || uri.scheme !== "file") {
        continue;
      }
      const key = uri.toString();
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      const doc = docByUri.get(key);
      items.push({
        path: uri.fsPath,
        uri: key,
        language: doc ? doc.languageId : null,
        is_dirty: doc ? doc.isDirty : !!tab.isDirty,
        is_untitled: false,
        is_active: key === activeUri
      });
    }
  }

  // Union in any loaded documents not surfaced as tabs.
  for (const [key, doc] of docByUri) {
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    items.push({
      path: doc.uri.fsPath,
      uri: key,
      language: doc.languageId,
      is_dirty: doc.isDirty,
      is_untitled: doc.isUntitled,
      is_active: key === activeUri
    });
  }

  return items;
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

async function loadProcessedCommandIds() {
  const target = commandResponsePath();
  let raw;
  try {
    raw = await fs.promises.readFile(target, "utf8");
  } catch (err) {
    if (err && err.code === "ENOENT") {
      return;
    }
    throw err;
  }
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }
    try {
      const response = JSON.parse(trimmed);
      if (response && typeof response.id === "string") {
        processedCommandIds.add(response.id);
      }
    } catch (_) {
      // Ignore malformed historical lines; the bridge only appends JSON.
    }
  }
}

async function processCommandQueue() {
  if (processingCommands) {
    return;
  }
  processingCommands = true;
  try {
    const target = commandQueuePath();
    let raw;
    try {
      raw = await fs.promises.readFile(target, "utf8");
    } catch (err) {
      if (err && err.code === "ENOENT") {
        return;
      }
      throw err;
    }

    for (const line of raw.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }
      let request;
      try {
        request = JSON.parse(trimmed);
      } catch (err) {
        continue;
      }
      if (!request || typeof request.id !== "string" || processedCommandIds.has(request.id)) {
        continue;
      }
      processedCommandIds.add(request.id);
      const response = await executeCommandRequest(request);
      await appendJsonl(commandResponsePath(), response);
    }
  } finally {
    processingCommands = false;
  }
}

async function executeCommandRequest(request) {
  const startedAt = new Date().toISOString();
  try {
    const result = await runIdeCommand(request.command, request.args || {});
    return {
      schema_version: 1,
      id: request.id,
      command: request.command,
      ok: true,
      started_at: startedAt,
      completed_at: new Date().toISOString(),
      result
    };
  } catch (err) {
    return {
      schema_version: 1,
      id: request.id,
      command: request.command,
      ok: false,
      started_at: startedAt,
      completed_at: new Date().toISOString(),
      error: err && err.message ? err.message : String(err)
    };
  }
}

async function runIdeCommand(command, args) {
  switch (command) {
    case "open_file":
      return openFile(args);
    case "reveal_range":
      return openFile(args);
    case "run_task":
      return runTask(args);
    case "write_snapshot": {
      const target = await writeSnapshot();
      return { snapshot_path: target };
    }
    default:
      throw new Error(`unsupported command: ${command}`);
  }
}

async function openFile(args) {
  const filePath = requiredString(args.path, "path");
  const document = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
  const editor = await vscode.window.showTextDocument(document, {
    preview: !!args.preview,
    preserveFocus: !!args.preserve_focus,
    viewColumn: viewColumn(args.view_column)
  });
  const range = rangeFromInfo(args.range);
  if (range) {
    editor.selection = new vscode.Selection(range.start, range.end);
    editor.revealRange(range, vscode.TextEditorRevealType.InCenterIfOutsideViewport);
  }
  return {
    file: filePath,
    language: document.languageId,
    revealed_range: range ? rangeInfo(range) : null
  };
}

async function runTask(args) {
  const name = requiredString(args.name, "name");
  const tasks = await vscode.tasks.fetchTasks();
  const task = tasks.find((candidate) => candidate.name === name);
  if (!task) {
    throw new Error(`task not found: ${name}`);
  }
  const execution = await vscode.tasks.executeTask(task);
  return {
    name: execution.task.name,
    source: execution.task.source || null
  };
}

function requiredString(value, name) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function rangeFromInfo(value) {
  if (!value || typeof value !== "object" || !value.start || !value.end) {
    return null;
  }
  return new vscode.Range(positionFromInfo(value.start), positionFromInfo(value.end));
}

function positionFromInfo(value) {
  const line = clampNumber(value.line, 0, Number.MAX_SAFE_INTEGER);
  const character = clampNumber(value.character, 0, Number.MAX_SAFE_INTEGER);
  return new vscode.Position(line, character);
}

function viewColumn(value) {
  if (value === undefined || value === null) {
    return undefined;
  }
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : undefined;
}

async function appendJsonl(target, value) {
  await fs.promises.mkdir(path.dirname(target), { recursive: true });
  await fs.promises.appendFile(target, `${JSON.stringify(value)}\n`, "utf8");
}

module.exports = {
  activate,
  deactivate
};
