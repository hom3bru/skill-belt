// node carrier-pigeon.test.mjs  — uses a temp CARRIER_PIGEON_HOME; never touches the real bus.
import {execFileSync,spawn,spawnSync} from 'node:child_process'; import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import assert from 'node:assert/strict';
const CLI=path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1')),'carrier-pigeon.mjs');
const HOME=fs.mkdtempSync(path.join(os.tmpdir(),'abtest-')); const env={...process.env,CARRIER_PIGEON_HOME:HOME};
const run=(...a)=>JSON.parse(execFileSync('node',[CLI,...a,'--json'],{env,encoding:'utf8',stdio:['ignore','pipe','pipe']}));
const runIn=(cwd,...a)=>JSON.parse(execFileSync('node',[CLI,...a,'--json'],{env,cwd,encoding:'utf8',stdio:['ignore','pipe','pipe']}));
const fail=(...a)=>{ try{ execFileSync('node',[CLI,...a],{env,stdio:['ignore','pipe','pipe']}); }catch(e){ return e.stderr.toString(); } assert.fail('expected failure: '+a.join(' ')); };
// A failing test is reported as "not ok" and the suite carries on, so one failure can't hide the tests after it.
let n=0, failed=0; const report=(name,e)=>{ if(!e) return console.log('ok',n,name); failed++; console.log('not ok',n,name); console.log('  '+String(e?.stack||e).split('\n').slice(0,6).join('\n  ')); };
const t=(name,fn)=>{ n++; try{ fn(); report(name); }catch(e){ report(name,e); } };
const ta=async(name,fn)=>{ n++; try{ await fn(); report(name); }catch(e){ report(name,e); } };
run('init');
t('send lands in inbox, no tmp files', ()=>{ const m=run('send','--from','grok','--to','claude','--subject','hi','--body','ask: say "x"\n---\nline');
  assert.equal(run('inbox','claude')[0].id,m.id); assert.deepEqual(fs.readdirSync(path.join(HOME,'agents/claude/inbox')).filter(f=>f.startsWith('.')),[]);
  assert.equal(run('read',m.id).body,'ask: say "x"\n---\nline'); });
t('validation errors are clear', ()=>{ assert.match(fail('send','--from','bob','--to','claude','--subject','s','--body','b'),/unknown agent "bob"/);
  assert.match(fail('send','--from','grok','--to','claude','--subject','s','--body','key sk-abcdefghijklmnopqrstuvwx'),/secret/); });
