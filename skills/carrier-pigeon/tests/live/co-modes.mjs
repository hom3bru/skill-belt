// Live checks (opt-in; real Haiku and Codex wakes in a throwaway mailbox) for the co modes co-research.mjs does not cover, plus a solo baseline.
//   --mode audit   Claude and Codex audit a small wake limiter with three planted defects (an inclusive window boundary, an off-by-one
//                  limit, entries never evicted). Reported, not gated: which planted defects the surviving findings name.
//   --mode design  Claude and Codex each design a per-project token budget for this listener, then attack each other's designs. The
//                  project carries three acceptance criteria; the script, as lead, rates them "untested" (it does not judge designs).
//   --mode build   Codex builds one unit in its own git worktree inside the mailbox; the script plays Claude: it builds the other unit,
//                  reruns Codex's tests and files one test-gap challenge, concedes whatever Codex raises, then merges both branches and
//                  rates the criteria from the merged test run. Gated on the merged tests passing. Codex runs as the co-build skill
//                  requires, a session launched to write: one `codex exec` per phase, sandboxed to workspace-write on this temp mailbox,
//                  with the user's other MCP servers off and this mailbox's own carrier-pigeon server. No listener runs: a listener-woken
//                  Codex rightly refuses to write code on an unsigned notice (it filed a deviation saying so in the first attempt).
//   --mode solo    No project: Claude and Codex each get the co-research question (same two files, same planted 5-vs-6 mismatch) as one
//                  ordinary ask. Reported: whether each answer names the mismatch, with latency and usage, as a baseline for co-research.
// In every project mode the script is lead and judge (matt) and rules "unresolved" on any defended dispute. Pass (project modes): the
// project closed with a clean protocol check, every real member added work and challenged or passed, and no member wrote into the
// project thread.
// Usage: node tests/live/co-modes.mjs --mode audit|design|build|solo [--claude BIN] [--claude-model haiku] [--codex BIN] [--port 4521] [--keep]
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import crypto from 'node:crypto'; import {execFileSync, spawnSync} from 'node:child_process'; import {fileURLToPath} from 'node:url';
const SK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..'); const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const mode = arg('mode'); if (!['audit', 'design', 'build', 'solo'].includes(mode)) throw new Error('--mode audit|design|build|solo');
const cfgFile = path.join(os.homedir(), '.carrier-pigeon', 'host', 'config.json'); const live = fs.existsSync(cfgFile) ? JSON.parse(fs.readFileSync(cfgFile, 'utf8')) : {};
const liveLog = path.join(os.homedir(), '.carrier-pigeon', 'log.jsonl'); const liveMtime = fs.existsSync(liveLog) ? fs.statSync(liveLog).mtimeMs : null;
const root = fs.mkdtempSync(path.join(os.tmpdir(), `cp-co${mode}-`)); const env = {...process.env, CARRIER_PIGEON_HOME: root};
const cli = (...a) => JSON.parse(execFileSync('node', [path.join(SK, 'bin', 'carrier-pigeon.mjs'), ...a, '--json'], {env, encoding: 'utf8'}));
const run = (cmd, args, cwd) => { const r = spawnSync(cmd, args, {cwd, encoding: 'utf8', shell: false}); return {code: r.status, out: ((r.stdout || '') + (r.stderr || '')).trim()}; };
const git = (cwd, ...a) => { const r = run('git', a, cwd); if (r.code) throw new Error(`git ${a.join(' ')}: ${r.out}`); return r.out; };
// node --test summary lines: "# pass 3" (TAP) or "ℹ pass 3" (spec, the default when output is not a terminal)
const counts = out => { const p = /^\S* ?pass (\d+)\s*$/m.exec(out), f = /^\S* ?fail (\d+)\s*$/m.exec(out); return `${p ? p[1] : '?'} passed, ${f ? f[1] : '?'} failed`; };
cli('install'); process.env.CARRIER_PIGEON_HOME = root;
const co = await import(new URL('file:///' + path.join(root, 'bin', 'cp-co.mjs').replace(/\\/g, '/')).href);
const H = await import(new URL('file:///' + path.join(root, 'host', 'carrier-pigeon-host.mjs').replace(/\\/g, '/')).href);
const sleep = ms => new Promise(r => setTimeout(r, ms)); const t0 = Date.now(); const work = path.join(root, 'work'); fs.mkdirSync(work);

