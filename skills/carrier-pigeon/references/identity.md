# Configurable human identity

Fresh installations use the anonymous actor `user`, approval marker
`requires_user_approval`, and Windows Hello key reference `carrier-pigeon-user`.
Configuration is local to the operator, never supplied by a message or peer.

Before using this version with an existing mailbox, set the same three variables
for every CLI, MCP and listener process:

| Variable | Value to select privately |
| --- | --- |
| `CARRIER_PIGEON_HUMAN_ID` | Existing human actor ID; select the actual mailbox namespace. |
| `CARRIER_PIGEON_HELLO_KEY_NAME` | Existing Windows Hello key name; this is a reference, not key material. |
| `CARRIER_PIGEON_LEGACY_APPROVAL_FIELD` | Exact existing `requires_<identifier>_approval` field. |

Keep real compatibility values in local shell/service configuration outside Git.
Do not infer them from a person's display name. All three settings are required
for a custom human actor. A public fictional test uses `legacy-person`,
`fixture-existing-key` and `requires_legacy_person_approval`; these are not values
to apply to a real installation. Set `CARRIER_PIGEON_HOME` explicitly when selecting
an existing mailbox. Do not run `init`, `install` or `hello init` to resolve a
configuration mismatch. The runtime refuses initialization and installation when
an existing log does not have the selected human inbox; it does not move messages,
rename folders, rewrite records, rotate keys or change security settings.

The configured actor is used consistently by routing, typed agent lists,
human-only memory operations, co-work adjudication and signature authority checks.
It cannot be one of the AI actor IDs. Existing host routing configuration is
preserved by installation; select the matching private identity before an update.

Signature versions 1 and 2 retain their original payload rules and field order.
Version 2 reads the explicitly configured legacy approval field without renaming
the stored record. New signatures use version 3 and bind the canonical generic
approval field. Unsupported versions, mixed signature-version markers, unknown
approval markers and conflicting legacy/canonical flags fail closed. The configured
legacy CLI flag and MCP argument are accepted as explicit aliases for new records;
new records use `requires_user_approval`. No alias grants authority: unsigned,
forged, expired or nonhuman messages remain untrusted requests. A signature still
requires the operator's Windows Hello gesture and the host-selected key.

This source update does not install itself, start a listener, create a key or
update the operator's running setup. Compatibility tests use disposable mailboxes
and software test keys. Native Windows Hello interaction is not requalified by
those tests. Earlier public Git history is preserved.
