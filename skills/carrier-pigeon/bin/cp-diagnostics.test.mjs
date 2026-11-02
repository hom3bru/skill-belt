// node bin/cp-diagnostics.test.mjs — disposable local fixtures and caller-supplied agentsStatus snapshots only.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import assert from 'node:assert/strict';
import {diagnose} from './cp-diagnostics.mjs';

const HOME=fs.mkdtempSync(path.join(os.tmpdir(),'cpdiagnostics-')), VERSION='1.2.3';
let fixtures=0, n=0, failed=0;
const t=async(name,fn)=>{ n++; try{ await fn(); console.log('ok',n,name); }catch(e){ failed++; console.log('not ok',n,name); console.log('  '+String(e?.stack||e).split('\n').slice(0,6).join('\n  ')); } };
function fixture({initialized=true,source=`export const VERSION = '${VERSION}';\n`}={}){
  const root=path.join(HOME,String(++fixtures)), file=path.join(root,'bin','cp-context.mjs');
  fs.mkdirSync(root);
  if(initialized){ fs.writeFileSync(path.join(root,'log.jsonl'),''); fs.mkdirSync(path.join(root,'agents','matt','inbox'),{recursive:true}); }
  if(source!==null){ fs.mkdirSync(path.dirname(file),{recursive:true}); fs.writeFileSync(file,source); }
  return {root,file};
}
const ready=()=>['claude','codex'].map(agent=>({agent,reach:'auto-wake',listener_pid:123456789,adapters:[{adapter:agent,state:'ready',wakes:true}],sessions:[]}));
const run=(root,agents=ready(),extra={})=>diagnose({root,loadedVersion:VERSION,agents,...extra});
const check=(result,code)=>{ const found=result.checks.find(c=>c.code===code); assert.ok(found,code); return found; };
function warningsAreActionable(result){
  for(const c of result.checks){
    assert.deepEqual(Object.keys(c).sort(),['code','message','next_action','status']);
    assert.equal(typeof c.message,'string'); assert.ok(c.message.length);
    assert.ok(['ok','warning'].includes(c.status));
    if(c.status==='warning'){ assert.equal(typeof c.next_action,'string'); assert.ok(c.next_action.trim().length); }
    else assert.equal(c.next_action,null);
  }
}
function versionActionsAreUseful(result){
  const action=check(result,'version').next_action;
  assert.match(action,/use the installed CLI immediately/i);
  assert.ok(action.includes(`node "${path.join(result.root,'bin','carrier-pigeon.mjs')}" <command>`),'give the installed CLI command with its path quoted');
  assert.match(action,/whole task lifecycle/i);
  assert.match(action,/update the mailbox from the source version you intend to use/i);
  assert.match(action,/node "<intended-skill-folder>\/bin\/carrier-pigeon\.mjs" install/);
  assert.match(action,/if a running MCP client should use that installed version, reconnect it/i);
  assert.match(action,/standalone CLI calls need no reconnect/i);
}
function snapshot(root){
  if(!fs.existsSync(root)) return null;
  const entries=[];
  const visit=dir=>{ for(const name of fs.readdirSync(dir).sort()){
    const file=path.join(dir,name), info=fs.statSync(file), relative=path.relative(root,file);
    entries.push({file:relative,mtime:info.mtimeMs,mode:info.mode,bytes:info.isFile()?fs.readFileSync(file).toString('base64'):null});
    if(info.isDirectory()) visit(file);
  } };
  visit(root); return entries;
}

