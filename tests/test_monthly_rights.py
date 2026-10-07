#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月次権利取り戦略のテスト（合成データ）
"""

import pandas as pd
import pytest

from src.backtest.monthly_rights_engine import MonthlyRightsEngine
from src.strategy.monthly_rights import (
    CostConfig, MarketPanel, MonthlyRightsConfig, MonthlyRightsSelector, RankingSelector,
    SelectionConfig, TradingConfig,
)

DATES = pd.bdate_range("2022-01-03", "2023-06-30")


def make_stock(prices=None, dividends=None, splits=None, base=1000.0):
    df = pd.DataFrame(index=DATES)
    df["Close"] = base
    for start, value in (prices or {}).items():
        df.loc[pd.Timestamp(start):, "Close"] = value
    df["Open"] = df["High"] = df["Low"] = df["Close"]
    df["Volume"] = 1_000_000
    df["Dividends"] = 0.0
    df["Stock Splits"] = 0.0
    for d, v in (dividends or {}).items():
        df.loc[pd.Timestamp(d), "Dividends"] = v
    for d, v in (splits or {}).items():
        df.loc[pd.Timestamp(d), "Stock Splits"] = v
    return df


@pytest.fixture
def data():
    return {
        # 3月権利・利回り3%: 権利落ち日に880へ下落し、4/17に960へ回復
        "1111": make_stock(prices={"2023-03-30": 880.0, "2023-04-17": 960.0},
                           dividends={"2022-03-30": 30.0, "2023-03-30": 30.0}),
        # 3月権利・利回り1%
        "2222": make_stock(dividends={"2022-03-30": 10.0, "2023-03-30": 10.0}),
        # 6月権利
        "3333": make_stock(dividends={"2022-06-29": 50.0, "2023-06-29": 50.0}),
        # 3月権利・6/1に1:2分割（それ以前の価格は分割調整済み）
        "4444": make_stock(dividends={"2022-03-30": 5.0}, splits={"2023-06-01": 2.0}),
    }


def config(**selection):
    return MonthlyRightsConfig(
        start_date="2023-01-02", end_date="2023-06-30", initial_capital=1_000_000,
        selection=SelectionConfig(top_n=1, min_turnover=0, max_unit_cost=10_000_000, **selection),
        trading=TradingConfig(unit_shares=100, entry_days_before_ex=2, nanpin_step=0.10, nanpin_max=2),
        costs=CostConfig(slippage=0, commission=0, min_commission=0, max_commission=0, tax_rate=0),
    )


def test_selects_highest_yield_in_record_month(data):
    panel = MarketPanel(data)
    selector = MonthlyRightsSelector(panel, config().selection, config().trading)

    picks = selector.select(pd.Timestamp("2023-03-01"))

    assert picks["code"].tolist() == ["1111"]
    assert picks.loc[0, "entry_date"] == pd.Timestamp("2023-03-28")
    assert picks.loc[0, "trailing_yield"] == pytest.approx(0.03)


def test_split_factor_restores_real_unit(data):
    panel = MarketPanel(data)

    assert panel.split_factor.at[pd.Timestamp("2023-05-31"), "4444"] == 2.0
    assert panel.split_factor.at[pd.Timestamp("2023-06-01"), "4444"] == 1.0


def test_rejects_implausible_dividend(data):
    # 株価1000円に対して1株2億円の配当（yfinanceのデータ異常）は採用しない
    data["5555"] = make_stock(dividends={"2022-03-30": 200_000_000.0, "2023-03-30": 200_000_000.0})
    panel = MarketPanel(data)

    assert "5555" not in set(panel.events["code"])
    assert len(panel.rejected_dividends) == 2


def test_cycle_dividend_nanpin_and_exit(data):
    engine = MonthlyRightsEngine(config(), data)
    results = engine.run()

    trades = results["trades"].query("ticker == '1111'")
    assert trades[["type", "price", "shares"]].values.tolist() == [
        ["BUY", 1000.0, 100],   # 3/28 権利付き最終日の前日
        ["BUY", 880.0, 100],    # 3/30 -10%を下回ってナンピン
        ["SELL", 960.0, 200],   # 4/17 平均取得単価940以上に回復
    ]
    position = results["positions"].set_index("ticker").loc["1111"]
    # 配当は権利落ち日前日の100株分のみ（ナンピン分は対象外）
    assert position["dividend_received"] == pytest.approx(3000)
    assert position["realized_pnl"] == pytest.approx((960 - 940) * 200 + 3000)
    assert results["metrics"]["nanpin_trades"] == 1
    # 6月権利の3333は株価1000のまま、権利落ち日に配当5000を受け取って同値で売却
    assert results["metrics"]["final_value"] == pytest.approx(1_000_000 + 7000 + 5000)


def test_no_exit_before_ex_date(data):
    # 権利落ち前に取得単価以上でも売らない（権利を取るまで保有）
    data["1111"] = make_stock(prices={"2023-03-29": 1100.0, "2023-03-30": 1050.0},
                              dividends={"2022-03-30": 30.0, "2023-03-30": 30.0})
    results = MonthlyRightsEngine(config(), data).run()

    sell = results["trades"].query("type == 'SELL'").iloc[0]
    assert sell["date"] == pd.Timestamp("2023-03-30")


def make_rankings():
    rows = [
        # 古いスナップショット（新しい方が優先される）
        ("2022-09-01", 3, 1, "2222", "B", "QUOカード", "金券", 100_000, 100),
        # 選定日より前の最新スナップショット
        ("2023-02-15", 3, 1, "1111", "A", "ホテル宿泊優待券", "交通・旅行", 100_000, 100),
        ("2023-02-15", 3, 2, "9999", "X", "QUOカード", "金券", 100_000, 100),
        ("2023-02-15", 3, 3, "2222", "B", "QUOカード", "金券", 200_000, 200),
        ("2023-02-15", 3, 4, "3333", "C", "自社製品", "食料品", 300_000, None),  # 旧形式（株数なし）
        # 選定日より後のスナップショットは使わない
        ("2023-03-15", 3, 1, "4444", "D", "QUOカード", "金券", 100_000, 100),
    ]
    df = pd.DataFrame(rows, columns=["snapshot", "month", "rank", "code", "name", "yutai_content",
                                     "categories", "min_invest_yen", "yutai_shares"])
    df["snapshot"] = pd.to_datetime(df["snapshot"])
    return df


def test_ranking_selector(data):
    panel = MarketPanel(data)
    selection = SelectionConfig(source="minkabu", top_n=2, max_unit_cost=10_000_000,
                                exclude_keywords=["ホテル", "宿泊"], exclude_categories=["交通・旅行"])
    selector = RankingSelector(panel, selection, TradingConfig(), make_rankings())

    picks = selector.select(pd.Timestamp("2023-03-01"))

    assert picks["code"].tolist() == ["2222", "3333"]
    assert (picks["snapshot"] == pd.Timestamp("2023-02-15")).all()
    b, c = picks.iloc[0], picks.iloc[1]
    # 2222: 3月の配当の権利落ち日（3/30）を使い、株数はランキングの優待発生株数
    assert (b["unit_shares"], b["ex_date"], b["rights_date_assumed"]) == (200, pd.Timestamp("2023-03-30"), False)
    # 3333: 3月に配当がないので月末（3/31）権利確定とみなす。株数は最低投資金額÷当時の株価
    assert (c["unit_shares"], c["record_date"], c["rights_date_assumed"]) == (300, pd.Timestamp("2023-03-31"), True)
    assert c["entry_date"] == pd.Timestamp("2023-03-28")
    reasons = {e["code"]: e["reason"] for e in selector.excluded}
    assert reasons == {"1111": "優待内容に「ホテル」", "9999": "株価データなし"}


def test_ranking_selector_uses_edinet_record_date(data):
    from src.data.edinet_benefits import parse_benefit

    panel = MarketPanel(data)
    selection = SelectionConfig(source="minkabu", top_n=2, max_unit_cost=10_000_000,
                                exclude_keywords=["ホテル"], exclude_categories=["交通・旅行"])
    text = "株主に対する特典 毎年３月20日現在の株主名簿に記載された100株以上保有の株主"
    benefits = pd.DataFrame({"code": ["3333"], "submitted": [pd.Timestamp("2022-06-28")],
                             "benefit": [parse_benefit(text)]})
    selector = RankingSelector(panel, selection, TradingConfig(), make_rankings(), benefits)

    c = selector.select(pd.Timestamp("2023-03-01")).set_index("code").loc["3333"]

    # 3/20(月)が優待の基準日 → 権利落ち日は3/17(金)、購入はその2営業日前の3/15
    assert c["rights_date_source"] == "edinet"
    assert c["record_date"] == pd.Timestamp("2023-03-20")
    assert c["ex_date"] == pd.Timestamp("2023-03-17")
    assert c["entry_date"] == pd.Timestamp("2023-03-15")


def test_stop_loss_after_nanpin(data):
    cfg = config()
    cfg.trading.nanpin_max, cfg.trading.stop_loss_pct = 1, 0.05
    trades = MonthlyRightsEngine(cfg, data).run()["trades"].query("ticker == '1111'")

    # 3/30 880円でナンピン（平均940円）→ 翌日も880円で平均の-5%(893円)以下なので損切り
    assert trades["type"].tolist() == ["BUY", "BUY", "SELL"]
    sell = trades.iloc[-1]
    assert (sell["date"], sell["reason"]) == (pd.Timestamp("2023-03-31"), "Stop loss after nanpin")


def test_max_holding_period(data):
    cfg = config()
    cfg.trading.nanpin_max, cfg.trading.max_holding_days = 0, 5
    trades = MonthlyRightsEngine(cfg, data).run()["trades"].query("ticker == '1111'")

    # 3/28購入、権利落ち後も880円で戻らない → 購入から5日経過した4/3に売却
    sell = trades.query("type == 'SELL'").iloc[0]
    assert (sell["date"], sell["price"], sell["reason"]) == (pd.Timestamp("2023-04-03"), 880.0, "Max holding period")


def test_objective_selector_bottom_and_random(data):
    panel = MarketPanel(data)
    trading = TradingConfig()
    bottom = MonthlyRightsSelector(panel, SelectionConfig(top_n=1, min_turnover=0, max_unit_cost=10_000_000,
                                                          pick="bottom"), trading)
    rand = MonthlyRightsSelector(panel, SelectionConfig(top_n=1, min_turnover=0, max_unit_cost=10_000_000,
                                                        pick="random", random_seed=1), trading)

    # 3月権利で利回りがあるのは 1111(3%) と 2222(1%)
    assert bottom.select(pd.Timestamp("2023-03-01"))["code"].tolist() == ["2222"]
    picked = rand.select(pd.Timestamp("2023-03-01"))["code"].tolist()
    assert len(picked) == 1 and picked[0] in {"1111", "2222"}
    assert rand.select(pd.Timestamp("2023-03-01"))["code"].tolist() == picked  # 同じシードなら同じ結果
