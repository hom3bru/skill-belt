// Operator-selected compatibility settings. No mailbox scanning, writes or key operations.
import fs from 'node:fs';
import path from 'node:path';
const configured = (key, fallback) => process.env[key] === undefined ? fallback : process.env[key];
export const HUMAN_ID = configured('CARRIER_PIGEON_HUMAN_ID', 'user');
if (!/^[a-z][a-z0-9_-]{0,31}$/.test(HUMAN_ID) || ['grok','cursor','claude','codex'].includes(HUMAN_ID))
  throw new Error('Invalid configured human actor; choose a distinct safe local identifier');
if(HUMAN_ID!=='user' && (process.env.CARRIER_PIGEON_HELLO_KEY_NAME===undefined || process.env.CARRIER_PIGEON_LEGACY_APPROVAL_FIELD===undefined)) throw new Error('A custom human actor requires explicit key and approval-field compatibility settings');
export const AGENTS = ['grok','cursor','claude','codex',HUMAN_ID];
export const HELLO_KEY_NAME = configured('CARRIER_PIGEON_HELLO_KEY_NAME', 'carrier-pigeon-user');
if (typeof HELLO_KEY_NAME !== 'string' || !HELLO_KEY_NAME.trim() || HELLO_KEY_NAME.length > 200 || /[\r\n\0]/.test(HELLO_KEY_NAME))
  throw new Error('Invalid Windows Hello key reference');
export const APPROVAL_FIELD = 'requires_user_approval';
export const LEGACY_APPROVAL_FIELD = configured('CARRIER_PIGEON_LEGACY_APPROVAL_FIELD', APPROVAL_FIELD);
if (!/^requires_[a-z][a-z0-9_]{0,63}_approval$/.test(LEGACY_APPROVAL_FIELD))
  throw new Error('Invalid legacy approval field reference');
export const LEGACY_APPROVAL_FLAG = LEGACY_APPROVAL_FIELD.replaceAll('_','-');
export function approvalRequired(message) {
  if(Object.keys(message).some(k=>/^requires_.+_approval$/.test(k) && ![APPROVAL_FIELD,LEGACY_APPROVAL_FIELD].includes(k))) throw new Error('Unknown approval marker: select explicit compatibility configuration');
  const values = [...new Set([APPROVAL_FIELD,LEGACY_APPROVAL_FIELD])].filter(k => Object.hasOwn(message,k)).map(k => message[k]);
  if (values.some(v => typeof v !== 'boolean')) throw new Error('Approval markers must be booleans');
  if (values.length === 2 && values[0] !== values[1]) throw new Error('Conflicting approval markers; inspect the original record');
  return values.some(v => v === true);
}
export function approvalOption(options) {
  const value = {};
  for (const flag of [...new Set(['requires-user-approval',LEGACY_APPROVAL_FLAG])]) {
    if (Object.hasOwn(options,flag)) {
      const v=options[flag];
      if (![true,false,'true','false'].includes(v)) throw new Error('Approval flags must be explicit booleans');
      value[flag === 'requires-user-approval' ? APPROVAL_FIELD : LEGACY_APPROVAL_FIELD] = v === true || v === 'true';
    }
  }
  return approvalRequired(value);
}
// A mismatched existing mailbox is never silently initialized or upgraded.
export function assertMailboxIdentity(root) {
  if (fs.existsSync(path.join(root,'log.jsonl')) && !fs.existsSync(path.join(root,'agents',HUMAN_ID,'inbox')))
    throw new Error('Existing mailbox identity differs: configure its human actor before use; no data was changed');
}
