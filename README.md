# DailyDigest_Markets

## mapp_strategy — mapped-sector retail themes

The strategy is isolated in [strategies/mapp_strategy](strategies/mapp_strategy/README.md), with a named [entry point](strategies/mapp_strategy/mapp_strategy.py) and [153-stock sector crosswalk](strategies/mapp_strategy/sector_mapping.csv).

The completed **January 2022–November 2026 simulation**, including PnL charts, trade mappings and independent checks, is in [the backtest report](strategies/mapp_strategy/backtests/2022_2026_month_gaps/README.md).

Only Part 4 of What Retail Is Playing supplies themes. Source positions use a 25% allocation, SMA20 entry gate, reserved waiting windows and ten-session holding rule; variants compare no hedge, a fixed SPY short and a daily short-or-flat beta hedge. New outputs are labeled `strategy_id=mapp_strategy`.

See [HANDOFF.md](HANDOFF.md) for implementation notes.
