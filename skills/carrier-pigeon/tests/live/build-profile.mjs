// Opt-in real Claude qualification: normal authentication with a job-private hook override and worker MCP.
// node tests/live/build-profile.mjs [--operator MAILBOX] [--out PRIVATE_REPORT.json]
// One configured Claude session. Temporary repository, native logs and job evidence are retained privately.
import fs from'node:fs';import path from'node:path';import os from'node:os';import crypto from'node:crypto';import assert from'node:assert/strict';
import{spawnSync}from'node:child_process';import{fileURLToPath}from'node:url';import{startJob,waitJob,readJob,cancelJob,loadJobDescriptor,buildNativeArgs}from'../../bin/cp-build-runtime.mjs';
const SKILL=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..','..');
const arg=(name,fallback)=>{const i=process.argv.indexOf('--'+name);if(i<0)return fallback;if(!process.argv[i+1]||process.argv[i+1].startsWith('--'))throw new Error('--'+name+' requires a value');return process.argv[i+1];};
const operatorRoot=fs.realpathSync(path.resolve(arg('operator',path.join(os.homedir(),'.carrier-pigeon')))),out=path.resolve(arg('out',path.join(os.tmpdir(),'cp-build-profile-qualification.json')));
assert.ok(fs.statSync(path.join(operatorRoot,'host','config.json')).isFile(),'Existing operator host configuration is required; this script never configures credentials.');
const runDir=fs.mkdtempSync(path.join(os.tmpdir(),'cp-build-profile-')),cwd=path.join(runDir,'repo'),mailbox=path.join(runDir,'mailbox'),jobDir=path.join(runDir,'jobs','job-profile');
for(const dir of[cwd,mailbox,path.join(runDir,'empty-hooks')])fs.mkdirSync(dir,{recursive:true});
const marker='profile-'+crypto.randomBytes(16).toString('hex'),readme='# Build profile qualification\n\nqualification_marker: '+marker+'\n\nRead-only fixture for the normal authenticated native build profile.\n';
const git=(...args)=>{const r=spawnSync('git',['-c','core.hooksPath='+path.join(runDir,'empty-hooks'),'-c','commit.gpgsign=false','-C',cwd,...args],{encoding:'utf8',windowsHide:true});assert.equal(r.status,0,r.stderr);return r.stdout.trim();};
git('init','-q','-b','main');git('config','user.name','Carrier Pigeon qualification');git('config','user.email','qualification@example.invalid');git('config','core.autocrlf','false');
fs.writeFileSync(path.join(cwd,'README.md'),readme);git('add','--','README.md');git('commit','-qm','Read-only profile qualification');const head=git('rev-parse','HEAD');
const init=spawnSync(process.execPath,[path.join(SKILL,'bin','carrier-pigeon.mjs'),'init','--json'],{cwd:runDir,env:{...process.env,CARRIER_PIGEON_HOME:mailbox},encoding:'utf8',windowsHide:true});assert.equal(init.status,0,init.stderr);assert.equal(JSON.parse(init.stdout).root,mailbox);
const options={jobDir,agent:'claude',role:'profile-qualification',cwd,mailbox,operatorRoot,readOnly:true,timeoutMs:300000,checks:[],
 schema:{type:'object',properties:{marker:{type:'string'},summary:{type:'string'}},required:['marker','summary'],additionalProperties:false},
 context:{runDir,task:'Read-only qualification of the authenticated automatic build profile.',file:'README.md',ownership:'Read only. No file edits, repository commands, other agents or workflow mutations.'},
 prompt:'Call the dedicated build_context tool to read your fixed grant. Then use the native Read tool to read README.md in the working directory. Return the exact literal value after qualification_marker: as marker, plus a concise summary of what you observed. Do not infer or invent the value. This is read-only: do not edit files, execute repository commands, or call other agents. Return only the required structured JSON object.'};
assert.equal(options.prompt.includes(marker),false);assert.equal(JSON.stringify(options.context).includes(marker),false);
const started=new Date().toISOString(),proof={format:'carrier-pigeon-build-profile-qualification-1',passed:false,started,run_dir:runDir,job_dir:jobDir,operator_root:operatorRoot,head,expected_marker:marker};let outcome;
try{
 await startJob(options);let last='';outcome=await waitJob(jobDir,{onUpdate:state=>{if(state.status!==last){last=state.status;console.log(JSON.stringify({event:'profile-job',status:state.status}));}}});
 proof.status=outcome.status;proof.execution_stopped=outcome.execution_stopped;proof.job_hash=outcome.job_hash;proof.paths=outcome.paths;proof.result=outcome.result;
 assert.equal(outcome.status,'completed',outcome.reason||outcome.error?.message);assert.equal(outcome.execution_stopped,true);assert.equal(outcome.result.marker,marker);assert.ok(outcome.result.summary.trim());
 const spec=await buildNativeArgs(loadJobDescriptor(jobDir)),settingsFile=spec.args[spec.args.indexOf('--settings')+1],settings=JSON.parse(fs.readFileSync(settingsFile,'utf8'));
 assert.equal(settings.disableAllHooks,true);assert.ok(settingsFile.startsWith(jobDir+path.sep));assert.equal(spec.args.includes('--bare'),false);assert.equal(spec.args.includes('--restricted'),false);assert.equal(spec.args.includes('--setting-sources'),false);
 const events=fs.readFileSync(outcome.paths.stdout,'utf8').split('\n').flatMap(line=>{try{return[JSON.parse(line)];}catch{return[];}}),calls=events.filter(e=>e.type==='assistant').flatMap(e=>(e.message?.content||[]).filter(b=>b.type==='tool_use').map(b=>b.name));
 assert.ok(calls.some(name=>/build_context$/.test(name)),'The real Claude must call its dedicated worker context tool.');assert.ok(calls.includes('Read'),'The real Claude must read the marker using its native file tool.');
 assert.equal(git('rev-parse','HEAD'),head);assert.equal(git('status','--porcelain'),'');assert.equal(fs.readFileSync(path.join(cwd,'README.md'),'utf8'),readme);
 proof.native_tool_calls=calls;proof.hook_override={file:settingsFile,disableAllHooks:settings.disableAllHooks};proof.normal_profile_launch=true;proof.repository_unchanged=true;proof.passed=true;
}catch(error){proof.error={code:error.code||'PROFILE_QUALIFICATION_FAILED',message:String(error.message||error)};try{const state=readJob(jobDir);if(!['completed','failed','cancelled'].includes(state.status))await cancelJob(jobDir,'Profile qualification failed; stop the native job.');proof.final_job=readJob(jobDir);}catch{}process.exitCode=1;
}finally{proof.finished=new Date().toISOString();fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(proof,null,2)+'\n');console.log(JSON.stringify({passed:proof.passed,status:outcome?.status||null,report:out}));}
