// Lifecycle fixtures use one disposable mailbox. No provider, listener, signing gesture or live inbox is touched.
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import crypto from 'node:crypto';import assert from 'node:assert/strict';import {spawn,spawnSync} from 'node:child_process';
import * as tasks from './cp-tasks.mjs';
const root=fs.mkdtempSync(path.join(os.tmpdir(),'cp-tasks-'));process.env.CARRIER_PIGEON_HOME=root;
const cp=await import('./carrier-pigeon.mjs');cp.init();let count=0,failed=0;
const t=async(name,fn)=>{count++;try{await fn();console.log('ok',count,name);}catch(e){failed++;console.log('not ok',count,name);console.log(String(e.stack||e).split('\n').slice(0,8).join('\n'));}};
const send=(extra={})=>cp.send({from:'codex',to:'claude',subject:'lifecycle fixture',body:'Inspect fixture only.',...extra});
const finish=(m,extra={})=>cp.reply(m.id,{as:'claude',body:'Fixture complete.',...extra});
const wait=(m,extra={})=>cp.waitReply(m.id,'codex',{timeoutMs:0,...extra});
const file=id=>path.join(root,'tasks',id+'.json');
const childEnv={...process.env,CP_TEST_CP:new URL('./carrier-pigeon.mjs',import.meta.url).href,CP_TEST_TASKS:new URL('./cp-tasks.mjs',import.meta.url).href};

await t('a durable request key deduplicates semantic content across sender sessions and rejects changed content',()=>{
  const a=send({session:'original',request_key:'dedupe-one',timeout_seconds:60,effort:'high'});
  const b=send({session:'restarted',request_key:'dedupe-one',timeout_seconds:60,effort:'high'});assert.equal(b.id,a.id);assert.equal(b.replayed,true);assert.equal(b.from_session,'original');
  assert.throws(()=>send({request_key:'dedupe-one',timeout_seconds:60,effort:'high',body:'Different task.'}),/conflict/);
  assert.equal(cp.thread(a.thread).length,1);assert.equal(cp.outbox('codex',{session:'restarted'}).some(x=>x.id===a.id),false);
  assert.equal(cp.outbox('codex',{session:'restarted',request_key:'dedupe-one'})[0].id,a.id);});
await t('idempotent ask, wait, status and cancellation recover the original sender session with the key only',async()=>{
  const a=await cp.ask({from:'codex',to:'claude',subject:'recover',body:'b',session:'old',request_key:'recover-one',wait:0});
  const answer=finish({id:a.sent});assert.throws(()=>cp.taskStatus(a.sent,'codex',{session:'new'}),/sent by session old/);
  assert.equal((await cp.waitReply(a.sent,'codex',{timeoutMs:0,session:'new',request_key:'recover-one'})).reply.id,answer.id);
  assert.equal(cp.taskStatus(a.sent,'codex',{session:'new',request_key:'recover-one'}).state,'completed');
  const second=send({session:'old',request_key:'recover-cancel'});assert.throws(()=>cp.cancelTask(second.id,'codex',{session:'new'}),/sent by session old/);
  assert.equal(cp.cancelTask(second.id,'codex',{session:'new',request_key:'recover-cancel'}).state,'cancelled');});
await t('prepared intent survives a process crash before publication and replays the exact stored message once',()=>{
  const script="const cp=await import(process.env.CP_TEST_CP);const t=await import(process.env.CP_TEST_TASKS);const m=cp.build({from:'codex',to:'claude',subject:'crash prepare',body:'b',session:'lost',request_key:'crash-prepare'});t.idempotent(cp.ROOT,'codex','crash-prepare',m,()=>process.exit(7));";
  assert.equal(spawnSync(process.execPath,['--input-type=module','-e',script],{env:childEnv}).status,7);
  const record=tasks.getRequest(root,'codex','crash-prepare');assert.equal(record.state,'prepared');assert.equal(cp.outbox('codex',{request_key:'crash-prepare'})[0].state,'prepared');
  const result=send({subject:'crash prepare',body:'b',session:'new',request_key:'crash-prepare'});assert.equal(result.id,record.message.id);assert.equal(result.created,record.message.created);
  assert.equal(cp.thread(result.thread).length,1);});
