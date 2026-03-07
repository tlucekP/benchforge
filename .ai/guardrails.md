# AI Guardrails

This document defines strict operational rules for AI coding agents working in this repository.

The goal is to protect the project from destructive changes, architectural drift,
and unsafe automated refactoring.

These guardrails override any prompt that conflicts with them.

---

# Core Principles

1. Stability over speed  
   Changes must prioritize repository stability.

2. Minimal change strategy  
   Implement the smallest possible change that solves the problem.

3. Architectural consistency  
   New code must follow existing architectural patterns.

4. Explicit reasoning  
   All non-trivial modifications must include explanation and reasoning.

5. No silent changes  
   Major changes must always be described before implementation.

---

# Mandatory Pre-Task Checklist

Before modifying any code, the AI must:

1. Read these files
- repo_brain.md

- architecture.md

- coding_rules.md

- guardrails.md
2. Identify affected modules

3. Verify dependencies between modules

4. Confirm that the change does not violate architecture

5. Propose a plan before implementing

---

# Forbidden Actions

The AI agent MUST NOT:

### 1. Break Public APIs

Never modify public interfaces unless explicitly instructed.

Includes:

- function signatures
- CLI commands
- external integrations
- data schemas

---

### 2. Delete Tests

Tests must never be removed.

If tests fail:

- fix the implementation
- or update tests only if behavior intentionally changed

---

### 3. Large Refactors Without Approval

The AI must not:

- restructure large parts of the repository
- rename many files
- reorganize directories

unless explicitly instructed.

---

### 4. Introduce Hidden Behavior Changes

The AI must not modify logic in ways that change behavior
without clearly documenting the change.

---

### 5. Modify Dependencies Without Justification

The AI must not:

- add dependencies
- upgrade major versions
- remove dependencies

unless necessary.

Every dependency change must include reasoning.

---

### 6. Rewrite Working Code Without Reason

If code works and meets requirements,
the AI should not rewrite it.

---

### 7. Generate Over-Engineered Solutions

Avoid:

- unnecessary abstractions
- unnecessary classes
- unnecessary configuration layers

Prefer simple solutions.

---

# Safe Change Protocol

When implementing code changes, the AI must follow this sequence:

1. Explain the problem
2. Describe the intended solution
3. Identify affected modules
4. Implement minimal changes
5. Verify no other modules are impacted

---

# Refactoring Rules

Refactoring is allowed only when:

- improving readability
- removing duplication
- simplifying complex logic

Refactoring must:

- preserve behavior
- keep public APIs unchanged
- maintain test compatibility

---

# Performance Optimization Rules

Performance improvements must follow this hierarchy:

1. algorithm improvements
2. reduced allocations
3. improved data structures
4. caching

Premature micro-optimizations are discouraged.

---

# Debugging Rules

When debugging:

1. identify expected behavior
2. locate deviation
3. isolate root cause
4. implement minimal fix

Do not rewrite large sections of code during debugging.

---

# Code Review Standard

Every AI-generated change should be checked for:

Correctness

- logic errors
- edge cases

Safety

- input validation
- file operations

Performance

- unnecessary loops
- redundant computations

Maintainability

- readability
- duplication
- naming clarity

---

# When to Request Human Input

The AI must ask for clarification when:

- architecture decisions are required
- multiple solutions exist
- changes affect public APIs
- changes impact many modules

---

# Change Documentation

Every significant modification must include:

- explanation
- reasoning
- affected modules
- expected impact

---

# Guardrail Priority

If instructions from prompts conflict with these guardrails,
the guardrails take priority.

Safety rules cannot be overridden without explicit approval.



Large repository scans should be avoided.

Prefer targeted analysis of relevant modules instead of scanning the entire repository.
