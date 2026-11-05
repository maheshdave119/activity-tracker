const vscode = require('vscode');
const http = require('http');
const path = require('path');
const os = require('os');

let output;
let lastDocChange = new Map();
let lastSelection = new Map();
let heartbeat;
let disposables = [];

function send(category, summary, details = {}, workspace = null) {
  const activeDoc = vscode.window.activeTextEditor?.document;
  const activeFolder = activeDoc && activeDoc.uri.scheme === 'file' ? workspaceFor(activeDoc.uri) : null;
  const folder = workspace || activeFolder || null;
  const payload = JSON.stringify({
    ts: new Date().toISOString(),
    workspace: folder,
    source: 'cursor_extension',
    category,
    summary,
    details: { ...details, collector: 'cursor-local-activity-collector', hostname: os.hostname() }
  });
  const req = http.request({
    hostname: '127.0.0.1', port: 8766, path: '/api/ingest', method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) }, timeout: 2500
  }, res => res.resume());
  req.on('error', () => {});
  req.on('timeout', () => req.destroy());
  req.write(payload); req.end();
}
function basename(uri) { return uri ? path.basename(uri.fsPath || uri.path || String(uri)) : 'Untitled'; }
function workspaceFor(uri) { const f = uri ? vscode.workspace.getWorkspaceFolder(uri) : null; return f ? f.uri.fsPath : null; }
function activate(context) {
  output = vscode.window.createOutputChannel('Cursor Activity Tracker');
  context.subscriptions.push(output);
  const folders = vscode.workspace.workspaceFolders || [];
  folders.forEach(f => send('Workspace', `Cursor workspace opened: ${path.basename(f.uri.fsPath)}`, { event: 'workspace_open', workspace_uri: f.uri.toString() }, f.uri.fsPath));
  send('Session', 'Cursor extension collector activated', { event: 'extension_activated', workspace_count: folders.length });

  context.subscriptions.push(vscode.workspace.onDidChangeWorkspaceFolders(e => {
    e.added.forEach(f => send('Workspace', `Workspace added: ${path.basename(f.uri.fsPath)}`, { event: 'workspace_added' }, f.uri.fsPath));
    e.removed.forEach(f => send('Workspace', `Workspace removed: ${path.basename(f.uri.fsPath)}`, { event: 'workspace_removed' }, f.uri.fsPath));
  }));

  context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(editor => {
    if (!editor) return;
    const doc = editor.document;
    const file = basename(doc.uri);
    const isSearch = doc.uri.scheme === 'vscode-search' || /search-editor/i.test(doc.uri.scheme);
    const cat = isSearch ? 'Search & Research' : 'Code Navigation';
    send(cat, isSearch ? 'Search editor opened or activated' : `Opened editor: ${file}`, {
      event: isSearch ? 'search_editor_activated' : 'editor_activated',
      file, language: doc.languageId, scheme: doc.uri.scheme, dirty: doc.isDirty
    }, doc.uri.scheme === 'file' ? workspaceFor(doc.uri) : null);
  }));

  context.subscriptions.push(vscode.workspace.onDidOpenTextDocument(doc => {
    if (doc.uri.scheme === 'vscode-search') {
      send('Search & Research', 'Search results/document opened', { event: 'search_document_opened', scheme: doc.uri.scheme });
    } else if (doc.uri.scheme === 'file') {
      send('Code Navigation', `Document opened: ${basename(doc.uri)}`, { event: 'document_opened', language: doc.languageId }, workspaceFor(doc.uri));
    }
  }));

  context.subscriptions.push(vscode.workspace.onDidSaveTextDocument(doc => {
    if (doc.uri.scheme !== 'file') return;
    send('Development', `Saved ${basename(doc.uri)}`, { event: 'document_saved', language: doc.languageId, file: doc.uri.fsPath }, workspaceFor(doc.uri));
  }));

  context.subscriptions.push(vscode.workspace.onDidChangeTextDocument(e => {
    const doc = e.document;
    if (doc.uri.scheme === 'vscode-search') {
      const key = doc.uri.toString(); const now = Date.now();
      if (now - (lastDocChange.get(key) || 0) > 15000) {
        lastDocChange.set(key, now);
        send('Search & Research', 'Search editor query/results changed', { event: 'search_editor_changed' });
      }
      return;
    }
    if (doc.uri.scheme !== 'file' || e.contentChanges.length === 0) return;
    const key = doc.uri.fsPath; const now = Date.now();
    if (now - (lastDocChange.get(key) || 0) < 20000) return;
    lastDocChange.set(key, now);
    send('Development', `Edited ${basename(doc.uri)}`, { event: 'document_edited', language: doc.languageId, change_count: e.contentChanges.length, file: doc.uri.fsPath }, workspaceFor(doc.uri));
  }));

  context.subscriptions.push(vscode.window.onDidChangeTextEditorSelection(e => {
    const doc = e.textEditor.document;
    if (doc.uri.scheme !== 'file') return;
    const key = doc.uri.fsPath; const now = Date.now();
    if (now - (lastSelection.get(key) || 0) < 60000) return;
    lastSelection.set(key, now);
    send('Code Navigation', `Worked in ${basename(doc.uri)}`, { event: 'editor_selection_activity', language: doc.languageId }, workspaceFor(doc.uri));
  }));

  context.subscriptions.push(vscode.window.onDidChangeActiveTerminal(term => {
    if (term) send('Terminal', `Terminal focused: ${term.name}`, { event: 'terminal_activated', terminal_name: term.name });
  }));
  context.subscriptions.push(vscode.window.onDidOpenTerminal(term => {
    send('Terminal', `Terminal opened: ${term.name}`, { event: 'terminal_opened', terminal_name: term.name });
  }));

  context.subscriptions.push(vscode.workspace.onDidCreateFiles(e => e.files.forEach(u => send('Development', `Created ${basename(u)}`, { event: 'file_created', file: u.fsPath }, workspaceFor(u) || path.dirname(u.fsPath)))));
  context.subscriptions.push(vscode.workspace.onDidDeleteFiles(e => e.files.forEach(u => send('Development', `Deleted ${basename(u)}`, { event: 'file_deleted', file: u.fsPath }, workspaceFor(u) || path.dirname(u.fsPath)))));
  context.subscriptions.push(vscode.workspace.onDidRenameFiles(e => e.files.forEach(f => send('Development', `Renamed ${basename(f.oldUri)} to ${basename(f.newUri)}`, { event: 'file_renamed', old_file: f.oldUri.fsPath, new_file: f.newUri.fsPath }, workspaceFor(f.newUri) || path.dirname(f.newUri.fsPath)))));

  heartbeat = setInterval(() => {
    const active = vscode.window.activeTextEditor;
    const ws = active?.document.uri.scheme === 'file' ? workspaceFor(active.document.uri) : vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    send('Session', 'Cursor is active in workspace', { event: 'cursor_heartbeat', active_file: active ? basename(active.document.uri) : null }, ws);
  }, 120000);
  context.subscriptions.push({ dispose: () => clearInterval(heartbeat) });
  output.appendLine('Collector active. Only metadata is sent to 127.0.0.1:8766; file contents and terminal commands are not collected.');
}
function deactivate() { if (heartbeat) clearInterval(heartbeat); }
module.exports = { activate, deactivate };
