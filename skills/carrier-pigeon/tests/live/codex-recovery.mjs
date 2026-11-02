// Opt-in: two real Codex turns with a full listener restart between them, in a throwaway mailbox.
// Uses the existing Codex login/default model, no Claude/API-key setup. Never sends to the live mailbox.
// node tests/live/codex-recovery.mjs [--codex BIN] [--keep]
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import net from 'node:net';
import {spawnSync,execFileSync} from 'node:child_process'; import {fileURLToPath,pathToFileURL} from 'node:url';
const source=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const arg=(name,fallback)=>{const i=process.argv.indexOf('--'+name);return i<0?fallback:process.argv[i+1];};
const liveRoot=process.env.CARRIER_PIGEON_HOME||path.join(os.homedir(),'.carrier-pigeon');
const cfgFile=path.join(liveRoot,'host/config.json'),live=fs.existsSync(cfgFile)?JSON.parse(fs.readFileSync(cfgFile,'utf8')):{};
const liveLog=path.join(liveRoot,'log.jsonl'),before=fs.existsSync(liveLog)?fs.statSync(liveLog).mtimeMs:null;
const root=fs.mkdtempSync(path.join(os.tmpdir(),'cp-codex-recovery-')),env={...process.env,CARRIER_PIGEON_HOME:root};
const cli=(...args)=>{const r=spawnSync(process.execPath,[path.join(source,'bin/carrier-pigeon.mjs'),...args,'--json'],{env,encoding:'utf8',windowsHide:true,timeout:30000});
  if(![0,3,4].includes(r.status))throw new Error(String(r.stderr||r.error||'CLI failed').slice(0,1000));return JSON.parse(r.stdout);};
cli('install');process.env.CARRIER_PIGEON_HOME=root;
const H=await import(pathToFileURL(path.join(root,'host/carrier-pigeon-host.mjs')).href),cp=await import(pathToFileURL(path.join(root,'bin/carrier-pigeon.mjs')).href);
const port=await new Promise((resolve,reject)=>{const s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p));});});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const until=async(fn,ms=30000)=>{const end=Date.now()+ms;while(Date.now()<end){const r=fn();if(r)return r;await sleep(250);}return null;};
const usageFile=path.join(root,'host/logs/usage.jsonl');
const usage=()=>fs.existsSync(usageFile)?fs.readFileSync(usageFile,'utf8').split('\n').filter(Boolean).map(JSON.parse):[];
let host,adapter;
const start=async()=>{adapter=H.codexAdapter();host=new H.Host({root,config:{watch:false,rescanMs:500,rate:{max:20,windowMs:600000},routes:{codex:['codex']},
  codex:{bin:arg('codex',live.codex?.bin||'codex'),port,lean:true,model:null}},adapters:{codex:adapter}});await host.start();
  if(!await until(()=>adapter.state.thread,60000))throw new Error('Codex did not become ready; inspect the temporary host logs');};
const stop=async()=>{if(!host)return;
  // The Windows process tree includes the per-thread MCP servers. Stop it before the app-server parent disappears.
  const sup=adapter?.sup,pid=sup?.child?.pid;if(process.platform==='win32'&&Number.isInteger(pid)){sup.stopped=true;try{execFileSync('taskkill.exe',['/PID',String(pid),'/T','/F'],{windowsHide:true,stdio:'ignore',timeout:10000});}catch{}}
  await host.stop();host=null;await sleep(500);
};
const ask=(subject,body,key,thread)=>cli('send','--from','grok','--session','recovery-harness','--to','codex','--subject',subject,'--body',body,
  '--request-key',key,'--timeout-seconds','360','--effort','low','--reply-schema','{"type":"object","properties":{"answer":{"type":"number"}},"required":["answer"],"additionalProperties":false}',...(thread?['--thread',thread]:[]));
const answer=async m=>{const w=await cp.waitReply(m.id,'grok',{session:'recovery-harness',timeoutMs:380000});if(w.status!=='replied')throw new Error('No completed reply: '+JSON.stringify(w));
  const result=typeof w.reply.result==='string'?JSON.parse(w.reply.result):w.reply.result;if(!result||typeof result.answer!=='number')throw new Error('Reply did not satisfy its structured contract');
  if(!await until(()=>usage().some(u=>u.msg===m.id),60000))throw new Error('The native turn did not finish after replying');return result.answer;};
const t0=Date.now();let report;
try{await start();const first=ask('Codex restart recovery step one','Compute 17 * 23. Reply using outcome completed and result {answer: the number}. Keep this conversation for a follow-up. Do not write shared memory for this temporary fixture.','live-recovery-first');
  const a=await answer(first);await stop();await start();
  const second=ask('Codex restart recovery step two','Add 100 to your previous answer in this native conversation. Reply using outcome completed and result {answer: the number}. Do not use shared memory.','live-recovery-second',first.thread);
  const b=await answer(second),rows=usage().filter(u=>[first.id,second.id].includes(u.msg)),ids=[...new Set(rows.map(u=>u.thread))];
  const status=cp.taskStatus(second.id,'grok',{session:'recovery-harness'});
  report={correct:a===391&&b===491,answers:[a,b],same_native_thread:ids.length===1&&rows.length>=2,structured_outcome:status.outcome,elapsed_seconds:Math.round((Date.now()-t0)/1000),
    no_false_recovery:[first,second].every(m=>!H.readReceipts(root,m.id).some(r=>r.ev==='recovery-needed')),
    live_mailbox_untouched:before===null?!fs.existsSync(liveLog):fs.statSync(liveLog).mtimeMs===before};
  if(!report.correct||!report.same_native_thread||!report.no_false_recovery||!report.live_mailbox_untouched||status.outcome!=='completed')throw new Error('Recovery trial failed: '+JSON.stringify(report));
}catch(e){report={...report,error:e.message,elapsed_seconds:Math.round((Date.now()-t0)/1000)};process.exitCode=1;}
finally{await stop();console.log(JSON.stringify(report,null,2));
  if(process.argv.includes('--keep')||process.exitCode)console.log('Temporary evidence: '+root);
  else{const resolved=path.resolve(root),temp=path.resolve(os.tmpdir());if(!resolved.startsWith(temp+path.sep))throw new Error('Refusing to remove a non-temporary path');try{fs.rmSync(root,{recursive:true,force:true});}catch{console.log('Remove temporary evidence later: '+root);}}}
