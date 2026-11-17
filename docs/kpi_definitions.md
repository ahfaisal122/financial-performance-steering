# KPI definitions

Generated from the table `kpi_definitions` by `python -m cockpit.kpi_docs`. Do not edit by hand:
change `sql/30_marts/kpi_definitions.sql`, run the pipeline, then run the command again.

Every KPI is computed from the Solvency II template S.05.01.02 (premiums, claims and expenses
by line of business). The row codes in the formulas (R0110, R0120 and so on) are the rows of
that template.

## KPIs

| KPI | Formula | Unit | Scope | Caveat | View and column |
| --- | --- | --- | --- | --- | --- |
| Gross written premium (GWP) | R0110 + R0120 + R0130 | TEUR | All |  | `kpi_gwp.gwp_teur` |
| Gross earned premium (GEP) | R0210 + R0220 + R0230 | TEUR | All |  | `kpi_gep.gep_teur` |
| Gross claims incurred | R0310 + R0320 + R0330 | TEUR | All | Mixes current-year claims and reserve changes on prior years | `kpi_gross_claims.gross_claims_teur` |
| Gross loss ratio | Gross claims / GEP | ratio | All, cross-company | Main comparison KPI | `kpi_gross_loss_ratio.gross_loss_ratio` |
| Ceded share | R0140 / GWP | ratio | All | Shows reliance on reinsurance | `kpi_ceded_share.ceded_share` |
| Net loss ratio | R0400 / R0300 | ratio | Within one company | Distorted by internal reinsurance | `kpi_net_loss_ratio.net_loss_ratio` |
| Net expense ratio | R0550 / R0300 | ratio | Within one company | Flag on every view, never compare across companies | `kpi_net_expense_ratio.net_expense_ratio` |
| GWP growth | GWP(t) / GWP(t-1) - 1 | ratio | All | HGB basis, currency effects included | `kpi_gwp_growth.gwp_growth` |
| Loss ratio change | LR(t) - LR(t-1), in points | points | All |  | `kpi_loss_ratio_change.loss_ratio_change_pts` |
| 3-year average loss ratio | Sum of claims / sum of GEP over t-2 to t | ratio | All | Earned-weighted, not a mean of ratios | `kpi_loss_ratio_3y_avg.loss_ratio_3y_avg` |
| Mix share | GEP of a line / total GEP | ratio | All | Drives the mix effect | `kpi_mix_share.mix_share` |
| Peer gap | LR(AGCS) - LR(HDI), in points | points | Per line |  | `kpi_peer_gap.peer_gap_pts` |
| Market gap | LR(company) - LR(German market), in points | points | Total level only, from EIOPA | Company books are global, the benchmark is Germany only | `kpi_market_gap.market_gap_pts` |

## Line groups

| Line group | Column codes of S.05.01.02 |
| --- | --- |
| Financial lines | C0120 |
| Liability | C0080, C0140 |
| Marine, aviation and transport | C0060, C0150 |
| Motor | C0040, C0050 |
| Other | C0010, C0020, C0030, C0090, C0100, C0110, C0130 |
| Property | C0070, C0160 |

## Rules that apply to every KPI

- **Accounting basis.** The SFCR figures follow German local GAAP (HGB). They differ from the
  IFRS 17 figures the groups publish.
- **Units.** Amounts are in EUR thousand, as reported. A unit of `ratio` is a fraction
  (0.65 means 65%). A unit of `points` is percentage points (5 means +5 points).
- **Levels.** Every KPI exists per line group and for the company total. The total is the
  total column (C0200) as reported.
- **Empty values.** A ratio is empty when its base is zero, negative or missing. An amount is
  empty when the report shows no value for any of its rows; it is never set to zero.
- **Prior year.** The prior year is exactly the year before. A gap in the years is not bridged.
- **Cross-company comparison.** Compare companies on gross figures only. The net loss ratio and
  the net expense ratio are valid within one company only.
- **Market gap.** Total level only: company total against the German non-life market total
  from EIOPA. There is no market gap per line in version 1.
