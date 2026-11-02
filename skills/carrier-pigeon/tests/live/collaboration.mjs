// Opt-in real work: Claude leads a review of the installed task lifecycle, gets two Codex reviews,
// then returns a structured synthesis. No planted bug or scripted peer answer. Local login only.
// node tests/live/collaboration.mjs [--minutes 20] [--verify-fixes]
// The isolated mailbox and receipts are retained for inspection; the live listener is untouched.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import net from 'node:net';
import crypto from 'node:crypto'; import assert from 'node:assert/strict';
import {spawnSync,execFileSync} from 'node:child_process'; import {pathToFileURL} from 'node:url';
const liveRoot=process.env.CARRIER_PIGEON_HOME||path.join(os.homedir(),'.carrier-pigeon');
const config=JSON.parse(fs.readFileSync(path.join(liveRoot,'host/config.json'),'utf8'));
const liveLog=path.join(liveRoot,'log.jsonl'),before=fs.existsSync(liveLog)?fs.statSync(liveLog).mtimeMs:null;
const root=fs.mkdtempSync(path.join(os.tmpdir(),'cp-collaboration-'));
for(const dir of ['bin','host']){fs.mkdirSync(path.join(root,dir));for(const name of fs.readdirSync(path.join(liveRoot,dir)))if(/\.(mjs|ps1)$/.test(name))fs.copyFileSync(path.join(liveRoot,dir,name),path.join(root,dir,name));}
const env={...process.env,CARRIER_PIGEON_HOME:root};process.env.CARRIER_PIGEON_HOME=root;
const cli=(...args)=>{const r=spawnSync(process.execPath,[path.join(root,'bin/carrier-pigeon.mjs'),...args,'--json'],{env,encoding:'utf8',windowsHide:true,timeout:30000});if(![0,3,4].includes(r.status))throw new Error(String(r.stderr||r.error));return JSON.parse(r.stdout);};
cli('init');
const cp=await import(pathToFileURL(path.join(root,'bin/carrier-pigeon.mjs')).href);
const H=await import(pathToFileURL(path.join(root,'host/carrier-pigeon-host.mjs')).href);
const port=await new Promise((resolve,reject)=>{const server=net.createServer();server.on('error',reject);server.listen(0,'127.0.0.1',()=>{const p=server.address().port;server.close(()=>resolve(p));});});
const adapters=H.defaultAdapters({...H.DEFAULTS,...config});
const host=new H.Host({root,config:{watch:false,rescanMs:1000,adapters:['claude','codex'],routes:{claude:['claude'],codex:['codex']},
 claude:{bin:config.claude?.bin||'claude',extraArgs:config.claude?.extraArgs||[]},codex:{bin:config.codex?.bin||'codex',port,lean:true,model:config.codex?.model||null}},
 adapters:{claude:adapters.claude,codex:adapters.codex}});
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const pinned=Object.fromEntries(['bin/cp-tasks.mjs','bin/carrier-pigeon.mjs','bin/cp-tasks.test.mjs','host/carrier-pigeon-host.mjs'].map(name=>[name,sha(path.join(root,name))]));
const schema={type:'object',properties:{summary:{type:'string'},peer_ask_ids:{type:'array',items:{type:'string'},minItems:2,maxItems:2},peer_reply_ids:{type:'array',items:{type:'string'},minItems:2,maxItems:2},coverage:{type:'array',items:{type:'string'},minItems:3},findings:{type:'array',items:{type:'object',properties:{severity:{type:'string',enum:['high','medium','low','info']},location:{type:'string'},problem:{type:'string'},reproduction:{type:'string'}},required:['severity','location','problem','reproduction'],additionalProperties:false}}},required:['summary','peer_ask_ids','peer_reply_ids','coverage','findings'],additionalProperties:false};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const minutesIndex=process.argv.indexOf('--minutes');const minutes=minutesIndex<0?20:Number(process.argv[minutesIndex+1]);assert.ok(minutes>0&&minutes<=30);
const verifyFixes=process.argv.includes('--verify-fixes');
const t0=Date.now();let message,report,previous='';
console.log(JSON.stringify({event:'started',root,pinned,deadline_minutes:minutes}));
try{
 await host.start();
 message=cli('send','--from','grok','--session','collaboration-driver','--to','claude','--subject','Review real task recovery with Codex; two review rounds',
 '--request-key','collaboration-review-v1','--timeout-seconds',String(minutes*60),'--reply-schema',JSON.stringify(schema),'--body',[
  'Ask: lead a correctness review of the actual Carrier Pigeon task lifecycle with Codex, then return an actionable synthesis for the operator to reproduce and fix. This is real source code, with no planted defects.',
  `Context: writable mailbox ${root}. Review bin/cp-tasks.mjs and only the relevant send/claim/reply/done/waitReply call sites in bin/carrier-pigeon.mjs. Also inspect ONLY taskState/progress in host/carrier-pigeon-host.mjs for native-event fencing. Existing regression coverage is bin/cp-tasks.test.mjs. Pinned SHA256: ${JSON.stringify(pinned)}.`,
  'Focus on request-key crash recovery, claim generation fencing, cancellation/deadline races and structured result publication. Read the real code before claiming a bug. Give exact path:line and a concrete reproducer; a limitation already stated by the contract is not automatically a defect.',
  ...(verifyFixes?['This is the verification task after two operator-reproduced fixes. Narrow the review to: (1) reclaim must revoke the old control generation before publishing the message, rejecting stale native events and mailbox calls on either publication failure; deliberate retry must restore a working claim; (2) reply retries with an existing prepared_reply must recover its original id, body/result and outcome, including failure after the reply was already published but before the ask moved to done. Inspect the two new regression fixtures in cp-tasks.test.mjs and the corresponding implementation. Do not broaden this verification into a new general audit. Give your conclusions and remaining limits for each invariant. The operator already ran all 25 lifecycle fixtures; reviewers must distinguish that reported receipt from tests they ran themselves.']:[]),
  'Constraints: read-only except Carrier Pigeon MCP operations. Do not edit code, run fixture-writing tests, read secrets, use web access or change settings. The operator will run proposed reproductions. Do not create shared memory for this temporary review.',
  'Workflow: read/claim this ask and inspect the source. Round 1: use send to ask Codex for an independent review of the same narrow scope; include paths, acceptance criteria, request_key, timeout_seconds and effort medium, the current mailbox thread and wake_on_reply true. End your turn after sending; its reply will resume you. Do not use a blocking ask.',
  'Round 2 after its first reply: inspect Codex\'s evidence yourself. Send a second ask to Codex in this same thread, with wake_on_reply true and a fresh request_key, challenging its strongest proposed defect or, if none, its strongest safety conclusion using a concrete edge case. End your turn again. Do not mark the original ask done while waiting; heartbeat it when making progress.',
  'After the second reply, synthesize only supported findings. An honest empty findings array is valid. Distinguish static reasoning from tests actually run. Cite both peer ask and reply IDs in the final result; coverage must say what you checked and did not check. Final reply to this original ask uses outcome completed, a typed result matching its reply_schema, and evidence array. Do not fabricate a finding or receipt to satisfy the test.',
  'Acceptance: two genuine Claude->Codex asks and Codex->Claude replies, critique in round 2, then a final structured review. The operator independently checks the messages, source hashes and any proposed bugs.'
 ].join('\n'));
 let final;
 while(Date.now()-t0<minutes*60000+30000){
  const state=cli('task',message.id,'--as','grok','--session','collaboration-driver');
  const events=H.readReceipts(root,message.id);const last=events.at(-1);
  const progress=JSON.stringify({state:state.state,delivery:last?.ev,progress:state.progress});if(progress!==previous){console.log(JSON.stringify({event:'progress',elapsed_s:Math.round((Date.now()-t0)/1000),...JSON.parse(progress)}));previous=progress;}
  const waited=await cp.waitReply(message.id,'grok',{session:'collaboration-driver',timeoutMs:0,keep:true});
  if(waited.status==='replied'){final=waited;break;}
  if(['expired','cancelled','blocked','declined','partial','closed_without_reply'].includes(waited.status))throw new Error('Review did not complete: '+JSON.stringify(waited));
  await sleep(3000);
 }
 if(!final)throw new Error('Collaboration exceeded its deadline');
 const result=typeof final.reply.result==='string'?JSON.parse(final.reply.result):final.reply.result;
 const messages=cp.thread(message.thread);const byId=new Map(messages.map(m=>[m.id,m]));
 const asks=result.peer_ask_ids.map(id=>byId.get(id));const replies=result.peer_reply_ids.map(id=>byId.get(id));
 assert.equal(new Set(result.peer_ask_ids).size,2);assert.equal(new Set(result.peer_reply_ids).size,2);
 for(let i=0;i<2;i++){assert.equal(asks[i]?.from,'claude');assert.equal(asks[i]?.to,'codex');assert.equal(asks[i]?.wake_on_reply,true);assert.ok(asks[i]?.request_key);assert.equal(replies[i]?.from,'codex');assert.equal(replies[i]?.to,'claude');assert.equal(replies[i]?.reply_to,asks[i].id);assert.ok(replies[i]?.body);assert.equal(cli('task',asks[i].id,'--as','claude','--session','listener').state,'completed');}
 assert.ok(asks[1].created>=replies[0].created,'second review follows first answer');
 for(const [file,digest]of Object.entries(pinned))assert.equal(sha(path.join(root,file)),digest,'source stays pinned');
 const usagePath=path.join(root,'host/logs/usage.jsonl');
 let usage=[];for(let n=0;n<40;n++){usage=fs.existsSync(usagePath)?fs.readFileSync(usagePath,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse):[];if(usage.filter(u=>u.agent==='claude').length>=3&&usage.filter(u=>u.agent==='codex').length>=2)break;await sleep(1000);}
 const claude=usage.filter(u=>u.agent==='claude'),codex=usage.filter(u=>u.agent==='codex');
 assert.ok(claude.length>=3&&claude.filter(u=>u.resumed).length>=2,'Claude resumes both peer replies');
 assert.ok(codex.length>=2&&new Set(codex.map(u=>u.thread)).size===1,'Codex uses one native conversation');
 report={passed:true,root,elapsed_s:Math.round((Date.now()-t0)/1000),ask:message.id,thread:message.thread,pinned,result,usage,messages:messages.map(m=>({id:m.id,from:m.from,to:m.to,reply_to:m.reply_to,kind:m.kind,created:m.created,body:m.body})),live_mailbox_untouched:before===null||fs.statSync(liveLog).mtimeMs===before};assert.ok(report.live_mailbox_untouched);
}catch(error){report={passed:false,root,elapsed_s:Math.round((Date.now()-t0)/1000),ask:message?.id,error:String(error.stack||error)};process.exitCode=1;}
finally{
 // Stop Windows descendants before their parent goes away, including per-conversation MCP servers.
 const pid=adapters.codex?.sup?.child?.pid;if(process.platform==='win32'&&Number.isInteger(pid)){adapters.codex.sup.stopped=true;try{execFileSync('taskkill.exe',['/PID',String(pid),'/T','/F'],{windowsHide:true,stdio:'ignore',timeout:10000});}catch{}}
 await host.stop();await sleep(500);
 fs.writeFileSync(path.join(root,'collaboration-report.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({event:'finished',passed:report.passed,root,elapsed_s:report.elapsed_s,result:report.result,error:report.error},null,2));
}
