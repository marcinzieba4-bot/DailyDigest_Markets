# mapp_strategy

This directory contains the isolated mapped-ETF strategy named `mapp_strategy`. Its command entry point is `mapp_strategy.py`, and new simulated records carry `strategy_id=mapp_strategy`. Its files and outputs are kept within this strategy directory. The complete 153-stock crosswalk is in [sector_mapping.csv](sector_mapping.csv); the implementation is in [source_tools/frozen_mapping/map_retail_etf.py](source_tools/frozen_mapping/map_retail_etf.py).

This experiment reads only the fourth positional topic in the report section “What Retail Is Playing.” It maps that theme to a fixed ETF universe, applies the existing daily trend and liquidity checks, and holds the funded source positions for the scheduled ten-session window. It compares the same source trade calendar under three SPY hedge policies.

This is retrospective research. Early report editions were reconstructed after their printed dates, and their availability at the printed date’s New York end of day is an assumption. The fixed theme map was designed in later research. Additional historical coverage does not establish that the reports were tradable at those historical times.

## Comparison scope

The fixed study runs through **17 November 2026**, the configured latest completed endpoint. The continuous history starts on **1 November 2023**. It has nine books: three report schedules times three hedge policies. A complete November 2023 backtest has not yet finished; input coverage and independent checks must pass before any new result is described as that full run.

| Schedule | What it measures |
|---|---|
| November continuous | A continuous account starting in November 2023, using the current public report archive and current price snapshot |
| September current | A fresh September 2024 start using the same current archive and price snapshot |
| September recorded fixture | The previously recorded 25 trade signatures, repriced with the current price snapshot |

The recorded fixture retains the earlier report dates, entry and exit dates, instruments and directions. Its repriced NAV is a counterfactual comparison; it does not reproduce an unavailable old report edition or old adjusted-price snapshot. Each book has its own initial capital and compounding. Do not add their ledgers together as one portfolio.

## Signal and calendar rules

1. Use positional Part 4 only. Do not substitute a different retail topic or an older report’s fourth card when that card is absent.
2. Use the frozen 17-ETF map. Unmapped themes remain in cash. Complete unsupported futures identifiers such as PL=F and HG=F stay unmapped.
3. At each potential opening, consider only a report available before that opening and after its printed calendar date. Use the latest ready report, no more than four calendar days old.
4. Keep the original USD/US-session listing checks and prior-20-session median raw dollar-volume floor of $10 million.
5. Reserve an opportunity only when at least one source leg already passes the metadata, entry-price and liquidity checks. Form that reserved window before applying the directional SMA20 gate. For a long source leg, the previous completed close must exceed the mean of the previous 20 completed closes; reverse that comparison for a short source leg. A rejected leg’s share remains cash.
6. Preserve the reservation even if no source leg passes the trend gate. After a window releases, skip the release session and the following session; the next opportunity can occur two sessions after release. Do not reuse the same report.
7. Allocate up to 25% of the book’s own opening NAV to the source positions, including their budgeted entry fee. Each funded leg retains its original share of that budget. Source units stay fixed within the trade.
8. Exit at the tenth subsequent session opening, within the 21-calendar-day cap. Liquidate any unfinished terminal trade at the final close and flag it as censored.

There is no RSI filter, weekly filter, new macro gate, stop loss or take profit. Starting earlier can change later reserved entry opportunities. A longer run must therefore be simulated continuously rather than joined to an old equity curve.

The fixed universe is EPOL, GLD, IEF, QQQ, SOXX, SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV and XLY. These are research instruments; mapped ETF payoffs do not equal the original named stocks’ or commodity contracts’ payoffs.

## Hedge policies

| Policy | Rule |
|---|---|
| unhedged25 | Add no SPY hedge. Retain the same source budget and reserved calendar. |
| dollar_short25 | At source entry, short SPY for the positive part of the signed source entry dollars. Hold those hedge units until source exit. |
| beta40_daily_short25 | At every held opening, estimate each source ETF’s beta from 40 completed daily returns using 41 closes ending before that opening. Short SPY for the positive part of total current signed source dollars times those lagged betas. Rebalance only SPY. |

