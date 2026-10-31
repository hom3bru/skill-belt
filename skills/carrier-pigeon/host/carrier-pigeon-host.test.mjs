// node carrier-pigeon-host.test.mjs — temp CARRIER_PIGEON_HOME, fake adapters; never launches claude/codex or touches the real bus.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import assert from 'node:assert/strict'; import {execFileSync,spawn} from 'node:child_process'; import {EventEmitter} from 'node:events';
import {Host,Supervisor,readReceipts,claudeAdapter,codexAdapter,grokWebhookAdapter,cursorCloudAdapter,toastScript,toastEnv,toastAdapter,cursorDeeplink,wakePrompt,claudeArgs,claudeShell,ensureClaudeSettings,CLAUDE_READ_DENY,codexLeanArgs,grokPayload} from './carrier-pigeon-host.mjs';
const here=path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1')); const CLI=path.resolve(here,'../bin/carrier-pigeon.mjs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms)); const until=async(f,ms=3000)=>{ const t=Date.now(); while(Date.now()-t<ms){ if(f()) return true; await sleep(20);} return false; };
function bus(){ const root=fs.mkdtempSync(path.join(os.tmpdir(),'abhost-')); const env={...process.env,CARRIER_PIGEON_HOME:root};
  const run=(...a)=>JSON.parse(execFileSync('node',[CLI,...a,'--json'],{env,encoding:'utf8'})); run('init'); return {root,run}; }
const fake=(name,wakes=true)=>({name,wakes,got:[],notes:[],async deliver(m){ this.got.push(m.id); return true; },async notify(n){ this.notes.push(n); }});
const evs=(root,id)=>readReceipts(root,id).map(r=>r.ev);
// A failing test is reported as "not ok" and the suite carries on, so one failure can't hide the tests after it.
let n=0, failed=0; const t=async(name,fn)=>{ n++; try{ await fn(); console.log('ok',n,name); }catch(e){ failed++; console.log('not ok',n,name); console.log('  '+String(e?.stack||e).split('\n').slice(0,6).join('\n  ')); } };
const noMcp=async()=>[]; // codex lean mode without running the real codex binary

await t('fs.watch delivers a new ask quickly; .tmp files ignored', async()=>{ const {root,run}=bus(); const a=fake('claude'); const h=new Host({root,config:{rescanMs:60000,adapters:[]},adapters:{claude:a}}); await h.start();
  fs.writeFileSync(path.join(root,'agents/claude/inbox/.tmp-1-x'),'junk'); const t0=Date.now(); const m=run('send','--from','grok','--to','claude','--subject','hi','--body','b');
  assert.ok(await until(()=>a.got.includes(m.id)),'not delivered'); console.log('   watch latency ms:',Date.now()-t0,'(includes CLI process spawn)'); assert.equal(a.got.length,1); await h.stop(); });
await t('rescan catches a missed watch event', async()=>{ const {root,run}=bus(); const a=fake('claude'); const h=new Host({root,config:{watch:false,rescanMs:200},adapters:{claude:a}}); await h.start();
  const m=run('send','--from','grok','--to','claude','--subject','s','--body','b'); assert.ok(await until(()=>a.got.includes(m.id),2000)); await h.stop(); });
await t('receipts: queued, notified, received, replied/declined + CLI receipts', async()=>{ const {root,run}=bus(); const a=fake('claude'); const h=new Host({root,config:{watch:false,rescanMs:100},adapters:{claude:a}}); await h.start();
  const m=run('send','--from','grok','--to','claude','--subject','s','--body','b'); await until(()=>a.got.length);
  run('claim',m.id,'--as','claude'); await until(()=>evs(root,m.id).includes('received')); run('reply',m.id,'--as','claude','--body','done'); await until(()=>evs(root,m.id).includes('replied'));
  assert.deepEqual(evs(root,m.id),['queued','notified:claude','received','replied']);
  const d=run('send','--from','grok','--to','claude','--subject','s2','--body','b'); await until(()=>a.got.includes(d.id)); run('reply',d.id,'--as','claude','--body','no','--decline');
  await until(()=>evs(root,d.id).includes('declined')); assert.deepEqual(evs(root,d.id),['queued','notified:claude','received','declined']);
  assert.equal(run('receipts',m.id).length,4); await h.stop(); });
await t('dedup by message id across rescans and host restart', async()=>{ const {root,run}=bus(); const a=fake('claude'); let h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{claude:a}}); await h.start();
  const m=run('send','--from','grok','--to','claude','--subject','s','--body','b'); await h.scanAll(); await h.scanAll(); await h.stop();
  h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{claude:a}}); await h.start(); await h.scanAll(); assert.deepEqual(a.got,[m.id]); assert.equal(evs(root,m.id).filter(e=>e==='queued').length,1); await h.stop(); });
