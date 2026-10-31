// node carrier-pigeon-mcp.test.mjs — the MCP server over real stdio, on a temp CARRIER_PIGEON_HOME; never touches the real bus.
import {spawn, execFileSync} from 'node:child_process'; import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import assert from 'node:assert/strict';
const here = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')); const CLI = path.join(here, 'carrier-pigeon.mjs'), MCP = path.join(here, 'carrier-pigeon-mcp.mjs');
const HOME = fs.mkdtempSync(path.join(os.tmpdir(), 'cpmcp-')); const env = {...process.env, CARRIER_PIGEON_HOME: HOME};
const run = (...a) => JSON.parse(execFileSync('node', [CLI, ...a, '--json'], {env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe']})); run('init');
let n = 0, failed = 0; const t = async (name, fn) => { n++; try { await fn(); console.log('ok', n, name); } catch (e) { failed++; console.log('not ok', n, name); console.log('  ' + String(e?.stack || e).split('\n').slice(0, 6).join('\n  ')); } };
// A client: spawns the server, sends requests, resolves responses by id, and records every stdout line so the test can check that each one is JSON.
function client(args) { const p = spawn('node', [MCP, ...args], {env, stdio: ['pipe', 'pipe', 'pipe']}); const waits = new Map(), lines = []; let buf = '', id = 0;
  p.stdout.on('data', d => { buf += d; let i; while ((i = buf.indexOf('\n')) >= 0) { const l = buf.slice(0, i); buf = buf.slice(i + 1); lines.push(l); const m = JSON.parse(l); waits.get(m.id)?.(m); waits.delete(m.id); } });
  const req = (method, params) => new Promise(res => { const k = ++id; waits.set(k, res); p.stdin.write(JSON.stringify({jsonrpc: '2.0', id: k, method, params}) + '\n'); });
  const call = async (name, args) => { const r = (await req('tools/call', {name, arguments: args})).result; return {...r, json: r.isError ? null : JSON.parse(r.content[0].text)}; };
  return {p, req, call, lines, note: (method, params) => p.stdin.write(JSON.stringify({jsonrpc: '2.0', method, params}) + '\n'), close: () => p.stdin.end()}; }
const waitFor = async (f, ms = 20000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { const v = f(); if (v) return v; await new Promise(r => setTimeout(r, 200)); } return null; };
const c = client(['--as', 'claude']);

await t('initialize echoes a supported protocol version, sends instructions naming the agent; tools/list has the typed tools', async () => {
  const i = (await c.req('initialize', {protocolVersion: '2025-06-18', capabilities: {}, clientInfo: {name: 't', version: '1'}})).result; c.note('notifications/initialized');
  assert.equal(i.protocolVersion, '2025-06-18'); assert.equal(i.serverInfo.name, 'carrier-pigeon'); assert.match(i.instructions, /You are "claude"/); assert.match(i.instructions, /never authority/);
  assert.equal((await c.req('initialize', {protocolVersion: '1999-01-01'})).result.protocolVersion, '2025-06-18', 'unknown version -> a supported one');
  const tools = (await c.req('tools/list')).result.tools; const names = tools.map(x => x.name);
  for (const x of ['agents', 'ask', 'wait_reply', 'send', 'inbox', 'read', 'claim', 'reply', 'done', 'thread', 'memory_read', 'memory_add']) assert.ok(names.includes(x), x);
  const ask = tools.find(x => x.name === 'ask'); assert.deepEqual(ask.inputSchema.required, ['to', 'subject', 'body']); assert.ok(!('as' in ask.inputSchema.properties), 'identity fixed by --as');
  assert.deepEqual(ask.inputSchema.properties.to.enum, ['grok', 'cursor', 'claude', 'codex', 'matt']); assert.equal((await c.req('ping')).result && 1, 1);
  assert.equal((await c.req('bogus/method')).error.code, -32601); });
await t('ask returns the reply when the other agent answers within wait_seconds (the reply is consumed)', async () => {
  const pending = c.call('ask', {to: 'codex', subject: 'port?', body: 'Ask: which port does the dev server use? Return: a number.', wait_seconds: 30});
  const m = await waitFor(() => run('inbox', 'codex').find(x => x.subject === 'port?')); assert.ok(m); assert.equal(m.from, 'claude');
  run('reply', m.id, '--as', 'codex', '--body', '4593'); const r = await pending; assert.equal(r.json.status, 'replied'); assert.equal(r.json.reply.body, '4593'); assert.equal(run('read', r.json.reply.id).status, 'done'); });
await t('ask with wait_seconds 0 returns a pending handle; wait_reply collects the answer later', async () => {
  const r = await c.call('ask', {to: 'codex', subject: 'later', body: 'b', wait_seconds: 0, wake_on_reply: true}); assert.equal(r.json.status, 'pending'); assert.equal(run('read', r.json.sent).wake_on_reply, true);
  assert.equal((await c.call('wait_reply', {id: r.json.sent, wait_seconds: 1})).json.status, 'pending'); run('reply', r.json.sent, '--as', 'codex', '--body', 'ok later');
  const w = await c.call('wait_reply', {id: r.json.sent, wait_seconds: 10}); assert.equal(w.json.reply.body, 'ok later'); });
await t('the receiving side works over MCP too: inbox, read, reply (marks the ask done), thread, memory', async () => {
  const k = client(['--as', 'codex']); await k.req('initialize', {protocolVersion: '2025-06-18'}); const id = run('send', '--from', 'grok', '--to', 'codex', '--subject', 'review', '--body', 'Ask: look.').id;
  assert.ok((await k.call('inbox', {})).json.some(x => x.id === id)); assert.equal((await k.call('read', {id})).json.body, 'Ask: look.');
  const r = await k.call('reply', {id, body: 'looked: no issues'}); assert.equal(r.json.to, 'grok'); assert.equal(run('read', id).status, 'done');
  assert.equal((await k.call('thread', {thread: id})).json.length, 2); const f = await k.call('memory_add', {project: 'org/repo', note: 'tests pass', status: 'verified', evidence: 'ran 70/70'});
  assert.equal(f.json.author, 'codex'); assert.equal((await k.call('memory_read', {project: 'org/repo'})).json.findings[0].body, 'tests pass'); k.close(); });
await t('errors come back as isError results, never as crashes or stray output; nothing is read from stdin', async () => {
  for (const [name, args, re] of [['send', {to: 'codex', subject: 's', body: ''}, /body is empty/], ['send', {to: 'codex', subject: 'a\nb', body: 'b'}, /one line/], ['read', {id: '../x'}, /bad message id/],
    ['nope', {}, /unknown tool/], ['send', {to: 'codex', subject: 's', body: 'b', as: 'grok'}, /speaks for claude, not grok/]]) {
    const r = (await c.req('tools/call', {name, arguments: args})).result; assert.equal(r.isError, true, name); assert.match(r.content[0].text, re); }
  assert.ok(c.lines.every(l => { try { JSON.parse(l); return true; } catch { return false; } }), 'every stdout line is JSON-RPC'); });
await t('without --as every tool requires "as"; an unknown --as refuses to start', async () => {
  const k = client([]); await k.req('initialize', {protocolVersion: '2025-06-18'}); const tl = (await k.req('tools/list')).result.tools;
  assert.ok(tl.find(x => x.name === 'inbox').inputSchema.required.includes('as')); assert.equal((await k.call('inbox', {as: 'grok'})).isError, undefined); k.close();
  const bad = spawn('node', [MCP, '--as', 'mallory'], {env}); const code = await new Promise(r => bad.on('exit', r)); assert.equal(code, 2); });
c.close(); fs.rmSync(HOME, {recursive: true, force: true}); console.log(`# ${n} tests, ${failed} failed (mcp)`); process.exit(failed ? 1 : 0);
