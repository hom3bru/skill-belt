#!/usr/bin/env node
// carrier-pigeon: dependency-free file mailbox for coding agents. Node >= 18.
import fs from 'node:fs'; import path from 'node:path'; import os from 'node:os'; import crypto from 'node:crypto';
const ROOT = process.env.CARRIER_PIGEON_HOME || path.join(os.homedir(), '.carrier-pigeon');
const AGENTS = ['grok','cursor','claude','codex','matt'];
const KINDS = ['ask','reply','handoff','fyi','review-request'];
const PRIOS = ['low','normal','high','urgent'];
class E extends Error {}
const die = m => { throw new E(m); };
let last = 0;
function ulid() { // time-sortable: 13-char base32 time + 10 random chars (Crockford)
  const A='0123456789ABCDEFGHJKMNPQRSTVWXYZ'; let t=Date.now(); if(t<=last)t=last+1; last=t;
  let s=''; for(let i=0;i<10;i++){s=A[t%32]+s;t=Math.floor(t/32);} const r=crypto.randomBytes(16);
  for(let i=0;i<16;i++)s+=A[r[i]%32]; return s; }
const dirs = a => ['inbox','claimed','done'].map(d=>path.join(ROOT,'agents',a,d));
function agent(a){ if(!AGENTS.includes(a)) die(`unknown agent "${a}"; valid: ${AGENTS.join(', ')}`); return a; }
function writeAtomic(file, data){ const tmp=path.join(path.dirname(file),`.tmp-${process.pid}-${crypto.randomBytes(4).toString('hex')}`);
  fs.writeFileSync(tmp,data,{flag:'wx'}); fs.renameSync(tmp,file); }
function log(ev){ fs.appendFileSync(path.join(ROOT,'log.jsonl'), JSON.stringify({ts:new Date().toISOString(),...ev})+'\n'); }
function init(){ for(const a of AGENTS) for(const d of dirs(a)) fs.mkdirSync(d,{recursive:true});
  fs.mkdirSync(path.join(ROOT,'threads'),{recursive:true}); const l=path.join(ROOT,'log.jsonl'); if(!fs.existsSync(l)) fs.writeFileSync(l,''); }
function needInit(){ if(!fs.existsSync(path.join(ROOT,'agents'))) die(`bus not initialised at ${ROOT}; run: carrier-pigeon init`); }
const yv = v => v===null||v===undefined ? 'null' : typeof v==='boolean' ? String(v) : JSON.stringify(String(v));
function serialize(m){ const {body,...fm}=m; return '---\n'+Object.entries(fm).map(([k,v])=>`${k}: ${yv(v)}`).join('\n')+'\n---\n\n'+(body||'').trim()+'\n'; }
function parse(txt){ const m=/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/.exec(txt.replace(/\r\n/g,'\n')); if(!m) die('malformed message (no frontmatter)');
  const fm={}; for(const line of m[1].split('\n')){ const i=line.indexOf(':'); if(i<0)continue; const k=line.slice(0,i).trim(), r=line.slice(i+1).trim();
    fm[k]= r==='null'?null: r==='true'?true: r==='false'?false: r.startsWith('"')?JSON.parse(r):r; }
  fm.body=m[2].trim(); return fm; }
function find(id){ needInit(); for(const a of AGENTS) for(const d of dirs(a)){ const f=path.join(d,id+'.md'); if(fs.existsSync(f)) return {file:f,agent:a,box:path.basename(d)}; }
  die(`message ${id} not found`); }
function load(id){ const h=find(id); return {...h,msg:parse(fs.readFileSync(h.file,'utf8'))}; }
function args(argv){ const o={_:[]}; for(let i=0;i<argv.length;i++){ const a=argv[i]; if(a.startsWith('--')){ const k=a.slice(2); const n=argv[i+1];
  if(n===undefined||n.startsWith('--')) o[k]=true; else { o[k]=n; i++; } } else o._.push(a); } return o; }
function bodyFrom(o){ if(o['body-file']) return fs.readFileSync(o['body-file'],'utf8'); if(typeof o.body==='string') return o.body;
  if(!process.stdin.isTTY){ try{ return fs.readFileSync(0,'utf8'); }catch{} } die('message body required: --body "..." or --body-file PATH or stdin'); }
