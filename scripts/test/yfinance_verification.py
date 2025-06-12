#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yfinance TOPIX500データ取得検証ツール
権利確定日（配当データ）と日足データの取得可能性を確認
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import jpholiday
from typing import Dict, List, Tuple, Optional
import json
import warnings

warnings.filterwarnings("ignore")

# TOPIX500銘柄のサンプル（実際の運用では完全なリストを使用）
# ここでは代表的な銘柄を含むサンプルリストを使用
TOPIX500_SAMPLE = [
    # 大型株（時価総額上位）
    "7203",  # トヨタ自動車
    "6758",  # ソニーグループ
    "9432",  # 日本電信電話
    "6861",  # キーエンス
    "8306",  # 三菱UFJフィナンシャル
    "9433",  # KDDI
    "4063",  # 信越化学工業
    "9984",  # ソフトバンクグループ
    "6098",  # リクルートホールディングス
    "7974",  # 任天堂
    # 中型株
    "8058",  # 三菱商事
    "8001",  # 伊藤忠商事
    "7267",  # ホンダ
    "6501",  # 日立製作所
    "4502",  # 武田薬品工業
    "6902",  # デンソー
    "8035",  # 東京エレクトロン
    "4503",  # アステラス製薬
    "7741",  # HOYA
    "9020",  # 東日本旅客鉄道
    # その他業種代表
    "3382",  # セブン&アイ
    "6367",  # ダイキン工業
    "8031",  # 三井物産
    "9022",  # 東海旅客鉄道
    "8802",  # 三菱地所
    "4661",  # オリエンタルランド
    "7011",  # 三菱重工業
    "6857",  # アドバンテスト
    "2914",  # 日本たばこ産業
    "6273",  # SMC
]


class DividendDateCalculator:
    """権利落ち日から権利確定日を計算するクラス"""

    @staticmethod
    def calculate_record_date(ex_dividend_date: datetime) -> datetime:
        """
        権利落ち日から権利確定日を計算（T+2ルール）

        Args:
            ex_dividend_date: 権利落ち日

        Returns:
            権利確定日
        """
        record_date = ex_dividend_date
        business_days_added = 0

        while business_days_added < 2:
            record_date += timedelta(days=1)
            # 土日と日本の祝日を除外
            if record_date.weekday() < 5 and not jpholiday.is_holiday(record_date):
                business_days_added += 1

        return record_date


