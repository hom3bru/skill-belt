rotation notes (from the march rotation)

- new key: generate in the KMS console, alias api-signing-next
- update SIGNING_KEY_ID in the deploy config, both regions
- deploy api, wait for all pods to restart
- both keys valid for 24h (verifier accepts old + new)
- then disable the old key in KMS. do NOT delete it for 30 days
- check /health/signing shows the new key id
- if verification errors spike: re-enable the old key, roll back the config
