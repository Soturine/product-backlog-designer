# /pbd-azure

**Mock only.** This build has no live transport: nothing authenticates to, reads from or writes to a real Azure DevOps organization, not even read-only or validateOnly. Inputs are local files the owner exported and authorized; the target is an in-memory mock saved to a local JSON file. A mock result never proves a live target.

Generation with `--formats azure` writes `output/azure/azure-import.json` (native fields, HTML description and acceptance kept separate, JSON Patch, proposed values never written) and a CSV subset with declared loss of fidelity. The publication workflow over that package is described in [/pbd-azure-publish](azure-publish.md); snapshots in [/pbd-azure-export](azure-export.md); read-back in [/pbd-azure-verify](azure-verify.md). Safety protocol: [docs/azure.md](../docs/azure.md).
