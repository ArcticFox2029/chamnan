// chamnan for VS Code — a distribution channel, not a second implementation.
//
// 🎯 [2026-09-17, the owner's framing] "it should cover all the work the same as it does now, just
// add a channel that makes installing easier." So this file spawns `bin/chamnan-*` and renders what
// comes back. It does not parse MAP.md, does not build the block, does not touch the redactor.
//
// **The rule that keeps it from forking the product**: every action here is a chamnan command
// invocation. If a capability ever exists only when this extension is installed, chamnan has become
// two products and the CLI becomes the neglected one. `run()` below is the only way anything
// executes, and a check in the suite asserts there is no second path.
//
// Nothing here reaches the network. No telemetry, no update check, no marketplace fetch at runtime.
// R25 #10 measured that "local mode" in several AI coding tools was a preference rather than a
// policy, with telemetry still firing; that must not become true here.

const vscode = require('vscode');
const cp = require('child_process');
const path = require('path');

// Activation must not spawn anything. VS Code's guidance is a 500 ms budget for everything the user
// has installed, and this machine already carries eight extensions; a quarter of it is our share.
// The first chamnan process runs when a command is invoked, never before.
function activate(context) {
  const reg = (id, fn) => context.subscriptions.push(vscode.commands.registerCommand(id, fn));
  reg('chamnan.status', () => show('chamnan-setup', []));
  reg('chamnan.setup', () => show('chamnan-setup', ['--dry-run']));
  reg('chamnan.context', () => show('chamnan-context', []));
}

// 🐛 [2026-09-17, caught by installing the real VSIX rather than trusting that packaging it was
// the end] This returned `path.join(__dirname, '..')`, which inside a packaged extension is
// `~/.vscode/extensions` — a directory with no `bin/` in it. Every command would have failed on a
// real install while passing every headless test, because in the checkout that path happens to be
// the package root.
//
// The fix is deliberately NOT "bundle bin/ and lib/ into the VSIX". That would put a second copy of
// chamnan on the machine, versioned by the marketplace rather than by the checkout, and a second
// copy drifting from the first is the exact confusion that cost an hour today: thirteen cached
// versions and a stale git clone, none of which was what ran.
//
// So: look for a real checkout, and when there is none, say so with the setting that fixes it.
function checkout() {
  const configured = vscode.workspace.getConfiguration('chamnan').get('checkoutPath');
  if (configured && configured.length) return configured;

  const fs = require('fs');
  const isCheckout = (d) => {
    try { return fs.statSync(path.join(d, 'bin', 'chamnan-setup')).isFile(); }
    catch (e) { return false; }
  };
  // Beside the extension covers running from source; the workspace covers the common case of
  // developing chamnan itself or vendoring it.
  for (const c of [path.join(__dirname, '..'), workspaceRoot(),
                   path.join(workspaceRoot(), 'Work-Mode', 'chamnan')]) {
    if (isCheckout(c)) return c;
  }
  return null;
}

function workspaceRoot() {
  const f = vscode.workspace.workspaceFolders;
  return f && f.length ? f[0].uri.fsPath : process.cwd();
}

// The single execution path. Everything this extension does goes through here, so "what can this
// run" has one answer that a reader can check in one place.
function run(command, args) {
  const py = vscode.workspace.getConfiguration('chamnan').get('pythonPath') || 'python3';
  const root = checkout();
  if (!root) {
    return Promise.resolve({ code: 2, stdout: '',
      stderr: 'No chamnan checkout found. Clone https://github.com/ArcticFox2029/chamnan and set '
            + '`chamnan.checkoutPath` to it.\n\nThis extension deliberately does not bundle its '
            + 'own copy: a second copy on the machine drifts from the one you actually run.' });
  }
  const bin = path.join(root, 'bin', command);
  return new Promise((resolve) => {
    cp.execFile(py, [bin, ...args], { cwd: workspaceRoot(), timeout: 120000 },
      (err, stdout, stderr) => resolve({ code: err ? (err.code ?? 1) : 0, stdout, stderr }));
  });
}

async function show(command, args) {
  const r = await run(command, args);
  const ch = vscode.window.createOutputChannel('chamnan');
  ch.clear();
  ch.appendLine(`$ ${command} ${args.join(' ')}`.trim());
  ch.appendLine('');
  ch.append(r.stdout || '');
  if (r.stderr) { ch.appendLine(''); ch.append(r.stderr); }
  ch.show(true);
}

function deactivate() {}

module.exports = { activate, deactivate, run, checkout };
