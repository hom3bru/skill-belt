// Local checks for the deep-dive draft. Sends nothing; uses Carrier Pigeon's own validator.
import fs from 'node:fs'; import path from 'node:path'; import { pathToFileURL, fileURLToPath } from 'node:url';
import { homedir } from 'node:os';
const validator = process.env.DEEP_DIVE_CP_VALIDATOR ?? path.join(process.env.USERPROFILE || homedir(), '.carrier-pigeon', 'bin', 'cp-tasks.mjs');
const { schemaInput, validateResult } = await import(pathToFileURL(path.resolve(validator)).href);
const root = path.resolve(process.argv[2] ?? fileURLToPath(new URL('../', import.meta.url)));
// Canonical sources nest children; a portable package exposes sibling skills.
const child = (name) => fs.existsSync(path.join(root, 'skills', name)) ? path.join(root, 'skills', name) : path.join(root, '..', name);
let run = 0, failed = 0;
const check = (name, fn) => { run++; try { fn(); console.log('PASS', name); } catch (e) { failed++; console.log('FAIL', name, '-', e.message); } };
const mustThrow = (name, fn) => check(name, () => { let threw = false; try { fn(); } catch { threw = true; } if (!threw) throw new Error('accepted a broken reply'); });

// 1. Schema accepted by Carrier Pigeon
const schemaPath = path.join(child('check-work'), 'references', 'reply-schema.json');
const schemaText = fs.readFileSync(schemaPath, 'utf8');
let schema;
check('schema under 8 KB (' + Buffer.byteLength(schemaText) + ' bytes)', () => { if (Buffer.byteLength(schemaText) > 8192) throw new Error('too big'); });
check('schemaInput accepts reply-schema.json', () => { schema = schemaInput(schemaText); if (!schema || schema.type !== 'object') throw new Error('bad'); });

// 2. A good reply passes
const finding = (i, over = {}) => ({ id: 'F' + i, severity: 'major', lens: 'evidence', section: '3 Top picks', quote: 'Licence: MIT', problem: 'LICENSE file is Apache-2.0', evidence: 'https://github.com/x/y/blob/main/LICENSE read 2026-11-05', checked_myself: true, smallest_fix: 'Correct the licence cell', changes_decision: false, ...over });
const counter = (i) => ({ id: 'C' + i, recommendation: 'Use Z instead', why: 'Active, permissive', evidence: 'https://github.com/z/z', beats_report_when: 'the user needs offline use', cost: 'Smaller community' });
const good = { verdict: 'fix-first', restatement: 'Claims Y is the best option for X as of Nov 2026.', own_answer: 'Z, then Y.',
  assumptions: [{ assumption: 'Y is maintained', section: '3', status: 'evidence-backed' }],
  findings: [finding(1), finding(2, { severity: 'minor', lens: 'recency' })], counter_recommendations: [counter(1)],
  questions: ['Does the user need offline use?'], held_up: ['Paper IDs verified'], not_checked: ['Reddit threads'] };
check('good reply validates', () => validateResult(good, schema));
check('good reply under 16 KB', () => { if (Buffer.byteLength(JSON.stringify(good)) > 16384) throw new Error('too big'); });
check('"holds" with no findings validates', () => validateResult({ ...good, verdict: 'holds', findings: [], counter_recommendations: [] }, schema));

// 3. Broken-copy controls: each must be rejected
const clone = (o) => JSON.parse(JSON.stringify(o));
mustThrow('rejects severity "nitpick"', () => validateResult({ ...good, findings: [finding(1, { severity: 'nitpick' })] }, schema));
mustThrow('rejects finding without evidence', () => { const g = clone(good); delete g.findings[0].evidence; validateResult(g, schema); });
mustThrow('rejects finding with empty quote', () => validateResult({ ...good, findings: [finding(1, { quote: '' })] }, schema));
mustThrow('rejects 11 findings', () => validateResult({ ...good, findings: Array.from({ length: 11 }, (_, i) => finding(i + 1)) }, schema));
mustThrow('rejects 4 counter-recommendations', () => validateResult({ ...good, counter_recommendations: [1, 2, 3, 4].map(counter) }, schema));
mustThrow('rejects verdict "lgtm"', () => validateResult({ ...good, verdict: 'lgtm' }, schema));
mustThrow('rejects extra property', () => validateResult({ ...good, rating: 9 }, schema));
mustThrow('rejects missing own_answer', () => { const g = clone(good); delete g.own_answer; validateResult(g, schema); });
mustThrow('rejects unknown lens', () => validateResult({ ...good, findings: [finding(1, { lens: 'style' })] }, schema));
mustThrow('rejects counter without evidence', () => { const g = clone(good); delete g.counter_recommendations[0].evidence; validateResult(g, schema); });

