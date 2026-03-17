---
name: benchforge-report-planner
description: Analyze BenchForge HTML or text reports and convert them into prioritized, repo-aware refactoring briefs. Use when a user provides a BenchForge report, asks how to act on BenchForge findings, wants a refactoring roadmap, or wants BenchForge results mapped to concrete work in the current repository.
---

# BenchForge Report Planner

Analyze BenchForge reports in the context of the currently open repository. Treat the report as an input signal, not as ground truth.

## Workflow

1. Read the BenchForge report or the extracted report text.
2. Identify the highest-signal findings and deduplicate overlapping points.
3. Group findings into practical buckets:
   - correctness and reliability
   - test gaps
   - complexity and maintainability
   - performance
   - security or dependency risk
   - architecture hotspots
4. Map each important finding to real code areas in the current repository before recommending implementation work.
5. Separate evidence from inference:
   - Mark what the report explicitly says.
   - Mark what you infer from the repository.
   - Mark what still requires validation.
6. Produce a refactoring brief that is specific enough for implementation.

## Report Intake

Accept any of these inputs:

- a pasted BenchForge report summary
- a local HTML report file path
- a report stored under `HTML_reports/<repo-name>/`
- extracted markdown or plain text from the report

If the user provides only an HTML path, read the file and extract the useful findings before planning.

If multiple reports exist for the same repository, prefer the newest one unless the user asks for comparison across runs.

## Planning Rules

- Prioritize user impact, correctness, security, and regression risk ahead of cleanup.
- Prefer small, verifiable improvement waves over large rewrites.
- Do not recommend an architecture rewrite unless the evidence is strong.
- Do not claim exact file-level fixes without checking the repository.
- Flag low-confidence findings instead of overstating them.
- When two findings share the same root cause, propose one combined fix track.

## Refactoring Brief Output

Always produce these sections:

1. Executive summary
2. Prioritized findings
3. Quick wins
4. Refactoring tracks
5. Code hotspots to inspect
6. Risks and assumptions
7. Verification plan
8. Handoff for repo implementation

Keep the handoff compact and actionable. For each recommended track, include:

- reason
- expected benefit
- implementation risk
- likely code area
- tests or checks needed

## Repository Validation

Before suggesting implementation order, inspect the repository and validate:

- whether the reported issue still appears current
- which files or modules are actually involved
- whether tests already cover the risky path
- whether the fix belongs in code, config, or CI

If repository evidence contradicts the report, say so clearly and explain the mismatch.

## Using Stored HTML Reports

When BenchForge archives reports under `HTML_reports/<repo-name>/`, use that folder as the first place to look for recent reports tied to the current repository.

If the repository name and the report folder name do not match exactly, say that the report-to-repo mapping needs confirmation before planning.

## Template

Use the brief template in [references/refactoring-brief-template.md](references/refactoring-brief-template.md) when the user wants a full plan or a reusable handoff.
