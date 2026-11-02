// Native-bound mailbox routing only. An alias does not grant task authority.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {ID_RE, safeName} from './cp-context.mjs';
import {remoteAddress} from './cp-claude-remote-client.mjs';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const PID_FILE = /^([1-9][0-9]*)\.json$/;
const MAX_BYTES = 64 * 1024;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const suffix = value => {
  const match = typeof value === 'string' ? /^(?:cse_|session_)([A-Za-z0-9]+)$/.exec(value) : null;
  return match && match[0] === value ? match[1] : undefined;
};
const sameFile = (a, b) => a.dev === b.dev && a.ino === b.ino;
const alive = pid => { try { process.kill(pid, 0); return true; } catch { return false; } };

function localPath(value) {
  if (typeof value !== 'string' || !path.isAbsolute(value) || /^(?:\\\\|\/\/)/.test(value) || /[\x00-\x1f\x7f]/.test(value)) throw Error();
  // Reject namespace paths and drive-relative/alternate-stream spellings too.
  if (process.platform === 'win32' && !/^[A-Za-z]:[\\/]/.test(value)) throw Error();
  if (process.platform === 'win32' && value.slice(2).includes(':')) throw Error();
  return path.resolve(value);
}

function checkedDirectory(value) {
  const dir = localPath(value), chain = [];
  for (let current = dir;; current = path.dirname(current)) {
    const stat = fs.lstatSync(current);
    if (!stat.isDirectory() || stat.isSymbolicLink()) throw Error();
    chain.push([current, stat]);
    if (path.dirname(current) === current) break;
  }
  return {dir, chain};
}

function unchangedDirectories(chain) {
  return chain.every(([name, before]) => {
    const after = fs.lstatSync(name);
    return after.isDirectory() && !after.isSymbolicLink() && sameFile(before, after);
  });
}

function boundedJson(file) {
  const before = fs.lstatSync(file);
  if (!before.isFile() || before.isSymbolicLink() || before.nlink !== 1 || before.size < 2 || before.size > MAX_BYTES) throw Error();
  const fd = fs.openSync(file, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  try {
    const opened = fs.fstatSync(fd);
    if (!sameFile(before, opened) || !opened.isFile() || opened.nlink !== 1 || opened.size !== before.size) throw Error();
    const bytes = Buffer.alloc(MAX_BYTES + 1);
    let size = 0, count;
    while (size < bytes.length && (count = fs.readSync(fd, bytes, size, bytes.length - size, null)) > 0) size += count;
    const after = fs.fstatSync(fd), named = fs.lstatSync(file);
    if (size > MAX_BYTES || size !== before.size || after.size !== size || after.mtimeMs !== opened.mtimeMs ||
        named.isSymbolicLink() || named.nlink !== 1 || !sameFile(after, named)) throw Error();
    const raw = bytes.subarray(0, size).toString('utf8'), value = JSON.parse(raw);
    if (!object(value)) throw Error();
    return {raw, value, stat: after};
  } finally { fs.closeSync(fd); }
}

function registrySnapshot(dir, nativeId) {
  const names = fs.readdirSync(dir).sort();
  if (names.length > 4096) throw Error();
  const live = [];
  for (const name of names) {
    const match = PID_FILE.exec(name);
    if (!match || match[0] !== name) continue; // Never open peer .key files.
    const pid = Number(match[1]);
    if (!Number.isSafeInteger(pid)) throw Error();
    const record = boundedJson(path.join(dir, name));
    if (record.value.sessionId === nativeId && alive(pid)) live.push({name, pid, ...record});
  }
  return {names, live};
}

export function resolveRemoteMailboxSession(options = {}) {
  try {
    const {root, message, env = process.env, parentPid = process.ppid} = options;
    if (!object(env)) return null;
    const registryDir = options.registryDir ?? path.join(env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude'), 'sessions');
    const nativeId = env.CLAUDE_CODE_SESSION_ID;
    if (typeof nativeId !== 'string' || nativeId.length !== 36 || !UUID.test(nativeId) || !Number.isSafeInteger(parentPid) || parentPid <= 0 ||
        !object(message) || message.to !== 'claude' || typeof message.id !== 'string' || !ID_RE.test(message.id) ||
        typeof message.thread !== 'string' || !safeName(message.thread) || typeof message.to_session !== 'string') return null;
    const environmentId = /^claude-desktop-(env_[A-Za-z0-9]+)$/.exec(message.to_session)?.[1];
    if (!environmentId || remoteAddress(environmentId) !== message.to_session) return null;
    const mailbox = checkedDirectory(root), registry = checkedDirectory(registryDir);
    const bindings = checkedDirectory(path.join(mailbox.dir, 'host', 'claude-remote-threads', environmentId));
    const bindingFile = path.join(bindings.dir, message.thread + '.json'), binding = boundedJson(bindingFile);
    const b = binding.value, bridge = suffix(b.remoteSessionId);
    if (b.environmentId !== environmentId || b.thread !== message.thread || !bridge) return null;
    const snapshot = registrySnapshot(registry.dir, nativeId);
    if (snapshot.live.length !== 1) return null;
    const record = snapshot.live[0], r = record.value;
    if (r.pid !== record.pid || record.pid !== parentPid || r.entrypoint !== 'claude-desktop' ||
        typeof r.hostSessionId !== 'string' || r.hostSessionId.length !== 42 || !r.hostSessionId.startsWith('local_') || !UUID.test(r.hostSessionId.slice(6)) ||
        suffix(r.bridgeSessionId) !== bridge) return null;
    // Re-read both contents and the live candidate set before returning routing identity.
    const again = boundedJson(bindingFile), final = registrySnapshot(registry.dir, nativeId);
    if (again.raw !== binding.raw || !sameFile(again.stat, binding.stat) || final.live.length !== 1 ||
        JSON.stringify(final.names) !== JSON.stringify(snapshot.names) || final.live[0].name !== record.name ||
        final.live[0].raw !== record.raw || !sameFile(final.live[0].stat, record.stat) || !alive(parentPid) ||
        !unchangedDirectories([...mailbox.chain, ...registry.chain, ...bindings.chain])) return null;
    return message.to_session;
  } catch { return null; }
}
