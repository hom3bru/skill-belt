# Design: session service

## Problem

Each of our three apps keeps its own login session, so a user signs in three times and a password change does not
sign them out everywhere.

## Proposal

- A new session service issues a session id at login and stores it in Redis with the user id and an expiry of 30 days.
- Each app sends the session id from its cookie to the session service on every request and gets back the user id.
- Logging out deletes the session in Redis. A password change deletes every session of that user.

## Rollout

Start with the admin app, then the two customer apps, one per week.
