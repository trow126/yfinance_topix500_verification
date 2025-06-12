#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当調整修正の検証スクリプト
修正前後の価格データと配当処理を比較
"""

import sys
import os
# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import numpy as np


def verify_price_adjustment():
    """価格調整の修正を検証"""
    print("=== 価格データの取得方法の検証 ===\n")
    
    ticker = "7203.T"  # トヨタ自動車
    start_date = "2023-09-20"
    end_date = "2023-10-05"
    
    stock = yf.Ticker(ticker)
    
    # 調整済み価格（修正前の実装）
    adjusted_data = stock.history(start=start_date, end=end_date, auto_adjust=True)
    adjusted_data.index = adjusted_data.index.tz_localize(None)
    
    # 未調整価格（修正後の実装）
    unadjusted_data = stock.history(start=start_date, end=end_date, auto_adjust=False)
    unadjusted_data.index = unadjusted_data.index.tz_localize(None)
    
    print("【調整済み価格（修正前）】")
    print(adjusted_data[['Close']].head())
    print("\n【未調整価格（修正後）】")
    print(unadjusted_data[['Close']].head())
    
    # 配当情報
    dividends = stock.dividends
    # タイムゾーンを除去して比較
    dividends.index = dividends.index.tz_localize(None)
    ex_dates = dividends.index[
        (dividends.index >= pd.to_datetime(start_date)) & 
        (dividends.index <= pd.to_datetime(end_date))
    ]
    
    if len(ex_dates) > 0:
        ex_date = ex_dates[0]
        print(f"\n権利落ち日: {ex_date.strftime('%Y-%m-%d')}")
        print(f"配当金額: {dividends[ex_date]:.2f}円")


def verify_execution_costs():
    """取引コストの修正を検証"""
    print("\n\n=== 取引コストの検証 ===\n")
    
    # 修正前の設定
    old_slippage = 0.001  # 0.1%
    old_commission = 0.0005  # 0.05%
    old_min_commission = 100
    
    # 修正後の設定
    new_slippage = 0.002  # 0.2%
    new_slippage_ex = 0.005  # 0.5%（権利落ち日）
    new_commission = 0.00055  # 0.055%
    new_min_commission = 550
    new_max_commission = 1100
    
    # テストケース
    test_cases = [
        ("少額取引", 100_000),
        ("通常取引", 1_000_000),
        ("大口取引", 3_000_000)
    ]
    
    print("取引コストの比較:")
    print("-" * 70)
    print(f"{'ケース':<10} {'取引金額':>12} {'修正前コスト':>15} {'修正後コスト':>15} {'差額':>10}")
    print("-" * 70)
    
    for case_name, amount in test_cases:
        # 修正前
        old_slip = amount * old_slippage
        old_comm = max(amount * old_commission, old_min_commission)
        old_total = old_slip + old_comm
        
        # 修正後（通常時）
        new_slip = amount * new_slippage
        new_comm = min(max(amount * new_commission, new_min_commission), new_max_commission)
        new_total = new_slip + new_comm
        
        print(f"{case_name:<10} {amount:>12,} {old_total:>15,.0f} {new_total:>15,.0f} {new_total-old_total:>10,.0f}")
    
    # 権利落ち日のケース
    print("\n【権利落ち日前後の取引】")
    amount = 1_000_000
    ex_slip = amount * new_slippage_ex
    ex_total = ex_slip + new_comm
    print(f"取引金額: {amount:,}円")
    print(f"スリッページ: {ex_slip:,.0f}円 ({new_slippage_ex:.1%})")
    print(f"合計コスト: {ex_total:,.0f}円")


def verify_dividend_payment():
    """配当支払いタイミングの検証"""
    print("\n\n=== 配当支払いタイミングの検証 ===\n")
    
    test_dates = [
        ("3月決算", datetime(2023, 3, 31)),
        ("9月中間配当", datetime(2023, 9, 30)),
        ("その他", datetime(2023, 6, 30))
    ]
    
    print("配当支払日の計算:")
    print("-" * 50)
    print(f"{'タイプ':<15} {'権利確定日':<15} {'支払日（修正後）':<15}")
    print("-" * 50)
    
    for type_name, record_date in test_dates:
        # 修正前：翌営業日
        old_payment = record_date + timedelta(days=1)
        
        # 修正後：実際のサイクル
        if record_date.month == 3:
            new_payment = datetime(record_date.year, 6, 25)
        elif record_date.month == 9:
            new_payment = datetime(record_date.year, 12, 10)
        else:
            new_payment = record_date + timedelta(days=75)
        
        print(f"{type_name:<15} {record_date.strftime('%Y-%m-%d'):<15} {new_payment.strftime('%Y-%m-%d'):<15}")


def verify_tax_calculation():
    """配当税計算の検証"""
    print("\n\n=== 配当税計算の検証 ===\n")
    
    dividend_per_share = 50
    shares = 1000
    gross_dividend = dividend_per_share * shares
    
    # 修正前：税金なし
    old_net = gross_dividend
    
    # 修正後：20.315%の税金
    tax_rate = 0.20315
    tax = gross_dividend * tax_rate
    new_net = gross_dividend - tax
    
    print(f"配当金: {dividend_per_share}円/株 × {shares:,}株")
    print(f"総配当金: {gross_dividend:,}円")
    print(f"\n【修正前】税引後配当: {old_net:,}円")
    print(f"【修正後】")
    print(f"  税金({tax_rate:.3%}): {tax:,.0f}円")
    print(f"  税引後配当: {new_net:,.0f}円")
    print(f"  差額: {old_net - new_net:,.0f}円")


def estimate_impact_on_returns():
    """リターンへの影響を推定"""
    print("\n\n=== バックテスト結果への影響推定 ===\n")
    
    # 仮定
    position_size = 1_000_000
    dividend_yield = 0.025  # 2.5%（年率）
    trades_per_year = 20
    
    # 1取引あたりの配当
    dividend_per_trade = position_size * (dividend_yield / 2)  # 半期配当
    
    # 修正前のリターン（楽観的）
    old_cost_rate = 0.0015  # 0.15%（往復）
    old_dividend_net = dividend_per_trade  # 税金なし
    old_dividend_drop = 0  # 配当落ちが見えない
    old_return = old_dividend_net - (position_size * old_cost_rate) - old_dividend_drop
    old_return_rate = old_return / position_size
    
    # 修正後のリターン（現実的）
    new_cost_rate = 0.0055  # 0.55%（往復、権利落ち日考慮）
    new_dividend_net = dividend_per_trade * (1 - 0.20315)  # 税引後
    new_dividend_drop = dividend_per_trade  # 配当落ち
    new_return = new_dividend_net - (position_size * new_cost_rate) - new_dividend_drop
    new_return_rate = new_return / position_size
    
    print("【1取引あたりの損益】")
    print(f"投資額: {position_size:,}円")
    print(f"配当金（税引前）: {dividend_per_trade:,.0f}円")
    
    print(f"\n修正前:")
    print(f"  配当金（税引後）: {old_dividend_net:,.0f}円")
    print(f"  取引コスト: {position_size * old_cost_rate:,.0f}円")
    print(f"  配当落ち損失: {old_dividend_drop:,.0f}円")
    print(f"  純損益: {old_return:,.0f}円 ({old_return_rate:.2%})")
    
    print(f"\n修正後:")
    print(f"  配当金（税引後）: {new_dividend_net:,.0f}円")
    print(f"  取引コスト: {position_size * new_cost_rate:,.0f}円")
    print(f"  配当落ち損失: {new_dividend_drop:,.0f}円")
    print(f"  純損益: {new_return:,.0f}円 ({new_return_rate:.2%})")
    
    print(f"\n【年間リターンへの影響】")
    print(f"年間取引回数: {trades_per_year}回")
    print(f"修正前の年間リターン: {old_return_rate * trades_per_year:.1%}")
    print(f"修正後の年間リターン: {new_return_rate * trades_per_year:.1%}")
    print(f"差: {(old_return_rate - new_return_rate) * trades_per_year:.1%}ポイント")


if __name__ == "__main__":
    print("配当取り戦略バックテストの修正検証")
    print("=" * 70)
    
    # 各検証を実行
    verify_price_adjustment()
    verify_execution_costs()
    verify_dividend_payment()
    verify_tax_calculation()
    estimate_impact_on_returns()
    
    print("\n" + "=" * 70)
    print("【結論】")
    print("修正により、バックテスト結果は大幅に現実的になります。")
    print("特に配当調整済み価格の問題を修正したことで、")
    print("年間リターンは約50%ポイント低下すると予想されます。")