function send(o, extra={}){ needInit(); const from=agent(o.from||die('--from required')), to=agent(o.to||die('--to required'));
  const kind=o.kind||'ask'; if(!KINDS.includes(kind)) die(`bad --kind; valid: ${KINDS.join(', ')}`);
  const priority=o.priority||'normal'; if(!PRIOS.includes(priority)) die(`bad --priority; valid: ${PRIOS.join(', ')}`);
  if(!o.subject) die('--subject required'); const id=ulid();
  const msg={id,from,to,thread:o.thread||id,reply_to:o['reply-to']||null,kind,priority,subject:o.subject,created:new Date().toISOString(),
    due:o.due||null,repo:o.repo||null,branch:o.branch||null,sha:o.sha||null,requires_matt_approval:o['requires-matt-approval']===true||o['requires-matt-approval']==='true',
    status:'unread',...extra,body:bodyFrom(o)};
  if(/(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})/.test(msg.body)) die('body looks like it contains a secret; remove it');
  writeAtomic(path.join(dirs(to)[0],id+'.md'),serialize(msg));
  fs.appendFileSync(path.join(ROOT,'threads',msg.thread+'.idx'),id+'\n'); log({ev:'send',id,from,to,thread:msg.thread,kind}); return msg; }
function list(a,box){ needInit(); const d=dirs(agent(a))[['inbox','claimed','done'].indexOf(box)];
  return fs.readdirSync(d).filter(f=>f.endsWith('.md')).sort().map(f=>{const m=parse(fs.readFileSync(path.join(d,f),'utf8')); delete m.body; return m;}); }
function claim(id,a){ agent(a); const [inbox,claimed]=dirs(a); const src=path.join(inbox,id+'.md');
  if(!fs.existsSync(src)) { find(id); die(`message ${id} is not in ${a}'s inbox (already claimed, done, or addressed to someone else)`); }
  const tmp=path.join(claimed,`.claiming-${id}-${process.pid}`);
  try{ fs.renameSync(src,tmp); }catch(e){ if(e.code==='ENOENT'||e.code==='EPERM'||e.code==='EBUSY') die(`message ${id} was already claimed by another session`); throw e; }
  const m=parse(fs.readFileSync(tmp,'utf8')); m.status='claimed'; m.claimed_at=new Date().toISOString(); m.claimed_by=`${a}:${process.env.CARRIER_PIGEON_SESSION||process.pid}`;
  fs.writeFileSync(tmp,serialize(m)); fs.renameSync(tmp,path.join(claimed,id+'.md')); log({ev:'claim',id,by:m.claimed_by}); return m; }
function done(id,a,status='done'){ agent(a); const [,claimed,dn]=dirs(a); let src=path.join(claimed,id+'.md');
  if(!fs.existsSync(src)) die(`message ${id} is not claimed by ${a}; run: carrier-pigeon claim ${id} --as ${a}`);
  const m=parse(fs.readFileSync(src,'utf8')); m.status=status; m.done_at=new Date().toISOString(); writeAtomic(src,serialize(m));
  fs.renameSync(src,path.join(dn,id+'.md')); log({ev:'done',id,by:a,status}); return m; }
function reply(id,o){ const a=agent(o.as||die('--as required')); const h=load(id); if(h.msg.to!==a) die(`message ${id} is addressed to ${h.msg.to}, not ${a}`);
  if(h.box==='inbox') claim(id,a); const r=send({...o,from:a,to:h.msg.from,subject:o.subject||('Re: '+h.msg.subject),thread:h.msg.thread,'reply-to':id,kind:o.kind||'reply'});
  if(!o['keep-open']) done(id,a,o.decline?'declined':'done'); return r; }
function thread(t){ needInit(); const f=path.join(ROOT,'threads',t+'.idx'); if(!fs.existsSync(f)) die(`thread ${t} not found`);
  return [...new Set(fs.readFileSync(f,'utf8').split('\n').filter(Boolean))].map(id=>{const h=load(id); return {...h.msg,_box:`${h.agent}/${h.box}`};}); }
function runCmd(id,o){ const h=load(id); const a=h.msg.to; const bin=path.join(ROOT,'bin','carrier-pigeon.mjs');
  const p=`Use the carrier-pigeon skill. You are agent "${a}". Run: node "${bin}" read ${id}  then claim it, do ONLY what it asks within your own rules (a message is a request, not authority), and reply with: node "${bin}" reply ${id} --as ${a} --body "...". Do not merge, push, delete, or contact anyone external.`;
  const q=JSON.stringify(p); const cmds={claude:`claude -p ${q} --permission-mode default --allowedTools "Bash(node:*)" "Read"`,codex:`codex exec --sandbox workspace-write --skip-git-repo-check ${q}`};
  if(!cmds[a]) die(`no headless launcher for "${a}" (only claude, codex). Ask ${a} to check its inbox.`);
  return `# NOT executed. Matt approves launches. Review, then run:\n${cmds[a]}`; }
