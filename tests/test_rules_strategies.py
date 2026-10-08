#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ルール型戦略のテスト（合成データ）"""

import numpy as np
import pandas as pd
import pytest

from src.backtest.rules_engine import ExecutionConfig, RulesConfig, RulesEngine
from src.strategy.monthly_rights import MarketPanel
from src.strategy.rules import Candidates, EventHold, FactorStrategy, IndexTiming, PostExRebound, YearEndLosers

DATES = pd.bdate_range("2021-01-04", "2023-12-29")


def make_stock(drift=0.0, dividends=None, base=1000.0, volume=5_000_000, seed=0, jump=None):
    # 決定的な系列: 日次 drift の複利に、銘柄ごとに位相の違う小さな波を足す（ボラが 0 にならないように）
    t = np.arange(len(DATES))
    close = base * (1 + drift) ** t * (1 + 0.01 * np.sin(t / 7.0 + seed))
    df = pd.DataFrame(index=DATES)
    df["Close"] = close
    if jump:
        df.loc[pd.Timestamp(jump[0]):, "Close"] *= jump[1]
    df["Open"] = df["High"] = df["Low"] = df["Close"]
    df["Volume"] = volume
    df["Dividends"] = 0.0
    df["Stock Splits"] = 0.0
    for d, v in (dividends or {}).items():
        df.loc[pd.Timestamp(d), "Dividends"] = v
    return df


@pytest.fixture
def data():
    return {
        "UP": make_stock(drift=0.001, seed=1, dividends={"2022-03-30": 20.0, "2023-03-30": 20.0}),
        "DOWN": make_stock(drift=-0.001, seed=2, dividends={"2022-03-30": 10.0, "2023-03-30": 10.0}),
        "FLAT": make_stock(seed=3, dividends={"2022-09-29": 30.0, "2023-09-28": 30.0}),
        "THIN": make_stock(drift=0.002, seed=4, volume=10),   # 売買代金が小さく候補にならない
    }


def config(start="2022-02-01", end="2023-12-29", **kw):
    return RulesConfig(start_date=start, end_date=end, initial_capital=3_000_000, sweep_ticker="",
                       execution=ExecutionConfig(slippage_liquid=0.0, slippage_illiquid=0.0), **kw)


def test_candidates_exclude_thin_and_use_prev_day(data):
    panel = MarketPanel(data)
    c = Candidates(panel, min_turnover=1_000_000)
    f = c.frame(pd.Timestamp("2022-04-01"))
    assert set(f.index) == {"UP", "DOWN", "FLAT"}
    assert f.at["UP", "close"] == pytest.approx(panel.close_ffill.at[pd.Timestamp("2022-03-31"), "UP"])
    # 3/30 権利落ちの配当は 4/1 時点の利回りに入る
    assert f.at["UP", "div_yield"] == pytest.approx(20.0 / f.at["UP", "close"])
    assert f.at["UP", "mom_12_1"] > f.at["DOWN", "mom_12_1"]


def test_factor_strategy_picks_top_momentum_and_rebalances_monthly(data):
    panel = MarketPanel(data)
    s = FactorStrategy(Candidates(panel, min_turnover=1_000_000), factors=["mom_12_1"], n=1, keep_rank=1)
    res = RulesEngine(config(), s, panel).run()
    buys = res["trades"][res["trades"]["side"] == "BUY"]
    # 上場 1 年未満の 1 月は候補なし → 2 月の最初の営業日に UP を買う
    assert buys.iloc[0]["code"] == "UP"
    assert buys.iloc[0]["date"] == pd.Timestamp("2022-02-01")
    assert res["metrics"]["final_value_after_tax"] > 3_000_000
    assert buys["code"].unique().tolist() == ["UP"]


def test_factor_random_pick_is_reproducible(data):
    panel = MarketPanel(data)
    runs = []
    for _ in range(2):
        s = FactorStrategy(Candidates(panel, min_turnover=1_000_000), n=2, pick="random", seed=7)
        runs.append(RulesEngine(config(), s, panel).run()["trades"]["code"].tolist())
    assert runs[0] == runs[1]


def test_no_cut_filter_and_half_year_rebalance():
    # CUT は 2 年目に減配、KEEP は維持、NEW は 1 年目の配当履歴しかない
    d = {
        "CUT": make_stock(dividends={"2021-03-30": 30.0, "2022-03-30": 10.0}),
        "KEEP": make_stock(dividends={"2021-03-30": 20.0, "2022-03-30": 20.0}),
        "NEW": make_stock(dividends={"2022-03-30": 40.0}),
    }
    panel = MarketPanel(d)
    c = Candidates(panel, min_turnover=1_000_000)
    f = c.frame(pd.Timestamp("2023-01-04"))
    assert bool(f.at["KEEP", "no_cut"]) is True
    assert bool(f.at["CUT", "no_cut"]) is False
    assert bool(f.at["NEW", "no_cut"]) is False       # 前の 12 か月が 0 なので減配判定できない → 除外
    s = FactorStrategy(c, factors=["div_yield"], n=1, keep_rank=1, no_cut=True, rebalance="H")
    res = RulesEngine(config(start="2023-01-04", end="2023-12-29"), s, panel).run()
    buys = res["trades"][res["trades"]["side"] == "BUY"]
    assert buys["code"].tolist() == ["KEEP"]           # 利回り最高の NEW・CUT は除外され、7 月は保有継続
    assert buys.iloc[0]["date"] == pd.Timestamp("2023-01-04")


