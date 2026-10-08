#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H7 税の扱い（計算のみ）: 1306 全額保有の税負担と、NISA に入れた場合の節税額の上限

仮定（docs/research/hypotheses.md H7）:
- 期間の初日に NISA 枠の分だけ 1306 を NISA で買い、残りは特定口座。NISA 内は分配金も売却益も非課税
- 使える NISA 枠（簡略化）: 2015-18 一般 NISA 120 万円 × 4 年 = 480 万円、2019-22 同 480 万円、
  2023-25 一般 120 万円（2023）+ 成長投資枠 240 万円 × 2 年（2024・2025）= 600 万円
  （本来は毎年の枠を順に使うが、ここでは期間初日にまとめて使えたとみなす＝節税額の上限）
- 損出し: 同じ年に相殺できる利益があるときだけ意味があるので、1306 を持ち続けるだけなら効果 0

使い方: python scripts/run/tax_overlay_h7.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.benchmark import buy_and_hold  # noqa: E402
from src.data.benchmark import load_benchmark  # noqa: E402

PERIODS = {"2015-18": ("2015-01-05", "2018-12-28", 4_800_000),
           "2019-22": ("2019-01-04", "2022-12-30", 4_800_000),
           "2023-25": ("2023-01-04", "2025-12-30", 6_000_000)}
CAPITAL = 15_000_000
RATE = 0.20315


def main():
    etf = load_benchmark("1306", str(PROJECT_ROOT / "data" / "cache" / "benchmark"))
    print("| 期間 | 税引前損益 | 分配金の税 | 売却益の税 | 税合計 | NISA枠 | NISA分の節税（上限） | 税引後損益(NISAなし→あり) |")
    print("|---|---|---|---|---|---|---|---|")
    for name, (s, e, nisa) in PERIODS.items():
        r = buy_and_hold(etf, s, e, CAPITAL, tax_rate=RATE)
        div_tax = r.dividends_after_tax / (1 - RATE) * RATE
        total_tax = div_tax + r.capital_gains_tax
        share = nisa / CAPITAL
        saving = total_tax * share  # NISA 分は分配金も売却益も非課税（損失の年も比例配分で近似）
        pre_tax = r.final_value_pre_tax + div_tax - CAPITAL
        print(f"| {name} | {pre_tax:,.0f} | {div_tax:,.0f} | {r.capital_gains_tax:,.0f} | {total_tax:,.0f} | "
              f"{nisa:,.0f} | {saving:,.0f} | {r.final_value_after_tax - CAPITAL:,.0f} → {r.final_value_after_tax - CAPITAL + saving:,.0f} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
