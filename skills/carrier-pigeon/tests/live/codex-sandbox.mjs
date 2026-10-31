// Live check (opt-in; Windows/macOS/Linux): does Codex's workspace-write sandbox, the mode the listener's Codex runs in, block writes
// outside the mailbox? Runs `codex sandbox` directly (no model, no tokens): one write inside a throwaway mailbox (positive control),
// one into a fresh folder in the home directory, one into the OS temp dir. Every file and folder it makes is removed afterwards.
// Usage: node tests/live/codex-sandbox.mjs [codex-bin]   (default: host/config.json codex.bin of ~/.carrier-pigeon, else "codex")
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import {spawnSync} from 'node:child_process';
const cfgFile = path.join(os.homedir(), '.carrier-pigeon', 'host', 'config.json');
const bin = process.argv[2] || (fs.existsSync(cfgFile) && JSON.parse(fs.readFileSync(cfgFile, 'utf8')).codex?.bin) || 'codex';
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-sbx-root-')); const home = fs.mkdtempSync(path.join(os.homedir(), 'cp-sbx-home-'));
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-sbx-tmp-')); const win = process.platform === 'win32';
// node writes the file, with the path as its own argv entry: no shell quoting to get wrong between codex and cmd/sh
const tryWrite = file => { const cmd = [process.execPath, '-e', 'require("fs").writeFileSync(process.argv[1], "sandbox-probe")', file];
  // `:workspace` is Codex's built-in workspace-write profile; -C makes the mailbox the workspace, as the listener's turns do
  const r = spawnSync(bin, ['sandbox', '-P', ':workspace', '-C', root, '--', ...cmd], {encoding: 'utf8', timeout: 120000, windowsHide: true});
  return {exit: r.status, created: fs.existsSync(file), err: (r.stderr || r.error?.message || '').trim().split(/\r?\n/).slice(-1)[0]?.slice(0, 160) || ''}; };
const res = {codex: bin, inside_mailbox: tryWrite(path.join(root, 'inside.txt')), home_folder: tryWrite(path.join(home, 'outside.txt')), os_temp: tryWrite(path.join(tmp, 'outside.txt'))};
res.verdict = !res.inside_mailbox.created ? 'inconclusive: the positive control failed (sandbox did not run the command)'
  : res.home_folder.created ? 'FAIL: a write outside the mailbox (home folder) succeeded' : 'pass: writes are confined (home folder blocked)';
res.note = res.os_temp.created ? 'the OS temp dir is writable inside the sandbox (workspace-write allows temp by design)' : 'the OS temp dir was blocked too';
for (const d of [root, home, tmp]) fs.rmSync(d, {recursive: true, force: true});
console.log(JSON.stringify(res, null, 1)); process.exit(res.verdict.startsWith('FAIL') ? 1 : 0);