// A fully filled result, generated from the schema itself, must still fit Carrier Pigeon's 16 KB result cap
const maxOf = (s) => {
  if (s.enum) return s.enum.reduce((a, b) => String(b).length > String(a).length ? b : a);
  if (s.type === 'string') return 'x'.repeat(s.maxLength ?? 1000);
  if (s.type === 'boolean') return false;
  if (s.type === 'array') return Array.from({ length: s.maxItems ?? 20 }, () => maxOf(s.items));
  if (s.type === 'object') return Object.fromEntries(Object.entries(s.properties).map(([k, v]) => [k, maxOf(v)]));
  throw new Error('unhandled type ' + s.type);
};
const maxed = maxOf(schema); const maxedBytes = Buffer.byteLength(JSON.stringify(maxed));
check('fully filled result validates', () => validateResult(maxed, schema));
check('fully filled result fits 16 KB (' + maxedBytes + ' bytes)', () => { if (maxedBytes > 16384) throw new Error('over the cap'); });

// 4. Frontmatter
const skills = [['deep-dive', path.join(root, 'SKILL.md'), null], ['deeper-dive', path.join(child('deeper-dive'), 'SKILL.md'), 'deep-dive'], ['check-work', path.join(child('check-work'), 'SKILL.md'), 'deep-dive']];
for (const [name, file, parent] of skills) {
  const text = fs.readFileSync(file, 'utf8'); const fm = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  check(name + ' has frontmatter', () => { if (!fm) throw new Error('none'); });
  if (!fm) continue;
  check(name + ' name matches', () => { if (!new RegExp('^name: ' + name + '$', 'm').test(fm[1])) throw new Error('name'); });
  const desc = (fm[1].match(/^description: "(.*)"$/m) || [])[1] || '';
  check(name + ' description 1..1024 chars (' + desc.length + ')', () => { if (!desc || desc.length > 1024) throw new Error('length'); });
  check(name + ' version 0.1.0', () => { if (!/^  version: "0\.1\.0"$/m.test(fm[1])) throw new Error('version'); });
  if (parent) check(name + ' parent ' + parent, () => { if (!new RegExp('^  parent: ' + parent + '$', 'm').test(fm[1])) throw new Error('parent'); });
}

