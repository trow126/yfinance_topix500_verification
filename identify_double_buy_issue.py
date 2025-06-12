#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最終的な問題特定スクリプト - execute_buyメソッドの詳細追跡
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from datetime import datetime
from src.utils.config import load_config
from src.backtest.portfolio import Portfolio
from src.strategy.position_manager import PositionManager


def test_execute_buy_behavior():
    """execute_buyの動作を詳細にテスト"""
    print("=== execute_buy の動作テスト ===\n")
    
    # ポートフォリオを初期化
    portfolio = Portfolio(initial_capital=10_000_000)
    
    # 1. 新規ポジションのオープン
    print("1. 新規ポジションのオープン:")
    success1 = portfolio.execute_buy(
        ticker="7203",
        date=datetime(2023, 3, 29),
        price=1852.0,
        shares=500,
        commission=0.0,
        reason="Initial entry",
        dividend_info={
            'ex_dividend_date': datetime(2023, 3, 30),
            'record_date': datetime(2023, 3, 31),
            'dividend_amount': 50.0
        }
    )
    print(f"  結果: {success1}")
    
    # ポジション状態を確認
    position = portfolio.position_manager.get_position("7203")
    print(f"  株数: {position.total_shares}")
    print(f"  平均取得価格: {position.average_price}")
    print(f"  権利落ち日: {position.ex_dividend_date}")
    
    # 2. 同じ銘柄に対して再度execute_buyを実行（これが問題の可能性）
    print("\n2. 同じ銘柄に対して再度execute_buy:")
    success2 = portfolio.execute_buy(
        ticker="7203",
        date=datetime(2023, 3, 30),
        price=1840.0,
        shares=500,
        commission=0.0,
        reason="Test addition",
        dividend_info=None  # 配当情報なし
    )
    print(f"  結果: {success2}")
    
    # ポジション状態を再確認
    position = portfolio.position_manager.get_position("7203")
    print(f"  株数: {position.total_shares}")
    print(f"  平均取得価格: {position.average_price}")
    print(f"  取引回数: {len(position.trades)}")
    
    # 取引履歴を表示
    print("\n取引履歴:")
    for i, trade in enumerate(position.trades):
        print(f"  Trade {i+1}: {trade.date.strftime('%Y-%m-%d')} "
              f"{trade.trade_type.value} {trade.shares}株 @{trade.price} "
              f"理由: {trade.reason}")


def analyze_engine_execute_entry():
    """engine.pyの_execute_entryメソッドを分析"""
    print("\n\n=== engine._execute_entry の分析 ===\n")
    
    with open("src/backtest/engine.py", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # _execute_entryメソッドの重要部分を探す
    if "_execute_entry" in content:
        print("_execute_entryメソッドの処理フロー:")
        print("1. スリッページと手数料を計算")
        print("2. portfolio.execute_buyを呼び出す")
        print("   → ここで既存ポジションがあると自動的に追加される")
        print("3. シグナル履歴に記録")
        
        print("\n⚠️ 問題の可能性:")
        print("- _execute_entryは買い増し(ADD)と新規エントリー(ENTRY)の両方で使われる")
        print("- portfolio.execute_buyは既存ポジションに自動的に追加する")
        print("- これにより、意図しない買い増しが発生する可能性がある")


def check_for_duplicate_entry_signals():
    """重複したエントリーシグナルの可能性をチェック"""
    print("\n\n=== 重複エントリーシグナルの可能性 ===\n")
    
    # 配当情報の例
    dividend_info = {
        'ex_dividend_date': datetime(2023, 3, 30),
        'record_date': datetime(2023, 3, 31),
        'dividend_amount': 50.0
    }
    
    # 権利確定日の3営業日前を計算
    from src.utils.calendar import DividendDateCalculator
    entry_date = DividendDateCalculator.calculate_entry_date(
        dividend_info['record_date'],
        days_before=3
    )
    
    print(f"権利確定日: {dividend_info['record_date'].strftime('%Y-%m-%d')}")
    print(f"権利落ち日: {dividend_info['ex_dividend_date'].strftime('%Y-%m-%d')}")
    print(f"エントリー日: {entry_date.strftime('%Y-%m-%d')}")
    
    print("\n考えられるシナリオ:")
    print("1. 3/29にエントリーシグナルで500株購入")
    print("2. 3/30（権利落ち日）に何らかの理由で再度エントリー処理が実行")
    print("   → portfolio.execute_buyが既存ポジションに追加")
    print("   → 結果的に1000株になる")


def proposed_fix():
    """修正案の提示"""
    print("\n\n=== 修正案 ===\n")
    
    print("【修正案1】portfolio.execute_buyの修正:")
    print("""
    def execute_buy(...):
        # 既存ポジションがある場合のチェックを追加
        if self.position_manager.get_position(ticker):
            # ADDシグナル以外では追加しない
            if reason and "Add" not in reason:
                log.warning(f"Position already exists for {ticker}, skipping buy")
                return False
    """)
    
    print("\n【修正案2】engine._execute_entryの修正:")
    print("""
    def _execute_entry(...):
        # SignalTypeをチェック
        if signal.signal_type == SignalType.ENTRY:
            # 既存ポジションがないことを確認
            if self.portfolio.position_manager.get_position(signal.ticker):
                log.warning(f"Position already exists for {signal.ticker}")
                return
    """)
    
    print("\n【修正案3】より根本的な修正:")
    print("- execute_buy を execute_open_position と execute_add_position に分離")
    print("- SignalTypeに応じて適切なメソッドを呼び出す")


def main():
    """メイン処理"""
    test_execute_buy_behavior()
    analyze_engine_execute_entry()
    check_for_duplicate_entry_signals()
    proposed_fix()
    
    print("\n\n=== 分析完了 ===")
    print("問題: portfolio.execute_buyが既存ポジションに自動的に追加する仕様")
    print("解決: SignalTypeを考慮した適切な処理分岐が必要")


if __name__ == "__main__":
    main()
