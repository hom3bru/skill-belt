// node carrier-pigeon-host.test.mjs — temp CARRIER_PIGEON_HOME, fake adapters; never launches claude/codex or touches the real bus.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import assert from 'node:assert/strict'; import {execFileSync,spawn} from 'node:child_process'; import {EventEmitter} from 'node:events';
import {Host,Supervisor,readReceipts,claudeAdapter,codexAdapter,grokWebhookAdapter,cursorCloudAdapter,toastScript,cursorDeeplink,claudeArgs,claudeShell} from './carrier-pigeon-host.mjs';
const here=path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1')); const CLI=path.resolve(here,'../bin/carrier-pigeon.mjs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms)); const until=async(f,ms=3000)=>{ const t=Date.now(); while(Date.now()-t<ms){ if(f()) return true; await sleep(20);} return false; };
function bus(){ const root=fs.mkdtempSync(path.join(os.tmpdir(),'abhost-')); const env={...process.env,CARRIER_PIGEON_HOME:root};
  const run=(...a)=>JSON.parse(execFileSync('node',[CLI,...a,'--json'],{env,encoding:'utf8'})); run('init'); return {root,run}; }
const fake=(name,wakes=true)=>({name,wakes,got:[],notes:[],async deliver(m){ this.got.push(m.id); return true; },async notify(n){ this.notes.push(n); }});
const evs=(root,id)=>readReceipts(root,id).map(r=>r.ev);
let n=0; const t=async(name,fn)=>{ await fn(); console.log('ok',++n,name); };

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
  now+=600001; run('send','--from','grok','--to','claude','--subject','later','--body','b'); await h.scanAll(); assert.equal(a.got.length,7); await h.stop(); });
await t('reply and fyi never auto-wake (toast still notifies)', async()=>{ const {root,run}=bus(); const a=fake('claude'), toast=fake('toast',false); toast.deliver=async function(m){ this.got.push(m.id); return true; };
  const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{claude:a,toast}}); await h.start();
  const f=run('send','--from','grok','--to','claude','--subject','f','--body','b','--kind','fyi'); const r=run('send','--from','grok','--to','claude','--subject','r','--body','b','--kind','reply'); await h.scanAll();
  assert.deepEqual(a.got,[]); assert.deepEqual(toast.got,[f.id,r.id]); assert.equal(readReceipts(root,f.id).find(x=>x.ev==='no-wake').reason,'no-wake-kind'); await h.stop(); });
await t('single-instance lock', async()=>{ const {root}=bus(); const h=new Host({root,config:{watch:false},adapters:{}}); await h.start();
  const code=`import {acquireLock} from ${JSON.stringify(new URL('./carrier-pigeon-host.mjs',import.meta.url).href)}; try{ acquireLock(process.argv[1]); console.log('GOT'); }catch(e){ console.log(e.message); }`; const out=execFileSync(process.execPath,['--input-type=module','-e',code,path.join(root,'host/host.lock')],{encoding:'utf8'}); assert.match(out,/already running/); await h.stop(); const h2=new Host({root,config:{watch:false},adapters:{}}); await h2.start(); await h2.stop(); });
await t('supervisor restarts a crashing child with backoff', async()=>{ const logs=[]; let starts=0; const s=new Supervisor('x',()=>{ starts++; return spawn(process.execPath,['-e','process.exit(1)']); },{baseMs:20,maxMs:80,stableMs:10000},e=>logs.push(e));
  s.start(); await until(()=>starts>=5,5000); s.stop(); const d=logs.filter(l=>l.ev==='restart-scheduled').map(l=>l.inMs); assert.deepEqual(d.slice(0,4),[20,40,80,80]); });
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
  const ad=codexAdapter({spawnFn,WS}); const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{codex:ad}}); await h.start(); await until(()=>ad.state.thread);
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
await t('toast script escapes XML/quotes; cursor deeplink is prefill-only URL', ()=>{ const s=toastScript({title:"a'b",text:'<x&y>',launch:cursorDeeplink('hi there')});
  assert.match(s,/&lt;x&amp;y&gt;/); assert.match(s,/a''b/); assert.match(s,/cursor:\/\/anysphere\.cursor-deeplink\/prompt\?text=hi%20there/); });
console.log(`# ${n} host tests passed`);

await t('retry: a failed delivery is re-sent once the adapter is ready', async()=>{ const {root,run}=bus(); let ready=false, got=[]; const a={name:'codex',wakes:true,start(c){ setTimeout(()=>{ ready=true; c.ready(); },300); },deliver:async m=>{ if(!ready) throw new Error('not ready'); got.push(m.id); return true; }};
  const h=new Host({root,config:{rescanMs:60000,routes:{codex:['codex']}},adapters:{codex:a}}); await h.start(); const id=run('send','--from','matt','--to','codex','--subject','p','--body','x').id;
  assert.ok(await until(()=>got.includes(id),3000),'redelivered after ready'); assert.ok(readReceipts(root,id).some(r=>r.ev==='notified:codex')); await h.stop(); });
