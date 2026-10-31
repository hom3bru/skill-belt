// Live check (opt-in; a few haiku wakes plus a few Codex turns): a real co-research project between the listener's Claude and Codex in a
// throwaway mailbox. The question is answerable from files inside that mailbox (the installed host code, and a docs copy with one planted
// mismatch: it says 5 auto-wakes per 10 minutes where the code says 6), so no web access is needed. The script is lead and judge (matt): it
// opens the project, rules "unresolved" on any defended dispute (it does not judge content), writes a placeholder synthesis and reads the
// report. Pass: the project closed with a clean protocol check, each member added cited claims and a coverage statement, challenged or
// passed, and answered every challenge to its claims, and no member wrote into the shared project thread (the first run, before the fix,
// had Claude reply to each notice with a summary that Codex then read during the blind phase). Reported, not gated: whether the planted
// mismatch surfaced in any entry.
// Usage: node tests/live/co-research.mjs [--claude BIN] [--claude-model haiku] [--codex BIN] [--port 4513] [--keep]
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import {execFileSync} from 'node:child_process'; import {fileURLToPath} from 'node:url';
const SK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..'); const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const cfgFile = path.join(os.homedir(), '.carrier-pigeon', 'host', 'config.json'); const live = fs.existsSync(cfgFile) ? JSON.parse(fs.readFileSync(cfgFile, 'utf8')) : {};
const liveLog = path.join(os.homedir(), '.carrier-pigeon', 'log.jsonl'); const liveMtime = fs.existsSync(liveLog) ? fs.statSync(liveLog).mtimeMs : null;
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-cores-')); const env = {...process.env, CARRIER_PIGEON_HOME: root};
const cli = (...a) => JSON.parse(execFileSync('node', [path.join(SK, 'bin', 'carrier-pigeon.mjs'), ...a, '--json'], {env, encoding: 'utf8'}));
cli('install'); process.env.CARRIER_PIGEON_HOME = root;
// the corpus: the installed host code plus a docs copy with the planted mismatch
const docs = path.join(root, 'docs'); fs.mkdirSync(docs); const real = fs.readFileSync(path.join(SK, 'references', 'listener.md'), 'utf8');
const planted = real.replace('Each agent gets at most 6 auto-wakes per 10 minutes.', 'Each agent gets at most 5 auto-wakes per 10 minutes.');
if (planted === real) throw new Error('the planted sentence is gone from references/listener.md; update this script'); fs.writeFileSync(path.join(docs, 'listener.md'), planted);
const co = await import(new URL('file:///' + path.join(root, 'bin', 'cp-co.mjs').replace(/\\/g, '/')).href);
const H = await import(new URL('file:///' + path.join(root, 'host', 'carrier-pigeon-host.mjs').replace(/\\/g, '/')).href);
const cfg = {rescanMs: 5000, adapters: ['claude', 'codex'], routes: {claude: ['claude'], codex: ['codex']},
  claude: {bin: arg('claude', live.claude?.bin || 'claude'), extraArgs: ['--model', arg('claude-model', 'haiku')]}, codex: {bin: arg('codex', live.codex?.bin || 'codex'), port: Number(arg('port', 4513)), model: null, sandbox: 'busOnly', lean: true}};
const host = new H.Host({root, config: cfg, adapters: H.defaultAdapters({...H.DEFAULTS, ...cfg})}); await host.start();
const sleep = ms => new Promise(r => setTimeout(r, ms)); const t0 = Date.now();
const code = path.join(root, 'host', 'carrier-pigeon-host.mjs'), doc = path.join(docs, 'listener.md');
const p = cli('co', 'new', '--mode', 'research', '--as', 'matt', '--lead', 'matt', '--judge', 'matt', '--members', 'claude,codex', '--min-challenges', '1',
  '--title', 'listener auto-wake limits', '--question', 'What limits does this carrier-pigeon listener put on automatic wakes (messages per thread, co-work threads, wakes per agent per time window), and do its docs match its code?',
  '--scope', `Only these two files; no web. Code: ${code}. Docs: ${doc}. Cite as "path | line N | exact words".`,
  '--assign', `codex: the code (${code})`, '--assign', `claude: the docs (${doc})`);
const timeline = [{phase: 'independent', s: 0}]; let last = 'independent', lastChange = Date.now();
while (Date.now() - t0 < 1800000) { const pr = co.load(p.id);
  if (pr.phase !== last) { timeline.push({phase: pr.phase, s: Math.round((Date.now() - t0) / 1000)}); last = pr.phase; lastChange = Date.now(); }
  if (pr.phase === 'adjudicate') { const all = co.entries(p.id);
    for (const c of all.filter(e => e.type === 'challenge' && all.some(r => r.type === 'response' && r.target === c.id && r.outcome === 'defend') && !all.some(v => v.type === 'verdict' && v.target === c.id)))
      co.verdict(p.id, 'matt', {target: c.id, outcome: 'unresolved', reason: 'the live-test driver does not judge content'});
    co.ready(p.id, 'matt'); continue; }
  if (pr.phase === 'closed') { if (!co.entries(p.id).some(e => e.type === 'synthesis')) co.add(p.id, 'matt', {type: 'synthesis', text: 'Placeholder synthesis written by the live-test driver; see the sections below.'}); co.ready(p.id, 'matt'); break; }
  if (Date.now() - lastChange > 900000) break; // a phase stalled for 15 minutes: report it rather than force it
  await sleep(5000); }
