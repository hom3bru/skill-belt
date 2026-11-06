<!-- runbook-6c9 -->
# Rotate the signing key

Use this when the signing key is due for rotation or may have been exposed. The release host is shared by the on-call rota.

1. Check you are on the release host: `deployctl whoami` prints `release`.
2. Sign in: `deployctl login --token "$DEPLOY_TOKEN"`.
3. Rotate: `deployctl rotate --key signing`.
4. Confirm: `deployctl verify --key signing` exits 0.
5. Sign out: `deployctl logout`.
