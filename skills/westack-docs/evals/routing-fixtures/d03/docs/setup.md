# Developer setup

## Prerequisites

- Node 20
- Docker Desktop
- Access to the team vault

## Steps

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in the values from the vault.
3. Start the database with `docker compose up -d db`.
4. Run `npm install`, then `npm run dev`.

The app is then on port 3000.