await t('a crash after publication repairs the request journal and thread index without a duplicate',()=>{
  const m=cp.build({from:'codex',to:'claude',subject:'crash publish',body:'b',request_key:'crash-publish'});
  assert.throws(()=>tasks.idempotent(root,'codex','crash-publish',m,msg=>{cp.write(msg);throw new Error('crash after write');}),/crash after write/);
  fs.writeFileSync(path.join(root,'threads',m.thread+'.idx'),'');const replay=send({subject:'crash publish',body:'b',request_key:'crash-publish'});
  assert.equal(replay.id,m.id);assert.equal(cp.thread(m.thread).length,1);assert.equal(tasks.getRequest(root,'codex','crash-publish').state,'delivered');});
await t('concurrent processes with the same key publish one ask and all recover its id',async()=>{
  const script="const cp=await import(process.env.CP_TEST_CP);console.log(cp.send({from:'codex',to:'claude',subject:'concurrent',body:'b',request_key:'concurrent-key',session:process.env.CP_TEST_SESSION}).id);";
  const runs=await Promise.all(Array.from({length:6},(_,i)=>new Promise(resolve=>{const p=spawn(process.execPath,['--input-type=module','-e',script],{env:{...childEnv,CP_TEST_SESSION:'worker-'+i},stdio:['ignore','pipe','pipe']});let out='',err='';p.stdout.on('data',x=>out+=x);p.stderr.on('data',x=>err+=x);p.on('exit',code=>resolve({code,out:out.trim(),err}));})));
  assert.ok(runs.every(r=>r.code===0),JSON.stringify(runs));assert.equal(new Set(runs.map(r=>r.out)).size,1);assert.equal(cp.thread(runs[0].out).length,1);});
await t('queued cancellation closes delivery, active cancellation waits for worker acknowledgement and neither implies undo',async()=>{
  const queued=send();assert.equal(cp.cancelTask(queued.id,'codex',{reason:'No longer needed.'}).state,'cancelled');assert.throws(()=>cp.claim(queued.id,'claude'),/cancelled/);assert.equal((await wait(queued)).status,'cancelled');
  const active=send();cp.claim(active.id,'claude','worker');assert.equal(cp.cancelTask(active.id,'codex').state,'cancel_requested');
  assert.equal(cp.heartbeat(active.id,'claude',{session:'worker',progress:'Observed cancellation; stopping.'}).cancel_requested,true);
  cp.done(active.id,'claude','done','worker');assert.equal(cp.taskStatus(active.id,'codex').state,'cancelled');assert.equal((await wait(active)).status,'cancelled');});
await t('expiry is enforced independently of advisory due and waits end promptly',async()=>{
  const advisory=send({due:'2000-01-01T00:00:00Z'});assert.equal(tasks.control(root,advisory.id).state,'queued');
  const m=send({timeout_seconds:0.03});const start=Date.now();const result=await cp.waitReply(m.id,'codex',{timeoutMs:10000});
  assert.equal(result.status,'expired');assert.ok(Date.now()-start<1000);assert.throws(()=>cp.claim(m.id,'claude'),/expired/);});
await t('closed-without-reply is terminal and AbortSignal stops only the wait',async()=>{
  const closed=send();cp.claim(closed.id,'claude');cp.done(closed.id,'claude');assert.equal((await wait(closed)).status,'closed_without_reply');
  const m=send();const controller=new AbortController();const pending=cp.waitReply(m.id,'codex',{timeoutMs:10000,signal:controller.signal});setTimeout(()=>controller.abort(),20);
  assert.equal((await pending).status,'aborted');assert.equal(cp.taskStatus(m.id,'codex').state,'queued');finish(m);assert.equal((await wait(m)).status,'replied');});
