#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EDINET から大量保有報告書（新規の 5% 超過報告）を集める

1. 日付ごとに書類一覧（documents.json, type=2）を取り、docTypeCode=350 かつ書類名が「大量保有報告書」の
   もの（変更報告書・特例対象株券等は除く）を data/edinet/large_holdings_list.tsv に記録する
2. 各書類の CSV（documents/{docID}, type=5）を取り、発行者の証券コード・名称、保有目的、株券等保有割合、
   報告義務発生日、提出日、提出者名を data/edinet/large_holdings.tsv に記録する

どちらも途中で止めても再実行で続きから取れる（済みの日付・docID を飛ばす）。
EDINET API の大量保有報告書は 2021 年 11 月ごろから一覧に出る。
API キーは .env の EDINET_API_KEY（値は表示・記録しない）。

使い方:
    python scripts/data/fetch_edinet_large_holdings.py --start 2021-11-01 --end 2026-10-08
"""

import argparse
import csv
import io
import os
import sys
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data" / "edinet"
LIST_FILE = OUT_DIR / "large_holdings_list.tsv"
DONE_DATES = OUT_DIR / "large_holdings_done_dates.txt"
DOC_FILE = OUT_DIR / "large_holdings.tsv"
BASE = "https://api.edinet-fsa.go.jp/api/v2"
LIST_COLUMNS = ["docID", "submitDateTime", "docDescription", "filerName", "issuerEdinetCode"]
DOC_COLUMNS = ["docID", "filing_date", "obligation_date", "issuer_code", "issuer_name", "filer_name",
               "holding_ratio", "purpose"]
FIELDS = {
    "jplvh_cor:SecurityCodeOfIssuer": "issuer_code",
    "jplvh_cor:NameOfIssuer": "issuer_name",
    "jplvh_cor:PurposeOfHolding": "purpose",
    "jplvh_cor:HoldingRatioOfShareCertificatesEtc": "holding_ratio",
    "jplvh_cor:DateWhenFilingRequirementAroseCoverPage": "obligation_date",
    "jplvh_cor:FilingDateCoverPage": "filing_date",
    "jplvh_cor:NameCoverPage": "filer_name",
}


def api(path: str, **params) -> requests.Response:
    params["Subscription-Key"] = os.environ["EDINET_API_KEY"].strip()
    for attempt in range(5):
        try:
            r = requests.get(f"{BASE}/{path}", params=params, timeout=120)
        except requests.RequestException as e:
            # 例外の文字列には URL（API キーを含む）が入るので、種類だけを出す
            print(f"    通信エラー {type(e).__name__}; {30 * (attempt + 1)} 秒待って再試行", flush=True)
            time.sleep(30 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"    HTTP {r.status_code}; {60 * (attempt + 1)} 秒待って再試行", flush=True)
            time.sleep(60 * (attempt + 1))
            continue
        return r
    raise RuntimeError(f"EDINET API に 5 回失敗: {path}")


def list_day(day: date) -> list:
    r = api("documents.json", date=f"{day:%Y-%m-%d}", type=2)
    if r.status_code != 200:
        print(f"  {day} HTTP {r.status_code}", flush=True)
        return []
    results = r.json().get("results") or []
    return [{k: x.get(k) for k in LIST_COLUMNS}
            for x in results if x.get("docTypeCode") == "350" and x.get("docDescription") == "大量保有報告書"]


def parse_doc(doc_id: str) -> dict:
    r = api(f"documents/{doc_id}", type=5)
    if r.status_code != 200:
        return {"docID": doc_id, "purpose": f"HTTP {r.status_code}"}
    try:
        zf = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile:
        return {"docID": doc_id, "purpose": "not a zip"}
    out = {"docID": doc_id}
    for name in zf.namelist():
        if not name.endswith(".csv"):
            continue
        text = zf.read(name).decode("utf-16", errors="replace")
        for row in csv.reader(io.StringIO(text), delimiter="\t"):
            if len(row) < 9:
                continue
            key = FIELDS.get(row[0])
            if key and key not in out:  # 共同保有者が複数のときは最初（提出者本人）の値
                out[key] = row[8].replace("\n", " ").replace("\t", " ").strip()
    return out


def read_tsv(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def append_tsv(path: Path, rows: list, columns: list) -> None:
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2021-11-01")
    p.add_argument("--end", default=f"{date.today():%Y-%m-%d}")
    p.add_argument("--sleep", type=float, default=0.3)
    p.add_argument("--skip-docs", action="store_true", help="一覧だけ取り、CSV は取らない")
    args = p.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.environ.get("EDINET_API_KEY"):
        print(".env に EDINET_API_KEY がありません")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    done = set(DONE_DATES.read_text(encoding="utf-8").split()) if DONE_DATES.exists() else set()
    start, end = datetime.strptime(args.start, "%Y-%m-%d").date(), datetime.strptime(args.end, "%Y-%m-%d").date()
    day = start
    n_days = n_docs = 0
    while day <= end:
        key = f"{day:%Y-%m-%d}"
        if key not in done and day.weekday() < 5:
            rows = list_day(day)
            if rows:
                append_tsv(LIST_FILE, rows, LIST_COLUMNS)
            with open(DONE_DATES, "a", encoding="utf-8") as f:
                f.write(key + "\n")
            n_days += 1
            n_docs += len(rows)
            if n_days % 50 == 0:
                print(f"  一覧 {key} まで: {n_days} 日, 大量保有報告書 {n_docs} 件", flush=True)
            time.sleep(args.sleep)
        day += timedelta(days=1)
    print(f"一覧の取得完了: 今回 {n_days} 日 / {n_docs} 件", flush=True)
    if args.skip_docs:
        return 0

    listed = read_tsv(LIST_FILE)
    have = {r["docID"] for r in read_tsv(DOC_FILE)}
    todo = [r for r in listed if r["docID"] not in have]
    print(f"CSV 取得: 一覧 {len(listed)} 件 / 済み {len(have)} / 未取得 {len(todo)}", flush=True)
    for i, r in enumerate(todo, 1):
        doc = parse_doc(r["docID"])
        append_tsv(DOC_FILE, [doc], DOC_COLUMNS)
        if i % 100 == 0:
            print(f"  CSV {i}/{len(todo)}", flush=True)
        time.sleep(args.sleep)
    print("完了", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
