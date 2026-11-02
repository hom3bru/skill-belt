// Local repository operations for the automatic co-build controller. No remote Git operation or shell evaluation.
import fs from 'node:fs'; import path from 'node:path'; import os from 'node:os'; import crypto from 'node:crypto';
import {spawn,spawnSync} from 'node:child_process';
import {atomic,withLock,canonical} from './cp-tasks.mjs'; import {deniedRead,isRemotePath,safeName} from './cp-context.mjs';

const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
const fail=(code,message,details)=>{throw Object.assign(new Error(message),{code,...(details?{details}:{})});};
const exists=file=>{try{return fs.lstatSync(file);}catch(e){if(e.code==='ENOENT')return null;throw e;}};
const json=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const cleanEnv=extra=>{const env={...process.env,...extra,GIT_OPTIONAL_LOCKS:'0'}; for(const k of ['GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_COMMON_DIR','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES'])delete env[k]; return env;};
const posix=file=>file.split(path.sep).join('/');
const sha=value=>{if(!/^[0-9a-f]{40}(?:[0-9a-f]{24})?$/.test(String(value)))fail('BAD_COMMIT','Expected a full local Git commit id.');return value;};
const inside=(root,target)=>{const relative=path.relative(path.resolve(root),path.resolve(target));return relative===''||(!relative.startsWith('..'+path.sep)&&relative!=='..'&&!path.isAbsolute(relative));};
function relative(file,{pattern=false}={}){
  if(typeof file!=='string'||!file||file.includes('\\')||file.includes(':')||/[\x00-\x1f\x7f]/.test(file)||path.posix.isAbsolute(file)||isRemotePath(file))fail('BAD_PATH','Expected a portable relative repository path.');
  let value=file;if(pattern&&value.endsWith('/**'))value=value.slice(0,-3);
  if(!value||value.split('/').some(p=>!p||p==='.'||p==='..')||/[?*\[\]]/.test(value))fail('BAD_PATH','Only exact paths or directory/** ownership is supported.');
  return file;
}
const protectedPath=file=>file.toLowerCase().split('/').some(p=>['.git','.agents','.codex','agents.md','claude.md'].includes(p)||/^\.env(?:\.|$)/.test(p))||/^\.github\/workflows(?:\/|$)/i.test(file);
function safeTarget(root,rel,{parentsOnly=false}={}){
  relative(rel);const target=path.resolve(root,...rel.split('/'));if(!inside(root,target))fail('PATH_ESCAPE','Repository path escaped its root.');
  const parts=rel.split('/');let cursor=path.resolve(root);
  for(let i=0;i<parts.length;i++){cursor=path.join(cursor,parts[i]);const stat=exists(cursor);if(!stat)continue;
    if(stat.isSymbolicLink())fail('LINKED_PATH','Linked repository paths are not permitted.',{path:rel});
    if(i<parts.length-1&&!stat.isDirectory())fail('BAD_PATH','A path parent is not a directory.',{path:rel});
    if(i===parts.length-1&&!parentsOnly&&!stat.isFile())fail('NONREGULAR_PATH','Only regular repository files are supported.',{path:rel});
  }return target;
}
// Native realpath expands Windows 8.3 aliases to the same physical spelling Git reports.
function regularRoot(root){if(isRemotePath(root))fail('BAD_ROOT','Build repositories must use a local path.');const resolved=fs.realpathSync.native(root);if(!fs.statSync(resolved).isDirectory())fail('BAD_ROOT','Expected a repository directory.');return resolved;}
function rawGit(cwd,args,{input,allowFailure=false,encoding='utf8',timeout=60000}={}){
  const result=spawnSync('git',['--literal-pathspecs','-C',cwd,...args],{env:cleanEnv(),input,encoding,windowsHide:true,timeout,maxBuffer:64*1024*1024});
  if(result.error)throw result.error;
  if(result.status!==0&&!allowFailure)fail('GIT_FAILED',`git ${args[0]} failed: ${String(result.stderr||result.stdout).trim().slice(0,2000)}`,{exit:result.status,args});
  return result;
}
export function git(cwd,...args){return rawGit(cwd,args).stdout.trim();}
function commonDir(cwd){return path.resolve(cwd,git(cwd,'rev-parse','--git-common-dir'));}
function safeGit(cwd,args,options={}){const common=commonDir(cwd),hooks=path.join(common,'cp-build-empty-hooks');fs.mkdirSync(hooks,{recursive:true});return rawGit(cwd,['-c','core.hooksPath='+hooks,'-c','commit.gpgsign=false',...args],options);}
const gitText=(cwd,args,options)=>safeGit(cwd,args,options).stdout.trim();
function gitFiles(cwd){return [...new Set(rawGit(cwd,['ls-files','-z','--cached','--others','--exclude-standard']).stdout.split('\0').filter(Boolean))].sort();}
function submodules(cwd){const entries=rawGit(cwd,['ls-files','--stage','-z']).stdout.split('\0');if(entries.some(v=>v.startsWith('160000 ')))fail('SUBMODULE_UNSUPPORTED','Build snapshots do not copy submodules.');}
function atomicBytes(file,data,mode){
  fs.mkdirSync(path.dirname(file),{recursive:true});const tmp=file+`.tmp-${process.pid}-${crypto.randomBytes(6).toString('hex')}`;
  const fd=fs.openSync(tmp,'wx',mode??0o600);try{fs.writeFileSync(fd,data);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  if(mode!=null)fs.chmodSync(tmp,mode);
  for(let n=0;;n++){try{fs.renameSync(tmp,file);return;}catch(e){if(!['EPERM','EACCES','EBUSY'].includes(e.code)||n>=20)throw e;Atomics.wait(sleeper,0,0,Math.min(5*2**Math.min(n,4),50));}}
}
const sleeper=new Int32Array(new SharedArrayBuffer(4));
const bytesHash=file=>{const stat=exists(file);if(!stat)return null;if(stat.isSymbolicLink()||!stat.isFile())fail('NONREGULAR_PATH','Expected a regular file.',{path:file});return hash(fs.readFileSync(file));};
const operationName=value=>{if(!safeName(value))fail('BAD_OPERATION','Invalid operation id.');return value;};
function operation(cwd,id){const common=commonDir(cwd),dir=safeTarget(common,'cp-build-operations/'+operationName(id),{parentsOnly:true});fs.mkdirSync(dir,{recursive:true});return {common,dir,file:path.join(dir,'operation.json')};}
function record(file){try{return json(file);}catch(e){if(e.code==='ENOENT')return null;fail('JOURNAL_CORRUPT','Invalid build operation journal.',{file});}}
function assertInput(current,expected){if(current.inputs_hash!==hash(canonical(expected)))fail('OPERATION_CONFLICT','Operation id was reused with different inputs.');}

export async function snapshotRepo({source,runDir}){
  source=regularRoot(source);runDir=path.resolve(runDir);
  if(inside(source,runDir))fail('BAD_RUN_ROOT','The isolated run directory must be outside the source repository.');
  fs.mkdirSync(runDir,{recursive:true});if(exists(runDir)?.isSymbolicLink())fail('LINKED_PATH','The run directory must not be linked.');runDir=fs.realpathSync.native(runDir);
  if(inside(source,runDir))fail('BAD_RUN_ROOT','The resolved run directory must be outside the source repository.');
  const repo=path.join(runDir,'repo'),manifestPath=path.join(runDir,'snapshot.json');
  return withLock(runDir,'snapshot',()=>{
    const previous=record(manifestPath);if(previous){if(previous.source!==source||previous.repo!==repo)fail('SNAPSHOT_CONFLICT','Run directory belongs to a different source.');
      if(previous.state==='complete'){if(git(repo,'rev-parse','HEAD')===previous.base||rawGit(repo,['merge-base','--is-ancestor',previous.base,'HEAD'],{allowFailure:true}).status===0)return {repo,base:previous.base,source,manifestPath,excluded:previous.excluded};fail('SNAPSHOT_CONFLICT','Snapshot Git history no longer contains its recorded base.');}}
    if(exists(repo))fail('RECOVERY_NEEDED','An incomplete snapshot exists; inspect it before starting another snapshot.');
    const top=regularRoot(git(source,'rev-parse','--show-toplevel'));if(top!==source)fail('BAD_ROOT','Pass the Git repository root to snapshotRepo.');submodules(source);
    const files=Object.create(null),excluded=[],checkpoint=path.join(runDir,'source-checkpoint');fs.mkdirSync(repo);fs.mkdirSync(checkpoint);
    atomic(manifestPath,{format:1,state:'preparing',source,repo,excluded,files});
    for(const rel of gitFiles(source)){
      relative(rel);const src=safeTarget(source,rel),stat=exists(src);if(!stat)continue;
      const denial=deniedRead(src,path.join(os.homedir(),'.carrier-pigeon'));if(denial){excluded.push({path:rel,reason:denial});continue;}
      const data=fs.readFileSync(src),digest=hash(data);if(data.length>64*1024*1024)fail('FILE_TOO_LARGE','Snapshot file exceeds 64 MB.',{path:rel});
      if(bytesHash(src)!==digest)fail('SOURCE_CHANGED','Source changed while its snapshot was captured.',{path:rel});
      const dest=safeTarget(repo,rel),saved=safeTarget(checkpoint,rel);atomicBytes(dest,data,stat.mode&0o777);atomicBytes(saved,data,stat.mode&0o777);
      files[rel]={sha256:digest,mode:stat.mode&0o777,checkpoint:posix(path.relative(runDir,saved))};
    }
    rawGit(repo,['init','-q','-b','codex/'+path.basename(runDir).replace(/[^a-zA-Z0-9_-]/g,'-')+'-integration']);
    rawGit(repo,['config','user.name','Carrier Pigeon build']);rawGit(repo,['config','user.email','carrier-pigeon-build@example.invalid']);rawGit(repo,['config','commit.gpgsign','false']);rawGit(repo,['config','core.autocrlf','false']);
    const hooks=path.join(commonDir(repo),'cp-build-empty-hooks');fs.mkdirSync(hooks);rawGit(repo,['config','core.hooksPath',hooks]);
    // A source can already track a path that its current .gitignore matches. It still belongs in the snapshot.
    const copied=Object.keys(files);if(copied.length)safeGit(repo,['add','--force','--pathspec-from-file=-','--pathspec-file-nul'],{input:Buffer.from(copied.join('\0')+'\0')});safeGit(repo,['commit','--allow-empty','-m','Snapshot source for isolated co-build']);const base=git(repo,'rev-parse','HEAD');
    atomic(manifestPath,{format:1,state:'complete',source,repo,base,created:new Date().toISOString(),excluded,files});return {repo,base,source,manifestPath,excluded};
  });
}

export async function initWorktree({repo,runDir,agent,base}){
  repo=regularRoot(repo);runDir=regularRoot(runDir);sha(base);if(!['codex','claude'].includes(agent))fail('BAD_AGENT','Build worktree agent must be codex or claude.');
  if(!inside(runDir,repo))fail('PATH_ESCAPE','The seed repository is outside this run.');
  const cwd=path.join(runDir,'worktrees',agent),branch='codex/'+path.basename(runDir).replace(/[^a-zA-Z0-9_-]/g,'-')+'-'+agent;
  safeTarget(runDir,'worktrees/'+agent,{parentsOnly:true});
  if(exists(cwd)){if(regularRoot(git(cwd,'rev-parse','--show-toplevel'))!==fs.realpathSync.native(cwd)||commonDir(cwd)!==commonDir(repo)||git(cwd,'branch','--show-current')!==branch)fail('WORKTREE_CONFLICT','Existing worktree belongs to a different build.');
    if(rawGit(cwd,['merge-base','--is-ancestor',base,'HEAD'],{allowFailure:true}).status!==0)fail('WORKTREE_CONFLICT','Worktree no longer contains its recorded base.');return {cwd,branch};}
  fs.mkdirSync(path.dirname(cwd),{recursive:true});safeGit(repo,['worktree','add','-b',branch,cwd,base]);return {cwd,branch};
}
export async function syncDependencies({repo,cwd,commits}){
  repo=regularRoot(repo);cwd=regularRoot(cwd);if(commonDir(repo)!==commonDir(cwd))fail('WORKTREE_CONFLICT','Dependency target is not in the isolated repository.');
  for(const commit of [...new Set(commits)]){sha(commit);if(rawGit(cwd,['merge-base','--is-ancestor',commit,'HEAD'],{allowFailure:true}).status===0)continue;
    if(git(cwd,'status','--porcelain'))fail('DIRTY_WORKTREE','Dependency merge requires a clean worktree.');
    const result=safeGit(cwd,['merge','--no-edit',commit],{allowFailure:true});if(result.status!==0)fail('MERGE_CONFLICT','Dependency merge needs conflict resolution; artifacts were preserved.',{cwd,commit,stderr:result.stderr});
  }return git(cwd,'rev-parse','HEAD');
}

function statusChanges(cwd){
  const rows=rawGit(cwd,['status','--porcelain=v1','-z','--untracked-files=all']).stdout.split('\0'),changes=[];
  for(let i=0;i<rows.length;i++){if(!rows[i])continue;const status=rows[i].slice(0,2),rel=rows[i].slice(3);relative(rel);
    if(/[RC]/.test(status)){const original=rows[++i];relative(original);changes.push({path:original,status:'D'},{path:rel,status:'A'});}else changes.push({path:rel,status:status.trim()||status});
  }return [...new Map(changes.map(v=>[v.path,v])).values()].sort((a,b)=>a.path.localeCompare(b.path));
}
export async function inspectWorktree({cwd}){return inspect(cwd);}
function inspect(cwd){cwd=regularRoot(cwd);submodules(cwd);const head=git(cwd,'rev-parse','HEAD'),changes=statusChanges(cwd),digest=crypto.createHash('sha256');
  for(const rel of gitFiles(cwd)){relative(rel);const file=safeTarget(cwd,rel),stat=exists(file);if(!stat)continue;digest.update(canonical({path:rel,mode:stat.mode&0o777,sha256:hash(fs.readFileSync(file))})+'\n');}
  return {head,changes,fingerprint:digest.digest('hex')};
}
function patternBase(pattern){relative(pattern,{pattern:true});return pattern.endsWith('/**')?pattern.slice(0,-3):pattern;}
export function ownsPath(patterns,file){relative(file);if(protectedPath(file))return false;const value=file.toLowerCase();return patterns.some(pattern=>{const base=patternBase(pattern).toLowerCase();return pattern.endsWith('/**')?value.startsWith(base+'/'):value===base;});}
export function validateOwnership(units){
  if(!Array.isArray(units)||!units.length)fail('BAD_OWNERSHIP','Expected build units.');const seen=[];
  for(const [index,unit] of units.entries()){if(typeof (unit.agent??unit.id)!=='string'||!(unit.agent??unit.id))fail('BAD_OWNERSHIP','Every unit needs an agent or id.');const patterns=unit.files||unit.patterns;if(!Array.isArray(patterns)||!patterns.length)fail('BAD_OWNERSHIP','Every unit needs owned paths.');
    for(const p of patterns){const base=patternBase(p).toLowerCase(),prefix=p.endsWith('/**');if(protectedPath(base)||prefix&&['.github/workflows'].some(v=>v.startsWith(base+'/')))fail('PROTECTED_PATH','Ownership includes protected project instructions or metadata.',{path:p});
      for(const old of seen)if(index!==old.unit&&(base===old.base||prefix&&old.base.startsWith(base+'/')||old.prefix&&base.startsWith(old.base+'/')))fail('OWNERSHIP_OVERLAP','Build unit paths overlap (case-insensitive).',{first:old.path,second:p});
      seen.push({base,prefix,path:p,unit:index});
    }
  }return true;
}
export async function checkOwnership({cwd,patterns,expectedHead}){return checkOwned({cwd,patterns,expectedHead});}
function checkOwned({cwd,patterns,expectedHead}){validateOwnership([{agent:'unit',files:patterns}]);const result=inspect(cwd);if(result.head!==sha(expectedHead))fail('HEAD_CHANGED','A worker changed its Git HEAD; do not commit unreviewed history.');
  const outside=result.changes.filter(c=>!ownsPath(patterns,c.path));if(outside.length)fail('OWNERSHIP_VIOLATION','A worker changed files outside its unit.',{paths:outside.map(c=>c.path)});return result;
}

const EXECUTABLES=new Set(['node','node.exe','python','python.exe','python3','python3.exe','py','py.exe','npm','npm.cmd','cargo','cargo.exe','go','go.exe','dotnet','dotnet.exe']);
export function validateCheck({argv,cwd,root=cwd,allowSetup=false}){
  if(!Array.isArray(argv)||!argv.length||argv.length>100||argv.some(v=>typeof v!=='string'||/[\x00\r\n]/.test(v)||v.length>8192))fail('BAD_CHECK','A check needs a bounded argv array.');
  const executable=path.basename(argv[0]).toLowerCase();if(!EXECUTABLES.has(executable))fail('BAD_CHECK','Unsupported check executable; use a repository test command, not a shell.');
  cwd=regularRoot(cwd);root=regularRoot(root);if(!inside(root,cwd))fail('PATH_ESCAPE','Check cwd escaped the build run.');
  const args=argv.slice(1);if(args.some(v=>/^--(?:eval|command|require|import|loader)(?:=|$)/.test(v))||(/^(?:node|python|py)/.test(executable)&&args.some(v=>/^-(?:e|c|r|p)(?:[^-]|$)/.test(v))))fail('BAD_CHECK','Inline evaluation and module preloads are not check commands.');
  if(executable.startsWith('npm')){
    const delimiter=args.indexOf('--'),options=delimiter<0?args:args.slice(0,delimiter);if(options.some(v=>/^(?:--(?:prefix|global|userconfig|globalconfig|cache|script-shell|registry)(?:=|$)|-g$)/.test(v)))fail('BAD_CHECK','npm checks cannot redirect configuration or run another repository.');
    const command=args[0];if(command==='ci'){if(!allowSetup||args.some(v=>!['ci','--ignore-scripts','--offline','--no-audit','--no-fund'].includes(v)))fail('BAD_CHECK','npm ci needs explicit setup authority and supported flags.');}
    else if(command==='test'||command==='t'){}else if(command==='run'&&/^(?:test|check|lint|build|typecheck|validate|verify|format)(?::[A-Za-z0-9_-]+)?$/.test(args[1]||'')){}else fail('BAD_CHECK','Only repository test/check scripts are allowed through npm.');
  }else if(/^python|^py(?:\.exe)?$/.test(executable)){
    const moduleIndex=args.indexOf('-m');if(moduleIndex>=0&&!['unittest','pytest','compileall'].includes(args[moduleIndex+1]))fail('BAD_CHECK','Unsupported Python check module.');
    if(moduleIndex<0&&!args.some(v=>!v.startsWith('-')&&v.endsWith('.py')))fail('BAD_CHECK','A Python check needs a repository script or test module.');
  }else if(executable.startsWith('node')){
    if(!args.length||!args.some(v=>/\.(?:mjs|cjs|js)$/.test(v)||v==='--test'||v==='--check'))fail('BAD_CHECK','A Node check needs a script or built-in test/check mode.');
  }else if(executable.startsWith('cargo')&&!['test','check','clippy','fmt'].includes(args[0]))fail('BAD_CHECK','Unsupported cargo check.');
  else if(executable.startsWith('go')&&!['test','vet'].includes(args[0]))fail('BAD_CHECK','Unsupported go check.');
  else if(executable.startsWith('dotnet')&&!['test','build'].includes(args[0]))fail('BAD_CHECK','Unsupported dotnet check.');
  // Scripts can be absolute (e.g. a reviewer probe), but must stay in the explicit run.
  for(const value of args.filter(v=>/\.(?:mjs|cjs|js|py)$/.test(v)&&!v.startsWith('-'))){const file=path.resolve(cwd,value);if(!inside(root,file))fail('PATH_ESCAPE','Check script escaped the build run.');const rel=posix(path.relative(root,file));safeTarget(root,rel);}
  return {argv:[...argv],cwd};
}
function npmCommand(argv){
  const candidates=[path.join(path.dirname(process.execPath),'node_modules/npm/bin/npm-cli.js'),path.resolve(path.dirname(process.execPath),'../lib/node_modules/npm/bin/npm-cli.js')];
  for(const dir of (process.env.PATH||'').split(path.delimiter))for(const name of process.platform==='win32'?['npm.cmd','npm']:['npm']){const file=path.join(dir,name);if(exists(file)){try{const real=fs.realpathSync(file);if(path.basename(real)==='npm-cli.js')candidates.push(real);}catch{}candidates.push(path.join(dir,'node_modules/npm/bin/npm-cli.js'),path.resolve(dir,'../lib/node_modules/npm/bin/npm-cli.js'));}}
  const cli=candidates.find(file=>exists(file)?.isFile());if(!cli)fail('CHECK_TOOL_MISSING','Cannot resolve npm-cli.js without a shell; install/configure Node/npm first.');return {file:process.execPath,args:[cli,...argv.slice(1)]};
}
export async function runCheck({argv,cwd,root=cwd,scratch,receiptDir,id,timeoutMs=600000,allowSetup=false,signal,sandbox=null}){
  ({argv,cwd}=validateCheck({argv,cwd,root,allowSetup}));operationName(id);if(!Number.isFinite(timeoutMs)||timeoutMs<1||timeoutMs>3600000)fail('BAD_CHECK','Check timeout must be 1..3600000 ms.');
  scratch=path.resolve(scratch);receiptDir=path.resolve(receiptDir);fs.mkdirSync(scratch,{recursive:true});fs.mkdirSync(receiptDir,{recursive:true});
  const stdout_path=path.join(receiptDir,id+'.stdout.log'),stderr_path=path.join(receiptDir,id+'.stderr.log'),receiptFile=path.join(receiptDir,id+'.json');
  if(exists(receiptFile)){const prior=json(receiptFile);if(canonical(prior.argv)!==canonical(argv)||prior.cwd!==cwd)fail('CHECK_CONFLICT','Check receipt id was reused for a different command.');if(prior.fingerprint!==inspect(cwd).fingerprint)fail('STALE_CHECK','Source changed after the recorded check; use a fresh check attempt.');return prior;}
  if(exists(stdout_path)||exists(stderr_path))fail('RECOVERY_NEEDED','An interrupted check left logs without a receipt; retain them and use a fresh attempt directory.',{stdout_path,stderr_path});
  const before=inspect(cwd),started=new Date().toISOString(),command=path.basename(argv[0]).toLowerCase().startsWith('npm')?npmCommand(argv):{file:argv[0],args:argv.slice(1)};
  let runner=command;if(sandbox){if(typeof sandbox.bin!=='string'||!sandbox.bin)fail('BAD_CHECK','Sandbox executable is required.');const profile=sandbox.profile||':workspace';if(profile!==':workspace')fail('BAD_CHECK','Unsupported check sandbox profile.');runner={file:sandbox.bin,args:['sandbox','-P',profile,'-C',cwd,'--',command.file,...command.args]};}
  const stdoutFd=fs.openSync(stdout_path,'wx');let stderrFd;try{stderrFd=fs.openSync(stderr_path,'wx');}catch(e){fs.closeSync(stdoutFd);throw e;}
  const stdout=fs.createWriteStream(stdout_path,{fd:stdoutFd}),stderr=fs.createWriteStream(stderr_path,{fd:stderrFd});let outBytes=0,errBytes=0,truncated=false,timed_out=false,aborted=false,error=null,killTimer=null;
  const checkEnv=cleanEnv({TEMP:scratch,TMP:scratch,TMPDIR:scratch,CARRIER_PIGEON_WORKER:'1',CARRIER_PIGEON_HOME:path.join(scratch,'check-mailbox'),NPM_CONFIG_CACHE:path.join(scratch,'npm-cache')});
  // Run checks as workers and omit common credential/preload environment variables.
  for(const name of Object.keys(checkEnv))if(/(?:^|_)(?:TOKEN|SECRET|PASSWORD|API_KEY|CREDENTIALS?)(?:_|$)/i.test(name)||['NODE_OPTIONS','NODE_PATH','PYTHONPATH'].includes(name))delete checkEnv[name];
  const child=spawn(runner.file,runner.args,{cwd,env:checkEnv,windowsHide:true,detached:process.platform!=='win32',stdio:['ignore','pipe','pipe']});
  const stop=()=>{if(child.exitCode!==null||child.signalCode)return;if(process.platform==='win32'&&Number.isInteger(child.pid)){try{spawnSync('taskkill.exe',['/PID',String(child.pid),'/T','/F'],{stdio:'ignore',windowsHide:true,timeout:10000});}catch{}}else if(Number.isInteger(child.pid)){try{process.kill(-child.pid,'SIGTERM');}catch{child.kill('SIGTERM');}killTimer=setTimeout(()=>{try{process.kill(-child.pid,'SIGKILL');}catch{}},1000);killTimer.unref();}};
  for(const stream of [stdout,stderr])stream.on('error',e=>{error=e.message;stop();});
  child.stdout.on('data',data=>{const left=2*1024*1024-outBytes;if(left>0)stdout.write(data.subarray(0,left));outBytes+=data.length;if(outBytes>2*1024*1024)truncated=true;});
  child.stderr.on('data',data=>{const left=2*1024*1024-errBytes;if(left>0)stderr.write(data.subarray(0,left));errBytes+=data.length;if(errBytes>2*1024*1024)truncated=true;});
  const timer=setTimeout(()=>{timed_out=true;stop();},timeoutMs);const abort=()=>{aborted=true;stop();};signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
  const exit=await new Promise(resolve=>{child.once('error',e=>{error=e.message;resolve(null);});child.once('close',resolve);});clearTimeout(timer);if(!timed_out&&!aborted)clearTimeout(killTimer);signal?.removeEventListener('abort',abort);
  await Promise.all([new Promise(r=>stdout.end(r)),new Promise(r=>stderr.end(r))]);const after=inspect(cwd);
  const result={id,argv,cwd,exit,passed:exit===0&&!timed_out&&!aborted&&!error,stdout_path,stderr_path,before_fingerprint:before.fingerprint,fingerprint:after.fingerprint,started,finished:new Date().toISOString(),timed_out,aborted,truncated,...(error?{error}:{}),runner:{file:runner.file,args:runner.args},sandboxed:!!sandbox};atomic(receiptFile,result);return result;
}

export async function commitUnit({repo,cwd,patterns,expectedHead,operationId,message}){
  repo=regularRoot(repo);cwd=regularRoot(cwd);if(commonDir(repo)!==commonDir(cwd))fail('WORKTREE_CONFLICT','Unit is outside the isolated repository.');sha(expectedHead);
  const op=operation(repo,operationId),inputs={kind:'commit',cwd,patterns,expectedHead,message:String(message)};
  return withLock(op.common,'build-git',()=>{let journal=record(op.file);if(journal)assertInput(journal,inputs);
    if(journal?.state==='committed'){if(rawGit(cwd,['merge-base','--is-ancestor',journal.commit,'HEAD'],{allowFailure:true}).status!==0)fail('HEAD_CHANGED','Recorded unit commit is no longer in the branch.');return journal.result;}
    const head=git(cwd,'rev-parse','HEAD'),marker=`[cp-build-op:${operationId}]`;
    if(journal&&head!==expectedHead){const parent=git(cwd,'rev-parse',head+'^'),tree=git(cwd,'rev-parse',head+'^{tree}'),body=git(cwd,'log','-1','--format=%B');
      if(parent!==expectedHead||tree!==journal.tree||!body.includes(marker))fail('RECOVERY_NEEDED','Git advanced during an interrupted commit; inspect the branch.');
      const result={commit:head,files:journal.files,fingerprint:inspect(cwd).fingerprint};atomic(op.file,{...journal,state:'committed',commit:head,result});return result;
    }
    const current=checkOwned({cwd,patterns,expectedHead});if(!current.changes.length)fail('NO_CHANGES','A build unit must contain an authored change.');
    const files=current.changes.map(c=>c.path);safeGit(cwd,['add','--all','--',...files]);const tree=git(cwd,'write-tree');
    if(journal&&journal.tree!==tree)fail('OPERATION_CONFLICT','Staged content changed after commit intent.');
    journal=journal||{format:1,inputs_hash:hash(canonical(inputs)),...inputs,state:'prepared',tree,files};atomic(op.file,journal);
    safeGit(cwd,['commit','-m',String(message)+'\n\n'+marker]);const commit=git(cwd,'rev-parse','HEAD'),result={commit,files,fingerprint:inspect(cwd).fingerprint};atomic(op.file,{...journal,state:'committed',commit,result});return result;
  });
}
export async function mergeUnits({repo,commits,operationId}){
  repo=regularRoot(repo);commits=[...new Set(commits.map(sha))];const op=operation(repo,operationId),inputs={kind:'merge',repo,commits};
  return withLock(op.common,'build-git',()=>{let journal=record(op.file);if(journal)assertInput(journal,inputs);if(journal?.state==='merged')return journal.result;
    if(!journal){if(git(repo,'status','--porcelain'))fail('DIRTY_WORKTREE','Integration requires a clean isolated worktree.');journal={format:1,inputs_hash:hash(canonical(inputs)),...inputs,state:'prepared',base:git(repo,'rev-parse','HEAD'),next:0};atomic(op.file,journal);}
    for(let i=journal.next;i<commits.length;i++){
      if(rawGit(repo,['merge-base','--is-ancestor',commits[i],'HEAD'],{allowFailure:true}).status!==0){const result=safeGit(repo,['merge','--no-edit',commits[i]],{allowFailure:true});if(result.status!==0)fail('MERGE_CONFLICT','Integration merge needs resolution; no source files were published.',{commit:commits[i],stderr:result.stderr});}
      journal={...journal,next:i+1};atomic(op.file,journal);
    }
    const commit=git(repo,'rev-parse','HEAD'),files=rawGit(repo,['diff','--no-renames','--name-only','-z',journal.base,commit]).stdout.split('\0').filter(Boolean),result={commit,files};atomic(op.file,{...journal,state:'merged',result});return result;
  });
}
function desiredFile(repo,commit,rel,old){
  const line=rawGit(repo,['ls-tree','-z',commit,'--',rel]).stdout.split('\0')[0];if(!line)return {data:null,sha256:null,mode:null};
  const mode=line.split(' ')[0];if(!['100644','100755'].includes(mode))fail('LINKED_PATH','Only regular files can be published.',{path:rel});
  let data=rawGit(repo,['show',commit+':'+rel],{encoding:null}).stdout;
  if(old){const original=fs.readFileSync(old.checkpointAbsolute),originalText=original.toString('utf8'),newText=data.toString('utf8');if(!original.includes(0)&&!data.includes(0)&&Buffer.from(originalText).equals(original)&&Buffer.from(newText).equals(data)&&/\r\n/.test(originalText)&&!/(^|[^\r])\n/.test(originalText))data=Buffer.from(newText.replace(/\r?\n/g,'\r\n'));}
  let permissions=old?.mode??(mode==='100755'?0o755:0o644);if(process.platform!=='win32')permissions=mode==='100755'?permissions|0o111:permissions&~0o111;
  return {data,sha256:hash(data),mode:permissions};
}
export async function publishResult({source,repo,base,commit,runDir,operationId}){
  source=regularRoot(source);repo=regularRoot(repo);runDir=regularRoot(runDir);sha(base);sha(commit);
  const manifest=json(path.join(runDir,'snapshot.json'));if(manifest.state!=='complete'||manifest.source!==source||manifest.repo!==repo||manifest.base!==base)fail('SNAPSHOT_CONFLICT','Publication does not match the captured source.');
  const op=operation(repo,operationId),inputs={kind:'publish',source,repo,base,commit};
  return withLock(op.common,'build-publish',()=>{let journal=record(op.file);if(journal)assertInput(journal,inputs);
    if(journal?.state==='published')return journal.result;
    if(!journal){
      const names=rawGit(repo,['diff','--no-renames','--name-only','-z',base,commit]).stdout.split('\0').filter(Boolean);const files=[];
      for(const rel of names){relative(rel);if(protectedPath(rel))fail('PROTECTED_PATH','Refusing to publish protected project instructions or metadata.',{path:rel});safeTarget(source,rel);
        const old=Object.hasOwn(manifest.files,rel)?manifest.files[rel]:null,checkpointAbsolute=old?path.resolve(runDir,old.checkpoint):null;
        if(old&&(!inside(runDir,checkpointAbsolute)||bytesHash(checkpointAbsolute)!==old.sha256))fail('JOURNAL_CORRUPT','The original source checkpoint failed integrity validation.',{path:rel});
        const target=desiredFile(repo,commit,rel,old?{...old,checkpointAbsolute}:null);const payload=path.join(op.dir,'payload',rel),backup=path.join(op.dir,'backup',rel);
        if(target.data!==null)atomicBytes(payload,target.data,target.mode);if(old)atomicBytes(backup,fs.readFileSync(checkpointAbsolute),old.mode);
        files.push({path:rel,old_sha256:old?.sha256??null,new_sha256:target.sha256,mode:target.mode,payload:target.data===null?null:posix(path.relative(op.dir,payload)),backup:old?posix(path.relative(op.dir,backup)):null,applied:false});
      }
      const patch=path.join(op.dir,'result.patch');atomicBytes(patch,rawGit(repo,['diff','--binary',base,commit],{encoding:null}).stdout,0o600);
      journal={format:1,inputs_hash:hash(canonical(inputs)),...inputs,state:'prepared',files,patch,backup:path.join(op.dir,'backup')};atomic(op.file,journal);
    }
    const conflicts=[];for(const file of journal.files){const current=bytesHash(safeTarget(source,file.path));if(current!==file.old_sha256&&current!==file.new_sha256)conflicts.push(file.path);
      if(file.payload&&bytesHash(safeTarget(op.dir,file.payload))!==file.new_sha256)fail('JOURNAL_CORRUPT','Prepared publication bytes failed integrity validation.',{path:file.path});
    }if(conflicts.length)fail('SOURCE_CHANGED','Original source changed since the build snapshot; integrated code and backups are preserved.',{paths:conflicts});
    for(let i=0;i<journal.files.length;i++){const item=journal.files[i],target=safeTarget(source,item.path),current=bytesHash(target);
      if(current!==item.new_sha256){if(current!==item.old_sha256)fail('SOURCE_CHANGED','Source changed during publication.',{paths:[item.path]});
        if(item.payload)atomicBytes(target,fs.readFileSync(safeTarget(op.dir,item.payload)),item.mode);else if(exists(target))fs.unlinkSync(target);
      }
      // Git can change only an executable bit, leaving the content hash unchanged.
      if(item.payload&&process.platform!=='win32'&&(fs.statSync(target).mode&0o777)!==item.mode)fs.chmodSync(target,item.mode);
      if(!item.applied){journal={...journal,files:journal.files.map((f,n)=>n===i?{...f,applied:true}:f)};atomic(op.file,journal);}
    }
    const result={applied:journal.files.map(f=>f.path),backup:journal.backup,patch:journal.patch};atomic(op.file,{...journal,state:'published',result});return result;
  });
}
