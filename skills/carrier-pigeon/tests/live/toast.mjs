// Live check (opt-in; Windows only): PowerShell's own parser finds only the expected commands in the toast script, and a hostile
// subject (curly quotes plus a command) never appears in it. --show also fires one real toast through the adapter and checks it exits 0.
// Usage: node tests/live/toast.mjs [--show]
import path from 'node:path'; import fs from 'node:fs'; import os from 'node:os'; import {execFileSync} from 'node:child_process'; import {fileURLToPath} from 'node:url';
if (process.platform !== 'win32') { console.log(JSON.stringify({skipped: 'Windows only'})); process.exit(0); }
const SK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const h = await import(new URL('file:///' + path.join(SK, 'host', 'carrier-pigeon-host.mjs').replace(/\\/g, '/')).href);
const hostile = '</text></toast>’); Start-Process calc; $null=(‘'; const env = h.toastEnv({title: 't', text: hostile, launch: null}); const script = h.toastScript();
const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'cp-toast-')), 's.ps1'); fs.writeFileSync(f, script, 'utf8');
// decode as UTF-8 explicitly: the host hands the script over as UTF-16 (-EncodedCommand), so curly quotes arrive as real characters
const ps = `$t=$null;$e=$null;$s=[IO.File]::ReadAllText('${f}',[Text.Encoding]::UTF8);$a=[System.Management.Automation.Language.Parser]::ParseInput($s,[ref]$t,[ref]$e);`
  + `$a.FindAll({param($x) $x -is [System.Management.Automation.Language.CommandAst]},$true) | ForEach-Object { $_.GetCommandName() } | Sort-Object -Unique`;
const cmds = execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', ps], {encoding: 'utf8'}).trim().split(/\r?\n/).filter(Boolean); fs.rmSync(path.dirname(f), {recursive: true, force: true});
const report = {commands_in_script: cmds, text_in_script: script.includes('Start-Process') || script.includes('’'), text_in_env: env.CP_TOAST_TEXT === hostile};
if (process.argv.includes('--show')) { const ad = h.toastAdapter(); ad.start({cfg: {toast: {enabled: true}}}); report.toast_exit_ok = await ad.notify({title: 'carrier-pigeon live check', text: 'Toast path OK. Curly quote: it’s fine.', launch: null}); }
report.verdict = !report.text_in_script && !cmds.includes('Start-Process') && report.toast_exit_ok !== false ? 'pass' : 'FAIL';
console.log(JSON.stringify(report, null, 1)); process.exit(report.verdict === 'pass' ? 0 : 1);
