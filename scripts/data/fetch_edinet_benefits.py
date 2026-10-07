#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EDINET（金融庁）の有価証券報告書から「提出会社の株式事務の概要」を取得する

この欄には基準日・剰余金の配当の基準日・単元株式数・株主に対する特典（優待）が書かれている。
年度ごとに取得するので、優待の新設・廃止や基準日の変更も追える。

- 対象銘柄: data/rankings/minkabu_popular_monthly.tsv に出てくる銘柄
- 出力: data/edinet/share_procedures.tsv（有報1件につき1行。本文はそのまま保存）
- キャッシュ: data/cache/edinet/（日別の書類一覧と、抜き出した本文）
- APIキー: .env の EDINET_API_KEY（https://api.edinet-fsa.go.jp/ で発行、英数字32文字）

使い方:
    python scripts/data/fetch_edinet_benefits.py --start 2018-06-01 --end 2026-09-30
"""

import argparse
import csv
import io
import json
import os
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE = PROJECT_ROOT / "data" / "cache" / "edinet"
OUT_FILE = PROJECT_ROOT / "data" / "edinet" / "share_procedures.tsv"
RANKINGS = PROJECT_ROOT / "data" / "rankings" / "minkabu_popular_monthly.tsv"
BASE = "https://api.edinet-fsa.go.jp/api/v2"
ELEMENT = "jpcrp_cor:OverviewOfOperationalProceduresForSharesTextBlock"
ANNUAL_REPORT = "120"  # 有価証券報告書

load_dotenv(PROJECT_ROOT / ".env", override=True)
session = requests.Session()


def api(path: str, **params) -> requests.Response:
    params["Subscription-Key"] = os.environ["EDINET_API_KEY"].strip()
    for attempt in range(5):
        try:
            r = session.get(f"{BASE}/{path}", params=params, timeout=120)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"EDINET API の呼び出しに失敗しました: {path} {params.get('date', '')}")


def list_documents(day: date) -> list:
    """その日に提出された書類の一覧（キャッシュあり）"""
    path = CACHE / "lists" / f"{day:%Y-%m-%d}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    j = api("documents.json", date=f"{day:%Y-%m-%d}", type=2).json()
    if j.get("metadata", {}).get("status") != "200":
        raise RuntimeError(f"書類一覧の取得に失敗: {day} {j.get('metadata') or j}")
    docs = [{k: d.get(k) for k in ("docID", "secCode", "filerName", "docTypeCode", "periodStart",
                                   "periodEnd", "submitDateTime", "csvFlag", "withdrawalStatus")}
            for d in j.get("results", []) if d.get("docTypeCode") == ANNUAL_REPORT]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.3)
    return docs


def fetch_text(doc_id: str) -> str:
    """有報のCSV（XBRL変換）から株式事務の概要の本文を取り出す（キャッシュあり）"""
    path = CACHE / "text" / f"{doc_id}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    r = api(f"documents/{doc_id}", type=5)
    text = ""
    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            for name in zf.namelist():
                if name.startswith("XBRL_TO_CSV/jpcrp") and name.endswith(".csv"):
                    df = pd.read_csv(zf.open(name), sep="\t", encoding="utf-16", dtype=str)
                    hit = df.loc[df["要素ID"] == ELEMENT, "値"]
                    if not hit.empty:
                        text = str(hit.iloc[0])
                        break
    except zipfile.BadZipFile:
        text = ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    time.sleep(0.5)
    return text


def main():
    parser = argparse.ArgumentParser(description="EDINETの有報から株式事務の概要（株主優待など）を取得")
    parser.add_argument("--start", default="2018-06-01")
    parser.add_argument("--end", default=f"{date.today():%Y-%m-%d}")
    args = parser.parse_args()

    if not os.environ.get("EDINET_API_KEY"):
        print(".env に EDINET_API_KEY がありません")
        return 1
    codes = set(pd.read_csv(RANKINGS, sep="\t", dtype={"code": str})["code"])
    targets = {f"{c}0" for c in codes}  # EDINETの証券コードは5桁

    # 1. 日別の書類一覧から対象銘柄の有報を探す
    day, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    docs = []
    total_days = (end - day).days + 1
    for i in range(total_days):
        d = day + timedelta(days=i)
        docs += [x for x in list_documents(d)
                 if x["secCode"] in targets and x["csvFlag"] == "1" and x["withdrawalStatus"] == "0"]
        if i % 60 == 0:
            print(f"  書類一覧 {d}（{i + 1}/{total_days}日） 対象の有報 {len(docs)} 件", flush=True)
    print(f"対象の有報: {len(docs)} 件（{len({x['secCode'] for x in docs})} 銘柄）", flush=True)

    # 2. 有報ごとに株式事務の概要を取り出す
    rows = []
    for i, doc in enumerate(sorted(docs, key=lambda x: x["submitDateTime"])):
        text = fetch_text(doc["docID"])
        rows.append({
            "code": doc["secCode"][:4], "doc_id": doc["docID"], "filer": doc["filerName"],
            "period_end": doc["periodEnd"], "submitted": doc["submitDateTime"][:10],
            "text": " ".join(text.split()),
        })
        if i % 100 == 0:
            print(f"  本文 {i + 1}/{len(docs)}", flush=True)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    empty = sum(1 for r in rows if not r["text"])
    print(f"保存しました: {OUT_FILE}（{len(rows)} 件、本文なし {empty} 件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
