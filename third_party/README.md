# Third-party material

| Component | Upstream (pinned) | License | Used in | What was taken | Modifications |
|---|---|---|---|---|---|
| Assertiva report design tokens | https://github.com/Soturine/Assertiva `assertiva/report_html.py` @ d4d8d49201ce0461cbc180798344f2518c2901f0 | Apache-2.0 ([LICENSE](assertiva/LICENSE)); no NOTICE file upstream | `src/pbd/render/report_html.py` (`CSS_TOKENS`) | light/dark CSS custom properties, radii, font stacks and status-tone classes (verbatim) | none to the token block; all components, layout and markup are original |
| Azure DevOps link reference names | https://github.com/microsoft/azure-devops-mcp `src/tools/work-items.ts` @ 2db70041a9bce29d228b4d8cbaea214541fc3ca9 | MIT ([LICENSE.md](azure-devops-mcp/LICENSE.md)) | `src/pbd/render/exports.py` (`AZURE_LINK_TYPES`) | mapping of link kinds to `System.LinkTypes.*` reference names | ported from TypeScript switch to a Python dict; subset only |

Everything else in PBD is original implementation; other upstreams informed design only (see [docs/upstream-adoption.md](../docs/upstream-adoption.md)).