await t('hop limit: 9th message in a thread does not auto-wake and alerts Matt once', async()=>{ const {root,run}=bus(); const a=fake('claude'), b=fake('codex'), toast=fake('toast',false);
  const h=new Host({root,config:{watch:false,rescanMs:60000,noWakeKinds:[]},adapters:{claude:a,codex:b,toast}}); await h.start();
  let th=null, ids=[]; for(let i=0;i<10;i++){ const to=i%2?'codex':'claude'; const m=run('send','--from',i%2?'claude':'codex','--to',to,'--subject','p'+i,'--body','b','--kind','ask',...(th?['--thread',th]:[])); th=th||m.thread; ids.push(m.id); await h.scanAll(); }
  assert.equal(a.got.length+b.got.length,8); assert.ok(evs(root,ids[8]).includes('no-wake')); assert.equal(readReceipts(root,ids[8]).find(r=>r.ev==='no-wake').reason,'hop-limit');
  assert.equal(toast.notes.filter(x=>/hop limit/.test(x.title)).length,1); assert.ok(evs(root,ids[8]).includes('notified:toast')); await h.stop(); });
await t('rate limit: max 6 auto-wakes per agent per window', async()=>{ const {root,run}=bus(); const a=fake('claude'), toast=fake('toast',false); let now=1e6;
  const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{claude:a,toast},now:()=>now}); await h.start(); const ids=[];
  for(let i=0;i<7;i++){ ids.push(run('send','--from','grok','--to','claude','--subject','r'+i,'--body','b').id); await h.scanAll(); }
  assert.equal(a.got.length,6); assert.equal(readReceipts(root,ids[6]).find(r=>r.ev==='no-wake').reason,'rate-limit'); assert.equal(toast.notes.length,1);
  now+=600001; const later=run('send','--from','grok','--to','claude','--subject','later','--body','b').id; await h.scanAll(); assert.deepEqual(a.got.slice(6),[ids[6],later]); assert.ok(evs(root,ids[6]).includes('rate-retry')); await h.stop(); });
await t('rate-limited ask: retried once window frees, survives restart, dropped if claimed meanwhile, toast not repeated', async()=>{ const {root,run}=bus(); const a=fake('claude'), toast=fake('toast',false); toast.deliver=async function(m){ this.got.push(m.id); return true; }; let now=1e6;
  let h=new Host({root,config:{watch:false,rescanMs:60000,routes:{claude:['claude','toast']}},adapters:{claude:a,toast},now:()=>now}); await h.start(); const ids=[];
  for(let i=0;i<8;i++){ ids.push(run('send','--from','grok','--to','claude','--subject','q'+i,'--body','b').id); await h.scanAll(); }
  assert.equal(a.got.length,6); await h.scanAll(); assert.equal(a.got.length,6,'no retry while window full'); await h.stop();
  run('claim',ids[7],'--as','claude'); now+=600001; h=new Host({root,config:{watch:false,rescanMs:60000,routes:{claude:['claude','toast']}},adapters:{claude:a,toast},now:()=>now}); await h.start(); await h.scanAll();
  assert.deepEqual(a.got.slice(6),[ids[6]]); assert.ok(evs(root,ids[7]).includes('rate-retry-dropped')); assert.equal(toast.got.filter(x=>x===ids[6]).length,1); await h.scanAll(); assert.equal(a.got.length,7); await h.stop(); });
await t('reply and fyi never auto-wake (toast still notifies)', async()=>{ const {root,run}=bus(); const a=fake('claude'), toast=fake('toast',false); toast.deliver=async function(m){ this.got.push(m.id); return true; };
  const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{claude:a,toast}}); await h.start();
  const f=run('send','--from','grok','--to','claude','--subject','f','--body','b','--kind','fyi'); const r=run('send','--from','grok','--to','claude','--subject','r','--body','b','--kind','reply'); await h.scanAll();
  assert.deepEqual(a.got,[]); assert.deepEqual(toast.got,[f.id,r.id]); assert.equal(readReceipts(root,f.id).find(x=>x.ev==='no-wake').reason,'no-wake-kind'); await h.stop(); });
await t('single-instance lock', async()=>{ const {root}=bus(); const h=new Host({root,config:{watch:false},adapters:{}}); await h.start();
  const code=`import {acquireLock} from ${JSON.stringify(new URL('./carrier-pigeon-host.mjs',import.meta.url).href)}; try{ acquireLock(process.argv[1]); console.log('GOT'); }catch(e){ console.log(e.message); }`; const out=execFileSync(process.execPath,['--input-type=module','-e',code,path.join(root,'host/host.lock')],{encoding:'utf8'}); assert.match(out,/already running/); await h.stop(); const h2=new Host({root,config:{watch:false},adapters:{}}); await h2.start(); await h2.stop(); });
