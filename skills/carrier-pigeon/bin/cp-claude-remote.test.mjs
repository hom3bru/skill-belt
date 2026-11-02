// Disposable mailbox tests only. Never contacts the API or starts a Desktop process.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto'; import {execFileSync} from 'node:child_process'; import {fileURLToPath} from 'node:url';
import {ClaudeRemoteBridge,credentialProvider} from './cp-claude-remote.mjs'; import {remoteAddress} from './cp-claude-remote-client.mjs';
import * as tasks from './cp-tasks.mjs';
const CLI=fileURLToPath(new URL('./carrier-pigeon.mjs',import.meta.url));let count=0,failed=0;
const test=async(name,fn)=>{count++;try{await fn();console.log('ok',count,name);}catch(e){failed++;console.log('not ok',count,name);console.log(String(e.stack).split('\n').slice(0,5).join('\n'));}};
async function fixture(fn){const root=fs.mkdtempSync(path.join(os.tmpdir(),'cp-remote-engine-')),environmentId='env_'+randomUUID().replaceAll('-',''),address=remoteAddress(environmentId),calls=[],bridges=[];
 const cli=(...args)=>JSON.parse(execFileSync(process.execPath,[CLI,...args,'--json'],{env:{...process.env,CARRIER_PIGEON_HOME:root},encoding:'utf8'}));cli('init');
 const ask=(...args)=>cli('send','--from','codex','--to','claude','--to-session',address,'--subject','PRIVATE SUBJECT','--body','PRIVATE BODY',...args);
 const client={create:async p=>{calls.push({kind:'create',...p});return 'session_'+randomUUID().replaceAll('-','');},send:async p=>{calls.push({kind:'send',...p});},get:async id=>({response_shape:{id,environment_id:environmentId,environment_kind:'bridge'}})};
 const bridge=(extra={})=>{const b=new ClaudeRemoteBridge({root,environmentId,cwd:root,client,scanMs:60000,...extra});bridges.push(b);return b;};
 try{await fn({root,environmentId,address,calls,cli,ask,client,bridge});}finally{for(const b of bridges)await b.stop();fs.rmSync(root,{recursive:true,force:true});}}
await test('no native submission before mail; exact addressed mail submits one fixed pointer',()=>fixture(async({ask,calls,bridge})=>{
 const b=bridge();await b.start();assert.equal(calls.length,0);const m=ask();await b.scan();await b.scan();assert.equal(calls.length,1);assert.equal(calls[0].kind,'create');assert.ok(calls[0].text.includes(m.id));assert.ok(!calls[0].text.includes('PRIVATE'));}));
await test('follow-ups use the same native remote session instead of creating another',()=>fixture(async({ask,calls,bridge})=>{
 const b=bridge();await b.start();const m=ask('--thread','release.1');await b.scan();ask('--thread',m.thread);await b.scan();assert.deepEqual(calls.map(c=>c.kind),['create','send']);assert.match(calls[1].sessionId,/^session_/);}));
await test('a changed or non-Desktop environment binding cannot receive follow-ups',()=>fixture(async({ask,calls,bridge,client})=>{
 const b=bridge();await b.start();const m=ask();await b.scan();client.get=async id=>({response_shape:{id,environment_id:'env_AnotherEnvironment',environment_kind:'cloud'}});
 ask('--thread',m.thread);await b.scan();assert.deepEqual(calls.map(c=>c.kind),['create']);
}));
await test('ordinary Claude mail, other addresses and FYI never submit',()=>fixture(async({ask,bridge,calls})=>{
 const b=bridge();await b.start();const m=ask();for(const patch of [{to_session:null},{to_session:'other'},{kind:'fyi'},{to:'codex'}])assert.equal(await b.deliver({...m,...patch}),false);assert.equal(calls.length,0);}));
await test('a reply wakes only when the addressed Desktop session requested wake_on_reply',()=>fixture(async({address,bridge,cli,calls})=>{
 const b=bridge();await b.start();
 for(const wake of [false,true]){
  const m=cli('send','--from','claude','--session',address,'--to','codex','--subject','peer request','--body','fixture',...(wake?['--wake-on-reply']:[]));
  cli('reply',m.id,'--as','codex','--body','peer response');await b.scan();assert.equal(calls.length,wake?1:0);
 }
 assert.ok(calls[0].text.includes('MCP claim and done'));assert.ok(!calls[0].text.includes('PRIVATE'));
}));
await test('cancelled and expired asks never leave the mailbox',()=>fixture(async({root,ask,bridge,calls})=>{
 const b=bridge();await b.start();const m=ask();tasks.initialize(root,m);const c=tasks.readControl(root,m.id);tasks.saveControl(root,m.id,{...c,state:'cancelled',cancel_requested:true});assert.equal(await b.deliver(m),false);
 const n=ask();assert.equal(await b.deliver({...n,expires_at:new Date(0).toISOString()}),false);assert.equal(calls.length,0);}));
