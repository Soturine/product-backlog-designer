# Threat model (M0)

Scope: local PBD runtime and agent workflow. Assets: user sources (often confidential), canonical backlog and evidence, private run state, future tracker credentials and remote work items. Complements [security](security.md).

| Threat | Vector | M0 control | Test evidence |
|---|---|---|---|
| Out-of-scope read | `..`, absolute paths, symlinks, Windows junctions, link members in directories | `Scope.resolve` canonicalizes, rejects escapes and any link on the selected path; directory walk never follows links | `tests/security/test_scope.py` |
| Archive abuse | zip-slip, absolute/drive paths, link/device entries, duplicate names, bombs, nested archives | inventory in place (no extraction), member/size/ratio limits, nested archives not expanded | `test_zip_*`, `test_tar_*` |
| Prompt injection from sources | source text instructing the agent to contact a tracker or copy files | sources are data; runtime has no network path; CLI runs under `offline()` | `test_offline_*`; CAL16 (planned M1 agent run) |
| Unintended network / tracker access | library or code path opening sockets | in-process guard on connect/connect_ex/getaddrinfo/create_connection; repo test forbids HTTP/subprocess imports in `src/pbd` | `test_offline_privacy_authority.py`, autouse fixture in `tests/conftest.py` |
| Unauthorized or stale remote write | apply without approval, edited plan, approval for another digest/target, conflicts | default-deny `authorize_apply`; live transport disabled; DELETE not in schema | `test_denied_*` |
| Secret or private data leak into Git | credentials, personal e-mails, private tracker URLs | privacy scanner over all tracked/untracked non-ignored files; `.gitignore` for `.pbd/`, outputs, env files | `test_repository_tracked_files_are_privacy_clean` |
| State corruption | crash mid-write, tampered/reordered/spliced journal | atomic replace with fsync; hash chain with sequence and prev link | `test_persistence.py` |
| False assurance | PASS without evidence, empty or generated-only denominator, mock claimed as live | gate rules, receipt schema forbids mock `LIVE_VERIFIED` | contract invalid cases |
| Identity drift | IDs from titles/positions, tracker IDs mixed with PBD IDs | opaque IDs, anchor key rejection, separate namespace | `test_identity_canonical.py` |

Residual risks: the network guard is in-process only (not an OS sandbox; subprocesses are uncontrolled, and PBD spawns none). Privacy scanning is pattern-based and can miss novel secret formats. Symlink paths are untested on hosts without symlink privileges (junction path tested on Windows). HTML/CSV injection controls arrive with renderers in M1.