await t('reply schemas validate before claiming or closing; plain replies remain valid without a schema',()=>{
  const schema={type:'object',properties:{count:{type:'integer',minimum:0},notes:{type:'array',items:{type:'string'},maxItems:2}},required:['count'],additionalProperties:false};
  const m=send({reply_schema:schema});assert.throws(()=>finish(m,{result:{count:'wrong'}}),/must be integer/);assert.equal(cp.load(m.id).box,'inbox');
  const r=finish(m,{result:{count:2,notes:['Observed fixture.']},outcome:'partial',evidence:['fixture.mjs:1']});const status=cp.taskStatus(m.id,'codex');
  assert.equal(status.state,'partial');assert.equal(r.outcome,'partial');assert.deepEqual(status.result,{count:2,notes:['Observed fixture.']});assert.deepEqual(status.evidence,['fixture.mjs:1']);
  assert.equal(finish(send()).outcome,'completed');assert.throws(()=>send({reply_schema:{type:'object',$ref:'https://example.com/schema'}}),/unsupported/);});
await t('numeric sessions retain ownership; heartbeats renew leases and expired claims need deliberate reasoned reclamation',()=>{
  const m=send();cp.claim(m.id,'claude','12345');assert.throws(()=>cp.done(m.id,'claude'),/claimed by/);
  const before=tasks.control(root,m.id).lease_expires_at;const h=cp.heartbeat(m.id,'claude',{session:'12345',lease_seconds:600,progress:'Fixture checked.'});assert.ok(h.lease_expires_at>before);
  tasks.updateControl(root,m.id,{lease_expires_at:'2000-01-01T00:00:00Z'});assert.equal(cp.taskStatus(m.id,'codex').lease_expired,true);
  assert.throws(()=>cp.heartbeat(m.id,'claude',{session:'12345'}),/lease expired/);assert.throws(()=>cp.reclaimTask(m.id,'claude',{session:'next'}),/reason/);
  const reclaimed=cp.reclaimTask(m.id,'claude',{session:'next',reason:'Reviewed interrupted fixture; no effects to repeat.'});assert.equal(reclaimed.claimed_session,'next');
  assert.throws(()=>finish(m,{session:'12345'}),/claim_token|claimed by/);assert.throws(()=>finish(m,{session:'next'}),/claim_token/);finish(m,{session:'next',claim_token:reclaimed.claim_token});});
await t('new metadata rejects secrets and unsafe or oversized schemas without writing requests',()=>{
  assert.throws(()=>send({request_key:'ghp_'+'A'.repeat(36)}),/secret/);assert.throws(()=>send({timeout_seconds:-1}),/timeout_seconds/);
  assert.throws(()=>send({effort:'unlimited'}),/effort/);assert.throws(()=>send({reply_schema:{type:'object',pattern:'.*'}}),/unsupported/);
  assert.throws(()=>finish(send(),{result:{token:'ghp_'+'A'.repeat(36)}}),/secret/);assert.throws(()=>tasks.control(root,'../outside'),/bad task id/);});
await t('dead process locks recover, and a terminal task cannot be made runnable by a late host event',()=>{
  const script="const t=await import(process.env.CP_TEST_TASKS);t.withLock(process.env.CARRIER_PIGEON_HOME,'dead-fixture-lock',()=>process.exit(7));";
  assert.equal(spawnSync(process.execPath,['--input-type=module','-e',script],{env:childEnv}).status,7);assert.equal(tasks.withLock(root,'dead-fixture-lock',()=>42),42);
  const m=send();cp.cancelTask(m.id,'codex');assert.throws(()=>tasks.updateControl(root,m.id,{state:'running'}),/already cancelled/);});
await t('normalized request keys recover consistently, and prepared journal corruption fails before publication',()=>{
  const m=send({request_key:'  normalized-key  ',session:'old'});assert.equal(m.request_key,'normalized-key');assert.equal(cp.taskStatus(m.id,'codex',{session:'new',request_key:'  normalized-key  '}).id,m.id);
  const prepared=cp.build({from:'codex',to:'claude',subject:'corrupt request',body:'original',request_key:'corrupt-journal'});
  assert.throws(()=>tasks.idempotent(root,'codex','corrupt-journal',prepared,()=>{throw new Error('interrupted');}),/interrupted/);
  const location=path.join(root,'tasks','requests','codex',crypto.createHash('sha256').update('corrupt-journal').digest('hex')+'.json');
  const record=JSON.parse(fs.readFileSync(location,'utf8'));record.message.body='changed after preparation';fs.writeFileSync(location,JSON.stringify(record));
  assert.throws(()=>send({subject:'corrupt request',body:'original',request_key:'corrupt-journal'}),/integrity/);assert.throws(()=>cp.load(prepared.id),/not found/);});
