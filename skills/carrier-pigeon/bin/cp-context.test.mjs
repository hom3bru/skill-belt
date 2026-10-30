// node bin/cp-context.test.mjs — v0.3 context layer: transcript packs, stable prefix, digests, usage. Temp roots only.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import assert from 'node:assert/strict'; import {execFileSync} from 'node:child_process'; import {EventEmitter} from 'node:events';
import * as cpx from './cp-context.mjs';
import {wakeTurn,claudeAdapter,codexAdapter,claudeForkArgs,Host} from '../host/carrier-pigeon-host.mjs';
const here=path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1')); const CLI=path.join(here,'carrier-pigeon.mjs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms)); const until=async(f,ms=3000)=>{ const t=Date.now(); while(Date.now()-t<ms){ if(f()) return true; await sleep(20);} return false; };
function bus(){ const root=fs.mkdtempSync(path.join(os.tmpdir(),'cpx-')); const env={...process.env,CARRIER_PIGEON_HOME:root};
  const run=(...a)=>JSON.parse(execFileSync('node',[CLI,...a,'--json'],{env,encoding:'utf8',stdio:['ignore','pipe','pipe']}));
  const fail=(...a)=>{ try{ execFileSync('node',[CLI,...a],{env,stdio:['ignore','pipe','pipe']}); }catch(e){ return e.stderr.toString(); } assert.fail('expected failure'); }; run('init'); return {root,run,fail}; }
let n=0; const t=async(name,fn)=>{ await fn(); console.log('ok',++n,name); };
const J=o=>JSON.stringify(o);
const CODEX=[J({type:'session_meta',payload:{id:'x'}}),J({type:'response_item',payload:{type:'message',role:'developer',content:[{type:'input_text',text:'SYSTEM RULES'}]}}),
  J({type:'response_item',payload:{type:'message',role:'user',content:[{type:'input_text',text:'count lines in a.txt'}]}}),
  J({type:'response_item',payload:{type:'reasoning',summary:[],encrypted_content:'gAAAA-opaque'}}),
  J({type:'response_item',payload:{type:'function_call',name:'shell',arguments:'{"cmd":"wc -l a.txt"}',call_id:'c1'}}),
  J({type:'response_item',payload:{type:'function_call_output',call_id:'c1',output:'4817 a.txt'}}),
  J({type:'event_msg',payload:{type:'token_count'}}),
  J({type:'response_item',payload:{type:'message',role:'assistant',content:[{type:'output_text',text:'a.txt has 4817 lines; key sk-abcdefghijklmnopqrstuvwxyz0'}]}})].join('\n');
const CLAUDE=[J({type:'user',sessionId:'s',message:{role:'user',content:'what port?'}}),
  J({type:'assistant',sessionId:'s',message:{role:'assistant',content:[{type:'thinking',thinking:'SECRET-THOUGHT',signature:'sig'},{type:'tool_use',id:'t1',name:'Grep',input:{pattern:'PORT'}}]}}),
  J({type:'user',sessionId:'s',message:{role:'user',content:[{type:'tool_result',tool_use_id:'t1',content:'config.ts:12: PORT=4593'}]}}),
  J({type:'assistant',sessionId:'s',message:{role:'assistant',content:[{type:'text',text:'Port 4593.'}]}})].join('\n');

await t('codex rollout -> verbatim items: user/tool call/tool output/assistant kept, developer dropped, encrypted reasoning marked not faked', ()=>{
  const r=cpx.normalizeTranscript(CODEX,'auto'); assert.equal(r.format,'codex'); assert.deepEqual(r.items.map(x=>x.kind),['text','reasoning','tool_call','tool_output','text']);
  assert.equal(r.items[3].text,'4817 a.txt'); assert.match(r.items[1].text,/omitted by policy/); assert.ok(!J(r).includes('SYSTEM RULES')); assert.ok(!J(r).includes('gAAAA')); });
await t('claude session jsonl -> items incl. tool_use input and tool_result text; signed thinking marked', ()=>{
  const r=cpx.normalizeTranscript(CLAUDE,'auto'); assert.equal(r.format,'claude'); assert.match(r.items[2].text,/Grep\(\{"pattern":"PORT"\}\)/); assert.equal(r.items[3].text,'config.ts:12: PORT=4593'); assert.match(r.items[1].text,/omitted by policy/); });
