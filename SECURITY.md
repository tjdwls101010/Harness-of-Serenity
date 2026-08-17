# Security Policy

## Supported version

Only the current `main` branch is supported. Historical v1 material is retained as a tagged/archive recovery record, not as a maintained runtime line.

## Reporting a vulnerability

Please do not open a public issue for a security vulnerability, suspected credential exposure, cleanroom escape, or command/path injection issue. Use GitHub’s private vulnerability reporting for this repository through the Security tab’s **Report a vulnerability** flow. Include the affected commit, reproducible steps, impact, relevant sanitized command/output, and any mitigation you identified.

No response-time SLA or disclosure date is promised. The maintainer will assess the report privately and coordinate disclosure when a fix is available.

## Sensitive configuration

`.env` is local configuration and must remain untracked. Never commit, paste into an issue, or include in a test fixture a real provider credential such as `FRED_API_KEY`, `EIA_API_KEY`, `BEA_API_KEY`, `BLS_REGISTRATION_KEY`, `SAM_API_KEY`, `USPTO_API_KEY`, `X_AUTH_TOKEN`, `X_CT0`, or `X_TWID`. The X values are session credentials used only for thesis-corpus scraping and should be treated as account-access secrets.

SEC requests require a contactable user agent through `SERENITY_SEC_USER_AGENT` or legacy `EDGAR_IDENTITY`. These values are not authentication secrets, but they can contain personal contact information; treat them as private configuration and avoid copying them into logs or public reports. `.env.example` contains empty keys only and is the safe template for documenting new variables.

Provider envelopes, saved artifacts, test fixtures, cleanroom packages, and evaluation reports must never serialize environment values. When reporting a provider problem, share the typed availability/provenance result after redacting any sensitive request headers or configuration.

## Cleanroom boundary

Normal local Codex uses the repository’s shared harness through its documented symlink. The E2E candidate arm runs outside the repository from an allowlisted, hash-recorded package containing the user case, typed evidence, and a content-hashed Harness receipt; the inline prompt loads only the root plus family-routed skills, while agents, hooks, settings, and the specification remain receipts rather than model instructions. It excludes provider secrets, the tweet database and media, expected invariants, prior verdicts, sessions, and prior evaluation results. The independent reviewer arm is a separate outside-repository package that excludes all Harness files as well as those answer and history surfaces, and receives only the typed candidate artifact plus evidence permitted by the case contract.

Report any way to read a path outside the active candidate or reviewer allowlist, inject a symlink/path that bypasses package validation, alter a hash-recorded package after validation, expose an evaluator-only invariant to the candidate, expose Harness instructions to a reviewer, or cause a cleanroom transcript to disclose secrets. Data quality, market outcomes, or an unavailable third-party provider are not security vulnerabilities unless they create an exploitable integrity, confidentiality, or execution issue.
