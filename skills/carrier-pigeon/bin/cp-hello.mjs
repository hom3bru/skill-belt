// carrier-pigeon authority: Matt signs with a Windows Hello key. Pure Node plus Windows' own WinRT, through powershell.exe (5.1).
// The private key is created in the TPM and never leaves it; creating it and every signature need Matt's Windows Hello gesture (PIN, face,
// fingerprint) in Windows' own prompt, so an agent (or malware running as Matt) can ask for a signature but cannot produce one.
// Verifying needs no gesture: the public key is read from the same Windows Hello credential, never from a file an agent could replace.
import {spawnSync} from 'node:child_process'; import crypto from 'node:crypto';
export const KEY_NAME = 'carrier-pigeon-matt', SIG_ALG = 'win-hello-rsa-pkcs1-sha256';
const sha256 = b => crypto.createHash('sha256').update(b).digest('hex');
// One script for every operation; inputs arrive in environment variables, never as script text.
const SCRIPT = `$ErrorActionPreference='Stop'; try {
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation\`1' })[0]
function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }
[Windows.Security.Credentials.KeyCredentialManager, Windows.Security.Credentials, ContentType = WindowsRuntime] | Out-Null
[Windows.Security.Cryptography.Core.CryptographicPublicKeyBlobType, Windows.Security.Cryptography.Core, ContentType = WindowsRuntime] | Out-Null
$M = [Windows.Security.Credentials.KeyCredentialManager]; $RT = [Windows.Security.Credentials.KeyCredentialRetrievalResult]; $key = $env:CP_HELLO_KEY; $op = $env:CP_HELLO_OP
$b64 = { param($buf) [Convert]::ToBase64String([System.Runtime.InteropServices.WindowsRuntime.WindowsRuntimeBufferExtensions]::ToArray($buf)) }
$spki = { param($c) & $b64 $c.RetrievePublicKey([Windows.Security.Cryptography.Core.CryptographicPublicKeyBlobType]::X509SubjectPublicKeyInfo) }
$out = @{ op = $op }
if ($op -eq 'status') { $out.supported = Await ($M::IsSupportedAsync()) ([bool]); $out.key = [string](Await ($M::OpenAsync($key)) $RT).Status }
elseif ($op -eq 'pubkey') { $r = Await ($M::OpenAsync($key)) $RT; $out.status = [string]$r.Status; if ($r.Status -eq 'Success') { $out.spki = & $spki $r.Credential } }
elseif ($op -eq 'create') { $r = Await ($M::RequestCreateAsync($key, [Windows.Security.Credentials.KeyCredentialCreationOption]::FailIfExists)) $RT; $out.status = [string]$r.Status; if ($r.Status -eq 'Success') { $out.spki = & $spki $r.Credential } }
elseif ($op -eq 'sign') { $r = Await ($M::OpenAsync($key)) $RT; $out.status = [string]$r.Status
  if ($r.Status -eq 'Success') { $buf = [System.Runtime.InteropServices.WindowsRuntime.WindowsRuntimeBufferExtensions]::AsBuffer([Convert]::FromBase64String($env:CP_HELLO_DATA))
    $s = Await ($r.Credential.RequestSignAsync($buf)) ([Windows.Security.Credentials.KeyCredentialOperationResult]); $out.status = [string]$s.Status; if ($s.Status -eq 'Success') { $out.sig = & $b64 $s.Result } } }
$out | ConvertTo-Json -Compress } catch { @{ op = $env:CP_HELLO_OP; error = $_.Exception.Message } | ConvertTo-Json -Compress }`;
function hello(op, data = '') { if (process.platform !== 'win32') return {op, error: 'Windows Hello signing needs Windows'};
  const r = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-EncodedCommand', Buffer.from(SCRIPT, 'utf16le').toString('base64')],
    {encoding: 'utf8', timeout: op === 'create' || op === 'sign' ? 180000 : 60000, windowsHide: op !== 'create' && op !== 'sign', env: {...process.env, CP_HELLO_OP: op, CP_HELLO_KEY: KEY_NAME, CP_HELLO_DATA: data}});
  const line = String(r.stdout || '').trim().split(/\r?\n/).filter(Boolean).pop(); try { return JSON.parse(line); } catch { return {op, error: (r.error?.message || String(r.stderr || line || 'no output')).slice(0, 300)}; } }
export const fingerprint = spkiDer => sha256(spkiDer).slice(0, 16);
export const helloStatus = () => hello('status');
let cached; // one PowerShell round trip per process
export function helloPublicKey() { if (cached !== undefined) return cached; const r = hello('pubkey');
  if (r.status !== 'Success' || !r.spki) return (cached = null); const der = Buffer.from(r.spki, 'base64');
  return (cached = {key: crypto.createPublicKey({key: der, format: 'der', type: 'spki'}), fingerprint: fingerprint(der)}); }
export function helloCreate() { const r = hello('create'); if (r.status !== 'Success') return r; cached = undefined; return {...r, fingerprint: fingerprint(Buffer.from(r.spki, 'base64'))}; }
export function helloSign(bytes) { const r = hello('sign', Buffer.from(bytes).toString('base64'));
  if (r.status !== 'Success' || !r.sig) throw new Error(`Windows Hello did not sign (${r.error || r.status}); nothing was sent`); return Buffer.from(r.sig, 'base64'); }
// What a signature covers: this exact message (id, route, thread, subject, body and context hashes) until it expires.
export const authorityPayload = m => Buffer.from(JSON.stringify({v: 1, alg: SIG_ALG, id: m.id, from: m.from, to: m.to, to_session: m.to_session || null, thread: m.thread, reply_to: m.reply_to || null,
  kind: m.kind, subject: m.subject, created: m.created, expires: m.sig_expires, body_sha256: sha256(String(m.body ?? '').trim()), context_sha256: m.context ? sha256(m.context) : null}), 'utf8');
// status: verified | unsigned | invalid | expired | unverifiable (no Windows Hello key here) | n/a (not from matt). pub: {key, fingerprint} or null.
export function verifyAuthority(m, pub, now = Date.now()) { if (m.from !== 'matt') return {status: 'n/a'}; if (!m.sig) return {status: 'unsigned'};
  if (!pub) return {status: 'unverifiable', why: 'no Windows Hello key on this machine'}; if (m.sig_alg !== SIG_ALG || m.sig_key !== pub.fingerprint) return {status: 'invalid', why: 'signed with another key'};
  let ok = false; try { ok = crypto.verify('sha256', authorityPayload(m), {key: pub.key, padding: crypto.constants.RSA_PKCS1_PADDING}, Buffer.from(m.sig, 'base64')); } catch {}
  if (!ok) return {status: 'invalid', why: 'signature does not match this message'};
  if (!(Date.parse(m.sig_expires) > now)) return {status: 'expired', expires: m.sig_expires}; return {status: 'verified', expires: m.sig_expires, key: pub.fingerprint}; }
