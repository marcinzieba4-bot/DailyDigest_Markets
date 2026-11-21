# mapp_strategy handoff

The [fixed 25% full-coverage backtest](strategies/mapp_strategy/backtests/2022_2026_no_gaps_fixed25/README.md) is the latest reference for the unhedged `absolute_reserved` / `unhedged25` strategy. It uses 1,281 reports through November 20, 2026, with no missing weekdays or months, and records +22.31% net return, −3.55% maximum closing drawdown and 55 funded baskets. The report links to the trade ledger, daily equity, recovery episodes and exact risk metrics.

The [stop-loss test](strategies/mapp_strategy/backtests/2022_2026_stoploss_sensitivity/README.md) re-simulates that `unhedged25` book with −5%, −8% and −10% stops, as resting orders and as close-based stops. All other rules, signals and baskets stay fixed. None of the six variants beat no stop; the −8% resting order came closest (+22.01%, −2.93% maximum drawdown). Run it with `python mapp_strategy.py stoploss-sensitivity --root <completed extended-history directory>`. With stops off, `ci/stoploss_sensitivity.py` must reproduce the engine's daily equity and the published fixed-25% statistics before it writes anything. It reads prices through the frozen `engine/data.py` helper and does not import or modify the economic simulator `engine/run_nohedge.py`.

Start with [the strategy README](strategies/mapp_strategy/README.md) and [the gate/clock comparison](strategies/mapp_strategy/backtests/2022_2026_relative_clock/README.md). The [original extended-history report](strategies/mapp_strategy/backtests/2022_2026_month_gaps/README.md) remains an immutable older snapshot.

The original saved profile runs from 3 January 2022 through 20 November 2026. It compares unhedged25, dollar_short25 and beta40_daily_short25 on one continuous source calendar, using 1,171 validated reports. Missing months block new theme entries; existing positions retain their normal exits and hedge management. The five gaps are July–October 2023 and May 2024.

The newer gate/clock experiment uses 1,192 reports because July 2023 is now available. Its four gaps are August–October 2023 and May 2024. It compares absolute/relative SMA20 and pre-gate/fill-only reservation across all three unchanged hedge policies. Fixed-short returns are +2.64%, −3.86%, +4.41% and −10.20% respectively. Do not replace the saved original results with this refreshed control or call the combined proposal an improvement.

Run `python mapp_strategy.py relative-clock --start 2022-01-01 --end 2026-11-20 --workers 12` in a fresh checkout. New components are `ci/run_relative_clock.py`, `ci/relative_clock_audit.py` and `ci/relative_clock_outputs.py`. They share one immutable campaign, independently verify all four schedules and twelve ledgers, retain rejected-candidate logs and export simulated data only. The economic simulator and mapping are unchanged.

## Implementation

- `strategies/mapp_strategy/mapp_strategy.py`: named command entry point.
- `strategies/mapp_strategy/ci/run_extended_history.py`: public archive inventory union, source identity normalization, explicit monthly entry mask, fixed-book execution and result export.
- `strategies/mapp_strategy/ci/extended_input_audit.py`: independent raw source/price, mapping, clock and eligibility checks.
- `strategies/mapp_strategy/ci/extended_outputs.py`: independent financial audit, chart and approved result package.
- `strategies/mapp_strategy/engine/run_nohedge.py`: unchanged economic simulator. Use the named adapter rather than its historical wrapper.
- `strategies/mapp_strategy/engine/data.py`: unchanged completed-bar indicators and core calendar functions.
- `strategies/mapp_strategy/source_tools/frozen_mapping/`: frozen stock/ETF map; `sector_mapping.csv` exposes its 153-stock crosswalk.
- `strategies/mapp_strategy/ci/independent_ledger.py`: independent orders, physical positions, cash/NAV, fees, borrow, beta and recovery reconstruction.

The complete GC=F identity is normalized to GLD in the extended adapter. Other unsupported complete futures remain unmapped; the F suffix must not become Ford. This was fixed before viewing the extended returns. The economic simulator and static crosswalk bytes remain unchanged.

## Reproduction and interpretation

Run `python mapp_strategy.py extended-history --start 2022-01-01 --end 2026-11-20 --workers 12` from the strategy directory after installing requirements, using a fresh checkout without prior result files. Inputs are fetched once, checked and frozen before simulation. Raw reports and prices remain local; public packages contain only simulated outputs and validation metadata.

Availability at printed-date end of day in New York is a retrospective assumption. Do not describe this replay as verified point-in-time history or untouched live validation. Inventories identify dates only, and full canonical HTML supplies each signal. The current index once dropped later links; the pinned earlier public inventory plus recent probes prevents those known reports from becoming false gaps.

Keep the source allocation, trend/liquidity checks, reserved wait, original leg weights, ten-session exit, 21-day cap, costs and hedge policies fixed when reproducing this result. No RSI, weekly filter, stop or new regime was added. Source SPY and shorts are allowed; only the conceptual hedge must be SPY short or flat. Net same-symbol positions before fees and borrow.

The older nine-book calendar/recorded-fixture comparison remains a separate reference profile. Its saved 25-trade records are historical results, and its code is not the completed extended-history run. Avoid mixing those benchmark rows with the new 54-trade accounts.
