// Live check (opt-in; costs real model calls): the whole listener on a throwaway mailbox, never the live one. It installs this skill's
// code there, starts the real host with real Claude (haiku) and a lean Codex app-server on a spare port, sends each agent an ask that
// needs a read-only command, and waits for their replies and usage rows.
// Usage: node tests/live/e2e.mjs [--claude BIN] [--codex BIN] [--port 4511] [--only claude|codex] [--keep]
// Bins default to ~/.carrier-pigeon/host/config.json, else "claude" / "codex" on PATH.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import {execFileSync} from 'node:child_process'; import {fileURLToPath} from 'node:url';
const SK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..'); const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const cfgFile = path.join(os.homedir(), '.carrier-pigeon', 'host', 'config.json'); const live = fs.existsSync(cfgFile) ? JSON.parse(fs.readFileSync(cfgFile, 'utf8')) : {};
const who = arg('only') ? [arg('only')] : ['codex', 'claude'];
const liveLog = path.join(os.homedir(), '.carrier-pigeon', 'log.jsonl'); const liveMtime = fs.existsSync(liveLog) ? fs.statSync(liveLog).mtimeMs : null;
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-e2e-')); const env = {...process.env, CARRIER_PIGEON_HOME: root};
const cli = (...a) => JSON.parse(execFileSync('node', [path.join(SK, 'bin', 'carrier-pigeon.mjs'), ...a, '--json'], {env, encoding: 'utf8'}));
const inst = cli('install'); process.env.CARRIER_PIGEON_HOME = root; // woken agents inherit it; the installed CLI also finds its own mailbox
const H = await import(new URL('file:///' + path.join(root, 'host', 'carrier-pigeon-host.mjs').replace(/\\/g, '/')).href);
const cfg = {rescanMs: 5000, adapters: who, routes: {claude: ['claude'], codex: ['codex']},
  claude: {bin: arg('claude', live.claude?.bin || 'claude'), extraArgs: ['--model', 'haiku']},
  codex: {bin: arg('codex', live.codex?.bin || 'codex'), port: Number(arg('port', 4511)), model: null, sandbox: 'busOnly', lean: true}};
const host = new H.Host({root, config: cfg, adapters: H.defaultAdapters({...H.DEFAULTS, ...cfg})}); await host.start();
const sleep = ms => new Promise(r => setTimeout(r, ms)); const t0 = Date.now();
const asks = who.map(to => cli('send', '--from', 'grok', '--to', to, '--subject', 'e2e check', '--body',
  'Ask: count the files in the bin folder of your working directory (a read-only listing), then reply with exactly PONG followed by that number. Constraints: change nothing. Return: one line.'));
let replies = []; while (Date.now() - t0 < 360000) { replies = cli('inbox', 'grok'); if (replies.length >= asks.length) break; await sleep(3000); }
const uf = path.join(root, 'host/logs/usage.jsonl'); const rows = () => fs.existsSync(uf) ? fs.readFileSync(uf, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
for (const t1 = Date.now(); Date.now() - t1 < 150000 && new Set(rows().map(r => r.agent)).size < asks.length;) await sleep(2000); // usage lands after each turn's last message
const binCount = fs.readdirSync(path.join(root, 'bin')).length; const hostLog = fs.readFileSync(path.join(root, 'host/logs/host.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
const report = {installed: inst.copied.length, elapsed_s: Math.round((Date.now() - t0) / 1000), bin_files: binCount,
  asks: asks.map(a => ({to: a.to, receipts: H.readReceipts(root, a.id).map(r => r.ev)})),
  replies: replies.map(r => { const body = cli('read', r.id).body; return {from: r.from, body: body.slice(0, 160), correct: new RegExp(`^PONG\\s*${binCount}\\.?$`).test(body.trim())}; }),
  usage: rows().map(u => ({agent: u.agent, input_total: u.input_total, cached: u.cached, output: u.output, context_tokens: u.context_tokens, latency_ms: u.latency_ms, cost_usd: u.cost_usd})),
  codex_lean: hostLog.find(e => e.ev === 'codex-lean' || e.ev === 'codex-lean-partial')?.mcp_servers_disabled, codex_model: hostLog.find(e => e.ev === 'codex-ready')?.model,
  errors: hostLog.filter(e => /error|failed/.test(e.ev)).map(e => e.ev + ' ' + (e.err || e.params || '').slice(0, 120)),
  live_mailbox_untouched: liveMtime === null || fs.statSync(liveLog).mtimeMs === liveMtime};
await host.stop(); await sleep(2000); console.log(JSON.stringify(report, null, 1));
if (process.argv.includes('--keep')) console.log('kept for inspection: ' + root); // --keep: leave the mailbox and its host/logs
else try { fs.rmSync(root, {recursive: true, force: true}); } catch { console.log('remove later: ' + root); }
process.exit(report.replies.length === asks.length && report.live_mailbox_untouched ? 0 : 1);