The hedge is always short or flat. A source theme can itself map to SPY or to a short ETF position. “Unhedged” means no conceptual hedge; it does not require zero physical SPY holdings or zero borrow. Source SPY and hedge SPY are netted before physical orders, fees, exposure and borrow are calculated.

Source units are fixed within each trade. Units can differ across the three books at later entries because each book compounds its own NAV. Removing a hedge does not increase the source allocation to 50% or 100%.

## Prices and accounting

The price snapshot stores raw and adjusted closes, raw opens, volume and adjusted synthetic opens calculated as raw open times adjusted close divided by raw close. Provider adjustments include dividends and splits. Preserve the exact snapshot and its manifest when reproducing a run.

Costs are 10 basis points per net physical order and 3% annual borrow on actual negative net physical positions, using the model’s saved opening and closing accrual convention. Cash earns zero. There is no gross-exposure cap or additional funding model. Taxes, broker margin, debit financing and historical lending availability are outside the simulation.

The beta policy can create substantial gross exposure, and the short-or-flat constraint can leave residual beta. None of the three implementations guarantees strict market neutrality. Return differences must distinguish retained market exposure, hedge PnL, fees, borrow and the effect of compounding source capital.

## Independent checks

The independent ledger module imports no production simulator. It rebuilds physical orders, netted holdings, cash, borrow, NAV, source/hedge attribution, sampled opening and closing exposures, lagged beta estimates and recovery dates. It also verifies every conceptual held-opening diagnostic, including fully netted SPY source/hedge windows.

Recovery statistics distinguish initial capital, each account’s running peak known through 4 April 2025, the corresponding fixed-dollar account’s common target, and the full-sample maximum drawdown episode. First recross and a recross sustained through the observed sample are separate. Sustained recovery is descriptive hindsight, not an entry signal.

Inspect the source availability, source mapping, price coverage, input freeze and accounting audit before interpreting the PnL. A successful fresh run is not evidence of old-price-vintage identity.

## Reproduction

Use Python 3.12. From the repository root:

~~~bash
cd strategies/mapp_strategy
python -m pip install -r requirements.txt
python mapp_strategy.py --help
python mapp_strategy.py fetch
python mapp_strategy.py prepare
python mapp_strategy.py preflight
~~~

The public CDN currently returns an HTTP-200 page whose body says 404 for May 2024. Do not skip these reports or count them as no-theme cash. A supplied retail collection can remain local and be parsed generically: in a local copy, set protocol.source_collections to map its local relative path to {sha256, start, end}. The fetch helper passes those runtime values to the collection parser; no protected collection fingerprint or report contents are embedded in the code. The complete nine-book November experiment remains unrun until the complete source snapshot passes independent preflight.

After complete source coverage and an independent preflight pass, an explicit research GO permits:

~~~bash
study_freeze_sha=$(python -c "import hashlib;from pathlib import Path;print(hashlib.sha256(Path('research_freeze.json').read_bytes()).hexdigest())")
python mapp_strategy.py backtest --execute --expected-freeze "$study_freeze_sha"
python mapp_strategy.py audit
python mapp_strategy.py plot
python mapp_strategy.py export
~~~

The same job keeps raw inputs locally from fetch through freeze and simulation; it does not refetch after freezing. Public results contain authorized simulated ledgers, aggregate checks and charts. Raw HTML archives, full market-response files and source excerpts are not public output artifacts.

The historical recorded trade/order CSVs are under benchmarks/september_2024_recorded. The recorded fixture is reconstructed from those economic records, not an exact copy of the original prepared JSON or an old price vintage. A fresh source/price snapshot must retain its own hashes and timing assumptions.

The separate command `python mapp_strategy.py recorded-controls --execute` reprices only the already recorded 25-decision fixture under the same three hedge policies. It reads no report archive and writes to `recorded_controls/`. It is not the continuous November 2023 backtest. The ordinary nine-book source-coverage gate remains unchanged.

The command wrapper forwards trailing arguments to the existing component scripts. It does not fetch during simulation, remove execution guards, publish files, select a different strategy, or optimize parameters. `python mapp_strategy.py COMMAND --help` shows a component's options.

## Repository checks

The `mapp_strategy code checks` workflow compiles the code, checks the command entry points, validates the sector crosswalk and runs the synthetic source-format checks. It fetches no market data and executes no backtest. Historical execution is an explicit local command using the required inputs.