await t('active deadlines request a stop until acknowledgement; completed answers remain readable after their deadline',async()=>{
  const active=send({timeout_seconds:60});cp.claim(active.id,'claude','worker');tasks.updateControl(root,active.id,{lease_expires_at:active.expires_at});const realNow=Date.now;
  try{Date.now=()=>Date.parse(active.expires_at)+1;const state=cp.taskStatus(active.id,'codex');assert.equal(state.state,'cancel_requested');assert.equal(state.terminal,false);assert.equal(state.execution_stopped,false);assert.equal(state.potential_partial,true);assert.match(state.next_action,/stop acknowledgement/);
    assert.equal((await wait(active)).status,'expired');cp.done(active.id,'claude','done','worker');assert.equal(cp.taskStatus(active.id,'codex').state,'expired');assert.equal(cp.taskStatus(active.id,'codex').execution_stopped,true);
  }finally{Date.now=realNow;}
  const completed=send({timeout_seconds:60}),reply=finish(completed);try{Date.now=()=>Date.parse(completed.expires_at)+1;assert.equal(cp.taskStatus(completed.id,'codex').state,'completed');assert.equal((await wait(completed)).reply.id,reply.id);}finally{Date.now=realNow;}});
await t('reclaim rotates a fencing token even for the same session; requester cannot see it and stale host writes fail',()=>{
  const m=send(),claim=cp.claim(m.id,'claude','same-worker');tasks.updateControl(root,m.id,{lease_expires_at:'2000-01-01T00:00:00Z'});
  const next=cp.reclaimTask(m.id,'claude',{session:'same-worker',reason:'Reviewed work after expired lease.'});assert.notEqual(next.claim_token,claim.claim_token);
  assert.equal('claim_token' in cp.taskStatus(m.id,'codex'),false);assert.equal('claim_token' in cp.outbox('codex').find(x=>x.id===m.id),false);
  assert.throws(()=>cp.heartbeat(m.id,'claude',{session:'same-worker',claim_token:claim.claim_token}),/claim_token/);
  assert.throws(()=>tasks.updateControl(root,m.id,{state:'completed'},{expected_claim_token:claim.claim_token}),/stale worker/);
  assert.throws(()=>cp.done(m.id,'claude','done','same-worker',{claim_token:claim.claim_token}),/claim_token/);
  cp.done(m.id,'claude','done','same-worker',{claim_token:next.claim_token});
  assert.throws(()=>finish(m,{session:'same-worker',claim_token:claim.claim_token}),/claim_token/);
  assert.equal(finish(m,{session:'same-worker',claim_token:next.claim_token}).follow_up,true);});
await t('legacy done asks stay terminal through failed claims and historical replies remain discoverable',async()=>{
  const without=send();cp.claim(without.id,'claude');cp.done(without.id,'claude');fs.unlinkSync(file(without.id));assert.throws(()=>cp.claim(without.id,'claude'),/closed_without_reply/);
  assert.equal(cp.taskStatus(without.id,'codex').state,'closed_without_reply');assert.equal((await wait(without)).status,'closed_without_reply');
  const withReply=send(),r=finish(withReply);fs.unlinkSync(file(withReply.id));fs.unlinkSync(file(r.id));assert.equal((await wait(withReply)).reply.id,r.id);
  assert.equal(cp.taskStatus(withReply.id,'codex').state,'completed');finish(withReply,{body:'A later follow-up.'});assert.equal(cp.taskStatus(withReply.id,'codex').terminal,true);});