await t('supervisor restarts a crashing child with backoff', async()=>{ const logs=[]; let starts=0; const s=new Supervisor('x',()=>{ starts++; return spawn(process.execPath,['-e','process.exit(1)']); },{baseMs:20,maxMs:80,stableMs:10000},e=>logs.push(e));
  // waits on the restart log itself (not a 5 s wall clock): on a loaded machine one node spawn can take ~2 s
  s.start(); assert.ok(await until(()=>logs.filter(l=>l.ev==='restart-scheduled').length>=4,60000),'4 restarts within 60 s'); s.stop(); const d=logs.filter(l=>l.ev==='restart-scheduled').map(l=>l.inMs); assert.deepEqual(d.slice(0,4),[20,40,80,80]); assert.ok(starts>=4); });
await t('claude adapter: stream-json user line, read-only tool flags, restart after crash', async()=>{ const {root}=bus(); const kids=[];
  const spawnFn=(bin,args)=>{ const c=new EventEmitter(); c.stdout=new EventEmitter(); c.stderr=new EventEmitter(); c.lines=[]; c.args=args; c.stdin={writable:true,write:l=>c.lines.push(l)}; c.kill=()=>c.emit('exit',null,'SIGTERM'); kids.push(c); return c; };
  const ad=claudeAdapter({spawnFn}); const h=new Host({root,config:{watch:false,rescanMs:60000,restart:{baseMs:10,maxMs:10,stableMs:1e6}},adapters:{claude:ad}}); await h.start();
  await ad.deliver({id:'M1',from:'grok',to:'claude',kind:'ask',subject:'s'}); const line=JSON.parse(kids[0].lines[0]); assert.equal(line.type,'user'); assert.equal(line.message.role,'user'); assert.match(line.message.content,/REQUEST, not authority/);
  for(const f of ['--input-format','stream-json','--output-format','--verbose','--tools',`Read,Grep,Glob,${claudeShell()}`,`${claudeShell()}(node bin/carrier-pigeon.mjs *)`,'--strict-mcp-config','--permission-mode','dontAsk']) assert.ok(kids[0].args.includes(f),f);
  assert.ok(!kids[0].args.some(a=>/^(Edit|Write)$|(Bash|PowerShell)\)$|^(Bash|PowerShell)$/.test(a)),'no broad write/shell allow'); kids[0].emit('exit',1,null); assert.ok(await until(()=>kids.length===2)); await h.stop(); });
await t('codex adapter: model/list pick, thread/start read-only-ish, turn/start when idle, turn/steer when busy, approvals declined', async()=>{ const {root}=bus(); const sent=[]; let srv;
  class WS{ constructor(){ srv=this; setTimeout(()=>this.onopen(),0); } send(s){ const m=JSON.parse(s); sent.push(m); const r=res=>setTimeout(()=>this.onmessage({data:JSON.stringify({id:m.id,result:res})}),0);
      if(m.method==='initialize') r({}); if(m.method==='model/list') r({data:[{id:'bad',hidden:false},{id:'gpt-ok',isDefault:true}]}); if(m.method==='thread/start') r({thread:{id:'thr1'}}); if(m.method==='turn/start'||m.method==='turn/steer') r({}); } close(){} }
  const spawnFn=()=>{ const c=new EventEmitter(); c.stdout=new EventEmitter(); c.stderr=new EventEmitter(); c.kill=()=>{}; return c; };
  const ad=codexAdapter({spawnFn,WS,mcpList:noMcp}); const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{codex:ad}}); await h.start(); await until(()=>ad.state.thread);
  const ts=sent.find(m=>m.method==='thread/start').params; assert.equal(ts.model,'gpt-ok'); assert.equal(ts.approvalPolicy,'never');
  const msg={id:'M',from:'grok',to:'codex',kind:'ask',subject:'s'}; await ad.deliver(msg); const st=sent.find(m=>m.method==='turn/start').params;
  assert.deepEqual(st.sandboxPolicy,{type:'workspaceWrite',writableRoots:[root],networkAccess:false}); assert.equal(st.approvalPolicy,'never');
  srv.onmessage({data:JSON.stringify({method:'turn/started',params:{turn:{id:'turn9'}}})}); await ad.deliver(msg); const steer=sent.find(m=>m.method==='turn/steer').params; assert.equal(steer.expectedTurnId,'turn9');
  srv.onmessage({data:JSON.stringify({id:77,method:'item/commandExecution/requestApproval',params:{}})}); assert.deepEqual(sent.at(-1),{id:77,result:{decision:'decline'}}); await h.stop(); });
