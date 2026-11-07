# Deploying and reading back

## Detect

`deploycheck.py detect <repo>` reads files only:

| File | Platform | What it gives |
| --- | --- | --- |
| `fly.toml` | fly | the app name and `https://<app>.fly.dev` |
| `render.yaml` | render | the first service name |
| `vercel.json` or `.vercel/` | vercel | |
| `netlify.toml` | netlify | the publish folder |
| `Procfile` | heroku | |
| `railway.json` or `railway.toml` | railway | |
| a workflow with a deploy step | github-actions | the workflow and the step (fly deploy, vercel --prod, netlify deploy, firebase deploy, kubectl apply, wrangler deploy, Pages actions, s3 sync, gcloud, az webapp) |
| `wrangler.toml` | cloudflare | |
| `Dockerfile` | docker | an image only: where it runs is still to name |
| `index.html` at the root or in dist, build, public, site, _site, out or www | static | the folder |

Several candidates, or none: ask the user which path is real and record their answer as `custom` with the command they name. Platforms that deploy on push (Vercel and Netlify connected to the repository, a deploy workflow) deploy when the push lands: that push needs the deploy grant, and westack-ship's pre-push check will stop at it.

## Deploy

- The grant names the target, its environment and the revision: "deploy abc1234 to staging". It does not carry over to another target or a later revision.
- Run the project's own path one step at a time: its CLI (`fly deploy`, `netlify deploy --prod`), a workflow dispatch, a container push, or for a static folder a copy into the target folder with the revision stamped where the read-back can see it.
- Record each step's name and exit code. A non-zero exit stops the deploy: inspect before any retry, never replay blindly.
- Wait bounded. Platforms that build after a push need time; check status every minute or so up to twenty minutes, then ask the user before waiting another twenty (`wait_grant`). A status query that errors is unknown, never success.

## Read back

`deploycheck.py readback <url> [--revision REV] [--text TEXT]` makes one GET with no cache and reports `status` (2xx) and, when asked, `revision` (in the body or an `X-Revision` header) and `text`. Run it against the target's health or version endpoint where it has one, else its home page. Healthy needs the status and the revision: a page that answers but serves the old revision is a failed deploy, and a target that does not answer is failed or unverified, never healthy.

## Rollback

Only when the user asks, in their own words naming the target: "roll staging back to the previous release". Use the platform's own rollback (`fly releases` then `fly deploy --image`, `vercel rollback`, Netlify's previous deploy, re-copying the previous folder) and read the target back for the previous revision. Record it under `rollback` with its own grant, steps, read-back and outcome.

## The record

```json
{"format": "westack-deploy-record-1", "platform": "static",
 "target": {"name": "fixture", "environment": "local", "url": "http://127.0.0.1:8781/"},
 "revision": "abc1234def", "grant": {"by": "the user", "said": "...", "scope": "deploy", "target": "fixture"},
 "steps": [{"name": "...", "exit": 0}], "waited_minutes": 0,
 "readback": {"url": "...", "status": 200, "checks": [{"name": "status", "passed": true}, {"name": "revision", "passed": true}]},
 "outcome": "healthy", "rollback": null}
```

`validate` refuses: a grant without who and their words, for another target or scope; healthy without a 2xx status and every check passed, without the revision read back, or with a failed step; unverified with a status or without its reason; a wait past twenty minutes without `wait_grant`; a rollback whose grant is not its own.

Provenance: gstack's setup-deploy and the deploy half of land-and-deploy at the mirror pin (absorption.json `gstack.deploy`), in westack's words.
