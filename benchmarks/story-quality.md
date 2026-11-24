# Story and acceptance evaluation suite (planned)

All examples below synthetic. Keep development and holdout cases distinct; independent gold and adjudication required before executing.

| Case | Input mutation / challenge | Expected evaluator behavior |
|---|---|---|
| SQ01 | story combines independent outcomes | identify split opportunity with rationale |
| SQ02 | conjunction inside one indivisible outcome | do not flag confirmed atomicity defect merely by syntax |
| SQ03 | nonstandard Job Story or technical enabler | evaluate according to profile; no fabricated actor |
| SQ04 | duplicate paraphrase across stories | identify candidate and verify semantic equivalence |
| SQ05 | similarly titled but distinct rules | do not merge distinct behavior |
| AC01 | missing rejection criterion | find uncovered obligation with source locator |
| AC02 | unsupported numeric threshold | flag proposed/unsupported, do not accept silently |
| AC03 | reversed condition or state transition | detect contradiction |
| AC04 | valid Gherkin with wrong expected outcome | semantic failure despite syntactic validity |
| AC05 | ambiguous exception behavior | question required, not invented expected result |
| AC06 | valid bullet criterion | do not force Gherkin |
| AC07 | duplicated test vs task vs criterion | maintain distinctions and trace links |
| AC08 | omitted table cell or negative requirement | independent source-first detection |
| PL01 | absent team capacity | no committed sprint plan |
| PL02 | missing architecture | spike/proposal, no fabricated technology |
| TX01 | HTML rich text and accented text | preserve content and semantic formatting on round-trip |

Measure per category precision/recall, false positives/negatives, criterion coverage, unsupported claims, reviewer agreement, format portability, task sufficiency, cost and variance. Compare rule-only, agent-only and hybrid approach; use same source sets, report abstention and unknowns separately. No score or qualification claimed yet. See [protocol](README.md).
