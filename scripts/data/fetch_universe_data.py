#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月次権利取り戦略用に、全上場株式の株価・配当をyfinanceから一括取得する

- 銘柄一覧: config/universe/jp_stock_codes.txt
- 保存先: data/cache/universe/{code}.pkl（未調整価格 + Dividends / Stock Splits）
- 取得済みの銘柄はスキップするので、途中で止まっても再実行で続きから取得できる

使い方:
    python scripts/data/fetch_universe_data.py --start 2018-01-01 --end 2026-01-01
"""

import argparse
import sys
import time
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODES_FILE = PROJECT_ROOT / "config" / "universe" / "jp_stock_codes.txt"
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "universe"
COLUMNS = ["Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"]


def load_codes(path: Path = CODES_FILE) -> list:
    """銘柄コード一覧を読み込む"""
    codes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            codes.append(line.split("\t")[0])
    return codes


def fetch_batch(codes: list, start: str, end: str) -> dict:
    """複数銘柄をまとめて取得し、銘柄ごとのDataFrameを返す"""
    tickers = [f"{c}.T" for c in codes]
    raw = yf.download(
        tickers, start=start, end=end, auto_adjust=False, actions=True,
        group_by="ticker", threads=4, progress=False,
    )
    result = {}
    for code, ticker in zip(codes, tickers):
        if raw.empty:
            break
        try:
            # group_by="ticker" では1銘柄でも (銘柄, 項目) の2段の列になることがある
            df = raw[ticker] if isinstance(raw.columns, pd.MultiIndex) else raw
        except KeyError:
            continue
        df = df.reindex(columns=COLUMNS).dropna(subset=["Close"])
        if df.empty:
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df[["Dividends", "Stock Splits"]] = df[["Dividends", "Stock Splits"]].fillna(0.0)
        result[code] = df
    return result


def main():
    parser = argparse.ArgumentParser(description="全上場株式の株価・配当を一括取得")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--sleep", type=float, default=5.0, help="バッチ間の待ち時間（秒）")
    parser.add_argument("--limit", type=int, default=None, help="動作確認用に先頭N銘柄だけ取得")
    parser.add_argument("--codes", nargs="*", help="指定した銘柄だけ取得（REIT・上場廃止銘柄など一覧外も可）")
    parser.add_argument("--rankings", nargs="?", const="data/rankings/minkabu_popular_monthly.tsv",
                        help="ランキングファイルに出てくる銘柄だけ取得（省略時は人気ランキング）")
    parser.add_argument("--cache-dir", default=None, help="保存先（期間を変えて取り直すときは別にする）")
    args = parser.parse_args()

    global CACHE_DIR
    if args.cache_dir:
        CACHE_DIR = PROJECT_ROOT / args.cache_dir
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if args.codes:
        codes = args.codes
    elif args.rankings:
        rankings = PROJECT_ROOT / args.rankings
        codes = sorted(pd.read_csv(rankings, sep="\t", dtype={"code": str})["code"].unique())
    else:
        codes = load_codes()[: args.limit]
    todo = [c for c in codes if not (CACHE_DIR / f"{c}.pkl").exists()]
    print(f"対象 {len(codes)} 銘柄 / 未取得 {len(todo)} 銘柄", flush=True)

    fetched = 0
    empty = []
    for i in range(0, len(todo), args.batch_size):
        batch = todo[i:i + args.batch_size]
        missing = batch
        # レート制限で取れなかった銘柄は待ってから再試行する
        for attempt, wait in enumerate([0, 60, 180, 600]):
            if wait:
                print(f"    {len(missing)} 銘柄が未取得のため {wait} 秒待って再試行 ({attempt}/3)", flush=True)
                time.sleep(wait)
            data = fetch_batch(missing, args.start, args.end)
            for code, df in data.items():
                df.to_pickle(CACHE_DIR / f"{code}.pkl")
            fetched += len(data)
            missing = [c for c in missing if c not in data]
            # 一部だけ欠けるのは上場前・廃止等による正常な欠損とみなす
            if len(missing) <= max(2, len(batch) // 10):
                break
        empty += missing
        print(f"  {i + len(batch)}/{len(todo)} 取得 {fetched} / データなし {len(empty)}", flush=True)
        time.sleep(args.sleep)

    # データが取れなかった銘柄（期間中に上場していない等）は記録だけ残す
    (CACHE_DIR / "_empty.txt").write_text("\n".join(empty), encoding="utf-8")
    print(f"完了: 取得 {fetched} 銘柄、データなし {len(empty)} 銘柄", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
