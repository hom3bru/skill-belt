// Controller recovery regressions: disposable real Git repositories and real local Node checks.
// Native providers are deterministic fixtures; no live provider, global Git config or original checkout is used.
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import assert from 'node:assert/strict';
import * as build from './cp-build.mjs';import * as repo from './cp-build-repo.mjs';
// Simulate the operator only inside this disposable fake-provider fixture process.
delete process.env.CARRIER_PIGEON_WORKER;
const TEST_ROOT=fs.mkdtempSync(path.join(os.tmpdir(),'cp-build-recovery-'));let sequence=0,count=0,failed=0;
const write=(root,file,data)=>{const target=path.join(root,file);fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,data);};
const read=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
// Optional literal name fragment selects one regression while iterating; the registered default runs every case.
const selected=process.argv[2];
const test=async(name,run)=>{if(selected&&!name.includes(selected))return;count++;try{await run();console.log('ok',count,name);}catch(error){failed++;console.log('not ok',count,name);console.log(String(error.stack||error));}};
function gate(){let resolve;const promise=new Promise(done=>{resolve=done;});return {promise,resolve};}
async function until(predicate,{timeout=10000,message='fixture condition was not reached'}={}){const end=Date.now()+timeout;for(;;){const value=predicate();if(value)return value;if(Date.now()>=end)throw Error(message);await pause(25);}}
async function fixture(integration='normal'){
 const root=path.join(TEST_ROOT,String(++sequence)),source=path.join(root,'source'),operatorRoot=path.join(root,'operator');fs.mkdirSync(source,{recursive:true});
 write(operatorRoot,'host/config.json',JSON.stringify({codex:{bin:'codex'},claude:{bin:'claude'}}));
 repo.git(source,'init','-q','-b','main');repo.git(source,'config','user.name','Build recovery fixture');repo.git(source,'config','user.email','build-recovery@example.invalid');repo.git(source,'config','commit.gpgsign','false');repo.git(source,'config','core.autocrlf','false');
 write(source,'src/a.mjs','export const a=1;\n');write(source,'src/b.mjs','export const b=1;\n');
 write(source,'unit.mjs',"import {a}from'./src/a.mjs';import {b}from'./src/b.mjs';if(a<=0||b<=0)throw Error('positive units required');\n");
 const arithmetic="import {a}from'./src/a.mjs';import {b}from'./src/b.mjs';if(a+b!==5)throw Error('expected a=2,b=3');\n";
 const scripts={normal:arithmetic,mutate:arithmetic+"import fs from'node:fs';fs.writeFileSync('src/a.mjs','export const a=99;\\n');console.log('mutated tracked implementation');\n",long:arithmetic+"import fs from'node:fs';import path from'node:path';fs.writeFileSync(path.join(process.env.TEMP,'integration.pid'),String(process.pid));setTimeout(()=>{fs.writeFileSync(path.join(process.env.TEMP,'integration-finished'),'unexpected completion');},30000);\n"};
 write(source,'integration.mjs',scripts[integration]);repo.git(source,'add','--all');repo.git(source,'commit','-qm','baseline');
 return {source,operatorRoot,repo:source,task:'Implement a=2 and b=3 in separate units, cross-review and verify their sum is 5',checks:[['node','integration.mjs']],background:false,head:repo.git(source,'rev-parse','HEAD'),index:repo.git(source,'show',':src/a.mjs')};
}
function unchanged(f){assert.equal(repo.git(f.source,'rev-parse','HEAD'),f.head);assert.equal(repo.git(f.source,'show',':src/a.mjs'),f.index);assert.equal(repo.git(f.source,'status','--porcelain'),'');assert.equal(fs.readFileSync(path.join(f.source,'src/a.mjs'),'utf8'),'export const a=1;\n');assert.equal(fs.readFileSync(path.join(f.source,'src/b.mjs'),'utf8'),'export const b=1;\n');}
function provider({blockFirstAuthor=false,onWait}={}){
 const jobs=new Map(),calls=[];let blocked=false;
 const runtime={async startJob(options){jobs.set(options.jobDir,options);calls.push(options);return {};},async waitJob(dir){
  const options=jobs.get(dir),resultFile=path.join(dir,'fixture-result.json');fs.mkdirSync(dir,{recursive:true});if(fs.existsSync(resultFile))return read(resultFile);await onWait?.(options);
  let result,skipChecks=false;
  if(options.role==='plan')result={title:'Recovery fixture',contract:'a=2 and b=3; integrated sum=5',units:['codex','claude'].map((agent,index)=>({agent,summary:'Implement '+(index?'b':'a'),files:['src/'+(index?'b':'a')+'.mjs'],depends_on:[],checks:[{argv:['node','unit.mjs'],cwd:'.'}]})),integration_checks:[{argv:['node','integration.mjs'],cwd:'.'}],questions:[]};
  else if(options.role==='plan-review')result={verdict:'approve',summary:'Two disjoint units with existing checks',issues:[]};
  else if(options.role==='build'){
   if(blockFirstAuthor&&options.agent==='codex'&&!blocked){blocked=true;skipChecks=true;result={summary:'Waiting for acceptance clarification',blocked:true,questions:['Confirm the requested value of a'],notes:[]};}
   else{const isA=options.agent==='codex';write(options.cwd,isA?'src/a.mjs':'src/b.mjs',isA?'export const a=2;\n':'export const b=3;\n');result={summary:'Implemented assigned arithmetic unit',blocked:false,questions:[],notes:[]};}
  }else if(options.role==='cross-review')result={summary:'Independently reviewed assigned peer unit',findings:[],notes:[]};
  else throw Error('Unexpected provider role: '+options.role);
  const checks=[];if(!skipChecks)for(const check of options.checks)checks.push(await repo.runCheck({...check,sandbox:null,scratch:path.join(dir,'scratch'),receiptDir:path.join(dir,'check-results'),id:check.id}));
  const output={status:'completed',result,checks,job_hash:'fixture-'+path.basename(dir),execution_stopped:true,paths:{}};fs.writeFileSync(resultFile,JSON.stringify(output));return output;
 },async cancelJob(){return {status:'cancelled',execution_stopped:true};}};
 return {runtime,calls,runCheck:options=>repo.runCheck({...options,sandbox:null})};
}

