# Harness of Serenity — Build State & Resume Plan

Resume anchor after session compaction. Everything below the "Done" line is committed to GitHub `main`.

## DONE (committed + pushed)
- **Repo**: `scripts/` (code + `.venv`, gitignored), `data/analysis_Serenity.db`, `references/` (build-time only), `.claude/skills/`, `CLAUDE.md`. git + GitHub `tjdwls101010/Harness-of-Serenity` (private, authed via gh). `.gitignore` excludes `.env`/`.venv`/`skill-creator`.
- **CLAUDE.md** (17.9KB / 138L): always-on persona, Claude-first voice, NO DB-ids, NO dev-meta. Carries: identity + 3-shapes, voice (asymmetrical un-banned), code/judgment boundary + CLI forms + gives-vs-judges table, 6 roots/10 values + priority order, funnel + archetype-fork + A>D>B>C>E, routing to the 3 skills, TLDR-sandwich + per-type content, non-negotiables (8) + prohibitions, DB-answer-key rule.
- **3 single-file skills** `.claude/skills/serenity-{discovery,analysis,macro}/SKILL.md` — authored + adversarially cross-verified (coverage/duplication/craft critics). Clean (0 DB-ids/dev-meta), cite-don't-restate the CLAUDE.md spine. discovery 164L, analysis 230L, macro 168L. (per-skill `references/` subdirs were merged in and removed — single-file per user.)
- **scripts/serenity_tweets.py** — thesis-DB CLI (search/get/stats), tested, carries the DB-discipline in its docstring.
- **scripts/pipeline/_evidence.py** `build_evidence` — refactored evidence-only: dropped `regime`/`risk_level` (→ raw `macro_inputs` signals only), institutional `classified_breakdown`, 8-K `confidence`, dead `legacy_extracted_terms`; ADDED `valuation_inputs.ev_multiples` (EV/Rev, EV/FCF). Verified on AAOI fixture (exit 0).
- **references/**: `db-mining-report.md` (corrections A1 voice / A2 EV-multiple banding / A3 GAAP-SBC + B1-B6 + the 12-thesis gold-set §D), `omo-craft.md`, `pipeline-audit.md`, `edgartools-guide.md` (verified vs installed edgartools 5.35.1), `principle-inventories/` (the WF1 inventories).
- Memory: `harness-of-serenity-project`, `serenity-db-discipline`, `askuserquestion-for-questions`.

## ARCHITECTURE (decided with user — do not re-litigate)
- CLAUDE.md = always-on macro persona + spine + routing + non-negotiables. Skills = situational depth, **single-file**, cite-don't-restate the spine.
- **Code loads deterministic evidence; the agent judges.** No flag/signal/score/regime/grade/archetype/verdict computed in code.
- **SEC decision**: REPLACE sec-analyzer (LLM + rigid pydantic schema baked in the pipeline) with — (a) XBRL **numbers** pulled DETERMINISTICALLY via **edgartools** in the pipeline; (b) **narrative** via a `serenity-filings` **subagent** (`.claude/agents/`) that reads filings via edgartools — adaptive (captures the unexpected link), fact-not-judgment, cite the filing. Removes the Gemini/Google dependency.
- `info`: keep numeric key_facts + sector/industry; DROP `longBusinessSummary` prose.
- DB = answer key, explicit cross-validation only (never default/preload).

## CONSTRAINTS (environment + harness)
- **SEC is IP-blocked in the build env (403 on raw curl, both data.sec.gov + www.sec.gov).** So the edgartools/SEC layer is **built from `references/edgartools-guide.md` and verified on the user's machine**. **yfinance works here** (numbers layer live-testable).
- **Workflow subagents CANNOT write files** (`Subagents should return findings as text`). → They return delimited text; the orchestrator parses + writes. (Pattern: `===FILE: path===\n...\n===END===`.)
- **Ask the user via the AskUserQuestion tool**, never a free-text question.
- edgartools 5.35.1 bugs to code around: `EightK.get()` doesn't exist (subscript+guard); `FactQuery.by_value` takes a callable; no top-level `get_company` / `find(form=,ticker=)` (use `Company().get_filings`); MD&A is `.management_discussion`, TenQ lacks named section props. Identity required (`set_identity` / `EDGAR_IDENTITY`).

## REMAINING WF3 (resume here — autonomous via dynamic-workflow)
1. **serenity_pipeline.py** — `analyze TICKER [--skip-macro]` (= fetch → `build_evidence`), `macro` (raw gauges, NO regime classification), `discover TKRS` (comparator). Factor `pipeline/_fetch.py: fetch_payload(ticker, skip_macro)` = macro signals (NO `_classify_macro_regime`) + l4 (info WITHOUT `longBusinessSummary`) + l5 + sec. Reuse the module script defs from `_commands.cmd_analyze` (lines ~192-365). **yfinance-testable here.**
2. **Schema collapse**: `analyst_revisions`+`earnings_estimate`+`revenue_estimate` → one `by_horizon` view (reuse `_postprocess._clean_analyst_revisions` minus its `trend_direction` label). fixture-testable.
3. **serenity_filings.py** — thin edgartools CLI per `references/edgartools-guide.md`: numbers (`company`/`financials`/`xbrl-facts`/`segments`/`statement`) + text (`filings`/`section`/`eightk`/`text`/`context`). JSON-out, possibly-null→null, no LLM/schema. Offline-test (imports/argparse) only.
4. **build_evidence SEC rework**: drop sec-analyzer; pull XBRL numbers (geo/customer concentration, inventory, purchase_obligations) via edgartools into `filing_evidence`; the narrative dossier now comes from the subagent, not the pipeline.
5. **.claude/agents/serenity-filings.md** — subagent: narrative-reading doctrine (relationships / country / critical-inputs / financing structure / recent 8-K events + the confidential-link & unexpected-link mindset; fact-not-judgment; cite the filing) + the edgartools cheat-sheet (from edgartools-guide.md) + serenity_filings.py CLI usage. In the validated CLAUDE.md voice; principle-embodied.
6. **serenity_harness.py validate** — self-check: skills frontmatter present, CLIs importable, CLAUDE.md present, evidence output carries no forbidden judgment keys.
7. **Legacy isolation**: move `_signals.py`/`_health.py`/`_control.py` + `_macro._classify_macro_regime` + the `legacy-*` commands into `pipeline/legacy/`; re-target `_regression.py` golden onto EVIDENCE invariants (dossier presence, raw revenue/margin/debt, no_growth floor, ev_multiples) BEFORE deleting the screen.
8. **Hooks (2)** `.claude/hooks/` + `settings.json` — `evidence_discipline` (UserPromptSubmit injector: equity/macro intent → run pipeline first, no memory-numbers, route to the right skill) + `web_number_guard` (PreToolUse on WebSearch/WebFetch → numbers from pipeline, web for narrative only). **Verify the hook JSON contract first** (claude-code-guide).

## THEN WF4 — validation (the user's capstone ask)
gold-set (`references/db-mining-report.md` §D — 12 theses across archetypes) → a **blind** harness analysis subagent (FIREWALLED from the DB, methodology + deterministic evidence + websearch only) → a **separate** judge subagent compares to the real DB thesis → fidelity/coverage score → gaps feed doctrine patches → loop until convergence. Mirrors skill-creator's with/without eval. Goal: faithfully reproduce serenity's method, more consistently/broadly than he does.
