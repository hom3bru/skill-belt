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
  const coEntry=put(path.join(HOME,'co','co-01M69500000000000000000000','entries','0001.json'),'{"text":"blind work"}'); // a peer's co entry: only co view may show it
  assert.match(f3(...send,'--body-file',coEntry),/refusing to read the co-work project store/); fs.rmSync(path.join(HOME,'co','co-01M69500000000000000000000'),{recursive:true,force:true});
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

t('session ownership survives a claim: another session cannot reply or finish it', ()=>{
  const q=run('send','--from','grok','--to','codex','--subject','owned work','--body','b');
  run('claim',q.id,'--as','codex','--session','worker-one'); const before=run('inbox','grok').length;
  assert.match(fail('reply',q.id,'--as','codex','--session','worker-two','--body','stolen'),/claimed by.*worker-one/);
  assert.match(fail('done',q.id,'--as','codex','--session','worker-two'),/claimed by.*worker-one/);
  assert.match(fail('done',q.id,'--as','codex'),/claimed by.*worker-one/);
  assert.equal(run('inbox','grok').length,before,'failed ownership checks send nothing');
  assert.equal(run('read',q.id).status,'claimed'); run('reply',q.id,'--as','codex','--session','worker-one','--body','owner answer');
  assert.equal(run('read',q.id).status,'done'); });

t('wait refuses another session\'s ask and does not consume its answer', ()=>{
  const q=run('send','--from','codex','--session','waiting-one','--to','claude','--subject','private wait','--body','b');
  const r=run('reply',q.id,'--as','claude','--body','owner answer');
  assert.match(fail('wait',q.id,'--as','codex','--session','waiting-two','--wait','0'),/sent by session waiting-one/);
  assert.match(fail('wait',q.id,'--as','grok','--wait','0'),/sent by codex/);
  assert.equal(run('read',r.id).status,'unread'); });

t('wait matches the original recipient and thread, not only reply_to', ()=>{
  const q=run('send','--from','codex','--to','claude','--subject','correlate reply','--body','b');
  run('send','--from','grok','--to','codex','--reply-to',q.id,'--kind','reply','--thread',q.thread,'--subject','wrong sender','--body','wrong');
  run('send','--from','claude','--to','codex','--reply-to',q.id,'--kind','reply','--subject','wrong thread','--body','wrong');
  const pending=spawnSync('node',[CLI,'wait',q.id,'--as','codex','--wait','0','--json'],{env,encoding:'utf8'});
  assert.equal(pending.status,3); assert.equal(JSON.parse(pending.stdout).status,'pending');
  const r=run('reply',q.id,'--as','claude','--body','correct');
  assert.equal(run('wait',q.id,'--as','codex','--wait','0').reply.id,r.id); });

t('a session-directed ask accepts an answer only from that recipient session', ()=>{
  const q=run('send','--from','codex','--to','claude','--to-session','intended-reviewer','--subject','directed answer','--body','b');
  run('send','--from','claude','--session','other-reviewer','--to','codex','--reply-to',q.id,'--kind','reply','--thread',q.thread,'--subject','other instance','--body','wrong');
  const pending=spawnSync('node',[CLI,'wait',q.id,'--as','codex','--wait','0','--json'],{env,encoding:'utf8'});
  assert.equal(pending.status,3); assert.equal(JSON.parse(pending.stdout).status,'pending');
  const r=run('reply',q.id,'--as','claude','--session','intended-reviewer','--body','right instance');
  assert.equal(run('wait',q.id,'--as','codex','--wait','0').reply.id,r.id); });
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
t('codex-hooks: install adds carrier-pigeon\'s PostToolUse and Stop hooks beside the others, once; remove takes only those; a backup is kept', ()=>{
  const CH=fs.mkdtempSync(path.join(os.tmpdir(),'cpcodexhome-')), f=path.join(CH,'hooks.json'), e2={...env,CODEX_HOME:CH}; const hk=(...a)=>JSON.parse(execFileSync('node',[CLI,'codex-hooks',...a,'--json'],{env:e2,encoding:'utf8',stdio:['ignore','pipe','pipe']}));
  const theirs={matcher:'Edit|Write',hooks:[{type:'command',command:'other-tool hook',timeout:5}]}; const before={hooks:{SessionStart:[],PostToolUse:[theirs],Stop:[{hooks:[{type:'command',command:'other-tool stop'}]}]}};
  fs.writeFileSync(f,JSON.stringify(before,null,2)); assert.equal(hk('status').installed,false);
  const r=hk('install'); const cp=c=>String(c).includes('cp-hook.mjs'); let h=JSON.parse(fs.readFileSync(f,'utf8')).hooks;
  assert.deepEqual(h.PostToolUse[0],theirs,'other tools\' hooks are kept'); assert.equal(h.Stop.length,2); assert.deepEqual(h.SessionStart,[],'untouched events stay as they were');
  const post=h.PostToolUse[1].hooks[0]; assert.ok(cp(post.command)&&cp(post.commandWindows)); assert.match(post.command,/ codex post-tool-use$/); assert.match(h.Stop[1].hooks[0].commandWindows,/^node ".*cp-hook\.mjs" codex stop$/);
  assert.equal(post.timeout,10); assert.equal(h.PostToolUse[1].matcher,undefined,'every tool'); assert.match(r.note,/trusted/); assert.deepEqual(JSON.parse(fs.readFileSync(r.backup,'utf8')),before);
  hk('install'); h=JSON.parse(fs.readFileSync(f,'utf8')).hooks; assert.equal(h.PostToolUse.filter(g=>g.hooks.some(x=>cp(x.command))).length,1,'reinstall replaces, never duplicates'); assert.equal(hk('status').installed,true);
  hk('remove'); assert.deepEqual(JSON.parse(fs.readFileSync(f,'utf8')),before,'remove restores exactly what was there'); assert.equal(hk('status').installed,false);
  fs.writeFileSync(f,'{not json'); assert.throws(()=>hk('install'),/not valid JSON/); assert.equal(fs.readFileSync(f,'utf8'),'{not json','a broken file is left alone');
  fs.rmSync(CH,{recursive:true,force:true}); });
