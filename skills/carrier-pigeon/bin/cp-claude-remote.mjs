// Experimental Desktop Remote Control adapter. It neither launches a CLI worker
// nor opens the GUI: an already enabled Desktop environment owns native startup.
import fs from 'node:fs'; import path from 'node:path'; import os from 'node:os';
import {randomUUID} from 'node:crypto'; import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {parse} from './carrier-pigeon.mjs'; import * as tasks from './cp-tasks.mjs'; import * as ctx from './cp-context.mjs';
import {remoteAddress,remotePointer,createRemoteClient} from './cp-claude-remote-client.mjs';

const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch(e){if(e.code==='ENOENT')return null;throw e;}};
const positivePid=pid=>Number.isSafeInteger(pid)&&pid>0;
// Only birth identity is queried. Never collect process arguments or command lines.
// null means unknown; only an explicit ESRCH establishes that a PID is dead.
function processIdentity(pid){
  if(!positivePid(pid))return null;
  try{process.kill(pid,0);}catch(e){if(e.code==='ESRCH')return {pid,dead:true};return null;}
  try{
    if(process.platform==='win32'){
      const command=`$p = Get-CimInstance Win32_Process -Filter 'ProcessId = ${pid}'; if ($p) { [PSCustomObject]@{pid=$p.ProcessId;created=$p.CreationDate.ToUniversalTime().ToString('o')} | ConvertTo-Json -Compress }`;
      const r=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-EncodedCommand',Buffer.from(command,'utf16le').toString('base64')],{windowsHide:true,encoding:'utf8',timeout:10000,maxBuffer:4096});
      if(r.status!==0)return null;const value=JSON.parse(r.stdout);
      if(value.pid!==pid||typeof value.created!=='string')return null;
      return {pid,birth:'win32:'+value.created,createdAtMs:Date.parse(value.created)};
    }
    if(process.platform==='linux'){
      const stat=fs.readFileSync(`/proc/${pid}/stat`,'utf8'),ticks=stat.slice(stat.lastIndexOf(')')+2).trim().split(/\s+/)[19];
      const boot=fs.readFileSync('/proc/sys/kernel/random/boot_id','utf8').trim();
      const bootSeconds=Number(/^btime (\d+)$/m.exec(fs.readFileSync('/proc/stat','utf8'))?.[1]);
      const hzResult=spawnSync('getconf',['CLK_TCK'],{encoding:'utf8',timeout:5000,maxBuffer:4096,windowsHide:true}),hz=Number(hzResult.stdout?.trim());
      if(!/^\d+$/.test(ticks)||!boot||hzResult.status!==0||!(hz>0)||!Number.isFinite(bootSeconds))return null;
      return {pid,birth:`linux:${boot}:${ticks}`,createdAtMs:bootSeconds*1000+Number(ticks)*1000/hz};
    }
    if(process.platform==='darwin'){
      const r=spawnSync('ps',['-p',String(pid),'-o','lstart='],{encoding:'utf8',timeout:5000,maxBuffer:4096,windowsHide:true,env:{...process.env,LC_ALL:'C',TZ:'UTC'}});
      if(r.status!==0)return null;const created=r.stdout.trim();
      return {pid,birth:'darwin:'+created,createdAtMs:Date.parse(created+' UTC')};
    }
  }catch{}return null;
}
const knownIdentity=(identity,pid)=>identity?.pid===pid&&positivePid(pid)&&identity.dead!==true&&typeof identity.birth==='string'&&identity.birth.length>0&&identity.birth.length<=256&&!/[\x00-\x1f]/.test(identity.birth)&&Number.isFinite(identity.createdAtMs)&&identity.createdAtMs>0;
const event=(root,id,ev,extra={})=>{const dir=path.join(root,'receipts');fs.mkdirSync(dir,{recursive:true});fs.appendFileSync(path.join(dir,id+'.jsonl'),JSON.stringify({ts:new Date().toISOString(),ev,...extra})+'\n');};
const error=code=>Object.assign(new Error(code),{code});
function localDirectory(dir){if(typeof dir!=='string'||!path.isAbsolute(dir)||ctx.isRemotePath(dir)||/[\x00-\x1f]/.test(dir)||!fs.statSync(dir).isDirectory())throw error('DESKTOP_INVALID_DIRECTORY');return dir;}
function credentialJson(file){const stat=fs.lstatSync(file);if(!stat.isFile()||stat.isSymbolicLink()||stat.nlink!==1||stat.size>2*1024*1024)throw error('DESKTOP_CREDENTIAL_UNSAFE');return JSON.parse(fs.readFileSync(file,'utf8'));}
// Existing credentials stay in memory and are used only for the official API.
// Expired credentials require the user's normal login; this adapter never refreshes or rewrites them.
export function credentialProvider({home=os.homedir(),accountId,orgId}={}){
  if(!/^[0-9a-f-]{36}$/i.test(accountId||'')||!/^[0-9a-f-]{36}$/i.test(orgId||''))throw error('DESKTOP_ACCOUNT_REQUIRED');
  return ()=>{try{
    const account=credentialJson(path.join(home,'.claude.json')).oauthAccount;
    if(account?.accountUuid!==accountId||account.organizationUuid!==orgId)throw error('DESKTOP_ACCOUNT_CHANGED');
    const c=credentialJson(path.join(home,'.claude','.credentials.json')).claudeAiOauth;
    if(!c?.scopes?.includes('user:sessions:claude_code')||typeof c.accessToken!=='string'||!c.accessToken)throw error('DESKTOP_AUTH_UNAVAILABLE');
    if(!Number.isFinite(c.expiresAt)||c.expiresAt<=Date.now()+5000)throw error('DESKTOP_AUTH_EXPIRED');
    return c.accessToken;
  }catch(e){throw error(/^DESKTOP_[A-Z_]+$/.test(e.code||'')?e.code:'DESKTOP_AUTH_UNAVAILABLE');}};
}
export class ClaudeRemoteBridge{
  constructor({root,environmentId,cwd,client,scanMs=1000,now=Date.now,log=()=>{},processIdentity:identityProvider=processIdentity}){
    if(!ctx.isMailbox(root)||ctx.isRemotePath(root))throw error('DESKTOP_LOCAL_MAILBOX_REQUIRED');
    this.root=root;this.environmentId=environmentId;this.address=remoteAddress(environmentId);this.cwd=localDirectory(cwd);
    this.client=client;this.scanMs=scanMs;this.now=now;this.log=log;this.processIdentity=identityProvider;this.stopped=true;this.busy=false;this.token=randomUUID();
    this.ownerFile=path.join(root,'host','claude-remote-owners',this.address+'.json');
    this.presenceFile=path.join(root,'sessions','claude~'+this.address+'.json');
  }
  stoppedTask(m){const c=tasks.control(this.root,m.id);return !!(c?.terminal||c?.cancel_requested||c?.lease_expired||(m.expires_at&&Date.parse(m.expires_at)<=Date.now()));}
  wantsReplyWake(m){if(m.kind!=='reply'||!ctx.ID_RE.test(String(m.reply_to)))return false;
    for(const box of ['done','claimed','inbox'])try{
      const ask=parse(fs.readFileSync(path.join(this.root,'agents',m.from,box,m.reply_to+'.md'),'utf8'));
      return ask.from==='claude'&&ask.to===m.from&&ask.from_session===this.address&&ask.thread===m.thread&&ask.wake_on_reply===true;
    }catch(e){if(e.code!=='ENOENT')throw e;}return false;}
  eligible(m){return m?.to==='claude'&&m.to_session===this.address&&ctx.ID_RE.test(String(m.id))&&ctx.safeName(m.thread)&&['codex','claude','cursor','grok','matt'].includes(m.from)&&(['ask','handoff','review-request'].includes(m.kind)||this.wantsReplyWake(m));}
  async deliver(m){
    if(!this.eligible(m)||this.stoppedTask(m)||this.stopped)return false;
    const file=path.join(this.root,'host','claude-remote-deliveries',m.id+'.json');
    const bindingFile=path.join(this.root,'host','claude-remote-threads',this.environmentId,m.thread+'.json');
    const reserved=tasks.withLock(this.root,'claude-remote:'+m.id,()=>{
      const old=read(file);if(old&&(old.phase!=='deferred'||old.retryAt>this.now()))return null;
      const recentDir=path.dirname(file);fs.mkdirSync(recentDir,{recursive:true});
      const recent=fs.readdirSync(recentDir).filter(n=>ctx.ID_RE.test(n.slice(0,-5))&&n.endsWith('.json')).map(n=>read(path.join(recentDir,n))).filter(s=>s?.environmentId===this.environmentId&&this.now()-s.at<60000&&['dispatching','submitted','uncertain'].includes(s.phase));
      if(recent.length>=3){
        const retryAt=Math.min(...recent.map(s=>s.at))+60000;
        tasks.atomic(file,{phase:'deferred',id:m.id,environmentId:this.environmentId,retryAt});
        if(!old)event(this.root,m.id,'desktop-remote-deferred',{reason:'rate-limit',retryAt});
        return null;
      }
      const state={phase:'dispatching',id:m.id,thread:m.thread,environmentId:this.environmentId,eventId:randomUUID(),owner:process.pid,at:this.now()};
      tasks.atomic(file,state);return state;
    });
    if(!reserved)return false;
    try{
      const index=path.join(this.root,'threads',m.thread+'.idx');
      if(fs.existsSync(index)&&fs.readFileSync(index,'utf8').split(/\r?\n/).filter(Boolean).length>8)throw Object.assign(error('DESKTOP_HOP_LIMIT'),{preDispatch:true});
      const binding=read(bindingFile);
      if(binding&&(binding.environmentId!==this.environmentId||binding.thread!==m.thread))throw Object.assign(error('DESKTOP_BINDING_INVALID'),{preDispatch:true});
      const text=remotePointer(m,{root:this.root,cli:path.join(this.root,'bin','carrier-pigeon.mjs')});
      if(this.stopped||this.stoppedTask(m))throw Object.assign(error('DESKTOP_TASK_STOPPED'),{preDispatch:true});
      event(this.root,m.id,'desktop-remote-requested',{environmentId:this.environmentId,follow_up:!!binding});
      let remoteSessionId;
      if(binding){
        remoteSessionId=binding.remoteSessionId;
        let response;try{response=await this.client.get(remoteSessionId);}catch(e){throw Object.assign(error(/^[A-Z][A-Z0-9_]{1,79}$/.test(e.code||'')?e.code:'DESKTOP_REMOTE_LOOKUP_FAILED'),{preDispatch:true});}
        const remote=response?.response_shape??response?.session;
        if(remote?.id!==remoteSessionId||remote.environment_id!==this.environmentId||remote.environment_kind!=='bridge')throw Object.assign(error('DESKTOP_BINDING_INVALID'),{preDispatch:true});
        if(this.stopped||this.stoppedTask(m))throw Object.assign(error('DESKTOP_TASK_STOPPED'),{preDispatch:true});
        await this.client.send({sessionId:remoteSessionId,text,eventId:reserved.eventId});
      }
      else{
        const response=await this.client.create({environmentId:this.environmentId,cwd:this.cwd,text,eventId:reserved.eventId,title:'carrier-pigeon hand-off '+m.id});
        remoteSessionId=typeof response==='string'?response:response?.session?.id;
        if(!/^(?:cse_|session_)[A-Za-z0-9]+$/.test(remoteSessionId||''))throw error('DESKTOP_REMOTE_BAD_SESSION');
        tasks.atomic(bindingFile,{environmentId:this.environmentId,thread:m.thread,remoteSessionId,createdBy:m.id});
      }
      tasks.atomic(file,{...reserved,phase:'submitted',remoteSessionId});
      event(this.root,m.id,'desktop-remote-submitted',{environmentId:this.environmentId,remoteSessionId});
      // API acceptance is not native startup or completion. Only native receipts
      // and the recipient's mailbox acknowledgement can establish that.
      return true;
    }catch(e){const code=/^[A-Z][A-Z0-9_]{1,79}$/.test(e.code||'')?e.code:'DESKTOP_REMOTE_FAILED';
      tasks.atomic(file,{...reserved,phase:e.preDispatch?'rejected':'uncertain',code});
      event(this.root,m.id,'desktop-remote-failed',{code,uncertain:!e.preDispatch});throw error(code);}
  }
  async scan(){if(this.stopped||this.busy)return;this.busy=true;try{
    const dir=path.join(this.root,'agents','claude','inbox');
    for(const name of fs.readdirSync(dir).filter(n=>n.endsWith('.md')&&ctx.ID_RE.test(n.slice(0,-3))).sort()){
      let m;try{m=parse(fs.readFileSync(path.join(dir,name),'utf8'));}catch(e){if(e.code==='ENOENT')continue;throw e;}
      if(this.eligible(m)&&!this.stoppedTask(m))try{await this.deliver(m);}catch(e){this.log({ev:'desktop-remote-error',id:m.id,code:e.code});}
    }
  }finally{this.busy=false;}}
  publishPresence(){const started=this.started;tasks.atomic(this.presenceFile,{agent:'claude',session:this.address,pid:process.pid,client:'carrier-pigeon Desktop Remote Control '+ctx.VERSION,started,last_seen:new Date().toISOString(),desktop_remote:true,environment_id:this.environmentId,owner:this.token});}
  async start(){tasks.withLock(this.root,'claude-remote-owner:'+this.address,()=>{
    const probe=pid=>{try{return this.processIdentity(pid);}catch{return null;}},old=read(this.ownerFile);
    if(old){
      if(!positivePid(old.pid))throw error('DESKTOP_REMOTE_OWNER_UNKNOWN');
      const current=probe(old.pid);
      if(!(current?.pid===old.pid&&current.dead===true)){
        if(!knownIdentity(current,old.pid))throw error('DESKTOP_REMOTE_OWNER_UNKNOWN');
        if(Object.hasOwn(old,'birth')){
          if(typeof old.birth!=='string'||!old.birth||old.birth.length>256||/[\x00-\x1f]/.test(old.birth))throw error('DESKTOP_REMOTE_OWNER_UNKNOWN');
          if(current.birth===old.birth)throw error('DESKTOP_REMOTE_OWNER_ACTIVE');
        }else{
          // A legacy PID alone cannot distinguish its original owner from reuse.
          // Only a strictly later OS birth than this record proves stale ownership.
          if(!(current.createdAtMs>fs.statSync(this.ownerFile).mtimeMs))throw error('DESKTOP_REMOTE_OWNER_ACTIVE');
        }
      }
    }
    const own=probe(process.pid);if(!knownIdentity(own,process.pid))throw error('DESKTOP_REMOTE_OWNER_UNKNOWN');
    tasks.atomic(this.ownerFile,{pid:process.pid,token:this.token,birth:own.birth});
  });
    this.started=new Date().toISOString();this.publishPresence();this.presenceTimer=setInterval(()=>{try{this.publishPresence();}catch{this.log({ev:'desktop-remote-presence-failed'});}},15000);
    this.stopped=false;this.timer=setInterval(()=>this.scan().catch(()=>this.log({ev:'desktop-remote-scan-failed'})),this.scanMs);await this.scan();}
  async stop(){this.stopped=true;clearInterval(this.timer);clearInterval(this.presenceTimer);tasks.withLock(this.root,'claude-remote-owner:'+this.address,()=>{const old=read(this.ownerFile);if(old?.pid===process.pid&&old.token===this.token){fs.rmSync(this.ownerFile,{force:true});const presence=read(this.presenceFile);if(presence?.owner===this.token)fs.rmSync(this.presenceFile,{force:true});}});}
}
export async function main(argv=process.argv.slice(2)){
  const value=k=>{const n=argv.indexOf('--'+k);return n<0?null:argv[n+1];};
  const root=value('root'),environmentId=value('environment'),cwd=value('cwd'),orgId=value('org'),accountId=value('account');
  const getAccessToken=credentialProvider({accountId,orgId});getAccessToken();
  const client=createRemoteClient({getAccessToken,orgId});
  const bridge=new ClaudeRemoteBridge({root,environmentId,cwd,client,log:e=>console.error(JSON.stringify(e))});
  await bridge.start();console.log(JSON.stringify({ev:'desktop-remote-ready',address:bridge.address,pid:process.pid}));
  for(const signal of ['SIGINT','SIGTERM','SIGBREAK'])process.on(signal,()=>bridge.stop().then(()=>process.exit(0)));
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(e=>{console.error('carrier-pigeon remote bridge: '+(/^DESKTOP_[A-Z_]+$/.test(e.code||'')?e.code:'START_FAILED'));process.exitCode=1;});