// ---------- corpora ----------
const LIMITER = ['// A per-agent wake limiter: at most `max` wakes per agent in any sliding window of `windowMs` milliseconds.',
  'export function makeLimiter({max = 6, windowMs = 600000} = {}) {', '  const seen = new Map(); // agent -> timestamps of allowed wakes', '  return {',
  '    allow(agent, now = Date.now()) {', '      const ts = (seen.get(agent) || []).filter(t => now - t <= windowMs);', '      if (ts.length > max) return false;',
  '      ts.push(now); seen.set(agent, ts); return true;', '    },', '    reset(agent) { seen.delete(agent); },', '    size() { return seen.size; },', '  };', '}', ''].join('\n');
const PLANTED = {boundary: /<=\s*windowMs|inclusive|boundary|exactly\s+windowMs|line 6\b/i, 'off-by-one': />\s*max|>=\s*max|max\s*\+\s*1|off.by.one|seven|7 wakes|line 7\b/i,
  'no-eviction': /evict|never (removed|deleted|pruned|shrinks)|grows|unbounded|memory|leak|stale (agent|entr)/i};
const hostCode = path.join(root, 'host', 'carrier-pigeon-host.mjs');
let docs = null; if (mode === 'solo') { docs = path.join(root, 'docs', 'listener.md'); fs.mkdirSync(path.dirname(docs)); const real = fs.readFileSync(path.join(SK, 'references', 'listener.md'), 'utf8');
  const planted = real.replace('Each agent gets at most 6 auto-wakes per 10 minutes.', 'Each agent gets at most 5 auto-wakes per 10 minutes.'); if (planted === real) throw new Error('planted sentence gone'); fs.writeFileSync(docs, planted); }

// ---------- build workspace: one repo, one worktree per member ----------
let wt = null, base = null; if (mode === 'build') {
  git(work, 'init', '-q', '-b', 'main'); git(work, 'config', 'user.name', 'co-build live test'); git(work, 'config', 'user.email', 'co-build@example.invalid');
  fs.writeFileSync(path.join(work, 'README.md'), '# co-build live check\n'); git(work, 'add', '-A'); git(work, 'commit', '-q', '-m', 'base'); base = git(work, 'rev-parse', '--short', 'HEAD');
  wt = {codex: path.join(root, 'wt-codex'), claude: path.join(root, 'wt-claude')}; git(work, 'worktree', 'add', '-q', '-b', 'co/codex', wt.codex); git(work, 'worktree', 'add', '-q', '-b', 'co/claude', wt.claude); }

const cfg = {rescanMs: 5000, adapters: mode === 'build' ? ['codex'] : ['claude', 'codex'], routes: mode === 'build' ? {codex: ['codex']} : {claude: ['claude'], codex: ['codex']},
  claude: {bin: arg('claude', live.claude?.bin || 'claude'), extraArgs: ['--model', arg('claude-model', 'haiku')]}, codex: {bin: arg('codex', live.codex?.bin || 'codex'), port: Number(arg('port', 4521)), model: null, sandbox: 'busOnly', lean: true}};