await test('completed blocked author resumes as a new native job with user feedback and preserves the old result',async()=>{
 const f=await fixture(),adapter=provider({blockFirstAuthor:true}),started=await build.startBuild(f),handle={operatorRoot:f.operatorRoot,id:started.id};
 const blocked=await build.runBuild(handle,adapter);assert.equal(blocked.status,'needs_input',JSON.stringify(blocked));unchanged(f);
 const oldCall=adapter.calls.find(call=>call.role==='build'&&call.agent==='codex'),oldResult=read(path.join(oldCall.jobDir,'fixture-result.json'));
 assert.equal(oldResult.status,'completed');assert.equal(oldResult.result.blocked,true);const oldBytes=fs.readFileSync(path.join(oldCall.jobDir,'fixture-result.json'));
 const oldState=read(path.join(blocked.run_dir,'state.json')),oldRecord=Object.values(oldState.jobs).find(job=>job.dir===oldCall.jobDir);assert.equal(oldRecord.needs_input,true);
 const feedback='Use the already requested value a=2; proceed within the original files.';build.resumeBuild({...handle,feedback,background:false});const completed=await build.runBuild(handle,adapter);
 assert.equal(completed.status,'completed',JSON.stringify(completed));const authors=adapter.calls.filter(call=>call.role==='build'&&call.agent==='codex');assert.equal(authors.length,2);assert.notEqual(authors[1].jobDir,oldCall.jobDir);assert.ok(JSON.stringify(authors[1].context).includes(feedback),'new native job must receive the resume clarification');assert.match(authors[1].prompt,/already requested value a=2/);
 assert.deepEqual(fs.readFileSync(path.join(oldCall.jobDir,'fixture-result.json')),oldBytes);assert.equal(repo.git(f.source,'rev-parse','HEAD'),f.head);assert.equal(repo.git(f.source,'show',':src/a.mjs'),f.index);assert.equal(fs.readFileSync(path.join(f.source,'src/a.mjs'),'utf8'),'export const a=2;\n');assert.equal(fs.readFileSync(path.join(f.source,'src/b.mjs'),'utf8'),'export const b=3;\n');
});

await test('concurrent controllers in the same process reject BUILD_BUSY without launching duplicate work',async()=>{
 const f=await fixture(),entered=gate(),release=gate(),adapter=provider({onWait:async options=>{if(options.role==='plan'){entered.resolve();await release.promise;}}}),started=await build.startBuild(f),handle={operatorRoot:f.operatorRoot,id:started.id};
 const first=build.runBuild(handle,adapter);try{await Promise.race([entered.promise,pause(10000).then(()=>{throw Error('planning fixture did not start');})]);await assert.rejects(build.runBuild(handle,adapter),error=>error.code==='BUILD_BUSY');assert.equal(adapter.calls.length,1);assert.equal(build.statusBuild(handle).controller_alive,true);}
 finally{build.cancelBuild({...handle,reason:'End concurrent controller fixture'});release.resolve();}
 const result=await first;assert.equal(result.status,'cancelled',JSON.stringify(result));assert.equal(adapter.calls.length,1);unchanged(f);
});

