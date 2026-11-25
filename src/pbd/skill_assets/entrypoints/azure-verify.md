# /pbd-azure-verify

**Mock only.** This build has no live transport: nothing authenticates to, reads from or writes to a real Azure DevOps organization, not even read-only or validateOnly. Inputs are local files the owner exported and authorized; the target is an in-memory mock saved to a local JSON file. A mock result never proves a live target.

`pbd azure verify --plan ... --receipt dir/publication-receipt.json --package azure-import.json --mock-state mock.json --out dir` reads every touched item back in batches of at most 200, compares written fields (normalized HTML) and parent links, and writes `publication-receipt.verified.json` (MOCK_VERIFIED or MISMATCH with deviations) and `published-state.json` (revision and managed-field digest per item, used by the next prepare to detect human edits). G17/G18 stay BLOCKED/NOT_RUN for a live target.
