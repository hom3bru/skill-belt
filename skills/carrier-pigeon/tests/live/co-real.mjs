// Live checks with every role played by a real model, on real material: no scripted member, lead or judge, and no planted defects.
// The harness never writes an entry. It only sets up, runs the listener or a sandboxed Codex session, and reports. Claude roles that no
// listener serves (a co-build builder, a non-member judge) are run by the operator's own Claude session as subagents, under that session's
// permission system; the harness does not launch Claude itself.
//   setup --mode audit   project auditing carrier-pigeon's own sealed-round code at the version under test; members claude and codex (woken
//                        by the listener), lead codex, judge grok (the unused, non-member id a separate Claude session acts under).
//   setup --mode build   repository plus one worktree per member; members claude and codex, lead codex, judge grok.
//   listen ROOT [--until PHASE[,PHASE]] [--member-model sonnet] [--port 4581]   run the listener (Claude and Codex) until the phase is reached
//                        or the lead has closed the project, then stop it. Usage rows go to ROOT/host/logs/usage.jsonl.
//   codex ROOT ROLE PROMPT-FILE   one Codex session launched to write: codex exec, workspace-write sandbox on ROOT, the user's other MCP
//                        servers off and ROOT's own carrier-pigeon server. Appends its record to ROOT/sessions.jsonl.
//   report ROOT          the protocol result and the pass gate:
//     - closed with a clean check;
//     - a synthesis from the lead;
//     - a judge verdict on every defended dispute;
//     - no member message in the project thread;
//     - audit: sealed until one clean reveal;
//     - build: C1 rated pass by the lead, and the merged tests pass when the harness reruns them.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import crypto from 'node:crypto'; import {execFileSync, spawnSync, spawn} from 'node:child_process'; import {fileURLToPath} from 'node:url';
const SK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..'); const argv = process.argv.slice(2); const arg = (k, d) => { const i = argv.indexOf('--' + k); return i >= 0 ? argv[i + 1] : d; };
const cfgFile = path.join(os.homedir(), '.carrier-pigeon', 'host', 'config.json'); const live = fs.existsSync(cfgFile) ? JSON.parse(fs.readFileSync(cfgFile, 'utf8')) : {};
const CLAUDE = arg('claude', live.claude?.bin || 'claude'), CODEX = arg('codex', live.codex?.bin || 'codex');
const run = (cmd, args, cwd) => { const r = spawnSync(cmd, args, {cwd, encoding: 'utf8'}); return {code: r.status, out: ((r.stdout || '') + (r.stderr || '')).trim()}; };
const git = (cwd, ...a) => { const r = run('git', a, cwd); if (r.code) throw new Error(`git ${a.join(' ')}: ${r.out}`); return r.out; };
const counts = out => { const p = /^\S* ?pass (\d+)\s*$/m.exec(out), f = /^\S* ?fail (\d+)\s*$/m.exec(out); return `${p ? p[1] : '?'} passed, ${f ? f[1] : '?'} failed`; };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const open = async root => { process.env.CARRIER_PIGEON_HOME = root; const env = {...process.env, CARRIER_PIGEON_HOME: root};
  const cli = (...a) => JSON.parse(execFileSync('node', [path.join(root, 'bin', 'carrier-pigeon.mjs'), ...a, '--json'], {env, encoding: 'utf8'}));
  const co = await import(new URL('file:///' + path.join(root, 'bin', 'cp-co.mjs').replace(/\\/g, '/')).href), H = await import(new URL('file:///' + path.join(root, 'host', 'carrier-pigeon-host.mjs').replace(/\\/g, '/')).href);
  const meta = JSON.parse(fs.readFileSync(path.join(root, 'co-real.json'), 'utf8')); return {env, cli, co, H, meta}; };