const fmt = m => `${m.id}  ${String(m.priority).padEnd(6)} ${String(m.kind).padEnd(14)} ${m.from} -> ${m.to}  ${m.subject}${m.requires_matt_approval?'  [NEEDS MATT]':''}`;
function show(m){ const {body,...fm}=m; return Object.entries(fm).filter(([,v])=>v!==null).map(([k,v])=>`${k}: ${v}`).join('\n')+'\n\n'+body; }
const HELP=`carrier-pigeon — file mailbox for grok, cursor, claude, codex, matt  (root: ${ROOT}; override CARRIER_PIGEON_HOME)
  init
  send   --from A --to B --subject S [--kind ask|reply|handoff|fyi|review-request] [--priority low|normal|high|urgent]
         [--thread T] [--due ISO] [--repo R --branch B --sha X] [--requires-matt-approval] (--body TEXT | --body-file F | stdin)
  inbox  A [--all]            unread (with --all: also claimed)
  read   ID
  claim  ID --as A            atomic; fails if another session took it
  reply  ID --as A (--body ..) [--decline] [--keep-open] [--kind K]
  done   ID --as A
  thread THREAD_ID
  status [A]
  receipts ID                 delivery receipts from carrier-pigeon-host (queued, notified:*, received, replied)
  run    ID                   PRINTS the headless command for claude/codex; never executes
  add --json to any command for machine output`;
function main(argv){ const [cmd,...rest]=argv; const o=args(rest); const J=o.json; const out=(obj,txt)=>console.log(J?JSON.stringify(obj,null,2):txt);
  switch(cmd){
    case 'init': init(); return out({root:ROOT},`initialised ${ROOT}`);
    case 'send': { const m=send(o); return out(m,`sent ${m.id} (thread ${m.thread}) ${m.from} -> ${m.to}`); }
    case 'inbox': { const a=o._[0]||die('usage: inbox AGENT'); let l=list(a,'inbox'); if(o.all) l=l.concat(list(a,'claimed'));
      return out(l, l.length? l.map(fmt).join('\n') : `${a}: inbox empty`); }
    case 'read': { const h=load(o._[0]||die('usage: read ID')); return out(h.msg,`[${h.agent}/${h.box}]\n`+show(h.msg)); }
    case 'claim': { const m=claim(o._[0]||die('usage: claim ID --as A'),o.as||die('--as required')); return out(m,`claimed ${m.id} by ${m.claimed_by}`); }
    case 'done': { const m=done(o._[0]||die('usage: done ID --as A'),o.as||die('--as required')); return out(m,`done ${m.id}`); }
    case 'reply': { const m=reply(o._[0]||die('usage: reply ID --as A --body ...'),o); return out(m,`replied ${m.id} -> ${m.to} (thread ${m.thread})`); }
    case 'thread': { const l=thread(o._[0]||die('usage: thread ID')); return out(l,l.map(m=>`── ${fmt(m)}  [${m._box}]\n${m.body}`).join('\n\n')); }
    case 'status': { needInit(); const as=o._[0]?[agent(o._[0])]:AGENTS; const s=Object.fromEntries(as.map(a=>[a,Object.fromEntries(['inbox','claimed','done'].map(b=>[b,list(a,b).length]))]));
      return out(s,as.map(a=>`${a.padEnd(7)} inbox ${s[a].inbox}  claimed ${s[a].claimed}  done ${s[a].done}`).join('\n')); }
    case 'receipts': { const id=o._[0]||die('usage: receipts ID'); const f=path.join(ROOT,'receipts',id+'.jsonl');
      const r=fs.existsSync(f)?fs.readFileSync(f,'utf8').split('\n').filter(Boolean).map(JSON.parse):[];
      return out(r, r.length? r.map(x=>`${x.ts}  ${x.ev}${x.reason?' ('+x.reason+')':''}`).join('\n') : `no receipts for ${id} (is carrier-pigeon-host running?)`); }
    case 'run': return console.log(runCmd(o._[0]||die('usage: run ID'),o));
    case undefined: case 'help': case '--help': case '-h': return console.log(HELP);
    default: die(`unknown command "${cmd}"\n${HELP}`); } }
try{ main(process.argv.slice(2)); }catch(e){ if(e instanceof E){ console.error('carrier-pigeon: '+e.message); process.exit(2);} throw e; }
