// No model calls: independently compare CLI and real-stdio MCP doctor against an installed disposable mailbox.
// node tests/live/doctor-parity.mjs [--skill SKILL_DIRECTORY] [--out REPORT_FILE]
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import assert from 'node:assert/strict';
import {spawn,spawnSync}from'node:child_process';import {fileURLToPath}from'node:url';
const arg=(name,fallback)=>{const i=process.argv.indexOf('--'+name);return i<0?fallback:process.argv[i+1];};
const skill=path.resolve(arg('skill',path.join(path.dirname(fileURLToPath(import.meta.url)),'../..')));
const parent=fs.mkdtempSync(path.join(os.tmpdir(),'cp-doctor-parity-')),root=path.join(parent,'mailbox'),env={...process.env,CARRIER_PIGEON_HOME:root};
const cli=(...a)=>{const r=spawnSync(process.execPath,[path.join(skill,'bin/carrier-pigeon.mjs'),...a],{env,encoding:'utf8',windowsHide:true,timeout:30000});assert.equal(r.status,0,String(r.stderr||r.error));return r.stdout;};
const json=(...a)=>JSON.parse(cli(...a,'--json'));
const snapshot=()=>{const result={};const walk=dir=>{for(const e of fs.readdirSync(dir,{withFileTypes:true})){const file=path.join(dir,e.name),stat=fs.statSync(file);result[path.relative(root,file)]={mtime:stat.mtimeMs,bytes:e.isFile()?fs.readFileSync(file).toString('base64'):null};if(e.isDirectory())walk(file);}};walk(root);return result;};
const cases=[];let child,report;
try{
 const missing=json('doctor','--as','codex','--session','parity');assert.equal(missing.health,'uninitialized');assert.equal(missing.initialized,false);assert.ok(!fs.existsSync(root));cases.push('missing mailbox diagnosed without initialization');
 json('install');
 fs.writeFileSync(path.join(root,'host/host.lock'),String(process.pid));
 fs.writeFileSync(path.join(root,'host/presence.json'),JSON.stringify({pid:process.pid,updated:'2000-01-01T00:00:00.000Z',routes:{claude:['claude'],codex:['codex']},adapters:{claude:{wakes:true,state:'ready'},codex:{wakes:true,state:'ready'}}}));
 const before=snapshot(),ready=json('doctor','--as','codex','--session','parity'),human=cli('doctor','--as','codex','--session','parity');
 assert.equal(ready.health,'ready');assert.equal(ready.needs_reconnect,false);assert.ok(/ready/i.test(human));assert.deepEqual(snapshot(),before);cases.push('JSON and human CLI report ready without writes; old presence timestamp remains valid');
 child=spawn(process.execPath,[path.join(skill,'bin/carrier-pigeon-mcp.mjs'),'--as','codex','--session','parity'],{env,windowsHide:true,stdio:['pipe','pipe','pipe']});
 let buffer='',seq=0;const pending=new Map();let stderr='';child.stderr.on('data',b=>stderr+=b);
 child.stdout.on('data',b=>{buffer+=b;let n;while((n=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,n);buffer=buffer.slice(n+1);if(!line.trim())continue;const msg=JSON.parse(line),entry=pending.get(msg.id);if(entry){pending.delete(msg.id);clearTimeout(entry.timer);msg.error?entry.reject(new Error(JSON.stringify(msg.error))):entry.resolve(msg.result);}}});
 const req=(method,params)=>new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(new Error('MCP parity timed out: '+method));},15000);pending.set(id,{resolve,reject,timer});child.stdin.write(JSON.stringify({jsonrpc:'2.0',id,method,params})+'\n');});
 await req('initialize',{protocolVersion:'2025-06-18',capabilities:{},clientInfo:{name:'doctor-parity',version:'1'}});
 const same=async()=>{const start=snapshot(),response=await req('tools/call',{name:'doctor',arguments:{}});assert.ok(!response.isError,JSON.stringify(response.content));const value=response.structuredContent||JSON.parse(response.content[0].text);assert.deepEqual(snapshot(),start,'doctor operation does not change files (after MCP session registration)');assert.deepEqual(value,json('doctor','--as','codex','--session','parity'));return value;};
 assert.equal((await same()).health,'ready');cases.push('CLI and bound MCP reports match exactly; MCP doctor itself does not write');
 const versionFile=path.join(root,'bin/cp-context.mjs');fs.writeFileSync(versionFile,"export const VERSION = 'parity-old-version';\n");const mismatch=await same();assert.equal(mismatch.needs_reconnect,true);assert.equal(mismatch.health,'attention');cases.push('loaded/installed version mismatch is consistent on both interfaces');
 fs.writeFileSync(versionFile,'this is not a VERSION declaration\n');const malformed=await same();assert.equal(malformed.installed_version,null);assert.equal(malformed.needs_reconnect,false);assert.equal(malformed.health,'attention');cases.push('malformed installed version produces an actionable report without importing it');
 fs.unlinkSync(versionFile);assert.equal((await same()).installed_version,null);cases.push('missing installed version stays nonfatal and read-only');
 child.stdin.end();await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('MCP did not close: '+stderr)),10000);child.once('close',code=>{clearTimeout(timer);code===0?resolve():reject(new Error('MCP exit '+code+': '+stderr));});});child=null;
 assert.ok(!fs.existsSync(path.join(root,'sessions/codex~parity.json')));report={passed:true,cases,root,skill};
}catch(error){report={passed:false,cases,root,skill,error:String(error.stack||error)};process.exitCode=1;}
finally{child?.kill();const output=JSON.stringify(report,null,2)+'\n';if(arg('out'))fs.writeFileSync(arg('out'),output);console.log(output);}
