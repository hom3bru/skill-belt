# Plan: move sign-in to the new identity provider

1. Register the app with the new provider and get test credentials.
2. Add a second login route that uses the provider; keep the old one.
3. Migrate users in batches of 500, matching accounts by email.
4. Turn the old login off for migrated users.
5. Remove the old login code and the password table.

Owner: platform team. Target: January.
