// Offline native-ownership fixtures. No credentials, native calls or mailbox claims.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
import {resolveRemoteMailboxSession as resolve} from './cp-claude-remote-identity.mjs';

let count = 0, failed = 0;
const test = (name, fn) => {
  count++;
  try { fn(); console.log('ok', count, name); }
  catch (error) {
    failed++; console.log('not ok', count, name);
    console.log(String(error.stack).split('\n').slice(0, 5).join('\n'));
  }
};

function fixture(fn) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-remote-identity-'));
  const root = path.join(temp, 'mail'), registryDir = path.join(temp, 'sessions'), environmentId = 'env_Fixture123';
  const bindingDir = path.join(root, 'host', 'claude-remote-threads', environmentId);
  fs.mkdirSync(bindingDir, {recursive: true}); fs.mkdirSync(registryDir);
  const nativeId = randomUUID(), alias = 'claude-desktop-' + environmentId;
  const message = {id: '01M60000000000000000000001', thread: 'release.1', to: 'claude', to_session: alias};
  const binding = {environmentId, thread: message.thread, remoteSessionId: 'cse_FixtureBridge123'};
  const record = {pid: process.pid, sessionId: nativeId, entrypoint: 'claude-desktop', hostSessionId: 'local_' + randomUUID(), bridgeSessionId: 'session_FixtureBridge123'};
  const bindingFile = path.join(bindingDir, message.thread + '.json'), recordFile = path.join(registryDir, process.pid + '.json');
  const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value));
  write(bindingFile, binding); write(recordFile, record);
  const options = {root, registryDir, message, env: {CLAUDE_CODE_SESSION_ID: nativeId}, parentPid: process.pid};
  try { return fn({temp, root, registryDir, environmentId, alias, message, binding, record, bindingFile, recordFile, write, options}); }
  finally { fs.rmSync(temp, {recursive: true, force: true}); }
}