// 6. Accepted adopt-adapt transfers (T1-T18) are present; each check fails if its rule is removed
const R = (rel) => fs.readFileSync(rel.startsWith('skills/') ? path.join(child(rel.split('/')[1]), ...rel.split('/').slice(2)) : path.join(root, rel), 'utf8');
const transfers = [
  ['T1 exact window', 'SKILL.md', /Set an exact window before searching[\s\S]*previous report's cutoff[\s\S]*\*uncertain\*/],
  ['T2 dated event, older announcement not new', 'SKILL.md', /announcement of older work is not new/],
  ['T3 units never added', 'SKILL.md', /never add them into one total/],
  ['T4 query outcomes in SKILL', 'SKILL.md', /An error is not an empty result/],
  ['T4 query outcomes in coverage', 'references/coverage.md', /\*none in window\*[\s\S]*an error is not an empty result/],
  ['T5 checked and set aside', 'references/report.md', /checked and set aside/],
  ['T6 origin labels', 'SKILL.md', /\*measured here\*, \*author-reported\*[\s\S]*Documented is not running/],
  ['T7 baseline in SKILL', 'SKILL.md', /its baseline: repository, branch, commit/],
  ['T7 baseline in report', 'references/report.md', /project baseline/],
  ['T8 proxy trap', 'SKILL.md', /A proxy is not the decision/],
  ['T9 lane IDs and inventory', 'references/report.md', /IDs go by lane[\s\S]*\*\*Inventory\*\*/],
  ['T10 settling comparison', 'references/report.md', /comparison that would settle the choice/],
  ['T10 hands-on keeps failures', 'SKILL.md', /Keep failures; never retry/],
  ['T11 manifest', 'SKILL.md', /Write `manifest\.json` with each file's bytes and sha256/],
  ['T12 read depth', 'references/report.md', /N of M parts, blind spots/],
  ['T13 withdrawal of refuted attribution', 'SKILL.md', /record the withdrawal and keep the need/],
  ['T14 doubt pass per pick', 'SKILL.md', /a doubt pass: the best case against it/],
  ['T15 demonstrated vs anticipated', 'references/report.md', /\*demonstrated\*[\s\S]*\*anticipated\*[\s\S]*defaults to defer/],
  ['T16 extrapolation', 'SKILL.md', /call it extrapolation/],
  ['T17 falsifier and stop rule', 'SKILL.md', /what finding would change the answer, and a stop rule/],
  ['T18 summary per opened source (SKILL)', 'SKILL.md', /every source you open: URL, date read, a one-line summary/],
  ['T18 sources-opened table (coverage)', 'references/coverage.md', /Sources opened \| URL/],
  ['palette log-use on save', 'SKILL.md', /palette log-use <item> --project <slug> --purpose cited/],
  ['check-work coverage lens knows errors', 'skills/check-work/references/ask.md', /a query that errored is counted as empty/],
];
for (const [name, rel, re] of transfers) check('transfer ' + name, () => { if (!re.test(R(rel))) throw new Error('rule missing from ' + rel); });

// Public canonical content must stay anonymous and share the local profile contract.
const profileText = R('references/user-profile.md');
check('shared profile contract', () => {
  if (!profileText.includes('Personal values come from the local profile ~/.claude/skill-belt-profile.json if present; otherwise ask the user.')) throw new Error('profile contract missing');
});
for (const placeholder of ['research_root', 'palette_home', 'plans_dir', 'cp_home', 'projects_root']) {
  check('profile path ' + placeholder, () => { if (!profileText.includes('<' + placeholder + '>')) throw new Error('placeholder missing'); });
}
for (const [name, file] of skills) {
  check(name + ' links shared profile', () => {
    const text = fs.readFileSync(file, 'utf8');
    const link = text.match(/\[user profile\]\(([^)]+)\)/);
    if (!link || path.resolve(path.dirname(file), link[1]) !== path.join(root, 'references', 'user-profile.md')) throw new Error('shared profile link missing or incorrect');
  });
}

// 5. Relative links resolve
const mds = []; const walk = (d) => { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, e.name); if (e.isDirectory()) walk(p); else if (p.endsWith('.md')) mds.push(p); } }; walk(root);
if (!fs.existsSync(path.join(root, 'skills'))) { walk(child('deeper-dive')); walk(child('check-work')); }
for (const md of mds) {
  check('anonymous ' + path.relative(root, md), () => {
    if (/\bMatt\b|[A-Z]:\\Users\\|\/Users\/|\/home\//i.test(fs.readFileSync(md, 'utf8'))) throw new Error('personal name or home path');
  });
  const text = fs.readFileSync(md, 'utf8').replace(/```[\s\S]*?```/g, '');
  for (const m of text.matchAll(/\]\(([^)\s]+)\)/g)) {
    const target = m[1].split('#')[0]; if (!target || /^[a-z]+:/i.test(target)) continue;
    check('link ' + path.relative(root, md) + ' -> ' + target, () => { if (!fs.existsSync(path.resolve(path.dirname(md), target))) throw new Error('missing'); });
  }
}
console.log(`# ${run} tests, ${failed} failed`);
console.log(JSON.stringify({ total: run, passed: run - failed, failed, skipped: 0 }));
process.exit(failed ? 1 : 0);
