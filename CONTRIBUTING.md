# Contributing to BenchForge

Thanks for contributing to BenchForge.

BenchForge is built as a practical tool for the AI coding era: deterministic first, honest about limitations, and focused on useful signal over noisy verdicts. This guide explains how to contribute in a way that fits the project.

## Before You Start

Please read these documents first:

- [`README.md`](README.md) for the product overview and quick start
- [`docs/scoring.md`](docs/scoring.md) for the scoring model and terminology
- [`docs/design_rulebook.md`](docs/design_rulebook.md) for project philosophy and design principles
- [`docs/roadmap.md`](docs/roadmap.md) for current direction
- [`docs/plugin_guide.md`](docs/plugin_guide.md) if you want to add language support

## What Kind of Contributions Are Helpful

BenchForge welcomes contributions such as:

- bug fixes
- clearer documentation
- better examples
- scoring improvements that stay transparent and configurable
- lower-noise static analysis rules
- benchmark scenarios
- UX improvements for CLI, reports, and output readability
- language-support groundwork that fits the existing architecture

## What BenchForge Optimizes For

When contributing, keep these priorities in mind:

- **Deterministic before AI**: AI can explain results, but should not invent or change them.
- **Signal over verdict**: the tool should help people review code, not pretend to replace judgment.
- **Low noise**: false positives are sometimes unavoidable, but avoid adding rules that create lots of shallow noise.
- **Transparent scoring**: weights, penalties, caps, thresholds, and scope behavior should be clear and auditable.
- **Beginner-friendly output**: BenchForge should stay understandable to vibecoders and newer programmers.

## Development Setup

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/benchforge.git
cd benchforge
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

If the project has a requirements or packaging workflow in the repo, use that preferred install path. A common local workflow is:

```bash
pip install -e .
```

If you are working on tests or docs, install any extra dependencies used by those workflows too.

## Typical Local Workflow

Run BenchForge against the repository while you work:

```bash
benchforge analyze .
benchforge benchmark .
benchforge report .
```

Useful checks before opening a PR:

- run the relevant tests
- run BenchForge locally if your change affects scoring, analysis, or reports
- review any docs you touched for accuracy and clarity
- check that README and deeper docs still agree with each other

## Documentation Contributions

Documentation quality matters a lot in this project.

When editing docs:

- prefer simple, concrete language
- explain beginner terms when needed
- do not oversell heuristic scoring as objective truth
- keep README focused on onboarding, and put deeper detail in the dedicated docs
- add explicit cross-links when one document depends on another

If you change scoring behavior, update the docs that explain it.

## Code Contributions

### Keep behavior aligned with the project philosophy

Please avoid changes that:

- make scoring feel like a universal truth machine
- let AI outputs override deterministic analysis
- add heavy noise for little signal
- hide important heuristics behind vague wording

### Prefer clear code over clever code

BenchForge is easier to maintain when code is readable and explicit.

Good defaults:

- small focused functions
- clear naming
- comments only where they add real value
- practical error handling
- minimal surprises in scoring logic

### Be careful with scoring changes

If you change any of these, call it out clearly in your PR:

- weights
- penalties
- caps
- thresholds
- scope defaults
- issue detection rules

Explain:

- what changed
- why it changed
- what user-facing effect it has
- what tradeoff it makes

## Pull Request Guidelines

A good pull request usually includes:

- a short summary of the problem
- the change you made
- why the change is correct
- any docs updated alongside it
- before/after examples if output changed

Small, focused PRs are easier to review than large mixed ones.

If your PR changes scoring or issue detection, include at least one concrete example that shows the impact.

## Issues and Discussions

When reporting a bug, try to include:

- what you expected
- what actually happened
- the command you ran
- a minimal code sample or repo snippet if possible
- your OS and Python version if relevant

For feature requests, explain the real workflow problem first. That makes it easier to judge whether the feature fits BenchForge.

## Tests and Validation

BenchForge changes should be validated in proportion to their impact.

Examples:

- a docs-only change may only need a docs review
- a scoring change should include tests or at least a clear reproducible example
- a detector change should show reduced false positives or better signal
- a CLI or report change should be checked from a user perspective, not just at the function level

## License

By contributing to BenchForge, you agree that your contributions will be released under the MIT License used by this repository. See [`LICENSE.md`](LICENSE.md).

## Questions

If something is unclear, open an issue or draft PR with a focused question. Clear reasoning and small examples are more helpful than broad hand-wavy proposals.
