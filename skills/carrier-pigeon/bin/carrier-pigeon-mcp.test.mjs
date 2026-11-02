// node carrier-pigeon-mcp.test.mjs — the MCP server over real stdio, on a temp CARRIER_PIGEON_HOME; never touches the real bus.
import {spawn, execFileSync} from 'node:child_process'; import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import assert from 'node:assert/strict';
import net from 'node:net'; import {claudeInbox} from './cp-push.mjs';
const here = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')); const CLI = path.join(here, 'carrier-pigeon.mjs'), MCP = path.join(here, 'carrier-pigeon-mcp.mjs');
const HOME = fs.mkdtempSync(path.join(os.tmpdir(), 'cpmcp-')); const env = {...process.env, CARRIER_PIGEON_HOME: HOME};
// Never the operator's own Claude Code session: test servers would post test mail into it (cp-push.mjs). Tests that want an inbox pass a fake one.
for (const k of ['CLAUDE_CODE_MESSAGING_SOCKET', 'CLAUDE_CODE_MESSAGING_TOKEN', 'CLAUDE_CODE_SESSION_ID']) delete env[k];
const run = (...a) => JSON.parse(execFileSync('node', [CLI, ...a, '--json'], {env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe']})); run('init');
let n = 0, failed = 0; const t = async (name, fn) => { n++; try { await fn(); console.log('ok', n, name); } catch (e) { failed++; console.log('not ok', n, name); console.log('  ' + String(e?.stack || e).split('\n').slice(0, 6).join('\n  ')); } };
// A client: spawns the server, sends requests, resolves responses by id, and records every stdout line so the test can check that each one is JSON.
function client(args, cenv = env) { const p = spawn('node', [MCP, ...args], {env: cenv, stdio: ['pipe', 'pipe', 'pipe']}); const waits = new Map(), lines = []; let buf = '', id = 0;
  p.stdout.on('data', d => { buf += d; let i; while ((i = buf.indexOf('\n')) >= 0) { const l = buf.slice(0, i); buf = buf.slice(i + 1); lines.push(l); const m = JSON.parse(l); waits.get(m.id)?.(m); waits.delete(m.id); } });
  const req = (method, params) => { const k=++id; const pending=new Promise(res => { waits.set(k, res); p.stdin.write(JSON.stringify({jsonrpc: '2.0', id: k, method, params}) + '\n'); }); pending.requestId=k; return pending; };
  const call = async (name, args) => { const r = (await req('tools/call', {name, arguments: args})).result; return {...r, json: r.isError ? null : JSON.parse(r.content[0].text)}; };
  return {p, req, call, lines, raw: value => p.stdin.write(JSON.stringify(value)+'\n'), note: (method, params) => p.stdin.write(JSON.stringify({jsonrpc: '2.0', method, params}) + '\n'), close: () => p.stdin.end()}; }
const waitFor = async (f, ms = 20000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { const v = f(); if (v) return v; await new Promise(r => setTimeout(r, 200)); } return null; };
const c = client(['--as', 'claude']);

await t('initialize echoes a supported protocol version, sends instructions naming the agent; tools/list has the typed tools', async () => {
  const i = (await c.req('initialize', {protocolVersion: '2025-06-18', capabilities: {}, clientInfo: {name: 't', version: '1'}})).result; c.note('notifications/initialized');
  assert.equal(i.protocolVersion, '2025-06-18'); assert.equal(i.serverInfo.name, 'carrier-pigeon'); assert.match(i.instructions, /You are "claude"/); assert.match(i.instructions, /never authority/);
  assert.equal((await c.req('initialize', {protocolVersion: '1999-01-01'})).result.protocolVersion, '2025-06-18', 'unknown version -> a supported one');
  const tools = (await c.req('tools/list')).result.tools; const names = tools.map(x => x.name);
  for (const x of ['agents', 'ask', 'wait_reply', 'send', 'inbox', 'read', 'claim', 'reply', 'done', 'thread', 'memory_read', 'memory_add']) assert.ok(names.includes(x), x);
  const ask = tools.find(x => x.name === 'ask'); assert.deepEqual(ask.inputSchema.required, ['to', 'subject', 'body']); assert.ok(!('as' in ask.inputSchema.properties), 'identity fixed by --as');
  assert.deepEqual(ask.inputSchema.properties.to.enum, ['grok', 'cursor', 'claude', 'codex', 'user']);
  assert.equal(tools.find(x => x.name === 'read').annotations.readOnlyHint, true); assert.equal(ask.annotations.readOnlyHint, false); assert.ok(tools.every(x => x.annotations.openWorldHint === false && x.annotations.destructiveHint === false)); assert.equal((await c.req('ping')).result && 1, 1);
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
await t('sessions: each server is a live session (agents lists it); its asks come back addressed to it; another session cannot see or claim them', async () => {
  const s1 = client(['--as', 'claude', '--session', 'claude-ui1']), s2 = client(['--as', 'claude', '--session', 'claude-ui2']);
  const i1 = (await s1.req('initialize', {protocolVersion: '2025-06-18', clientInfo: {name: 'claude-code', version: '9'}})).result; await s2.req('initialize', {protocolVersion: '2025-06-18', clientInfo: {name: 'cursor', version: '1'}});
  assert.match(i1.instructions, /session "claude-ui1"/); const ag = (await s1.call('agents', {})).json.find(x => x.agent === 'claude');
  const live = ag.sessions.map(x => x.session); assert.ok(live.includes('claude-ui1') && live.includes('claude-ui2'), live.join()); assert.ok(live.some(s => /^claude-[0-9a-z]+$/.test(s) && !s.startsWith('claude-ui')), 'the suite client got an auto label');
  assert.ok(ag.sessions.some(x => x.client === 'claude-code'));
  const a = await s1.call('ask', {to: 'codex', subject: 'sess', body: 'b', wait_seconds: 0}); assert.equal(run('read', a.json.sent).from_session, 'claude-ui1');
  const rep = run('reply', a.json.sent, '--as', 'codex', '--body', 'only for ui1'); assert.equal(rep.to_session, 'claude-ui1');
  assert.ok(!(await s2.call('inbox', {})).json.some(x => x.id === rep.id), 'not in the other session\'s inbox'); assert.equal((await s2.call('claim', {id: rep.id})).isError, true);
  assert.equal((await s1.call('wait_reply', {id: a.json.sent, wait_seconds: 5})).json.reply.body, 'only for ui1');
  s2.close(); await new Promise(r => s2.p.on('exit', r)); assert.ok(!(await s1.call('agents', {})).json.find(x => x.agent === 'claude').sessions.some(x => x.session === 'claude-ui2'), 'a closed session drops out'); s1.close(); });
await t('MCP validates the advertised argument schema before sending anything', async () => {
  const before = run('inbox', 'codex').length;
  for (const args of [{to:'codex',subject:'s',body:'b',surprise:true}, {to:'codex',subject:'s',body:'b',wait_seconds:-1},
    {to:'codex',subject:'s',body:'b',wait_seconds:601}, {to:'codex',subject:'s',body:'b',wake_on_reply:'true'}]) {
    assert.equal((await c.call('ask',args)).isError,true,JSON.stringify(args));
  }
  assert.equal(run('inbox','codex').length,before,'invalid asks have no side effects');
  const k=client([]); await k.req('initialize',{protocolVersion:'2025-06-18'});
  const message=run('send','--from','grok','--to','codex','--subject','identity check','--body','b');
  assert.equal((await k.call('read',{id:message.id})).isError,true,'read also requires generic-server identity'); k.close(); });
await t('MCP carries exact handoff references and deadlines; structured results preserve text; receipts are readable', async () => {
  const source=path.join(HOME,'handoff.jsonl'); fs.writeFileSync(source,JSON.stringify({type:'user',message:{role:'user',content:'review this evidence'}})+'\n');
  const transcript=run('transcript','pack',source,'--as','claude').sha256;
  const fork='codex-thread-0001', sid='0f8fad5b-d9cb-469f-a165-70867728950e';
  const sent=await c.call('send',{to:'codex',subject:'exact handoff',body:'b',transcript,fork_codex_thread:fork,fork_claude_session:sid,due:'2030-01-01T00:00:00Z'});
  assert.equal(sent.isError,undefined); assert.deepEqual(sent.structuredContent,sent.json);
  const m=run('read',sent.json.id); assert.equal(m.transcript,transcript); assert.equal(m.fork_codex_thread,fork); assert.equal(m.fork_claude_session,sid); assert.equal(m.due,'2030-01-01T00:00:00Z');
  fs.mkdirSync(path.join(HOME,'receipts'),{recursive:true}); const record={ts:'2030-01-01T00:00:00Z',ev:'turn-failed',reason:'test'};
  fs.writeFileSync(path.join(HOME,'receipts',m.id+'.jsonl'),JSON.stringify(record)+'\n');
  const receipts=await c.call('receipts',{id:m.id}); assert.deepEqual(receipts.json,[record]); assert.deepEqual(receipts.structuredContent,{items:[record]});
  assert.equal((await c.call('receipts',{id:'../escape'})).isError,true);
  const bad=await c.call('send',{to:'codex',subject:'invalid fork',body:'b',fork_codex_thread:'--bad'}); assert.equal(bad.isError,true); });
await t('valid JSON that is not a request returns invalid-request and leaves the server usable', async () => {
  const k=client(['--as','codex']); await k.req('initialize',{protocolVersion:'2025-06-18'});
  for(const value of [null,[],17,'invalid']) k.raw(value);
  const errors=await waitFor(()=>{const all=k.lines.map(JSON.parse).filter(x=>x.id===null&&x.error?.code===-32600); return all.length===4?all:null;},2000);
  assert.ok(errors,'every malformed request receives -32600'); assert.deepEqual((await k.req('ping')).result,{}); k.close(); });
await t('MCP reliable asks replay one request and validate structured answers before closing it', async()=>{
  const requester=client(['--as','grok','--session','requester']), worker=client(['--as','codex','--session','builder']);
  try{ await requester.req('initialize',{protocolVersion:'2025-06-18'}); await worker.req('initialize',{protocolVersion:'2025-06-18'});
    const args={to:'codex',subject:'reliable MCP review',body:'Return the verified count.',request_key:'mcp-review-one',wait_seconds:0,
      timeout_seconds:120,effort:'low',reply_schema:{type:'object',required:['count'],properties:{count:{type:'number'}},additionalProperties:false}};
    const first=await requester.call('ask',args); assert.equal(first.isError,undefined,first.content?.[0]?.text); const id=first.json.ask;
    assert.equal((await requester.call('ask',args)).json.ask,id,'a repeated request key recovers its original message');
    assert.equal((await requester.call('ask',{...args,body:'different work'})).isError,true,'key reuse cannot silently change work');
    assert.equal((await requester.call('outbox',{request_key:args.request_key})).json[0].id,id);
    assert.equal((await worker.call('claim',{id})).isError,undefined);
    const beat=await worker.call('heartbeat',{id,progress:'Checked the requested fixture',lease_seconds:60}); assert.equal(beat.isError,undefined,beat.content?.[0]?.text);
    assert.equal((await worker.call('reply',{id,body:'bad answer',outcome:'completed',result:{count:'invented'}})).isError,true);
    assert.equal(run('read',id).status,'claimed','invalid structured data cannot close the ask');
    const result=await worker.call('reply',{id,body:'Count is 4',outcome:'completed',result:{count:4},evidence:['fixture count: 4']}); assert.equal(result.isError,undefined,result.content?.[0]?.text);
    const status=await requester.call('task_status',{id}); assert.equal(status.json.outcome,'completed'); assert.deepEqual(status.json.result,{count:4});
    assert.equal((await requester.call('wait_reply',{id,wait_seconds:0})).json.status,'replied');
    const blocked=await requester.call('ask',{...args,request_key:'mcp-review-blocked',subject:'blocked structured review'});
    const refused=await worker.call('reply',{id:blocked.json.ask,body:'Required input is unavailable.',outcome:'blocked'});
    assert.equal(refused.isError,undefined,'a failure outcome does not fabricate success-schema data');
    assert.equal((await requester.call('task_status',{id:blocked.json.ask})).json.outcome,'blocked');
  }finally{requester.close();worker.close();}
});
await t('MCP request keys recover ownership after restart and unclaimed cancellation becomes terminal',async()=>{
  const a=client(['--as','grok','--session','before-restart']),b=client(['--as','grok','--session','after-restart']);
  try{ await a.req('initialize',{protocolVersion:'2025-06-18'}); await b.req('initialize',{protocolVersion:'2025-06-18'});
    const args={to:'codex',subject:'recover after restart',body:'temporary work',request_key:'restart-key',wait_seconds:0};
    const sent=await a.call('ask',args),id=sent.json.ask; a.close();
    assert.equal((await b.call('task_status',{id})).isError,true,'ordinary session checks remain');
    assert.equal((await b.call('ask',args)).json.ask,id,'recovery is explicit through the same key');
    const cancel=await b.call('cancel',{id,request_key:args.request_key,reason:'This fixture is no longer needed'}); assert.equal(cancel.json.state,'cancelled');
    assert.equal((await b.call('wait_reply',{id,request_key:args.request_key,wait_seconds:0})).json.status,'cancelled');
    assert.equal((await b.call('outbox',{request_key:args.request_key})).json[0].terminal,true);
  }finally{if(!a.p.stdin.destroyed)a.close();b.close();}
});
await t('MCP cancellation stops a wait promptly while preserving the delivered request',async()=>{
  const k=client(['--as','grok','--session','cancel-wait']);
  try{ await k.req('initialize',{protocolVersion:'2025-06-18'});
    const pending=k.req('tools/call',{name:'ask',arguments:{to:'codex',subject:'cancel transport wait',body:'temporary work',request_key:'cancel-wait-key',wait_seconds:60}});
    const ask=await waitFor(()=>run('inbox','codex','--all-sessions').find(m=>m.subject==='cancel transport wait'),5000); assert.ok(ask);
    k.note('notifications/cancelled',{requestId:pending.requestId,reason:'client moved on'});
    let timer; const response=await Promise.race([pending,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('cancelled wait did not return')),3000);})]).finally(()=>clearTimeout(timer));
    const value=JSON.parse(response.result.content[0].text); assert.equal(value.status,'aborted'); assert.equal(value.ask,ask.id);
    assert.equal(run('read',ask.id).status,'unread','transport cancellation is not task cancellation');
    assert.equal((await k.call('outbox',{request_key:'cancel-wait-key'})).json[0].id,ask.id);
  }finally{k.close();}
});
await t('MCP transcript tools preserve verified context, report truncation, and refuse protected file reads',async()=>{
  const file=path.join(HOME,'tool-transcript.jsonl'); fs.writeFileSync(file,JSON.stringify({type:'user',message:{role:'user',content:'A detail that must survive the transfer'}})+'\n');
  const packed=await c.call('transcript_pack',{path:file}); assert.equal(packed.isError,undefined,packed.content?.[0]?.text);
  const h=packed.json.sha256,short=await c.call('transcript_read',{sha256:h,max_chars:20}); assert.equal(short.json.truncated,true); assert.equal(short.json.text.length,20);
  const full=await c.call('transcript_read',{sha256:h,max_chars:500000}); assert.equal(full.json.truncated,false); assert.match(full.json.text,/detail that must survive/);
  const checked=await c.call('transcript_verify',{sha256:h,text:full.json.text}); assert.equal(checked.isError,undefined); assert.equal(checked.json.matched_records.length,full.json.canaries);
  const protectedFile=path.join(HOME,'.env');fs.writeFileSync(protectedFile,fs.readFileSync(file));
  assert.equal((await c.call('transcript_pack',{path:protectedFile})).isError,true);
  assert.match((await c.call('transcript_pack',{path:HOME})).content[0].text,/regular local file/);
  assert.equal((await c.call('transcript_pack',{path:file,repo:'//fixture-server/share'})).isError,true,'capture provenance cannot contact a remote repository');
  assert.equal((await c.call('transcript_read',{sha256:h,message_id:'../escape'})).isError,true);
});
// doctor reads installed code from the mailbox's bin/cp-context.mjs. This fixture mailbox is initialised without install, so that file starts
// absent; the tests write it to cover matching and newer installed versions, and fake a live listener with this process's pid.
const LOADED = run('version').version;
const snap = (root, skip = []) => { if (!fs.existsSync(root)) return null; const l = []; const visit = d => { for (const f of fs.readdirSync(d).sort()) { const p = path.join(d, f), rel = path.relative(root, p);
  if (skip.some(s => rel === s || rel.startsWith(s + path.sep))) continue; const s = fs.statSync(p); l.push([rel, s.mtimeMs, s.isFile() ? fs.readFileSync(p, 'base64') : 'dir']); if (s.isDirectory()) visit(p); } }; visit(root); return l; };
const installed = v => { fs.mkdirSync(path.join(HOME, 'bin'), {recursive: true}); fs.writeFileSync(path.join(HOME, 'bin', 'cp-context.mjs'), v); };
const listener = routes => { fs.mkdirSync(path.join(HOME, 'host'), {recursive: true}); fs.writeFileSync(path.join(HOME, 'host', 'host.lock'), String(process.pid));
  fs.writeFileSync(path.join(HOME, 'host', 'presence.json'), JSON.stringify({pid: process.pid, routes: Object.fromEntries(Object.keys(routes).map(a => [a, [a + '-adapter']])),
    adapters: Object.fromEntries(Object.entries(routes).map(([a, state]) => [a + '-adapter', {state, wakes: true}]))})); };
const dcheck = (d, code) => d.json.checks.find(x => x.code === code);
await t('MCP doctor reports version/session and whether installed code needs a reconnect',async()=>{
  // sessions/ is the transport's own bookkeeping (refreshed on tool calls); everything else must stay byte-identical.
  const before=snap(HOME,['sessions']); const d=await c.call('doctor',{});assert.equal(d.isError,undefined);
  for(const k of ['loaded_version','installed_version','needs_reconnect','agent','session','root','agents','initialized','health','checks']) assert.ok(Object.hasOwn(d.json,k),k);
  assert.equal(d.json.loaded_version,LOADED);assert.equal(d.json.agent,'claude');assert.ok(d.json.session);assert.equal(d.json.root,HOME);assert.equal(d.json.agents.length,5);
  assert.equal(d.json.installed_version,null,'no installed code in an init-only fixture');assert.equal(d.json.needs_reconnect,false);assert.equal(d.json.initialized,true);
  assert.equal(d.json.health,'attention');assert.equal(dcheck(d,'version').status,'warning');assert.ok(dcheck(d,'version').next_action);assert.equal(dcheck(d,'mailbox').status,'ok');
  assert.deepEqual(d.json.checks.map(x=>x.code),['mailbox','version','listener','agent:claude','agent:codex']);assert.deepEqual(d.structuredContent,d.json);
  installed(`export const VERSION = '${LOADED}';\n`);const m=await c.call('doctor',{});assert.equal(m.json.installed_version,LOADED);assert.equal(m.json.needs_reconnect,false);assert.equal(dcheck(m,'version').status,'ok');
  installed("export const VERSION = '999.0.0';\n");const o=await c.call('doctor',{});assert.equal(o.json.installed_version,'999.0.0');assert.equal(o.json.needs_reconnect,true,'loaded code is older than installed');assert.match(dcheck(o,'version').next_action,/[Rr]econnect/);
  installed('export const VERSION = computeIt();\n');const x=await c.call('doctor',{});assert.equal(x.json.installed_version,null);assert.equal(x.json.needs_reconnect,false);
  fs.rmSync(path.join(HOME,'bin'),{recursive:true});assert.deepEqual(snap(HOME,['sessions']),before,'doctor changed mailbox files');
});
await t('MCP doctor: listener and claude/codex readiness come from the shared checks (ready, not-ready, pull)',async()=>{
  installed(`export const VERSION = '${LOADED}';\n`);
  try{ listener({claude:'ready',codex:'ready'}); const before=snap(HOME,['sessions']); const r=await c.call('doctor',{});
    assert.equal(r.json.health,'ready');assert.ok(r.json.checks.every(x=>x.status==='ok'&&x.next_action===null));assert.equal(r.json.agents.find(a=>a.agent==='codex').reach,'auto-wake');
    listener({codex:'starting'}); const u=await c.call('doctor',{}); assert.equal(u.json.health,'attention');assert.equal(dcheck(u,'listener').status,'ok');
    assert.match(dcheck(u,'agent:codex').message,/auto-wake \(not ready\)/);assert.match(dcheck(u,'agent:claude').message,/pull/);assert.ok(dcheck(u,'agent:claude').next_action);
    fs.rmSync(path.join(HOME,'host','host.lock')); const p=await c.call('doctor',{}); assert.equal(dcheck(p,'listener').status,'warning');assert.ok(p.json.agents.every(a=>a.reach==='pull'));
    assert.deepEqual(snap(HOME,['sessions']).filter(([f])=>!f.startsWith('host')),before.filter(([f])=>!f.startsWith('host')),'doctor changed mailbox files');
  }finally{ fs.rmSync(path.join(HOME,'host'),{recursive:true,force:true}); fs.rmSync(path.join(HOME,'bin'),{recursive:true,force:true}); }
});
await t('MCP doctor works before init and never creates the mailbox (unbound and bound servers)',async()=>{
  const root=path.join(HOME,'..',path.basename(HOME)+'-uninit'), e={...env,CARRIER_PIGEON_HOME:root};
  const u=client([],{...e,CARRIER_PIGEON_AS:'',CARRIER_PIGEON_SESSION:''}), b=client(['--as','codex','--session','doctor-noinit'],e);
  try{ await u.req('initialize',{protocolVersion:'2025-06-18'});
    const d=await u.call('doctor',{as:'codex'});assert.equal(d.isError,undefined,d.content?.[0]?.text);assert.equal(d.json.health,'uninitialized');assert.equal(d.json.initialized,false);
    assert.deepEqual(d.json.agents,[]);assert.equal(d.json.agent,null);assert.equal(d.json.loaded_version,LOADED);assert.ok(dcheck(d,'mailbox').next_action);
    assert.equal(fs.existsSync(root),false,'an unbound doctor call must not create the root');
    await b.req('initialize',{protocolVersion:'2025-06-18'}); const before=snap(root);
    const s=await b.call('doctor',{});assert.equal(s.json.health,'uninitialized');assert.equal(s.json.agent,'codex');assert.equal(s.json.session,'doctor-noinit');
    assert.equal(fs.existsSync(path.join(root,'log.jsonl')),false);assert.equal(fs.existsSync(path.join(root,'agents')),false);assert.deepEqual(snap(root,['sessions']),before.filter(([f])=>!f.startsWith('sessions')));
    const bad=await b.call('doctor',{as:'grok'});assert.equal(bad.isError,true,'a bound server keeps its typed identity');
  }finally{ u.close(); b.close(); await new Promise(r=>setTimeout(r,300)); fs.rmSync(root,{recursive:true,force:true}); }
});
await t('MCP remembers claim generations and fences a stale connection even after the winner replies',async()=>{
  const a=client(['--as','codex','--session','fenced-worker']),b=client(['--as','codex','--session','fenced-worker']);
  try{await a.req('initialize',{protocolVersion:'2025-06-18'});await b.req('initialize',{protocolVersion:'2025-06-18'});
    const sent=await c.call('ask',{to:'codex',subject:'claim generation fixture',body:'inspect this fixture only',wait_seconds:0});const id=sent.json.ask;
    assert.equal((await a.call('claim',{id})).isError,undefined);assert.equal((await a.call('heartbeat',{id,progress:'Inspecting fixture',lease_seconds:1})).isError,undefined);
    await new Promise(r=>setTimeout(r,1100));const reclaimed=await b.call('reclaim',{id,reason:'Verified this isolated fixture has no partial effects'});assert.equal(reclaimed.isError,undefined,reclaimed.content?.[0]?.text);
    assert.equal((await a.call('reply',{id,body:'stale answer'})).isError,true);
    assert.equal((await b.call('heartbeat',{id,progress:'Continuing after deliberate takeover'})).isError,undefined,'current token is remembered without model plumbing');
    assert.equal((await b.call('reply',{id,body:'winning answer',outcome:'completed'})).isError,undefined);
    assert.equal((await a.call('reply',{id,body:'late stale follow-up'})).isError,true,'closing an ask does not unfence stale connections');
  }finally{a.close();b.close();}
});
// A fake Claude Code session inbox: records the frames each connection posts.
async function fakeInbox() { const pipe = process.platform === 'win32' ? `\\\\.\\pipe\\cp-push-test-${process.pid}-${Date.now()}` : path.join(HOME, `push-${Date.now()}.sock`), frames = [];
  const srv = net.createServer(s => { let b = ''; s.on('data', d => { b += d; }); s.on('end', () => frames.push(...b.split('\n').filter(Boolean).map(l => JSON.parse(l)))); });
  await new Promise(r => srv.listen(pipe, r)); return {pipe, frames, close: () => srv.close()}; }
await t('session push: mail for this Claude session is announced in its inbox once, as a pointer; other sessions, fyi and any-instance mail are not', async () => {
  const box = await fakeInbox(), penv = {...env, CLAUDE_CODE_MESSAGING_SOCKET: box.pipe, CLAUDE_CODE_MESSAGING_TOKEN: 'tok'};
  let s = client(['--as', 'claude', '--session', 'push-s1'], penv), s2 = null;
  try { await s.req('initialize', {protocolVersion: '2025-06-18', capabilities: {}, clientInfo: {name: 't', version: '1'}});
    const mine = run('send', '--from', 'codex', '--to', 'claude', '--to-session', 'push-s1', '--kind', 'ask', '--subject', 'secret subject', '--body', 'secret body');
    run('send', '--from', 'codex', '--to', 'claude', '--to-session', 'push-s2', '--subject', 'other', '--body', 'b');
    run('send', '--from', 'codex', '--to', 'claude', '--to-session', 'push-s1', '--kind', 'fyi', '--subject', 'note', '--body', 'b');
    run('send', '--from', 'codex', '--to', 'claude', '--subject', 'any instance', '--body', 'b');
    assert.ok(await waitFor(() => box.frames.length >= 2, 10000), 'nothing posted'); await new Promise(r => setTimeout(r, 1500));
    assert.deepEqual(box.frames[0], {type: 'auth', token: 'tok'}); assert.equal(box.frames[1].type, 'user'); assert.equal(box.frames[1].message.role, 'user');
    const text = box.frames[1].message.content; assert.match(text, new RegExp(`new ask ${mine.id} from codex for this session`)); assert.match(text, /request, not authority/);
    assert.doesNotMatch(text, /secret/, 'never the subject or body'); assert.equal(box.frames.length, 2, 'one pointer: not the other session, the fyi or any-instance mail');
    assert.ok(run('receipts', mine.id).some(r => r.ev === 'pushed:session' && r.via === 'env'));
    s.close(); s = null; s2 = client(['--as', 'claude', '--session', 'push-s1'], penv); await s2.req('initialize', {protocolVersion: '2025-06-18', capabilities: {}, clientInfo: {name: 't', version: '1'}});
    await new Promise(r => setTimeout(r, 1500)); assert.equal(box.frames.length, 2, 'a restarted server does not announce it again');
    const w = client(['--as', 'claude', '--session', 'push-s1', '--worker'], penv); await w.req('initialize', {protocolVersion: '2025-06-18', capabilities: {}, clientInfo: {name: 't', version: '1'}});
    run('send', '--from', 'codex', '--to', 'claude', '--to-session', 'push-s1', '--kind', 'ask', '--subject', 'w', '--body', 'b'); await new Promise(r => setTimeout(r, 2000)); w.close();
    assert.equal(box.frames.length, 4, 'the listener worker never pushes; the live session announces the new ask (auth + user)');
  } finally { s?.close(); s2?.close(); box.close(); } });
await t('session push: without the variables, the inbox comes from Claude Code\'s registry by session id, with the peer token', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cpreg-')), sessions = path.join(dir, 'sessions'); fs.mkdirSync(sessions);
  fs.writeFileSync(path.join(sessions, '4242.json'), JSON.stringify({pid: 4242, sessionId: 'sess-a', messagingSocketPath: 'PIPE-A'}));
  fs.writeFileSync(path.join(sessions, '4242.abc.key'), JSON.stringify({peerToken: 'peer-a'})); fs.writeFileSync(path.join(sessions, '7.json'), JSON.stringify({pid: 7, sessionId: 'sess-b'}));
  try { assert.deepEqual(claudeInbox({CLAUDE_CODE_SESSION_ID: 'sess-a', CLAUDE_CONFIG_DIR: dir}), {path: 'PIPE-A', token: 'peer-a', via: 'registry'});
    assert.equal(claudeInbox({CLAUDE_CODE_SESSION_ID: 'sess-b', CLAUDE_CONFIG_DIR: dir}), null, 'a session with no inbox'); assert.equal(claudeInbox({}), null);
    assert.deepEqual(claudeInbox({CLAUDE_CODE_MESSAGING_SOCKET: 'S', CLAUDE_CODE_MESSAGING_TOKEN: 'T', CLAUDE_CODE_SESSION_ID: 'sess-a', CLAUDE_CONFIG_DIR: dir}), {path: 'S', token: 'T', via: 'env'});
  } finally { fs.rmSync(dir, {recursive: true, force: true}); } });
c.close(); fs.rmSync(HOME, {recursive: true, force: true}); console.log(`# ${n} tests, ${failed} failed (mcp)`); process.exit(failed ? 1 : 0);
