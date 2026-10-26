# Bounded feature

Task: change parse's return shape. Inspect parser → normalizer → CLI. Plan three vertical work units or prove an adapter preserves both consumers. Include an integration assertion through the CLI; a parser-only unit test cannot establish consumer compatibility.

Keep requirement origins explicit. If the user changes SQLite to JSON, supersede the database choice and invalidate pending actions tied to it. Preserve offline/no-cloud constraints. Record only material design choices, the allowed subtree and the next safe unit.

A green local integration check does not authorize installing a dependency, pushing a branch or deploying.