await t('render mode (lossy, opt-in): content-addressed, secrets redacted, hash verified, thinking text never included', ()=>{ const {root,run,fail}=bus(); const f=path.join(root,'r.jsonl'); fs.writeFileSync(f,CODEX);
  const a=run('transcript','pack',f,'--as','codex','--render'), b=run('transcript','pack',f,'--as','codex','--render'); assert.equal(a.sha256,b.sha256); assert.equal(a.redactions,1); assert.equal(a.mode,'render');
  const txt=run('transcript','read',a.sha256).text; assert.match(txt,/LOSSY/); assert.ok(!txt.includes('sk-abcdefghij')); assert.equal(run('transcript','pack',f,'--as','codex','--render','--last','2').items,2);
  const cf=path.join(root,'c.jsonl'); fs.writeFileSync(cf,CLAUDE); assert.ok(!run('transcript','read',run('transcript','pack',cf,'--as','claude','--render').sha256).text.includes('SECRET-THOUGHT'));
  fs.appendFileSync(a.file,'tamper'); assert.match(fail('transcript','read',a.sha256),/failed hash check/); assert.match(fail('send','--from','codex','--to','claude','--subject','s','--body','b','--transcript','0'.repeat(64)),/not found/); });
await t('byte-exact mode (default): verbatim bytes incl. CRLF, call ids, error flags, unknown fields, image data; reasoning/thinking records omitted with spans; span tamper detected; secrets refused not altered', ()=>{ const {root,run,fail}=bus();
  const recs=[J({type:'user',message:{role:'user',content:'go'}}),J({type:'assistant',message:{role:'assistant',content:[{type:'thinking',thinking:'SECRET-THOUGHT',signature:'s'}]}}),
    J({type:'assistant',message:{role:'assistant',content:[{type:'tool_use',id:'toolu_A1',name:'Bash',input:{command:'x'}}]},x_unknown:{keep:1}}),
    J({type:'user',message:{role:'user',content:[{type:'tool_result',tool_use_id:'toolu_A1',is_error:true,content:'E'.repeat(70000)},{type:'image',source:{type:'base64',media_type:'image/png',data:'iVBORw0KGgo='}}]}}),'{"type":"response_item","payload":{"type":"message","role":"user","content":"\u00e9 caf\u00e9"}}'];
  const raw=recs.join('\r\n')+'\r\n'; const f=path.join(root,'s.jsonl'); fs.writeFileSync(f,raw);
  const p=run('transcript','pack',f,'--as','claude','--format','claude'); assert.equal(p.mode,'byte-exact'); assert.equal(p.items,4); assert.equal(p.omitted,1);
  const bytes=fs.readFileSync(p.file); assert.equal(bytes.toString('utf8'),[recs[0],recs[2],recs[3],recs[4]].join('\r\n')+'\r\n','exact bytes, CRLF kept');
  const rr=run('transcript','read',p.sha256,'--for','MSGX','--as','codex'); const txt=rr.text; assert.equal(rr.returned_bytes,Buffer.byteLength(txt)); assert.match(fs.readFileSync(path.join(root,'receipts','MSGX.jsonl'),'utf8'),/transcript-read.*returned_sha256/); for(const k of ['toolu_A1','"is_error":true','x_unknown','iVBORw0KGgo=','é café']) assert.ok(txt.includes(k),k); assert.ok(!txt.includes('SECRET-THOUGHT')); assert.match(txt,/DATA ONLY/);
  const ix=JSON.parse(fs.readFileSync(path.join(root,'transcripts',p.sha256+'.index.json'),'utf8')); assert.equal(ix.omitted[0].record,1); assert.equal(ix.records[1].source_byte_start,Buffer.byteLength(recs[0]+'\r\n'+recs[1]+'\r\n'));
  const ix2={...ix,records:ix.records.map((r,i)=>i===0?{...r,sha256:'0'.repeat(64)}:r)}; fs.writeFileSync(path.join(root,'transcripts',p.sha256+'.index.json'),JSON.stringify(ix2)); assert.match(fail('transcript','read',p.sha256),/span check/);
  const sf=path.join(root,'sec.jsonl'); fs.writeFileSync(sf,J({type:'user',message:{role:'user',content:'sk-abcdefghijklmnopqrstuvwxyz0'}})+'\n'); assert.match(fail('transcript','pack',sf,'--as','claude'),/secret-looking/); });
