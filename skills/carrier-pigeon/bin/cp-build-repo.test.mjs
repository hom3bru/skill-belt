// Disposable repositories only: no model, global Git setting, live mailbox or original checkout is changed.
import fs from 'node:fs';import path from 'node:path';import os from 'node:os';import assert from 'node:assert/strict';import {spawnSync} from 'node:child_process';
import * as build from './cp-build-repo.mjs';
const HOME=fs.realpathSync.native(fs.mkdtempSync(path.join(os.tmpdir(),'cp-build-repo-')));let fixtures=0,n=0,failed=0;
const t=async(name,fn)=>{n++;try{await fn();console.log('ok',n,name);}catch(e){failed++;console.log('not ok',n,name);console.log(String(e.stack||e).split('\n').slice(0,9).join('\n'));}};
const write=(root,rel,data)=>{const file=path.join(root,...rel.split('/'));fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,data);return file;};
const git=(cwd,...args)=>{const r=spawnSync('git',['-C',cwd,...args],{encoding:'utf8',windowsHide:true});if(r.status)throw new Error(r.stderr);return r.stdout.trim();};
async function fixture(extra={}){const root=path.join(HOME,String(++fixtures)),source=path.join(root,'source'),runDir=path.join(root,'run');fs.mkdirSync(source,{recursive:true});
  git(source,'init','-q','-b','main');git(source,'config','user.name','Build fixture');git(source,'config','user.email','fixture@example.invalid');git(source,'config','commit.gpgsign','false');git(source,'config','core.autocrlf','false');
  for(const [rel,data] of Object.entries({'src/a.mjs':'export const a = 1;\n','src/b.mjs':'export const b = 2;\n','README.md':'fixture\n','.gitignore':'ignored.tmp\n',...extra}))write(source,rel,data);
  git(source,'add','--all');git(source,'commit','-qm','baseline');return {root,source,runDir,sourceHead:git(source,'rev-parse','HEAD')};
}
const capture=async f=>{const snapshot=await build.snapshotRepo(f);return {...f,...snapshot};};
const work=(f,agent='codex')=>build.initWorktree({...f,agent});
const commit=(f,w,id,patterns=['src/**'])=>build.commitUnit({repo:f.repo,cwd:w.cwd,patterns,expectedHead:f.base,operationId:id,message:'fixture unit'});
const expectCode=(promise,code)=>assert.rejects(promise,e=>e.code===code);

await t('native canonical roots accept Windows short aliases and retain containment, subdirectory and link safeguards',async()=>{
  const f=await fixture();fs.mkdirSync(f.runDir);
  const alias=dir=>{
    if(process.platform!=='win32')return dir;
    // FSO queries the existing filesystem alias; never enable 8.3 names or change settings.
    const script="$ErrorActionPreference='Stop'; $f=New-Object -ComObject Scripting.FileSystemObject; $f.GetFolder($env:CP_SHORT_PATH_FIXTURE).ShortPath | ConvertTo-Json -Compress";
    const r=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-EncodedCommand',Buffer.from(script,'utf16le').toString('base64')],{encoding:'utf8',windowsHide:true,timeout:30000,env:{...process.env,CP_SHORT_PATH_FIXTURE:dir}});
    assert.equal(r.status,0,'querying the available filesystem alias succeeds');const short=JSON.parse(r.stdout.trim());
    assert.equal(fs.realpathSync.native(short),fs.realpathSync.native(dir));return short;
  };
  const source=alias(f.source),runDir=alias(f.runDir);
  const s=await build.snapshotRepo({source,runDir});assert.equal(s.source,fs.realpathSync.native(f.source));assert.equal(s.repo,path.join(fs.realpathSync.native(f.runDir),'repo'));
  assert.equal(fs.readFileSync(path.join(s.repo,'src/a.mjs'),'utf8'),'export const a = 1;\n','snapshot captures the nonempty source');
  assert.equal((await build.snapshotRepo({source:f.source,runDir:f.runDir})).base,s.base,'long and short paths resume the same snapshot');
  const w=await build.initWorktree({...s,runDir,agent:'codex'});
  assert.deepEqual(await build.initWorktree({...s,runDir,agent:'codex'}),w,'existing worktree uses the same canonical root');
  assert.equal(build.validateCheck({argv:['node','--test'],cwd:alias(w.cwd),root:runDir}).cwd,fs.realpathSync.native(w.cwd));
  await expectCode(build.snapshotRepo({source,runDir:path.join(source,'nested-run')}),'BAD_RUN_ROOT');
  await expectCode(build.snapshotRepo({source:path.join(source,'src'),runDir:path.join(f.root,'subdir-run')}),'BAD_ROOT');
  const linked=path.join(f.root,'linked-run');fs.symlinkSync(f.runDir,linked,process.platform==='win32'?'junction':'dir');
  await expectCode(build.snapshotRepo({source,runDir:linked}),'LINKED_PATH');
});

