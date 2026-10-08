#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比較対象: ベンチマーク ETF（1306）を期間の最初に全額買って持ち続けた場合（税引後）

調査指示書 4 章の定義:
- 分配金は受取時に 20.315% を源泉徴収し、現金で持つ（再投資しない）
- 売却益は期末に一括で課税する（期末に全部売ったとみなす）
- 売買のスリッページは ETF なので片道 0.05%、手数料は 0 円（楽天ゼロコース）
"""

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .tax import CapitalGainsTax


@dataclass
class BenchmarkResult:
    history: pd.DataFrame       # date × (etf_value, cash, total_value, total_value_after_tax)
    units: float
    buy_price: float
    final_price: float
    dividends_after_tax: float
    capital_gains_tax: float
    final_value_pre_tax: float  # 期末の評価額（分配金の税は引いた後、売却益の税は引く前）
    final_value_after_tax: float
    max_drawdown: float         # 税引前の評価額ベース（税は期末一括なので日次には効かない）

    def metrics(self) -> Dict:
        return {
            "final_value_pre_tax": self.final_value_pre_tax,
            "final_value_after_tax": self.final_value_after_tax,
            "dividends_after_tax": self.dividends_after_tax,
            "capital_gains_tax": self.capital_gains_tax,
            "max_drawdown": self.max_drawdown,
        }


def buy_and_hold(etf: pd.DataFrame, start: str, end: str, capital: float,
                 tax_rate: float = 0.20315, slippage: float = 0.0005,
                 calendar: Optional[pd.DatetimeIndex] = None) -> BenchmarkResult:
    """
    期間 [start, end] の最初の営業日の終値で全額買い、最後の営業日の終値で全部売る

    calendar を渡すと、その日付で評価額の履歴を作る（戦略側の履歴と同じ日付にそろえるため）。
    """
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    px = etf["Close"]
    px = px[(px.index >= start_ts) & (px.index <= end_ts)].dropna()
    if px.empty:
        raise ValueError(f"ベンチマークのデータが期間 {start}〜{end} にありません")
    dist = etf["Dividends"].reindex(px.index).fillna(0.0)

    tax = CapitalGainsTax(rate=tax_rate)
    buy_price = float(px.iloc[0]) * (1 + slippage)
    units = capital / buy_price          # ETF は 1 口から買えるものとして端数を許す
    cash = 0.0
    dividends_after_tax = 0.0
    rows = []
    for date, price in px.items():
        d = float(dist.get(date, 0.0))
        if d > 0:
            gross = units * d
            net = gross - tax.on_dividend(date, gross)
            cash += net
            dividends_after_tax += net
        etf_value = units * float(price)
        rows.append({"date": date, "etf_value": etf_value, "cash": cash, "total_value": etf_value + cash})
    history = pd.DataFrame(rows).set_index("date")

    final_price = float(px.iloc[-1]) * (1 - slippage)
    gain = units * final_price - capital
    cg_tax = tax.on_sale(px.index[-1], gain)
    cg_tax = max(cg_tax, 0.0)
    final_pre = units * final_price + cash
    final_after = final_pre - cg_tax
    history["total_value_after_tax"] = history["total_value"]
    history.iloc[-1, history.columns.get_loc("total_value_after_tax")] = final_after
    if calendar is not None:
        history = history.reindex(calendar.union(history.index)).ffill().reindex(calendar)

    values = history["total_value"]
    mdd = float((values / values.cummax() - 1).min())
    return BenchmarkResult(history, units, buy_price, final_price, dividends_after_tax, cg_tax,
                           final_pre, final_after, mdd)


def max_drawdown(values: pd.Series) -> float:
    values = values.dropna()
    if values.empty:
        return 0.0
    return float((values / values.cummax() - 1).min())


def annualized(values: pd.Series) -> Dict[str, float]:
    """年率リターン・ボラ・シャープ（無リスク金利 0）"""
    values = values.dropna()
    if len(values) < 2:
        return {"cagr": 0.0, "vol": 0.0, "sharpe": 0.0}
    years = (values.index[-1] - values.index[0]).days / 365.25
    daily = values.pct_change().dropna()
    cagr = (values.iloc[-1] / values.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0
    vol = float(daily.std() * np.sqrt(252))
    sharpe = float(daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else 0.0
    return {"cagr": float(cagr), "vol": vol, "sharpe": sharpe}