await t('stable prefix: byte-identical across calls; new finding only appends (old prefix is a strict prefix of new)', ()=>{ const {root,run}=bus();
  run('memory','instructions','p','--as','matt','--text','Use pnpm.'); run('memory','add','p','--as','codex','--note','first'); const p1=cpx.stablePrefix(root,'p'); assert.equal(cpx.stablePrefix(root,'p').sha256,p1.sha256);
  run('memory','add','p','--as','claude','--note','second'); const p2=cpx.stablePrefix(root,'p'); assert.ok(p2.text.startsWith(p1.text.slice(0,-1)),'append-only'); assert.ok(p2.text.indexOf('first')<p2.text.indexOf('second')); });
await t('digest: needs --files or --sha, marked DIGEST in prefix, body from file, stale when file changes', ()=>{ const {root,run,fail}=bus(); const src=path.join(root,'src.txt'); fs.writeFileSync(src,'v1'); const bf=path.join(root,'map.md'); fs.writeFileSync(bf,'repo map: 3 dirs');
  assert.match(fail('memory','digest','p','--as','codex','--note','x'),/needs --files/); const d=run('memory','digest','p','--as','codex','--body-file',bf,'--files',src);
  assert.equal(d.kind,'digest'); assert.match(cpx.stablePrefix(root,'p').text,new RegExp(d.id+' DIGEST')); fs.writeFileSync(src,'v2'); assert.equal(run('memory','read','p').findings[0].effective,'stale'); });
await t('wakeTurn: prefix first and only once per session; transcript verbatim before the message; message last', ()=>{ const {root,run}=bus(); run('memory','add','general','--as','codex','--note','N1');
  const f=path.join(root,'c.jsonl'); fs.writeFileSync(f,CLAUDE); const tr=run('transcript','pack',f,'--as','claude').sha256; const sent=new Map();
  const w1=wakeTurn({id:'1',kind:'ask',from:'claude',to:'codex',subject:'s',transcript:tr},root,sent); assert.ok(w1.startsWith('[carrier-pigeon v0.3 stable prefix]'));
  const rc=fs.readFileSync(path.join(root,'receipts','1.jsonl'),'utf8'); assert.match(rc,/transcript-submitted/); assert.match(rc,/submitted_sha256/);
  assert.ok(w1.indexOf('N1')<w1.indexOf('PORT=4593')&&w1.indexOf('PORT=4593')<w1.indexOf('New ask 1')); const w2=wakeTurn({id:'2',kind:'ask',from:'a',to:'codex',subject:'s'},root,sent); assert.match(w2,/memory unchanged/); assert.ok(!w2.includes('N1'));
  run('memory','add','general','--as','codex','--note','N2'); assert.match(wakeTurn({id:'3',kind:'ask',from:'a',to:'codex',subject:'s'},root,sent),/N2/); });
await t('usage normalisation: claude adds cache reads/writes to input; codex delta of totals; stats hit rate', ()=>{ const {root}=bus();
  const c=cpx.claudeUsage({usage:{input_tokens:10,cache_read_input_tokens:900,cache_creation_input_tokens:90,output_tokens:5},duration_ms:7}); assert.deepEqual([c.input_total,c.cached,c.uncached],[1000,900,10]);
  const d=cpx.codexDelta({inputTokens:100,cachedInputTokens:0},{inputTokens:600,cachedInputTokens:400,outputTokens:9}); assert.deepEqual([d.input_total,d.cached,d.uncached],[500,400,100]);
  fs.mkdirSync(path.join(root,'host','logs'),{recursive:true}); fs.writeFileSync(path.join(root,'host','logs','usage.jsonl'),[J({ts:'a',agent:'codex',input_total:500,cached:400,latency_ms:3}),J({ts:'b',agent:'codex',input_total:500,cached:100,latency_ms:5})].join('\n')+'\n');
  const s=cpx.stats(root).agents[0]; assert.equal(s.hit_rate,0.5); assert.equal(s.wakes,2); assert.equal(s.median_latency_ms,5); });