await t('a dirty and untracked source snapshot preserves the source index and excludes ignored and credential files',async()=>{
  const f=await fixture({'.env':'fixture configuration\n','AGENTS.md':'Fixture instructions.\n'});
  write(f.source,'src/a.mjs','staged\n');git(f.source,'add','--','src/a.mjs');write(f.source,'src/a.mjs','staged and unstaged\n');write(f.source,'new.mjs','untracked\n');write(f.source,'ignored.tmp','not copied\n');write(f.source,'.gitignore','ignored.tmp\nsrc/a.mjs\n');
  const index=git(f.source,'show',':src/a.mjs'),status=git(f.source,'status','--porcelain');const s=await build.snapshotRepo(f);
  assert.equal(fs.readFileSync(path.join(s.repo,'src/a.mjs'),'utf8'),'staged and unstaged\n');assert.equal(fs.readFileSync(path.join(s.repo,'new.mjs'),'utf8'),'untracked\n');
  assert.equal(fs.existsSync(path.join(s.repo,'ignored.tmp')),false);assert.equal(fs.existsSync(path.join(s.repo,'.env')),false);assert.ok(s.excluded.some(x=>x.path==='.env'));
  assert.ok(fs.existsSync(path.join(s.repo,'AGENTS.md')),'instructions are available for reading');assert.equal(git(s.repo,'show','HEAD:src/a.mjs'),'staged and unstaged');assert.equal(git(f.source,'status','--porcelain'),status);assert.equal(git(f.source,'show',':src/a.mjs'),index);assert.equal(git(f.source,'rev-parse','HEAD'),f.sourceHead);
  assert.equal((await build.snapshotRepo(f)).base,s.base,'resume reuses captured baseline');
});
await t('snapshots refuse linked tracked files and submodule entries without following their targets',async()=>{
  const f=await fixture(),outside=path.join(f.root,'outside');fs.mkdirSync(outside);write(outside,'secret.txt','outside fixture');
  const link=path.join(f.source,'linked');if(process.platform==='win32')fs.symlinkSync(outside,link,'junction');else fs.symlinkSync(outside,link);
  await expectCode(build.snapshotRepo(f),'LINKED_PATH');assert.equal(fs.readFileSync(path.join(outside,'secret.txt'),'utf8'),'outside fixture');
  const g=await fixture();git(g.source,'update-index','--add','--cacheinfo','160000,'+g.sourceHead+',module');await expectCode(build.snapshotRepo(g),'SUBMODULE_UNSUPPORTED');
});
await t('run and worktree roots cannot escape their isolated repository and repeated worktree setup is idempotent',async()=>{
  const f=await fixture();await expectCode(build.snapshotRepo({source:f.source,runDir:path.join(f.source,'nested')}),'BAD_RUN_ROOT');
  const s=await capture(f),a=await work(s);assert.deepEqual(await work(s),a);assert.ok(a.branch.startsWith('codex/'));assert.equal(git(a.cwd,'rev-parse','HEAD'),s.base);
  await expectCode(build.initWorktree({...s,agent:'user'}),'BAD_AGENT');
});
await t('ownership detects case-insensitive prefix overlap and protected/traversal paths',async()=>{
  assert.equal(build.validateOwnership([{agent:'codex',files:['src/a.mjs']},{agent:'claude',files:['src/b.mjs','test/**']}]),true);
  for(const units of [[{agent:'codex',files:['src/**']},{agent:'claude',files:['SRC/a.mjs']}],[{agent:'codex',files:['src/a.mjs']},{agent:'claude',files:['Src/A.mjs']}],[{agent:'codex',files:['src/**']},{agent:'codex',files:['src/a.mjs']}]])assert.throws(()=>build.validateOwnership(units),e=>e.code==='OWNERSHIP_OVERLAP');
  for(const file of ['../escape','/absolute','src/../a','src\\a','C:escape','AGENTS.md','src/CLAUDE.md','.git/config','.agents/**','.codex/**','.github/**','.env'])assert.throws(()=>build.validateOwnership([{agent:'codex',files:[file]}]),file);
  assert.equal(build.ownsPath(['src/**'],'src/a.mjs'),true);assert.equal(build.ownsPath(['src/**'],'src/.env'),false);assert.equal(build.ownsPath(['src/a.mjs'],'src/ab.mjs'),false);
});
await t('content fingerprints detect unstaged/untracked changes and remain stable when identical bytes are committed',async()=>{
  const f=await capture(await fixture()),w=await work(f),initial=await build.inspectWorktree(w);write(w.cwd,'src/a.mjs','changed\n');write(w.cwd,'src/new.mjs','new\n');
  const edited=await build.inspectWorktree(w);assert.notEqual(edited.fingerprint,initial.fingerprint);assert.equal(edited.changes.length,2);
  const result=await commit(f,w,'fingerprint');const after=await build.inspectWorktree(w);assert.equal(after.fingerprint,edited.fingerprint);assert.equal(after.head,result.commit);assert.equal(after.changes.length,0);
});
await t('unit checks reject unowned changes, protected instructions and unexpected HEAD movement',async()=>{
  const f=await capture(await fixture()),w=await work(f);write(w.cwd,'README.md','outside ownership\n');await expectCode(build.checkOwnership({...w,patterns:['src/**'],expectedHead:f.base}),'OWNERSHIP_VIOLATION');
  git(w.cwd,'add','--','README.md');git(w.cwd,'commit','-qm','unexpected worker commit');await expectCode(build.checkOwnership({...w,patterns:['src/**'],expectedHead:f.base}),'HEAD_CHANGED');
  await expectCode(build.checkOwnership({...w,patterns:['AGENTS.md'],expectedHead:git(w.cwd,'rev-parse','HEAD')}),'PROTECTED_PATH');
});
await t('commit broker disables configured hooks/signing and reuses a completed operation without extra commits',async()=>{
  const f=await capture(await fixture()),w=await work(f),hooks=path.join(f.root,'bad-hooks');fs.mkdirSync(hooks);fs.writeFileSync(path.join(hooks,'pre-commit'),'#!/bin/sh\nexit 73\n');fs.chmodSync(path.join(hooks,'pre-commit'),0o755);
  git(f.repo,'config','core.hooksPath',hooks);git(f.repo,'config','commit.gpgsign','true');git(f.repo,'config','gpg.program','missing-build-fixture-gpg');write(w.cwd,'src/a.mjs','broker change\n');
  const first=await commit(f,w,'hooks');assert.equal(git(w.cwd,'rev-list','--count',f.base+'..HEAD'),'1');const again=await commit(f,w,'hooks');assert.deepEqual(again,first);assert.equal(git(w.cwd,'rev-list','--count',f.base+'..HEAD'),'1');
  await expectCode(build.commitUnit({repo:f.repo,cwd:w.cwd,patterns:['src/**'],expectedHead:f.base,operationId:'hooks',message:'different operation'}),'OPERATION_CONFLICT');
});
await t('commit recovery recognizes Git success before its durable completion record',async()=>{
  const f=await capture(await fixture()),w=await work(f);write(w.cwd,'src/a.mjs','recover commit\n');const original=fs.renameSync;let injected=false;
  try{fs.renameSync=(from,to)=>{if(String(to).endsWith(path.join('commit-gap','operation.json'))&&JSON.parse(fs.readFileSync(from,'utf8')).state==='committed'&&!injected){injected=true;throw new Error('injected committed journal failure');}return original(from,to);};await assert.rejects(commit(f,w,'commit-gap'),/injected/);}finally{fs.renameSync=original;}
  assert.equal(injected,true);const head=git(w.cwd,'rev-parse','HEAD'),recovered=await commit(f,w,'commit-gap');assert.equal(recovered.commit,head);assert.equal(git(w.cwd,'rev-list','--count',f.base+'..HEAD'),'1');
});
await t('dependency and integration merges are sequential, repeatable and include both authored branches',async()=>{
  const f=await capture(await fixture()),a=await work(f,'codex'),b=await work(f,'claude');write(a.cwd,'src/a.mjs','codex\n');const ca=await commit(f,a,'merge-a');
  const dep=await build.syncDependencies({repo:f.repo,cwd:b.cwd,commits:[ca.commit]});assert.equal(dep,ca.commit);assert.equal(await build.syncDependencies({repo:f.repo,cwd:b.cwd,commits:[ca.commit]}),dep);
  write(b.cwd,'src/b.mjs','claude\n');const cb=await build.commitUnit({repo:f.repo,cwd:b.cwd,patterns:['src/b.mjs'],expectedHead:dep,operationId:'merge-b',message:'claude fixture'});
  const merged=await build.mergeUnits({repo:f.repo,commits:[ca.commit,cb.commit],operationId:'integration'});assert.equal(git(f.repo,'merge-base','--is-ancestor',ca.commit,merged.commit),'');assert.equal(git(f.repo,'merge-base','--is-ancestor',cb.commit,merged.commit),'');assert.deepEqual(await build.mergeUnits({repo:f.repo,commits:[ca.commit,cb.commit],operationId:'integration'}),merged);
});
await t('an integration interrupted after a successful merge resumes without duplicating that merge',async()=>{
  const f=await capture(await fixture()),a=await work(f,'codex'),b=await work(f,'claude');write(a.cwd,'src/a.mjs','left\n');write(b.cwd,'src/b.mjs','right\n');const ca=await commit(f,a,'left'),cb=await commit(f,b,'right');
  const original=fs.renameSync;let injected=false;try{fs.renameSync=(from,to)=>{const body=String(to).endsWith(path.join('merge-gap','operation.json'))?JSON.parse(fs.readFileSync(from,'utf8')):null;if(body?.next===1&&!injected){injected=true;throw new Error('injected merge checkpoint failure');}return original(from,to);};await assert.rejects(build.mergeUnits({repo:f.repo,commits:[ca.commit,cb.commit],operationId:'merge-gap'}),/injected/);}finally{fs.renameSync=original;}
  const merged=await build.mergeUnits({repo:f.repo,commits:[ca.commit,cb.commit],operationId:'merge-gap'});assert.ok(merged.files.includes('src/a.mjs')&&merged.files.includes('src/b.mjs'));assert.deepEqual(await build.mergeUnits({repo:f.repo,commits:[ca.commit,cb.commit],operationId:'merge-gap'}),merged);
});
await t('check policy rejects shell/eval/install escapes and accepts explicit test/setup argv',async()=>{
  const f=await capture(await fixture());for(const argv of [['powershell','-Command','whoami'],['node','--eval=1'],['node','-p','1'],['python','-cprint(1)'],['npm','install','a'],['npm','run','deploy'],['npm','run','test','--prefix','../source'],['python','-m','pip','install','x'],['node','../../outside.mjs']])assert.throws(()=>build.validateCheck({argv,cwd:f.repo,root:f.runDir}),JSON.stringify(argv));
  assert.deepEqual(build.validateCheck({argv:['node','--test'],cwd:f.repo}).argv,['node','--test']);assert.deepEqual(build.validateCheck({argv:['python','-B','-m','unittest'],cwd:f.repo}).argv,['python','-B','-m','unittest']);
  assert.throws(()=>build.validateCheck({argv:['npm','ci'],cwd:f.repo}),/setup authority/);assert.ok(build.validateCheck({argv:['npm','ci','--ignore-scripts'],cwd:f.repo,allowSetup:true}));
});
await t('checks record real exits and content fingerprints, reject stale receipts and do not evaluate shell metacharacters',async()=>{
  const f=await capture(await fixture({'pass.mjs':"console.log('pass fixture');\n",'fail.mjs':"process.stderr.write('failure fixture');process.exit(7);\n"}));const scratch=path.join(f.runDir,'scratch'),receiptDir=path.join(f.runDir,'checks');
  const passing=await build.runCheck({argv:[process.execPath,'pass.mjs','& not a shell command'],cwd:f.repo,root:f.runDir,scratch,receiptDir,id:'passing'});assert.equal(passing.exit,0);assert.equal(passing.passed,true);assert.match(fs.readFileSync(passing.stdout_path,'utf8'),/pass fixture/);assert.equal(passing.before_fingerprint,passing.fingerprint);assert.deepEqual(await build.runCheck({argv:[process.execPath,'pass.mjs','& not a shell command'],cwd:f.repo,root:f.runDir,scratch,receiptDir,id:'passing'}),passing);
  const failing=await build.runCheck({argv:[process.execPath,'fail.mjs'],cwd:f.repo,root:f.runDir,scratch,receiptDir,id:'failure'});assert.equal(failing.exit,7);assert.equal(failing.passed,false);assert.match(fs.readFileSync(failing.stderr_path,'utf8'),/failure fixture/);
  write(receiptDir,'interrupted.stdout.log','partial log');await expectCode(build.runCheck({argv:[process.execPath,'pass.mjs'],cwd:f.repo,root:f.runDir,scratch,receiptDir,id:'interrupted'}),'RECOVERY_NEEDED');assert.equal(fs.readFileSync(path.join(receiptDir,'interrupted.stdout.log'),'utf8'),'partial log');
  await expectCode(build.runCheck({argv:[process.execPath,'fail.mjs'],cwd:f.repo,root:f.runDir,scratch,receiptDir,id:'passing'}),'CHECK_CONFLICT');write(f.repo,'src/a.mjs','new bytes\n');await expectCode(build.runCheck({argv:[process.execPath,'pass.mjs','& not a shell command'],cwd:f.repo,root:f.runDir,scratch,receiptDir,id:'passing'}),'STALE_CHECK');
});
await t('check timeout and cancellation stop the spawned process and retain truthful receipts',async()=>{
  const f=await capture(await fixture({'wait.mjs':'setTimeout(()=>{},30000);\n'})),common={argv:[process.execPath,'wait.mjs'],cwd:f.repo,scratch:path.join(f.runDir,'scratch'),receiptDir:path.join(f.runDir,'checks')};
  const timed=await build.runCheck({...common,id:'timeout',timeoutMs:200});assert.equal(timed.passed,false);assert.equal(timed.timed_out,true);
  const controller=new AbortController();setTimeout(()=>controller.abort(),150);const cancelled=await build.runCheck({...common,id:'cancel',signal:controller.signal});assert.equal(cancelled.passed,false);assert.equal(cancelled.aborted,true);
});
await t('sandboxed checks retain declared argv, receive scratch and fail closed without an unsandboxed retry',async()=>{
  const stub="const {spawnSync}=require('node:child_process');const fs=require('node:fs');const path=require('node:path');const args=process.argv.slice(2);fs.writeFileSync(path.join(process.env.TEMP,'sandbox-seen'),JSON.stringify(args));if(fs.existsSync(path.join(process.env.TEMP,'deny')))process.exit(41);const at=args.indexOf('--');const r=spawnSync(args[at+1],args.slice(at+2),{stdio:'inherit'});process.exit(r.status||0);\n";
  const f=await capture(await fixture({'sandbox':stub,'pass.mjs':"requireMarker(); function requireMarker(){ console.log('sandbox child'); }\n"})),scratch=path.join(f.runDir,'scratch'),common={argv:[process.execPath,'pass.mjs'],cwd:f.repo,scratch,receiptDir:path.join(f.runDir,'checks'),sandbox:{bin:process.execPath}};
  const first=await build.runCheck({...common,id:'sandbox-ok'});assert.equal(first.passed,true);assert.equal(first.sandboxed,true);assert.deepEqual(first.argv,common.argv);assert.deepEqual(JSON.parse(fs.readFileSync(path.join(scratch,'sandbox-seen'),'utf8')).slice(0,4),['-P',':workspace','-C',f.repo]);
  write(scratch,'deny','denied');const denied=await build.runCheck({...common,id:'sandbox-denied'});assert.equal(denied.exit,41);assert.equal(denied.passed,false);assert.equal(fs.readFileSync(denied.stdout_path,'utf8'),'');
});
await t('publication preserves initial dirty content, unrelated concurrent edits, line endings and original Git index',async()=>{
  const f=await fixture({'src/a.mjs':'base\r\n'});write(f.source,'src/a.mjs','staged\r\n');git(f.source,'add','--','src/a.mjs');write(f.source,'src/a.mjs','staged plus unstaged\r\n');const staged=git(f.source,'show',':src/a.mjs');
  Object.assign(f,await build.snapshotRepo(f));const w=await work(f);write(w.cwd,'src/a.mjs','staged plus unstaged\nfeature\n');write(w.cwd,'src/b.mjs','second feature\n');const unit=await commit(f,w,'publish-unit'),merged=await build.mergeUnits({repo:f.repo,commits:[unit.commit],operationId:'publish-merge'});write(f.source,'README.md','unrelated concurrent user edit\n');
  const result=await build.publishResult({...f,commit:merged.commit,operationId:'publish'});assert.deepEqual(result.applied,['src/a.mjs','src/b.mjs']);assert.equal(fs.readFileSync(path.join(f.source,'src/a.mjs'),'utf8'),'staged plus unstaged\r\nfeature\r\n');assert.equal(fs.readFileSync(path.join(f.source,'README.md'),'utf8'),'unrelated concurrent user edit\n');assert.equal(git(f.source,'show',':src/a.mjs'),staged);assert.equal(git(f.source,'rev-parse','HEAD'),f.sourceHead);assert.equal(fs.readFileSync(path.join(result.backup,'src/a.mjs'),'utf8'),'staged plus unstaged\r\n');assert.ok(fs.existsSync(result.patch));assert.deepEqual(await build.publishResult({...f,commit:merged.commit,operationId:'publish'}),result);
});
await t('publication refuses unknown concurrent bytes before applying any candidate file',async()=>{
  const f=await capture(await fixture()),w=await work(f);write(w.cwd,'src/a.mjs','candidate a\n');write(w.cwd,'src/b.mjs','candidate b\n');const unit=await commit(f,w,'conflict-unit'),merged=await build.mergeUnits({repo:f.repo,commits:[unit.commit],operationId:'conflict-merge'});write(f.source,'src/b.mjs','concurrent user edit\n');
  await expectCode(build.publishResult({...f,commit:merged.commit,operationId:'conflict-publish'}),'SOURCE_CHANGED');assert.equal(fs.readFileSync(path.join(f.source,'src/a.mjs'),'utf8'),'export const a = 1;\n');assert.equal(fs.readFileSync(path.join(f.source,'src/b.mjs'),'utf8'),'concurrent user edit\n');
});
await t('a publication interrupted after a target write resumes from old-or-intended bytes without rewriting completed files',async()=>{
  const f=await capture(await fixture()),w=await work(f);write(w.cwd,'src/a.mjs','first published\n');write(w.cwd,'src/b.mjs','second published\n');const unit=await commit(f,w,'gap-unit'),merged=await build.mergeUnits({repo:f.repo,commits:[unit.commit],operationId:'gap-merge'});
  const original=fs.renameSync;let injected=false;try{fs.renameSync=(from,to)=>{const body=String(to).endsWith(path.join('publish-gap','operation.json'))?JSON.parse(fs.readFileSync(from,'utf8')):null;if(body?.state==='prepared'&&body.files.some(x=>x.applied)&&!injected){injected=true;throw new Error('injected post-write publication failure');}return original(from,to);};await assert.rejects(build.publishResult({...f,commit:merged.commit,operationId:'publish-gap'}),/injected/);}finally{fs.renameSync=original;}
  assert.equal(fs.readFileSync(path.join(f.source,'src/a.mjs'),'utf8'),'first published\n');const stamp=fs.statSync(path.join(f.source,'src/a.mjs')).mtimeMs;const result=await build.publishResult({...f,commit:merged.commit,operationId:'publish-gap'});assert.equal(fs.statSync(path.join(f.source,'src/a.mjs')).mtimeMs,stamp);assert.equal(fs.readFileSync(path.join(f.source,'src/b.mjs'),'utf8'),'second published\n');assert.equal(result.applied.length,2);
});
await t('publication handles UTF-8 filenames, binary bytes and checked individual file deletions',async()=>{
  const f=await capture(await fixture({'src/café.mjs':'old unicode\n','src/raw.bin':Buffer.from([0xff,13,10])})),w=await work(f);write(w.cwd,'src/café.mjs','updated unicode\n');write(w.cwd,'src/raw.bin',Buffer.from([0xfe,10]));fs.unlinkSync(path.join(w.cwd,'src/b.mjs'));write(f.source,'unrelated.tmp','preserve untracked source\n');
  const unit=await commit(f,w,'unicode-unit'),merged=await build.mergeUnits({repo:f.repo,commits:[unit.commit],operationId:'unicode-merge'});assert.deepEqual(merged.files,['src/b.mjs','src/café.mjs','src/raw.bin']);const result=await build.publishResult({...f,commit:merged.commit,operationId:'unicode-publish'});
  assert.deepEqual(result.applied,['src/b.mjs','src/café.mjs','src/raw.bin']);assert.equal(fs.existsSync(path.join(f.source,'src/b.mjs')),false);assert.equal(fs.readFileSync(path.join(f.source,'src/café.mjs'),'utf8'),'updated unicode\n');assert.deepEqual(fs.readFileSync(path.join(f.source,'src/raw.bin')),Buffer.from([0xfe,10]));assert.equal(fs.readFileSync(path.join(f.source,'unrelated.tmp'),'utf8'),'preserve untracked source\n');assert.equal(fs.readFileSync(path.join(result.backup,'src/b.mjs'),'utf8'),'export const b = 2;\n');
});

