# mapp_strategy

The mapped-sector strategy is isolated in this directory. Its entry point is [mapp_strategy.py](mapp_strategy.py), and simulated outputs use `strategy_id=mapp_strategy`.

## Completed simulation

The latest completed study covers **3 January 2022–20 November 2026**, using **1,171** validated public reports. The three separately compounded accounts start with $100,000 and use the same 54 completed theme trades.

| Variant | Total net return | Maximum drawdown |
|---|---:|---:|
| No SPY hedge | +19.45% | −3.55% |
| Fixed-dollar SPY short | +2.73% | −8.97% |
| Daily beta SPY short or flat | −3.46% | −11.01% |

[Full report, PnL chart and trade mapping](backtests/2022_2026_month_gaps/README.md) · [All trades](backtests/2022_2026_month_gaps/all_trades.csv) · [Result ZIP](backtests/2022_2026_month_gaps/mapp_strategy_extended_simulated_results.zip)

July–October 2023 and May 2024 had no available reports. They generated no new entries; existing positions and hedges kept their normal schedules. Calendar time and the account history remain continuous through gaps.

## Strategy rules

1. Read only the fourth positional topic of **What Retail Is Playing**.
2. Map its heading into the fixed universe: SPY, QQQ, XLK, XLC, XLF, XLE, XLI, XLY, XLP, XLV, XLB, XLRE, XLU, SOXX, EPOL, GLD and IEF. See the [153-stock crosswalk](sector_mapping.csv) and [frozen mapping implementation](source_tools/frozen_mapping/map_retail_etf.py).
3. Require an eligible USD US-session instrument and a median of at least $10 million raw daily dollar volume over the preceding 20 sessions.
4. Reserve the opportunity window before applying the trend gate. The previous completed adjusted close must be above the preceding 20-close SMA for longs, and below it for shorts. Rejected weights remain cash.
5. Allocate up to 25% of opening NAV, including the source entry fee. Keep source units fixed. Hold until the opening of the tenth subsequent US session, with a 21-calendar-day cap. After release, skip the release session and the following session.
6. Use the latest report ready before the opening, at most four calendar days old. Do not reuse a report. Missing months block new reservations and entries, while normal exits continue.

The three policies are no conceptual hedge; a fixed entry-dollar SPY short; and a daily SPY short or flat sized from 40 strictly prior daily returns. A hedge never buys SPY. Genuine source SPY positions and source shorts remain valid. Net same-symbol source/hedge units before charging fees or borrow.

The extended profile fixes complete futures identifiers before frozen mapping: GC=F maps to GLD; unsupported complete futures identifiers stay unmapped so their F suffix cannot become Ford. The static 153-stock dictionary and economic simulator are unchanged.

There is no RSI, weekly filter, new stop, regime filter or parameter optimization. Costs are 10 bp per net physical order, 3% annual ACT365 net-short borrow and zero cash interest. Adjusted synthetic opens are raw open multiplied by adjusted close divided by raw close.

## Reproduce the extended study

Use Python 3.12 and a fresh checkout or copy without existing simulation outputs:

~~~bash
cd strategies/mapp_strategy
python -m pip install -r requirements.txt
python mapp_strategy.py extended-history --start 2022-01-01 --end 2026-11-20 --workers 12
~~~

The runner combines the current archive index, a pinned older public date inventory and recent-date probes. Those inventories supply dates only: every signal is extracted from the full dated report HTML. It freezes the local input hashes, independently checks raw prices, reports, mapping, reservation clock and monthly entry blocking before running the unchanged economic engine. Independent physical-order, cash/NAV, fees, borrow and beta checks run afterward.

Raw inputs stay on the execution machine. `publication/` and `mapp_strategy_extended_simulated_results.zip` contain simulated results and validation metadata only.

Reports are current retrospective reconstructions. Historical availability at printed-date 23:59:59 New York is assumed. The replay does not establish contemporaneous publication or live performance.

## Other components

`python mapp_strategy.py --help` lists the named commands. The older nine-book source-window comparison (`fetch`, `prepare`, `preflight`, `backtest`, `audit`, `plot`, `export`) remains available separately. It is not the completed three-policy extended-history profile above. The historical 25-trade fixture is under [benchmarks/september_2024_recorded](benchmarks/september_2024_recorded/summary_from_records.json).

The code-check workflow compiles code, checks command help, verifies the crosswalk and frozen calculation hashes, and exercises invented source-format inputs. The separate research-branch workflow executes the requested simulation.
