# DailyDigest_Markets

## mapp_strategy — mapped-sector retail themes

The strategy is isolated in [strategies/mapp_strategy](strategies/mapp_strategy/README.md), with a named [entry point](strategies/mapp_strategy/mapp_strategy.py) and [153-stock sector crosswalk](strategies/mapp_strategy/sector_mapping.csv).

The latest [fixed 25% backtest with full archive coverage](strategies/mapp_strategy/backtests/2022_2026_no_gaps_fixed25/README.md) covers January 2022 through November 20, 2026. It includes the risk and recovery statistics, daily P&L chart, and all 55 trades for the unhedged strategy without martingale sizing.

The original **January 2022–November 2026 simulation**, including PnL charts, trade mappings and independent checks, is in [the backtest report](strategies/mapp_strategy/backtests/2022_2026_month_gaps/README.md).

Only Part 4 of What Retail Is Playing supplies themes. Source positions use a 25% allocation, SMA20 entry gate, reserved waiting windows and ten-session holding rule; variants compare no hedge, a fixed SPY short and a daily short-or-flat beta hedge. New outputs are labeled `strategy_id=mapp_strategy`.

The [gate and reservation-clock experiment](strategies/mapp_strategy/backtests/2022_2026_relative_clock/README.md) compares four fixed variants on refreshed 1,192-report history. The combined proposal failed; relative strength alone modestly improved the fixed-short account but remains concentrated in XLE and 2026. It includes all twelve PnL curves, trades and rejected-candidate logs.

See [HANDOFF.md](HANDOFF.md) for implementation notes.
