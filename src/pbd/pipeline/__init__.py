"""Agent-led run pipeline: deterministic contracts around semantic stages done by the host agent.

start (runtime)      scope → inventory → text extraction → reader assignments → work order
reading (agent)      one logical reader per declared source submits a verified ledger
claims (agent)       orchestrator reconciles reader obligations into atomic claims
design (agent)       hierarchy, stories, criteria, tasks, relations, questions
independent_review   separate source-first reviewer: own obligation inventory + per-item verdicts
finalize (runtime)   canonical backlog → gates (verified evidence) → projections → report
"""
