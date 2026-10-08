#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yfinance の全銘柄データの品質チェック

- 分割が記録されていないのに株価が 1 日で 45% 以上動いている銘柄（例: 2013 年の 1:10 併合、
  8303 の 2023-09-27 の終値 5.5 兆円）は、戦略の候補から外す
- 候補から外した銘柄は一覧にして報告に書く（生存者バイアスと同様、結論に与える向きを記録する）
"""

from typing import Dict, Set

import pandas as pd


def anomalous_codes(data: Dict[str, pd.DataFrame], threshold: float = 0.45,
                    start: str = None, end: str = None) -> pd.DataFrame:
    """
    1 日の変化率が -threshold 以下、または +1/(1-threshold)-1 以上で、前後 3 営業日に分割の記録がない
    銘柄・日付を返す（列: code, date, ret）。start/end で期間を絞れる
    """
    close = pd.DataFrame({c: df["Close"] for c, df in data.items()}).sort_index()
    splits = pd.DataFrame({c: df["Stock Splits"] for c, df in data.items()}).reindex(close.index).fillna(0.0)
    if start:
        close, splits = close.loc[pd.Timestamp(start):], splits.loc[pd.Timestamp(start):]
    if end:
        close, splits = close.loc[:pd.Timestamp(end)], splits.loc[:pd.Timestamp(end)]
    ret = close.pct_change(fill_method=None)
    up = 1.0 / (1.0 - threshold) - 1.0
    hit = (ret <= -threshold) | (ret >= up)
    near_split = (splits > 0).rolling(7, center=True, min_periods=1).max().astype(bool)
    flagged = hit & ~near_split
    rows = [{"code": c, "date": d, "ret": float(ret.at[d, c])}
            for c in flagged.columns for d in flagged.index[flagged[c].to_numpy()]]
    return pd.DataFrame(rows, columns=["code", "date", "ret"])


def excluded_codes(data: Dict[str, pd.DataFrame], **kw) -> Set[str]:
    return set(anomalous_codes(data, **kw)["code"].unique())