const [cmd] = argv;
if (cmd === 'setup') { const mode = arg('mode'); if (!['audit', 'build'].includes(mode)) throw new Error('setup --mode audit|build');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), `cp-real${mode}-`)), env = {...process.env, CARRIER_PIGEON_HOME: root};
  const cli = (...a) => JSON.parse(execFileSync('node', [path.join(SK, 'bin', 'carrier-pigeon.mjs'), ...a, '--json'], {env, encoding: 'utf8'})); cli('install');
  const liveLog = path.join(os.homedir(), '.carrier-pigeon', 'log.jsonl'); const meta = {mode, root, live_log_mtime: fs.existsSync(liveLog) ? fs.statSync(liveLog).mtimeMs : null};
  if (mode === 'audit') { const target = path.join(root, 'bin', 'cp-co.mjs'), cpm = path.join(root, 'bin', 'carrier-pigeon.mjs'); const head = run('git', ['rev-parse', '--short', 'HEAD'], SK).out || 'unknown';
    const sha = crypto.createHash('sha256').update(fs.readFileSync(target)).digest('hex').slice(0, 16);
    meta.project = cli('co', 'new', '--mode', 'audit', '--as', 'user', '--lead', 'codex', '--judge', 'grok', '--members', 'claude,codex', '--min-challenges', '1', '--subject', `carrier-pigeon@${head} cp-co.mjs sha256:${sha}`,
      '--title', 'sealed first round audit', '--question', 'What defects does carrier-pigeon\'s sealed first round have? Can a member see, infer or influence another member\'s first-round work before the reveal, alter its own after committing, or make the reveal fail or lie?',
      '--scope', `Read-only; no web; edit nothing. Code: ${target} (seal, unseal, store, ownOpen, reveal, sealHolds, view, blockers, advanceIfDone, advance, check) and ${cpm} (send, thread, reply). Threat model: a member agent running as the same OS user that uses the tools as given but probes their edges; also crash-safety of the reveal. Out of scope: an agent deliberately reading host/secrets (a documented limit). Location as "path:line".`).id; }
  if (mode === 'build') { const work = path.join(root, 'work'); fs.mkdirSync(work); git(work, 'init', '-q', '-b', 'main'); git(work, 'config', 'user.name', 'co-build live test'); git(work, 'config', 'user.email', 'co-build@example.invalid');
    fs.writeFileSync(path.join(work, 'README.md'), '# co-build live check\n'); git(work, 'add', '-A'); git(work, 'commit', '-q', '-m', 'base'); const base = git(work, 'rev-parse', '--short', 'HEAD');
    const wt = {codex: path.join(root, 'wt-codex'), claude: path.join(root, 'wt-claude')}; git(work, 'worktree', 'add', '-q', '-b', 'co/codex', wt.codex); git(work, 'worktree', 'add', '-q', '-b', 'co/claude', wt.claude);
    Object.assign(meta, {work, base, wt}); meta.project = cli('co', 'new', '--mode', 'build', '--as', 'user', '--lead', 'codex', '--judge', 'grok', '--members', 'claude,codex', '--min-challenges', '1', '--subject', `work@${base}`,
      '--title', 'slug and list helpers', '--question', 'Add two helpers with tests, slugify (codex) and formatList (claude), each in its own module, so that `node --test` passes on the merged branch.',
      '--scope', `Repository ${work}, base ${base}. Contracts: slugify(s: string): string lowercases, turns each run of characters outside a-z0-9 into one "-", and trims leading and trailing "-". formatList(items: string[]): string joins with ", " and puts " and " before the last item ("" for none, the item alone for one). Each member works and commits only in its own worktree.`,
      '--assign', `codex: src/slug.mjs and test/slug.test.mjs (node:test), in worktree ${wt.codex} on branch co/codex`, '--assign', `claude: src/format.mjs and test/format.test.mjs (node:test), in worktree ${wt.claude} on branch co/claude`,
      '--criterion', 'node --test passes on the merged branch', '--criterion', 'each branch changes only its own unit\'s files').id; }
  fs.writeFileSync(path.join(root, 'co-real.json'), JSON.stringify(meta, null, 1)); console.log(JSON.stringify(meta, null, 1)); process.exit(0); }

