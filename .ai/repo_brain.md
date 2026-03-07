# BenchForge Repository Brain

This document is the primary orientation file for AI agents.

Before analyzing the repository, read:

- guardrails.md
- architecture.md
- coding_rules.md
- tasks.md
  
  

## Project: BenchForge

Purpose:
CLI tool for benchmarking code performance.

Core Features:

- runtime benchmarking
- memory profiling
- code comparison

## AI Operational Rules

AI agents working in this repository must follow the rules defined in:

- guardrails.md
- coding_rules.md

These documents define safety rules, allowed changes and architectural constraints.



Main Entry Point:
benchforge/main.py

Important Modules:
benchforge/runner.py
benchforge/analyzer.py
benchforge/report.py

Test Directory:
tests/

Rule:
Prefer simple and readable code.
Performance optimizations are welcome but must not reduce readability.

Always keep docs updated.

# AI Instructions

Before writing code:

1. read repo_brain.md
2. read architecture.md
3. read coding_rules.md