await t('claude adapter logs result usage per wake; fork uses --resume ID --fork-session with prompt on stdin', async()=>{ const {root}=bus(); const kids=[];
  const spawnFn=(bin,args)=>{ const c=new EventEmitter(); c.stdout=new EventEmitter(); c.stderr=new EventEmitter(); c.lines=[]; c.args=args; c.stdin={writable:true,write:l=>c.lines.push(l),end(){}}; c.kill=()=>{}; kids.push(c); return c; };
  const ad=claudeAdapter({spawnFn}); const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{claude:ad}}); await h.start();
  await ad.deliver({id:'M1',from:'grok',to:'claude',kind:'ask',subject:'s'}); kids[0].stdout.emit('data',Buffer.from(J({type:'result',session_id:'S',usage:{input_tokens:3,cache_read_input_tokens:97,cache_creation_input_tokens:0,output_tokens:1}})+'\n'));
  assert.ok(await until(()=>fs.existsSync(path.join(root,'host/logs/usage.jsonl')))); const u=JSON.parse(fs.readFileSync(path.join(root,'host/logs/usage.jsonl'),'utf8').trim()); assert.deepEqual([u.agent,u.msg,u.input_total,u.cached],['claude','M1',100,97]);
  await ad.deliver({id:'M2',from:'grok',to:'claude',kind:'ask',subject:'s',fork_claude_session:'SESS'}); const fk=kids.at(-1); assert.deepEqual(fk.args.slice(-3),['--resume','SESS','--fork-session']); assert.ok(!fk.args.includes('--input-format')); assert.match(fk.lines.join(''),/New ask M2/);
  assert.deepEqual(claudeForkArgs('.','X').slice(-2),['X','--fork-session']); await h.stop(); });
await t('codex adapter: logs per-turn cached/total delta; fork_codex_thread -> thread/fork then turn/start on the fork', async()=>{ const {root}=bus(); const sent=[]; let srv;
  class WS{ constructor(){ srv=this; setTimeout(()=>this.onopen(),0); } send(s){ const m=JSON.parse(s); sent.push(m); const r=res=>setTimeout(()=>this.onmessage({data:J({id:m.id,result:res})}),0);
      if(m.method==='initialize') r({}); if(m.method==='model/list') r({data:[{id:'g',isDefault:true}]}); if(m.method==='thread/start') r({thread:{id:'thr1'}}); if(m.method==='thread/fork') r({thread:{id:'fork1'}}); if(m.method==='turn/start'||m.method==='turn/steer') r({}); } close(){} }
  const spawnFn=()=>{ const c=new EventEmitter(); c.stdout=new EventEmitter(); c.stderr=new EventEmitter(); c.kill=()=>{}; return c; };
  const ad=codexAdapter({spawnFn,WS}); const h=new Host({root,config:{watch:false,rescanMs:60000},adapters:{codex:ad}}); await h.start(); await until(()=>ad.state.thread);
  const N=(method,params)=>srv.onmessage({data:J({method,params})});
  N('thread/tokenUsage/updated',{threadId:'thr1',tokenUsage:{total:{inputTokens:1000,cachedInputTokens:0}}}); await ad.deliver({id:'A1',from:'grok',to:'codex',kind:'ask',subject:'s'});
  N('turn/started',{threadId:'thr1',turn:{id:'T1'}}); N('thread/tokenUsage/updated',{threadId:'thr1',tokenUsage:{total:{inputTokens:3000,cachedInputTokens:1500,outputTokens:20}}}); N('turn/completed',{threadId:'thr1',turn:{id:'T1',status:'completed'}});
  const uf=path.join(root,'host/logs/usage.jsonl'); assert.ok(await until(()=>fs.existsSync(uf))); const u=JSON.parse(fs.readFileSync(uf,'utf8').trim()); assert.deepEqual([u.msg,u.input_total,u.cached,u.output],['A1',2000,1500,20]);
  await ad.deliver({id:'A2',from:'grok',to:'codex',kind:'ask',subject:'s'}); N('turn/started',{threadId:'thr1',turn:{id:'T2'}}); await ad.deliver({id:'A3',from:'grok',to:'codex',kind:'ask',subject:'s'});
  assert.equal(sent.at(-1).method,'turn/steer'); N('turn/completed',{threadId:'thr1',turn:{id:'T2',status:'completed'}}); assert.ok(await until(()=>fs.readFileSync(uf,'utf8').trim().split('\n').length===2));
  assert.deepEqual(JSON.parse(fs.readFileSync(uf,'utf8').trim().split('\n')[1]).steered,['A3'],'steered asks are attributed to the turn they joined');
  await ad.deliver({id:'F1',from:'grok',to:'codex',kind:'ask',subject:'s',fork_codex_thread:'src9'}); assert.deepEqual(sent.find(m=>m.method==='thread/fork').params,{threadId:'src9'}); assert.equal(sent.filter(m=>m.method==='turn/start').at(-1).params.threadId,'fork1');
  assert.equal(ad.state.thread,'thr1','main thread unchanged'); await h.stop(); });
