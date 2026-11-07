<!-- adr-0004-5f1 -->
# ADR 0004: No network cache services in the quotes service

Status: accepted, 2026-06-12 (platform team)

## Context

The quotes service runs as one process per region. On 2026-05-03 a shared cache tier in another service failed
and took checkout down with it for 40 minutes. Ops runs no Redis or Memcached for this service and has no on-call
owner for one.

## Decision

Do not add network cache services (Redis, Memcached or similar) to the quotes service. When something needs
caching, cache it in process: `functools.lru_cache`, or a small dict with a time-to-live.

## Revisit when

Ops offers a managed cache with an on-call owner.
