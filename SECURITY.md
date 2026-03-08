# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in BenchForge, please report it privately rather than opening a public issue.

Use GitHub's private vulnerability reporting:

1. Go to the [Security tab](https://github.com/tlucekP/benchforge/security) of this repository.
2. Click **"Report a vulnerability"**.
3. Describe the issue, steps to reproduce, and potential impact.

You will receive a response as soon as possible. For valid reports, a fix or mitigation will be worked on before any public disclosure.

## Scope

BenchForge is a local CLI tool. It:

- reads files from your local filesystem
- never executes the code it analyzes (read-only AST parsing only)
- makes one optional outbound network call to the Mistral AI API when `--ai` is used — only structured metadata is sent, never source code

The attack surface is intentionally small. The most likely vulnerability classes would be path traversal, malicious file parsing, or unexpected behavior when analyzing adversarially crafted input files.

## Supported Versions

Security fixes are applied to the latest version only.
