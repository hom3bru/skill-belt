# Plan: move the reports database to the new host

1. Create the new Postgres instance and restore last night's dump.
2. Point the nightly report job at the new host.
3. Run both hosts side by side for a week and compare row counts.
4. Switch the dashboard to the new host.
5. Shut down the old host.

Owner: data team. Target: end of November.
