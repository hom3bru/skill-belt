# Changelog

## 1.0.0-alpha.0 (first build), unreleased

westack-deploy is built: detect, deploy, read back and rollback modes. `scripts/deploycheck.py` runs no command: `detect` names the platform from the project's files (Fly, Render, Vercel, Netlify, Heroku, Railway, a deploy workflow, Cloudflare, a Dockerfile, a static folder), `readback` makes one GET and checks the status and the revision, and `validate` checks the deploy record: the grant names the target and scope, healthy needs a 2xx status, every check passed and the revision read back (a reachable URL alone proves nothing), a failing read-back is failed and never reverted, unverified says why, a rollback carries its own grant, and a wait past twenty minutes needs the user's yes. Ideas from gstack's setup-deploy and land-and-deploy at the mirror pin. Tests: 18, with broken copies for detection, the healthy rule, the revision rule and a reused grant.
