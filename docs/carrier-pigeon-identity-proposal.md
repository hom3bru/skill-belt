# Configurable human identity proposal

For review by the Carrier Pigeon 0.19 task.

Read the human identifier from local profile configuration through an explicit identity setting. Keep existing mailbox and signature identifiers as legacy aliases until their owner approves migration. Signing keys remain bound to the exact identity and payload they authenticated. Resolve aliases before routing, but preserve the original signed envelope for signature verification.

Accept the existing human agent identifier as a legacy alias through an explicit compatibility mapping to the configured human identity. Record the concrete legacy value in the private migration configuration. Keep the existing Windows Hello key name as a configured legacy key reference. Changing the profile must never rename mailbox folders, replace signing keys or authenticate unsigned messages.

Tests should cover old and new routing, ambiguous alias rejection, restart persistence, signed legacy-envelope verification and refusal of alias collisions with agent identifiers. This release changes no Carrier Pigeon code or configuration.