await t('a missing root stays absent and defaults identity, session and agent snapshot',()=>{
  const root=path.join(HOME,'absent'), before=snapshot(HOME), result=diagnose({root,loadedVersion:VERSION});
  assert.equal(result.root,root); assert.equal(result.loaded_version,VERSION); assert.equal(result.agent,null); assert.equal(result.session,null); assert.deepEqual(result.agents,[]);
  assert.equal(result.initialized,false); assert.equal(result.health,'uninitialized'); assert.equal(result.installed_version,null); assert.equal(result.needs_reconnect,false);
  assert.deepEqual(result.checks.map(c=>c.code),['mailbox','version','listener','agent:claude','agent:codex']);
  assert.ok(result.checks.every(c=>c.status==='warning')); warningsAreActionable(result);
  assert.equal(fs.existsSync(root),false); assert.deepEqual(snapshot(HOME),before);
});
await t('initialization requires both existing mailbox markers and takes health priority',()=>{
  for(const missing of ['log.jsonl',path.join('agents','matt','inbox')]){
    const {root}=fixture(); fs.rmSync(path.join(root,missing),{recursive:true});
    const result=run(root);
    assert.equal(result.initialized,false); assert.equal(result.health,'uninitialized'); assert.equal(check(result,'mailbox').status,'warning');
    assert.ok(result.checks.filter(c=>c.code!=='mailbox').every(c=>c.status==='ok')); warningsAreActionable(result);
  }
});
await t('an installed module alone does not initialize a mailbox',()=>{
  const {root}=fixture({initialized:false}), result=run(root);
  assert.equal(result.initialized,false); assert.equal(result.health,'uninitialized'); assert.equal(result.installed_version,VERSION);
  assert.equal(fs.existsSync(path.join(root,'log.jsonl')),false); assert.equal(fs.existsSync(path.join(root,'agents')),false);
});
await t('matching versions, live listener snapshot and auto-wake agents produce ready health and full result shape',()=>{
  const {root}=fixture(), agents=ready(), result=run(root,agents);
  assert.deepEqual(result,{loaded_version:VERSION,installed_version:VERSION,needs_reconnect:false,agent:null,session:null,root,agents,initialized:true,health:'ready',checks:result.checks});
  assert.ok(result.checks.every(c=>c.status==='ok')); warningsAreActionable(result);
});
await t('caller identity and session are preserved without rebinding',()=>{
  const {root}=fixture(), result=run(root,ready(),{agent:'codex',session:'interactive-core'});
  assert.equal(result.agent,'codex'); assert.equal(result.session,'interactive-core'); assert.equal(result.root,root);
});
await t('an old loaded version preserves reconnect semantics and offers CLI, install and conditional MCP actions',()=>{
  const {root}=fixture(), result=run(root,ready(),{loadedVersion:'1.2.2'});
  assert.equal(result.loaded_version,'1.2.2'); assert.equal(result.installed_version,VERSION); assert.equal(result.needs_reconnect,true); assert.equal(result.health,'attention');
  assert.equal(check(result,'version').status,'warning'); versionActionsAreUseful(result); warningsAreActionable(result);
});
await t('a newer loaded version preserves reconnect semantics and offers intended-source installation',()=>{
  const {root}=fixture({source:"export const VERSION = '1.2.2';\n"}), result=run(root);
  assert.equal(result.installed_version,'1.2.2'); assert.equal(result.needs_reconnect,true); assert.equal(result.health,'attention');
  versionActionsAreUseful(result); warningsAreActionable(result);
});
await t('opaque version labels offer both choices to CLI and MCP callers without inferring version order',()=>{
  for(const [loadedVersion,installedVersion] of [['source-main','release-stable'],['release-stable','source-main']]){
    const {root}=fixture({source:`export const VERSION = '${installedVersion}';\n`}), spacedRoot=root+' mailbox with spaces';
    fs.renameSync(root,spacedRoot);
    for(const identity of [{},{agent:'codex',session:'running-mcp'}]){
      const result=run(spacedRoot,ready(),{loadedVersion,...identity});
      assert.equal(result.loaded_version,loadedVersion); assert.equal(result.installed_version,installedVersion);
      assert.equal(result.agent,identity.agent??null); assert.equal(result.session,identity.session??null);
      assert.equal(result.needs_reconnect,true); assert.equal(result.health,'attention');
      versionActionsAreUseful(result); warningsAreActionable(result);
    }
  }
});
await t('a missing installed file is a warning without a reconnect claim or crash',()=>{
  const {root}=fixture({source:null}), result=run(root);
  assert.equal(result.initialized,true); assert.equal(result.installed_version,null); assert.equal(result.needs_reconnect,false); assert.equal(result.health,'attention');
  assert.equal(check(result,'version').status,'warning'); warningsAreActionable(result);
});
await t('an unreadable installed file is a warning without a reconnect claim or crash',()=>{
  const {root,file}=fixture(), read=fs.readFileSync;
  // A deterministic EACCES fixture works on Windows too, where chmod does not deny reads.
  fs.readFileSync=(name,...args)=>{ if(name===file) throw Object.assign(new Error('fixture access denied'),{code:'EACCES'}); return read(name,...args); };
  let result; try{ result=run(root); }finally{ fs.readFileSync=read; }
  assert.equal(result.installed_version,null); assert.equal(result.needs_reconnect,false); assert.equal(result.health,'attention'); warningsAreActionable(result);
});
await t('a directory at the installed file path is diagnosed without crashing',()=>{
  const {root,file}=fixture({source:null}); fs.mkdirSync(file,{recursive:true}); const result=run(root);
  assert.equal(result.installed_version,null); assert.equal(result.needs_reconnect,false); assert.equal(check(result,'version').status,'warning');
});
await t('absent, empty, malformed and computed VERSION declarations are not installed versions',()=>{
  for(const source of ['',"export const OTHER = '1.2.3';\n","export const VERSION = '';\n","export const VERSION = '   ';\n",
    "export const VERSION = '1.2.3;\n",'export const VERSION = \'1.2.3";\n',"export const VERSION = '1.2.3' + '-dev';\n",
    "export const VERSION = getVersion();\n","export const VERSION = `1.2.3`;\n"]){
    const {root}=fixture({source}), result=run(root);
    assert.equal(result.installed_version,null,source); assert.equal(result.needs_reconnect,false,source); assert.equal(result.health,'attention',source); warningsAreActionable(result);
  }
});
await t('plain single and double quoted declarations accept whitespace and prerelease versions',()=>{
  for(const source of ["export const VERSION = '1.2.3-beta.1+fixture';\n",'  export\tconst VERSION\t=\t"1.2.3-beta.1+fixture"; // installed\r\n',
    'export const VERSION = "1.2.3-beta.1+fixture"\n']){
    const {root}=fixture({source}), result=run(root,ready(),{loadedVersion:'1.2.3-beta.1+fixture'});
    assert.equal(result.installed_version,'1.2.3-beta.1+fixture'); assert.equal(result.needs_reconnect,false); assert.equal(result.health,'ready');
  }
});
await t('commented declarations and quoted examples cannot supply an installed version',()=>{
  for(const source of ["// export const VERSION = 'decoy';\n","/* example\nexport const VERSION = 'decoy';\n*/\n",
    "const example = `\nexport const VERSION = 'decoy';\n`;\n"]){
    const {root}=fixture({source}), result=run(root); assert.equal(result.installed_version,null); assert.equal(check(result,'version').status,'warning');
  }
  const {root}=fixture({source:"/* export const VERSION = 'decoy'; */\nexport const VERSION = '1.2.3';\n"});
  assert.equal(run(root).installed_version,VERSION);
});
await t('installed source is read passively even if importing it would throw or write',()=>{
  const marker=path.join(HOME,'executed'), {root}=fixture({source:`export const VERSION = '${VERSION}';\nimport fs from 'node:fs';\nfs.writeFileSync(${JSON.stringify(marker)},'executed');\nthrow new Error('must not execute');\n`});
  assert.equal(run(root).health,'ready'); assert.equal(fs.existsSync(marker),false);
});
await t('listener readiness accepts a positive validated pid anywhere in the snapshot',()=>{
  const {root}=fixture(), agents=ready().map(a=>({...a,listener_pid:null})); agents.push({agent:'grok',reach:'pull',listener_pid:123456789});
  const result=run(root,agents); assert.equal(check(result,'listener').status,'ok'); assert.equal(result.health,'ready');
});
await t('missing, zero, negative and nonnumeric listener pids require attention',()=>{
  const {root}=fixture();
  for(const listener_pid of [undefined,null,0,-1,'123',NaN,Infinity]){
    const result=run(root,ready().map(a=>({...a,listener_pid})));
    assert.equal(check(result,'listener').status,'warning',String(listener_pid)); assert.equal(result.health,'attention'); warningsAreActionable(result);
    assert.equal(check(result,'agent:claude').status,'ok'); assert.equal(check(result,'agent:codex').status,'ok');
  }
});
for(const agent of ['claude','codex']) await t(`${agent} is ready only for exact auto-wake reach`,()=>{
  const {root}=fixture();
  for(const reach of ['pull','notify-only','auto-wake (not ready)','auto-wake ','AUTO-WAKE','',undefined]){
    const result=run(root,ready().map(a=>a.agent===agent?{...a,reach}:a));
    assert.equal(check(result,`agent:${agent}`).status,'warning',String(reach)); assert.equal(result.health,'attention'); warningsAreActionable(result);
    assert.equal(check(result,`agent:${agent==='claude'?'codex':'claude'}`).status,'ok');
  }
});
await t('an absent agent is warned even when another agent has a ready listener',()=>{
  const {root}=fixture(), result=run(root,ready().filter(a=>a.agent==='claude'));
  assert.equal(check(result,'agent:claude').status,'ok'); assert.equal(check(result,'agent:codex').status,'warning'); assert.equal(result.health,'attention'); warningsAreActionable(result);
});
await t('unrelated pull agents do not prevent ready health',()=>{
  const {root}=fixture(), result=run(root,[{agent:'matt',reach:'pull',listener_pid:null},...ready(),{agent:'grok',reach:'pull',listener_pid:null}]);
  assert.equal(result.health,'ready'); assert.equal(result.checks.length,5);
});
await t('the supplied snapshot and nested adapter/session objects are returned without mutation',()=>{
  const {root}=fixture(), agents=ready(); agents[0].sessions.push({session:'old-session',last_seen:'2000-01-01T00:00:00Z'});
  const before=JSON.stringify(agents), freeze=o=>{ for(const v of Object.values(o)) if(v&&typeof v==='object') freeze(v); return Object.freeze(o); }; freeze(agents);
  const result=run(root,agents); assert.strictEqual(result.agents,agents); assert.equal(JSON.stringify(agents),before); assert.equal(result.health,'ready');
});
await t('stale presence files and timestamps do not override the validated snapshot or trigger process probes',()=>{
  const {root}=fixture(); fs.mkdirSync(path.join(root,'host')); const presence=path.join(root,'host','presence.json');
  fs.writeFileSync(presence,'{"updated":"2000-01-01T00:00:00Z","adapters":{}}'); fs.utimesSync(presence,new Date(0),new Date(0));
  const kill=process.kill; process.kill=()=>assert.fail('diagnostics must not re-probe listener liveness');
  try{ assert.equal(run(root).health,'ready'); }finally{ process.kill=kill; }
});
await t('diagnosis reads no config, secrets or mailbox data and leaves all files and directories unchanged',()=>{
  const {root,file}=fixture();
  for(const [name,body] of [['host/config.json','{"fixture":true}'],['host/secrets/fixture.txt','private fixture'],['host/presence.json','not json'],['agents/codex/inbox/fixture.md','message fixture']]){
    const target=path.join(root,name); fs.mkdirSync(path.dirname(target),{recursive:true}); fs.writeFileSync(target,body);
  }
  const before=snapshot(root), read=fs.readFileSync, reads=[];
  fs.readFileSync=(name,...args)=>{ reads.push(name); assert.equal(name,file,'only installed VERSION source may be read'); return read(name,...args); };
  let healthy, warning;
  try{ healthy=run(root); warning=run(root,[]); }finally{ fs.readFileSync=read; }
  assert.equal(healthy.health,'ready'); assert.equal(warning.health,'attention'); assert.deepEqual(reads,[file,file]);
  assert.deepEqual(snapshot(root),before); warningsAreActionable(warning);
});

fs.rmSync(HOME,{recursive:true,force:true}); console.log(`# ${n} tests, ${failed} failed (diagnostics)`); process.exit(failed?1:0);
