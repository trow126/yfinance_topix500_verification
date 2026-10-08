#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
J-Quants の日足（scripts/data/fetch_jquants.py bars）を yfinance と同じ形の DataFrame にする

yfinance に無い銘柄（主に上場廃止）を補うために使う（hypotheses.md 3g 章、生存者バイアスの確認）。
- 価格は分割調整済み（AdjO/AdjH/AdjL/AdjC、AdjVo）。yfinance と同じく後の分割で過去を遡及調整した値
- Stock Splits: J-Quants の AdjFactor（分割・併合の効力発生日に、それより前の価格に掛ける倍率。1:2 分割なら 0.5、
  10:1 併合なら 10）の逆数。yfinance の表記（1:2 分割なら 2.0）にそろえる
- Dividends: J-Quants の日足には権利落ち日の配当が無いので 0（補った銘柄の配当収入は入らない＝戦略に不利な側）
"""

import json
from pathlib import Path
from typing import Dict

import pandas as pd


def load_jquants_bars(cache_dir: Path) -> Dict[str, pd.DataFrame]:
    out = {}
    for f in sorted(Path(cache_dir).glob("*.json")):
        rows = json.loads(f.read_text())
        if not rows:
            continue
        d = pd.DataFrame(rows)
        d = d.dropna(subset=["AdjC"])
        if d.empty:
            continue
        idx = pd.DatetimeIndex(pd.to_datetime(d["Date"]), name="Date")
        df = pd.DataFrame({"Open": d["AdjO"].to_numpy(), "High": d["AdjH"].to_numpy(), "Low": d["AdjL"].to_numpy(),
                           "Close": d["AdjC"].to_numpy(), "Volume": d["AdjVo"].fillna(0).to_numpy()}, index=idx)
        factor = pd.to_numeric(d["AdjFactor"], errors="coerce").fillna(1.0).to_numpy()
        df["Dividends"] = 0.0
        df["Stock Splits"] = [0.0 if abs(x - 1.0) < 1e-12 or x <= 0 else 1.0 / x for x in factor]
        out[f.stem] = df.sort_index()
    return out