await t('grok webhook: dormant w/o secret; 8KB cap, key header, retry on 5xx, dedup', async()=>{ const {root}=bus(); const calls=[]; let fails=1;
  const fetchFn=async(u,o)=>{ calls.push(o); if(fails-->0) return {ok:false,status:503}; return {ok:true,status:200}; }; const logs=[]; const log=e=>logs.push(e);
  let ad=grokWebhookAdapter({fetchFn,baseMs:1}); ad.start({root,log}); assert.equal(ad.dormant,true);
  fs.mkdirSync(path.join(root,'host/secrets'),{recursive:true}); fs.writeFileSync(path.join(root,'host/secrets/grok-webhook.json'),JSON.stringify({url:'https://example.invalid/hook',key:'K123'}));
  ad=grokWebhookAdapter({fetchFn,baseMs:1}); ad.start({root,log}); assert.equal(ad.dormant,false); const m={id:'W1',from:'claude',to:'grok',kind:'ask',subject:'s',body:'x'.repeat(20000)};
  assert.equal(await ad.deliver(m),true); assert.equal(calls.length,2); assert.ok(Buffer.byteLength(calls[1].body)<=8192); assert.equal(calls[1].headers['x-carrier-pigeon-key'],'K123'); assert.equal(JSON.parse(calls[1].body).truncated,true);
  assert.equal(await ad.deliver(m),false); assert.equal(calls.length,2); assert.ok(!JSON.stringify(logs).includes('K123')); });
await t('cursor cloud: steer body, Basic auth, no retry on 5xx, dedup', async()=>{ const {root}=bus(); const calls=[]; const fetchFn=async(u,o)=>{ calls.push({u,o}); return {ok:false,status:500}; };
  fs.mkdirSync(path.join(root,'host/secrets'),{recursive:true}); fs.writeFileSync(path.join(root,'host/secrets/cursor-cloud.json'),JSON.stringify({apiKey:'ckey',agentId:'bc-1'}));
  const ad=cursorCloudAdapter({fetchFn,baseMs:1}); ad.start({root,log:()=>{}}); await assert.rejects(ad.deliver({id:'C1',from:'grok',to:'cursor',kind:'ask',subject:'s'}),/HTTP 500/);
  assert.equal(calls.length,1); assert.equal(calls[0].u,'https://api.cursor.com/v1/agents/bc-1/runs'); const b=JSON.parse(calls[0].o.body); assert.deepEqual(Object.keys(b).sort(),['delivery','prompt']); assert.equal(b.delivery,'steer');
  assert.equal(calls[0].o.headers.authorization,'Basic '+Buffer.from('ckey:').toString('base64')); assert.equal(await ad.deliver({id:'C1'}),false); });
await t('toast: the PowerShell script is constant (text only via env, XML-escaped); cursor deeplink is prefill-only URL', ()=>{ const evil='x’); Start-Process calc; $null=(‘ <x&y>';
  const e=toastEnv({title:"a'b",text:evil,launch:cursorDeeplink('hi there')}); assert.match(e.CP_TOAST_XML,/&lt;x&amp;y&gt;/); assert.match(e.CP_TOAST_XML,/a&apos;b/);
  assert.match(e.CP_TOAST_XML,/cursor:\/\/anysphere\.cursor-deeplink\/prompt\?text=hi%20there/); assert.equal(e.CP_TOAST_TEXT,evil);
  const s=toastScript(); assert.ok(!s.includes('Start-Process')&&!s.includes('a\'b')&&!s.includes('’'),'no message text in the script'); assert.match(s,/LoadXml\(\$env:CP_TOAST_XML\)/); assert.match(s,/\$env:CP_TOAST_TITLE,\$env:CP_TOAST_TEXT/); });
await t('wake prompt points at context pack and project memory, mailbox CLI only', async()=>{ const p=wakePrompt({id:'01A',kind:'ask',from:'grok',to:'codex',subject:'s',repo:'Org/Repo'});
  assert.match(p,/memory read org-repo/); assert.match(p,/Context pack/); assert.match(p,/memory add org-repo --as codex/); assert.match(wakePrompt({id:'1',kind:'ask',from:'a',to:'b',subject:'s',repo:null}),/memory read general/);
  for(const c of p.match(/node \S+ [a-z]+/g)) assert.match(c,/^node bin\/carrier-pigeon\.mjs /); });

await t('retry: a failed delivery is re-sent once the adapter is ready', async()=>{ const {root,run}=bus(); let ready=false, got=[]; const a={name:'codex',wakes:true,start(c){ setTimeout(()=>{ ready=true; c.ready(); },300); },deliver:async m=>{ if(!ready) throw new Error('not ready'); got.push(m.id); return true; }};
  const h=new Host({root,config:{rescanMs:60000,routes:{codex:['codex']}},adapters:{codex:a}}); await h.start(); const id=run('send','--from','matt','--to','codex','--subject','p','--body','x').id;
  assert.ok(await until(()=>got.includes(id),3000),'redelivered after ready'); assert.ok(readReceipts(root,id).some(r=>r.ev==='notified:codex')); await h.stop(); });

