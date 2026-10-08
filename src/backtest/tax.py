#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
譲渡益課税（特定口座・源泉徴収あり）の簡易モデル

- 売るたびに、その年の実現損益の累計（手数料控除後）に対して 20.315% を源泉徴収する
- 同じ年の中では損失と利益を通算する: 累計がプラスのときだけ税を納め、
  あとで損が出て累計が減れば、その年に納めた分の範囲で還付される（証券会社の源泉徴収口座と同じ挙動）
- 年をまたぐ損失の繰越（確定申告による3年繰越）は扱わない（調査指示書 4章1: 損益通算は同一年内のみ）
- 配当・分配金は受取時に同じ税率で源泉徴収する。配当と譲渡損の通算は既定では行わない
  （行わない方が税額が多く、戦略側に不利＝保守的）。include_dividends=True で通算に含められる
"""

from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd


@dataclass
class TaxRecord:
    date: pd.Timestamp
    pnl: float          # この取引の実現損益（手数料控除後）
    year_cum: float     # 取引後のその年の累計損益
    tax_delta: float    # 納めた税（正）／還付（負）


@dataclass
class CapitalGainsTax:
    rate: float = 0.20315
    include_dividends: bool = False
    paid_by_year: Dict[int, float] = field(default_factory=dict)   # その年に納めた税の累計
    cum_by_year: Dict[int, float] = field(default_factory=dict)    # その年の実現損益の累計
    records: List[TaxRecord] = field(default_factory=list)

    def _settle(self, date: pd.Timestamp, pnl: float) -> float:
        """損益 pnl を計上し、口座から引かれる税額（正）または還付額（負）を返す"""
        year = pd.Timestamp(date).year
        cum = self.cum_by_year.get(year, 0.0) + pnl
        self.cum_by_year[year] = cum
        due = self.rate * max(cum, 0.0)
        paid = self.paid_by_year.get(year, 0.0)
        delta = due - paid
        self.paid_by_year[year] = due
        self.records.append(TaxRecord(pd.Timestamp(date), pnl, cum, delta))
        return delta

    def on_sale(self, date, pnl: float) -> float:
        """売却の実現損益を計上し、源泉徴収額（正）／還付額（負）を返す"""
        return self._settle(date, pnl)

    def on_dividend(self, date, amount: float) -> float:
        """配当・分配金 amount（税引前）に対する税額を返す"""
        if self.include_dividends:
            return self._settle(date, amount)
        return amount * self.rate

    @property
    def total_paid(self) -> float:
        """期間全体で納めた税の合計（還付控除後）"""
        return float(sum(self.paid_by_year.values()))

    def ledger(self) -> pd.DataFrame:
        return pd.DataFrame([r.__dict__ for r in self.records])