// let every run finish before stopping the host: usage is logged when a run or turn ends, one row per delivered notice
const uf = path.join(root, 'host/logs/usage.jsonl'); const rows = () => fs.existsSync(uf) ? fs.readFileSync(uf, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
const delivered = a => cli('thread', p.id).filter(m => m.kind === 'ask' && m.to === a && H.readReceipts(root, m.id).some(r => String(r.ev).startsWith('notified'))).length;
for (const t1 = Date.now(); Date.now() - t1 < 240000; await sleep(5000)) if (['claude', 'codex'].every(a => rows().filter(u => u.agent === a).length >= delivered(a))) break;
const usage = rows(); const all = co.entries(p.id), rep = co.report(p.id), chk = co.check(p.id), pr = co.load(p.id);
const per = a => ({claims: all.filter(e => e.type === 'claim' && e.by === a).length, cited: all.filter(e => e.type === 'claim' && e.by === a).every(e => (e.cites || []).length > 0),
  coverage: all.some(e => e.type === 'coverage' && e.by === a), challenges: all.filter(e => e.type === 'challenge' && e.by === a).length, passes: all.filter(e => e.type === 'pass' && e.by === a).length,
  responses: all.filter(e => e.type === 'response' && e.by === a).map(r => r.outcome), revisions: all.filter(e => e.revises && e.by === a).length});
const members = {claude: per('claude'), codex: per('codex')};
// surfaced = one entry (claim, challenge or response) names both figures and says they disagree; two separate claims that each state
// one figure are not a finding (the second live run had exactly that: both survived, nobody compared them)
const surfaced = all.filter(e => { const s = [e.text, e.evidence, e.reason].filter(Boolean).join(' ');
  return /\b5\b/.test(s) && /\b6\b/.test(s) && /mismatch|discrepan|contradict|differ|stale|does not (match|describe)|doesn't match|inconsisten/i.test(s); }).map(e => e.id);
const report = {elapsed_s: Math.round((Date.now() - t0) / 1000), project: p.id, phase: pr.phase, timeline, members,
  passed: pr.phase === 'closed' && chk.clean && Object.values(members).every(m => m.claims > 0 && m.cited && m.coverage && (m.challenges > 0 || m.passes > 0))
    && !cli('thread', p.id).some(m => ['claude', 'codex'].includes(m.from)), // a member's message in the shared thread is the blind-phase leak 0.8.0 closes
  check: chk.findings.map(f => `${f.code} ${f.id || ''}: ${f.msg}`), survived: rep.survived.length, overturned: rep.overturned.length, disputed: rep.disputed.length,
  member_messages_in_thread: cli('thread', p.id).filter(m => ['claude', 'codex'].includes(m.from)).map(m => `${m.from} ${m.kind}: ${String(m.body).replace(/\s+/g, ' ').slice(0, 80)}`),
  planted_mismatch_surfaced_in: surfaced,
  wakes: usage.map(u => ({agent: u.agent, thread: u.thread === p.id ? 'project' : u.thread, resumed: u.resumed, input_total: u.input_total, cost_usd: u.cost_usd, latency_s: u.latency_ms ? Math.round(u.latency_ms / 1000) : null})),
  claude_cost_usd: +usage.filter(u => u.agent === 'claude').reduce((s, u) => s + (u.cost_usd || 0), 0).toFixed(4),
  no_wake: cli('thread', p.id).map(m => H.readReceipts(root, m.id).filter(r => r.ev === 'no-wake').map(r => m.kind + ':' + r.reason)).flat(),
  errors: fs.readFileSync(path.join(root, 'host/logs/host.jsonl'), 'utf8').trim().split('\n').map(JSON.parse).filter(e => /error|failed/.test(e.ev) && !/not ready/.test(e.err || '')).map(e => e.ev + ' ' + (e.err || e.why || '').slice(0, 100)),
  live_mailbox_untouched: liveMtime === null || fs.statSync(liveLog).mtimeMs === liveMtime};
await host.stop(); await sleep(2000); fs.writeFileSync(path.join(root, 'co-report.md'), rep.markdown); console.log(JSON.stringify(report, null, 1)); console.log('\n' + rep.markdown);
if (process.argv.includes('--keep')) console.log('kept for inspection: ' + root); else try { fs.rmSync(root, {recursive: true, force: true}); } catch { console.log('remove later: ' + root); }
process.exit(report.passed ? 0 : 1);