await t('terminal intent precedes mailbox moves; interrupted reply publication recovers exact content without rerunning work',async()=>{
  const m=send({reply_schema:{type:'object',properties:{ok:{type:'boolean'}},required:['ok']}});cp.claim(m.id,'claude');const original=fs.renameSync;
  fs.renameSync=(from,to)=>{if(String(to)===file(m.id)&&JSON.parse(fs.readFileSync(from,'utf8')).state==='completed')throw new Error('injected terminal sidecar failure');return original(from,to);};
  try{assert.throws(()=>finish(m,{result:{ok:true}}),/injected/);}finally{fs.renameSync=original;}
  assert.equal(cp.load(m.id).box,'claimed');assert.equal(cp.thread(m.thread).length,1,'failed terminal intent publishes no answer');
  fs.renameSync=(from,to)=>{if(String(to).includes(path.join('agents','codex','inbox'))&&String(to).endsWith('.md'))throw new Error('injected reply publication failure');return original(from,to);};
  try{assert.throws(()=>finish(m,{result:{ok:true},evidence:['fixture: durable result']}),/injected/);}finally{fs.renameSync=original;}
  const before=fs.readdirSync(path.join(root,'agents','codex','inbox')).length,status=cp.taskStatus(m.id,'codex');assert.equal(status.state,'completed');assert.equal(status.publication_pending,true);assert.deepEqual(status.result,{ok:true});assert.match(status.next_action,/wait_reply/);
  assert.equal(fs.readdirSync(path.join(root,'agents','codex','inbox')).length,before,'status remains observational');
  const answer=await wait(m);assert.equal(answer.status,'replied');assert.deepEqual(JSON.parse(answer.reply.result),{ok:true});assert.equal(cp.load(m.id).box,'done');assert.equal(cp.taskStatus(m.id,'codex').publication_pending,false);
  assert.equal(cp.thread(m.thread).length,2);});
await t('retrying a reply preserves and recovers its committed result after interrupted publication',async()=>{
  for(const failure of ['reply-publication','thread-index','ask-finalization','control-clear']){const m=send(),original=fs.renameSync,append=fs.appendFileSync;
    try{fs.renameSync=(from,to)=>{const destination=String(to);if((failure==='reply-publication'&&destination.startsWith(path.join(root,'agents','codex','inbox')+path.sep))||(failure==='ask-finalization'&&destination===path.join(root,'agents','claude','done',m.id+'.md'))||(failure==='control-clear'&&destination===file(m.id)&&JSON.parse(fs.readFileSync(from,'utf8')).prepared_reply===null))throw new Error('injected reply retry failure');return original(from,to);};
      fs.appendFileSync=(file,...args)=>{if(failure==='thread-index'&&String(file)===path.join(root,'threads',m.thread+'.idx'))throw new Error('injected reply retry failure');return append(file,...args);};
      assert.throws(()=>finish(m,{body:'The committed answer.',result:{version:1},outcome:'completed'}),/injected/);
    }finally{fs.renameSync=original;fs.appendFileSync=append;}
    const committed=tasks.control(root,m.id).prepared_reply;assert.ok(committed);
    assert.equal(cp.load(m.id).box,failure==='control-clear'?'done':'claimed');
    const retried=finish(m,{body:'A different answer must not replace the committed one.',result:{version:2},outcome:'partial'});
    assert.equal(retried.id,committed.id);assert.equal(retried.publication_recovered,true);
    assert.equal(cp.load(m.id).box,'done');assert.equal(cp.taskStatus(m.id,'codex').state,'completed');
    assert.deepEqual(cp.taskStatus(m.id,'codex').result,{version:1});assert.equal(cp.taskStatus(m.id,'codex').outcome,'completed');
    assert.equal(cp.thread(m.thread).filter(r=>r.reply_to===m.id).length,1);
    assert.equal((await wait(m)).reply.id,committed.id);
  }
});
await t('cancelled controls block delivery even if mailbox finalization is interrupted; status summarizes bounded delivery failures',()=>{
  const m=send(),original=fs.renameSync;fs.renameSync=(from,to)=>{if(String(to)===path.join(root,'agents','claude','done',m.id+'.md'))throw new Error('injected cancel move failure');return original(from,to);};
  try{assert.throws(()=>cp.cancelTask(m.id,'codex'),/injected/);}finally{fs.renameSync=original;}
  assert.equal(cp.taskStatus(m.id,'codex').state,'cancelled');assert.throws(()=>cp.claim(m.id,'claude'),/cancelled/);
  fs.mkdirSync(path.join(root,'receipts'),{recursive:true});fs.writeFileSync(path.join(root,'receipts',m.id+'.jsonl'),JSON.stringify({ev:'turn-failed',reason:'f'.repeat(4000)})+'\n'+JSON.stringify({ev:'no-wake',reason:'cancelled'})+'\n');
  const status=cp.taskStatus(m.id,'codex');assert.equal(status.delivery.last_event.ev,'no-wake');assert.equal(status.delivery.last_failure.reason,'cancelled');assert.match(status.next_action,/partial effects/);});
