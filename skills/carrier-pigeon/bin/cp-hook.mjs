#!/usr/bin/env node
// carrier-pigeon's Codex hook: `node cp-hook.mjs codex post-tool-use|stop`, installed by `carrier-pigeon codex-hooks install`. When the listener
// held a follow-up for a Codex app thread because its turn was running (host/codex-app.json, `pending`), this hands the fixed pointer to that
// turn: at its next tool call as PostToolUse additionalContext, or at its Stop as decision:block, which Codex runs as a new prompt in the same
// turn. Output shapes follow reason-network src/hook.rs:153-176 (MIT OR Apache-2.0) and Codex's hooks documentation. Codex runs this for every
// tool call in every session, so it reads one small file and exits; and it never fails loudly: a broken mailbox must not break Codex.
import fs from 'node:fs'; import path from 'node:path'; import {fileURLToPath} from 'node:url';

const [agent, event] = process.argv.slice(2);
const SELF = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const ROOT = process.env.CARRIER_PIGEON_HOME || SELF; // installed as <mailbox>/bin/cp-hook.mjs

// The hook payload, without hanging if Codex never closes stdin.
const readStdin = ms => new Promise(res => { let s = ''; const t = setTimeout(() => res(s), ms); process.stdin.setEncoding('utf8');
  process.stdin.on('data', d => { s += d; }); process.stdin.on('end', () => { clearTimeout(t); res(s); }); process.stdin.on('error', () => { clearTimeout(t); res(s); }); });

// On Windows Codex runs hooks through a shell that can re-encode what passes through it: JSON in ASCII is safe from that (hook.rs:178-191).
export const ascii = s => s.replace(/[\u0080-￿]/g, c => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));
export function output(event, text) {
  if (event === 'post-tool-use') return ascii(JSON.stringify({hookSpecificOutput: {hookEventName: 'PostToolUse', additionalContext: text}}));
  if (event === 'stop') return ascii(JSON.stringify({decision: 'block', reason: text}));
  return null; }

// The pointers pending for this Codex thread, each handed over at most once: the first hook to create its mark takes it.
export function take(root, thread) { let s; try { s = JSON.parse(fs.readFileSync(path.join(root, 'host', 'codex-app.json'), 'utf8')); } catch { return []; }
  const b = (s?.threads || []).find(x => x?.id === thread); if (!b?.pending?.length) return [];
  const dir = path.join(root, 'host', 'codex-app-hooked'), out = [];
  for (const p of b.pending) { if (!/^[A-Za-z0-9_-]{1,80}$/.test(String(p?.id)) || typeof p.text !== 'string') continue;
    if (!fs.existsSync(path.join(root, 'agents', 'codex', 'inbox', p.id + '.md'))) continue; // already claimed or gone: nothing to announce
    try { fs.mkdirSync(dir, {recursive: true}); fs.closeSync(fs.openSync(path.join(dir, p.id), 'wx')); out.push(p.text); } catch {} }
  return out; }

async function main() {
  if (agent !== 'codex' || !['post-tool-use', 'stop'].includes(event)) return null;
  let v = {}; try { v = JSON.parse((await readStdin(3000)).replace(/^﻿/, '')); } catch { return null; }
  const thread = typeof v.session_id === 'string' ? v.session_id : null; if (!thread) return null;
  const texts = take(ROOT, thread); return texts.length ? output(event, texts.join('\n\n')) : null; }

// Exit as soon as the answer is written: Codex may keep stdin open, and nothing here may outlive 8 s.
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) { setTimeout(() => process.exit(0), 8000).unref();
  main().then(out => out ? process.stdout.write(out + '\n', () => process.exit(0)) : process.exit(0), () => process.exit(0)); }
