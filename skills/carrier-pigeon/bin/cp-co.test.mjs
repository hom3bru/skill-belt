// node cp-co.test.mjs — the co-work engine (cp-co.mjs), its CLI and MCP surface, and the four co-* sub-skills that document it.
// A temp CARRIER_PIGEON_HOME is set before the library is loaded, so nothing touches the real mailbox.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import assert from 'node:assert/strict'; import {spawnSync} from 'node:child_process';
const HOME = fs.mkdtempSync(path.join(os.tmpdir(), 'cpco-')); process.env.CARRIER_PIGEON_HOME = HOME;
const cp = await import('./carrier-pigeon.mjs'); const co = await import('./cp-co.mjs'); cp.init();
const BIN = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')), SKILL = path.dirname(BIN);
let n = 0, failed = 0; const t = async (name, fn) => { n++; try { await fn(); console.log('ok', n, name); } catch (e) { failed++; console.log('not ok', n, name); console.log('  ' + String(e?.stack || e).split('\n').slice(0, 6).join('\n  ')); } };
const cite = 'https://example.org/docs | v2 section 3 | the documented behaviour';
const claim = (p, as, text = 'a claim by ' + as, o = {}) => co.add(p.id, as, {text, strength: 'present', cites: [cite], ...o});
const cover = (p, as) => co.add(p.id, as, {type: 'coverage', text: 'read the vendor docs; did not search the issue tracker'});
const SUBJECT = 'repo api@3f2c1ab';
const notices = a => cp.list(a, 'inbox', {allSessions: true}).filter(m => m.thread && String(m.thread).startsWith('co-'));
const research = (o = {}) => co.create({mode: 'research', title: 'q', question: 'what holds?', members: 'claude,codex', lead: 'matt', minChallenges: 1, as: 'matt', ...o});
// independent -> challenge with one claim each; returns the claim entries
const toChallenge = p => { const a = claim(p, 'codex', 'codex claim'), b = claim(p, 'claude', 'claude claim'); cover(p, 'codex'); cover(p, 'claude'); co.ready(p.id, 'codex'); co.ready(p.id, 'claude'); return {a, b}; };
const cli = (...args) => spawnSync('node', [path.join(BIN, 'carrier-pigeon.mjs'), ...args], {env: process.env, encoding: 'utf8'});

await t('create validates the mode, the members and the assignments, and refuses an unknown agent', () => {
  assert.throws(() => research({mode: 'poetry'}), /bad mode/); assert.throws(() => research({members: 'claude'}), /two or more/);
  assert.throws(() => research({members: 'claude,nobody'}), /unknown agent/); assert.throws(() => research({title: 'two\nlines'}), /one line/);
  assert.throws(() => research({assign: ['grok: docs']}), /member of the project/); assert.throws(() => research({assign: ['no colon here']}), /member: their part/);
  const p = research({assign: ['codex: vendor docs', 'claude: issues and benchmarks']}); assert.match(p.id, /^co-[0-9A-Z]{26}$/); assert.equal(p.phase, 'independent'); assert.equal(p.judge, 'matt');
  assert.deepEqual(p.members, [{agent: 'claude', part: 'issues and benchmarks'}, {agent: 'codex', part: 'vendor docs'}]); });
await t('opening sends each member a phase notice in the project thread, naming their part', () => { const p = research({assign: ['codex: changelogs']});
  const [mine] = notices('codex').filter(m => m.thread === p.id); assert.ok(mine, 'codex got a notice'); assert.equal(mine.kind, 'ask'); assert.match(mine.subject, /\[co-research\].*phase independent/);
  const body = cp.load(mine.id).msg.body; assert.match(body, /Your part: changelogs/); assert.match(body, /co ready/); assert.match(body, /untrusted peer work/);
  assert.ok(!cp.load(notices('claude').find(m => m.thread === p.id).id).msg.body.includes('Your part'), 'an unassigned member takes the whole question'); });