t('command help is read-only, succeeds before required arguments, and documents structured replies',()=>{
  const before=run('status');const help=run('reply','--help');assert.match(help.help,/--result/);assert.match(help.help,/request-key/);assert.deepEqual(run('status'),before);
});
// doctor: each case gets its own root. A live listener is faked with this test process's pid in host/host.lock and a presence.json naming it.
{ let roots=0; const LOADED=run('version').version;
  const docRun=(root,...a)=>spawnSync('node',[CLI,'doctor',...a],{env:{...process.env,CARRIER_PIGEON_HOME:root,CARRIER_PIGEON_SESSION:''},encoding:'utf8'});
  const docJson=(root,...a)=>{ const r=docRun(root,...a,'--json'); assert.equal(r.status,0,r.stderr); assert.equal(r.stderr,''); return JSON.parse(r.stdout); };
  const snap=root=>{ if(!fs.existsSync(root)) return null; const l=[]; const visit=d=>{ for(const f of fs.readdirSync(d).sort()){ const p=path.join(d,f), s=fs.statSync(p);
    l.push([path.relative(root,p),s.mtimeMs,s.isFile()?fs.readFileSync(p,'base64'):'dir']); if(s.isDirectory()) visit(p); } }; visit(root); return l; };
  const mailbox=({version=LOADED,routes=null}={})=>{ const root=path.join(HOME,'doctor-'+(++roots));
    execFileSync('node',[CLI,'init'],{env:{...process.env,CARRIER_PIGEON_HOME:root},stdio:'ignore'});
    if(version!==null){ fs.mkdirSync(path.join(root,'bin')); fs.writeFileSync(path.join(root,'bin','cp-context.mjs'),typeof version==='function'?version():`export const VERSION = '${version}';\n`); }
    if(routes){ fs.mkdirSync(path.join(root,'host'),{recursive:true}); fs.writeFileSync(path.join(root,'host','host.lock'),String(process.pid));
      fs.writeFileSync(path.join(root,'host','presence.json'),JSON.stringify({pid:process.pid,routes:Object.fromEntries(Object.keys(routes).map(a=>[a,[a+'-adapter']])),
        adapters:Object.fromEntries(Object.entries(routes).map(([a,state])=>[a+'-adapter',{state,wakes:true}]))})); }
    return root; };
  const check=(r,code)=>r.checks.find(c=>c.code===code);
  const actionable=r=>{ assert.deepEqual(r.checks.map(c=>c.code),['mailbox','version','listener','agent:claude','agent:codex']);
    for(const c of r.checks) c.status==='warning'?assert.ok(c.next_action?.trim(),c.code):assert.equal(c.next_action,null,c.code); };
  t('doctor before init reports uninitialized, exits 0 in both formats and never creates the mailbox',()=>{ const root=path.join(HOME,'doctor-absent');
    const human=docRun(root); assert.equal(human.status,0,human.stderr); assert.match(human.stdout,/^carrier-pigeon doctor: uninitialized/); assert.match(human.stdout,/next: Run carrier-pigeon init/);
    const r=docJson(root); assert.equal(r.initialized,false); assert.equal(r.health,'uninitialized'); assert.deepEqual(r.agents,[]); assert.equal(r.installed_version,null); assert.equal(r.loaded_version,LOADED);
    assert.ok(r.checks.every(c=>c.status==='warning')); actionable(r); assert.equal(fs.existsSync(root),false,'doctor must not create the mailbox'); });
  t('doctor: an invalid explicit agent or session is a usage error, still without creating anything',()=>{ const root=path.join(HOME,'doctor-usage');
    for(const a of [['--as','bob'],['--as=']]){ const r=docRun(root,...a); assert.equal(r.status,2,a.join(' ')); assert.match(r.stderr,/unknown agent/); assert.equal(r.stdout,''); }
    const s=docRun(root,'--session','../escape'); assert.equal(s.status,2); assert.match(s.stderr,/bad session/); assert.equal(fs.existsSync(root),false); });
  t('doctor: matching installed version, live listener and auto-wake claude/codex are ready; identity is echoed; files unchanged',()=>{
    const root=mailbox({routes:{claude:'ready',codex:'ready'}}), before=snap(root);
    const r=docJson(root,'--as','codex','--session','doc-fixture'); assert.equal(r.health,'ready'); assert.equal(r.initialized,true); assert.equal(r.installed_version,LOADED); assert.equal(r.needs_reconnect,false);
    assert.equal(r.agent,'codex'); assert.equal(r.session,'doc-fixture'); assert.equal(r.agents.length,5); assert.equal(r.agents.find(a=>a.agent==='claude').listener_pid,process.pid); actionable(r);
    const human=docRun(root); assert.equal(human.status,0); assert.match(human.stdout,/doctor: ready/); assert.doesNotMatch(human.stdout,/warning|next:/); assert.match(human.stdout,new RegExp(`loaded ${LOADED.replace(/\./g,'\\.')}, installed`));
    assert.deepEqual(snap(root),before,'doctor changed mailbox files'); });
  t('doctor: missing and malformed installed versions warn without a reconnect claim and exit 0',()=>{
    for(const version of [null,()=>'export const VERSION = getVersion();\n',()=>'// export const VERSION = \'1.0.0\';\n']){
      const root=mailbox({version,routes:{claude:'ready',codex:'ready'}}), before=snap(root), r=docJson(root);
      assert.equal(r.installed_version,null); assert.equal(r.needs_reconnect,false); assert.equal(r.health,'attention'); assert.equal(check(r,'version').status,'warning'); actionable(r);
      const human=docRun(root); assert.equal(human.status,0); assert.match(human.stdout,/installed unknown/); assert.deepEqual(snap(root),before); } });
  t('doctor: a loaded version older than installed code needs a reconnect',()=>{ const root=mailbox({version:'999.0.0',routes:{claude:'ready',codex:'ready'}}), r=docJson(root);
    assert.equal(r.installed_version,'999.0.0'); assert.equal(r.needs_reconnect,true); assert.equal(r.health,'attention'); assert.match(check(r,'version').next_action,/[Rr]econnect/);
    assert.match(docRun(root).stdout,/installed 999\.0\.0: reconnect needed/); });
  t('doctor: pull and not-ready agents and a missing listener give attention with next actions',()=>{
    const root=mailbox({routes:{codex:'starting'}}), before=snap(root), r=docJson(root); assert.equal(r.health,'attention');
    assert.equal(check(r,'listener').status,'ok'); assert.equal(check(r,'agent:claude').status,'warning'); assert.match(check(r,'agent:claude').message,/pull/);
    assert.equal(check(r,'agent:codex').status,'warning'); assert.match(check(r,'agent:codex').message,/auto-wake \(not ready\)/); actionable(r);
    const human=docRun(root); assert.equal(human.status,0); assert.match(human.stdout,/warning agent:claude/); assert.match(human.stdout,/next: .*inbox claude/);
    const idle=mailbox(), q=docJson(idle); assert.equal(check(q,'listener').status,'warning'); assert.ok(q.agents.every(a=>a.reach==='pull'&&a.listener_pid===null)); actionable(q);
    assert.deepEqual(snap(root),before); });
  t('doctor appears in help and leaves existing commands intact',()=>{ assert.match(execFileSync('node',[CLI,'help'],{env,encoding:'utf8'}),/doctor \[--as A\] \[--session S\]/); assert.ok(run('status').claude); });
}
t('co controller metadata travels on stdin beyond the Windows argv limit and refuses recursive intake',()=>{
 const question='A detailed local build acceptance criterion. '.repeat(900),argv=['new','--mode','build','--title','Large controller brief','--question',question,'--subject','fixture@baseline','--members','codex,claude','--as','codex','--lead','codex'];
 const result=spawnSync(process.execPath,[CLI,'co','--request-stdin','--json'],{env,input:JSON.stringify({argv}),encoding:'utf8',windowsHide:true});assert.equal(result.status,0,result.stderr);assert.equal(JSON.parse(result.stdout).question,question.trim());
 const nested=spawnSync(process.execPath,[CLI,'co','--request-stdin','--json'],{env,input:JSON.stringify({argv:['--request-stdin']}),encoding:'utf8',windowsHide:true});assert.equal(nested.status,2);assert.match(nested.stderr,/bounded string argv/);
});
fs.rmSync(HOME,{recursive:true,force:true}); console.log(`# ${n} tests, ${failed} failed (cli)`); process.exit(failed?1:0);