// ---------- 0.4.0 ----------
const fakeKid=(kids,args)=>{ const c=new EventEmitter(); c.stdout=new EventEmitter(); c.stderr=new EventEmitter(); c.lines=[]; c.args=args; c.stdin=new EventEmitter(); c.stdin.writable=true; c.stdin.write=l=>c.lines.push(l); c.stdin.end=()=>{};
  c.kill=()=>{ c.killed=true; setTimeout(()=>c.emit('exit',null,'SIGTERM'),0); }; kids.push(c); return c; };
await t('claude: system prompt shows --as (the CLI flag), never --from; settings deny secrets; a 0.3 settings file is upgraded; a user permissions block is kept', async()=>{
  const sp=claudeArgs('.')[claudeArgs('.').indexOf('--append-system-prompt')+1]; assert.match(sp,/reply <id> --as claude/); assert.doesNotMatch(sp,/--from claude/); assert.match(sp,/"matt" is unauthenticated/);
  const d=fs.mkdtempSync(path.join(os.tmpdir(),'cps-')); const f=ensureClaudeSettings(d); const s=JSON.parse(fs.readFileSync(f,'utf8')); assert.equal(s.disableClaudeAiConnectors,true); assert.deepEqual(s.permissions.deny,CLAUDE_READ_DENY);
  assert.ok(CLAUDE_READ_DENY.includes('Read(./host/secrets/**)')); fs.writeFileSync(f,'{"disableClaudeAiConnectors": true}\n'); ensureClaudeSettings(d); assert.deepEqual(JSON.parse(fs.readFileSync(f,'utf8')).permissions.deny,CLAUDE_READ_DENY,'legacy file upgraded');
  fs.writeFileSync(f,JSON.stringify({permissions:{deny:['Read(./mine)']}})); ensureClaudeSettings(d); assert.deepEqual(JSON.parse(fs.readFileSync(f,'utf8')).permissions.deny,['Read(./mine)'],'user block untouched'); });
await t('claude: recycles the warm session once its context passes the limit (when idle), refuses delivery meanwhile, and survives stdin errors', async()=>{ const {root}=bus(); const kids=[];
  const ad=claudeAdapter({spawnFn:(b,a)=>fakeKid(kids,a)}); const h=new Host({root,config:{watch:false,rescanMs:60000,restart:{baseMs:10,maxMs:10,stableMs:1e6},claude:{recycleAtContextTokens:1000}},adapters:{claude:ad}}); await h.start();
  kids[0].stdin.emit('error',Object.assign(new Error('write EPIPE'),{code:'EPIPE'})); // would be an uncaught 'error' event without a handler
  await ad.deliver({id:'R1',from:'grok',to:'claude',kind:'ask',subject:'s'}); const emit=o=>kids[0].stdout.emit('data',Buffer.from(JSON.stringify(o)+'\n'));
  emit({type:'assistant',message:{usage:{input_tokens:5,cache_read_input_tokens:900,cache_creation_input_tokens:50}}}); emit({type:'result',usage:{input_tokens:5}}); assert.ok(!kids[0].killed,'under the limit: kept');
  await ad.deliver({id:'R2',from:'grok',to:'claude',kind:'ask',subject:'s'}); emit({type:'assistant',message:{usage:{input_tokens:5,cache_read_input_tokens:1500,cache_creation_input_tokens:50}}}); emit({type:'result',usage:{input_tokens:5}});
  assert.ok(kids[0].killed,'over the limit: recycled'); await assert.rejects(ad.deliver({id:'R3',from:'grok',to:'claude',kind:'ask',subject:'s'}),/claude session recycling/);
  assert.ok(await until(()=>kids.length===2),'fresh session started'); assert.ok(await until(()=>ad.sup.child===kids[1])); await ad.deliver({id:'R4',from:'grok',to:'claude',kind:'ask',subject:'s'}); assert.match(kids[1].lines[0],/stable prefix/,'fresh session gets the full prefix');
  const u=fs.readFileSync(path.join(root,'host/logs/usage.jsonl'),'utf8').trim().split('\n').map(JSON.parse); assert.deepEqual(u.map(x=>x.context_tokens),[955,1555]);
  assert.ok(fs.readFileSync(path.join(root,'host/logs/host.jsonl'),'utf8').includes('"ev":"claude-recycle"')); await h.stop(); });