t('claim, reply, thread, done', ()=>{ const id=run('inbox','claude')[0].id; assert.equal(run('claim',id,'--as','claude').status,'claimed');
  assert.match(fail('claim',id,'--as','claude'),/not in claude's inbox/); const r=run('reply',id,'--as','claude','--body','claude here');
  assert.equal(r.to,'grok'); assert.equal(r.reply_to,id); const th=run('thread',id); assert.equal(th.length,2); assert.equal(th[0]._box,'claude/done'); assert.equal(run('inbox','grok').length,1); });
t('ids are time-sortable and unique', ()=>{ const ids=Array.from({length:20},(_,i)=>run('send','--from','matt','--to','codex','--subject','s'+i,'--body','b').id);
  assert.deepEqual([...ids].sort(),ids); assert.equal(new Set(ids).size,20); });
await ta('8 concurrent claims -> exactly 1 winner', async()=>{ const id=run('send','--from','grok','--to','codex','--subject','race','--body','b').id;
  const res=await Promise.all(Array.from({length:8},()=>new Promise(r=>{const p=spawn('node',[CLI,'claim',id,'--as','codex'],{env}); p.on('exit',c=>r(c));})));
  assert.equal(res.filter(c=>c===0).length,1,'exactly one claimer wins: '+res); assert.equal(res.filter(c=>c===2).length,7); });
t('run prints but does not execute', ()=>{ const id=run('inbox','codex')[0].id; const s=execFileSync('node',[CLI,'run',id],{env,encoding:'utf8'}); assert.match(s,/NOT executed/); assert.match(s,/codex exec/); });
t('context pack round-trips and read shows it', ()=>{ const cf=path.join(HOME,'ctx.txt'); fs.writeFileSync(cf,'decided: use plan B');
  const m=run('send','--from','grok','--to','codex','--subject','pk','--body','b','--summary','short sum','--files','a.js,b/c.md','--refs','01X,01Y','--context-file',cf);
  const r=run('read',m.id); assert.match(r.context,/Summary: short sum/); assert.match(r.context,/- b\/c\.md/); assert.match(r.context,/- 01Y/); assert.match(r.context,/plan B/); assert.equal(r.body,'b');
  const txt=execFileSync('node',[CLI,'read',m.id],{env,encoding:'utf8'}); assert.match(txt,/## Context pack/); assert.ok(run('inbox','codex').find(x=>x.id===m.id).has_context);
  assert.equal(run('send','--from','grok','--to','codex','--subject','np','--body','b').context,null); });
t('context pack cap and secret rejection', ()=>{ const big=path.join(HOME,'big.txt'); fs.writeFileSync(big,'x'.repeat(9000));
  assert.match(fail('send','--from','grok','--to','codex','--subject','s','--body','b','--context-file',big),/cap is 8192/);
  assert.match(fail('send','--from','grok','--to','codex','--subject','s','--body','b','--summary','token ghp_abcdefghijklmnopqrstuvwxyz12'),/context pack looks like it contains a secret/); });
t('memory: instructions are human-only; findings record provenance; list', ()=>{ assert.equal(run('memory','read','Org/Repo').instructions,null);
  assert.match(fail('memory','instructions','Org/Repo','--as','codex','--text','x'),/only matt/); run('memory','instructions','Org/Repo','--as','matt','--text','Run tests with node.');
  const src=path.join(HOME,'src.txt'); fs.writeFileSync(src,'v1');
  const f=run('memory','add','Org/Repo','--as','grok','--note','parser bug fixed','--repo','org/repo','--sha','abc123','--files',src+',other/x.js@'+'a'.repeat(64),'--sources','PR#3','--status','verified','--evidence','tests: all 11 passed');
  assert.equal(f.project,'org-repo'); assert.ok(fs.existsSync(path.join(HOME,'memory','org-repo','findings',f.id+'.md')));
  const r=run('memory','read','org-repo'); assert.match(r.instructions,/Run tests/); const x=r.findings[0]; assert.equal(x.author,'grok'); assert.equal(x.sha,'abc123'); assert.equal(x.effective,'verified');
  assert.equal(x.files[0].sha256.length,64); assert.deepEqual(x.unchecked,['other/x.js']); assert.match(x.evidence,/11 passed/);
  const txt=execFileSync('node',[CLI,'memory','read','org-repo'],{env,encoding:'utf8'}); assert.match(txt,/instructions[\s\S]*Run tests[\s\S]*\[verified\][\s\S]*evidence: tests/);
  assert.match(fail('memory','add','org-repo','--as','grok','--note','n','--status','verified'),/needs --evidence/);
  assert.match(fail('memory','add','x','--as','grok','--note','AKIAABCDEFGHIJKLMNOP'),/secret/); assert.match(fail('memory','add','x','--as','bob','--note','n'),/unknown agent/);
  assert.deepEqual(run('memory','list').map(x=>[x.project,x.instructions,x.findings]),[['org-repo',true,1]]); });
t('memory: changed file hash marks finding stale; filters and limit', ()=>{ const src=path.join(HOME,'src.txt'); fs.writeFileSync(src,'v2');
  const r=run('memory','read','org-repo'); assert.equal(r.findings[0].effective,'stale'); assert.equal(r.findings[0].status,'verified'); assert.deepEqual(r.findings[0].changed,[src]);
  for(let i=0;i<4;i++) run('memory','add','org-repo','--as','codex','--note','n'+i,'--repo','other/repo');
  assert.equal(run('memory','read','org-repo','--repo','org/repo').findings.length,1); assert.equal(run('memory','read','org-repo','--status','stale').total,1);
  assert.equal(run('memory','read','org-repo','--path','x.js').total,1); const l=run('memory','read','org-repo','--limit','2'); assert.equal(l.total,5); assert.equal(l.findings[0].body,'n3'); assert.equal(l.findings.length,2); });
t('context pack references finding ids, not copies', ()=>{ const fid=run('memory','read','org-repo').findings[0].id;
  const m=run('send','--from','grok','--to','codex','--subject','fr','--body','b','--findings',fid); assert.match(run('read',m.id).context,new RegExp('- '+fid)); assert.doesNotMatch(run('read',m.id).context,/n3/); });
await ta('12 concurrent finding adds -> 12 files, none lost', async()=>{ const res=await Promise.all(Array.from({length:12},(_,i)=>new Promise(r=>{const p=spawn('node',[CLI,'memory','add','race','--as','codex','--note','c'+i],{env}); p.on('exit',c=>r(c));})));
  assert.deepEqual(res,Array(12).fill(0)); const r=run('memory','read','race','--limit','50'); assert.equal(r.total,12); assert.deepEqual(r.findings.map(x=>x.body).sort(),Array.from({length:12},(_,i)=>'c'+i).sort());
  assert.deepEqual(fs.readdirSync(path.join(HOME,'memory','race','findings')).filter(f=>f.startsWith('.')),[]); });

// ---------- 0.4.0 ----------
t('ids and thread names are validated before any path is built (no reads or writes outside the root)', ()=>{ const outside=path.join(path.dirname(HOME),'escaped.idx');
  assert.match(fail('send','--from','grok','--to','claude','--subject','x','--body','b','--thread','../../escaped'),/bad thread id/); assert.ok(!fs.existsSync(outside));
  for(const cmd of [['read','../../../memory/org-repo/instructions'],['claim','../x','--as','claude'],['done','..\\x','--as','claude'],['receipts','../../log'],['thread','../threads/x'],['reply','01X','--as','claude','--body','b']])
    assert.match(fail(...cmd),/bad (message|thread) id/,cmd.join(' '));
  assert.match(fail('send','--from','grok','--to','claude','--subject','x','--body','b','--reply-to','../x'),/bad --reply-to id/);
  assert.match(fail('transcript','read','0'.repeat(64),'--for','../../x'),/bad --for message id/); });
t('reply: checks run before the claim; a reply to a done ask is a follow-up, not an error; --from is accepted for --as', ()=>{
  const m=run('send','--from','grok','--to','claude','--subject','q','--body','b'); assert.match(fail('reply',m.id,'--as','claude','--body',''),/body is empty/);
  assert.match(fail('reply',m.id,'--as','claude','--body','token ghp_abcdefghijklmnopqrstuvwxyz12'),/body looks like it contains a secret/);
  assert.match(fail('reply',m.id,'--as','claude','--body','ok','--context-file',path.join(HOME,'big.txt')),/cap is 8192/);
  assert.equal(run('read',m.id).status,'unread','a rejected reply leaves the ask unclaimed'); const before=run('inbox','grok').length;
  run('reply',m.id,'--as','claude','--body','first'); const again=run('reply',m.id,'--as','claude','--body','second'); assert.equal(again.follow_up,true);
  assert.equal(run('inbox','grok').length,before+2); assert.equal(run('read',m.id).status,'done');
  const m2=run('send','--from','grok','--to','claude','--subject','q2','--body','b'); assert.equal(run('reply',m2.id,'--from','claude','--body','ok').to,'grok'); });
t('flag values may start with --; empty body and bad subject/sha/due are rejected', ()=>{
  assert.equal(run('read',run('send','--from','grok','--to','codex','--subject','d','--body','--decline is a word here').id).body,'--decline is a word here');
  assert.equal(run('read',run('send','--from','grok','--to','codex','--subject','d','--body=--x=y').id).body,'--x=y');
  assert.match(fail('send','--from','grok','--to','codex','--subject','d'),/body is empty|body required/); assert.match(fail('send','--from','grok','--to','codex','--subject','d','--body'),/--body needs a value/);
  assert.match(fail('send','--from','grok','--to','codex','--subject','a\nb','--body','b'),/one line/); assert.match(fail('send','--from','grok','--to','codex','--subject','S'.repeat(301),'--body','b'),/max 300/);
  assert.match(fail('send','--from','grok','--to','codex','--subject','key ghp_abcdefghijklmnopqrstuvwxyz12','--body','b'),/subject\/metadata looks like it contains a secret/);
  assert.match(fail('send','--from','grok','--to','codex','--subject','s','--body','b','--sha','not-a-sha'),/bad --sha/); assert.match(fail('send','--from','grok','--to','codex','--subject','s','--body','b','--due','someday'),/bad --due/);
  assert.equal(run('send','--from','grok','--to','codex','--subject','s','--body','b','--requires-matt-approval').requires_matt_approval,true);
  assert.equal(run('send','--from','grok','--to','codex','--subject','s','--body','b','--requires-matt-approval=false').requires_matt_approval,false,'--flag=false is false');
  assert.match(fail('send','--from','grok','--to','codex','--subject','s','--body','b','--json=maybe'),/--json is yes\/no/);
  const k=run('send','--from','grok','--to','claude','--subject','kd','--body','b').id; run('reply',k,'--as','claude','--body','not a decline','--decline=false'); assert.equal(run('read',k).status,'done','--decline=false does not decline');
  for(const s of ['see docs/risk-assessment-framework-notes.md','task-based-onboarding-workflow']) assert.ok(run('send','--from','grok','--to','codex','--subject',s,'--body',s).id,'no false secret: '+s);
  assert.match(fail('send','--from','grok','--to','codex','--subject','s','--body','b','--thread','ghp_abcdefghijklmnopqrstuvwxyz12'),/subject\/metadata looks like it contains a secret/); });
t('fork ids that look like options are refused; valid ones pass', ()=>{
  assert.match(fail('send','--from','grok','--to','claude','--subject','f','--body','b','--fork-claude-session','--dangerously-skip-permissions'),/bad --fork-claude-session/);
  assert.match(fail('send','--from','grok','--to','codex','--subject','f','--body','b','--fork-codex-thread','-c'),/bad --fork-codex-thread/);
  const u='0f8fad5b-d9cb-469f-a165-70867728950e'; assert.equal(run('send','--from','grok','--to','claude','--subject','f','--body','b','--fork-claude-session',u).fork_claude_session,u);
  const jf=path.join(HOME,'sess.jsonl'); fs.writeFileSync(jf,'{}\n'); assert.equal(runIn(HOME,'send','--from','grok','--to','claude','--subject','f','--body','b','--fork-claude-session','sess.jsonl').fork_claude_session,jf);
  const th='f0f0f0f0-0000-7000-8000-000000000001'; assert.equal(run('send','--from','grok','--to','codex','--subject','f','--body','b','--fork-codex-thread',th).fork_codex_thread,th); });
t('memory: a file found on disk is stored absolute, so a reader in another cwd re-hashes the same file', ()=>{ const a=fs.mkdtempSync(path.join(os.tmpdir(),'cpa-')), b=fs.mkdtempSync(path.join(os.tmpdir(),'cpb-'));
  fs.writeFileSync(path.join(a,'f.txt'),'v1'); fs.writeFileSync(path.join(b,'f.txt'),'another file with the same name'); const f=runIn(a,'memory','add','rel','--as','codex','--note','n','--files','f.txt');
  assert.equal(JSON.parse(f.files)[0].path,path.join(a,'f.txt')); const x=runIn(b,'memory','read','rel').findings[0]; assert.equal(x.effective,'unverified'); assert.deepEqual(x.changed,[]);
  fs.writeFileSync(path.join(a,'f.txt'),'v2'); assert.equal(runIn(b,'memory','read','rel').findings[0].effective,'stale'); fs.rmSync(a,{recursive:true,force:true}); fs.rmSync(b,{recursive:true,force:true}); });
t('run: the printed cd line round-trips a root with an apostrophe and a curly quote; listener-equivalent flags; codex workspace = mailbox', ()=>{
  const Q=fs.mkdtempSync(path.join(os.tmpdir(),'cp o\'neil’s-')); const eq={...process.env,CARRIER_PIGEON_HOME:Q}; const cq=(...a)=>execFileSync('node',[CLI,...a],{env:eq,encoding:'utf8'});
  cq('init'); const c=JSON.parse(cq('send','--from','grok','--to','codex','--subject','r','--body','b','--json')).id, k=JSON.parse(cq('send','--from','grok','--to','claude','--subject','r','--body','b','--json')).id;
  const sc=cq('run',c).split(/\r?\n/), sk=cq('run',k).split(/\r?\n/); assert.match(sc[0],/NOT executed/); assert.match(sc[1],/^(Set-Location|cd) '/);
  const here=process.platform==='win32'
    ? Buffer.from(execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',sc[1]+'; [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Location).Path))'],{encoding:'utf8'}).trim(),'base64').toString('utf8')
    : execFileSync('sh',['-c',sc[1]+' && pwd'],{encoding:'utf8'}).trim();
  const norm=p=>process.platform==='win32'?path.resolve(p).toLowerCase():path.resolve(p); assert.equal(norm(here),norm(fs.realpathSync(Q)),'the printed cd line lands in the root');
  assert.match(sc[2],/^codex exec --sandbox workspace-write --skip-git-repo-check -C '/); assert.ok(sc[2].includes(sc[1].replace(/^(Set-Location|cd) /,'')),'codex -C is the same quoted root');
  for(const f of ['(node bin/carrier-pigeon.mjs *)','--permission-mode dontAsk','--strict-mcp-config','--mcp-config host/empty-mcp.json','--settings host/claude-settings.json']) assert.ok(sk[2].includes(f),f);
  assert.ok(JSON.parse(fs.readFileSync(path.join(Q,'host/claude-settings.json'),'utf8')).permissions.deny.includes('Read(./host/secrets/**)')); assert.ok(fs.existsSync(path.join(Q,'host/empty-mcp.json')));
  for(const s of [sc.join('\n'),sk.join('\n')]){ assert.doesNotMatch(s,/\\"/); assert.doesNotMatch(s,/Bash\(node:\*\)/); } fs.rmSync(Q,{recursive:true,force:true}); });
t('memory: a UNC path in a finding is never opened (reported unchecked)', ()=>{ const unc='\\\\example.invalid\\share\\x.txt'; const t0=Date.now();
  run('memory','add','unc','--as','codex','--note','n','--files',unc+'@'+'b'.repeat(64)+','+unc.replace('x.txt','y.txt')); const x=run('memory','read','unc').findings[0];
  assert.deepEqual(x.unchecked.sort(),[unc,unc.replace('x.txt','y.txt')].sort()); assert.ok(Date.now()-t0<20000,'no network wait'); });
t('status counts files without parsing them; read flags matt as unauthenticated; version', ()=>{ fs.writeFileSync(path.join(HOME,'agents/codex/done/01ZZZZZZZZZZZZZZZZZZZZZZZZ.md'),'not a message');
  assert.ok(run('status','codex').codex.done>=1); const m=run('send','--from','matt','--to','codex','--subject','m','--body','b');
  assert.match(execFileSync('node',[CLI,'read',m.id],{env,encoding:'utf8'}),/"matt" is not authenticated/); assert.match(run('version').version,/^\d+\.\d+\.\d+$/); });
t('a non-usage error prints one line, no stack trace', ()=>{ const r=spawnSync('node',[CLI,'transcript','pack',path.join(HOME,'missing.jsonl'),'--as','claude'],{env,encoding:'utf8'});
  assert.equal(r.status,1); assert.match(r.stderr,/^carrier-pigeon: ENOENT/); assert.doesNotMatch(r.stderr,/\n\s+at /); });
t('file flags refuse host secrets, credential stores and .env files, including through a junction; ordinary files still work', ()=>{
  const H=fs.mkdtempSync(path.join(os.tmpdir(),'cpdeny-')); const e3={...process.env,CARRIER_PIGEON_HOME:HOME,USERPROFILE:H,HOME:H};
  const f3=(...a)=>{ try{ execFileSync('node',[CLI,...a],{env:e3,stdio:['ignore','pipe','pipe']}); }catch(e){ return e.stderr.toString(); } assert.fail('expected refusal: '+a.join(' ')); };
  const put=(p,s='x')=>{ fs.mkdirSync(path.dirname(p),{recursive:true}); fs.writeFileSync(p,s); return p; };
  const sec=put(path.join(HOME,'host','secrets','probe.txt')), ssh=put(path.join(H,'.ssh','id_test')), env=put(path.join(H,'proj','.env.local')), auth=put(path.join(H,'.codex','auth.json'),'{}');
  const link=path.join(H,'link'); fs.symlinkSync(path.join(HOME,'host','secrets'),link,'junction'); const tj=put(path.join(H,'.ssh','s.jsonl'),'{}\n');
  const send=['send','--from','claude','--to','grok','--subject','s'];
  assert.match(f3(...send,'--body-file',sec),/refusing to read the host secrets folder/); assert.match(f3(...send,'--body-file',path.join(link,'probe.txt')),/host secrets folder/,'junction resolved');
  assert.match(f3(...send,'--body','b','--context-file',ssh),/refusing to read ~\/\.ssh/); assert.match(f3(...send,'--body-file',env),/a \.env file/);
  assert.match(f3('memory','add','p','--as','codex','--body-file',auth),/~\/\.codex\/auth\.json/); assert.match(f3('memory','instructions','p','--as','matt','--file',env),/\.env file/);
  assert.match(f3('transcript','pack',tj,'--as','claude'),/refusing to read ~\/\.ssh/); assert.match(f3('transcript','verify','0'.repeat(64),'--text-file',sec),/host secrets/);
  const ok=put(path.join(H,'proj','notes.md'),'plain notes'); assert.equal(JSON.parse(execFileSync('node',[CLI,...send,'--body-file',ok,'--json'],{env:e3,encoding:'utf8'})).body,'plain notes');
  fs.unlinkSync(link); fs.rmSync(H,{recursive:true,force:true}); fs.rmSync(path.join(HOME,'host','secrets'),{recursive:true,force:true}); });
// ---------- 0.5.0 ----------
const runAsync=(...a)=>new Promise(res=>{ const p=spawn('node',[CLI,...a,'--json'],{env}); let o=''; p.stdout.on('data',d=>o+=d); p.on('exit',code=>res({code,out:o})); });
const waitFor=async(f,ms=20000)=>{ const t0=Date.now(); while(Date.now()-t0<ms){ const v=f(); if(v) return v; await new Promise(r=>setTimeout(r,200)); } return null; };
await ta('ask: returns the reply when it arrives within --wait; the consumed reply is marked done', async()=>{
  const p=runAsync('ask','--from','claude','--to','codex','--subject','what port?','--body','Ask: which port? Return: a number.','--wait','60');
  const askMsg=await waitFor(()=>run('inbox','codex').find(m=>m.subject==='what port?')); assert.ok(askMsg,'ask delivered'); run('reply',askMsg.id,'--as','codex','--body','4593');
  const r=await p; assert.equal(r.code,0); const j=JSON.parse(r.out); assert.equal(j.status,'replied'); assert.equal(j.reply.body,'4593'); assert.equal(j.sent,askMsg.id);
  assert.equal(run('read',j.reply.id).status,'done','reply consumed'); });
await ta('ask --wait 0 sends and exits 3 with a handle; wait picks the reply up later; --wake-on-reply is recorded', async()=>{
  const r=spawnSync('node',[CLI,'ask','--from','claude','--to','codex','--subject','later','--body','b','--wait','0','--wake-on-reply','--json'],{env,encoding:'utf8'}); assert.equal(r.status,3);
  const j=JSON.parse(r.stdout); assert.equal(j.status,'pending'); assert.equal(run('read',j.sent).wake_on_reply,true); run('reply',j.sent,'--as','codex','--body','done later');
  const w=spawnSync('node',[CLI,'wait',j.sent,'--as','claude','--wait','10','--keep','--json'],{env,encoding:'utf8'}); assert.equal(w.status,0); assert.equal(JSON.parse(w.stdout).reply.body,'done later');
  assert.equal(run('read',JSON.parse(w.stdout).reply.id).status,'unread','--keep leaves it in the inbox'); });
t('agents: pull without a listener; auto-wake / notify-only from a live listener\'s presence file; stale presence ignored', ()=>{
  assert.ok(run('agents').every(x=>x.reach==='pull')); const hd=path.join(HOME,'host'); fs.mkdirSync(hd,{recursive:true});
  fs.writeFileSync(path.join(hd,'host.lock'),String(process.pid)); // a live pid: this test process
  fs.writeFileSync(path.join(hd,'presence.json'),JSON.stringify({pid:process.pid,routes:{codex:['codex','toast'],matt:['toast'],claude:['claude']},adapters:{codex:{wakes:true,state:'ready',model:'m1'},toast:{wakes:false,state:'ready'},claude:{wakes:true,state:'down'}}}));
  const by=Object.fromEntries(run('agents').map(x=>[x.agent,x])); assert.equal(by.codex.reach,'auto-wake'); assert.equal(by.matt.reach,'notify-only'); assert.equal(by.claude.reach,'auto-wake (not ready)'); assert.equal(by.grok.reach,'pull');
  fs.writeFileSync(path.join(hd,'presence.json'),JSON.stringify({pid:1,routes:{codex:['codex']},adapters:{codex:{wakes:true,state:'ready'}}})); assert.equal(run('agents').find(x=>x.agent==='codex').reach,'pull','presence from another pid is stale');
  fs.rmSync(path.join(hd,'host.lock')); fs.rmSync(path.join(hd,'presence.json')); });
// ---------- 0.6.0 ----------
t('sessions: a reply goes back to the asking session; other sessions\' mail is hidden and cannot be claimed; wait in the session consumes it', ()=>{
  const q=run('send','--from','claude','--session','claude-s1','--to','codex','--subject','sq','--body','b'); assert.equal(q.from_session,'claude-s1');
  const r=run('reply',q.id,'--as','codex','--body','for s1 only'); assert.equal(r.to_session,'claude-s1');
  const ids=(...a)=>run('inbox','claude',...a).map(x=>x.id); assert.ok(!ids().includes(r.id),'hidden from the generic claude'); assert.ok(!ids('--session','claude-s2').includes(r.id),'hidden from another session');
  assert.ok(ids('--session','claude-s1').includes(r.id)); assert.ok(ids('--all-sessions').includes(r.id));
  assert.match(fail('claim',r.id,'--as','claude','--session','claude-s2'),/addressed to session claude-s1/);
  const w=JSON.parse(execFileSync('node',[CLI,'wait',q.id,'--as','claude','--session','claude-s1','--wait','5','--json'],{env,encoding:'utf8'})); assert.equal(w.reply.body,'for s1 only'); assert.equal(run('read',r.id).status,'done');
  assert.match(fail('send','--from','claude','--to','codex','--subject','s','--body','b','--to-session','../x'),/bad --to-session/); });
t('install: copies code into the root, keeps an existing config, backs up what it replaces, leaves mailbox data alone', ()=>{ const T=fs.mkdtempSync(path.join(os.tmpdir(),'cpinst-')); const e2={...process.env,CARRIER_PIGEON_HOME:T};
  const inst=(cli=CLI)=>JSON.parse(execFileSync('node',[cli,'install','--json'],{env:e2,encoding:'utf8',stdio:['ignore','pipe','pipe']})); const SK=path.dirname(path.dirname(CLI));
  const r=inst(); for(const f of ['bin/carrier-pigeon.mjs','bin/cp-context.mjs','host/carrier-pigeon-host.mjs','host/start-host.ps1','host/config.json']){ assert.ok(r.copied.includes(f),f); assert.ok(fs.readFileSync(path.join(T,f)).equals(fs.readFileSync(path.join(SK,f))),f); }
  assert.ok(fs.existsSync(path.join(T,'agents/claude/inbox'))); const m=JSON.parse(execFileSync('node',[CLI,'send','--from','grok','--to','codex','--subject','keep','--body','b','--json'],{env:e2,encoding:'utf8'}));
  fs.writeFileSync(path.join(T,'host/config.json'),'{"rescanMs": 5000}\n'); fs.appendFileSync(path.join(T,'bin/cp-context.mjs'),'\n// local edit\n');
  const r2=inst(); assert.deepEqual(r2.copied,['bin/cp-context.mjs']); assert.deepEqual(r2.kept,['host/config.json']); assert.equal(fs.readFileSync(path.join(T,'host/config.json'),'utf8'),'{"rescanMs": 5000}\n');
  assert.match(fs.readFileSync(path.join(r2.backup,'bin/cp-context.mjs'),'utf8'),/local edit/); assert.ok(fs.existsSync(path.join(T,'agents/codex/inbox',m.id+'.md')),'messages untouched');
  assert.deepEqual(inst().copied,[],'idempotent'); try{ execFileSync('node',[path.join(T,'bin/carrier-pigeon.mjs'),'install'],{env:e2,stdio:['ignore','pipe','pipe']}); assert.fail('expected refusal'); }catch(e){ assert.match(String(e.stderr),/already installed/); }
  const {CARRIER_PIGEON_HOME:_, ...bare}=process.env; const st=JSON.parse(execFileSync('node',[path.join(T,'bin/carrier-pigeon.mjs'),'status','codex','--json'],{env:bare,cwd:T,encoding:'utf8'}));
  assert.equal(st.codex.inbox,1,'an installed CLI without CARRIER_PIGEON_HOME acts on its own mailbox');
  // The skill folder has agents/openai.yaml: run from there without the variable, the CLI must target ~/.carrier-pigeon (a temp home here), not itself.
  const H2=fs.mkdtempSync(path.join(os.tmpdir(),'cphome-')); const home={...bare,USERPROFILE:H2,HOME:H2}; assert.ok(fs.existsSync(path.join(SK,'agents')),'fixture: skill folder has agents/');
  assert.ok(execFileSync('node',[CLI,'help'],{env:home,encoding:'utf8'}).includes('root: '+path.join(H2,'.carrier-pigeon')),'help names the home mailbox');
  const r3=JSON.parse(execFileSync('node',[CLI,'install','--json'],{env:home,encoding:'utf8'})); assert.equal(r3.root,path.join(H2,'.carrier-pigeon')); assert.ok(fs.existsSync(path.join(H2,'.carrier-pigeon','bin','carrier-pigeon.mjs')));
  assert.ok(!fs.existsSync(path.join(SK,'agents','claude')),'nothing created in the skill folder'); fs.rmSync(H2,{recursive:true,force:true});
  fs.rmSync(T,{recursive:true,force:true}); });
fs.rmSync(HOME,{recursive:true,force:true}); console.log(`# ${n} tests, ${failed} failed (cli)`); process.exit(failed?1:0);
