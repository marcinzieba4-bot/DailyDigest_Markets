# Retrospective yield corrections, Market Intelligence Briefing archive (2026-06-25 to 2026-10-18)

Two systematic errors were removed from all 116 archived reports, using only data available on each report date (official Treasury closes up to the prior business day, plus the live 10Y reading each report already contained).

1. The "US 2Y" was the Yahoo 13-week T-bill (^IRX), not the 2-year note, so every 10Y-2Y spread was overstated by roughly 50 to 80 bps and the curve was described as "normal" or "steep" when it was flat (the long-run average 2s10s is about +90 to +100 bps).
2. Yield changes were quoted as percent of the yield (for example "↑5.8%") instead of basis points (+25 bps).

Rule of thumb for any uncorrected copy you still have: the true 10Y-2Y spread was about a third to a half of the quoted figure, and a quoted "x%" yield move converts to basis points as x% times the yield level (5.8% of 4.49% is about 26 bps).

The "Old 10Y 4W change" column is a best-effort regex extraction from the old text and may occasionally catch a neighbouring figure; the other columns come from the data cards.

| Date | 10Y (live, kept) | Old 10Y 4W change (as printed) | True 10Y 4W change | Old "2Y" (was the bill) | True 2Y (prior close) | Old spread | True 10Y-2Y (prior close) | Curve move vs 4W |
|---|---|---|---|---|---|---|---|---|
| 2026-06-25 | 4.38% | ↓3.8% | -10 bps | 3.68% | 4.11% | +70 bps | +30 bps | flattening (2Y up, 10Y down/flat) |
| 2026-06-26 | 4.38% | - | -7 bps | 3.66% | 4.09% | +72 bps | +31 bps | flattening (2Y up, 10Y down/flat) |
| 2026-06-27 | 4.45% | ↓0.9% | +0 bps | 3.66% | 4.07% | +79 bps | +31 bps | flattening (2Y up, 10Y down/flat) |
| 2026-06-28 | 4.37% | - | -8 bps | 3.66% | 4.07% | +71 bps | +31 bps | flattening (2Y up, 10Y down/flat) |
| 2026-06-29 | 4.38% | ↓1.7% | -7 bps | 3.68% | 4.07% | +70 bps | +31 bps | flattening (2Y up, 10Y down/flat) |
| 2026-06-30 | 4.41% | ↓1.1% | -6 bps | 3.73% | 4.10% | +67 bps | +28 bps | flattening (2Y up, 10Y down/flat) |
| 2026-07-01 | 4.47% | ↓9% | +2 bps | - | 4.14% | +75 bps | +30 bps | flattening (2Y up, 10Y down/flat) |
| 2026-07-02 | 4.49% | ↑0.6% | +0 bps | - | 4.17% | +81 bps | +31 bps | bear flattening (both up, 2Y up more) |
| 2026-07-03 | 4.37% | ↓2.3% | -12 bps | 3.66% | 4.14% | +71 bps | +35 bps | flattening (2Y up, 10Y down/flat) |
| 2026-07-04 | 4.37% | ↑1.2% | -12 bps | 3.66% | 4.14% | +71 bps | +35 bps | flattening (2Y up, 10Y down/flat) |
| 2026-07-05 | 4.49% | - | +0 bps | 3.67% | 4.14% | +82 bps | +35 bps | flattening (2Y up, 10Y down/flat) |
| 2026-07-06 | 4.48% | ↑0.1% | +0 bps | 3.69% | 4.14% | +79 bps | +35 bps | flattening (2Y up, 10Y down/flat) |
| 2026-07-07 | 4.53% | ↑1.0% | -1 bps | - | 4.13% | +80 bps | +35 bps | bear flattening (both up, 2Y up more) |
| 2026-07-08 | 4.58% | - | +3 bps | 3.72% | 4.19% | +86 bps | +36 bps | little changed |
| 2026-07-09 | 4.54% | ↓0.2% | +1 bps | 3.69% | 4.21% | - | +35 bps | flattening (2Y up, 10Y down/flat) |
| 2026-07-10 | 4.56% | - | +2 bps | 3.69% | 4.16% | +87 bps | +38 bps | little changed |
| 2026-07-11 | 4.57% | ↑0.9% | +3 bps | 3.69% | 4.21% | +87 bps | +35 bps | bear flattening (both up, 2Y up more) |
| 2026-07-12 | 4.57% | - | +3 bps | 3.69% | 4.21% | +87 bps | +35 bps | bear flattening (both up, 2Y up more) |
| 2026-07-13 | 4.62% | ↑3.4% | +16 bps | 3.73% | 4.21% | +88 bps | +35 bps | bear flattening (both up, 2Y up more) |
| 2026-07-14 | 4.58% | - | +9 bps | 3.70% | 4.26% | +88 bps | +36 bps | bear flattening (both up, 2Y up more) |
| 2026-07-15 | 4.55% | - | +8 bps | 3.70% | 4.18% | +86 bps | +40 bps | bear steepening (both up, 10Y up more) |
| 2026-07-16 | 4.58% | ↑3.4% | +15 bps | 3.70% | 4.13% | - | +42 bps | bear steepening (both up, 10Y up more) |
| 2026-07-17 | 4.55% | - | +9 bps | - | 4.16% | - | +41 bps | bear steepening (both up, 10Y up more) |
| 2026-07-18 | 4.54% | - | +8 bps | - | 4.18% | +83 bps | +37 bps | steepening (10Y up, 2Y down/flat) |
| 2026-07-19 | 4.54% | - | +8 bps | - | 4.18% | +83 bps | +37 bps | steepening (10Y up, 2Y down/flat) |
| 2026-07-20 | 4.60% | ↑3.4% | +15 bps | 3.71% | 4.18% | +90 bps | +37 bps | steepening (10Y up, 2Y down/flat) |
| 2026-07-21 | 4.63% | ↑2.6% | +12 bps | 3.73% | 4.21% | +90 bps | +39 bps | bear steepening (both up, 10Y up more) |
| 2026-07-22 | 4.65% | ↑3.4% | +16 bps | 3.75% | 4.26% | +90 bps | +37 bps | bear steepening (both up, 10Y up more) |
| 2026-07-23 | 4.70% | - | +30 bps | - | 4.31% | +90 bps | +36 bps | bear steepening (both up, 10Y up more) |
| 2026-07-24 | 4.66% | ↑6.2% | +27 bps | 3.79% | 4.37% | +87 bps | +34 bps | bear steepening (both up, 10Y up more) |
| 2026-07-25 | 4.70% | ↑6.8% | +31 bps | 3.80% | 4.33% | +90 bps | +36 bps | bear steepening (both up, 10Y up more) |
| 2026-07-26 | 4.70% | - | +31 bps | 3.80% | 4.33% | +90 bps | +36 bps | bear steepening (both up, 10Y up more) |
| 2026-07-27 | 4.64% | ↓5.3% | +27 bps | 3.81% | 4.33% | +83 bps | +36 bps | bear steepening (both up, 10Y up more) |
| 2026-07-28 | 4.59% | - | +22 bps | 3.76% | 4.31% | +84 bps | +34 bps | bear steepening (both up, 10Y up more) |
| 2026-07-29 | 4.65% | - | +23 bps | 3.78% | 4.26% | +88 bps | +35 bps | bear steepening (both up, 10Y up more) |
| 2026-07-30 | 4.66% | ↓1.1% | +19 bps | 3.66% | 4.22% | +100 bps | +45 bps | bear steepening (both up, 10Y up more) |
| 2026-07-31 | 4.74% | ↑5.6% | +25 bps | - | 4.23% | +105 bps | +45 bps | bear steepening (both up, 10Y up more) |
| 2026-08-01 | 4.74% | ↑5.8% | +25 bps | 3.68% | 4.28% | +106 bps | +47 bps | bear steepening (both up, 10Y up more) |
| 2026-08-02 | 4.74% | ↑5.8% | +25 bps | 3.68% | 4.28% | +106 bps | +47 bps | bear steepening (both up, 10Y up more) |
| 2026-08-03 | 4.69% | ↑4.7% | +21 bps | 3.70% | 4.28% | +99 bps | +47 bps | bear steepening (both up, 10Y up more) |
| 2026-08-04 | 4.63% | - | +10 bps | - | 4.25% | +90 bps | +45 bps | bear steepening (both up, 10Y up more) |
| 2026-08-05 | 4.63% | - | +6 bps | 3.73% | 4.20% | +90 bps | +43 bps | bear steepening (both up, 10Y up more) |
| 2026-08-06 | 4.67% | - | +13 bps | 3.73% | 4.18% | - | +45 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-07 | 4.65% | ↑1.8% | +8 bps | 3.72% | 4.25% | +93 bps | +44 bps | bear steepening (both up, 10Y up more) |
| 2026-08-08 | 4.66% | - | +9 bps | 3.71% | 4.19% | +95 bps | +46 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-09 | 4.66% | ↑2.0% | +9 bps | 3.71% | 4.19% | - | +46 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-10 | 4.70% | - | +9 bps | 3.72% | 4.19% | +98 bps | +46 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-11 | 4.68% | ↑2.2% | +9 bps | 3.73% | 4.25% | - | +47 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-12 | 4.68% | - | +13 bps | 3.70% | 4.22% | +97 bps | +48 bps | bear steepening (both up, 10Y up more) |
| 2026-08-13 | 4.64% | - | +7 bps | 3.70% | 4.20% | +95 bps | +48 bps | bear steepening (both up, 10Y up more) |
| 2026-08-14 | 4.69% | - | +15 bps | 3.70% | 4.15% | +99 bps | +48 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-15 | 4.70% | ↑3.4% | +16 bps | 3.70% | 4.17% | +100 bps | +51 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-16 | 4.70% | ↑3.4% | +16 bps | 3.70% | 4.17% | +100 bps | +51 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-17 | 4.71% | ↑2.5% | +11 bps | 3.70% | 4.17% | +101 bps | +51 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-18 | 4.71% | - | +8 bps | 3.70% | 4.19% | +100 bps | +53 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-19 | 4.66% | ↓0.9% | +0 bps | 3.70% | 4.19% | +95 bps | +52 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-20 | 4.70% | - | +0 bps | 3.70% | 4.19% | +99 bps | +46 bps | bull steepening (both down, 2Y down more) |
| 2026-08-21 | 4.73% | ↑1.2% | +5 bps | 3.71% | 4.19% | +102 bps | +50 bps | bull steepening (both down, 2Y down more) |
| 2026-08-22 | 4.74% | ↑1.3% | +6 bps | - | 4.24% | +103 bps | +50 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-23 | 4.74% | ↑1.3% | +6 bps | 3.71% | 4.24% | +103 bps | +50 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-24 | 4.70% | - | +6 bps | 3.71% | 4.24% | +99 bps | +50 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-25 | 4.64% | - | +4 bps | 3.70% | 4.24% | +94 bps | +46 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-26 | 4.67% | - | +5 bps | 3.70% | 4.17% | +97 bps | +47 bps | steepening (10Y up, 2Y down/flat) |
| 2026-08-27 | 4.66% | - | +0 bps | 3.68% | 4.19% | +98 bps | +47 bps | little changed |
| 2026-08-28 | 4.72% | - | -2 bps | 3.73% | 4.20% | +99 bps | +47 bps | little changed |
| 2026-08-29 | 4.67% | - | -7 bps | 3.68% | 4.34% | +99 bps | +39 bps | flattening (2Y up, 10Y down/flat) |
| 2026-08-30 | 4.72% | - | -2 bps | 3.73% | 4.34% | +99 bps | +39 bps | flattening (2Y up, 10Y down/flat) |
| 2026-08-31 | 4.76% | - | +7 bps | 3.74% | 4.34% | +102 bps | +39 bps | flattening (2Y up, 10Y down/flat) |
| 2026-09-01 | 4.79% | ↑3.5% | +16 bps | 3.77% | 4.34% | - | +41 bps | bear flattening (both up, 2Y up more) |
| 2026-09-02 | 4.80% | - | +18 bps | 3.77% | 4.39% | +102 bps | +40 bps | bear flattening (both up, 2Y up more) |
| 2026-09-03 | 4.75% | - | +8 bps | 3.75% | 4.39% | +100 bps | +40 bps | bear flattening (both up, 2Y up more) |
| 2026-09-04 | 4.76% | ↑2.2% | +10 bps | 3.76% | 4.34% | +100 bps | +43 bps | bear flattening (both up, 2Y up more) |
| 2026-09-05 | 4.78% | - | +12 bps | 3.76% | 4.37% | +103 bps | +41 bps | bear flattening (both up, 2Y up more) |
| 2026-09-06 | 4.78% | ↑2.7% | +12 bps | 3.76% | 4.37% | +103 bps | +41 bps | bear flattening (both up, 2Y up more) |
| 2026-09-07 | 4.78% | - | +12 bps | 3.76% | 4.37% | +103 bps | +41 bps | bear flattening (both up, 2Y up more) |
| 2026-09-08 | 4.79% | - | +9 bps | 3.78% | 4.37% | +101 bps | +41 bps | bear flattening (both up, 2Y up more) |
| 2026-09-09 | 4.85% | ↑3.4% | +17 bps | 3.81% | 4.39% | - | +41 bps | bear flattening (both up, 2Y up more) |
| 2026-09-10 | 4.92% | ↑5.0% | +24 bps | 3.84% | 4.43% | +107 bps | +40 bps | bear flattening (both up, 2Y up more) |
| 2026-09-11 | 4.95% | ↑6.7% | +31 bps | 3.90% | 4.56% | +105 bps | +39 bps | bear flattening (both up, 2Y up more) |
| 2026-09-12 | 4.97% | ↑7.2% | +33 bps | 3.91% | 4.63% | +106 bps | +33 bps | bear flattening (both up, 2Y up more) |
| 2026-09-13 | 4.97% | ↑7.2% | +33 bps | 3.91% | 4.63% | +106 bps | +33 bps | bear flattening (both up, 2Y up more) |
| 2026-09-14 | 4.94% | ↑5.1% | +24 bps | 3.93% | 4.63% | +101 bps | +33 bps | bear flattening (both up, 2Y up more) |
| 2026-09-15 | 5.00% | - | +28 bps | 3.96% | 4.65% | - | +32 bps | bear flattening (both up, 2Y up more) |
| 2026-09-16 | 4.95% | ↑5.3% | +24 bps | 3.94% | 4.67% | +101 bps | +33 bps | bear flattening (both up, 2Y up more) |
| 2026-09-17 | 4.95% | ↑6.4% | +30 bps | 3.97% | 4.74% | - | +27 bps | bear flattening (both up, 2Y up more) |
| 2026-09-18 | 5.00% | ↑6.4% | +30 bps | 3.98% | 4.67% | +102 bps | +27 bps | bear flattening (both up, 2Y up more) |
| 2026-09-19 | 5.00% | ↑6.4% | +30 bps | 3.98% | 4.76% | +102 bps | +25 bps | bear flattening (both up, 2Y up more) |
| 2026-09-20 | 5.00% | - | +30 bps | 3.98% | 4.76% | +102 bps | +25 bps | bear flattening (both up, 2Y up more) |
| 2026-09-21 | 4.95% | - | +21 bps | 3.98% | 4.76% | +97 bps | +25 bps | bear flattening (both up, 2Y up more) |
| 2026-09-22 | 4.97% | - | +27 bps | 4.01% | 4.76% | +96 bps | +20 bps | bear flattening (both up, 2Y up more) |
| 2026-09-23 | 5.10% | ↑8.5% | +46 bps | 4.02% | 4.71% | - | +25 bps | bear flattening (both up, 2Y up more) |
| 2026-09-24 | 5.14% | ↑10.8% | +48 bps | 4.06% | 4.85% | +108 bps | +26 bps | bear flattening (both up, 2Y up more) |
| 2026-09-25 | 5.19% | - | +52 bps | 4.07% | 4.87% | +112 bps | +31 bps | bear flattening (both up, 2Y up more) |
| 2026-09-26 | 5.18% | - | +51 bps | 4.07% | 4.81% | - | +36 bps | bear flattening (both up, 2Y up more) |
| 2026-09-27 | 5.18% | ↑11% | +51 bps | 4.07% | 4.81% | +111 bps | +36 bps | bear flattening (both up, 2Y up more) |
| 2026-09-28 | 5.25% | ↑11.2% | +53 bps | 4.06% | 4.81% | +119 bps | +36 bps | bear flattening (both up, 2Y up more) |
| 2026-09-29 | 5.28% | ↑11% | +52 bps | 4.09% | 4.92% | +119 bps | +32 bps | bear flattening (both up, 2Y up more) |
| 2026-09-30 | 5.29% | - | +49 bps | 4.03% | 4.89% | +126 bps | +37 bps | bear flattening (both up, 2Y up more) |
| 2026-10-01 | 5.23% | - | +43 bps | 4.00% | 4.88% | +123 bps | +41 bps | bear steepening (both up, 10Y up more) |
| 2026-10-02 | 5.28% | - | +52 bps | - | 4.78% | +128 bps | +46 bps | bear steepening (both up, 10Y up more) |
| 2026-10-03 | 5.28% | ↑10.8% | +52 bps | 3.99% | 4.83% | - | +45 bps | bear steepening (both up, 10Y up more) |
| 2026-10-04 | 5.28% | ↑10.8% | +52 bps | 3.99% | 4.83% | +128 bps | +45 bps | bear steepening (both up, 10Y up more) |
| 2026-10-05 | 5.34% | ↑11.5% | +56 bps | 4.02% | 4.83% | +132 bps | +45 bps | bear steepening (both up, 10Y up more) |
| 2026-10-06 | 5.28% | - | +47 bps | 4.03% | 4.84% | +124 bps | +47 bps | bear steepening (both up, 10Y up more) |
| 2026-10-07 | 5.32% | - | +48 bps | 4.05% | 4.79% | +128 bps | +48 bps | bear steepening (both up, 10Y up more) |
| 2026-10-08 | 5.25% | - | +31 bps | 4.05% | 4.77% | +121 bps | +51 bps | bear steepening (both up, 10Y up more) |
| 2026-10-09 | 5.24% | - | +27 bps | 4.06% | 4.75% | +119 bps | +47 bps | bear steepening (both up, 10Y up more) |
| 2026-10-10 | 5.24% | ↑5.4% | +27 bps | 4.06% | 4.80% | +119 bps | +44 bps | bear steepening (both up, 10Y up more) |
| 2026-10-11 | 5.24% | - | +27 bps | 4.06% | 4.80% | +119 bps | +44 bps | bear steepening (both up, 10Y up more) |
| 2026-10-12 | 5.24% | - | +28 bps | 4.05% | 4.80% | +119 bps | +44 bps | bear steepening (both up, 10Y up more) |
| 2026-10-13 | 5.23% | - | +23 bps | 4.06% | 4.80% | - | +44 bps | bear steepening (both up, 10Y up more) |
| 2026-10-14 | 5.24% | - | +23 bps | 4.10% | 4.79% | +114 bps | +42 bps | bear steepening (both up, 10Y up more) |
| 2026-10-15 | 5.09% | ↑3.1% | +14 bps | 4.09% | 4.82% | +100 bps | +37 bps | bear steepening (both up, 10Y up more) |
| 2026-10-16 | 5.13% | - | +13 bps | 4.07% | 4.77% | +105 bps | +33 bps | bear steepening (both up, 10Y up more) |
| 2026-10-17 | 5.10% | - | +10 bps | 4.07% | 4.74% | +103 bps | +35 bps | bear steepening (both up, 10Y up more) |
| 2026-10-18 | 5.10% | - | +10 bps | 4.07% | 4.74% | - | +35 bps | bear steepening (both up, 10Y up more) |
