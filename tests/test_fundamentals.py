#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判断日に分かっていた財務指標（src/data/fundamentals.py）のテスト（合成データ）"""

import pandas as pd

from src.data.fundamentals import Fundamentals

CAL = pd.bdate_range("2014-01-01", "2025-12-31")


def row(date, time, doc, per, fy_end, np_="", eqar="", div="", fdiv="", nxfdiv="", code="11110"):
    return {"Code": code, "DiscDate": date, "DiscTime": time, "DocType": doc, "CurPerType": per, "CurFYEn": fy_end,
            "NP": np_, "EqAR": eqar, "DivAnn": div, "FDivAnn": fdiv, "NxFDivAnn": nxfdiv}


FY = "FYFinancialStatements_Consolidated_JP"
Q1 = "1QFinancialStatements_Consolidated_JP"
REV = "DividendForecastRevision"


def make():
    rows = [row("2014-05-12", "15:00:00", FY, "FY", "2014-03-31", np_="100", eqar="0.5", div="10", nxfdiv="10"),
            row("2015-05-12", "13:00:00", FY, "FY", "2015-03-31", np_="120", eqar="0.5", div="10", nxfdiv="12"),
            row("2016-05-12", "15:00:00", FY, "FY", "2016-03-31", np_="130", eqar="0.4", div="12", nxfdiv="12"),
            row("2016-08-05", "15:00:00", Q1, "1Q", "2017-03-31", eqar="0.35", fdiv="12"),
            row("2016-09-01", "16:00:00", REV, "FY", "2017-03-31", fdiv="8")]
    return Fundamentals(pd.DataFrame(rows), CAL)


def test_late_disclosure_is_known_next_day_and_used_the_day_after():
    f = make()
    # 2016-05-12 15:00 の通期短信 → 13 日に分かる → 14 日の判断から使える
    assert f.frame(pd.Timestamp("2016-05-13")).loc["1111", "prev_div"] == 10
    assert f.frame(pd.Timestamp("2016-05-16")).loc["1111", "prev_div"] == 12


def test_intraday_disclosure_usable_next_day():
    f = make()
    # 2015-05-12 13:00 の開示は 12 日の引け後に分かる → 12 日の判断には使えず、13 日の判断から使える
    assert f.frame(pd.Timestamp("2015-05-12")).loc["1111", "fdiv"] == 10   # 前年度短信の NxFDivAnn
    assert f.frame(pd.Timestamp("2015-05-13")).loc["1111", "fdiv"] == 12


def test_three_years_of_profit_and_latest_forecast():
    f = make()
    jul = f.frame(pd.Timestamp("2016-07-01")).loc["1111"]
    assert bool(jul["np_pos3"]) and jul["fdiv"] == 12 and jul["eqar"] == 0.4
    assert "1111" in f.passes(pd.Timestamp("2016-07-01")).index
    # 9/1 16:00 に配当予想を 8 円へ減額 → 9/2 に分かる → 9/5 の判断から外れる
    assert "1111" in f.passes(pd.Timestamp("2016-09-02")).index
    sep = f.frame(pd.Timestamp("2016-09-05")).loc["1111"]
    assert sep["fdiv"] == 8 and sep["eqar"] == 0.35
    assert "1111" not in f.passes(pd.Timestamp("2016-09-05")).index


def test_needs_three_fiscal_years():
    f = make()
    assert not bool(f.frame(pd.Timestamp("2015-06-01")).loc["1111", "np_pos3"])
