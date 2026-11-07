# Opt-in extensions

All four are off by default; the standard-library index works without any of them. Each needs the user's yes for what it touches, named before it runs.

## Local embeddings (a vector arm)

`codeindex.py build|update --embed URL [--embed-model NAME]` sends each chunk to an embedding endpoint and stores the vectors in the index; `search --embed URL` embeds the query and adds a third arm, by cosine similarity, to the reciprocal-rank fusion. The endpoint speaks Ollama's `/api/embed` or an OpenAI-style `/v1/embeddings` (`{"model", "input"}` in, `embeddings` or `data[].embedding` out). It must be on this machine (127.0.0.1, localhost, ::1): any other host would receive the repository's code, so it needs `--allow-remote-embed`, which only the user's grant justifies, and never a paid service under the stack's no-new-paid-services rule. A down endpoint leaves the chunks without vectors and the search keyword-only, and says so.

## tree-sitter

`build|update --tree-sitter` uses tree-sitter grammars, when installed, for JavaScript, TypeScript, Go and Rust: class and impl methods become their own symbols (`WidgetStore.add`, `Server.Start`, `Store.new`), and calls are told apart as `f(...)` or `obj.m(...)`, which the definition patterns cannot do. Without the package or a grammar it says so and the patterns are used. Switching it on or off re-walks the index. Installing tree-sitter is the user's install, not this skill's.

## Sharing an index (`indexsync.py`)

`export --repo R --out FOLDER [--exclude PATH ...]` writes the index's pages and chunks as JSONL after a secret scan of every chunk (AWS, GitHub, Slack, Google and OpenAI-style keys, private key blocks, and quoted values assigned to password, secret, api key or token): one finding refuses the export and writes nothing. Remove the secret, or leave the file out with `--exclude`; test fixtures with fake keys trip it too. `import --repo R --from FOLDER` merges an export for the same repository key into this machine's index: missing pages are added, and a page this index has with other content keeps the local version (listed as a conflict).

Moving the folder through a private git repository (add, commit, push, pull) is the agent's work under the user's grant; the script never runs git. Never push an export to a public remote.

## MCP server (`mcpserver.py`)

`mcpserver.py --repo R` serves the read verbs (search, show, def, refs, callers, callees, context, delta, doctor) over stdio as JSON-RPC, one message per line. It never builds, updates, sets a tier or writes guidance, and each call obeys the trust tier. Adding it to a host's MCP settings is persistent configuration: the user does it, or grants it, and the report names the entry.

Provenance: gbrain's local embedding provider, secret scan and MCP server, and gstack's private-git brain sync, at the mirror pins (absorption.json `gbrain.local-embeddings`, `gbrain.secret-scan`, `gbrain.mcp`, `gstack.brain-sync.git`), in westack's words. gbrain's local reranker is not built: no acceptance check covers it yet.
