#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""譲渡益課税とベンチマーク（1306 全額保有）のテスト"""

import pandas as pd
import pytest

from src.backtest.benchmark import buy_and_hold
from src.backtest.tax import CapitalGainsTax
from src.data.benchmark import apply_corrections, find_unrecorded_splits

RATE = 0.20315


def test_tax_is_withheld_on_gain_and_refunded_on_later_loss_in_same_year():
    tax = CapitalGainsTax(rate=RATE)
    assert tax.on_sale("2023-03-01", 100_000) == pytest.approx(100_000 * RATE)
    # 同じ年に 30,000 の損 → 累計 70,000 に対する税との差額が還付される
    assert tax.on_sale("2023-06-01", -30_000) == pytest.approx(-30_000 * RATE)
    # 累計がマイナスになったら、その年に納めた分は全部戻る（それ以上は戻らない）
    assert tax.on_sale("2023-09-01", -100_000) == pytest.approx(-70_000 * RATE)
    assert tax.on_sale("2023-10-01", -50_000) == 0.0
    assert tax.paid_by_year[2023] == 0.0


def test_loss_does_not_carry_over_to_next_year():
    tax = CapitalGainsTax(rate=RATE)
    tax.on_sale("2023-12-01", -100_000)
    assert tax.on_sale("2024-01-10", 50_000) == pytest.approx(50_000 * RATE)
    assert tax.total_paid == pytest.approx(50_000 * RATE)


def test_dividend_tax_separate_by_default():
    tax = CapitalGainsTax(rate=RATE)
    tax.on_sale("2023-02-01", -10_000)
    assert tax.on_dividend("2023-03-01", 1_000) == pytest.approx(1_000 * RATE)
    tax2 = CapitalGainsTax(rate=RATE, include_dividends=True)
    tax2.on_sale("2023-02-01", -10_000)
    assert tax2.on_dividend("2023-03-01", 1_000) == 0.0


def make_etf():
    dates = pd.bdate_range("2014-12-01", "2015-02-27")
    df = pd.DataFrame(index=dates)
    df["Close"] = 1500.0
    df.loc["2015-01-05":, "Close"] = 150.0
    for c in ("Open", "High", "Low"):
        df[c] = df["Close"]
    df["Volume"] = 1000
    df["Dividends"] = 0.0
    df.loc[pd.Timestamp("2014-12-10"), "Dividends"] = 20.0
    df["Stock Splits"] = 0.0
    return df


def test_find_unrecorded_split():
    found = find_unrecorded_splits(make_etf())
    assert len(found) == 1
    assert found.iloc[0]["date"] == pd.Timestamp("2015-01-05")


def test_apply_corrections_divides_prices_and_dividends_before_split():
    fixed = apply_corrections(make_etf(), "X", {"X": {"splits": [("2015-01-05", 10.0)], "dividends": []}})
    assert fixed.loc["2014-12-30", "Close"] == pytest.approx(150.0)
    assert fixed.loc["2014-12-10", "Dividends"] == pytest.approx(2.0)
    assert fixed.loc["2014-12-30", "Volume"] == 10_000
    assert fixed.loc["2015-01-05", "Close"] == pytest.approx(150.0)
    assert find_unrecorded_splits(fixed).empty


def test_buy_and_hold_after_tax():
    dates = pd.bdate_range("2023-01-02", "2023-12-29")
    etf = pd.DataFrame({"Close": 100.0, "Dividends": 0.0}, index=dates)
    etf.loc[dates[-1], "Close"] = 120.0
    etf.loc[pd.Timestamp("2023-07-10"), "Dividends"] = 2.0
    res = buy_and_hold(etf, "2023-01-02", "2023-12-29", 1_000_000, tax_rate=RATE, slippage=0.0)
    units = 10_000
    assert res.units == pytest.approx(units)
    assert res.dividends_after_tax == pytest.approx(units * 2.0 * (1 - RATE))
    gain = units * 20.0
    assert res.capital_gains_tax == pytest.approx(gain * RATE)
    assert res.final_value_after_tax == pytest.approx(units * 120.0 + res.dividends_after_tax - gain * RATE)
    assert res.history["total_value"].iloc[-1] == pytest.approx(res.final_value_pre_tax)
    assert res.max_drawdown == pytest.approx(0.0)


def test_buy_and_hold_loss_has_no_tax():
    dates = pd.bdate_range("2023-01-02", "2023-03-31")
    etf = pd.DataFrame({"Close": 100.0, "Dividends": 0.0}, index=dates)
    etf.loc[dates[-1], "Close"] = 80.0
    res = buy_and_hold(etf, "2023-01-02", "2023-03-31", 1_000_000, tax_rate=RATE, slippage=0.0)
    assert res.capital_gains_tax == 0.0
    assert res.final_value_after_tax == pytest.approx(800_000)
    assert res.max_drawdown == pytest.approx(-0.2)
