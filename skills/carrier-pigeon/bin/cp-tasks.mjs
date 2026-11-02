import * as identity from './cp-identity.mjs';
// Durable local request controls. Message content is immutable; cancellation, leases and delivery state live beside it.
// No provider calls, timers, shell, or dependencies. control() is a pure read so the host can gate dispatch safely.
import fs from 'node:fs'; import path from 'node:path'; import crypto from 'node:crypto';
import {ID_RE,hasSecret} from './cp-context.mjs';
const AGENTS=['grok','cursor','claude','codex',identity.HUMAN_ID];
export const TERMINAL=new Set(['completed','declined','blocked','partial','closed_without_reply','cancelled','expired']);
const STATES=new Set(['queued','claimed','running','cancel_requested','recovery_needed','missing_reply',...TERMINAL]);
const fail=m=>{throw new Error(m);};
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const idOf=id=>{if(!ID_RE.test(String(id)))fail('bad task id (want a 26-char ULID)');return id;};
const rootDir=root=>path.join(root,'tasks');
const taskFile=(root,id)=>path.join(rootDir(root),idOf(id)+'.json');
const now=()=>new Date().toISOString();
export function text(value,name,max=2048){if(typeof value!=='string'||!value.trim()||Buffer.byteLength(value)>max)fail(`${name} must be nonempty text, at most ${max} bytes`);if(hasSecret(value))fail(`${name} looks like it contains a secret`);return value.trim();}
export function requestKey(key){return text(key,'request_key',128);}
export function seconds(value,name,max=604800){const n=Number(value);if(!Number.isFinite(n)||n<=0||n>max)fail(`${name} must be greater than zero and at most ${max}`);return n;}
export const canonical=value=>JSON.stringify(sortJson(value));
function sortJson(v){if(Array.isArray(v))return v.map(sortJson);if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,sortJson(v[k])]));return v;}
export function jsonInput(value,name,max=16384){let v=value;if(typeof v==='string'){try{v=JSON.parse(v);}catch{fail(`${name} must be valid JSON`);}}
  const s=canonical(v);if(s===undefined||Buffer.byteLength(s)>max)fail(`${name} exceeds ${max} bytes`);if(hasSecret(s))fail(`${name} looks like it contains a secret`);return v;}
