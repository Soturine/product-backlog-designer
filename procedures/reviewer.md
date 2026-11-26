# Independent reviewer procedure

You did not reconcile claims or design this backlog. Your review is the independent evidence for gates G02, G04–G09, G13 and G14.

## Order matters
1. **Sources first.** Before opening the design, re-read every source member (`sources/text/...`). Build your own inventory of obligations, each with `locator` (`source_id`, `member`, `line_start`) and a verbatim `quote`. This is the coverage denominator; do not copy the generated claims.
2. Then open `stages/claims.json` and `stages/design.json`. Map each of your obligations: COVERED / PARTIALLY_COVERED / NOT_COVERED / QUESTION_REQUIRED / CONFLICTING / OUT_OF_SCOPE / SUPERSEDED / DEFERRED / BLOCKED, with `covered_by` design keys and rationale.
3. Judge **every** item and **every** criterion exactly once: `verdict` pass/concern/fail, `source_support` supported/proposal_justified/unsupported, notes for concerns and failures. Stories also get INVEST ratings (supported/concern/unknown/not_applicable, each with a note; missing team sizing data is `unknown`, not a defect) and `task_sufficiency` when tasks were requested. Every buildable item that declares `readiness` gets `readiness_check`: `agree` or `dispute` (with `readiness_notes`). Dispute when work the sources leave undecided is presented as ready, when a question that prevents work is marked non-blocking, or when unrelated work is blocked by association. A dispute fails G08.

## Detection passes (adapted from Spec Kit analyze; semantic, not keyword-based)
Duplication · ambiguity (vague adjectives, missing thresholds) · underspecification (missing outcome, actor, error behavior) · alignment with sources and approved decisions · coverage gaps (both directions) · inconsistency (terminology, contradicting criteria, wrong state transitions). Sizing signals (adapted from HVE Core story quality) are *candidates*: a feature whose only child restates it, an epic without children, a task with beneficiary framing, a story whose criteria cannot be verified without splitting.

## Mandatory checks
- Re-read the ORIGINAL sources with your host's native tools (as readers do: native first, extracted text to locate and verify lines); a quote of figure or diagram content must come from your own `visual_transcriptions`.
- Confirmed behavior that resolves an ambiguity the sources leave open is an `unsupported_assumption` finding, even if plausible.
- An effective obligation represented only in an Epic/Feature (see `signals.claims_only_in_containers` in `output/checks.json` after finalize, or check it yourself) is PARTIALLY_COVERED unless a criterion, verifiable rule or task carries it.
- Work on a superseded mechanism without implementation evidence of that mechanism is a finding.
- Values stated by the sources (priorities, estimates) missing from the fields are a gap.

## Audit mode
When the work order says AUDIT, the backlog is an imported baseline: it has no claim references by design. Judge it only against the sources: map each of your obligations to the baseline items/criteria that carry it (`covered_by`), set `source_support` per item and criterion, and record every divergence, gap, superseded requirement still demanded and out-of-scope item as a finding. Imported wording and formats are not defects by themselves.

## Compare mode
When the work order says COMPARE, two imported baselines (keys `L-...` and `R-...`) are judged against the same sources; neither is gold and item counts are not quality. Re-read the sources first and build one inventory. For each obligation give `left` and `right` objects (`disposition`, `covered_by` with that side's keys, `rationale`). Review every item and criterion of both sides once (stories on both sides also need INVEST ratings, as in generation). Map them in `mappings` (`left`: [...], `right`: [...], `relation`: equivalent | split | merge | overlap | divergent | conflicting, `rationale`, optional `differences`): legitimate differences of decomposition are not defects. Findings carry `side`: left | right | both. Never declare a winner.
```json
{"reviewer": {...}, "sources_reread": [...],
 "independent_obligations": [{"key": "O1", "text": "...", "quote": "...", "locator": {...}, "matched_claims": ["C1"],
   "left": {"disposition": "COVERED", "covered_by": ["L-12.AC1"], "rationale": "..."},
   "right": {"disposition": "PARTIALLY_COVERED", "covered_by": ["R-7"], "rationale": "..."}}],
 "items": [{"key": "L-12", "verdict": "pass", "source_support": "supported"}], "criteria": [...],
 "mappings": [{"left": ["L-12"], "right": ["R-7", "R-8"], "relation": "split", "rationale": "..."}],
 "findings": [{"side": "left", "classification": "confirmed_gap", "severity": "high", "expected": "...", "actual": "...",
   "why": "...", "impact": "...", "recommendation": "...", "affects": ["L-12"]}]}
```
Submit with `pbd submit comparison --file comparison.json`, then `pbd finalize`.

## False-positive controls
A conjunction is not automatically two stories; a valid nonstandard format need not be rewritten; an enabler without persona is legitimate; an optional field left empty is not a defect; unknown is not wrong. Distinguish confirmed divergence from candidate concern and optional improvement.

## Contract
```json
{"reviewer": {"agent": "reviewer-1", "model": "<actual model>", "independence": "separate_agent"},
 "sources_reread": [{"source_id": "<SRC-ID>", "complete": true}],
 "independent_obligations": [{"key": "O1", "text": "...", "quote": "...",
   "locator": {"source_id": "<SRC-ID>", "member": "prd.md", "line_start": 12},
   "disposition": "COVERED", "matched_claims": ["C1"], "covered_by": ["AC1"], "rationale": "..."}],
 "items": [{"key": "US1", "verdict": "pass", "source_support": "supported", "notes": "",
            "invest": {"independent": {"rating": "supported", "note": "..."}, "negotiable": {"rating": "supported", "note": "..."},
                       "valuable": {"rating": "supported", "note": "..."}, "estimable": {"rating": "unknown", "note": "no team data"},
                       "small": {"rating": "supported", "note": "..."}, "testable": {"rating": "supported", "note": "..."}},
            "task_sufficiency": "sufficient", "readiness_check": "agree"},
           {"key": "T3", "verdict": "concern", "source_support": "supported", "notes": "...",
            "readiness_check": "dispute", "readiness_notes": "needs the provider the sources leave open"}],
 "criteria": [{"key": "AC1", "verdict": "pass", "source_support": "supported"}],
 "duplicates": [{"items": ["US2", "US5"], "assessment": "distinct", "rationale": "different rule"}],
 "dependencies_reviewed": true,
 "findings": [{"gate": "G06", "classification": "confirmed_gap", "severity": "high", "expected": "...", "actual": "...",
               "why": "...", "impact": "...", "recommendation": "...", "affects": ["US1"], "review_status": "confirmed"}]}
```

Allowed values: `verdict` pass/concern/fail (concern and fail need `notes`); `source_support` supported/proposal_justified/unsupported; INVEST `rating` supported/concern/unknown/not_applicable; `task_sufficiency` sufficient/insufficient/not_applicable; `readiness_check` agree/dispute (dispute needs `readiness_notes`); `duplicates[].assessment` duplicate/distinct/overlap; finding `classification` confirmed_divergence/confirmed_gap/ambiguous_source/unsupported_assumption/planning_gap/candidate_concern/optional_improvement/justified_exception/question (out-of-scope work is an `unsupported_assumption` or `confirmed_divergence`); finding `review_status` candidate/confirmed; finding `affects` lists design or claim keys only (cite a question in the text, not in `affects`); `covered_by` lists only design item/criterion keys and `matched_claims` only claim keys.

Write every payload as UTF-8 (for example `open(path, 'w', encoding='utf-8')` or your file-writing tool); avoid shell heredocs for large JSON.
