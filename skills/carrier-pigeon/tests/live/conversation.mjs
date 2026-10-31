// Live check (opt-in; a few haiku wakes plus two Codex turns): a real multi-turn conversation between the listener's agents in a throwaway
// mailbox. grok asks Claude to coordinate with Codex in two steps; the second question ("add 100 to your previous answer") deliberately
// omits the number, so Codex can only answer from its memory of this conversation. Checks the reply wakes, per-thread sessions and the result.
// --mode wake (default): Claude must use send with wake_on_reply and end its turn, so each answer wakes its resumed per-thread session.
// --mode ask: Claude may use the blocking ask tool and stay in one run.
// Usage: node tests/live/conversation.mjs [--mode wake|ask] [--claude BIN] [--codex BIN] [--port 4512] [--keep]
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import {execFileSync} from 'node:child_process'; import {fileURLToPath} from 'node:url';
const SK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..'); const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const cfgFile = path.join(os.homedir(), '.carrier-pigeon', 'host', 'config.json'); const live = fs.existsSync(cfgFile) ? JSON.parse(fs.readFileSync(cfgFile, 'utf8')) : {};
const liveLog = path.join(os.homedir(), '.carrier-pigeon', 'log.jsonl'); const liveMtime = fs.existsSync(liveLog) ? fs.statSync(liveLog).mtimeMs : null;
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-conv-')); const env = {...process.env, CARRIER_PIGEON_HOME: root};
const cli = (...a) => JSON.parse(execFileSync('node', [path.join(SK, 'bin', 'carrier-pigeon.mjs'), ...a, '--json'], {env, encoding: 'utf8'}));
cli('install'); process.env.CARRIER_PIGEON_HOME = root;
const H = await import(new URL('file:///' + path.join(root, 'host', 'carrier-pigeon-host.mjs').replace(/\\/g, '/')).href);
const cfg = {rescanMs: 5000, adapters: ['claude', 'codex'], routes: {claude: ['claude'], codex: ['codex']},
  claude: {bin: arg('claude', live.claude?.bin || 'claude'), extraArgs: ['--model', 'haiku']}, codex: {bin: arg('codex', live.codex?.bin || 'codex'), port: Number(arg('port', 4512)), model: null, sandbox: 'busOnly', lean: true}};
const host = new H.Host({root, config: cfg, adapters: H.defaultAdapters({...H.DEFAULTS, ...cfg})}); await host.start();
const sleep = ms => new Promise(r => setTimeout(r, ms)); const t0 = Date.now(); const mode = arg('mode', 'wake');
const kick = cli('send', '--from', 'grok', '--to', 'claude', '--subject', 'two-step check with codex', '--body', [
  'Ask: coordinate with codex in two steps, in this thread, with wake_on_reply each time.',
  ...(mode === 'wake' ? ['Use the send tool (not ask) for each question to codex, then end your turn: the answer will wake you again in this conversation.'] : []),
  'Step 1: ask codex exactly: "What is 17 * 23? Reply with only the number."',
  'Step 2: when codex answers, ask codex exactly: "Add 100 to your previous answer. Reply with only the number." Do not include any number in that question.',
  'Step 3: when the second answer arrives, reply to this message with exactly: A=<first answer> B=<second answer>',
  'Constraints: read-only apart from the mailbox. Return: one line.'].join('\n'));
let fin = null; while (Date.now() - t0 < 900000) { fin = cli('inbox', 'grok', '--all-sessions').find(m => m.reply_to === kick.id); if (fin) break; await sleep(4000); }
// let every run finish (usage is logged when a run or turn ends) before stopping the host: Claude 3 runs in wake mode, Codex 2 turns
const uf = path.join(root, 'host/logs/usage.jsonl'); const rows = () => fs.existsSync(uf) ? fs.readFileSync(uf, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
for (const t1 = Date.now(); Date.now() - t1 < 180000; await sleep(3000)) { const u = rows(); if (u.filter(x => x.agent === 'codex').length >= 2 && u.filter(x => x.agent === 'claude').length >= (mode === 'wake' ? 3 : 1)) break; }
const usage = rows();
const th = cli('thread', kick.thread); const finBody = fin ? cli('read', fin.id).body.trim() : null;
const report = {elapsed_s: Math.round((Date.now() - t0) / 1000), final: finBody, correct: /A\s*=\s*391\b/.test(finBody || '') && /B\s*=\s*491\b/.test(finBody || ''),
  thread: th.map(m => `${m.from}${m.from_session ? '[' + m.from_session + ']' : ''} -> ${m.to}${m.to_session ? '[' + m.to_session + ']' : ''} ${m.kind}${m.wake_on_reply ? ' +wake_on_reply' : ''}: ${String(m.body).replace(/\s+/g, ' ').slice(0, 90)}`),
  all_in_one_thread: th.length >= 5, wakes: usage.map(u => ({agent: u.agent, msg: u.msg, thread: u.thread, resumed: u.resumed, input_total: u.input_total, cost_usd: u.cost_usd, latency_s: u.latency_ms ? Math.round(u.latency_ms / 1000) : null})),
  mode, codex_threads_used: [...new Set(usage.filter(u => u.agent === 'codex').map(u => u.thread))].length, claude_runs: usage.filter(u => u.agent === 'claude').length,
  claude_resumed_runs: usage.filter(u => u.agent === 'claude' && u.resumed).length, claude_cost_usd: +usage.filter(u => u.agent === 'claude').reduce((s, u) => s + (u.cost_usd || 0), 0).toFixed(4),
  no_wake: th.map(m => H.readReceipts(root, m.id).filter(r => r.ev === 'no-wake').map(r => m.kind + ':' + r.reason)).flat(),
  errors: fs.readFileSync(path.join(root, 'host/logs/host.jsonl'), 'utf8').trim().split('\n').map(JSON.parse).filter(e => /error|failed/.test(e.ev) && !/not ready/.test(e.err || '')).map(e => e.ev + ' ' + (e.err || e.why || '').slice(0, 100)),
  live_mailbox_untouched: liveMtime === null || fs.statSync(liveLog).mtimeMs === liveMtime};
await host.stop(); await sleep(2000); console.log(JSON.stringify(report, null, 1));
if (process.argv.includes('--keep')) console.log('kept for inspection: ' + root); else try { fs.rmSync(root, {recursive: true, force: true}); } catch { console.log('remove later: ' + root); }
process.exit(report.correct ? 0 : 1);