class YFinanceDataChecker:
    """yfinanceでのデータ取得可能性を検証するクラス"""

    def __init__(self, stock_codes: List[str]):
        self.stock_codes = stock_codes
        self.results = {"dividend_data": {}, "price_data": {}, "summary": {}}

    def check_dividend_data(self, code: str) -> Dict:
        """
        配当データの取得を試行

        Args:
            code: 銘柄コード

        Returns:
            取得結果の辞書
        """
        try:
            ticker = yf.Ticker(f"{code}.T")

            # 配当履歴を取得
            dividends = ticker.dividends

            if dividends.empty:
                return {
                    "success": False,
                    "has_data": False,
                    "message": "配当データなし",
                    "count": 0,
                }

            # 最新の配当情報
            latest_dividend = dividends.iloc[-1]
            latest_ex_date = dividends.index[-1].date()

            # 権利確定日を計算
            # タイムゾーンを除去してnaiveなdatetimeに変換
            ex_date_naive = (
                pd.Timestamp(latest_ex_date).to_pydatetime().replace(tzinfo=None)
            )
            record_date = DividendDateCalculator.calculate_record_date(ex_date_naive)

            # 過去2年間の配当回数
            # タイムゾーンを考慮したpandasのTimestampを使用
            two_years_ago = pd.Timestamp.now(tz="Asia/Tokyo") - pd.Timedelta(days=730)
            recent_dividends = dividends[dividends.index >= two_years_ago]

            return {
                "success": True,
                "has_data": True,
                "latest_dividend_amount": float(latest_dividend),
                "latest_ex_date": latest_ex_date.strftime("%Y-%m-%d"),
                "estimated_record_date": record_date.strftime("%Y-%m-%d"),
                "total_dividends": len(dividends),
                "recent_dividends_2y": len(recent_dividends),
                "dividend_dates": [
                    d.strftime("%Y-%m-%d") for d in dividends.index[-5:].date
                ],
            }

        except Exception as e:
            return {
                "success": False,
                "has_data": False,
                "message": f"エラー: {str(e)}",
                "error_type": type(e).__name__,
            }

    def check_price_data(self, code: str, start_date: str = "2023-01-01") -> Dict:
        """
        日足価格データの取得を試行

        Args:
            code: 銘柄コード
            start_date: データ取得開始日

        Returns:
            取得結果の辞書
        """
        try:
            ticker = yf.Ticker(f"{code}.T")

            # 日足データを取得
            hist = ticker.history(
                start=start_date, end=datetime.now().strftime("%Y-%m-%d")
            )

            if hist.empty:
                return {
                    "success": False,
                    "has_data": False,
                    "message": "価格データなし",
                }

            # データ品質のチェック
            total_days = len(hist)
            null_count = hist.isnull().sum().sum()

            # 取引日数の計算（概算）
            date_range = pd.date_range(start=start_date, end=datetime.now())
            business_days = len([d for d in date_range if d.weekday() < 5])
            coverage_rate = (
                (total_days / business_days) * 100 if business_days > 0 else 0
            )

            return {
                "success": True,
                "has_data": True,
                "total_days": total_days,
                "null_values": int(null_count),
                "coverage_rate": round(coverage_rate, 2),
                "latest_close": float(hist["Close"].iloc[-1]),
                "latest_date": hist.index[-1].strftime("%Y-%m-%d"),
                "date_range": f"{hist.index[0].strftime('%Y-%m-%d')} to {hist.index[-1].strftime('%Y-%m-%d')}",
            }

        except Exception as e:
            return {
                "success": False,
                "has_data": False,
                "message": f"エラー: {str(e)}",
                "error_type": type(e).__name__,
            }

    def run_comprehensive_check(self, delay: float = 0.5) -> None:
        """
        全銘柄の包括的なチェックを実行

        Args:
            delay: リクエスト間の遅延（秒）
        """
        print(f"検証開始: {len(self.stock_codes)}銘柄")
        print("=" * 60)

        for i, code in enumerate(self.stock_codes):
            print(f"\n[{i + 1}/{len(self.stock_codes)}] 銘柄コード: {code}")

            # 配当データチェック
            dividend_result = self.check_dividend_data(code)
            self.results["dividend_data"][code] = dividend_result

            if dividend_result["success"] and dividend_result["has_data"]:
                print(f"  ✓ 配当データ取得成功")
                print(f"    - 最新配当: {dividend_result['latest_dividend_amount']}円")
                print(f"    - 権利落ち日: {dividend_result['latest_ex_date']}")
                print(
                    f"    - 推定権利確定日: {dividend_result['estimated_record_date']}"
                )
                print(
                    f"    - 過去2年の配当回数: {dividend_result['recent_dividends_2y']}"
                )
            else:
                print(
                    f"  ✗ 配当データ取得失敗: {dividend_result.get('message', 'データなし')}"
                )

            # 価格データチェック
            price_result = self.check_price_data(code)
            self.results["price_data"][code] = price_result

            if price_result["success"] and price_result["has_data"]:
                print(f"  ✓ 価格データ取得成功")
                print(f"    - データ日数: {price_result['total_days']}日")
                print(f"    - カバレッジ率: {price_result['coverage_rate']}%")
                print(f"    - 最新終値: {price_result['latest_close']:,.0f}円")
            else:
                print(
                    f"  ✗ 価格データ取得失敗: {price_result.get('message', 'データなし')}"
                )

            # API制限回避のための遅延
            if i < len(self.stock_codes) - 1:
                time.sleep(delay)

    def generate_summary(self) -> Dict:
        """検証結果のサマリーを生成"""

        # 配当データの集計
        dividend_success = sum(
            1
            for r in self.results["dividend_data"].values()
            if r["success"] and r["has_data"]
        )
        dividend_total = len(self.results["dividend_data"])

        # 価格データの集計
        price_success = sum(
            1
            for r in self.results["price_data"].values()
            if r["success"] and r["has_data"]
        )
        price_total = len(self.results["price_data"])

        # カバレッジ率の統計
        coverage_rates = [
            r["coverage_rate"]
            for r in self.results["price_data"].values()
            if r.get("coverage_rate")
        ]

        self.results["summary"] = {
            "total_stocks": len(self.stock_codes),
            "dividend_data": {
                "success_count": dividend_success,
                "success_rate": round((dividend_success / dividend_total) * 100, 2)
                if dividend_total > 0
                else 0,
                "failed_stocks": [
                    code
                    for code, r in self.results["dividend_data"].items()
                    if not (r["success"] and r["has_data"])
                ],
            },
            "price_data": {
                "success_count": price_success,
                "success_rate": round((price_success / price_total) * 100, 2)
                if price_total > 0
                else 0,
                "avg_coverage_rate": round(np.mean(coverage_rates), 2)
                if coverage_rates
                else 0,
                "min_coverage_rate": round(min(coverage_rates), 2)
                if coverage_rates
                else 0,
                "failed_stocks": [
                    code
                    for code, r in self.results["price_data"].items()
                    if not (r["success"] and r["has_data"])
                ],
            },
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return self.results["summary"]

    def print_summary(self) -> None:
        """サマリー結果を表示"""
        summary = self.generate_summary()

        print("\n" + "=" * 60)
        print("検証結果サマリー")
        print("=" * 60)
        print(f"検証日時: {summary['timestamp']}")
        print(f"検証銘柄数: {summary['total_stocks']}")

        print("\n【配当データ】")
        print(f"  取得成功: {summary['dividend_data']['success_count']}銘柄")
        print(f"  成功率: {summary['dividend_data']['success_rate']}%")
        if summary["dividend_data"]["failed_stocks"]:
            print(f"  失敗銘柄: {', '.join(summary['dividend_data']['failed_stocks'])}")

        print("\n【価格データ】")
        print(f"  取得成功: {summary['price_data']['success_count']}銘柄")
        print(f"  成功率: {summary['price_data']['success_rate']}%")
        print(f"  平均カバレッジ率: {summary['price_data']['avg_coverage_rate']}%")
        print(f"  最低カバレッジ率: {summary['price_data']['min_coverage_rate']}%")
        if summary["price_data"]["failed_stocks"]:
            print(f"  失敗銘柄: {', '.join(summary['price_data']['failed_stocks'])}")

    def save_results(self, filename: str = "yfinance_check_results.json") -> None:
        """結果をJSONファイルに保存"""
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"\n結果を {filename} に保存しました")


def main():
    """メイン実行関数"""

    print("yfinance TOPIX500データ取得検証ツール")
    print("=" * 60)

    # 必要なライブラリのインストール確認
    try:
        import yfinance
        import jpholiday
    except ImportError:
        print("必要なライブラリがインストールされていません。")
        print("以下のコマンドでインストールしてください：")
        print("pip install yfinance jpholiday pandas numpy")
        return

    # 検証実行
    checker = YFinanceDataChecker(TOPIX500_SAMPLE)

    # 包括的チェックを実行
    checker.run_comprehensive_check(delay=0.5)

    # サマリーを表示
    checker.print_summary()

    # 結果を保存
    checker.save_results()

    # 追加の分析例
    print("\n" + "=" * 60)
    print("追加分析: 配当回数の分布")
    print("=" * 60)

    dividend_counts = {}
    for code, result in checker.results["dividend_data"].items():
        if result.get("recent_dividends_2y") is not None:
            count = result["recent_dividends_2y"]
            dividend_counts[count] = dividend_counts.get(count, 0) + 1

    for count, num_stocks in sorted(dividend_counts.items()):
        print(f"  年{count / 2:.1f}回配当: {num_stocks}銘柄")


if __name__ == "__main__":
    main()