await test('a passing integration command that mutates tracked implementation is rejected before publication',async()=>{
 const f=await fixture('mutate'),adapter=provider(),receipts=[];adapter.runCheck=async options=>{const receipt=await repo.runCheck({...options,sandbox:null});receipts.push(receipt);return receipt;};
 const started=await build.startBuild(f),result=await build.runBuild({operatorRoot:f.operatorRoot,id:started.id},adapter);assert.equal(result.status,'needs_input',JSON.stringify(result));assert.equal(result.error.code,'OWNERSHIP_VIOLATION');assert.match(result.error.message,/Integration check changed the code/);assert.ok(result.integration);assert.deepEqual(result.applied,[]);unchanged(f);
 assert.equal(receipts.length,1);assert.equal(receipts[0].passed,true);assert.notEqual(receipts[0].before_fingerprint,receipts[0].fingerprint);assert.equal(fs.readFileSync(path.join(result.run_dir,'repo','src/a.mjs'),'utf8'),'export const a=99;\n');assert.equal(repo.git(path.join(result.run_dir,'repo'),'show',result.integration+':src/a.mjs'),'export const a=2;');assert.equal(read(path.join(result.run_dir,'state.json')).publication,undefined);
});

await test('cancellation during a real integration command aborts its runner and preserves the original source',async()=>{
 const f=await fixture('long'),adapter=provider(),started=await build.startBuild(f),handle={operatorRoot:f.operatorRoot,id:started.id};let receipt,signal,pid,requested;
 adapter.runCheck=async options=>{signal=options.signal;const running=repo.runCheck({...options,sandbox:null,timeoutMs:7000});const marker=path.join(options.scratch,'integration.pid');await until(()=>fs.existsSync(marker),{timeout:4000,message:'integration process did not start'});pid=Number(fs.readFileSync(marker,'utf8'));assert.ok(Number.isInteger(pid)&&pid>0);assert.equal(build.statusBuild(handle).phase,'integration');requested=Date.now();const cancelled=build.cancelBuild({...handle,reason:'Cancel running integration fixture'});assert.equal(cancelled.cancel_requested,true);receipt=await running;return receipt;};
 const result=await build.runBuild(handle,adapter);assert.equal(result.status,'cancelled',JSON.stringify(result));assert.ok(signal instanceof AbortSignal,'integration checks must receive the controller cancellation signal');assert.equal(signal.aborted,true);assert.equal(receipt.aborted,true);assert.equal(receipt.timed_out,false);assert.equal(receipt.passed,false);assert.ok(Date.now()-requested<6500,'cancellation must stop the command before its timeout');let alive=true;try{process.kill(pid,0);}catch(error){if(error.code==='ESRCH')alive=false;else throw error;}assert.equal(alive,false,'integration process must have exited');assert.equal(fs.existsSync(path.join(result.run_dir,'scratch','integration-finished')),false);assert.deepEqual(result.applied,[]);unchanged(f);
});

await test('cancellation never acknowledges an unconfirmed native shutdown',async()=>{
 const f=await fixture(),started=await build.startBuild(f),handle={operatorRoot:f.operatorRoot,id:started.id};
 const runtime={async startJob(){},async waitJob(){build.cancelBuild({...handle,reason:'Cancel uncertain native fixture'});return {status:'recovery_needed',reason:'simulated stop uncertainty',execution_stopped:false,result:null,checks:[],paths:{}};}};
 const result=await build.runBuild(handle,{runtime});assert.equal(result.status,'needs_input');assert.equal(result.error.code,'RECOVERY_NEEDED');assert.match(result.error.message,/shutdown could not be confirmed/);unchanged(f);
});

// Resolve and verify the explicit disposable root before recursive cleanup.
const resolved=fs.realpathSync(TEST_ROOT);assert.equal(path.dirname(resolved),fs.realpathSync(os.tmpdir()));fs.rmSync(resolved,{recursive:true,force:true,maxRetries:3,retryDelay:100});
console.log(`# ${count} tests, ${failed} failed (build-recovery)`);if(failed)process.exitCode=1;
