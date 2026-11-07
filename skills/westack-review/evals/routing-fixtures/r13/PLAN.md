# Plan: event ingestion pipeline

## Goal

Accept client events over HTTP and make them queryable within a minute.

## Architecture

- An ingest service validates events and writes them to a queue.
- A consumer batches events and writes them to the warehouse every 30 seconds.
- A query API reads from the warehouse.
- Failed batches go to a dead-letter queue and are retried once an hour.

## Milestones

1. Ingest service with validation.
2. Consumer and warehouse schema.
3. Query API.
