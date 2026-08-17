---
name: serenity-cohort
description: Compare or rank a cohort of US-listed candidates without a hidden provider score. Use for X versus Y, thematic baskets, peer comparisons, and requests to rank candidates. Do not use for pure discovery with no candidate set or for an isolated ticker unless peer comparison is necessary to test its claim.
---

# Cohort research

## Question frame

Use this mode for X versus Y, a thematic basket, a peer set, or a request to rank named candidates; do not use it for pure discovery with no candidate set or an isolated ticker unless comparison is necessary to test its claim. Start with `"$SERENITY_PYTHON" "$SERENITY_CLI" run start --mode cohort --question "<question>" --subject TICKER --as-of YYYY-MM-DD`, then run `"$SERENITY_PYTHON" "$SERENITY_CLI" run start --help` before adding artifact arguments. Define one common comparison question, cutoff, membership rules, and exclusions before any ordering.

## Competing hypotheses

Ask for a blind challenge to the candidate set without prior decisions or rankings. Keep alternatives explicit: each candidate may own the economic link, be a proxy, have a different binding constraint, or fail the comparison altogether. A shared narrative does not establish comparable exposure or relative superiority.

## Evidence sought

Gather equivalent evidence for each surviving candidate: identity and revenue linkage, customer or supplier relationship, qualification, adoption, substitutability, capacity, capital needs, lens validity, trigger, bear case, and falsifier. Preserve evidence quality and availability gaps alongside the fact. Use later outcomes only with complete time-stamped attribution, including losses and benchmarks, rather than a selected win list.

## Inference

Explain relative fit to the common question: which links are direct, which assumptions differ, and where evidence is stronger or weaker. Provider fields can describe facts but never create an ordering; no hidden score substitutes for comparative judgment. Keep uncertainty beside each comparison and distinguish a cohort ordering from a directional action.

## Action and falsifier

Assign an action only when that candidate’s evidence supports it. Exclude unresolved identities, weak proxy links, and no-clean-vehicle cases rather than forcing a rank. Use `MONITOR`, `PASS`, or `BLOCKED` where relative fit cannot be established, and retain the falsifier that would reorder the cohort: lost qualification, changed vendor share, failed ramp, dilution, or evidence that another node captures the economics.

## Deliverable and hand-off

Deliver a transparent membership and exclusion list, per-candidate facts versus inferences, relative fit, action, trigger, bear case, falsifier, and confidence limit. Hand a chosen name to single-name research for its own decision record; preserve the blind challenge as evidence, never as the final verdict.

Method claims: `claim-03-verify-identity-and-revenue-linkage`, `claim-09-use-milestone-falsifiers-not-price-alone`, `claim-11-evaluate-process-with-complete-attribution`, `aug-adaptive-evidence-not-decision-code`, and `aug-blind-method-and-evaluation-boundary` route comparable evidence, price-independent falsification, outcome discipline, and blind challenge here.