await t('the independent phase is blind for members and open for a non-member lead; build mode is open', () => { const p = research(); claim(p, 'codex'); claim(p, 'claude');
  const v = co.view(p.id, 'codex'); assert.equal(v.entries.length, 1); assert.equal(v.entries[0].by, 'codex'); assert.equal(v.blind, true); assert.equal(v.hidden, 1);
  assert.equal(co.view(p.id, 'matt').entries.length, 2, 'the lead is not a member here');
  const b = co.create({mode: 'build', title: 'b', question: 'build it', members: 'claude,codex', lead: 'claude', subject: SUBJECT, as: 'claude'});
  co.add(b.id, 'codex', {text: 'u', files: 'a.js', verification: 'node a.test.js: exit 0, 3 passed'}); assert.equal(co.view(b.id, 'claude').entries.length, 1, 'build units are visible to every member'); });
await t('each mode demands its evidence: citations, location and evidence, tradeoffs and risks, files and a receipt', () => {
  const r = research(); assert.throws(() => co.add(r.id, 'codex', {text: 'x', strength: 'present'}), /--cite/); assert.throws(() => claim(r, 'codex', 'x', {strength: 'proven'}), /strength/);
  assert.throws(() => co.add(r.id, 'codex', {text: 'x', cites: ['only-a-source']}), /source \| location/); assert.throws(() => claim(r, 'grok'), /not a member/);
  assert.equal(claim(r, 'codex', 'x', {cites: [cite, 'b.md | l2 | words | with a bar']}).cites[1].excerpt, 'words | with a bar');
  assert.throws(() => co.create({mode: 'audit', title: 'a', question: 'audit it', members: 'claude,codex', lead: 'matt', as: 'matt'}), /--subject required for audit/);
  const a = co.create({mode: 'audit', title: 'a', question: 'audit it', members: 'claude,codex', lead: 'matt', subject: SUBJECT, as: 'matt'});
  assert.throws(() => co.add(a.id, 'codex', {text: 'x', severity: 'huge', location: 'f:1', evidence: 'e'}), /severity/); assert.throws(() => co.add(a.id, 'codex', {text: 'x', severity: 'high', evidence: 'e'}), /--location/);
  assert.equal(co.add(a.id, 'codex', {text: 'x', severity: 'high', location: 'f.ts:9', evidence: 'quoted line'}).strength, 'claimed');
  const d = co.create({mode: 'design', title: 'd', question: 'design it', members: 'claude,codex', lead: 'matt', as: 'matt'});
  assert.throws(() => co.add(d.id, 'codex', {text: 'x', rationale: 'r', tradeoffs: 't'}), /--risks/); assert.throws(() => co.add(d.id, 'codex', {type: 'claim', text: 'x'}), /proposals/);
  assert.throws(() => co.create({mode: 'build', title: 'b', question: 'b', members: 'claude,codex', lead: 'matt', as: 'matt'}), /--subject required for build/);
  const b = co.create({mode: 'build', title: 'b', question: 'b', members: 'claude,codex', lead: 'matt', subject: SUBJECT, as: 'matt'}); assert.throws(() => co.add(b.id, 'codex', {text: 'u', files: 'a.js'}), /--verification/); });
await t('an entry that looks like it holds a secret is refused', () => { const r = research();
  assert.throws(() => claim(r, 'codex', 'token ghp_' + 'A'.repeat(36)), /secret/); assert.equal(co.entries(r.id).length, 0); });
await t('build units own disjoint files: an overlapping unit, or a revision taking over another unit\'s file, is refused', () => {
  const b = co.create({mode: 'build', title: 'b', question: 'b', members: 'claude,codex', lead: 'matt', subject: SUBJECT, as: 'matt'}); const rcpt = 'npm test: exit 0, 4 passed';
  co.add(b.id, 'codex', {text: 'parser', files: 'src/parse.ts,src/parse.test.ts', verification: rcpt}); const mine = co.add(b.id, 'claude', {text: 'ui', files: 'src/ui.tsx', verification: rcpt});
  assert.throws(() => co.add(b.id, 'claude', {text: 'more', files: 'src/parse.ts', verification: rcpt}), /already belong.*src\/parse\.ts/);
  assert.throws(() => co.add(b.id, 'claude', {text: 'ui2', files: 'src/ui.tsx,src/parse.test.ts', verification: rcpt, revises: mine.id}), /already belong/);
  assert.equal(co.add(b.id, 'claude', {text: 'ui2', files: 'src/ui.tsx', verification: rcpt, revises: mine.id}).revises, mine.id); assert.ok(!co.check(b.id).findings.some(f => f.code === 'overlap')); });
