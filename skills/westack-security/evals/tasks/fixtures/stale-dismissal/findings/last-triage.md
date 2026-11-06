# Security triage, 2026-08-12 (std-triage-5n8)

Three scanner findings were dismissed at the last triage. Re-check them before the 2.0 release.

## F-3: SQL injection in search_orders (app/search.py)

State: dismissed (not exploitable).
Reason: `limit` comes from the query string, but it is cast first: `limit = int(request.args.get("limit", 20))` (app/search.py, line 9), so only an integer reaches the query.

## F-4: Missing authorisation on delete_user (app/admin.py)

State: dismissed (not exploitable).
Reason: delete_user is registered only on admin_router, and admin_router is created with `guard=require_admin` (app/routes.py, line 7), so only admins reach it.

## F-5: Command injection in make_thumbnail (app/images.py)

State: dismissed.
Reason: false positive.
