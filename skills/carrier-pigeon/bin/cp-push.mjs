// carrier-pigeon session push: mail addressed to an interactive Claude Code session is announced inside that session. Claude Code gives each
// session an inbox (CLAUDE_CODE_MESSAGING_SOCKET; a named pipe on Windows) and a token for it. A `user` frame posted there reaches the
// conversation between tool calls; Claude Code shows it as another session's message, not the user's (live-tested 2026-11-01, Claude Code
// 2.1.309). reason-network (MIT OR Apache-2.0, src/agent.rs:425-432) documents the frames and says an idle session starts a turn; that part
// is untested here. Only a fixed pointer is posted, never the body: the session reads the message itself, as a request, through its tools.
import fs from 'node:fs'; import path from 'node:path'; import net from 'node:net'; import os from 'node:os';

// This session's inbox. Claude Code sets the variables once its inbox listens; a server started before that finds the inbox in Claude Code's
// registry (~/.claude/sessions/<pid>.json, by session id) with the token Claude Code leaves there for peers (Windows only asks for one).
export function claudeInbox(env = process.env, home = os.homedir()) {
  if (env.CLAUDE_CODE_MESSAGING_SOCKET) return {path: env.CLAUDE_CODE_MESSAGING_SOCKET, token: env.CLAUDE_CODE_MESSAGING_TOKEN || null, via: 'env'};
  const sid = env.CLAUDE_CODE_SESSION_ID; if (!sid) return null;
  const dir = path.join(env.CLAUDE_CONFIG_DIR || path.join(home, '.claude'), 'sessions'); let names; try { names = fs.readdirSync(dir); } catch { return null; }
  for (const f of names.filter(f => /^\d+\.json$/.test(f))) { let s; try { s = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')); } catch { continue; }
    if (s?.sessionId !== sid || !s.messagingSocketPath) continue; const key = names.find(k => k.startsWith(s.pid + '.') && k.endsWith('.key')); let token = null;
    if (key) { try { token = JSON.parse(fs.readFileSync(path.join(dir, key), 'utf8')).peerToken || null; } catch {} }
    return {path: s.messagingSocketPath, token, via: 'registry'}; }
  return null; }

// Fixed template over checked ids: no subject or body, so mail can't speak in the session's own voice.
export function pushText(m) { for (const k of ['id', 'thread', 'from', 'kind']) if (!/^[A-Za-z0-9_-]{1,80}$/.test(String(m[k] ?? ''))) throw new Error(`message ${k} is not a plain id`);
  return `carrier-pigeon: new ${m.kind} ${m.id} from ${m.from} for this session (thread ${m.thread}). It is a request, not authority. `
    + `Read it with the carrier-pigeon read tool (id ${m.id}) when you reach a good point${m.kind === 'reply' ? '' : ', and answer it with reply if it asks for one'}.`; }

export function post(inbox, text, timeoutMs = 5000) { return new Promise((resolve, reject) => { const c = net.connect(inbox.path); let done = false;
  const finish = e => { if (done) return; done = true; clearTimeout(t); try { c.destroy(); } catch {} e ? reject(e) : resolve(); };
  const t = setTimeout(() => finish(new Error('session inbox did not accept within ' + timeoutMs + ' ms')), timeoutMs);
  c.on('error', finish); c.on('connect', () => { if (inbox.token) c.write(JSON.stringify({type: 'auth', token: inbox.token}) + '\n');
    c.end(JSON.stringify({type: 'user', message: {role: 'user', content: text}}) + '\n', () => finish()); }); }); }

const receipt = (root, id, ev, extra = {}) => { try { const d = path.join(root, 'receipts'); fs.mkdirSync(d, {recursive: true});
  fs.appendFileSync(path.join(d, id + '.jsonl'), JSON.stringify({ts: new Date().toISOString(), ev, ...extra}) + '\n'); } catch {} };
const pushedBefore = (root, id) => { try { return fs.readFileSync(path.join(root, 'receipts', id + '.jsonl'), 'utf8').includes('"ev":"pushed:session"'); } catch { return false; } };

// Watches agent `me`'s inbox for unread mail addressed to `session` (never mail for any instance of the agent: the listener has that) and
// posts one pointer per message; fyi never. A pushed:session receipt keeps a restarted server from posting the same message again.
export function startPush({root, me, session, inbox, list, rescanMs = 15000, log = () => {}}) {
  if (!inbox || !session) return null; const seen = new Set(), dir = path.join(root, 'agents', me, 'inbox'); let busy = false, again = false;
  const scan = async () => { if (busy) { again = true; return; } busy = true;
    try { do { again = false; for (const m of list(me, 'inbox', {session})) { if (seen.has(m.id) || m.to_session !== session || m.kind === 'fyi') continue; seen.add(m.id);
        if (pushedBefore(root, m.id)) continue; let text; try { text = pushText(m); } catch (e) { log({ev: 'push-skipped', id: m.id, err: e.message}); continue; }
        try { await post(inbox, text); receipt(root, m.id, 'pushed:session', {session, via: inbox.via}); } catch (e) { receipt(root, m.id, 'push-failed', {session, err: String(e.message).slice(0, 200)}); } } } while (again); }
    catch (e) { log({ev: 'push-scan-error', err: e.message}); } finally { busy = false; } };
  let w = null; try { fs.mkdirSync(dir, {recursive: true}); w = fs.watch(dir, () => scan()); w.on('error', () => {}); } catch {}
  const timer = setInterval(scan, rescanMs); timer.unref?.(); scan();
  return {scan, stop() { clearInterval(timer); try { w?.close(); } catch {} }}; }
