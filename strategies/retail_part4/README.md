# Retail Part 4 strategy research

This draft publishes the frozen ETF mapping, calendar/data helper, anonymous source and price fetchers, and nine-case renderer. The economic runtime and new November orchestration are being integrated next. **No November 2023 portfolio result has been generated yet.**

The comparison retains the original 25% source entry allocation, directional prior-close SMA20, liquidity eligibility, reserved report windows and ten-session exit. It compares fixed-dollar short SPY, daily 40-return beta short-or-flat SPY, and no SPY hedge. There is no RSI, weekly filter, new stop or optimization grid. Candidate eligibility/liquidity precedes reservation; reservation precedes SMA20. Rejected weights remain in cash, without renormalization.

The requested main history is 1 November 2023 through 30 October 2026. A September 2024 current-clock reset separates earlier chronology from the current source snapshot. Repricing the earlier 25 recorded cohorts is planned separately; the private records and detailed trade/order datasets are not published without specific approval.

The source fetchers use anonymous public report HTML and Yahoo prices. Current response metadata and content hashes are retained separately from assumed historical report availability at printed-date end of day in New York. Reconstructed reports and fresh price vintages are not untouched historical validation.

Only code and aggregate methodology are published at this stage. Data preparation, input freeze and independent review must precede any new portfolio calculation. Detailed inputs/results and write-capable CI publication require their separate authorization. The finished availability workflow is removed from this branch so code changes do not repeatedly trigger it; its source and aggregate probe record remain.