await test('uncertain API acceptance is retained and never automatically replayed',()=>fixture(async({root,ask,bridge})=>{
 let calls=0;const b=bridge({client:{create:async()=>{calls++;throw new Error('network error with private details');}}});await b.start();const m=ask();await b.scan();await b.scan();assert.equal(calls,1);
 const state=JSON.parse(fs.readFileSync(path.join(root,'host','claude-remote-deliveries',m.id+'.json')));assert.equal(state.phase,'uncertain');assert.equal(state.code,'DESKTOP_REMOTE_FAILED');assert.ok(!JSON.stringify(state).includes('private'));}));
await test('API rejection remains distinct from uncertain delivery',()=>fixture(async({root,ask,bridge})=>{
 const b=bridge({client:{create:async()=>{throw Object.assign(new Error('private body'),{code:'DESKTOP_API_HTTP_403',preDispatch:true});}}});await b.start();const m=ask();await b.scan();
 const state=JSON.parse(fs.readFileSync(path.join(root,'host','claude-remote-deliveries',m.id+'.json')));assert.equal(state.phase,'rejected');assert.equal(state.code,'DESKTOP_API_HTTP_403');}));
await test('duplicate watchers cannot take or remove another watcher ownership',()=>fixture(async({bridge})=>{
 const a=bridge(),b=bridge();await a.start();await assert.rejects(b.start(),{code:'DESKTOP_REMOTE_OWNER_ACTIVE'});await b.stop();await assert.rejects(bridge().start(),{code:'DESKTOP_REMOTE_OWNER_ACTIVE'});}));
await test('agents discovers a stable Desktop address while its dispatcher is alive',()=>fixture(async({root,address,bridge,cli})=>{
 const b=bridge();await b.start();const session=cli('agents').find(a=>a.agent==='claude').sessions.find(s=>s.session===address);assert.equal(session.wake_via,'desktop:remote-control');
 assert.ok(!JSON.stringify(session).includes(b.token));await b.stop();assert.ok(!fs.existsSync(path.join(root,'sessions','claude~'+address+'.json')));
}));
await test('bounded rate defers a burst and submits it after the window clears',()=>fixture(async({ask,bridge,calls})=>{
 let clock=Date.now();const b=bridge({now:()=>clock});await b.start();for(let n=0;n<4;n++)ask();await b.scan();assert.equal(calls.length,3);
 await b.scan();assert.equal(calls.length,3);clock+=60001;await b.scan();assert.equal(calls.length,4);await b.scan();assert.equal(calls.length,4);}));
await test('thread hop limit stops further automatic messages before API dispatch',()=>fixture(async({ask,bridge,calls})=>{
 const b=bridge();await b.start();for(let n=0;n<9;n++)ask('--thread','loop-guard');await b.scan();assert.equal(calls.length,0);}));
await test('credential provider binds account and organization, checks scope/expiry and leaks no credential errors',()=>{
 const home=fs.mkdtempSync(path.join(os.tmpdir(),'cp-remote-auth-')),accountId=randomUUID(),orgId=randomUUID();fs.mkdirSync(path.join(home,'.claude'));
 const accountFile=path.join(home,'.claude.json'),creds=path.join(home,'.claude','.credentials.json');const account={oauthAccount:{accountUuid:accountId,organizationUuid:orgId}};
 const valid={claudeAiOauth:{accessToken:'fixture-access-value',expiresAt:Date.now()+60000,scopes:['user:sessions:claude_code']}};
 try{fs.writeFileSync(accountFile,JSON.stringify(account));fs.writeFileSync(creds,JSON.stringify(valid));const get=credentialProvider({home,accountId,orgId});assert.equal(get(),'fixture-access-value');
  fs.writeFileSync(creds,JSON.stringify({...valid,claudeAiOauth:{...valid.claudeAiOauth,expiresAt:0}}));assert.throws(get,{code:'DESKTOP_AUTH_EXPIRED'});
  fs.writeFileSync(creds,JSON.stringify({...valid,claudeAiOauth:{...valid.claudeAiOauth,scopes:[]}}));assert.throws(get,{code:'DESKTOP_AUTH_UNAVAILABLE'});
  fs.writeFileSync(accountFile,JSON.stringify({oauthAccount:{...account.oauthAccount,accountUuid:randomUUID()}}));assert.throws(get,{code:'DESKTOP_ACCOUNT_CHANGED'});
  fs.writeFileSync(accountFile,'private invalid JSON');assert.throws(get,e=>e.code==='DESKTOP_AUTH_UNAVAILABLE'&&!e.message.includes('private'));
 }finally{fs.rmSync(home,{recursive:true,force:true});}
});
console.log(`# ${count} tests, ${failed} failed`);if(failed)process.exitCode=1;
