# mapp_strategy handoff

Start with [the strategy README](strategies/mapp_strategy/README.md) and [the completed extended-history report](strategies/mapp_strategy/backtests/2022_2026_month_gaps/README.md).

The current completed profile runs from 3 January 2022 through 20 November 2026. It compares unhedged25, dollar_short25 and beta40_daily_short25 on one continuous source calendar, using 1,171 validated reports. Missing months block new theme entries; existing positions retain their normal exits and hedge management. The five gaps are July–October 2023 and May 2024.

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