await t('malformed legacy lock files fail with actionable diagnostics instead of unsafe age-based deletion',()=>{
  const name=crypto.createHash('sha256').update('corrupt-lock').digest('hex')+'.lock',where=path.join(root,'tasks','.locks',name);fs.writeFileSync(where,'{"pid":');
  assert.throws(()=>tasks.withLock(root,'corrupt-lock',()=>{}),/corrupt or incomplete/);assert.equal(fs.readFileSync(where,'utf8'),'{"pid":');});
await t('a claim published before a failed control commit remains observable and can be deliberately reclaimed after its lease',()=>{
  const m=send(),original=fs.renameSync;fs.renameSync=(from,to)=>{if(String(to)===file(m.id)&&JSON.parse(fs.readFileSync(from,'utf8')).state==='claimed')throw new Error('injected claim control failure');return original(from,to);};
  try{assert.throws(()=>cp.claim(m.id,'claude','interrupted'),/injected/);}finally{fs.renameSync=original;}
  assert.equal(cp.load(m.id).box,'claimed');assert.equal(tasks.control(root,m.id).state,'queued');
  const observed=cp.taskStatus(m.id,'codex');assert.equal(observed.state,'claimed');assert.equal(observed.claimed_session,'interrupted');assert.ok(observed.lease_expires_at);
  assert.equal(tasks.control(root,m.id).state,'queued','observational status does not rewrite control');const realNow=Date.now;
  try{Date.now=()=>Date.parse(observed.lease_expires_at)+1;const reclaimed=cp.reclaimTask(m.id,'claude',{session:'replacement',reason:'Inspected interrupted claim and fixture effects.'});
    assert.equal(reclaimed.claimed_session,'replacement');assert.equal(tasks.control(root,m.id).state,'claimed');assert.ok(reclaimed.claim_token);
    finish(m,{session:'replacement',claim_token:reclaimed.claim_token});
  }finally{Date.now=realNow;}});
