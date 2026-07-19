# Security Policy

## Supported versions

Harness of Serenity is a personal research project with a single active line of development.
Only the current `main` branch receives fixes.

| Version | Supported |
| --- | --- |
| `main` (latest commit) | ✅ |
| `v0.1.0` and earlier tags | ❌ — upgrade to `main` |

## Reporting a vulnerability

**Please do not open a public GitHub issue for a security problem.**

Email **chunghun1@naver.com** with `[SECURITY]` in the subject line.

If you would rather not use email, use GitHub's private vulnerability reporting on the
repository's **Security** tab → **Report a vulnerability**, which keeps the report private until
a fix is published.

### What to include

- What the issue is and why it is a security problem rather than a bug.
- Steps to reproduce, ideally a minimal command or payload.
- The commit SHA or tag you tested against, plus your Python version and OS.
- What an attacker could actually achieve — data exposure, code execution, credential leakage.
- Any suggested fix, if you have one.

### What to expect

This is a solo side project, so no response-time guarantee is offered — but realistically:

- **Acknowledgment** within about a week.
- **An assessment** — accepted, needs more information, or out of scope — after that.
- **Coordinated disclosure.** Please give a reasonable window before publishing. Credit is given
  in the changelog unless you prefer otherwise.

## Scope

### In scope

- Code execution or command injection through any CLI in `scripts/`, including through crafted
  ticker symbols, accession numbers, or fixture files.
- Credential leakage — anything that causes `.env` values (`FRED_API_KEY`, `EDGAR_IDENTITY`,
  X/Twitter session cookies) to be written to output, logs, or committed files.
- Path traversal via `--fixture`, `--db`, or any other path-taking flag.
- SQL injection in `serenity_tweets.py` against `data/analysis_Serenity.db`.
- Unsafe deserialization or evaluation anywhere in the fetch and normalization path.
- A `.claude/hooks/` script that can be induced to execute attacker-controlled input.

### Out of scope

- **Wrong, stale, or missing market data.** Upstream sources (yfinance, FRED, CBOE, SEC EDGAR)
  go down, rate-limit, and change shape. That is a data-quality bug — file it as a normal issue.
- **Investment losses.** See the disclaimer in the [README](README.md). This tool provides no
  advice and guarantees no accuracy.
- Vulnerabilities in third-party dependencies with no exploitable path through this code —
  report those upstream. If there *is* a path through this code, that is in scope.
- Rate limiting or denial of service against public data providers reached by this tool.
- Findings that require an attacker to already have write access to the repository or shell
  access to the machine running it.

## Handling secrets in this repository

Worth knowing before you contribute or fork:

- **`.env` is gitignored and must stay that way.** `.gitignore` ignores `.env` and `.env.*` while
  explicitly re-including `.env.example`. Never commit a real key.
- **`.env.example` is the template** and contains no live values. Keep it that way when adding a
  variable.
- **`EDGAR_IDENTITY` is not a secret** — SEC EDGAR requires a contact string in the User-Agent by
  policy, so it is transmitted with every request by design. If unset, `serenity_filings.py`
  falls back to a default identity containing the maintainer's email.
- **X/Twitter session cookies** (`X_AUTH_TOKEN`, `X_CT0`, `X_TWID`) are listed in `.env.example`
  for an out-of-tree scraper. No code in this repository reads them. Treat them as
  account-takeover credentials if you ever populate them.
- **`data/analysis_Serenity.db` is committed** and contains only public posts. It holds no
  credentials. See [Concepts](docs/wiki/Concepts.md#the-thesis-db) for how it is used.

If you find a committed secret in the history, report it privately using the process above rather
than opening an issue that points at it.
