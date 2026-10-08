#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
J-Quants API（V2）から決算短信サマリー（fins/summary）・銘柄マスタ・日足を取得する（H10・H11 用）

- 認証: .env の JQUANTS_API_KEY を x-api-key ヘッダで送る。キーの値・ヘッダは表示もログもしない
- 通信エラーは例外の種類と HTTP ステータスだけを出す
- 再開可能: 日付ごと / 銘柄ごとに data/cache/jquants/<endpoint>/ に JSON で保存し、あるものは取り直さない
- 間隔: 既定 0.2 秒（Premium の上限 500 回/分より十分遅い）

使い方:
    python scripts/data/fetch_jquants.py summary --start 2012-01-01 --end 2026-10-08
    python scripts/data/fetch_jquants.py master --dates 2015-01-05,2026-10-08
    python scripts/data/fetch_jquants.py bars --codes-file data/rankings/delisted_codes.txt
    python scripts/data/fetch_jquants.py build      # キャッシュから data/jquants/summary.pkl を作る
"""

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE = "https://api.jquants.com/v2"
CACHE = PROJECT_ROOT / "data" / "cache" / "jquants"
OUT = PROJECT_ROOT / "data" / "jquants"


class Client:
    def __init__(self, wait: float = 0.2):
        load_dotenv(PROJECT_ROOT / ".env")
        key = os.environ.get("JQUANTS_API_KEY")
        if not key:
            raise SystemExit("JQUANTS_API_KEY が .env にありません")
        self._session = requests.Session()
        self._session.headers["x-api-key"] = key
        self.wait = wait

    def get_all(self, endpoint: str, params: dict) -> list:
        rows, query = [], dict(params)
        seen = set()
        while True:
            for attempt in range(5):
                try:
                    r = self._session.get(f"{BASE}/{endpoint}", params=query, timeout=60)
                except requests.RequestException as e:
                    print(f"  通信エラー {type(e).__name__}（{attempt + 1} 回目）", flush=True)
                    time.sleep(5 * (attempt + 1))
                    continue
                if r.status_code == 429 or r.status_code >= 500:
                    print(f"  HTTP {r.status_code}（{attempt + 1} 回目）", flush=True)
                    time.sleep(10 * (attempt + 1))
                    continue
                break
            else:
                raise RuntimeError(f"{endpoint}: 再試行の上限")
            time.sleep(self.wait)
            if r.status_code != 200:
                raise RuntimeError(f"{endpoint}: HTTP {r.status_code}")
            j = r.json()
            rows.extend(j.get("data", []))
            key = j.get("pagination_key")
            if not key or key in seen:
                return rows
            seen.add(key)
            query["pagination_key"] = key


def daterange(start: str, end: str):
    d, e = date.fromisoformat(start), date.fromisoformat(end)
    while d <= e:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def fetch_summary(c: Client, start: str, end: str):
    out = CACHE / "summary"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for d in daterange(start, end):
        f = out / f"{d}.json"
        if f.exists():
            continue
        rows = c.get_all("fins/summary", {"date": d.isoformat()})
        f.write_text(json.dumps(rows, ensure_ascii=False))
        n += 1
        if n % 100 == 0:
            print(f"  {d} まで（新規 {n} 日）", flush=True)
    print(f"summary: 新規 {n} 日", flush=True)


def fetch_master(c: Client, dates):
    out = CACHE / "master"
    out.mkdir(parents=True, exist_ok=True)
    for d in dates:
        f = out / f"{d}.json"
        if not f.exists():
            f.write_text(json.dumps(c.get_all("equities/master", {"date": d}), ensure_ascii=False))
        print(f"master {d}: {len(json.loads(f.read_text()))} 銘柄", flush=True)


def fetch_bars(c: Client, codes, start: str, end: str):
    out = CACHE / "bars"
    out.mkdir(parents=True, exist_ok=True)
    for i, code in enumerate(codes):
        f = out / f"{code}.json"
        if f.exists():
            continue
        f.write_text(json.dumps(c.get_all("equities/bars/daily", {"code": code, "from": start, "to": end}),
                                ensure_ascii=False))
        if (i + 1) % 50 == 0:
            print(f"  bars {i + 1}/{len(codes)}", flush=True)


def build():
    files = sorted((CACHE / "summary").glob("*.json"))
    rows = [r for f in files for r in json.loads(f.read_text())]
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_pickle(OUT / "summary.pkl")
    print(f"summary.pkl: {len(df)} 行、{files[0].stem}〜{files[-1].stem}、"
          f"銘柄 {df['Code'].nunique() if 'Code' in df else df.get('LocalCode', pd.Series()).nunique()}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("what", choices=["summary", "master", "bars", "build"])
    p.add_argument("--start", default="2012-01-01")
    p.add_argument("--end", default="2026-10-08")
    p.add_argument("--dates", default="")
    p.add_argument("--codes-file", default="")
    args = p.parse_args()
    if args.what == "build":
        return build()
    c = Client()
    if args.what == "summary":
        fetch_summary(c, args.start, args.end)
    elif args.what == "master":
        fetch_master(c, [d for d in args.dates.split(",") if d])
    else:
        codes = [x.strip() for x in Path(args.codes_file).read_text().split() if x.strip()]
        fetch_bars(c, codes, args.start, args.end)
    return 0


if __name__ == "__main__":
    sys.exit(main())
