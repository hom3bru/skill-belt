// Live check (opt-in; Windows only; needs the Codex desktop app): the codexApp mechanics against the real Codex and the real app, with no
// mailbox. A named thread with no turn is started with the user's own Codex config; one prompt goes on Codex's queue; codex://threads/<id>
// opens it and the app must run it; a second prompt is queued with no link and the app must run that too (a loaded thread's queue).
// Each prompt asks for one fresh nonce word; the run reads the thread's rollout for the user prompt and for the reply.
// Usage: node tests/live/codex-app.mjs [--minutes 4]
import path from 'node:path'; import fs from 'node:fs'; import os from 'node:os'; import crypto from 'node:crypto'; import {fileURLToPath} from 'node:url';
if (process.platform !== 'win32') { console.log(JSON.stringify({skipped: 'Windows only'})); process.exit(0); }
const SK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const h = await import(new URL('file:///' + path.join(SK, 'host', 'carrier-pigeon-host.mjs').replace(/\\/g, '/')).href);
const cfgFile = path.join(os.homedir(), '.carrier-pigeon', 'host', 'config.json');
const bin = (fs.existsSync(cfgFile) && JSON.parse(fs.readFileSync(cfgFile, 'utf8')).codex?.bin) || 'codex';
const mi = process.argv.indexOf('--minutes'), limit = (mi > 0 ? Number(process.argv[mi + 1]) : 4) * 60000;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const cwd = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-codex-app-'));
// A reply is an assistant message whose text is the nonce (Codex 0.166 rollouts record it as a response_item, not an agent_message event).
const said = r => r.type === 'response_item' && r.payload?.type === 'message' && r.payload.role === 'assistant' ? (r.payload.content || []).map(c => c?.text || '').join('') : null;
const replied = (file, nonce) => fs.readFileSync(file, 'utf8').split('\n').some(l => { try { return String(said(JSON.parse(l)) ?? '').trim().toLowerCase() === nonce; } catch { return false; } });
const wait = async (file, nonce) => { const t = Date.now(); while (Date.now() - t < limit) { if (fs.existsSync(file) && replied(file, nonce)) return Date.now() - t; await sleep(2000); } return null; };
const ask = n => `carrier-pigeon live check (codex-app.mjs). Reply with exactly the word ${n} and nothing else. Do not run any tools.`;
const nonce = () => 'cp' + crypto.randomBytes(4).toString('hex');
const report = {bin, cwd};
try {
  const t = await h.startAppThread(bin, cwd, 'carrier-pigeon live check (codex-app.mjs)');
  report.thread = t.id; report.rollout_after_start = !!(t.path && fs.existsSync(t.path));
  const n1 = nonce(); report.queue1 = (await h.codexQueue(bin, t.id, ask(n1))).trim();
  const argv = h.appOpenArgv({}, `codex://threads/${t.id}`); const {spawn} = await import('node:child_process');
  spawn(argv[0], argv.slice(1), {detached: true, stdio: 'ignore', windowsHide: true}).unref();
  report.first_ms = await wait(t.path, n1);
  const n2 = nonce(); report.queue2 = (await h.codexQueue(bin, t.id, ask(n2))).trim(); report.second_ms = await wait(t.path, n2);
  report.verdict = report.rollout_after_start && report.first_ms != null && report.second_ms != null ? 'pass' : 'FAIL';
} catch (e) { report.error = e.message; report.verdict = 'FAIL'; }
console.log(JSON.stringify(report, null, 1)); process.exit(report.verdict === 'pass' ? 0 : 1);
