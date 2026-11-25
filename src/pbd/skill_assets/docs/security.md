# Security and privacy

- Authorized source allowlist, canonical path validation, symlink escape prevention; document text and remote fields are untrusted data, not executable instructions.
- No corporate/customer names, real IDs, documents, screenshots, credentials, private URLs or production snapshots in public examples, commits, logs or benchmarks. Synthetic fixtures only. Private working state ignored by Git.
- Redact secrets before reports/logs, never export credentials, avoid unnecessary identity data; local output remains sensitive.
- Safe HTML allowlist, escaped text, no scripts from sources, no remote assets by default, CSV formula injection mitigation, safe filenames, bounded archive/document parsing.
- Least-privilege auth, explicit destination verification, separate read/write modes, exact plan hash approval, revision checks, no automatic deletion or rule bypass.
- Fail closed on malformed inputs, incomplete coverage, auth errors, schema mismatch and unverified publication. Recovery via journal and reconciliation, not blind retry.
- Dependency and license review; no copying third-party skill content without checking license and attribution.
- No public CI secrets or live production testing; use disposable targets and explicit credentials.
