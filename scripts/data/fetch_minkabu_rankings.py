#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
みんかぶ「【N月権利確定】株主優待人気ランキング」の過去版を Wayback Machine から取得する

- 対象: --kind popular   … https://minkabu.jp/yutai/popular_ranking/total?month=1..12（2019年以降の人気ランキング）
        --kind yield_old … https://minkabu.jp/yutai/ranking/yutai_haito/1..12（2014〜2017年の配当+優待利回りランキング）
- 保存先: data/rankings/minkabu_popular_monthly.tsv（スナップショット日・月・順位ごとに1行）
- 取得したHTMLは data/cache/wayback/ に保存し、再実行時は再利用する

使い方:
    python scripts/data/fetch_minkabu_rankings.py
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "wayback"
# 種類ごとのURL・出力先・読み取り関数（popular: 2019年以降の人気ランキング / yield_old: 2014〜2017年の配当+優待利回りランキング）
KINDS = {
    "popular": ("minkabu.jp/yutai/popular_ranking/total?month={month}",
                PROJECT_ROOT / "data" / "rankings" / "minkabu_popular_monthly.tsv"),
    "yield_old": ("minkabu.jp/yutai/ranking/yutai_haito/{month}",
                  PROJECT_ROOT / "data" / "rankings" / "minkabu_yield_monthly_2014_2017.tsv"),
}
CDX = "https://web.archive.org/cdx/search/cdx"
FIELDS = ["snapshot", "month", "rank", "code", "name", "yutai_content", "categories",
          "min_invest_yen", "yutai_shares", "yutai_yield", "dividend_yield"]

session = requests.Session()
session.headers["User-Agent"] = "yfinance_topix500_verification research (personal backtest)"


def get(url: str, params: dict = None, retries: int = 8) -> requests.Response:
    # Wayback は混雑時に 429/503 や接続切れを返すので、待ち時間を伸ばしながら再試行する
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=90)
            if r.status_code == 200:
                return r
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
        except requests.RequestException:
            pass
        time.sleep(min(30 * (attempt + 1), 180))
    raise RuntimeError(f"取得に失敗しました: {url} {params}")


def list_snapshots(url: str, month: int) -> list:
    """月ごとのスナップショット（1日1件）"""
    r = get(CDX, {"url": url.format(month=month), "output": "json", "fl": "timestamp",
                  "filter": "statuscode:200", "collapse": "timestamp:8"})
    rows = r.json()
    return [row[0] for row in rows[1:]]


def fetch_snapshot(kind: str, url: str, month: int, timestamp: str) -> str:
    path = CACHE_DIR / f"minkabu_{kind}_m{month:02d}_{timestamp}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    r = get(f"https://web.archive.org/web/{timestamp}id_/https://{url.format(month=month)}")
    html = r.content.decode("utf-8", errors="replace")
    path.write_text(html, encoding="utf-8")
    time.sleep(2)  # Wayback への負荷を抑える
    return html


def _number(text: str):
    m = re.search(r"-?[\d,]+(?:\.\d+)?", text or "")
    return float(m.group().replace(",", "")) if m else None


def _labeled_value(item, label: str):
    """「最低投資金額 1.3万」のようなラベル直後の数値を返す（「---」はNone）"""
    node = item.find(string=re.compile(label))
    if node is None:
        return None
    # ラベルと値は同じセル（ラベル要素の親）に入っている
    cell = node.parent.parent.get_text(" ", strip=True)
    m = re.search(re.escape(node.strip()) + r"\s*(---|[\d,]+(?:\.\d+)?)\s*(万|株|%)?", cell)
    if m is None or m.group(1) == "---":
        return None
    value = _number(m.group(1))
    return value * 10_000 if m.group(2) == "万" else value


def parse_ranking(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    # サイドバー等にも同じクラスの一覧があるため、本体のランキングに限定する
    for rank, item in enumerate(soup.select("ol#shareholder_benefit_list > li.yutai_rank_style"), start=1):
        link = item.find("a", href=re.compile(r"/stock/[0-9A-Z]{4}/yutai"))
        if link is None:
            continue
        code = re.search(r"/stock/([0-9A-Z]{4})/yutai", link["href"]).group(1)
        name_link = item.find("a", string=re.compile(rf"\({code}\)"))
        name = re.sub(rf"\s*\({code}\)\s*", "", name_link.get_text(strip=True)) if name_link else ""
        content = item.select_one(".yutai_item")
        rows.append({
            "rank": rank,
            "code": code,
            "name": name,
            "yutai_content": content.get_text(" ", strip=True) if content else "",
            "categories": "|".join(c.get_text(strip=True) for c in item.select(".yutai_category")),
            "min_invest_yen": _labeled_value(item, "最低投資金額"),
            "yutai_shares": _labeled_value(item, "優待発生株数"),
            "yutai_yield": _labeled_value(item, "^優待利回り"),
            "dividend_yield": _labeled_value(item, "^配当利回り"),
        })
    return rows


def parse_ranking_old(html: str) -> list:
    """2014〜2017年の旧形式（配当+優待利回りランキング）"""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for item in soup.select("li"):
        num, code_el = item.select_one("div.num span"), item.select_one("div.code a")
        funds = item.select_one("div.funds")
        # サイドバーの一覧（投資金額の欄がない）は除く
        if num is None or code_el is None or funds is None:
            continue
        yld = item.select_one("div.yield")
        content = item.select("div.text > a")
        rows.append({
            "rank": int(num.get_text(strip=True)),
            "code": code_el.get_text(strip=True),
            "name": item.select_one("div.stockname").get_text(strip=True),
            "yutai_content": content[-1].get_text(" ", strip=True) if content else "",
            "categories": "|".join(c.get_text(strip=True) for c in item.select("div.cat")),
            "min_invest_yen": _number(funds.get_text()) * 10_000 if funds and _number(funds.get_text()) else None,
            "yutai_shares": None,
            "yutai_yield": _number(yld.get_text()) if yld else None,  # 配当+優待利回り
            "dividend_yield": None,
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description="みんかぶ月別優待ランキングの過去版を取得")
    parser.add_argument("--kind", choices=list(KINDS), default="popular")
    parser.add_argument("--since", default=None, help="この年（YYYY）以降のスナップショットのみ")
    parser.add_argument("--until", default=None, help="この年（YYYY）以前のスナップショットのみ")
    args = parser.parse_args()
    url, out_file = KINDS[args.kind]
    since = args.since or ("2019" if args.kind == "popular" else "2014")
    until = args.until or ("9999" if args.kind == "popular" else "2018")
    parse = parse_ranking if args.kind == "popular" else parse_ranking_old

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_rows = []
    for month in range(1, 13):
        snapshots = [t for t in list_snapshots(url, month) if since <= t[:4] <= until]
        print(f"{month}月: スナップショット {len(snapshots)} 件", flush=True)
        for ts in snapshots:
            rows = parse(fetch_snapshot(args.kind, url, month, ts))
            if not rows:
                print(f"  {ts}: ランキングを読み取れませんでした", flush=True)
                continue
            snapshot = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            out_rows += [{"snapshot": snapshot, "month": month, **r} for r in rows]
            print(f"  {snapshot}: {len(rows)} 銘柄（1位 {rows[0]['name']}）", flush=True)

    with open(out_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(out_rows, key=lambda r: (r["snapshot"], r["month"], r["rank"])))
    print(f"保存しました: {out_file}（{len(out_rows)} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