await t('claude: a fork id that looks like an option is refused; a fork spawn error is logged, not thrown', async()=>{ const {root}=bus(); const kids=[];
  const ad=claudeAdapter({spawnFn:(b,a)=>fakeKid(kids,a)}); const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{claude:ad}}); await h.start();
  for(const bad of ['--dangerously-skip-permissions','relative.jsonl','\\\\server\\share\\s.jsonl']) await assert.rejects(ad.deliver({id:'F0',from:'grok',to:'claude',kind:'ask',subject:'s',fork_claude_session:bad}),/refusing fork_claude_session/,bad);
  assert.equal(kids.length,1,'no fork process spawned for a refused id');
  await ad.deliver({id:'F1',from:'grok',to:'claude',kind:'ask',subject:'s',fork_claude_session:'0f8fad5b-d9cb-469f-a165-70867728950e'}); kids.at(-1).emit('error',new Error('spawn ENOENT')); kids.at(-1).stdin.emit('error',new Error('EPIPE'));
  assert.ok(fs.readFileSync(path.join(root,'host/logs/host.jsonl'),'utf8').includes('claude-fork-error')); await h.stop(); });
await t('codex: lean launch argv disables plugins, apps and each named MCP server; lean:false is the full profile (argv only; the real binary is checked by hand)', async()=>{
  assert.deepEqual(codexLeanArgs(['headroom','a.b']),['--disable','plugins','--disable','apps','-c','mcp_servers.headroom.enabled=false','-c','mcp_servers."a.b".enabled=false']);
  const mk=async lean=>{ const {root}=bus(); const spawned=[]; const spawnFn=(b,a)=>{ spawned.push(a); const c=new EventEmitter(); c.stdout=new EventEmitter(); c.stderr=new EventEmitter(); c.kill=()=>{}; return c; };
    class WS{ constructor(){ setTimeout(()=>this.onerror(),0); } send(){} close(){} }
    const ad=codexAdapter({spawnFn,WS,mcpList:async()=>['headroom','figma']}); const h=new Host({root,config:{watch:false,rescanMs:60000,codex:{lean,connectTries:1},restart:{baseMs:60000,maxMs:60000,stableMs:1e6}},adapters:{codex:ad}}); await h.start();
    await ad.launched; await h.stop(); return spawned[0]; };
  const a=await mk(true); assert.deepEqual(a.slice(0,9),['app-server','--disable','plugins','--disable','apps','-c','mcp_servers.headroom.enabled=false','-c','mcp_servers.figma.enabled=false']); assert.ok(a.includes('--listen'));
  const b=await mk(false); assert.equal(b[1],'--listen'); });
await t('codex: a failed connect kills the app-server so the supervisor restarts it; "no models" is a clear error, not a TypeError', async()=>{ const {root}=bus(); const kids=[];
  const spawnFn=()=>{ const c=new EventEmitter(); c.stdout=new EventEmitter(); c.stderr=new EventEmitter(); c.kill=()=>{ c.killed=true; setTimeout(()=>c.emit('exit',1,null),0); }; kids.push(c); return c; };
  class WS{ constructor(){ setTimeout(()=>this.onopen(),0); } send(s){ const m=JSON.parse(s); const r=res=>setTimeout(()=>this.onmessage({data:JSON.stringify({id:m.id,result:res})}),0); if(m.method==='initialize') r({}); if(m.method==='model/list') r({data:[]}); } close(){} }
  const ad=codexAdapter({spawnFn,WS,mcpList:noMcp}); const h=new Host({root,config:{watch:false,rescanMs:60000,codex:{connectTries:1},restart:{baseMs:10,maxMs:10,stableMs:1e6}},adapters:{codex:ad}}); await h.start();
  assert.ok(await until(()=>kids.length>=2),'app-server restarted after the failed connect'); assert.ok(kids[0].killed); await h.stop();
  const log=fs.readFileSync(path.join(root,'host/logs/host.jsonl'),'utf8'); assert.match(log,/codex-connect-failed[^\n]*model\/list returned no models/); });
