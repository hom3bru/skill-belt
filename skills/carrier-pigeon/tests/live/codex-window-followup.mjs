// Live check (opt-in; Windows; opens one Codex terminal window): a follow-up reaches a hand-off window. A throwaway mailbox and its own
// listener (codexWindow for hand-offs, codexApp with no hand-off kinds for follow-ups) open a real window; once its first turn ends, a
// follow-up must be found a thread (from the window's rollout), queued into it, and run by the idle window. The live mailbox is untouched.
// Usage: node tests/live/codex-window-followup.mjs [--minutes 6]
import path from 'node:path'; import fs from 'node:fs'; import os from 'node:os'; import crypto from 'node:crypto'; import {execFileSync} from 'node:child_process'; import {fileURLToPath} from 'node:url';
if (process.platform !== 'win32') { console.log(JSON.stringify({skipped: 'Windows only'})); process.exit(0); }
const SK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..'), h = await import(new URL('file:///' + path.join(SK, 'host', 'carrier-pigeon-host.mjs').replace(/\\/g, '/')).href);
const cfgFile = path.join(os.homedir(), '.carrier-pigeon', 'host', 'config.json'), live = fs.existsSync(cfgFile) ? JSON.parse(fs.readFileSync(cfgFile, 'utf8')) : {};
const bin = live.codex?.bin || 'codex', mi = process.argv.indexOf('--minutes'), limit = (mi > 0 ? Number(process.argv[mi + 1]) : 6) * 60000, sleep = ms => new Promise(r => setTimeout(r, ms));
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-window-')); const env = {...process.env, CARRIER_PIGEON_HOME: root};
for (const k of ['CLAUDE_CODE_MESSAGING_SOCKET', 'CLAUDE_CODE_MESSAGING_TOKEN', 'CLAUDE_CODE_SESSION_ID']) delete env[k];
const cli = (...a) => JSON.parse(execFileSync(process.execPath, [path.join(SK, 'bin', 'carrier-pigeon.mjs'), ...a, '--json'], {env, encoding: 'utf8'}));
const until = async (f, ms = limit) => { const t = Date.now(); while (Date.now() - t < ms) { const v = f(); if (v) return v; await sleep(1500); } return null; };
const said = (file, word) => fs.readFileSync(file, 'utf8').split('\n').some(l => { try { const r = JSON.parse(l); return r.type === 'response_item' && r.payload?.role === 'assistant' && (r.payload.content || []).some(c => String(c?.text || '').includes(word)); } catch { return false; } });
cli('init'); const w1 = 'first-' + crypto.randomBytes(3).toString('hex'), w2 = 'second-' + crypto.randomBytes(3).toString('hex'), report = {root, w1, w2};
const host = new h.Host({root, config: {watch: true, rescanMs: 5000, adapters: ['codexApp', 'codexWindow'], routes: {codex: ['codexApp', 'codexWindow'], claude: [], grok: [], cursor: [], user: []},
  codex: {bin}, codexWindow: {enabled: true, kinds: ['handoff'], args: ['--no-daemon']}, codexApp: {kinds: [], pollMs: 1000, pickupMs: 120000}}, adapters: {codexApp: h.codexAppAdapter(), codexWindow: h.codexWindowAdapter()}});
await host.start();
try {
  const ho = cli('send', '--from', 'claude', '--to', 'codex', '--kind', 'handoff', '--subject', 'window live check', '--body',
    `Ask: answer in this conversation with exactly the word ${w1}, and nothing else. This test mailbox is not connected to your carrier-pigeon tools: do not claim or reply. Context: carrier-pigeon live check (tests/live/codex-window-followup.mjs). A follow-up may arrive later in this conversation; do what it asks.`);
  report.window_opened = !!(await until(() => h.readReceipts(root, ho.id).some(r => r.ev === 'notified:codexWindow'), 60000));
  const f = {id: 'probe', from: 'claude', to: 'codex', kind: 'ask', thread: ho.thread}; const cfg = host.cfg;
  // A new window can wait minutes before its first frame: Codex fetches its model list first (one fetch timed out, and the retry came 4.5 min later).
  const b = await until(() => h.appThreadFor(root, f, cfg), limit); report.thread_found = b?.id || null; if (!b) throw new Error('the window\'s thread was not found');
  report.first_answered = !!(await until(() => said(b.path, w1) && !h.turnRunning(b.path), 240000)); await sleep(3000);
  const fu = cli('send', '--from', 'claude', '--to', 'codex', '--thread', ho.thread, '--kind', 'ask', '--subject', 'window follow-up', '--body', `Ask: answer in this conversation with exactly the word ${w2}, and nothing else.`);
  report.queued = !!(await until(() => h.readReceipts(root, fu.id).some(r => r.ev === 'notified:codexApp'), 60000));
  report.started = !!(await until(() => h.readReceipts(root, fu.id).some(r => r.ev === 'app-turn-started'), 120000));
  report.answered = !!(await until(() => said(b.path, w2), 120000));
  report.verdict = report.window_opened && report.thread_found && report.first_answered && report.queued && report.started && report.answered ? 'pass' : 'FAIL';
} catch (e) { report.error = e.message; report.verdict = 'FAIL'; } finally { await host.stop(); }
console.log(JSON.stringify(report, null, 1)); process.exit(report.verdict === 'pass' ? 0 : 1);
