# Part 4 Strategy Handoff

The public strategy implementation is documented in [strategies/retail_part4/README.md](strategies/retail_part4/README.md). It compares three unchanged hedge policies on three explicit report schedules, with the input freeze and an independent accounting audit carried alongside the results.

## Start here

| Item | Purpose |
|---|---|
| strategies/retail_part4/README.md | Trading rules, scope, price conventions and reproduction |
| strategies/retail_part4/engine/run_nohedge.py | Recovered economic simulator; preserve its core accounting semantics |
| strategies/retail_part4/engine/data.py | Completed-bar indicators, eligibility and reserved report calendar |
| strategies/retail_part4/ci/independent_ledger.py | Independent physical-order, cash/NAV, borrow, beta and recovery verification |
| strategies/retail_part4/ci/check_study.py | Input preflight and validation entry point |
| Input and price manifests | Pin the source editions, current price snapshot, case configuration and code used for a run |

The recovered simulator file contains its historical wrapper. Use the current study adapter documented by the workflow; do not call a legacy three-book wrapper that expects an old local baseline directory.

## Fixed experiment

Run the November 2023 continuous schedule, the September 2024 current-archive schedule and the recorded 25-signature September fixture, each under unhedged25, dollar_short25 and beta40_daily_short25. Keep the source allocation at 25% of opening NAV, the original SMA20/liquidity checks, reserved wait and ten-session exit. Do not add RSI, weekly, stop or new sizing parameters.

The recorded fixture is repriced on the current snapshot. Historical recorded trade and order CSVs are reference records; their old prices, units, fees and PnL are not assertions for the fresh run. Treat current report-edition and start-calendar effects separately from hedge-policy effects.

Source SPY positions and source shorts are valid if produced by the frozen map. Only the conceptual hedge must remain short or flat. Net source and hedge units in the same physical SPY instrument before charging fees or borrow. Preserve the simulator’s physical-exposure definition of active_day, which differs from a conceptual held window when source SPY and hedge SPY cancel.

## Validation sequence

1. Pin the report files, extraction/mapping rules, price responses, configuration and code.
2. Prepare source calendars without calculating portfolio outcomes.
3. Run preflight and save its receipt against research_freeze.json.
4. Run only the fixed case/policy combinations.
5. Rebuild the accounts independently and verify the frozen hashes.
6. Inspect total return, drawdown, gross exposure, market beta, fees/borrow and first versus sustained recovery.
7. Export charts and ledgers with their source/price provenance.

The independent module writes detailed trade attribution locally. Console output contains aggregate counts and summary metrics. No brokerage orders are placed.

## Continue the work

Use the exact commands in strategies/retail_part4/README.md. prepare_study.py builds the three schedules and freezes inputs without portfolio returns; run_study.py calls the unchanged simulate() only after a matching independent preflight. The CI execution flag remains off while May 2024 source coverage is unresolved. Do not bypass that missing-source gate.

Start with the README’s reproduction section, then check the matching input freeze and preflight receipt. Do not claim a fresh adjusted-price replay is byte-identical to an old price vintage. Do not describe reconstructed report dates as verified historical publication times or the additional history as untouched live validation.

When changing a rule, create an explicit new experiment before reading its outcomes. For a backward extension under unchanged rules, retain the full continuous reservation calendar and report any changed later trade dates.