await t('codex: a dropped socket restarts the app-server; repeated warnings are logged once', async()=>{ const {root}=bus(); const kids=[]; let srv;
  const spawnFn=()=>{ const c=new EventEmitter(); c.stdout=new EventEmitter(); c.stderr=new EventEmitter(); c.kill=()=>{ c.killed=true; setTimeout(()=>c.emit('exit',1,null),0); }; kids.push(c); return c; };
  class WS{ constructor(){ srv=this; setTimeout(()=>this.onopen(),0); } send(s){ const m=JSON.parse(s); const r=res=>setTimeout(()=>this.onmessage({data:JSON.stringify({id:m.id,result:res})}),0);
      if(m.method==='initialize') r({}); if(m.method==='model/list') r({data:[{id:'g',isDefault:true}]}); if(m.method==='thread/start') r({thread:{id:'thr'}}); } close(){} }
  const ad=codexAdapter({spawnFn,WS,mcpList:noMcp}); const h=new Host({root,config:{watch:false,rescanMs:60000,restart:{baseMs:10,maxMs:10,stableMs:1e6}},adapters:{codex:ad}}); await h.start(); assert.ok(await until(()=>ad.state.thread));
  for(let i=0;i<3;i++) srv.onmessage({data:JSON.stringify({method:'warning',params:{message:'same plugin warning'}})});
  srv.onclose(); assert.equal(ad.state.thread,null); assert.ok(await until(()=>kids.length>=2),'app-server restarted after the socket dropped'); await h.stop();
  assert.equal(fs.readFileSync(path.join(root,'host/logs/host.jsonl'),'utf8').split('same plugin warning').length-1,1); });
await t('grok webhook: an oversized subject is capped and delivery returns (0.3 looped forever)', async()=>{ const {root}=bus(); const calls=[];
  fs.mkdirSync(path.join(root,'host/secrets'),{recursive:true}); fs.writeFileSync(path.join(root,'host/secrets/grok-webhook.json'),JSON.stringify({url:'https://example.invalid/hook',key:'K'}));
  const ad=grokWebhookAdapter({fetchFn:async(u,o)=>{ calls.push(o); return {ok:true,status:200}; },baseMs:1}); ad.start({root,log:()=>{}});
  const r=await Promise.race([ad.deliver({id:'G1',from:'claude',to:'grok',kind:'ask',subject:'S'.repeat(9000),body:'b'.repeat(9000)}),sleep(3000).then(()=>'hung')]);
  assert.equal(r,true); const p=JSON.parse(calls[0].body); assert.equal(p.subject.length,300); assert.ok(Buffer.byteLength(calls[0].body)<=8192); });
await t('state file is rewritten only when the state changes', async()=>{ const {root,run}=bus(); const a=fake('claude'); const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{claude:a}}); await h.start();
  run('send','--from','grok','--to','claude','--subject','s','--body','b'); await h.scanAll(); const sf=path.join(root,'host/state.json'); assert.ok(fs.existsSync(sf)); fs.rmSync(sf);
  await h.scanAll(); await h.scanAll(); assert.ok(!fs.existsSync(sf),'unchanged state not rewritten'); run('send','--from','grok','--to','claude','--subject','s2','--body','b'); await h.scanAll(); assert.ok(fs.existsSync(sf)); await h.stop(); });
await t('host re-validates inbox files: a hand-written id, sender, thread or fork never steers a path or spawn; good mail still flows', async()=>{ const {root,run}=bus(); const a=fake('claude');
  const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{claude:a}}); await h.start(); const inbox=path.join(root,'agents/claude/inbox'); const U='01ZZZZZZZZZZZZZZZZZZZZZZZZ';
  const fm=o=>'---\n'+Object.entries(o).map(([k,v])=>`${k}: ${JSON.stringify(v)}`).join('\n')+'\n---\n\nbody\n'; const base={from:'grok',to:'claude',thread:U,kind:'ask',subject:'s'};
  fs.writeFileSync(path.join(inbox,U+'.md'),fm({...base,id:'..\\..\\..\\escaped'})); fs.writeFileSync(path.join(inbox,'01YYYYYYYYYYYYYYYYYYYYYYYY.md'),fm({...base,id:'01YYYYYYYYYYYYYYYYYYYYYYYY',thread:'../../x'}));
  fs.writeFileSync(path.join(inbox,'01XXXXXXXXXXXXXXXXXXXXXXXX.md'),fm({...base,id:'01XXXXXXXXXXXXXXXXXXXXXXXX',to:'codex'})); fs.writeFileSync(path.join(inbox,'01WWWWWWWWWWWWWWWWWWWWWWWW.md'),fm({...base,id:'01WWWWWWWWWWWWWWWWWWWWWWWW',fork_claude_session:'--dangerously-skip-permissions'}));
  const good=run('send','--from','grok','--to','claude','--subject','ok','--body','b').id; await h.scanAll(); assert.deepEqual(a.got,[good]);
  assert.ok(!fs.existsSync(path.join(root,'..','escaped.jsonl'))&&!fs.existsSync(path.join(path.dirname(root),'escaped.jsonl')),'no receipt outside the root');
  const why=fs.readFileSync(path.join(root,'host/logs/host.jsonl'),'utf8').split('\n').filter(l=>l.includes('bad-message')).map(l=>JSON.parse(l).why).sort();
  assert.deepEqual(why,['bad fork_claude_session','bad thread','id is not the ULID file name','to does not match the inbox']); await h.stop(); });
