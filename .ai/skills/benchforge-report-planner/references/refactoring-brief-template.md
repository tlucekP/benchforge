# Refactoring Brief Template

## Executive Summary

- Summarize the overall BenchForge signal in 2-4 sentences.
- State whether the main problem is correctness, maintainability, performance, security, or test coverage.

## Prioritized Findings

For each major finding, include:

- `Priority:` High, Medium, or Low
- `Confidence:` High, Medium, or Low
- `Evidence:` What the BenchForge report says
- `Repository context:` What the current code inspection confirms
- `Action:` What should be done

## Quick Wins

- List low-risk, high-value fixes that can usually be done first.
- Prefer tests, guard clauses, config cleanup, dead-code removal, and small complexity reductions.

## Refactoring Tracks

Describe 2-5 tracks such as:

- reliability hardening
- complexity reduction
- test coverage repair
- performance cleanup
- dependency or configuration cleanup

For each track, include:

- `Goal:`
- `Likely code areas:`
- `Change shape:`
- `Risk level:`
- `Verification:`

## Code Hotspots To Inspect

- Name the files, modules, or subsystems most likely involved.
- Mark any hotspot as inferred if it comes from repository inspection rather than the report text.

## Risks And Assumptions

- List unresolved uncertainties.
- Call out any missing repository evidence.
- Note where the report might be stale, partial, or misleading.

## Verification Plan

- unit tests to add or update
- integration scenarios to run
- CLI or build checks to run
- regression cases tied to the findings

## Handoff For Repo Implementation

State:

- the implementation order
- the first safe slice to change
- what to avoid changing yet
- what “done” looks like