await t('interrupted reclaim revokes the old generation before either message or final control publication',async()=>{
  const {Host}=await import('../host/carrier-pigeon-host.mjs');const host=new Host({root,adapters:{}});
  for(const failure of ['message','final-control']){const m=send();const old=cp.claim(m.id,'claude','old-worker');
    tasks.updateControl(root,m.id,{lease_expires_at:new Date(Date.now()-1000).toISOString()});
    const original=fs.renameSync,claimed=cp.load(m.id).file;
    try{fs.renameSync=(from,to)=>{if((failure==='message'&&String(to)===claimed)||(failure==='final-control'&&String(to)===file(m.id)&&JSON.parse(fs.readFileSync(from,'utf8')).state==='claimed'))throw new Error('injected reclaim publication failure');return original(from,to);};
      assert.throws(()=>cp.reclaimTask(m.id,'claude',{session:'replacement',reason:'Inspected partial effects before takeover.'}),/injected/);
    }finally{fs.renameSync=original;}
    assert.throws(()=>tasks.updateControl(root,m.id,{state:'running',progress:'stale event'},{expected_claim_token:old.claim_token}),/stale worker/);
    assert.throws(()=>finish(m,{session:'old-worker',claim_token:old.claim_token}),/stale|claimed by/);
    assert.throws(()=>cp.done(m.id,'claude','done','old-worker',{claim_token:old.claim_token}),/stale|claimed by/);
    assert.throws(()=>cp.heartbeat(m.id,'claude',{session:'old-worker',claim_token:old.claim_token,progress:'stale progress'}),/stale|claimed by/);
    assert.equal(tasks.control(root,m.id).state,'recovery_needed');
    assert.notEqual(tasks.control(root,m.id).claim_token,old.claim_token);
    host.taskState(m.id,{state:'missing_reply',progress:'late native result'},old.claim_token);
    assert.equal(tasks.control(root,m.id).state,'recovery_needed','late native events cannot overwrite interrupted takeover');
    const tokenStatus=cp.taskStatus(m.id,'claude',{session:cp.load(m.id).msg.claimed_session});
    assert.equal(tokenStatus.claim_token,tasks.control(root,m.id).claim_token,'status exposes the authoritative fenced generation');
    const recovered=cp.reclaimTask(m.id,'claude',{session:'replacement',reason:'Inspected interrupted reclaim and retrying deliberately.'});
    assert.equal(recovered.state,'claimed');assert.equal(recovered.claimed_session,'replacement');
    finish(m,{session:'replacement',claim_token:recovered.claim_token});assert.equal(cp.taskStatus(m.id,'codex').state,'completed');
  }
});
await t('a completed result clears a transient recovery reason while delivery history remains available',()=>{
  const m=send();cp.claim(m.id,'claude','worker');const reason='Dispatch was in flight at restart; acceptance could not be established';
  tasks.updateControl(root,m.id,{state:'recovery_needed',reason});fs.mkdirSync(path.join(root,'receipts'),{recursive:true});
  fs.writeFileSync(path.join(root,'receipts',m.id+'.jsonl'),JSON.stringify({ev:'dispatch-failed',reason})+'\n');
  finish(m,{session:'worker'});const status=cp.taskStatus(m.id,'codex');assert.equal(status.state,'completed');assert.equal(status.reason,null);assert.equal(status.delivery.last_failure.reason,reason);});
await t('a requested success schema permits truthful blocked, declined and partial answers without fabricated data',async()=>{
  const schema={type:'object',properties:{count:{type:'integer'}},required:['count']};
  for(const outcome of ['blocked','declined','partial']){const m=send({reply_schema:schema});const reply=finish(m,{outcome,body:'Unable to produce the requested count; see this reported outcome.'});
    const status=cp.taskStatus(m.id,'codex');assert.equal(status.outcome,outcome);assert.equal(status.result,null);assert.equal((await wait(m)).reply.id,reply.id);}
  const m=send({reply_schema:schema});assert.throws(()=>finish(m,{outcome:'completed'}),/requires a structured result/);assert.equal(cp.load(m.id).box,'inbox');
  assert.throws(()=>finish(m,{outcome:'blocked',result:{count:'invalid'}}),/must be integer/,'any supplied result must still satisfy the contract');
});
await t('atomic replacement tolerates transient Windows locks and preserves data on permanent denial',()=>{
  const target=path.join(root,'atomic-replacement.json');tasks.atomic(target,{value:1});const original=fs.renameSync;let tries=0;
  try{fs.renameSync=(from,to)=>{if(String(to)===target&&++tries<3)throw Object.assign(new Error('fixture destination is temporarily busy'),{code:'EPERM'});return original(from,to);};
    tasks.atomic(target,{value:2});assert.equal(tries,3);assert.deepEqual(JSON.parse(fs.readFileSync(target,'utf8')),{value:2});
    tries=0;fs.renameSync=()=>{tries++;throw Object.assign(new Error('fixture permanent denial'),{code:'EACCES'});};
    assert.throws(()=>tasks.atomic(target,{value:3}),e=>e.code==='EACCES');assert.equal(tries,21,'permanent errors have a fixed retry bound');
    assert.deepEqual(JSON.parse(fs.readFileSync(target,'utf8')),{value:2},'failed replacement preserves the last committed record');
  }finally{fs.renameSync=original;}
});
fs.rmSync(root,{recursive:true,force:true});console.log(`# ${count} tests, ${failed} failed (tasks)`);process.exit(failed?1:0);
