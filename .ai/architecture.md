# Architecture

BenchForge is a modular benchmarking tool.

Components:

Runner
Executes benchmark tests.

Analyzer
Processes timing results.

Reporter
Generates output reports.

Flow:

benchmark target
→ runner
→ analyzer
→ reporter
