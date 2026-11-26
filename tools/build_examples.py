"""Build the synthetic example reports shipped with the docs (generation, audit and comparison).

These are FIXTURE REPRODUCTIONS: the stage payloads come from the test suite (fictional community
garden domain), not from a new agent-led execution. They exist to show the renderer and the
artifacts of each mode. Every report is labelled synthetic.

Usage: python tools/build_examples.py [examples/reports]
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.pipeline import library_fixture, test_audit, test_compare, test_team_planning  # noqa: E402
from tests.pipeline.helpers import claims_payload, designed_run, make_workspace, read_all  # noqa: E402
from tests.pipeline.test_review_finalize import review_payload  # noqa: E402

from pbd.pipeline.compare import finalize_comparison, submit_comparison  # noqa: E402
from pbd.pipeline.design import submit_claims  # noqa: E402
from pbd.pipeline.finalize import finalize  # noqa: E402
from pbd.pipeline.planning import plan  # noqa: E402
from pbd.pipeline.review import submit_review  # noqa: E402
from pbd.pipeline.run import normalize_request, start  # noqa: E402
from pbd.render.report_html import render_plan_report  # noqa: E402

KEEP = (
    "report.html",
    "backlog.json",
    "gates.json",
    "metrics.json",
    "comparison.json",
    "comparison.md",
    "backlog.md",
)


def _copy(run_out: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in KEEP:
        if (run_out / name).exists():
            shutil.copy2(run_out / name, dest / name)


def main(out: Path) -> None:
    tmp = Path(tempfile.mkdtemp())
    gen = designed_run(tmp / "gen", formats=["md", "azure"], profile="azure-agile", title="Horta comunitária")
    submit_review(gen, review_payload(gen))
    finalize(gen)
    _copy(gen.path("output"), out / "generate")

    ws = make_workspace(tmp / "aud")
    (ws / "baseline.json").write_text(json.dumps(test_audit.BASELINE), encoding="utf-8")
    aud = start(
        tmp / "aud" / "out",
        ws,
        test_audit.SOURCES,
        normalize_request(mode="audit", synthetic=True, title="Horta — auditoria"),
        baselines=["baseline.json"],
    )
    read_all(aud)
    submit_claims(aud, claims_payload(aud))
    submit_review(aud, test_audit._audit_review(aud))
    finalize(aud)
    _copy(aud.path("output"), out / "audit")

    ws = make_workspace(tmp / "cmp")
    (ws / "left.json").write_text(json.dumps(test_compare.LEFT), encoding="utf-8")
    (ws / "right.json").write_text(json.dumps(test_compare.RIGHT), encoding="utf-8")
    cmp_ = start(
        tmp / "cmp" / "out",
        ws,
        test_compare.SOURCES,
        normalize_request(mode="compare", synthetic=True, title="Horta — comparação"),
        baselines=["left.json", "right.json"],
    )
    read_all(cmp_)
    submit_claims(cmp_, claims_payload(cmp_))
    submit_comparison(cmp_, test_compare.payload(cmp_))
    finalize_comparison(cmp_)
    _copy(cmp_.path("output"), out / "compare")
    lib = library_fixture.designed_run(
        tmp / "lib", formats=["md", "azure"], profile="azure-agile", title="Biblioteca do bairro"
    )
    submit_review(lib, library_fixture.review_payload(lib))
    finalize(lib)
    _copy(lib.path("output"), out / "readiness")

    team = test_team_planning._input()
    team["actual"] = {"source": "snapshot.json", "assignees": {test_team_planning.T[5]: "dev-a"}}
    doc = plan(test_team_planning._backlog(), team)
    (out / "plan").mkdir(parents=True, exist_ok=True)
    (out / "plan" / "sprint-plan.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (out / "plan" / "plan-report.html").write_text(
        render_plan_report(doc, "Plano de sprints (sintético)", "pt-BR", "examples"), encoding="utf-8"
    )
    (out / "README.md").write_text(
        "# Example reports (synthetic)\n\n"
        "Fixture reproductions built by `python tools/build_examples.py` from the test-suite payloads of a\n"
        "fictional community-garden domain (plus a fictional neighbourhood library and a two-developer team\n"
        "plan for the readiness and planning views). They are not agent-led executions and carry no\n"
        "real data.\n\n"
        "- [generation](generate/report.html)\n- [audit of an existing backlog](audit/report.html)\n"
        "- [comparison of two backlogs](compare/report.html)\n"
        "- [generation with a blocking question and development readiness](readiness/report.html)\n"
        "- [team sprint plan: owners, assignees, load by person](plan/plan-report.html)\n\n"
        "Open a `report.html` with a double click: it works offline from `file://`.\n",
        encoding="utf-8",
    )
    print(f"examples written to {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "examples" / "reports")