test('owned live Desktop child resolves cse/session suffixes without reading keys', () => fixture(f => {
  fs.writeFileSync(path.join(f.registryDir, process.pid + '.key'), 'not JSON; never read');
  assert.equal(resolve(f.options), f.alias);
  f.write(f.bindingFile, {...f.binding, remoteSessionId: f.record.bridgeSessionId});
  assert.equal(resolve(f.options), f.alias);
}));
test('default registry uses CLAUDE_CONFIG_DIR/sessions', () => fixture(f => {
  const {registryDir, ...options} = f.options;
  assert.equal(resolve({...options, env: {...options.env, CLAUDE_CONFIG_DIR: f.temp}}), f.alias);
}));
test('requires strict native UUID and positive integer parent PID', () => fixture(f => {
  for (const options of [null, undefined, {}, {...f.options, env: null}]) assert.equal(resolve(options), null);
  for (const sid of [undefined, '', 'native-fixture', f.record.sessionId + '\n']) assert.equal(resolve({...f.options, env: {CLAUDE_CODE_SESSION_ID: sid}}), null);
  for (const parentPid of [0, -1, '1', 1.5, process.pid + 1]) assert.equal(resolve({...f.options, parentPid}), null);
}));
test('rejects other recipients, target environments and unsafe message identifiers', () => fixture(f => {
  for (const patch of [{to: 'codex'}, {to_session: 'claude-desktop-env_Other'}, {to_session: 'native-chat'}, {id: 'bad'}, {id: {}}, {thread: '../escape'}, {thread: 'a;command'}, {thread: ''}])
    assert.equal(resolve({...f.options, message: {...f.message, ...patch}}), null);
}));
test('binding must match thread and environment and have a strict bridge identifier', () => fixture(f => {
  for (const patch of [{environmentId: 'env_Other'}, {thread: 'other'}, {remoteSessionId: 'cse_'}, {remoteSessionId: 'session_x/events'}, {remoteSessionId: 'cse_FixtureBridge123\n'}]) {
    f.write(f.bindingFile, {...f.binding, ...patch}); assert.equal(resolve(f.options), null);
  }
}));
test('registry must match native ID, filename PID, desktop entrypoint, local host and bridge', () => fixture(f => {
  for (const patch of [{sessionId: randomUUID()}, {pid: process.pid + 1}, {entrypoint: 'cli'}, {hostSessionId: 'remote_' + randomUUID()}, {hostSessionId: 'local_bad'}, {hostSessionId: f.record.hostSessionId + '\n'}, {bridgeSessionId: 'session_Other'}, {bridgeSessionId: 'session_FixtureBridge123\n'}]) {
    f.write(f.recordFile, {...f.record, ...patch}); assert.equal(resolve(f.options), null);
  }
}));
test('dead native process cannot establish ownership', () => fixture(f => {
  const child = spawnSync(process.execPath, ['-e', ''], {windowsHide: true});
  assert.equal(child.status, 0); assert.ok(child.pid > 0);
  fs.unlinkSync(f.recordFile); f.write(path.join(f.registryDir, child.pid + '.json'), {...f.record, pid: child.pid});
  assert.equal(resolve({...f.options, parentPid: child.pid}), null);
}));
test('two live native-ID records fail closed even when only one is the parent', () => fixture(f => {
  assert.notEqual(process.pid, process.ppid);
  f.write(path.join(f.registryDir, process.ppid + '.json'), {...f.record, pid: process.ppid});
  assert.equal(resolve(f.options), null);
}));
test('an unrelated live Desktop chat cannot supply or block this routing identity', () => fixture(f => {
  f.write(path.join(f.registryDir, process.ppid + '.json'), {...f.record, pid: process.ppid, sessionId: randomUUID()});
  assert.equal(resolve(f.options), f.alias);
  fs.unlinkSync(f.recordFile);
  assert.equal(resolve(f.options), null);
}));
test('missing, malformed, nonobject and oversized files fail closed', () => fixture(f => {
  for (const file of [f.bindingFile, f.recordFile]) {
    for (const raw of ['{', '[]', 'null', ' '.repeat(65537)]) { fs.writeFileSync(file, raw); assert.equal(resolve(f.options), null); }
    fs.unlinkSync(file); assert.equal(resolve(f.options), null);
    f.write(file, file === f.bindingFile ? f.binding : f.record);
  }
}));
test('hardlinked binding or registry files fail closed', () => fixture(f => {
  for (const file of [f.bindingFile, f.recordFile]) {
    const link = path.join(f.temp, 'hardlink'); fs.linkSync(file, link);
    assert.equal(resolve(f.options), null); fs.unlinkSync(link);
  }
}));
test('symlinked ancestor directories fail closed', () => fixture(f => {
  const link = path.join(f.temp, 'linked-mail');
  fs.symlinkSync(f.root, link, process.platform === 'win32' ? 'junction' : 'dir');
  assert.equal(resolve({...f.options, root: link}), null);
  const registryLink = path.join(f.temp, 'linked-registry');
  fs.symlinkSync(f.registryDir, registryLink, process.platform === 'win32' ? 'junction' : 'dir');
  assert.equal(resolve({...f.options, registryDir: registryLink}), null);
}));
test('UNC, namespace and relative paths fail closed', () => fixture(f => {
  for (const bad of ['relative', '//server/share', '\\\\server\\share', '\\\\?\\C:\\mail']) {
    assert.equal(resolve({...f.options, root: bad}), null);
    assert.equal(resolve({...f.options, registryDir: bad}), null);
  }
}));
test('binding mutation between reads fails closed', () => fixture(f => {
  const original = fs.readSync; let reads = 0;
  try {
    fs.readSync = function(...args) {
      // First binding read, EOF, first registry read, EOF, then binding recheck.
      if (++reads === 5) f.write(f.bindingFile, {...f.binding, remoteSessionId: 'cse_Changed'});
      return original.apply(this, args);
    };
    assert.equal(resolve(f.options), null); assert.ok(reads >= 5);
  } finally { fs.readSync = original; }
}));
test('registry mutation between reads fails closed', () => fixture(f => {
  const original = fs.readSync; let reads = 0;
  try {
    fs.readSync = function(...args) {
      if (++reads === 7) f.write(f.recordFile, {...f.record, hostSessionId: 'local_' + randomUUID()});
      return original.apply(this, args);
    };
    assert.equal(resolve(f.options), null); assert.ok(reads >= 7);
  } finally { fs.readSync = original; }
}));

console.log(`# ${count} tests, ${failed} failed (claude-remote-identity)`);
if (failed) process.exitCode = 1;
