// Live check (opt-in; one cheap haiku session): a real Claude Code client drives the mailbox only through the carrier-pigeon MCP server
// (--strict-mcp-config, no shell) in a throwaway mailbox. It must (1) read and answer a seeded ask with the inbox/read/reply tools and
// (2) use the blocking `ask` tool, which returns the answer this script gives while playing "codex" through the CLI.
// Usage: node tests/live/mcp-claude.mjs [--claude BIN]
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path'; import {spawn, execFileSync} from 'node:child_process'; import {fileURLToPath} from 'node:url';
const SK = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..'); const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const cfgFile = path.join(os.homedir(), '.carrier-pigeon', 'host', 'config.json'); const live = fs.existsSync(cfgFile) ? JSON.parse(fs.readFileSync(cfgFile, 'utf8')) : {};
const BIN = arg('claude', live.claude?.bin || 'claude'); const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-mcp-')); const env = {...process.env, CARRIER_PIGEON_HOME: root};
const CLI = path.join(SK, 'bin', 'carrier-pigeon.mjs'); const run = (...a) => JSON.parse(execFileSync('node', [CLI, ...a, '--json'], {env, encoding: 'utf8'})); run('init');
const seeded = run('send', '--from', 'grok', '--to', 'claude', '--subject', 'capital check', '--body', 'Ask: what is the capital of France? Return: one word.');
const mcpCfg = path.join(root, 'mcp.json'); fs.writeFileSync(mcpCfg, JSON.stringify({mcpServers: {'carrier-pigeon': {command: process.execPath, args: [path.join(SK, 'bin', 'carrier-pigeon-mcp.mjs'), '--as', 'claude'], env: {CARRIER_PIGEON_HOME: root}}}}));
const prompt = 'You have the carrier-pigeon MCP tools. Step 1: check your inbox, read the message there, and reply to it with your answer. '
  + 'Step 2: use the ask tool to ask agent codex "What port does the dev server use?" (subject "port?", wait_seconds 40); if it returns pending, call wait_reply once. Then tell me the port it answered.';
const ch = spawn(BIN, ['-p', prompt, '--model', 'haiku', '--output-format', 'stream-json', '--verbose', '--strict-mcp-config', '--mcp-config', mcpCfg, '--tools', '', '--allowedTools', 'mcp__carrier-pigeon', '--permission-mode', 'dontAsk'],
  {cwd: root, env, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true});
let out = ''; ch.stdout.on('data', d => out += d); ch.stderr.on('data', d => out += d); const timer = setTimeout(() => ch.kill(), 300000);
// play codex: answer the port ask as soon as it appears
const codex = setInterval(() => { try { const m = run('inbox', 'codex').find(x => x.subject === 'port?'); if (m) { run('reply', m.id, '--as', 'codex', '--body', '4593'); clearInterval(codex); } } catch {} }, 1000);
ch.on('exit', code => { clearTimeout(timer); clearInterval(codex); const lines = out.split('\n').map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  const calls = lines.filter(o => o.type === 'assistant').flatMap(o => (o.message?.content || []).filter(b => b.type === 'tool_use').map(b => b.name)); const res = lines.find(o => o.type === 'result') || {};
  const answer = run('inbox', 'grok').find(x => x.reply_to === seeded.id); const answerBody = answer ? run('read', answer.id).body : null;
  const report = {exit: code, tool_calls: calls, seeded_ask_status: run('read', seeded.id).status, answer_to_grok: answerBody, final_text: String(res.result || '').slice(0, 200), cost_usd: res.total_cost_usd,
    verdict: answerBody && /paris/i.test(answerBody) && calls.some(n => /__ask$/.test(n)) && /4593/.test(String(res.result || '')) ? 'pass' : 'FAIL'};
  console.log(JSON.stringify(report, null, 1)); fs.rmSync(root, {recursive: true, force: true}); process.exit(report.verdict === 'pass' ? 0 : 1); });
