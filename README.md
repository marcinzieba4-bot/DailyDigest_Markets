# DailyDigest_Markets

## mapp_strategy — mapped-sector retail themes

The strategy is isolated in [strategies/mapp_strategy](strategies/mapp_strategy/README.md).

- [Named entry point](strategies/mapp_strategy/mapp_strategy.py)
- [153-stock sector crosswalk](strategies/mapp_strategy/sector_mapping.csv)
- [Frozen mapping implementation](strategies/mapp_strategy/source_tools/frozen_mapping/map_retail_etf.py)
- [Handoff and reproduction](HANDOFF.md)

It uses only Part 4 of “What Retail Is Playing,” the fixed ETF universe, SMA20 entry gate, reserved waiting periods and ten-session holding rule. New simulation outputs are labeled `strategy_id=mapp_strategy`.

The GitHub workflow checks code only. No complete November 2023–November 2026 backtest result is claimed.