if (cmd === 'listen') { const root = argv[1]; const {co, H, meta} = await open(root); const until = String(arg('until', 'closed')).split(','); const t0 = Date.now(), pid = meta.project;
  const cfg = {rescanMs: 5000, adapters: ['claude', 'codex'], routes: {claude: ['claude'], codex: ['codex']}, claude: {bin: CLAUDE, extraArgs: ['--model', arg('member-model', 'sonnet')]},
    codex: {bin: CODEX, port: Number(arg('port', 4581)), model: null, sandbox: 'busOnly', lean: true}};
  const host = new H.Host({root, config: cfg, adapters: H.defaultAdapters({...H.DEFAULTS, ...cfg})}); await host.start(); let lastChange = Date.now(), last = null; const seen = [];
  const leadDone = () => fs.existsSync(path.join(root, 'co', pid, 'ready', `closed~${co.load(pid).lead}.json`));
  while (Date.now() - t0 < 3600000) { const pr = co.load(pid); if (pr.phase !== last) { seen.push(`${pr.phase}@${Math.round((Date.now() - t0) / 1000)}s`); last = pr.phase; lastChange = Date.now(); }
    if (pr.sealed && pr.phase === 'independent') for (const e of co.entries(pid).filter(e => ['claude', 'codex'].includes(e.by) && e.type !== 'sealed')) fs.appendFileSync(path.join(root, 'plaintext-before-reveal.log'), `${e.id} ${e.type} by ${e.by}\n`);
    if ((pr.phase === 'closed' && leadDone()) || (pr.phase !== 'closed' && until.includes(pr.phase))) break; if (Date.now() - lastChange > 1200000) break; await sleep(5000); }
  const uf = path.join(root, 'host', 'logs', 'usage.jsonl'); const rows = () => fs.existsSync(uf) ? fs.readFileSync(uf, 'utf8').trim().split('\n').filter(Boolean).length : 0;
  for (let n = -1, t1 = Date.now(); Date.now() - t1 < 120000; await sleep(10000)) { const k = rows(); if (k === n) break; n = k; } // let running turns finish and log
  await host.stop(); await sleep(2000); console.log(JSON.stringify({phase: co.load(pid).phase, phases_seen: seen, lead_done: leadDone()})); process.exit(0); }

