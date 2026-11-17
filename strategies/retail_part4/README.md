# Part 4 retail strategy

The main research policy is `unhedged25`: trade the fourth positional topic in **What Retail Is Playing**, using the frozen ETF mapping, original daily SMA20 and liquidity gates, a 25% source entry budget, and ten-session scheduled exits. The reservation calendar and full-flat wait are part of the strategy. No RSI, weekly filter, stop or take profit is added.

The last completed simulation covers **3 September 2024–30 October 2026**, with 25 baskets per account:

| Policy | Net return | Maximum drawdown |
| --- | ---: | ---: |
| No SPY hedge | +16.57% | 2.23% |
| Fixed-dollar short SPY | +8.89% | 3.40% |
| Daily beta40 short-or-flat SPY | +6.35% | 4.12% |

These are historical replay results after modeled order fees and borrow. The unhedged account retains positive market exposure; its realized market beta was +0.154 on active days. Early report publication times are assumed for reconstructed archive editions.

The requested extension starts **1 November 2023** and retains the **30 October 2026** endpoint. **No November-start portfolio result has been calculated or validated.**

## Availability probe

`ci/availability_probe.py` checks public report endpoints and SPY price-history coverage from a GitHub-hosted runner. It records HTTP status, object metadata, byte digests, retail-section/card counts and price-bar counts. It does not calculate trading returns.

The workflow uses public HTTP requests without AWS credentials. Its result is written to `availability_probe.json` on this research branch when the branch has not advanced, and retained as a GitHub Actions artifact.

## Original code import

The previously audited executable package and frozen mapping are not yet imported into this repository. They remain in the author's saved research workspace and Library archives. This probe and summary must not be represented as the complete executable strategy.

The full simulator, fixed mapper, source version records, price vintage, ledgers, independent audit and reproducible charts must be imported and checked before claiming that the extended simulation reproduces the original research.