export function atomic(file,value){fs.mkdirSync(path.dirname(file),{recursive:true});const tmp=file+`.tmp-${process.pid}-${crypto.randomBytes(6).toString('hex')}`;
  const fd=fs.openSync(tmp,'wx');try{fs.writeFileSync(fd,JSON.stringify(value,null,1)+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  // Windows readers/AV can briefly deny replacement. Retry the same staged bytes, never republish the logical operation.
  // An attempt bound avoids dependence on wall-clock changes; permanent denial still surfaces with the staged record intact.
  for(let attempt=0;;attempt++){try{fs.renameSync(tmp,file);return;}catch(e){if(!['EPERM','EACCES','EBUSY'].includes(e.code)||attempt>=20)throw e;
      Atomics.wait(sleeper,0,0,Math.min(5*2**Math.min(attempt,4),50));}}}
const sleeper=new Int32Array(new SharedArrayBuffer(4));
// A complete owner record is linked atomically into one exclusive slot. Dead-owner cleanup is itself serialized.
export function withLock(root,key,fn){const dir=path.join(rootDir(root),'.locks');fs.mkdirSync(dir,{recursive:true});const file=path.join(dir,hash(key)+'.lock'),token=crypto.randomBytes(12).toString('hex'),until=Date.now()+10000;
  // Link a fully written owner record into the lock slot atomically. A crash can leave an orphan owner file, never an ownerless new lock.
  const owner=file+`.owner-${process.pid}-${token}`,fd=fs.openSync(owner,'wx');try{fs.writeFileSync(fd,JSON.stringify({pid:process.pid,token}));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  try{for(;;){try{fs.linkSync(owner,file);break;}catch(e){if(e.code!=='EEXIST')throw e;let old=null,raw=null;try{raw=fs.readFileSync(file,'utf8');old=JSON.parse(raw);}catch(e){if(e.code==='ENOENT')continue;fail('task lock is corrupt or incomplete; inspect the lock record and active processes before removing it');}
      if(!Number.isInteger(old?.pid)||old.pid<=0||typeof old.token!=='string')fail('task lock has no valid owner; inspect it before removing it');
      let alive=false;try{process.kill(old.pid,0);alive=true;}catch(e){alive=e.code==='EPERM';}
      if(!alive){const guard=file+'.reap';let held=false;try{try{fs.linkSync(owner,guard);held=true;}catch(e){if(e.code!=='EEXIST')throw e;const reaper=read(guard);let busy=false;try{process.kill(reaper?.pid,0);busy=true;}catch(e){busy=e.code==='EPERM';}if(!busy)fail('task lock recovery was interrupted; inspect its recovery lock before retrying');}
          if(held){let current=null;try{current=JSON.parse(fs.readFileSync(file,'utf8'));}catch(e){if(e.code==='ENOENT')continue;throw e;}let currentAlive=false;try{process.kill(current.pid,0);currentAlive=true;}catch(e){currentAlive=e.code==='EPERM';}if(!currentAlive){fs.unlinkSync(file);continue;}}}
        finally{if(held){try{fs.unlinkSync(guard);}catch{}}}}
      if(Date.now()>=until)fail('task is busy in another process; retry the same request key');Atomics.wait(sleeper,0,0,20);}}
    try{return fn();}finally{try{if(JSON.parse(fs.readFileSync(file,'utf8')).token===token)fs.unlinkSync(file);}catch{}}}
  finally{try{fs.unlinkSync(owner);}catch{}}}
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch(e){if(e.code==='ENOENT')return null;throw new Error(`invalid durable task record: ${path.basename(file)}`);}};
export function control(root,id){const c=read(taskFile(root,id));if(c&&c.id!==id)fail('invalid task control record');return effectiveControl(c);}
export function effectiveControl(c){if(!c)return null;if(!STATES.has(c.state))fail('invalid task control record');
  const expired=!!c.expires_at&&!(Date.parse(c.expires_at)>Date.now()),active=['claimed','running','cancel_requested','recovery_needed','missing_reply'].includes(c.state);
  const state=expired&&!TERMINAL.has(c.state)?active?'cancel_requested':'expired':c.state;return {...c,state,deadline_expired:expired&&!TERMINAL.has(c.state)||c.state==='expired',
    cancel_requested:state==='cancel_requested'||c.cancel_requested===true,terminal:TERMINAL.has(state),execution_stopped:c.execution_stopped===true||['cancelled','expired'].includes(c.state)||(state==='expired'&&!active),potential_partial:c.potential_partial===true||active||(['cancelled','expired'].includes(c.state)&&!!c.lease_expires_at),
    lease_expired:!!c.lease_expires_at&&Date.parse(c.lease_expires_at)<=Date.now()};}
function validatePatch(p){for(const k of Object.keys(p))if(!['state','reason','progress','claimed_session','claim_token','claim_fenced','execution_stopped','potential_partial','deadline_expired','prepared_reply','prepared_reply_hash','lease_expires_at','lease_seconds','outcome','reply_id','cancel_requested','expires_at','from','to','from_session','to_session','request_key','created','reply_schema','effort','timeout_seconds','heartbeat_at'].includes(k))fail(`unknown task control field ${k}`);
  if(p.state!=null&&!STATES.has(p.state))fail('bad task state');for(const k of ['reason','progress'])if(p[k]!=null)text(p[k],k);
  if(p.outcome!=null&&!['completed','declined','blocked','partial'].includes(p.outcome))fail('bad task outcome');if(p.reply_id!=null)idOf(p.reply_id);
  for(const k of ['expires_at','lease_expires_at','heartbeat_at'])if(p[k]!=null&&!Number.isFinite(Date.parse(p[k])))fail(`bad ${k}`);
  if(p.prepared_reply!=null){jsonInput(p.prepared_reply,'prepared_reply',524288);idOf(p.prepared_reply.id);if(p.prepared_reply.reply_to==null)fail('prepared reply needs an ask id');if(p.prepared_reply_hash!==hash(canonical(p.prepared_reply)))fail('prepared reply failed its integrity check');}
  if(hasSecret(canonical(p)))fail('task control looks like it contains a secret');}
export function updateControl(root,id,patch,options={}){idOf(id);validatePatch(patch);return withLock(root,'task:'+id,()=>{const previous=read(taskFile(root,id));
    if(Object.hasOwn(options,'expected_claim_token')&&(previous?.claim_token??null)!==options.expected_claim_token)fail('stale worker claim token; current task was not changed');
    // Terminal tasks never become runnable through a late provider event. A deliberate reclaim uses its separate API.
    const next={...(previous||{id,state:'queued',created:now()}),...patch,updated:now()};if(previous&&TERMINAL.has(previous.state)&&next.state!==previous.state)fail(`task is already ${previous.state}`);
    atomic(taskFile(root,id),next);return control(root,id);});}
export function initialize(root,m,{box='inbox'}={}){const file=taskFile(root,m.id);return withLock(root,'task:'+m.id,()=>{if(read(file))return control(root,m.id);
    const state=box==='done'?['cancelled','expired','declined'].includes(m.status)?m.status:m.kind==='reply'?'completed':'closed_without_reply':box==='claimed'?'claimed':'queued';
    const c={id:m.id,state,from:m.from,to:m.to,from_session:m.from_session||null,to_session:m.to_session||null,created:m.created,
      expires_at:m.expires_at||null,request_key:m.request_key||null,reply_schema:m.reply_schema||null,effort:m.effort||null,cancel_requested:false,updated:now(),
      ...(box==='claimed'?{claimed_session:m.claimed_session??null,claim_token:m.claim_token||null,claim_fenced:!!m.claim_fenced,lease_seconds:300,lease_expires_at:new Date((Date.parse(m.claimed_at)||Date.now())+300000).toISOString()}: {})};atomic(file,c);return c;});}
export function taskLock(root,id,fn){return withLock(root,'task:'+idOf(id),fn);}
// Internal helpers for a caller already holding taskLock; never nest the same task lock.
export const readControl=(root,id)=>read(taskFile(root,id));
export function saveControl(root,id,c){validatePatch(Object.fromEntries(Object.entries(c).filter(([k])=>!['id','updated'].includes(k))));atomic(taskFile(root,id),{...c,id,updated:now()});return control(root,id);}
const requestFile=(root,from,key)=>{if(!AGENTS.includes(from))fail('bad request sender');return path.join(rootDir(root),'requests',from,hash(requestKey(key))+'.json');};
export function getRequest(root,from,key){key=requestKey(key);const r=read(requestFile(root,from,key));if(r&&(r.from!==from||r.request_key!==key||!ID_RE.test(String(r.message?.id))||r.message.from!==from||r.message.request_key!==key))fail('invalid request-key record');
  if(r&&(r.fingerprint!==fingerprint(r.message)||r.content_hash!==hash(canonical(r.message))))fail('request-key journal content failed its integrity check; inspect it before recovery');return r;}
// Only semantic message content identifies the operation; generated ids/timestamps/session labels change across retries.
export function fingerprint(m){const copy={...m};for(const k of ['id','created','from_session','status','sig','sig_alg','sig_key','sig_expires','sig_version','expires_at'])delete copy[k];
  copy.body=String(copy.body||'').trim();if(copy.thread===m.id)copy.thread=null;return hash(canonical(copy));}
export function idempotent(root,from,key,message,publish,{beforePrepare=null}={}){key=requestKey(key);const file=requestFile(root,from,key),fp=fingerprint(message);
  return withLock(root,'request:'+from+':'+key,()=>{let record=getRequest(root,from,key),replayed=!!record;if(record&&record.fingerprint!==fp)fail('request_key conflict: content differs from the original request');
    if(!record){beforePrepare?.(message);record={v:1,from,request_key:key,fingerprint:fp,content_hash:hash(canonical(message)),state:'prepared',message};atomic(file,record);}
    const result=publish(record.message);if(record.state!=='delivered'){record.state='delivered';record.delivered=now();atomic(file,record);}return replayed?{...result,replayed:true}:result;});}

// Restricted, bounded JSON Schema: no refs, evaluation, external fetches, combinators, regexes or coercion.
const TYPES=new Set(['object','array','string','number','integer','boolean','null']);
const KEYS=new Set(['type','properties','required','additionalProperties','items','enum','minimum','maximum','minLength','maxLength','minItems','maxItems','description']);
export function schemaInput(value){const s=jsonInput(value,'reply_schema',8192);validateSchema(s,0);if(s.type!=='object')fail('reply_schema root must have type object');return s;}
function validateSchema(s,depth){if(depth>8||!s||typeof s!=='object'||Array.isArray(s))fail('reply_schema must be an object, depth at most 8');
  for(const k of Object.keys(s))if(!KEYS.has(k))fail(`unsupported reply_schema keyword ${k}`);if(!TYPES.has(s.type))fail('reply_schema needs a supported type');
  if(s.properties!==undefined){if(!s.properties||typeof s.properties!=='object'||Array.isArray(s.properties)||Object.keys(s.properties).length>100)fail('bad reply_schema properties');for(const sub of Object.values(s.properties))validateSchema(sub,depth+1);}
  if(s.required!==undefined&&(!Array.isArray(s.required)||s.required.some(k=>typeof k!=='string'||!Object.hasOwn(s.properties||{},k))))fail('reply_schema required fields must exist in properties');
  if(s.additionalProperties!==undefined&&typeof s.additionalProperties!=='boolean')fail('reply_schema additionalProperties must be boolean');
  if(s.items!==undefined)validateSchema(s.items,depth+1);if(s.enum!==undefined&&(!Array.isArray(s.enum)||!s.enum.length||s.enum.length>100))fail('bad reply_schema enum');
  for(const k of ['minimum','maximum','minLength','maxLength','minItems','maxItems'])if(s[k]!=null&&(!Number.isFinite(s[k])||(/Length|Items/.test(k)&&(!Number.isInteger(s[k])||s[k]<0))))fail(`bad reply_schema ${k}`);}
export function validateResult(value,schema,where='result'){const type=value===null?'null':Array.isArray(value)?'array':typeof value;
  if(schema.type==='integer'?!Number.isInteger(value):type!==schema.type)fail(`${where} must be ${schema.type}`);
  if(schema.enum&&!schema.enum.some(v=>canonical(v)===canonical(value)))fail(`${where} is not in the allowed enum`);
  if(type==='number'&&(!Number.isFinite(value)||(schema.minimum!=null&&value<schema.minimum)||(schema.maximum!=null&&value>schema.maximum)))fail(`${where} is outside the allowed range`);
  if(type==='string'&&((schema.minLength!=null&&value.length<schema.minLength)||(schema.maxLength!=null&&value.length>schema.maxLength)))fail(`${where} has invalid length`);
  if(type==='array'){if((schema.minItems!=null&&value.length<schema.minItems)||(schema.maxItems!=null&&value.length>schema.maxItems))fail(`${where} has invalid item count`);if(schema.items)value.forEach((v,i)=>validateResult(v,schema.items,`${where}[${i}]`));}
  if(type==='object'){for(const k of schema.required||[])if(!Object.hasOwn(value,k))fail(`${where}.${k} is required`);for(const [k,v]of Object.entries(value)){const sub=Object.hasOwn(schema.properties||{},k)?schema.properties[k]:null;if(sub)validateResult(v,sub,`${where}.${k}`);else if(schema.additionalProperties===false)fail(`${where}.${k} is not allowed`);}}return value;}
