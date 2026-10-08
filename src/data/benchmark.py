#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ベンチマーク ETF（1306 など）の株価データを読み込み、yfinance の既知の不備を補正する

yfinance の 1306.T には 2015-01-05 の 1:10 分割（受益権口数の分割）が記録されておらず、
2014-12-30 の終値 1,459 円が翌営業日に 139.3 円になっている。分配金も 2014 年までは分割前の
金額（20.6 円）のまま、2015-07-10 の分配金は 23.0 円（分割後の株価 161 円に対して 14%）と
明らかに桁が違う。ここでは分割前の価格・分配金を 1/10 にし、2015-07-10 の分配金を 2.3 円に
置き換える（2016 年の 2.73 円、2014 年の 2.06 円（補正後）と整合する）。

補正はこのファイルの CORRECTIONS に明示的に書き、暗黙には行わない。
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

PRICE_COLUMNS = ["Open", "High", "Low", "Close"]

# 銘柄 → {"splits": [(分割日, 比率)], "dividends": [(日付, 正しい金額)]}
# 分割日より前の価格と配当を 比率 で割り、出来高を 比率 倍する
CORRECTIONS: Dict[str, Dict[str, List[Tuple[str, float]]]] = {
    "1306": {
        "splits": [("2015-01-05", 10.0)],
        "dividends": [("2015-07-10", 2.3)],
    },
}


def apply_corrections(df: pd.DataFrame, code: str,
                      corrections: Optional[Dict] = None) -> pd.DataFrame:
    """既知の補正を適用した新しい DataFrame を返す（元は変えない）"""
    table = (CORRECTIONS if corrections is None else corrections).get(code)
    if not table:
        return df
    out = df.copy()
    for split_date, ratio in table.get("splits", []):
        before = out.index < pd.Timestamp(split_date)
        for col in PRICE_COLUMNS + ["Dividends"]:
            if col in out:
                out.loc[before, col] = out.loc[before, col] / ratio
        if "Volume" in out:
            out.loc[before, "Volume"] = out.loc[before, "Volume"] * ratio
    for date, amount in table.get("dividends", []):
        ts = pd.Timestamp(date)
        if ts in out.index:
            out.at[ts, "Dividends"] = amount
    return out


def load_benchmark(code: str = "1306", data_dir: str = "./data/cache/benchmark") -> pd.DataFrame:
    """補正済みのベンチマーク ETF データを読み込む"""
    df = pd.read_pickle(Path(data_dir) / f"{code}.pkl")
    return apply_corrections(df, code)


def find_unrecorded_splits(df: pd.DataFrame, threshold: float = 0.45) -> pd.DataFrame:
    """
    分割が記録されていないのに株価が 1 日で大きく飛んでいる日を探す（データ確認用）

    前日比が -threshold 以下、または +1/(1-threshold)-1 以上の日のうち、前後 3 営業日に
    Stock Splits の記録がないものを返す。
    """
    if len(df) < 2:
        return pd.DataFrame(columns=["date", "ret", "prev_close", "close"])
    close = df["Close"]
    ret = close.pct_change()
    up = 1.0 / (1.0 - threshold) - 1.0
    hits = ret[(ret <= -threshold) | (ret >= up)]
    rows = []
    splits = df["Stock Splits"] if "Stock Splits" in df else pd.Series(0.0, index=df.index)
    for date, r in hits.items():
        i = df.index.get_loc(date)
        if (splits.iloc[max(0, i - 3):i + 4] > 0).any():
            continue
        rows.append({"date": date, "ret": float(r), "prev_close": float(close.iloc[i - 1]),
                     "close": float(close.iloc[i])})
    return pd.DataFrame(rows, columns=["date", "ret", "prev_close", "close"])