await t('ready refuses until the phase\'s work is done; the last member to finish moves the project on', () => { const p = research();
  assert.throws(() => co.ready(p.id, 'codex'), /add at least one claim/); assert.throws(() => co.ready(p.id, 'matt'), /nothing to do/);
  claim(p, 'codex'); assert.throws(() => co.ready(p.id, 'codex'), /state your coverage/); cover(p, 'codex');
  assert.equal(co.ready(p.id, 'codex').advanced, false); assert.equal(co.load(p.id).phase, 'independent');
  claim(p, 'claude'); cover(p, 'claude'); const r = co.ready(p.id, 'claude'); assert.equal(r.advanced, true); assert.equal(r.phase, 'challenge'); assert.equal(co.load(p.id).phase, 'challenge'); });
await t('marking ready closes your notices for the phase, and the next phase sends new ones', () => { const p = research(); claim(p, 'codex'); claim(p, 'claude'); cover(p, 'codex'); cover(p, 'claude');
  co.ready(p.id, 'codex'); assert.equal(notices('codex').filter(m => m.thread === p.id).length, 0, 'codex\'s independent notice is done');
  co.ready(p.id, 'claude'); const next = notices('codex').filter(m => m.thread === p.id); assert.equal(next.length, 1); assert.match(next[0].subject, /phase challenge/); });
await t('a second advance of the same phase is refused, so racing members never double the notices', () => { const p = research(); claim(p, 'codex'); claim(p, 'claude'); cover(p, 'codex'); cover(p, 'claude');
  fs.writeFileSync(path.join(HOME, 'co', p.id, 'ready', 'advanced~independent'), 'another member got here first'); co.ready(p.id, 'codex');
  assert.equal(co.ready(p.id, 'claude').advanced, false); assert.equal(co.load(p.id).phase, 'independent'); });
await t('challenges: only in phase, never your own entry, a known kind; the quota blocks ready until met or passed', () => { const p = research({minChallenges: 2});
  assert.throws(() => co.challenge(p.id, 'codex', {target: 'E1', kind: 'missing', text: 'x'}), /challenge phase/); const {a, b} = toChallenge(p);
  assert.throws(() => co.challenge(p.id, 'codex', {target: a.id, kind: 'missing', text: 'x'}), /not your own/); assert.throws(() => co.challenge(p.id, 'codex', {target: b.id, kind: 'rude', text: 'x'}), /--kind/);
  co.challenge(p.id, 'codex', {target: b.id, kind: 'not-in-source', text: 'the excerpt is not at v2 section 3'}); assert.throws(() => co.ready(p.id, 'codex'), /at least 2.*1 so far/);
  co.pass(p.id, 'codex', {reason: 'one claim to attack'}); co.ready(p.id, 'codex'); assert.throws(() => co.pass(p.id, 'claude', {reason: ' '}), /--reason/); });
await t('respond: only the author answers; revise needs the revision first; concede overturns, revise revises', () => { const p = research(); const {a, b} = toChallenge(p);
  const c1 = co.challenge(p.id, 'codex', {target: b.id, kind: 'overstated', text: 'present, not tested'}); const c2 = co.challenge(p.id, 'claude', {target: a.id, kind: 'counter-evidence', text: 'newer source'});
  co.ready(p.id, 'codex'); co.ready(p.id, 'claude'); assert.equal(co.load(p.id).phase, 'respond');
  assert.throws(() => co.respond(p.id, 'codex', {target: c1.id, outcome: 'defend', text: 'x'}), /only the author/);
  assert.throws(() => co.respond(p.id, 'claude', {target: c1.id, outcome: 'revise', text: 'x'}), /--revises/);
  claim(p, 'claude', 'narrower claim', {revises: b.id}); co.respond(p.id, 'claude', {target: c1.id, outcome: 'revise', text: 'narrowed'}); co.respond(p.id, 'codex', {target: c2.id, outcome: 'concede', text: 'they are right'});
  const st = Object.fromEntries(co.state(co.load(p.id)).map(s => [s.id, s.status])); assert.equal(st[a.id], 'overturned'); assert.equal(st[b.id], 'revised');
  co.ready(p.id, 'codex'); assert.equal(co.ready(p.id, 'claude').phase, 'closed', 'no defended challenge: adjudicate is skipped'); });
