#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汎用ルールエンジンのテスト（合成データ）"""

import pandas as pd
import pytest

from src.backtest.rules_engine import ExecutionConfig, Orders, RulesConfig, RulesEngine
from src.backtest.stats import deflated_sharpe_ratio, probabilistic_sharpe_ratio, random_rank
from src.strategy.monthly_rights import MarketPanel

DATES = pd.bdate_range("2023-01-02", "2023-12-29")
RATE = 0.20315


def make_stock(prices=None, dividends=None, base=1000.0, volume=2_000_000):
    df = pd.DataFrame(index=DATES)
    df["Close"] = base
    for start, value in (prices or {}).items():
        df.loc[pd.Timestamp(start):, "Close"] = value
    df["Open"] = df["High"] = df["Low"] = df["Close"]
    df["Volume"] = volume
    df["Dividends"] = 0.0
    df["Stock Splits"] = 0.0
    for d, v in (dividends or {}).items():
        df.loc[pd.Timestamp(d), "Dividends"] = v
    return df


def make_etf(base=100.0):
    df = pd.DataFrame(index=DATES)
    df["Close"] = base
    df["Dividends"] = 0.0
    return df


class BuyOnceSellLater:
    """3/1 に AAAA を 100 万円買い、6/1 に売る"""
    name = "test"

    def orders(self, date, panel, holdings, equity):
        if date == pd.Timestamp("2023-03-01"):
            return Orders(buys={"AAAA": 1_000_000}, reason="entry")
        if date == pd.Timestamp("2023-06-01"):
            return Orders(sells=["AAAA"], reason="exit")
        return None


def config(**kw):
    return RulesConfig(start_date="2023-01-02", end_date="2023-12-29", initial_capital=2_000_000,
                       sweep_ticker="", execution=ExecutionConfig(slippage_liquid=0.0, slippage_illiquid=0.0,
                                                                  tax_rate=RATE), **kw)


def test_gain_is_taxed_and_dividend_is_taxed():
    data = {"AAAA": make_stock(prices={"2023-04-03": 1200.0}, dividends={"2023-03-30": 10.0})}
    panel = MarketPanel(data)
    res = RulesEngine(config(), BuyOnceSellLater(), panel).run()
    m = res["metrics"]
    # 1,000 株（100 万円）買い → 配当 10,000 円（税引後 7,969 円）→ 120 万円で売り（益 20 万、税 40,630 円）
    assert m["stock_trades"] == 2
    assert m["dividends_after_tax"] == pytest.approx(10_000 * (1 - RATE))
    assert m["tax_paid"] == pytest.approx(200_000 * RATE)
    assert m["final_value_after_tax"] == pytest.approx(2_000_000 + 200_000 * (1 - RATE) + 10_000 * (1 - RATE))
    assert res["closed"].iloc[0]["pnl"] == pytest.approx(200_000)


def test_liquid_and_illiquid_slippage_tiers():
    data = {"AAAA": make_stock(volume=100)}  # 売買代金が小さい → 0.3%
    panel = MarketPanel(data)
    cfg = RulesConfig(start_date="2023-01-02", end_date="2023-12-29", initial_capital=2_000_000, sweep_ticker="",
                      execution=ExecutionConfig(tax_rate=RATE))
    res = RulesEngine(cfg, BuyOnceSellLater(), panel).run()
    t = res["trades"]
    assert t.iloc[0]["price"] == pytest.approx(1000 * 1.003)
    assert t.iloc[1]["price"] == pytest.approx(1000 * 0.997)


def test_idle_cash_sits_in_etf_and_etf_sale_is_taxed():
    data = {"AAAA": make_stock()}
    etf = make_etf()
    etf.loc[pd.Timestamp("2023-02-01"):, "Close"] = 110.0   # 買った後に 10% 上がる
    panel = MarketPanel(data)
    cfg = RulesConfig(start_date="2023-01-02", end_date="2023-12-29", initial_capital=2_000_000, sweep_ticker="1306",
                      execution=ExecutionConfig(slippage_liquid=0.0, slippage_illiquid=0.0, etf_slippage=0.0,
                                                tax_rate=RATE))
    res = RulesEngine(cfg, BuyOnceSellLater(), panel, etf).run()
    h = res["history"]
    assert h.iloc[0]["etf_value"] == pytest.approx(2_000_000)       # 初日に全額 ETF
    assert h.loc["2023-03-01", "stock_value"] == pytest.approx(1_000_000)
    # 期末に ETF を全部売る → 益は 20 万（100→110、2 万口）のうち 3/1 に 1/11 ほど売却済み。税の合計は益の 20.315%
    etf_sells = res["trades"][(res["trades"]["code"] == "1306") & (res["trades"]["side"] == "SELL")]
    assert etf_sells["pnl"].sum() == pytest.approx(200_000, rel=1e-6)
    assert res["metrics"]["tax_paid"] == pytest.approx(200_000 * RATE, rel=1e-6)
    assert res["metrics"]["final_value_after_tax"] == pytest.approx(2_200_000 - 200_000 * RATE, rel=1e-6)
    assert res["benchmark"].final_value_after_tax == pytest.approx(2_200_000 - 200_000 * RATE, rel=1e-6)


def test_losses_offset_gains_within_year_only():
    class TwoTrades:
        name = "t"

        def orders(self, date, panel, holdings, equity):
            if date == pd.Timestamp("2023-02-01"):
                return Orders(buys={"AAAA": 500_000, "BBBB": 500_000}, reason="in")
            if date == pd.Timestamp("2023-05-01"):
                return Orders(sells=["AAAA"], reason="win")
            if date == pd.Timestamp("2023-08-01"):
                return Orders(sells=["BBBB"], reason="loss")
            return None

    data = {"AAAA": make_stock(prices={"2023-04-03": 1100.0}), "BBBB": make_stock(prices={"2023-07-03": 900.0})}
    panel = MarketPanel(data)
    res = RulesEngine(config(), TwoTrades(), panel).run()
    # +50,000 で税 10,157 → -50,000 で全額還付
    assert res["metrics"]["tax_paid"] == pytest.approx(0.0)
    assert res["metrics"]["final_value_after_tax"] == pytest.approx(2_000_000)


def test_stats_helpers():
    assert probabilistic_sharpe_ratio(0.1, 0.0, 1000) > 0.99
    d = deflated_sharpe_ratio(0.05, [0.01, 0.02, 0.05, -0.01, 0.0], T=750)
    assert 0.0 < d["sr_star"] < 0.05
    assert 0.0 <= d["dsr"] <= 1.0
    r = random_rank(10.0, [1, 2, 3, 4, 5, 6, 7, 8, 9, 11])
    assert r["percentile"] == pytest.approx(0.9)
