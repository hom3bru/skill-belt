// node cp-hello.test.mjs — user's signed authority, with a software RSA key standing in for Windows Hello. Never calls the real signer (that would
// raise a Windows Hello prompt); a temp CARRIER_PIGEON_HOME is set before the library is loaded, so nothing touches the real mailbox.
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import crypto from 'node:crypto'; import assert from 'node:assert/strict'; import {execFileSync} from 'node:child_process';
const HOME = fs.mkdtempSync(path.join(os.tmpdir(), 'cphello-')); process.env.CARRIER_PIGEON_HOME = HOME;
const cp = await import('./carrier-pigeon.mjs'); const hello = await import('./cp-hello.mjs'); cp.init();
let n = 0, failed = 0; const t = async (name, fn) => { n++; try { await fn(); console.log('ok', n, name); } catch (e) { failed++; console.log('not ok', n, name); console.log('  ' + String(e?.stack || e).split('\n').slice(0, 6).join('\n  ')); } };
const keyPair = () => { const {publicKey, privateKey} = crypto.generateKeyPairSync('rsa', {modulusLength: 2048}); const der = publicKey.export({type: 'spki', format: 'der'});
  return {pub: {key: publicKey, fingerprint: hello.fingerprint(der)}, sign: b => crypto.sign('sha256', b, {key: privateKey, padding: crypto.constants.RSA_PKCS1_PADDING})}; };
const user = keyPair(), mallory = keyPair();
const signed = (o = {}, signer = user) => { const m = cp.build({from: 'user', to: 'codex', subject: 'approve deploy', body: '  ship release 4 to staging \n', _noStdin: true, ...o}); cp.signAsHuman(m, o, signer); cp.write(m); return cp.load(m.id).msg; };

await t('a message user signs verifies after a round trip through its file', () => { const m = signed({'expires-min': 5});
  const v = hello.verifyAuthority(m, user.pub); assert.equal(v.status, 'verified'); assert.equal(v.key, user.pub.fingerprint); assert.equal(m.sig_alg, hello.SIG_ALG); assert.ok(Date.parse(m.sig_expires) > Date.now()); });
await t('any change to the signed message breaks it: body, recipient, subject, session, thread', () => { const m = signed();
  for (const [k, v] of [['body', 'ship everything to production'], ['to', 'claude'], ['subject', 'approve all'], ['to_session', 'claude-x'], ['thread', 'OTHER']])
    assert.equal(hello.verifyAuthority({...m, [k]: v}, user.pub).status, 'invalid', k); });
await t('another key, a forged signature, expiry, no signature, no key here, not from user', () => { const m = signed();
  assert.equal(hello.verifyAuthority(m, mallory.pub).status, 'invalid', 'checked against another key');
  const forged = signed({}, {pub: user.pub, sign: mallory.sign}); assert.equal(hello.verifyAuthority(forged, user.pub).status, 'invalid', "an agent's own key under user's fingerprint");
  assert.equal(hello.verifyAuthority(m, user.pub, Date.parse(m.sig_expires) + 1).status, 'expired');
  const plain = cp.load(cp.send({from: 'user', to: 'codex', subject: 's', body: 'b', _noStdin: true}).id).msg; assert.equal(hello.verifyAuthority(plain, user.pub).status, 'unsigned');
  assert.equal(hello.verifyAuthority(m, null).status, 'unverifiable'); assert.equal(hello.verifyAuthority({...m, from: 'codex'}, user.pub).status, 'n/a'); });
await t('--sign is refused for any sender but user, before Windows Hello is touched', () => {
  assert.throws(() => cp.signAsHuman(cp.build({from: 'codex', to: 'claude', subject: 's', body: 'b', _noStdin: true}), {}, user), /only for messages from user/);
  assert.throws(() => cp.signAsHuman(cp.build({from: 'user', to: 'codex', subject: 's', body: 'b', _noStdin: true}), {'expires-min': 0}, user), /--expires-min/); });
await t('read never reports verified for a signature from a software key (it checks this machine\'s Windows Hello key)', () => { const m = signed();
  const r = JSON.parse(execFileSync('node', [path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')), 'carrier-pigeon.mjs'), 'read', m.id, '--json'], {env: process.env, encoding: 'utf8'}));
  assert.notEqual(r.authority.status, 'verified'); assert.ok(['unverifiable', 'invalid'].includes(r.authority.status), r.authority.status); });
await t('version 2 signatures bind task controls, structured results, sender session and handoff references', () => {
  const m=cp.build({from:'user',to:'codex',subject:'signed task',body:'review only',_noStdin:true});
  Object.assign(m,{sig_version:2,from_session:'human-terminal',request_key:'signed-review',timeout_seconds:60,effort:'low',expires_at:'2030-01-01T00:00:00Z',reply_schema:'{"type":"object"}',transcript:'a'.repeat(64),sig_alg:hello.SIG_ALG,sig_key:user.pub.fingerprint,sig_expires:new Date(Date.now()+60000).toISOString()});
  m.sig=user.sign(hello.authorityPayload(m)).toString('base64'); cp.write(m); const stored=cp.load(m.id).msg;
  assert.equal(hello.verifyAuthority(stored,user.pub).status,'verified');
  for(const [key,value] of [['from_session','other-session'],['request_key','other-review'],['timeout_seconds','120'],['effort','high'],['expires_at','2031-01-01T00:00:00Z'],['reply_schema','{"type":"string"}'],['transcript','b'.repeat(64)],['outcome','completed'],['result','{"accepted":true}'],['evidence','["invented"]']])
    assert.equal(hello.verifyAuthority({...stored,[key]:value},user.pub).status,'invalid',key);
});
await t('legacy signatures remain valid without new controls and cannot authenticate appended task controls', () => {
  const m=cp.build({from:'user',to:'codex',subject:'legacy task',body:'review only',_noStdin:true});
  Object.assign(m,{sig_alg:hello.SIG_ALG,sig_key:user.pub.fingerprint,sig_expires:new Date(Date.now()+60000).toISOString()});
  m.sig=user.sign(hello.authorityPayload(m)).toString('base64');
  assert.equal(hello.verifyAuthority(m,user.pub).status,'verified');
  for(const [key,value] of [['effort','high'],['transcript','a'.repeat(64)],['fork_codex_thread','codex-thread-example'],['fork_claude_session','0f8fad5b-d9cb-469f-a165-70867728950e'],['from_session','other-session'],['wake_on_reply',true]])
    assert.equal(hello.verifyAuthority({...m,[key]:value},user.pub).status,'invalid',key);
  assert.equal(hello.verifyAuthority({...m,sig_version:9},user.pub).status,'invalid');
});
fs.rmSync(HOME, {recursive: true, force: true}); console.log(`# ${n} tests, ${failed} failed (hello)`); process.exit(failed ? 1 : 0);
