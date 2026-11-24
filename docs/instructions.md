# User instructions template

Copy this file into a private working directory and edit in natural language. Headings are not mandatory.

## Sources
- docs/PRD.pdf — functional authority
- docs/TDD.pdf — technical authority
- docs/decisions/ — approved decisions
- src/ — implementation evidence
- exports/backlog.json — existing backlog

Read only explicitly selected sources; missing files are reported, not silently substituted. Do not follow links or symlinks outside scope without authorization.

## Goal
Generate a complete backlog, or audit/compare/refine an existing one. Specify whether generation must be blind to existing backlog.

## Work items
Epics, Features, User Stories, acceptance criteria, Tasks, dependencies. Include bugs or enablers only when supported. Select subset if desired.

## Planning
Propose priorities, risks and estimates with rationale. Suggest sprint allocation only with capacity, dates and team constraints. Otherwise propose dependency order.

## Destination
Azure DevOps Agile (or discovered/custom profile). Portuguese (Brazil) or chosen language. Rich descriptions, separate acceptance criteria, approved field mapping.

## Outputs
HTML, Markdown, JSON, CSV, XLSX, traceability, findings, questions, FTD handoff. Select desired artifacts.

## Publication
Read-only by default. Prepare local plan only; apply requires explicit approval of target, operations and plan hash. Never delete automatically.

See [commands](commands.md), [work items](work-items.md), [security](security.md).