await t('pack capture: git branch/HEAD + dirty/untracked list, sha256 of referenced ones; read re-hashes and flags changes', ()=>{ const {root,run}=bus(); const repo=path.join(root,'repo'); fs.mkdirSync(repo);
  const g=(...a)=>execFileSync('git',['-C',repo,'-c','user.email=t@t','-c','user.name=t',...a],{encoding:'utf8'}); g('init','-q','-b','main'); fs.writeFileSync(path.join(repo,'a.txt'),'v1'); fs.writeFileSync(path.join(repo,'quiet.txt'),'q'); g('add','.'); g('commit','-qm','c');
  fs.writeFileSync(path.join(repo,'a.txt'),'v2'); fs.writeFileSync(path.join(repo,'new.txt'),'n'); fs.writeFileSync(path.join(repo,'quiet.txt'),'q2');
  const f=path.join(root,'s.jsonl'); fs.writeFileSync(f,J({type:'user',message:{role:'user',content:'edit a.txt and new.txt'}})+'\n');
  const p=run('transcript','pack',f,'--as','claude','--repo',repo); const cap=JSON.parse(fs.readFileSync(path.join(root,'transcripts',p.sha256+'.index.json'),'utf8')).capture;
  assert.equal(cap.branch,'main'); assert.match(cap.head,/^[0-9a-f]{40}$/); assert.deepEqual(cap.dirty.map(e=>e.path).sort(),['a.txt','quiet.txt']); assert.deepEqual(cap.untracked.map(e=>e.path),['new.txt']);
  assert.equal(cap.dirty.find(e=>e.path==='a.txt').sha256,cpx.sha256('v2')); assert.equal(cap.dirty.find(e=>e.path==='quiet.txt').sha256,undefined,'unreferenced: listed, not hashed');
  let r=run('transcript','read',p.sha256); assert.ok(r.files_at_read.every(x=>!x.changed)); assert.match(r.text,/changed since capture: none/);
  fs.writeFileSync(path.join(repo,'a.txt'),'v3'); r=run('transcript','read',p.sha256,'--for','M2'); assert.deepEqual(r.files_at_read.filter(x=>x.changed).map(x=>x.path),['a.txt']); assert.match(r.text,/changed since capture: a\.txt/);
  assert.match(fs.readFileSync(path.join(root,'receipts','M2.jsonl'),'utf8'),/files_at_read.*"changed":true/); });
await t('canaries: per-record HMAC markers, key stays in host/secrets, verify reports matched records (possession of marker only)', ()=>{ const {root,run}=bus();
  const f=path.join(root,'s.jsonl'); fs.writeFileSync(f,[1,2,3].map(i=>J({type:'user',message:{role:'user',content:'r'+i}})).join('\n')+'\n'); const p=run('transcript','pack',f,'--as','claude');
  const r=run('transcript','read',p.sha256); const cs=r.text.match(/cpk-[0-9a-f]{20}/g); assert.equal(cs.length,3); assert.equal(r.canaries,3);
  const key=fs.readFileSync(path.join(root,'host','secrets','canary.key'),'utf8').trim(); assert.ok(!r.text.includes(key)); assert.ok(!fs.readFileSync(path.join(root,'transcripts',p.sha256+'.index.json'),'utf8').includes(cs[0]),'canaries not stored in index');
  assert.equal(run('transcript','read',p.sha256).text,r.text,'stable across reads'); assert.ok(!/cpk-/.test(run('transcript','read',p.sha256,'--no-canaries').text));
  const ans=path.join(root,'ans.txt'); fs.writeFileSync(ans,`saw ${cs[0]} and ${cs[2]} and cpk-${'0'.repeat(20)}`); const v=run('transcript','verify',p.sha256,'--text-file',ans,'--for','M3');
  assert.deepEqual(v.matched_records,[0,2]); assert.deepEqual(v.missing_records,[1]); assert.equal(v.unknown_markers,1); assert.match(v.label,/possession of marker only/); assert.match(fs.readFileSync(path.join(root,'receipts','M3.jsonl'),'utf8'),/canary-verify/);
  const body=fs.readFileSync(p.file,'utf8'); assert.ok(!body.includes('cpk-'),'pack bytes unchanged'); });
console.log(`# ${n} context tests passed`); process.exit(0);
