# Upstream pins and adoption records

Pinned 2026-11-24 for M0. "Concept" means design ideas were studied and reimplemented originally; no file, function body or text was copied. Repository license is still pending, so no code adoption is permitted yet (see [upstream audit](upstream-code-audit.md)).

| Upstream | Pinned commit (inspected clone) | License (root) | Adoption in M0 | Notes |
|---|---|---|---|---|
| [Functional Test Designer](https://github.com/Soturine/functional-test-designer) | `314e8d6dd9a81ee533fe46f87da293e0b981b7ab` (VERSION 2.5.0) | MIT | concept | scoped source selection, atomic writes, content digests, prepare/apply split. Root LICENSE copyright line must be reviewed before any copy. |
| [Assertiva](https://github.com/Soturine/Assertiva) | `d4d8d49201ce0461cbc180798344f2518c2901f0`; CLI 1.0.0 executed | Apache-2.0 | concept + tool run | gate semantics (absent evidence ≠ pass). `assertiva audit` executed against PBD; see [M0 evidence](evidence/M0.md). |
| [Derivanta](https://github.com/Soturine/derivanta) | `218761dbd7ce78809ace0ae2c03ee23adf9b406b` | Apache-2.0 | not adopted | governance/evidence style followed in docs. Its `check_markdown_links.py` hard-codes its own repository root, so it was not run (NOT_RUN); PBD has an original link test. |
| Others in [upstream audit](upstream-code-audit.md) | blob SHAs listed there | as listed | none in M0 | revisit per milestone (M2 HVE/Spec Kit, M3 Azure MCP, M5 OpenSpec). |

## Adoption record template (required before any copy)
Upstream URL and commit/blob · file-level license and NOTICE · purpose · modifications · dependency surface · security review · original and new tests · behavior difference · update policy · owner approval reference.