await t('grok webhook: a failed POST is retried (not dropped as a duplicate); multibyte bodies keep as much as fits, marker last', async()=>{ const {root}=bus(); let fail=true; const calls=[];
  fs.mkdirSync(path.join(root,'host/secrets'),{recursive:true}); fs.writeFileSync(path.join(root,'host/secrets/grok-webhook.json'),JSON.stringify({url:'https://example.invalid/hook',key:'K'}));
  const ad=grokWebhookAdapter({fetchFn:async(u,o)=>{ calls.push(o); return fail?{ok:false,status:503}:{ok:true,status:200}; },baseMs:1}); ad.start({root,log:()=>{}}); const m={id:'G2',from:'claude',to:'grok',kind:'ask',subject:'s',body:'b'};
  await assert.rejects(ad.deliver(m),/HTTP 503/); fail=false; assert.equal(await ad.deliver(m),true,'retry posts again'); assert.equal(await ad.deliver(m),false,'then deduped');
  const cjk=grokPayload({id:'G3',from:'a',to:'grok',subject:'s',body:'漢'.repeat(4000)}); const p=JSON.parse(cjk); assert.ok(Buffer.byteLength(cjk)<=8192); assert.ok(p.body.length>2400,'kept '+p.body.length+' chars');
  assert.match(p.body,/…\[truncated; run carrier-pigeon read G3\]$/); const emoji=JSON.parse(grokPayload({id:'G4',from:'a',to:'grok',subject:'s',body:'\u{1F600}'.repeat(3000)})).body; assert.ok(!/[\uD800-\uDBFF](?![\uDC00-\uDFFF])/.test(emoji),'no lone surrogate'); });
await t('codex: a failed turn/start is retried with the prefix, not "unchanged", and leaves no queued entry behind', async()=>{ const {root}=bus(); const sent=[]; let failStart=true;
  class WS{ constructor(){ setTimeout(()=>this.onopen(),0); } send(s){ const m=JSON.parse(s); sent.push(m); const r=res=>setTimeout(()=>this.onmessage({data:JSON.stringify({id:m.id,result:res})}),0);
      if(m.method==='initialize') r({}); if(m.method==='model/list') r({data:[{id:'g',isDefault:true}]}); if(m.method==='thread/start') r({thread:{id:'thr'}});
      if(m.method==='turn/start'){ if(failStart){ failStart=false; setTimeout(()=>this.onmessage({data:JSON.stringify({id:m.id,error:{message:'busy'}})}),0); } else r({}); } } close(){} }
  const spawnFn=()=>{ const c=new EventEmitter(); c.stdout=new EventEmitter(); c.stderr=new EventEmitter(); c.kill=()=>{}; return c; };
  const ad=codexAdapter({spawnFn,WS,mcpList:noMcp}); const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{codex:ad}}); await h.start(); assert.ok(await until(()=>ad.state.thread));
  const msg={id:'01AAAAAAAAAAAAAAAAAAAAAAAA',from:'grok',to:'codex',kind:'ask',subject:'s'}; await assert.rejects(ad.deliver(msg),/busy/); await ad.deliver(msg);
  const starts=sent.filter(m=>m.method==='turn/start').map(m=>m.params.input[0].text); assert.equal(starts.length,2); assert.match(starts[1],/stable prefix/); assert.doesNotMatch(starts[1],/memory unchanged/); await h.stop(); });
await t('toast adapter (win32): constant -EncodedCommand script, message text passed in env', async()=>{ const calls=[]; const spawnFn=(bin,args,opt)=>{ calls.push({bin,args,opt}); const c=new EventEmitter(); setTimeout(()=>c.emit('exit',0),0); return c; };
  const ad=toastAdapter({spawnFn,platform:'win32'}); ad.start({cfg:{toast:{enabled:true}}}); await ad.deliver({id:'T1',from:'grok',to:'claude',kind:'ask',subject:'hi ’); Start-Process calc'}); await sleep(10);
  const c=calls[0]; assert.equal(c.bin,'powershell.exe'); assert.equal(Buffer.from(c.args.at(-1),'base64').toString('utf16le'),toastScript()); assert.match(c.opt.env.CP_TOAST_TEXT,/Start-Process calc/);
  const lin=[]; const ad2=toastAdapter({spawnFn:(b,a)=>{ lin.push(a); const e=new EventEmitter(); setTimeout(()=>e.emit('exit',0),0); return e; },platform:'linux'}); ad2.start({cfg:{toast:{enabled:true}}});
  await ad2.deliver({id:'T2',from:'grok',to:'claude',kind:'ask',subject:'-u critical'}); await sleep(10); assert.equal(lin[0][0],'--'); });
console.log(`# ${n} tests, ${failed} failed (host)`); process.exit(failed?1:0);
