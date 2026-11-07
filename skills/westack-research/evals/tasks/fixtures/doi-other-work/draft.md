<!-- draft-d2b -->
## 3. Why shard by tenant

Tenant-level sharding halves p99 write latency under mixed load [Haddad and Moreau, "Tenant Sharding at Scale",
2023, doi:10.5555/dbconf.2023.118]. We expect the same for the orders database.
