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


PRICE_COLUMNS = ("Open", "High", "Low", "Close")


def fix_transient_scale_errors(df: pd.DataFrame, max_days: int = 3) -> pd.DataFrame:
    """
    yfinance が数日だけ価格を 1/10（または 10 倍）で返す不備を直す

    例: 1306.T の 2026-03-30・31 は終値 37 円（前後は 380 円台）。分割の記録は無く、2 日で元に戻る。
    前日比が 1/8〜1/12 に落ち、max_days 営業日以内に 8〜12 倍で戻る区間の OHLC を 10 倍する
    （逆に 10 倍に跳ねて戻る区間は 1/10 にする）。本当の分割・併合（戻らない）は対象にならない。
    """
    close = df["Close"].to_numpy(dtype=float)
    out = df.copy()
    i = 1
    n = len(close)
    while i < n:
        prev = close[i - 1]
        if prev > 0 and close[i] > 0:
            ratio = close[i] / prev
            for down, factor in ((True, 10.0), (False, 0.1)):
                if (0.08 <= ratio <= 0.125) if down else (8.0 <= ratio <= 12.5):
                    # 戻る日を探す
                    for j in range(i + 1, min(i + max_days + 1, n)):
                        back = close[j] / close[j - 1] if close[j - 1] > 0 else 0
                        if (8.0 <= back <= 12.5) if down else (0.08 <= back <= 0.125):
                            cols = [c for c in PRICE_COLUMNS if c in out.columns]
                            out.iloc[i:j, [out.columns.get_loc(c) for c in cols]] *= factor
                            close[i:j] *= factor
                            i = j
                            break
                    break
        i += 1
    return out
