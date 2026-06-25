# Pipeline Audit — Evidence-Only Refactor Checklist (WF3 input)

Code root: `scripts/` (was `.claude/skills/Serenity/Scripts/`). Entry: `scripts/pipeline/__main__.py`. Boundary law: **code loads evidence; the agent judges.** The `evidence` command is the target path and is already ~85% clean — its `_pick` allowlist + `_top_holders_without_labels` + the dossier deliberately exclude most module verdicts. The refactor is surgical, not a rewrite.

## CLI surface (current → target)
- `evidence --fixture <inputs.json> [--ticker]` — the evidence-only path (target). Has an `evidence_contract` block (`judgment_owner: agent`) + a `_sanitize` guard applied only to `macro_inputs`.
- `legacy-macro` / `legacy-analyze` / `legacy-discover` / `legacy-regress` — the OLD judgment-laden path. **Target:** move the whole legacy judgment layer (`_signals.py`, `_health.py`, `_control.py`, `_macro.py` classification, the legacy commands) into `scripts/pipeline/legacy/` (isolate now, delete after validation builds trust — user's choice). The CLI entry `serenity_pipeline.py` becomes the clean wrapper exposing `evidence` (+ `macro` evidence-only).

## The 4 live judgment-leaks in `evidence` output (fix these)
1. **`macro_inputs.regime` / `risk_level` / `regime_thresholds`** — `_macro.py:9-110` `_classify_macro_regime` assigns risk_on/off/transitional + high/elevated/moderate/low by threshold-counting. `_sanitize`'s FORBIDDEN set doesn't list them so they pass through. **Fix:** build `macro_inputs` from the raw `signals` dict only (erp_pct, vix_spot, vix_structure numbers, net_liq_direction, fear_greed score, real_rate, bdi/dxy z-scores). Regime classification is the agent's call.
2. **`market_structure_inputs.institutional_holders.breakdown`** — `institutional_quality.py:180-195` `_classify_holder` buckets holders passive/long_only/hedge/quant_mm via keyword lists (brittle, opinionated; UNCLASSIFIED is often the largest bucket). **Fix:** drop `breakdown`; keep `total` + the label-free `top_holders` (name + shares) that `_top_holders_without_labels` already emits. The agent classifies holders itself. (The module's `io_quality_score` 1-10 is already correctly excluded.)
3. **`catalyst_inputs.earnings_history...recent_events[].confidence`** — `events.py:166` buckets high/med/low on count of regex hits. **Fix:** drop `confidence`; surface `supply_chain_relevance` (the matched patterns). `event_type` (the 8-K Item code) and `context` are objective facts — keep.
4. **`surprise_history[].beat` (borderline)** — `surprise.py:252` trivial `actual>estimate`. **Fix (optional):** drop; keep estimate/actual and let the agent read the sign.

## Dead / duplicate (delete)
- **`filing_evidence.legacy_extracted_terms`** (`_evidence.py:76-89` `_legacy_sec_terms`) — targets enum keys (`critical_input`, `key_suppliers`...) that no longer exist in the current `SerenitySupplyChain` schema; returns `{}` in practice. Superseded by `dossier`. Delete.

## Schema bloat (collapse)
- `catalyst_inputs` carries three overlapping nested matrices: `analyst_revisions` (eps_revisions+eps_trend+growth_estimates) + `earnings_estimate` + `revenue_estimate` — ~120 leaf fields of 0q/+1q/0y/+1y × low/high/avg/yearAgo/growth/numberOfAnalysts. **Fix:** collapse into ONE `by_horizon` view (reuse `_postprocess._clean_analyst_revisions` minus its `trend_direction` label): per horizon keep current vs 30d/90d-ago EPS/rev numbers + net up/down revision counts. Drop low/high bands + numberOfAnalysts. ~120 → ~24 fields.
- `key_facts.grossMargins`/`operatingMargins` (yfinance TTM) duplicate the precise per-quarter `fundamental_inputs.margins` — drop the TTM pair from key_facts.
- `recent_events[].context` (≤400-char 8-K excerpt × N) — load-bearing (only place the filing's words appear for events); keep but cap length.

## Add (DB correction A2 — the real valuation lens)
- Surface raw **EV/Revenue** and **EV/FCF** (compute from EV + revenue + FCF already loaded) as evidence. The *banding vs peers/chain* is agent judgment (serenity-valuation doctrine). The `no_growth` block (fair_value, margin_of_safety_pct) stays as ONE deterministic anchor — it is the correct template: keep the floor arithmetic, exclude the `stress_test` pass/fail verdict (already excluded).

## Module-level judgment helpers (delete at source when modules become pure)
All already excluded from `evidence` (not `_pick`ed), but baked into modules + the legacy path. Deleting at source de-risks the allowlist from future accidental re-inclusion:
`margin_tracker.flag`; `sbc_analyzer.flag`/`dilution_flag`/`sbc_interpretation`; `debt_structure.debt_quality_grade`/`debt_health`/`grade_interpretation`; `iv_context.interpretation`/`iv_tier`/`iv_regime_shift`; `institutional_quality.io_quality_score`/`CATEGORY_SCORES`; `growth.*_accelerating`/`overall_trend`; `info.short_interest.contrarian_signal`/`si_trend`; `surprise.cockroach_effect`; `no_growth_valuation._determine_stress_test`.

## Caveat — regression harness
`legacy-regress` asserts on `screen_score`, `pre_commercial`, `screen_component_keys` (`_regression.py:97,133-139`) — products of `_build_objective_screen`. Re-target the golden harness onto stable EVIDENCE invariants (dossier presence, raw revenue_status from `totalRevenue`, margin/debt raw values, no_growth floor arithmetic) BEFORE removing the screen, so we keep a regression guard through the refactor.
