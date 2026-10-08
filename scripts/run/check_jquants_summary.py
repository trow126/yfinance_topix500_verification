#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H10 のバックテスト前のデータ確認（hypotheses.md 3g 章「データの確認」）

- 年ごとの開示件数・銘柄数、通期短信の欠損率（当期純利益・自己資本比率・年間配当・来期予想配当）
- 各判断日（1・7 月の最初の営業日）に財務フィルタを通る銘柄数、売買代金 10 億円以上の候補との重なり
- 予想配当利回りの分布（極端な値の銘柄を表示）
- 1 社 1 期の突き合わせ: 8058 三菱商事の 2016 年 3 月期（純損失 -1,494 億円、年間配当 50 円）

使い方: python scripts/run/check_jquants_summary.py
"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run.run_oos_2026 import load_all  # noqa: E402
from src.data.fundamentals import Fundamentals  # noqa: E402
from src.data.quality import excluded_codes  # noqa: E402
from src.strategy.monthly_rights import MarketPanel  # noqa: E402
from src.strategy.rules import Candidates  # noqa: E402


def main():
    s = pd.read_pickle(PROJECT_ROOT / "data" / "jquants" / "summary.pkl")
    s["year"] = s["DiscDate"].str[:4]
    fy = s[s["DocType"].str.contains("FYFinancialStatements", na=False)]
    print("年 / 開示件数 / 銘柄数 / 通期短信 / 通期の欠損率（NP, EqAR, DivAnn, NxFDivAnn）")
    for y, g in s.groupby("year"):
        f = fy[fy["year"] == y]
        miss = [round((f[c] == "").mean(), 3) for c in ("NP", "EqAR", "DivAnn", "NxFDivAnn")]
        print(f"  {y}: {len(g):6d} {g['Code'].nunique():5d} {len(f):5d} {miss}")
    print("開示時刻の分布（時）:", s["DiscTime"].str[:2].value_counts().sort_index().to_dict())

    data = load_all()
    panel = MarketPanel(data)
    cand = Candidates(panel, min_turnover=1_000_000_000, excluded=excluded_codes(data))
    fund = Fundamentals(s, panel.calendar)

    print("\n8058 三菱商事の突き合わせ")
    m = s[s["Code"].str[:4] == "8058"]
    m = m[m["CurFYEn"].isin(["2015-03-31", "2016-03-31", "2017-03-31"]) & m["DocType"].str.contains("FY", na=False)]
    print(m[["DiscDate", "DiscTime", "DocType", "CurFYEn", "NP", "EqAR", "DivAnn", "NxFDivAnn"]].to_string(index=False))
    for d in ("2016-01-04", "2016-07-01", "2017-07-03"):
        date = panel.calendar[panel.calendar.searchsorted(pd.Timestamp(d))]
        print(f"  {date.date()}:", fund.frame(date).loc["8058"].to_dict())

    print("\n判断日 / 財務フィルタ通過 / 候補（10 億円以上・単元 ≤ 75 万円）/ 両方 / 予想利回り 上位20の範囲 / 10% 超")
    for y in range(2015, 2027):
        for mth in (1, 7):
            if y == 2026 and mth == 7:
                continue
            date = panel.calendar[panel.calendar.searchsorted(pd.Timestamp(y, mth, 1))]
            ok = fund.passes(date)
            f = cand.frame(date)
            f = f[f["unit_cost"] <= 750_000]
            both = f[f.index.isin(ok.index)].copy()
            both["fy"] = ok.loc[both.index, "fdiv"] / (both["unit_cost"] / 100)
            top = both["fy"].nlargest(20)
            hi = both[both["fy"] > 0.10]
            print(f"  {date.date()}: {len(ok):5d} {len(f):4d} {len(both):4d}  {top.min():.3f}〜{top.max():.3f}  "
                  f"{len(hi)} {list(hi.index)[:5]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