await t('repository checks inherit neither operator build authority nor token environment values',async()=>{
 const f=await capture(await fixture({'env.mjs':"console.log(JSON.stringify({worker:process.env.CARRIER_PIGEON_WORKER,mailbox:process.env.CARRIER_PIGEON_HOME,token:process.env.CP_FIXTURE_TOKEN,cache:process.env.NPM_CONFIG_CACHE}));\n"})),scratch=path.join(f.runDir,'scratch');
 const old=process.env.CP_FIXTURE_TOKEN;process.env.CP_FIXTURE_TOKEN='dummy-test-value';let result;
 try{result=await build.runCheck({argv:[process.execPath,'env.mjs'],cwd:f.repo,scratch,receiptDir:path.join(f.runDir,'checks'),id:'env'});}finally{if(old===undefined)delete process.env.CP_FIXTURE_TOKEN;else process.env.CP_FIXTURE_TOKEN=old;}
 assert.equal(result.passed,true);const env=JSON.parse(fs.readFileSync(result.stdout_path,'utf8'));assert.equal(env.worker,'1');assert.equal(env.mailbox,path.join(scratch,'check-mailbox'));assert.equal(env.cache,path.join(scratch,'npm-cache'));assert.equal(env.token,undefined);
});
// Every fixture was created under this resolved temporary root; never remove a computed external target.
assert.equal(path.dirname(fs.realpathSync.native(HOME)),fs.realpathSync.native(os.tmpdir()));fs.rmSync(HOME,{recursive:true,force:true});
console.log(`# ${n} tests, ${failed} failed (build-repo)`);process.exit(failed?1:0);
