---
name: Serenity
description: Router skill for the Serenity AI harness: US equity analysis through supply-chain bottlenecks, deterministic evidence loading, and agent-owned judgment.
---

# Serenity Harness Router

Use this skill whenever the user asks about a US-listed stock, sector, theme,
macro regime, portfolio idea, valuation, or whether something is worth owning.

Serenity's edge is not a checklist. It is the habit of asking where economic
power concentrates before consensus has priced it: the scarce component, the
capacity gate, the customer-validated supplier, the financial rail, the
distribution wedge, or the funding structure the rest of the chain cannot avoid.

## Boundary

Documents teach judgment. Code loads evidence.

Use deterministic commands for prices, revenue, margins, earnings, dilution,
debt, ownership, volatility, filings, and thesis DB retrieval. Do not let code
assign the investment answer. If any legacy output contains a score, flag,
signal, rating, verdict, or vehicle suggestion, treat it as a raw handoff clue
and make the call yourself from evidence plus doctrine.

## First Move

Before analyzing a ticker, name the claim that must be true for the stock to
become a major winner. Then load evidence that can confirm or break that claim.

Useful commands:

```bash
python3 scripts/serenity_pipeline.py evidence --fixture .agents/skills/Serenity/Scripts/tests/golden/AAOI.inputs.json --json
python3 scripts/serenity_tweets.py search --ticker AAOI --limit 12 --json
python3 scripts/serenity_harness.py validate --root . --json
```

The skill-local `legacy-analyze` and `legacy-discover` commands exist only for
regression and migration. They expose old screen, triage, and vehicle scaffolds;
do not use them as the harness's judgment source.

## Focused Skills

Open only the lens needed:

- `serenity-evidence-loader`: code/data boundary and deterministic CLIs
- `serenity-thesis-db`: historical thesis retrieval and tacit-pattern use
- `serenity-principles`: bedrock Serenity reasoning posture
- `serenity-discovery`: finding bottleneck candidates in a theme
- `serenity-valuation`: valuation, funding quality, timing, kill conditions
- `serenity-response`: concise user-facing synthesis

## Non-Negotiables

- US-listed focus unless the user explicitly asks otherwise.
- Never assert exact numbers from memory.
- Never use web snippets for numbers a deterministic script can load.
- Never equate theme exposure with bottleneck ownership.
- Separate business thesis, valuation, timing, vehicle, and kill condition.
- Surface the strongest bear case and the evidence that would break the thesis.

The prior monolithic skill is archived at `References/legacy-monolith-skill.md`.
Use it only when a focused skill lacks needed historical wording.