await t('the judge rules on defended challenges but never on its own entry or challenge; those stay disputed', () => {
  const p = research({lead: 'claude', as: 'claude'}); assert.equal(p.judge, 'claude'); const {a, b} = toChallenge(p);
  const c1 = co.challenge(p.id, 'codex', {target: b.id, kind: 'weak-evidence', text: 'secondary only'}); co.challenge(p.id, 'claude', {target: a.id, kind: 'missing', text: 'gap'});
  co.ready(p.id, 'codex'); co.ready(p.id, 'claude'); for (const [as, c] of [['claude', c1]]) co.respond(p.id, as, {target: c.id, outcome: 'defend', text: 'it is primary'});
  co.respond(p.id, 'codex', {target: co.entries(p.id).find(e => e.type === 'challenge' && e.by === 'claude').id, outcome: 'defend', text: 'covered'});
  co.ready(p.id, 'codex'); assert.equal(co.ready(p.id, 'claude').phase, 'closed', 'the judge is a party to every dispute: nothing to adjudicate');
  assert.ok(co.state(co.load(p.id)).every(s => s.status === 'disputed'));
  const q = research({judge: 'grok'}); const x = toChallenge(q); const ch = co.challenge(q.id, 'codex', {target: x.b.id, kind: 'counter-evidence', text: 'newer'}); co.pass(q.id, 'claude', {reason: 'fine'});
  co.ready(q.id, 'codex'); co.ready(q.id, 'claude'); co.respond(q.id, 'claude', {target: ch.id, outcome: 'defend', text: 'no'}); co.ready(q.id, 'claude'); co.ready(q.id, 'codex');
  assert.equal(co.load(q.id).phase, 'adjudicate'); assert.throws(() => co.verdict(q.id, 'codex', {target: ch.id, outcome: 'dismissed', reason: 'mine'}), /only the judge/);
  assert.throws(() => co.ready(q.id, 'grok'), /rule on/); co.verdict(q.id, 'grok', {target: ch.id, outcome: 'sustained', reason: 'the newer source is primary'});
  assert.equal(co.state(co.load(q.id)).find(s => s.id === x.b.id).status, 'overturned'); assert.equal(co.ready(q.id, 'grok').phase, 'closed'); });
