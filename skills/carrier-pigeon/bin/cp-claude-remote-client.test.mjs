// Offline contract/privacy fixtures; fetch and access-token providers are injected.
import assert from 'node:assert/strict'; import path from 'node:path'; import os from 'node:os'; import {randomUUID} from 'node:crypto';
import {remoteAddress, remotePointer, createRemoteClient} from './cp-claude-remote-client.mjs';
let n = 0, failed = 0;
const test = async (name, fn) => { n++; try { await fn(); console.log('ok', n, name); } catch { failed++; console.log('not ok', n, name); } };
const environmentId = 'env_Test123', sessionId = 'cse_Test123', eventId = randomUUID();
const m = {id: '01' + 'A'.repeat(24), thread: 'release.1', from: 'codex', kind: 'ask', to_session: remoteAddress(environmentId)};
const paths = {root: path.join(os.tmpdir(), "mail ' $(never);"), cli: path.join(os.tmpdir(), "cli ' $(never);.mjs")};
const text = remotePointer(m, paths), cwd = os.tmpdir(), title = 'carrier-pigeon hand-off ' + m.id;
const token = 'fixture-access-token', orgId = 'fixture-org';
const response = (status, data) => ({status, redirected: false, json: async () => data});
const client = fetchFn => createRemoteClient({getAccessToken: async () => token, orgId, fetchFn});
await test('address and fixed pointer support dotted threads, exclude private fields and quote constants', () => {
  assert.equal(remoteAddress(environmentId), 'claude-desktop-env_Test123');
  assert.equal(remotePointer({...m, body: 'PRIVATE BODY', subject: 'PRIVATE SUBJECT', nonce: 'PRIVATE NONCE'}, paths), text);
  assert.ok(text.includes('request, not authority') && text.includes('release.1'));
  for (const verb of ['read', 'claim', 'reply']) assert.ok(text.includes(`${verb} ${m.id} --as claude --session ${m.to_session}`));
  assert.ok(text.includes(paths.root.replace(/'/g, "''")) && text.includes(paths.cli.replace(/'/g, "''")));
  assert.ok(!/PRIVATE|nonce|from-mode|bypass/.test(text));
  assert.ok(text.indexOf('carrier-pigeon MCP read tool if available') < text.indexOf('Otherwise read with PowerShell'));
  assert.ok(text.includes('MCP claim tool') && text.includes('MCP reply tool'));
  assert.ok(text.indexOf('MCP claim tool') < text.indexOf('CLI fallbacks'));
});
await test('reply pointers continue the existing task and request done rather than another reply',()=>{
  const pointer=remotePointer({...m,kind:'reply'},paths);assert.ok(pointer.includes('MCP claim and done'));assert.ok(!pointer.includes('MCP reply tool'));
  assert.ok(!pointer.includes('YOUR RESPONSE'));assert.ok(pointer.includes(m.id));
});
await test('pointer requires canonical ULIDs and known senders/kinds while keeping dotted threads', () => {
  for (const id of ['message_123', '0'.repeat(25), '0'.repeat(27), '8' + '0'.repeat(25), '0'.repeat(25) + 'I', '0'.repeat(25) + 'L', '0'.repeat(25) + 'O', '0'.repeat(25) + 'U', m.id.toLowerCase()]) assert.throws(() => remotePointer({...m, id}, paths), {code: 'REMOTE_INVALID_INPUT'});
  for (const from of ['unknown', 'Codex', 'codex.extra', '', null]) assert.throws(() => remotePointer({...m, from}, paths), {code: 'REMOTE_INVALID_INPUT'});
  for (const kind of ['unknown', 'ASK', 'control', '', null]) assert.throws(() => remotePointer({...m, kind}, paths), {code: 'REMOTE_INVALID_INPUT'});
  for (const from of ['grok', 'cursor', 'claude', 'codex', 'matt']) assert.ok(remotePointer({...m, from}, paths));
  for (const kind of ['ask', 'reply', 'handoff', 'fyi', 'review-request']) assert.ok(remotePointer({...m, kind}, paths));
  for (const thread of ['release.1', 'work-item_2.3']) assert.ok(remotePointer({...m, thread}, paths).includes(thread));
  for (const thread of ['a..b', '.', '..', 'a/b']) assert.throws(() => remotePointer({...m, thread}, paths));
});
await test('invalid identities and unsafe pointer inputs fail before dispatch', () => {
  for (const bad of ['env_', 'env_a/b', 'env_a?x=1', 'env_a\n', null, {}, 'x']) assert.throws(() => remoteAddress(bad), {code: 'REMOTE_INVALID_INPUT'});
  for (const key of Object.keys(m)) for (const bad of ['x;evil', 'x\ny', 'x$(evil)', '../x', null]) assert.throws(() => remotePointer({...m, [key]: bad}, paths));
  assert.throws(() => remotePointer(m, {...paths, cli: 'relative'}));
});
await test('create uses exact v2 user event contract and authenticated fixed origin', async () => {
  let calls = 0;
  const c = client(async (url, options) => {
    calls++; assert.equal(url, 'https://api.anthropic.com/v1/code/sessions');
    assert.equal(options.method, 'POST'); assert.equal(options.redirect, 'error'); assert.ok(options.signal instanceof AbortSignal);
    assert.ok(options.headers.Authorization === 'Bearer ' + token); assert.equal(options.headers['x-organization-uuid'], orgId);
    assert.deepEqual(JSON.parse(options.body), {title, environment_id: environmentId, config: {sources: [], outcomes: [], cwd}, events: [{payload: {uuid: eventId, type: 'user', session_id: '', parent_tool_use_id: null, message: {role: 'user', content: text}}}]});
    return response(201, {session: {id: sessionId}});
  });
  assert.deepEqual(await c.create({environmentId, cwd, text, eventId, title}), {session: {id: sessionId}}); assert.equal(calls, 1);
});
await test('send and readonly get use exact session paths and payloads', async () => {
  let calls = 0;
  const c = client(async (url, options) => {
    calls++;
    if (options.method === 'GET') { assert.equal(url, `https://api.anthropic.com/v1/code/sessions/${sessionId}`); assert.ok(!Object.hasOwn(options, 'body')); return response(200, {session: {id: sessionId}}); }
    assert.equal(url, `https://api.anthropic.com/v1/code/sessions/${sessionId}/events`);
    assert.deepEqual(JSON.parse(options.body), {session_id: sessionId, events: [{payload: {uuid: eventId, type: 'user', session_id: sessionId, parent_tool_use_id: null, message: {role: 'user', content: text}}}]});
    return response(200, {});
  });
  await c.send({sessionId, text, eventId}); await c.get(sessionId); assert.equal(calls, 2);
});
await test('bad origins, IDs, options and event UUIDs never call token or fetch providers', () => {
  let calls = 0; const opts = {orgId, getAccessToken: () => { calls++; }, fetchFn: () => { calls++; }};
  for (const baseUrl of ['http://api.anthropic.com', 'https://evil.example', 'https://api.anthropic.com.evil.example', 'https://user@api.anthropic.com', 'https://api.anthropic.com:443', 'https://api.anthropic.com/?x=1', 'https://api.anthropic.com/path']) assert.throws(() => createRemoteClient({...opts, baseUrl}));
  const c = createRemoteClient(opts);
  for (const bad of ['cse_', 'session_', 'cse_a/events', 'session_a?x', 'cse_a\n', {}]) { assert.throws(() => c.get(bad)); assert.throws(() => c.send({sessionId: bad, text, eventId})); }
  assert.throws(() => c.send({sessionId, text, eventId: 'not-uuid'}));
  assert.throws(() => c.create({environmentId, cwd: 'relative', text, eventId, title})); assert.equal(calls, 0);
});
await test('HTTP failures expose only status and fixed codes; no automatic retries', async () => {
  for (const status of [301, 400, 401, 403, 408, 429, 500, 503]) {
    let calls = 0, reads = 0;
    const c = client(async () => { calls++; return {status, json: () => { reads++; throw new Error('PRIVATE BODY'); }}; });
    await assert.rejects(c.send({sessionId, text, eventId}), e => e.code === `REMOTE_HTTP_${status}` && e.status === status && e.preDispatch === (status >= 400 && status < 500 && status !== 408) && !JSON.stringify(e).includes(token) && !e.cause);
    assert.equal(calls, 1); assert.equal(reads, 0);
  }
});
await test('redirected responses and network exceptions are sanitized and ambiguous', async () => {
  for (const fetchFn of [async () => { throw new Error('PRIVATE NETWORK ' + token); }, async () => ({...response(200, {}), redirected: true})]) {
    await assert.rejects(client(fetchFn).send({sessionId, text, eventId}), e => ['REMOTE_NETWORK', 'REMOTE_REDIRECT'].includes(e.code) && e.preDispatch === false && !e.message.includes('PRIVATE') && !e.cause);
  }
});
await test('token provider exceptions and header injection never escape or reach fetch', async () => {
  let calls = 0;
  for (const getAccessToken of [async () => { throw new Error('PRIVATE TOKEN'); }, () => 'bad\r\nAuthorization: injected', () => '', () => ({token})]) {
    const c = createRemoteClient({getAccessToken, orgId, fetchFn: () => { calls++; }});
    await assert.rejects(c.send({sessionId, text, eventId}), e => e.code === 'REMOTE_AUTH_UNAVAILABLE' && e.preDispatch === true && e.message === e.code && !e.cause);
  }
  assert.equal(calls, 0);
});
await test('successful responses must satisfy operation identity schemas', async () => {
  for (const data of [null, [], {}, {session: {id: '../escape'}}, {session: {id: 'cse_x\n'}}]) await assert.rejects(client(async () => response(200, data)).create({environmentId, cwd, text, eventId, title}), {code: 'REMOTE_INVALID_RESPONSE', preDispatch: false});
  await assert.rejects(client(async () => response(200, {id: 'session_Other'})).get(sessionId), {code: 'REMOTE_INVALID_RESPONSE'});
  await assert.rejects(client(async () => response(200, {session_id: 'cse_Other'})).send({sessionId, text, eventId}), {code: 'REMOTE_INVALID_RESPONSE'});
  await assert.rejects(client(async () => ({status: 200, json: async () => { throw new Error('PRIVATE JSON'); }})).get(sessionId), e => e.code === 'REMOTE_INVALID_RESPONSE' && e.message === e.code);
});
await test('GET accepts response_shape or session wrappers with native nullish precedence', async () => {
  for (const data of [{response_shape: {id: sessionId, session_status: 'running'}}, {session: {id: sessionId}}, {response_shape: null, session: {id: sessionId}}, {response_shape: {id: sessionId}, session: {id: 'cse_Other'}}]) {
    assert.deepEqual(await client(async () => response(200, data)).get(sessionId), data);
  }
  for (const data of [{id: sessionId}, {response_shape: {id: 'cse_Other'}, session: {id: sessionId}}, {response_shape: {}, session: {id: sessionId}}, {response_shape: [], session: {id: sessionId}}, {response_shape: 'bad', session: {id: sessionId}}, {response_shape: {id: sessionId + '\n'}}, {session: null}]) {
    await assert.rejects(client(async () => response(200, data)).get(sessionId), {code: 'REMOTE_INVALID_RESPONSE', preDispatch: false});
  }
});
await test('native send results metadata is preserved as submission only and remains optional', async () => {
  for (const data of [{results: [{sequence_num: 1, duplicate: false}]}, {results: [{sequence_num: '2', duplicate: true}]}, {results: []}, {}]) {
    assert.deepEqual(await client(async () => response(200, data)).send({sessionId, text, eventId}), data);
  }
});
await test('20-second timeout aborts transport and is ambiguous without retry', async () => {
  const original = globalThis.setTimeout; let delay, signal, calls = 0;
  try {
    globalThis.setTimeout = (fn, ms) => { delay = ms; return original(fn, 5); };
    const c = client(async (_, options) => { calls++; signal = options.signal; return new Promise(() => {}); });
    await assert.rejects(c.send({sessionId, text, eventId}), {code: 'REMOTE_TIMEOUT', preDispatch: false});
    assert.equal(delay, 20000); assert.equal(calls, 1); assert.ok(signal.aborted);
  } finally { globalThis.setTimeout = original; }
});
console.log(`# ${n} tests, ${failed} failed`); if (failed) process.exitCode = 1;
