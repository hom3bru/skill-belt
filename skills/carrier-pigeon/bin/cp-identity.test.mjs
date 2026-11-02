// Isolated compatibility tests: fictional actor, software RSA keys, no Windows Hello operations.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
import crypto from 'node:crypto'; import assert from 'node:assert/strict'; import {spawnSync} from 'node:child_process';
const ROOT=fs.mkdtempSync(path.join(os.tmpdir(),'cp-identity-'));
process.env.CARRIER_PIGEON_HOME=ROOT;
process.env.CARRIER_PIGEON_HUMAN_ID='legacy-person';
process.env.CARRIER_PIGEON_HELLO_KEY_NAME='fixture-existing-key';
process.env.CARRIER_PIGEON_LEGACY_APPROVAL_FIELD='requires_legacy_person_approval';
const identity=await import('./cp-identity.mjs'), cp=await import('./carrier-pigeon.mjs'), hello=await import('./cp-hello.mjs');
const host=await import('../host/carrier-pigeon-host.mjs');
const HERE=path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'));
const CLI=path.join(HERE,'carrier-pigeon.mjs'); let n=0,failed=0;
const t=async(name,fn)=>{n++;try{await fn();console.log('ok',n,name);}catch(e){failed++;console.log('not ok',n,name);console.log(e.stack);}};
const run=(args,env=process.env)=>spawnSync(process.execPath,[CLI,...args],{env,encoding:'utf8',windowsHide:true});
const defaults={...process.env}; for(const k of ['CARRIER_PIGEON_HUMAN_ID','CARRIER_PIGEON_HELLO_KEY_NAME','CARRIER_PIGEON_LEGACY_APPROVAL_FIELD'])delete defaults[k];
cp.init();
const keys=crypto.generateKeyPairSync('rsa',{modulusLength:2048}),der=keys.publicKey.export({format:'der',type:'spki'});
const pub={key:keys.publicKey,fingerprint:hello.fingerprint(der)};
const sign=b=>crypto.sign('sha256',b,{key:keys.privateKey,padding:crypto.constants.RSA_PKCS1_PADDING});
const legacyField='requires_legacy_person_approval';
function oldPayload(m,v){
 const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
 const p={v,alg:'win-hello-rsa-pkcs1-sha256',id:m.id,from:m.from,to:m.to,to_session:m.to_session||null,thread:m.thread,reply_to:m.reply_to||null,kind:m.kind,subject:m.subject,created:m.created,expires:m.sig_expires,body_sha256:sha(String(m.body??'').trim()),context_sha256:m.context?sha(m.context):null};
 if(v===2)p.execution={from_session:m.from_session??null,transcript:m.transcript??null,fork_codex_thread:m.fork_codex_thread??null,fork_claude_session:m.fork_claude_session??null,wake_on_reply:m.wake_on_reply??null,due:m.due??null,[legacyField]:m[legacyField]??null,request_key:m.request_key??null,expires_at:m.expires_at??null,timeout_seconds:m.timeout_seconds!=null?Number(m.timeout_seconds):null,effort:m.effort??null,reply_schema:m.reply_schema??null,outcome:m.outcome??null,result:m.result??null,evidence:m.evidence??null};
 return Buffer.from(JSON.stringify(p));
}
function oldMessage(v){const m=cp.build({from:'legacy-person',to:'codex',subject:'fictional review',body:'Review only',_noStdin:true});delete m.requires_user_approval;Object.assign(m,{sig_version:v,sig_alg:hello.SIG_ALG,sig_key:pub.fingerprint,sig_expires:new Date(Date.now()+600000).toISOString()});if(v===2)m[legacyField]=true;m.sig=sign(oldPayload(m,v)).toString('base64');return m;}
await t('default identity is generic and explicit compatibility references select existing identity',()=>{
 const check=spawnSync(process.execPath,['--input-type=module','-e',`import * as i from ${JSON.stringify(new URL('./cp-identity.mjs',import.meta.url).href)}; console.log(JSON.stringify([i.HUMAN_ID,i.HELLO_KEY_NAME,i.LEGACY_APPROVAL_FIELD]))`],{env:defaults,encoding:'utf8'});
 assert.equal(check.status,0,check.stderr);assert.deepEqual(JSON.parse(check.stdout),['user','carrier-pigeon-user','requires_user_approval']);
 assert.equal(hello.KEY_NAME,'fixture-existing-key');assert.ok(cp.AGENTS.includes('legacy-person'));assert.ok(host.AGENTS.includes('legacy-person'));assert.ok(!cp.AGENTS.includes('user'));
});
await t('independently serialized v1 and v2 signatures retain exact payload bytes',()=>{
 for(const v of [1,2]){const m=oldMessage(v);assert.deepEqual(hello.authorityPayload(m),oldPayload(m,v));assert.equal(hello.verifyAuthority(m,pub).status,'verified');assert.equal(hello.verifyAuthority({...m,body:'different'},pub).status,'invalid');}
});
await t('reading original signed records preserves bytes and legacy approval intent',()=>{
 const m=oldMessage(2),{body,...fm}=m;const raw='---\n'+Object.entries(fm).map(([k,v])=>k+': '+JSON.stringify(v)).join('\n')+'\n---\n\n'+body+'\n';
 const f=path.join(ROOT,'agents/codex/inbox',m.id+'.md');fs.writeFileSync(f,raw);const loaded=cp.load(m.id).msg;
 assert.equal(hello.verifyAuthority(loaded,pub).status,'verified');assert.equal(identity.approvalRequired(loaded),true);assert.match(cp.fmt(loaded),/NEEDS USER/);assert.equal(fs.readFileSync(f,'utf8'),raw);
});
await t('new v3 signatures bind canonical controls and reject legacy marker injection',()=>{
 const m=cp.build({from:'legacy-person',to:'codex',subject:'new review',body:'Only this task',_noStdin:true,'requires-user-approval':true});
 cp.signAsHuman(m,{}, {pub,sign});assert.equal(m.sig_version,3);assert.equal(hello.verifyAuthority(m,pub).status,'verified');
 assert.equal(hello.verifyAuthority({...m,requires_user_approval:false},pub).status,'invalid');assert.equal(hello.verifyAuthority({...m,[legacyField]:true},pub).status,'invalid');
});
await t('old versions cannot authenticate new or conflicting approval controls',()=>{
 const v1=oldMessage(1),v2=oldMessage(2);
 assert.equal(hello.verifyAuthority({...v1,requires_user_approval:true},pub).status,'invalid');
 assert.equal(hello.verifyAuthority({...v2,requires_user_approval:true},pub).status,'invalid');
 assert.throws(()=>identity.approvalRequired({requires_user_approval:false,[legacyField]:true}),/Conflicting/);
 assert.throws(()=>identity.approvalRequired({requires_unknown_approval:true}),/Unknown/);
 assert.equal(hello.verifyAuthority({...v2,from:'codex'},pub).status,'n/a');assert.equal(hello.verifyAuthority({...v2,sig:null},pub).status,'unsigned');
});
await t('explicit legacy CLI marker maps to canonical new records and conflicts fail closed',()=>{
 const r=run(['send','--from','legacy-person','--to','codex','--subject','fixture','--body','review','--requires-legacy-person-approval','--json']);assert.equal(r.status,0,r.stderr);const m=cp.load(JSON.parse(r.stdout).id).msg;assert.equal(m.requires_user_approval,true);assert.equal(Object.hasOwn(m,legacyField),false);
 const conflict=run(['send','--from','legacy-person','--to','codex','--subject','fixture','--body','review','--requires-user-approval=false','--requires-legacy-person-approval']);assert.notEqual(conflict.status,0);
});
await t('mismatched identity cannot initialize or install over an existing mailbox',()=>{
 const before=fs.readFileSync(path.join(ROOT,'log.jsonl'));
 for(const action of ['init','install']){const r=run([action],defaults);assert.notEqual(r.status,0);assert.match(r.stderr,/identity differs/);}
 assert.equal(fs.existsSync(path.join(ROOT,'agents/user')),false);assert.deepEqual(fs.readFileSync(path.join(ROOT,'log.jsonl')),before);
});
await t('human-only instructions remain denied to agents under custom identity',()=>{
 assert.notEqual(run(['memory','instructions','fixture','--as','codex','--text','not permitted']).status,0);
 assert.equal(run(['memory','instructions','fixture','--as','legacy-person','--text','fixture instruction']).status,0);
 assert.throws(()=>cp.signAsHuman(cp.build({from:'codex',to:'claude',subject:'no','body':'no',_noStdin:true}),{}, {pub,sign}),/only for messages/);
});
fs.rmSync(ROOT,{recursive:true,force:true});console.log(`# ${n} tests, ${failed} failed (identity)`);process.exit(failed?1:0);