await t('the synthesis is the lead\'s, after adjudication; the report separates survived, overturned and disputed and scores each member', () => {
  const p = research(); const {a, b} = toChallenge(p); assert.throws(() => co.add(p.id, 'matt', {type: 'synthesis', text: 's'}), /after adjudication/);
  const c = co.challenge(p.id, 'codex', {target: b.id, kind: 'counter-evidence', text: 'refuted'}); co.pass(p.id, 'claude', {reason: 'codex claim checks out'}); co.ready(p.id, 'codex'); co.ready(p.id, 'claude');
  co.respond(p.id, 'claude', {target: c.id, outcome: 'concede', text: 'yes'}); co.ready(p.id, 'claude'); co.ready(p.id, 'codex'); assert.equal(co.load(p.id).phase, 'closed');
  assert.throws(() => co.add(p.id, 'codex', {type: 'synthesis', text: 's'}), /only the lead/); assert.throws(() => claim(p, 'codex'), /closed/);
  assert.equal(co.check(p.id).findings[0].code, 'no-synthesis'); co.add(p.id, 'matt', {type: 'synthesis', text: 'Codex claim holds; claude claim refuted.'}); co.ready(p.id, 'matt');
  const r = co.report(p.id); assert.deepEqual(r.survived.map(s => s.id), [a.id]); assert.deepEqual(r.overturned.map(s => s.id), [b.id]); assert.equal(r.disputed.length, 0);
  assert.deepEqual(r.scorecard.find(s => s.agent === 'codex'), {agent: 'codex', entries: 1, survived: 1, overturned: 0, challenges: 1, landed: 1});
  for (const h of ['## Synthesis', '## Survived (1)', '## Overturned (1)', '## Scorecard', '## Protocol check', '- clean']) assert.ok(r.markdown.includes(h), h);
  assert.match(r.markdown, /## Passes \(no challenge stood, with the reason\)\n- E\d+ by claude: codex claim checks out/, 'a pass reason reaches the report'); assert.equal(co.check(p.id).clean, true); });
await t('the lead (or matt) can force a stalled phase on; the skip is recorded and reported, not hidden', () => { const p = research(); claim(p, 'codex'); cover(p, 'codex'); co.ready(p.id, 'codex');
  assert.throws(() => co.advance(p.id, 'codex', 'impatient'), /only the lead/); assert.throws(() => co.advance(p.id, 'matt', ''), /--reason/);
  const r = co.advance(p.id, 'matt', 'claude went quiet'); assert.equal(r.phase, 'challenge'); assert.deepEqual(r.forced, ['claude']);
  const k = co.check(p.id); assert.ok(k.findings.some(f => f.code === 'forced' && /claude/.test(f.msg))); assert.equal(k.clean, true, 'a recorded skip alone is not a protocol failure'); });
await t('the protocol check flags unanswered challenges and unmet quotas once their phase has passed', () => { const p = research(); const {b} = toChallenge(p);
  co.challenge(p.id, 'codex', {target: b.id, kind: 'missing', text: 'gap'}); co.ready(p.id, 'codex'); co.advance(p.id, 'matt', 'claude never challenged'); co.advance(p.id, 'matt', 'claude never answered');
  const codes = co.check(p.id).findings.map(f => f.code); assert.ok(codes.includes('challenge-unanswered')); assert.ok(!codes.includes('quota-unmet'), 'a forced skip excuses the quota'); assert.equal(co.check(p.id).clean, false); });
await t('research and audit members state their coverage; the report shows it and the check flags a member who never did', () => {
  const a = co.create({mode: 'audit', title: 'a', question: 'audit it', members: 'claude,codex', lead: 'matt', subject: SUBJECT, as: 'matt'});
  co.add(a.id, 'codex', {text: 'x', severity: 'low', location: 'f.ts:1', evidence: 'quoted line'}); assert.throws(() => co.ready(a.id, 'codex'), /state your coverage/);
  co.add(a.id, 'codex', {type: 'coverage', text: 'src/auth/** read; error paths not traced'}); co.ready(a.id, 'codex');
  assert.throws(() => co.add(a.id, 'grok', {type: 'coverage', text: 'x'}), /not a member/); co.advance(a.id, 'matt', 'claude silent');
  const r = co.report(a.id); assert.match(r.markdown, /## Coverage\n- claude: \(no statement\)\n- codex: src\/auth\/\*\* read; error paths not traced/);
  assert.ok(!co.check(a.id).findings.some(f => f.code === 'no-coverage'), 'a forced skip of the independent phase excuses it');
  const d = co.create({mode: 'design', title: 'd', question: 'design it', members: 'claude,codex', lead: 'matt', as: 'matt'});
  co.add(d.id, 'codex', {text: 'x', rationale: 'r', tradeoffs: 't', risks: 'k'}); co.ready(d.id, 'codex'); assert.ok(!co.report(d.id).markdown.includes('## Coverage'), 'design does not require coverage'); });
await t('the brief is fixed and hashed when the project opens: an edited project.json is flagged, and audit and build show the pinned subject', () => {
  const a = co.create({mode: 'audit', title: 'a', question: 'audit it', members: 'claude,codex', lead: 'matt', subject: SUBJECT, as: 'matt'});
  assert.match(a.brief_sha256, /^[0-9a-f]{64}$/); assert.match(cp.load(notices('codex').find(m => m.thread === a.id).id).msg.body, /Subject \(pinned\): repo api@3f2c1ab/);
  assert.ok(co.check(a.id).clean); const f = path.join(HOME, 'co', a.id, 'project.json'); const j = JSON.parse(fs.readFileSync(f, 'utf8'));
  fs.writeFileSync(f, JSON.stringify({...j, question: 'audit something easier'})); const k = co.check(a.id); assert.ok(k.findings.some(x => x.code === 'brief-changed')); assert.equal(k.clean, false);
  assert.match(co.report(a.id).markdown, /\*\*Subject \(pinned\):\*\* repo api@3f2c1ab/); });
await t('a deviation proposes a change to the brief without editing it, and the report lists it apart', () => {
  const b = co.create({mode: 'build', title: 'b', question: 'b', members: 'claude,codex', lead: 'matt', subject: SUBJECT, scope: 'contract: exportRows(rows): string', as: 'matt'});
  const dv = co.add(b.id, 'codex', {type: 'deviation', text: 'exportRows needs an options argument for the delimiter'}); assert.equal(dv.type, 'deviation');
  assert.equal(co.load(b.id).scope, 'contract: exportRows(rows): string', 'the brief is unchanged'); assert.ok(co.check(b.id).clean);
  assert.match(co.report(b.id).markdown, /## Deviations proposed \(the brief was not changed\)\n- E1 by codex: exportRows needs an options argument/);
  co.advance(b.id, 'matt', 'go'); co.advance(b.id, 'matt', 'go'); co.advance(b.id, 'matt', 'go'); assert.throws(() => co.add(b.id, 'codex', {type: 'deviation', text: 'late'}), /project is closed/); });
await t('entries record the writer\'s session; the report names the sessions and says the blind phase is protocol only', () => { const p = research();
  claim(p, 'codex', 'c', {session: 'codex-thread-1'}); co.add(p.id, 'claude', {type: 'coverage', text: 'docs', session: 'claude-main'});
  assert.equal(co.entries(p.id)[0].session, 'codex-thread-1'); const md = co.report(p.id).markdown;
  assert.match(md, /blind by protocol, not by access control/); assert.match(md, /Sessions: claude \[claude-main\]; codex \[codex-thread-1\]/); });
await t('the research report groups claims by source and marks a source several members cite as one source', () => { const p = research();
  claim(p, 'codex', 'a', {cites: ['https://www.Example.org/docs/#v2 | s3 | x']}); claim(p, 'claude', 'b', {cites: ['http://example.org/docs | s4 | y', 'other.md | l1 | z']});
  const s = co.report(p.id).sources; assert.equal(s.length, 2); assert.deepEqual(s[0].by, ['codex', 'claude']); assert.deepEqual(s[0].entries, ['E1', 'E2']);
  assert.match(co.report(p.id).markdown, /one source, not independent corroboration[\s\S]*: E1, E2 \(cited by codex, claude\)/); });
await t('a phase notice takes no reply: reply is refused and points at co ready (a reply would leak into the shared thread)', () => { const p = research();
  const n = notices('claude').find(m => m.thread === p.id); assert.throws(() => cp.reply(n.id, {as: 'claude', body: 'my findings so far: ...', _noStdin: true}), /phase notice: it needs no reply[\s\S]*co ready/);
  assert.equal(cp.thread(p.id, 'matt').filter(m => m.kind === 'reply').length, 0, 'nothing was written');
  const q = cp.send({from: 'grok', to: 'claude', subject: 'ordinary ask', body: 'b', _noStdin: true}); assert.equal(cp.reply(q.id, {as: 'claude', body: 'ok', _noStdin: true}).kind, 'reply'); });
await t('in the blind phase a member reading the project thread sees only its own messages; a reader must say who it is', () => { const p = research();
  cp.send({from: 'codex', to: 'matt', thread: p.id, subject: 'note', body: 'codex independent findings', _noStdin: true});
  assert.ok(cp.thread(p.id, 'claude').every(m => m.from === 'claude' || m.to === 'claude'), 'claude sees no codex message');
  assert.ok(cp.thread(p.id, 'codex').some(m => m.body.includes('codex independent findings'))); assert.equal(cp.thread(p.id, 'matt').length, 3, 'the lead sees everything');
  assert.throws(() => cp.thread(p.id), /blind phase: pass --as/); co.advance(p.id, 'matt', 'open it'); assert.equal(cp.thread(p.id).length, 5, 'open after the blind phase');
  const b = co.create({mode: 'build', title: 'b', question: 'b', members: 'claude,codex', lead: 'matt', subject: SUBJECT, as: 'matt'}); assert.equal(cp.thread(b.id).length, 2, 'build mode is open'); });
await t('a citation keeps its excerpt verbatim: only the first two bars separate the fields', () => { const p = research();
  const e = claim(p, 'codex', 'x', {cites: ['host.mjs | line 10 | if (a || b) { c |= d; }', 'C:\\x\\a.md|l2|']}); assert.equal(e.cites[0].excerpt, 'if (a || b) { c |= d; }');
  assert.deepEqual(e.cites[1], {source: 'C:\\x\\a.md', location: 'l2', excerpt: null}); assert.throws(() => claim(p, 'codex', 'y', {cites: ['onlysource | ']}), /source and location required/); });
await t('sources cited by absolute and by relative path join, and a revision that only changed citations says so', () => { const p = research();
  const a = claim(p, 'codex', 'a', {cites: ['C:\\tmp\\run\\docs\\listener.md | line 75 | x']}); claim(p, 'claude', 'b', {cites: ['docs/listener.md | line 75 | x']});
  const s = co.report(p.id).sources; assert.equal(s.length, 1); assert.deepEqual(s[0].by, ['codex', 'claude']); assert.deepEqual(s[0].entries, ['E1', 'E2']);
  cover(p, 'codex'); cover(p, 'claude'); co.ready(p.id, 'codex'); co.ready(p.id, 'claude'); const c = co.challenge(p.id, 'claude', {target: a.id, kind: 'weak-evidence', text: 'excerpt garbled'});
  co.pass(p.id, 'codex', {reason: 'fine'}); co.ready(p.id, 'claude'); co.ready(p.id, 'codex'); claim(p, 'codex', 'a', {cites: ['C:\\tmp\\run\\docs\\listener.md | line 75 | exact words'], revises: a.id});
  co.respond(p.id, 'codex', {target: c.id, outcome: 'revise', text: 'fixed the excerpt'}); assert.match(co.report(p.id).markdown, /revised: same text; its citations or fields changed/); });
await t('a bad project id is refused before any path is built', () => { for (const id of ['../agents', 'co-short', 'co-' + 'U'.repeat(26)]) assert.throws(() => co.load(id), /bad project id/); });

await t('CLI: co new takes repeated --assign and co add repeated --cite; co check exits 1 on findings', () => {
  const r = cli('co', 'new', '--mode', 'research', '--title', 'cli', '--question', 'q?', '--members', 'claude,codex', '--as', 'matt', '--assign', 'codex: a', '--assign', 'claude: b', '--json');
  assert.equal(r.status, 0, r.stderr); const p = JSON.parse(r.stdout); assert.deepEqual(p.members.map(m => m.part), ['b', 'a']);
  const a = cli('co', 'add', p.id, '--as', 'codex', '--text', 't', '--strength', 'present', '--cite', 'x.md | 1 | e', '--cite', 'y.md | 2 | f', '--json'); assert.equal(a.status, 0, a.stderr);
  assert.equal(JSON.parse(a.stdout).cites.length, 2); const v = cli('co', 'view', p.id, '--as', 'claude'); assert.match(v.stdout, /part of codex: a/); assert.match(v.stdout, /1 entries by others are hidden/);
  co.advance(p.id, 'matt', 'claude added nothing'); co.challenge(p.id, 'claude', {target: JSON.parse(a.stdout).id, kind: 'weak-evidence', text: 'undated'});
  while (co.load(p.id).phase !== 'closed') co.advance(p.id, 'matt', 'skip'); co.add(p.id, 'matt', {type: 'synthesis', text: 's'});
  const k = cli('co', 'check', p.id); assert.equal(k.status, 1, 'an unanswered challenge fails the check'); assert.match(k.stdout, /challenge-unanswered/);
  const q = research(); while (co.load(q.id).phase !== 'closed') co.advance(q.id, 'matt', 'skip'); co.add(q.id, 'matt', {type: 'synthesis', text: 's'});
  assert.equal(cli('co', 'check', q.id).status, 0, 'forced skips alone leave the check clean'); });
await t('MCP: the co tools are listed and a co project can be opened and worked through them', () => {
  const lines = [{id: 1, method: 'initialize', params: {protocolVersion: '2025-06-18'}}, {id: 2, method: 'tools/list'},
    {id: 3, method: 'tools/call', params: {name: 'co_new', arguments: {mode: 'audit', title: 'm', question: 'q', members: ['claude', 'codex'], subject: SUBJECT, assign: ['codex: auth']}}}].map(x => JSON.stringify({jsonrpc: '2.0', ...x})).join('\n');
  const r = spawnSync('node', [path.join(BIN, 'carrier-pigeon-mcp.mjs'), '--as', 'matt'], {input: lines, env: process.env, encoding: 'utf8'}); const out = r.stdout.trim().split('\n').map(l => JSON.parse(l));
  const names = out[1].result.tools.map(x => x.name); for (const k of ['co_new', 'co_list', 'co_view', 'co_add', 'co_challenge', 'co_pass', 'co_respond', 'co_verdict', 'co_ready', 'co_report']) assert.ok(names.includes(k), k);
  assert.ok(out[1].result.tools.find(x => x.name === 'co_view').annotations?.readOnlyHint, 'co_view is read-only'); const p = JSON.parse(out[2].result.content[0].text);
  assert.equal(p.mode, 'audit'); assert.equal(p.lead, 'matt'); assert.equal(p.members.find(m => m.agent === 'codex').part, 'auth'); });

// The four sub-skills document this engine; keep them true to it.
const subSkills = Object.values(co.MODES).map(m => m.skill); const version = /^\s+version: "([^"]+)"/m.exec(fs.readFileSync(path.join(SKILL, 'SKILL.md'), 'utf8'))[1];
const read = s => fs.readFileSync(path.join(SKILL, 'skills', s, 'SKILL.md'), 'utf8');
await t('each mode has its sub-skill: same name as its folder, the parent\'s version, a routing description within 500 characters', () => {
  assert.deepEqual(fs.readdirSync(path.join(SKILL, 'skills')).sort(), [...subSkills].sort());
  for (const s of subSkills) { const front = /^---\n([\s\S]*?)\n---\n/.exec(read(s).replace(/\r\n/g, '\n'))[1];
    assert.equal(/^name: (.+)$/m.exec(front)[1], s); assert.equal(/^\s+version: "([^"]+)"/m.exec(front)[1], version, s + ' version'); assert.match(front, /^\s+parent: carrier-pigeon$/m);
    const desc = /^description: "(.+)"$/m.exec(front)[1]; assert.ok(desc.length <= 500, `${s} description ${desc.length} chars`); assert.match(desc, /carrier-pigeon sub-skill/); assert.match(desc, /Not for/); } });
await t('the sub-skills and references/co.md name only real co commands, MCP tools, kinds, strengths and severities', () => {
  const subs = new Set(['new', 'list', 'view', 'add', 'challenge', 'pass', 'respond', 'verdict', 'ready', 'advance', 'check', 'report']);
  const mcp = new Set([...fs.readFileSync(path.join(BIN, 'carrier-pigeon-mcp.mjs'), 'utf8').matchAll(/name: '(co_\w+)'/g)].map(m => m[1]));
  const docs = [...subSkills.map(s => [s, read(s)]), ['co.md', fs.readFileSync(path.join(SKILL, 'references', 'co.md'), 'utf8')]];
  for (const [name, text] of docs) {
    for (const [, sub] of text.matchAll(/`co ([a-z]+)\b/g)) assert.ok(subs.has(sub), `${name}: co ${sub}`);
    for (const [, sub] of text.matchAll(/^co ([a-z]+)\b/gm)) assert.ok(subs.has(sub), `${name}: co ${sub}`);
    for (const [, tool] of text.matchAll(/\b(co_[a-z]+)\b/g)) assert.ok(tool === 'co_' || mcp.has(tool), `${name}: ${tool}`);
    for (const [, kind] of text.matchAll(/--kind ([a-z-]+)/g)) assert.ok(co.CHALLENGE_KINDS.includes(kind), `${name}: kind ${kind}`);
    for (const [, s] of text.matchAll(/--strength ([a-z]+)\b/g)) assert.ok(co.MODES.research.strengths.includes(s), `${name}: strength ${s}`);
    for (const [, s] of text.matchAll(/--severity ([a-z]+)\b/g)) assert.ok(co.MODES.audit.severities.includes(s), `${name}: severity ${s}`); }
  const table = docs.at(-1)[1]; for (const k of co.CHALLENGE_KINDS) assert.ok(table.includes('`' + k + '`'), 'co.md lists kind ' + k); });
await t('the sub-skills never say "the user" or "the human" (the private edition must not have to rewrite them)', () => {
  for (const s of subSkills) assert.equal((read(s).match(/\bthe (user|human)\b/gi) || []).length, 0, s); });

fs.rmSync(HOME, {recursive: true, force: true}); console.log(`# ${n} tests, ${failed} failed (co)`); process.exit(failed ? 1 : 0);
