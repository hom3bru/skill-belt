// Read-only diagnostics shared by the CLI and MCP transport. No mailbox setup or process probes.
import fs from 'node:fs'; import path from 'node:path';

function installedVersion(root){
  try{
    const source=fs.readFileSync(path.join(root,'bin','cp-context.mjs'),'utf8');
    // Skip comments and quoted examples; accept a complete, plain string declaration without executing installed code.
    const declarations=/\/\/[^\r\n]*|\/\*[\s\S]*?(?:\*\/|$)|'(?:\\[\s\S]|[^'\\])*'|"(?:\\[\s\S]|[^"\\])*"|`(?:\\[\s\S]|[^`\\])*`|\bexport\s+const\s+VERSION\s*=\s*(['"])([^'"\\\r\n]+)\1[ \t]*(?:;|(?=\r?\n|$))/g;
    for(const match of source.matchAll(declarations)) if(match[2]?.trim()) return match[2];
  }catch{} // Missing, unreadable or malformed installed code is a diagnostic warning.
  return null;
}

export function diagnose({root,loadedVersion,agent=null,session=null,agents=[]}){
  // Identical to cp-context.isMailbox: use only init's two markers, without loading the installed module.
  const initialized=fs.existsSync(path.join(root,'log.jsonl'))&&fs.existsSync(path.join(root,'agents','matt','inbox'));
  const installed_version=installedVersion(root), needs_reconnect=installed_version!==null&&installed_version!==loadedVersion;
  // agentsStatus already checked the listener's liveness. Presence timestamps are state transitions, not heartbeats.
  const listener=agents.find(a=>Number.isInteger(a.listener_pid)&&a.listener_pid>0);
  const checks=[
    {code:'mailbox',status:initialized?'ok':'warning',message:initialized?`Mailbox is initialized at ${root}.`:`Mailbox is not initialized at ${root}.`,
      next_action:initialized?null:'Run carrier-pigeon init when you want to create this mailbox.'},
    {code:'version',status:installed_version!==null&&!needs_reconnect?'ok':'warning',
      message:installed_version===null?'Installed VERSION could not be read from bin/cp-context.mjs.':needs_reconnect?`Loaded version ${loadedVersion} differs from installed version ${installed_version}.`:`Loaded and installed versions match (${loadedVersion}).`,
      // Version labels are opaque; let callers choose the installed copy or their intended source.
      next_action:installed_version===null?'Check that the mailbox bin/cp-context.mjs is readable and declares VERSION as a quoted string.':needs_reconnect?
        `Use the installed CLI immediately for the whole task lifecycle: node "${path.join(root,'bin','carrier-pigeon.mjs')}" <command>. Or update the mailbox from the source version you intend to use: node "<intended-skill-folder>/bin/carrier-pigeon.mjs" install. If a running MCP client should use that installed version, reconnect it to refresh its loaded code. Standalone CLI calls need no reconnect.`:null},
    {code:'listener',status:listener?'ok':'warning',message:listener?`Listener is running (pid ${listener.listener_pid}).`:'No live listener is reported.',
      next_action:listener?null:'Check the listener status; start it manually if background delivery is needed.'},
    ...['claude','codex'].map(id=>{
      const reach=agents.find(a=>a.agent===id)?.reach, ready=reach==='auto-wake';
      return {code:`agent:${id}`,status:ready?'ok':'warning',message:ready?`${id} is ready for auto-wake.`:`${id} reach: ${reach||'not reported'}.`,
        next_action:ready?null:`Check listener readiness and the ${id} waking adapter; use inbox ${id} to pull messages meanwhile.`};
    })
  ];
  const health=!initialized?'uninitialized':checks.some(c=>c.status==='warning')?'attention':'ready';
  return {loaded_version:loadedVersion,installed_version,needs_reconnect,agent,session,root,agents,initialized,health,checks};
}
