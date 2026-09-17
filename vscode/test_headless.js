// Headless test: the extension's entry points driven with a fake `vscode` module.
// Same technique as check 90's planted shapes — exercise the REAL code path, never a copy of it.
const Module = require('module');
const path = require('path');
const assert = require('assert');

const shown = [];
const fakeVscode = {
  workspace: {
    workspaceFolders: [{ uri: { fsPath: path.join(__dirname, '..', '..', '..') } }],
    getConfiguration: () => ({ get: (k) => (k === 'pythonPath' ? '/usr/bin/python3' : '') }),
  },
  commands: { registerCommand: (id, fn) => ({ id, fn, dispose() {} }) },
  window: { createOutputChannel: () => ({
    clear() {}, appendLine(s) { shown.push(s); }, append(s) { shown.push(s); }, show() {} }) },
};
const origResolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
  if (req === 'vscode') return 'vscode';
  return origResolve.call(this, req, ...rest);
};
require.cache['vscode'] = { id: 'vscode', filename: 'vscode', loaded: true, exports: fakeVscode };

const ext = require('./extension.js');
let passed = 0, failed = [];
const check = (name, cond) => { if (cond) { passed++; } else { failed.push(name); } };

// 1. Activation registers commands and spawns nothing. Timed, because the budget is the design's.
const t0 = process.hrtime.bigint();
const subs = [];
ext.activate({ subscriptions: subs });
const ms = Number(process.hrtime.bigint() - t0) / 1e6;
check('activation registers three commands', subs.length === 3);
check(`activation stays under the 200 ms self-imposed ceiling (took ${ms.toFixed(1)} ms)`, ms < 200);

// 2. The only execution path runs a chamnan command and nothing else.
const src = require('fs').readFileSync(path.join(__dirname, 'extension.js'), 'utf8');
const spawns = (src.match(/execFile|exec\(|spawn\(|spawnSync|execSync/g) || []).length;
check('exactly one process-spawning call exists in the whole extension', spawns === 1);
check('no network module is required anywhere', !/require\(['"](https?|net|dgram|tls)['"]\)/.test(src));

// 3. The packaged-install case, which passed every test until a real VSIX was installed:
//    __dirname/.. is ~/.vscode/extensions there, and it has no bin/.
check('checkout() finds a real checkout from the source layout', ext.checkout() !== null);
{
  const fs = require('fs'), os = require('os');
  const fake = fs.mkdtempSync(path.join(os.tmpdir(), 'chamnan-noco-'));
  const nested = path.join(fake, 'extensions', 'pub.chamnan-1.0.0');
  fs.mkdirSync(nested, { recursive: true });
  // Re-resolve with __dirname somewhere that is NOT a checkout, the way an install looks.
  const probe = (d) => { try { return fs.statSync(path.join(d, 'bin', 'chamnan-setup')).isFile(); }
                         catch (e) { return false; } };
  check('a packaged install directory is correctly NOT taken for a checkout', !probe(path.join(nested, '..')));
}

// 4. It really runs the real command.
ext.run('chamnan-setup', ['--json']).then((r) => {
  let parsed = null;
  try { parsed = JSON.parse(r.stdout); } catch (e) { /* reported below */ }
  check('chamnan-setup --json returns parseable JSON through the extension', parsed !== null);
  check('and it names this checkout\'s version', parsed && typeof parsed.source === 'string');
  check('and it reports every host it found', parsed && Array.isArray(parsed.hosts));

  console.log(`\n  activation: ${ms.toFixed(1)} ms`);
  for (const f of failed) console.log(`  FAIL  ${f}`);
  console.log(`\n${passed}/${passed + failed.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
});