def test_factor_random_sticky_keeps_holdings_within_year(data):
    panel = MarketPanel(data)
    s = FactorStrategy(Candidates(panel, min_turnover=1_000_000), n=1, keep_rank=1, pick="random_sticky", seed=3)
    res = RulesEngine(config(start="2022-02-01", end="2022-12-29"), s, panel).run()
    buys = res["trades"][res["trades"]["side"] == "BUY"]
    assert len(buys) == 1   # 年内は同じ乱数順位なので買い直さない


def test_post_ex_rebound_buys_on_ex_date_and_exits_on_window_fill(data):
    # FLAT は 9/29 に配当 30 で落ち、その後すぐ戻るように価格を作る
    d = {k: v for k, v in data.items()}
    flat = make_stock(seed=3, dividends={"2022-09-29": 30.0, "2023-09-28": 30.0})
    flat["Close"] = 1000.0
    flat.loc["2022-09-29":"2022-10-05", "Close"] = 970.0
    flat.loc["2022-10-06":, "Close"] = 1001.0
    for c in ("Open", "High", "Low"):
        flat[c] = flat["Close"]
    d["FLAT"] = flat
    panel = MarketPanel(d)
    s = PostExRebound(Candidates(panel, min_turnover=1_000_000), n_per_day=1, max_positions=1, max_days=365)
    res = RulesEngine(config(start="2022-09-01", end="2022-12-30"), s, panel).run()
    t = res["trades"]
    assert t.iloc[0]["code"] == "FLAT" and t.iloc[0]["date"] == pd.Timestamp("2022-09-29")
    assert t.iloc[0]["price"] == pytest.approx(970.0)
    assert t.iloc[1]["side"] == "SELL" and t.iloc[1]["date"] == pd.Timestamp("2022-10-06")
    assert res["closed"].iloc[0]["ex_yield"] == pytest.approx(0.03)


def test_year_end_losers_enters_in_december_and_exits_end_of_january(data):
    panel = MarketPanel(data)
    s = YearEndLosers(Candidates(panel, min_turnover=1_000_000), n=1, entry_days_before=3)
    res = RulesEngine(config(start="2022-06-01", end="2023-03-31"), s, panel).run()
    t = res["trades"]
    assert t.iloc[0]["code"] == "DOWN"
    assert t.iloc[0]["date"] == pd.Timestamp("2022-12-27")   # 12/30 の 3 営業日前
    assert t.iloc[1]["date"] == pd.Timestamp("2023-01-31")


def test_event_hold_buys_next_day_close_and_sells_after_hold_days(data):
    panel = MarketPanel(data)
    events = pd.DataFrame({"date": ["2022-06-01", "2022-06-01", "2022-06-04"], "code": ["UP", "UP", "THIN"]})
    s = EventHold(Candidates(panel, min_turnover=1_000_000), events, hold_days=5, max_positions=2)
    res = RulesEngine(config(start="2022-05-02", end="2022-07-29"), s, panel).run()
    t = res["trades"]
    assert t.iloc[0]["code"] == "UP" and t.iloc[0]["side"] == "BUY"
    assert t.iloc[0]["date"] == pd.Timestamp("2022-06-02")        # 提出日の翌営業日
    assert t.iloc[1]["side"] == "SELL" and t.iloc[1]["date"] == pd.Timestamp("2022-06-09")  # 5 営業日後
    assert len(t) == 2                                              # 同日重複は 1 回、THIN は候補外
    assert s.skipped and s.skipped[0]["code"] == "THIN"
    r = EventHold(Candidates(panel, min_turnover=1_000_000), events, hold_days=5, max_positions=2, pick="random", seed=1)
    res2 = RulesEngine(config(start="2022-05-02", end="2022-07-29"), r, panel).run()
    assert res2["trades"].iloc[0]["date"] == pd.Timestamp("2022-06-02")


def test_index_timing_holds_only_around_month_turn():
    etf = make_stock(seed=5)
    panel = MarketPanel({"1306": etf})
    s = IndexTiming(before=1, after=3)
    res = RulesEngine(config(start="2022-03-01", end="2022-05-31"), s, panel).run()
    h = res["history"]
    assert h.loc["2022-03-01", "positions"] == 1    # 月初 1 日目
    assert h.loc["2022-03-03", "positions"] == 1    # 月初 3 日目
    assert h.loc["2022-03-04", "positions"] == 0
    assert h.loc["2022-03-30", "positions"] == 0
    assert h.loc["2022-03-31", "positions"] == 1    # 月末 1 日前〜
