# Language and representation support

Rule Or Reason has no programming-language allowlist for reading. A host agent can inspect text in an unfamiliar language, but the quality of that analysis is bounded by its actual understanding and tools. Do not describe this as universal semantic understanding.

## Report a capability vector

For each relevant language or representation, report these dimensions independently:

| Dimension | Evidence needed |
| --- | --- |
| Discovered | Relevant files, embedded blocks, templates, generated code, or captured outputs identified |
| Read | Actual source spans and limitations recorded; omitted files remain visible |
| Parsed | A named parser/tool and version successfully parsed the relevant material |
| Linked | Calls/imports/data dependencies traced, with dynamic or unresolved paths marked |
| Executed | The named runtime executed the artifact in the authorized environment |
| Evaluated | The task oracle checked the relevant behavior; parsing alone does not establish this |

Use verified, partial, unavailable, or not attempted per dimension. State whether analysis is textual, parser-backed, static, or observed. A successful Python comparison helper does not mean a Java, Rust, SQL, or COBOL candidate ran.

## Discovery approach

Start with repository instructions, manifests, explicit entry points, file names/extensions, and source contents. Use existing host tools such as targeted text search, language servers, compilers, or project scripts where available. Do not install a parser just to claim support.

Recognize polyglot repositories and embedded languages: SQL inside Java, shell inside CI, templating inside HTML, regular expressions inside strings, notebooks with multiple kernels, and foreign-function interfaces. File suffix is a hint, not an execution contract. Generated and vendored sources need provenance and a clear authoring boundary.

When a parser is absent, inspect text and callers manually. Name unresolved syntax, macros, dynamic dispatch, metaprogramming, reflection, generated imports, and runtime configuration. Continue useful discovery without manufacturing complete call-graph coverage. Propose a concrete parser/runtime check only if it would change the decision.

## Human languages and encodings

Accept Unicode source and natural-language documents. Detect or ask about materially ambiguous encodings; preserve original bytes and a decoded view with its encoding. Do not silently replace undecodable characters and then claim exact evidence.

Keep original-language evidence and source coordinates. Name the representation and coordinate unit (bytes, UTF-16 code units, code points, or graphemes), transformation identity, and whether an exact mapping back to the original exists. Revalidate ranges, source hashes and exact content after normalization, translation or serialization; do not guess offsets from repeated matching text. Translation can help analysis, but it is a derived artifact with a translator/model identity and known uncertainty. Do not make translation a hidden production dependency. Include mixed-language documents, code-switching, non-Latin names, right-to-left text, accented characters, and culturally specific numeric/date conventions in evaluation where they are in scope.

Normalization is a contract decision. NFC/NFKC, case folding, transliteration, punctuation removal, whitespace changes, and Unicode confusables can change identity or meaning. Record the transformation and test it. An ASCII regex passing English examples does not establish Arabic, Japanese, French, or multilingual coverage.

Unknown input language should cause an explicit support limitation or appropriate abstention, not silent English treatment. Do not infer language capability from a model's marketing or a parser's package name.

## Preserve semantics across implementation languages

For a port or language-neutral intermediate representation, cover material differences in:

- Integer range, overflow, decimal precision, floating point, NaN and infinity.
- Null, missing keys, empty strings, falsy values, defaults, and optional values.
- Unicode normalization, text indexing, graphemes, case folding, regex syntax/complexity.
- Equality, coercion, collection ordering, stable sorting, and locale collation.
- Dates, clocks, time zones, units, and reference exchange-rate/source versions.
- Exceptions, error results, partial success, retries, cancellation, and timeouts.
- Ownership, memory, threads, initialization, shared state, and transaction behavior.
- Serialization, wire types, ABI boundaries, and resource lifetime.

Mark a dimension not applicable only with a reason. An unfamiliar implementation can still be read; unknown material semantics prevent claiming a verified replacement.

## Output languages

Prefer the recipient's existing language and libraries. A deterministic algorithm is a behavioral property, not a Python implementation requirement. Use the recipient's normal build, lint, type, and test commands. Propose cross-language bridging only when evidence justifies it and the user's authorized scope permits it.

The bundled comparison helper requires Python 3.10+ and only the standard library. It reads language-neutral JSON prediction records; it cannot parse or execute arbitrary source files. Without Python, compute the same declared descriptive quantities through available tools and state that the bundled helper was not run.

There are no bundled language-specific parsers, compiler integrations, OCR engines, translators, sandbox providers, or automatic arbitrary-language runners in version 0.1.1.