const host = mode === 'build' ? null : new H.Host({root, config: cfg, adapters: H.defaultAdapters({...H.DEFAULTS, ...cfg})}); await host?.start();
// build mode: one write-capable Codex session per phase (see the header). Returns its last message, wall time and reported token usage.
const execRuns = []; const runCodex = async (phase, prompt) => { const bin = cfg.codex.bin; let lean = []; try { lean = H.codexLeanArgs(await H.codexMcpServers(bin)); } catch {}
  const outFile = path.join(root, `codex-${phase}.txt`), started = Date.now();
  const args = [...lean, ...H.codexOwnMcpArgs(root), 'exec', '-s', 'workspace-write', '-C', root, '--skip-git-repo-check', '--ephemeral', '--json', '-o', outFile, prompt];
  const r = await new Promise(res => { const {spawn} = process.getBuiltinModule('node:child_process'); // stdin ignored: codex exec reads piped stdin to EOF and appends it to the prompt, so an open pipe would hang it
    const ch = spawn(bin, args, {cwd: root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']}); let so = '';
    ch.stdout.on('data', d => { so += d; }); ch.stderr.on('data', () => {}); const kill = setTimeout(() => ch.kill(), 1200000); ch.on('close', code => { clearTimeout(kill); res({code, so}); }); });
  const usage = r.so.split('\n').map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(e => e?.usage).map(e => e.usage);
  const last = fs.existsSync(outFile) ? fs.readFileSync(outFile, 'utf8') : ''; execRuns.push({phase, exit: r.code, s: Math.round((Date.now() - started) / 1000), input_tokens: usage.reduce((s, u) => s + (u.input_tokens || 0), 0) || null, last: last.replace(/\s+/g, ' ').slice(0, 300)}); };
const codexBrief = () => [`You are agent "codex", a member of co-build project ${p.id} on carrier-pigeon (mailbox ${root}). This session was launched to do your part of the project.`,
  `Use the co-build skill's rules. Mailbox commands: node bin/carrier-pigeon.mjs <command> from ${root} (CARRIER_PIGEON_HOME is set), or your carrier-pigeon MCP tools. Start with: co view ${p.id} --as codex.`,
  `You may write only inside your worktree ${wt.codex} (branch co/codex) and through mailbox commands. Never edit another unit's files. Do not reply to phase notices; co ready closes them.`].join('\n');
const uf = path.join(root, 'host/logs/usage.jsonl'); const rows = () => fs.existsSync(uf) ? fs.readFileSync(uf, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : [];
const hostLog = path.join(root, 'host/logs/host.jsonl');
const errors = () => !fs.existsSync(hostLog) ? [] : fs.readFileSync(hostLog, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse).filter(e => /error|failed/.test(e.ev) && !/not ready/.test(e.err || '')).map(e => e.ev + ' ' + (e.err || e.why || '').slice(0, 100));
const finish = async (report, ok) => { await host?.stop(); await sleep(2000); report.errors = errors(); report.live_mailbox_untouched = liveMtime === null || fs.statSync(liveLog).mtimeMs === liveMtime;
  report.passed = ok && report.live_mailbox_untouched; console.log(JSON.stringify(report, null, 1)); if (report.markdown_path) console.log('\n' + fs.readFileSync(report.markdown_path, 'utf8'));
  if (process.argv.includes('--keep')) console.log('kept for inspection: ' + root); else try { fs.rmSync(root, {recursive: true, force: true}); } catch { console.log('remove later: ' + root); }
  process.exit(report.passed ? 0 : 1); };
const usageOf = agent => rows().filter(u => u.agent === agent).map(u => ({input_total: u.input_total, cost_usd: u.cost_usd, latency_s: u.latency_ms ? Math.round(u.latency_ms / 1000) : null}));

// ---------- solo baseline ----------
if (mode === 'solo') { const q = 'What limits does this carrier-pigeon listener put on automatic wakes (messages per thread, co-work threads, wakes per agent per time window), and do its docs match its code?';
  const asks = Object.fromEntries(['claude', 'codex'].map(a => [a, cli('send', '--from', 'grok', '--to', a, '--subject', 'listener auto-wake limits', '--body',
    [`Ask: ${q}`, `Use only these two files; no web. Code: ${hostCode}. Docs: ${docs}.`, 'Return: the limits, each with "path | line N | exact words", then whether the docs match the code.'].join('\n'))]));
  const got = {}; for (const t1 = Date.now(); Date.now() - t1 < 1200000 && Object.keys(got).length < 2; await sleep(5000))
    for (const [a, m] of Object.entries(asks)) if (!got[a]) { const r = cli('inbox', 'grok', '--all-sessions').find(x => x.reply_to === m.id); if (r) got[a] = {s: Math.round((Date.now() - t0) / 1000), body: cli('read', r.id).body}; }
  for (const t1 = Date.now(); Date.now() - t1 < 180000 && !['claude', 'codex'].every(a => usageOf(a).length); await sleep(5000));
  const names = b => /\b5\b/.test(b || '') && /\b6\b/.test(b || '') && /mismatch|discrepan|contradict|differ|disagree|stale|do(es)? not match|doesn't match|inconsisten/i.test(b || '');
  const report = {mode, elapsed_s: Math.round((Date.now() - t0) / 1000), answers: Object.fromEntries(['claude', 'codex'].map(a => [a, {answered: !!got[a], at_s: got[a]?.s ?? null, names_mismatch: names(got[a]?.body), usage: usageOf(a),
    excerpt: (got[a]?.body || '').replace(/\s+/g, ' ').slice(0, 400)}]))};
  await finish(report, ['claude', 'codex'].every(a => got[a])); }

// ---------- projects ----------
let p; const realMembers = mode === 'build' ? ['codex'] : ['claude', 'codex'];
if (mode === 'audit') { const f = path.join(work, 'limiter.mjs'); fs.writeFileSync(f, LIMITER); const sha = crypto.createHash('sha256').update(LIMITER).digest('hex').slice(0, 16);
  p = cli('co', 'new', '--mode', 'audit', '--as', 'matt', '--lead', 'matt', '--judge', 'matt', '--members', 'claude,codex', '--min-challenges', '1', '--subject', `limiter.mjs@sha256:${sha}`,
    '--title', 'wake limiter audit', '--question', 'What defects does this wake limiter have against the contract stated on its line 1?',
    '--scope', `Only this file; no web; do not edit it. File: ${f}. Location as "path:line".`); }
if (mode === 'design') p = cli('co', 'new', '--mode', 'design', '--as', 'matt', '--lead', 'matt', '--judge', 'matt', '--members', 'claude,codex', '--min-challenges', '1',
  '--title', 'per-project token budget', '--question', 'Design a per-project token budget for co-work projects in this listener: where it is enforced, how usage is counted, and what happens to a wake when it runs out.',
  '--scope', `Read only ${hostCode}; no web; design only, edit nothing. Proposals name the functions they change in that file.`,
  '--criterion', 'names the function(s) in host/carrier-pigeon-host.mjs where the budget is checked', '--criterion', 'says what happens to a wake when the budget is exhausted',
  '--criterion', 'leaves the per-agent rate limit unchanged');
if (mode === 'build') p = cli('co', 'new', '--mode', 'build', '--as', 'matt', '--lead', 'matt', '--judge', 'matt', '--members', 'claude,codex', '--min-challenges', '1', '--subject', `work@${base}`,
  '--title', 'slug and list helpers', '--question', 'Add two helpers with tests: slugify (codex) and formatList (claude), each in its own module, so that `node --test` passes on the merged branch.',
  '--scope', `Repository ${work}, base ${base}. Contracts: slugify(s: string): string lowercases, turns each run of characters outside a-z0-9 into one "-", and trims leading and trailing "-". formatList(items: string[]): string joins with ", " and puts " and " before the last item. Each member works and commits only in its own worktree; never edit another unit's files.`,
  '--assign', `codex: src/slug.mjs and test/slug.test.mjs (node:test), in worktree ${wt.codex} on branch co/codex; commit there, then record the unit with your test receipt`,
  '--assign', `claude: src/format.mjs and test/format.test.mjs, in worktree ${wt.claude} on branch co/claude`,
  '--criterion', 'node --test passes on the merged branch', '--criterion', 'each branch changes only its own unit\'s files');

// ---------- the script's own parts: lead (adjudicate, closed) and, in build mode, the claude member ----------
const hooks = {
  adjudicate: async () => { const all = co.entries(p.id); for (const c of all.filter(e => e.type === 'challenge' && all.some(r => r.type === 'response' && r.target === e.id && r.outcome === 'defend') && !all.some(v => v.type === 'verdict' && v.target === e.id)))
    co.verdict(p.id, 'matt', {target: c.id, outcome: 'unresolved', reason: 'the live-test driver does not judge content'}); co.ready(p.id, 'matt'); }};
const integration = {}; if (mode === 'build') Object.assign(hooks, {
  independent: async () => { fs.mkdirSync(path.join(wt.claude, 'src')); fs.mkdirSync(path.join(wt.claude, 'test'));
    fs.writeFileSync(path.join(wt.claude, 'src', 'format.mjs'), "export function formatList(items) {\n  if (items.length < 2) return items.join('');\n  return items.slice(0, -1).join(', ') + ' and ' + items.at(-1);\n}\n");
    fs.writeFileSync(path.join(wt.claude, 'test', 'format.test.mjs'), "import test from 'node:test'; import assert from 'node:assert/strict'; import {formatList} from '../src/format.mjs';\n" +
      "test('empty and one', () => { assert.equal(formatList([]), ''); assert.equal(formatList(['a']), 'a'); });\ntest('two and three', () => { assert.equal(formatList(['a', 'b']), 'a and b'); assert.equal(formatList(['a', 'b', 'c']), 'a, b and c'); });\n");
    git(wt.claude, 'add', '-A'); git(wt.claude, 'commit', '-q', '-m', 'formatList'); const r = run('node', ['--test'], wt.claude);
    co.add(p.id, 'claude', {text: 'formatList with tests', files: 'src/format.mjs,test/format.test.mjs', verification: `node --test (in ${wt.claude}): exit ${r.code}, ${counts(r.out)}`, branch: 'co/claude', contract: 'formatList(items: string[]): string'});
    co.ready(p.id, 'claude');
    await runCodex('independent', codexBrief() + `\nPhase independent: implement src/slug.mjs and test/slug.test.mjs (node:test) in your worktree, to the slugify contract in the brief. Run node --test there and commit on co/codex. Then record the unit: co add ${p.id} --as codex --text "..." --files src/slug.mjs,test/slug.test.mjs --verification "<exact command>: exit <code>, <N> passed, <M> failed" --branch co/codex --contract "slugify(s: string): string". Then co ready ${p.id} --as codex.`); },
  challenge: async () => { const unit = co.entries(p.id).filter(e => e.type === 'unit' && e.by === 'codex').pop(); if (!unit) return co.advance(p.id, 'matt', 'codex recorded no unit');
    const r = run('node', ['--test'], wt.codex); integration.codex_rerun = `exit ${r.code}, ${counts(r.out)}`;
    if (r.code) co.challenge(p.id, 'claude', {target: unit.id, kind: 'bug', text: 'node --test fails in your worktree when I rerun it', evidence: r.out.slice(-600)});
    else co.challenge(p.id, 'claude', {target: unit.id, kind: 'test-gap', text: 'No test pins the trimming rule on both ends with mixed separators: slugify("--Hello,  World!--") must be "hello-world". Add it and re-record the unit with a new receipt.', evidence: `rerun in ${wt.codex}: ${integration.codex_rerun}`});
    co.ready(p.id, 'claude');
    await runCodex('challenge', codexBrief() + `\nPhase challenge: review claude's unit (co view ${p.id} --as codex shows it). Run node --test in ${wt.claude}, read git -C ${work} diff ${base}..co/claude, and check it against its contract. Then either co challenge ${p.id} --as codex --target E<n> --kind bug|test-gap|contract|regression --text "..." --evidence "...", or co pass ${p.id} --as codex --reason "<what you ran and what you saw>". Then co ready ${p.id} --as codex.`); },
  respond: async () => { const all = co.entries(p.id); const mine = new Set(all.filter(e => e.type === 'unit' && e.by === 'claude').map(e => e.id));
    for (const c of all.filter(e => e.type === 'challenge' && mine.has(e.target))) co.respond(p.id, 'claude', {target: c.id, outcome: 'concede', text: 'conceded by the scripted member (it does not revise code)'});
    co.ready(p.id, 'claude');
    await runCodex('respond', codexBrief() + `\nPhase respond: answer every challenge to your unit (co view ${p.id} --as codex shows them). To revise: change your files in your worktree, rerun node --test, commit on co/codex, record the revision with co add ${p.id} --as codex --revises E<n> --text "..." --files <the same files> --verification "<new receipt>" --branch co/codex, then co respond ${p.id} --as codex --target <challenge id> --outcome revise --text "...". Or concede, or defend with evidence. Then co ready ${p.id} --as codex.`); }});
hooks.closed = async () => { const ratings = [];
  // one branch at a time: an octopus merge runs git-merge-octopus, a shell script, and Git-Bash's sh cannot fork on some Windows machines
  if (mode === 'build') { let merged = true; try { for (const b of ['co/claude', 'co/codex']) git(work, 'merge', '-q', '--no-edit', b); } catch (e) { merged = false; integration.merge_error = String(e.message).slice(0, 300); }
    const r = merged ? run('node', ['--test'], work) : {code: null, out: ''}; integration.merged = merged; integration.receipt = merged ? `node --test on main after merging co/claude and co/codex: exit ${r.code}, ${counts(r.out)}` : 'merge failed';
    const units = co.entries(p.id).filter(e => e.type === 'unit'); const own = a => new Set(units.filter(u => u.by === a).flatMap(u => u.files));
    const changed = b => { try { return git(work, 'diff', '--name-only', `${base}..${b}`).split('\n').filter(Boolean); } catch { return null; } };
    const stray = ['codex', 'claude'].flatMap(a => (changed('co/' + a) || ['(branch unreadable)']).filter(f => !own(a).has(f)).map(f => `${a}: ${f}`)); integration.stray = stray;
    ratings.push(['C1', merged && r.code === 0 ? 'pass' : 'fail', integration.receipt], ['C2', stray.length ? 'fail' : 'pass', stray.length ? 'outside its unit: ' + stray.join(', ') : 'each branch diff stays inside its unit\'s files']); }
  else for (const c of co.load(p.id).criteria || []) ratings.push([c.id, 'untested', 'the live-test driver does not judge designs']);
  for (const [criterion, result, text] of ratings) co.add(p.id, 'matt', {type: 'rating', criterion, result, text});
  co.add(p.id, 'matt', {type: 'synthesis', text: mode === 'build' ? `Integration: ${integration.receipt}. See the units, challenges and ratings below.` : 'Placeholder synthesis written by the live-test driver; see the sections below.'}); co.ready(p.id, 'matt'); };

const timeline = [{phase: 'independent', s: 0}]; let last = null, lastChange = Date.now(); const handled = new Set();
while (Date.now() - t0 < 1800000) { const pr = co.load(p.id);
  if (pr.phase !== last) { if (last) timeline.push({phase: pr.phase, s: Math.round((Date.now() - t0) / 1000)}); last = pr.phase; lastChange = Date.now(); }
  const mine = pr.phase === 'adjudicate' || pr.phase === 'closed' || (mode === 'build' && ['independent', 'challenge', 'respond'].includes(pr.phase));
  if (mine && !handled.has(pr.phase)) { handled.add(pr.phase); try { await hooks[pr.phase](); } catch (e) { integration.hook_error = `${pr.phase}: ${String(e.message).slice(0, 300)}`; break; } if (pr.phase === 'closed') break; continue; }
  if (Date.now() - lastChange > 900000) break; await sleep(5000); }
const delivered = a => cli('thread', p.id, '--as', 'matt').filter(m => m.kind === 'ask' && m.to === a && H.readReceipts(root, m.id).some(r => String(r.ev).startsWith('notified'))).length;
// one usage row per delivered notice, so no run is still going when the host stops (a steered Codex turn can cover several notices,
// hence the cap on the wait)
for (const t1 = Date.now(); Date.now() - t1 < 240000 && !realMembers.every(a => rows().filter(u => u.agent === a).length >= delivered(a)); await sleep(5000));
await sleep(mode === 'build' ? 20000 : 5000); // a steered Codex turn may still be finishing
const all = co.entries(p.id), rep = co.report(p.id), chk = co.check(p.id), pr = co.load(p.id); const prim = co.MODES[mode].primary;
const per = a => ({entries: all.filter(e => e.type === prim && e.by === a).length, coverage: all.some(e => e.type === 'coverage' && e.by === a), challenges: all.filter(e => e.type === 'challenge' && e.by === a).length,
  passes: all.filter(e => e.type === 'pass' && e.by === a).length, responses: all.filter(e => e.type === 'response' && e.by === a).map(r => r.outcome), revisions: all.filter(e => e.revises && e.by === a).length});
const members = Object.fromEntries(['claude', 'codex'].map(a => [a, per(a)])); const threadMsgs = cli('thread', p.id, '--as', 'matt').filter(m => realMembers.includes(m.from));
const md = path.join(root, `co-${mode}-report.md`); fs.writeFileSync(md, rep.markdown);
const report = {mode, elapsed_s: Math.round((Date.now() - t0) / 1000), project: p.id, phase: pr.phase, timeline, members, check: chk.findings.map(f => `${f.code} ${f.id || ''}: ${f.msg}`),
  survived: rep.survived.length, overturned: rep.overturned.length, disputed: rep.disputed.length, accepted: rep.accepted, criteria: rep.criteria?.map(c => `${c.id} ${c.result}`),
  member_messages_in_thread: threadMsgs.map(m => `${m.from} ${m.kind}: ${String(m.body).replace(/\s+/g, ' ').slice(0, 80)}`),
  ...(mode === 'audit' ? {planted_found: Object.fromEntries(Object.entries(PLANTED).map(([k, re]) => [k, rep.survived.concat(rep.disputed).filter(s => re.test([s.entry.text, s.entry.evidence, s.entry.location].join(' '))).map(s => s.id)]))} : {}),
  hook_error: integration.hook_error || null, ...(mode === 'build' ? {integration, codex_sessions: execRuns} : {}), usage: Object.fromEntries(realMembers.map(a => [a, usageOf(a)])), markdown_path: md};
const ok = pr.phase === 'closed' && chk.clean && !threadMsgs.length && !integration.hook_error && realMembers.every(a => members[a].entries > 0 && (members[a].challenges > 0 || members[a].passes > 0))
  && (mode !== 'audit' || realMembers.every(a => members[a].coverage)) && (mode !== 'build' || (integration.merged && rep.criteria.find(c => c.id === 'C1')?.result === 'pass'));
await finish(report, ok);