if (cmd === 'codex') { const [, root, role, promptFile] = argv; const {env, H} = await open(root); const prompt = fs.readFileSync(promptFile, 'utf8'); let lean = [];
  try { lean = H.codexLeanArgs(await H.codexMcpServers(CODEX)); } catch {} const out = path.join(root, `codex-${role}.txt`), started = Date.now();
  // stdin ignored: codex exec reads piped stdin to EOF and appends it to the prompt
  const r = await new Promise(res => { const ch = spawn(CODEX, [...lean, ...H.codexOwnMcpArgs(root), 'exec', '-s', 'workspace-write', '-C', root, '--skip-git-repo-check', '--ephemeral', '--json', '-o', out, prompt],
    {cwd: root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']}); let so = ''; ch.stdout.on('data', d => { so += d; }); ch.stderr.on('data', () => {});
    const kill = setTimeout(() => ch.kill(), 1500000); ch.on('close', code => { clearTimeout(kill); res({code, so}); }); });
  const usage = r.so.split('\n').map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(e => e?.usage).map(e => e.usage);
  const rec = {role, as: 'codex', exit: r.code, s: Math.round((Date.now() - started) / 1000), input_tokens: usage.reduce((s, u) => s + (u.input_tokens || 0), 0) || null, last: (fs.existsSync(out) ? fs.readFileSync(out, 'utf8') : '').replace(/\s+/g, ' ').slice(0, 400)};
  fs.appendFileSync(path.join(root, 'sessions.jsonl'), JSON.stringify(rec) + '\n'); console.log(JSON.stringify(rec)); process.exit(0); }

if (cmd === 'report') { const root = argv[1]; const {cli, co, meta} = await open(root); const pid = meta.project; const all = co.entries(pid), rep = co.report(pid), chk = co.check(pid), pr = co.load(pid); const prim = co.MODES[meta.mode].primary;
  const defended = all.filter(c => c.type === 'challenge' && all.some(r => r.type === 'response' && r.target === c.id && r.outcome === 'defend')); const verdicts = all.filter(e => e.type === 'verdict');
  const syn = all.filter(e => e.type === 'synthesis').pop(); const threadMsgs = cli('thread', pid, '--as', 'user').filter(m => ['claude', 'codex'].includes(m.from) && m.kind !== 'ask');
  const pf = path.join(root, 'plaintext-before-reveal.log'); const plaintext = fs.existsSync(pf) ? [...new Set(fs.readFileSync(pf, 'utf8').trim().split('\n').filter(Boolean))] : [];
  let rerun = null; if (meta.mode === 'build') { const r = run('node', ['--test'], meta.work); rerun = `exit ${r.code}, ${counts(r.out)}; main: ${run('git', ['log', '--oneline', '-6', 'main'], meta.work).out.replace(/\n/g, ' | ')}`; }
  const per = a => ({entries: all.filter(e => e.type === prim && e.by === a).length, coverage: all.some(e => e.type === 'coverage' && e.by === a), challenges: all.filter(e => e.type === 'challenge' && e.by === a).length,
    passes: all.filter(e => e.type === 'pass' && e.by === a).length, responses: all.filter(e => e.type === 'response' && e.by === a).map(r => r.outcome)});
  const sf = path.join(root, 'sessions.jsonl'), uf = path.join(root, 'host', 'logs', 'usage.jsonl'); const liveLog = path.join(os.homedir(), '.carrier-pigeon', 'log.jsonl');
  const report = {mode: meta.mode, project: pid, phase: pr.phase, phases: pr.phases.map(x => `${x.phase}@${x.at}`), members: {claude: per('claude'), codex: per('codex')}, check: chk.findings.map(f => `${f.code} ${f.id || ''}: ${f.msg}`),
    synthesis_by: syn?.by || null, synthesis: syn ? String(syn.text).replace(/\s+/g, ' ').slice(0, 700) : null, defended: defended.map(c => c.id),
    verdicts: verdicts.map(v => `${v.id} on ${v.target} by ${v.by}: ${v.outcome} (${String(v.reason).replace(/\s+/g, ' ').slice(0, 220)})`), criteria: rep.criteria?.map(c => `${c.id} ${c.result}: ${String(c.evidence || '').slice(0, 200)}`),
    rerun_by_harness: rerun, sealed: pr.sealed ? {revealed: pr.revealed || null, plaintext_before_reveal: plaintext} : null, member_messages_in_thread: threadMsgs.map(m => `${m.from} ${m.kind}`),
    findings: [...rep.survived.map(s => ['survived', s]), ...rep.disputed.map(s => ['disputed', s]), ...rep.overturned.map(s => ['overturned', s])]
      .map(([k, s]) => `${k} ${s.id} (${s.by}${s.entry.severity ? ', ' + s.entry.severity : ''}${s.entry.location ? ', ' + s.entry.location : ''}): ${String(s.entry.text).replace(/\s+/g, ' ').slice(0, 500)}`),
    codex_sessions: fs.existsSync(sf) ? fs.readFileSync(sf, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [],
    listener_usage: fs.existsSync(uf) ? fs.readFileSync(uf, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse).map(u => ({agent: u.agent, input_total: u.input_total, cost_usd: u.cost_usd, latency_s: u.latency_ms ? Math.round(u.latency_ms / 1000) : null})) : [],
    live_mailbox_untouched: meta.live_log_mtime === null || fs.statSync(liveLog).mtimeMs === meta.live_log_mtime};
  report.passed = pr.phase === 'closed' && chk.clean && syn?.by === pr.lead && defended.every(c => verdicts.some(v => v.target === c.id && v.by === pr.judge)) && !threadMsgs.length && report.live_mailbox_untouched
    && (meta.mode !== 'audit' || (pr.sealed && !plaintext.length && pr.revealed?.opened > 0 && !pr.revealed?.failed))
    && (meta.mode !== 'build' || (rep.criteria.find(c => c.id === 'C1')?.result === 'pass' && /^exit 0,/.test(rerun || '') && ['claude', 'codex'].every(a => all.some(u => u.type === 'unit' && u.by === a))));
  fs.writeFileSync(path.join(root, `co-real-${meta.mode}-report.md`), rep.markdown); console.log(JSON.stringify(report, null, 1)); process.exit(report.passed ? 0 : 1); }

console.error('usage: co-real.mjs setup --mode audit|build | listen ROOT [--until PHASE] | codex ROOT ROLE PROMPT-FILE | report ROOT'); process.exit(64);
