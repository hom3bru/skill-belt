// Live check (opt-in; Windows; needs the Codex desktop app): the codexApp fallback when no hook takes a follow-up. A throwaway mailbox and
// its own listener (codexApp only) run a real hand-off in the Codex app. Installed carrier-pigeon hooks read the live mailbox, never this one,
// so for this thread no hook can take anything: a follow-up sent mid-turn must wait (codex-app-deferred), be queued when the turn ends,
// and run as the thread's next turn. The live mailbox is untouched.
// Usage: node tests/live/codex-app-fallback.mjs [--minutes 6]
import path from 'node:path'; import fs from 'node:fs'; import os from 'node:os'; import crypto from 'node:crypto'; import {execFileSync} from 'node:child_process'; import {fileURLToPath} from 'node:url';
if (process.platform !== 'win32') { console.log(JSON.stringify({skipped: 'Windows only'})); process.exit(0); }
const SK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..'), url = f => new URL('file:///' + path.join(SK, f).replace(/\\/g, '/')).href;
const h = await import(url('host/carrier-pigeon-host.mjs'));
const cfgFile = path.join(os.homedir(), '.carrier-pigeon', 'host', 'config.json');
const bin = (fs.existsSync(cfgFile) && JSON.parse(fs.readFileSync(cfgFile, 'utf8')).codex?.bin) || 'codex';
const mi = process.argv.indexOf('--minutes'), limit = (mi > 0 ? Number(process.argv[mi + 1]) : 6) * 60000, sleep = ms => new Promise(r => setTimeout(r, ms));
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-fallback-')), work = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-fallback-work-'));
const env = {...process.env, CARRIER_PIGEON_HOME: root}; for (const k of ['CLAUDE_CODE_MESSAGING_SOCKET', 'CLAUDE_CODE_MESSAGING_TOKEN', 'CLAUDE_CODE_SESSION_ID']) delete env[k];
const cli = (...a) => JSON.parse(execFileSync(process.execPath, [path.join(SK, 'bin', 'carrier-pigeon.mjs'), ...a, '--json'], {env, encoding: 'utf8'}));
const evs = id => h.readReceipts(root, id).map(r => r.ev), until = async (f, ms = limit) => { const t = Date.now(); while (Date.now() - t < ms) { const v = f(); if (v) return v; await sleep(1000); } return null; };
const said = (file, word) => fs.readFileSync(file, 'utf8').split('\n').some(l => { try { const r = JSON.parse(l); return r.type === 'response_item' && r.payload?.role === 'assistant' && (r.payload.content || []).some(c => String(c?.text || '').includes(word)); } catch { return false; } });
cli('init'); const nonce = 'fallback-' + crypto.randomBytes(3).toString('hex'), report = {root, nonce};
const host = new h.Host({root, config: {watch: true, rescanMs: 5000, adapters: ['codexApp'], routes: {codex: ['codexApp'], claude: [], grok: [], cursor: [], user: []}, codex: {bin}, codexApp: {cwd: work, pollMs: 1000, pickupMs: 120000}}, adapters: {codexApp: h.codexAppAdapter()}});
await host.start();
try {
  const ho = cli('send', '--from', 'claude', '--to', 'codex', '--kind', 'handoff', '--subject', 'fallback live check: three slow steps', '--body',
    'Ask: run `Start-Sleep -Seconds 15; Get-Date -Format HH:mm:ss` three times, as three separate shell tool calls, then stop. This test mailbox is not connected to your carrier-pigeon tools: do not claim or reply. Context: carrier-pigeon live check (tests/live/codex-app-fallback.mjs). A follow-up may arrive later in this conversation; do what it asks.');
  const b = await until(() => h.appBindings(root).find(x => x.key === ho.thread && x.path && fs.existsSync(x.path)), 120000); report.thread = b?.id;
  if (!b) throw new Error('no app thread was opened');
  report.first_turn_started = !!(await until(() => evs(ho.id).includes('app-turn-started'), 120000));
  await until(() => h.turnRunning(b.path) && /custom_tool_call|function_call/.test(fs.readFileSync(b.path, 'utf8').split('\n').slice(-40).join('\n')), 120000);
  const fu = cli('send', '--from', 'claude', '--to', 'codex', '--thread', ho.thread, '--kind', 'ask', '--subject', 'fallback follow-up', '--body', `Ask: when you see this, answer in this conversation with exactly the word ${nonce}.`);
  report.deferred = !!(await until(() => fs.readFileSync(path.join(root, 'host', 'logs', 'host.jsonl'), 'utf8').includes('"codex-app-deferred","id":"' + fu.id), 30000));
  report.turn_ended = !!(await until(() => !h.turnRunning(b.path)));
  report.queued_after_turn = !!(await until(() => fs.readFileSync(path.join(root, 'host', 'logs', 'host.jsonl'), 'utf8').match(new RegExp(`"ev":"codex-app","id":"${fu.id}"[^\\n]*"follow_up":true`)), 60000));
  report.hooked = evs(fu.id).includes('app-hooked');
  report.followup_turn_started = !!(await until(() => evs(fu.id).includes('app-turn-started'), 180000));
  report.answered = !!(await until(() => said(b.path, nonce), 180000));
  report.verdict = report.deferred && report.turn_ended && report.queued_after_turn && !report.hooked && report.followup_turn_started && report.answered ? 'pass' : 'FAIL';
} catch (e) { report.error = e.message; report.verdict = 'FAIL'; } finally { await host.stop(); }
console.log(JSON.stringify(report, null, 1)); process.exit(report.verdict === 'pass' ? 0 : 1);
