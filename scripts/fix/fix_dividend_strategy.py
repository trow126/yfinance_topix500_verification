#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当取り戦略の主要な問題を修正
1. 配当支払日の計算問題
2. 権利落ち前価格の取得問題
3. 買い増し機能の設定確認
"""

import sys
import os
# プロジェクトルートをパスに追加（2つ上のディレクトリ）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pathlib import Path
from datetime import datetime
import shutil
import re


def fix_dividend_payment_date():
    """配当支払日の計算ロジックを修正"""
    print("=== 配当支払日の計算ロジックを修正 ===\n")
    
    engine_file = Path("src/backtest/engine.py")
    
    # バックアップ作成
    backup_file = engine_file.with_suffix('.py.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(engine_file, backup_file)
    print(f"バックアップ作成: {backup_file}")
    
    with open(engine_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修正1: 配当支払日の計算を修正
    old_payment_logic = r'if record_date\.month == 3:'
    new_payment_logic = 'if record_date.month in [3, 4]:'  # 3月または4月
    
    content = re.sub(old_payment_logic, new_payment_logic, content)
    
    old_payment_logic2 = r'elif record_date\.month == 9:'
    new_payment_logic2 = 'elif record_date.month in [9, 10]:'  # 9月または10月
    
    content = re.sub(old_payment_logic2, new_payment_logic2, content)
    
    # ファイルに書き込み
    with open(engine_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 配当支払日の計算ロジックを修正しました")
    print("   - 3月と4月の権利確定 → 6月支払い")
    print("   - 9月と10月の権利確定 → 12月支払い")


def fix_pre_ex_price_logic():
    """権利落ち前価格の取得ロジックを修正"""
    print("\n=== 権利落ち前価格の取得ロジックを修正 ===\n")
    
    engine_file = Path("src/backtest/engine.py")
    
    with open(engine_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修正2: 権利落ち前価格の取得方法を改善
    # _process_existing_positions内の該当部分を探す
    lines = content.split('\n')
    modified_lines = []
    in_target_section = False
    
    for i, line in enumerate(lines):
        if 'pre_ex_date = BusinessDayCalculator.add_business_days(current_date, -1)' in line:
            # より正確な方法に変更
            modified_lines.append(line)
            modified_lines.append('                # 実際の価格データから前営業日を取得')
            modified_lines.append('                price_data = self.data_manager.get_price_data(ticker)')
            modified_lines.append('                if price_data is not None and not price_data.empty:')
            modified_lines.append('                    dates = price_data.index.tolist()')
            modified_lines.append('                    try:')
            modified_lines.append('                        current_idx = next(i for i, d in enumerate(dates) if d.date() == current_date.date())')
            modified_lines.append('                        if current_idx > 0:')
            modified_lines.append('                            pre_ex_date = dates[current_idx - 1]')
            modified_lines.append('                            pre_ex_price = price_data.iloc[current_idx - 1]["Close"]')
            modified_lines.append('                        else:')
            modified_lines.append('                            pre_ex_price = self.data_manager.get_price_on_date(ticker, pre_ex_date)')
            modified_lines.append('                    except StopIteration:')
            modified_lines.append('                        pre_ex_price = self.data_manager.get_price_on_date(ticker, pre_ex_date)')
            modified_lines.append('                else:')
            # 次の行をスキップ
            if i + 1 < len(lines) and 'pre_ex_price = self.data_manager.get_price_on_date' in lines[i + 1]:
                continue
        elif i > 0 and 'pre_ex_price = self.data_manager.get_price_on_date' in lines[i] and 'pre_ex_date = BusinessDayCalculator' in lines[i-1]:
            # この行はスキップ（上で処理済み）
            continue
        else:
            modified_lines.append(line)
    
    # ファイルに書き込み
    with open(engine_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(modified_lines))
    
    print("✅ 権利落ち前価格の取得ロジックを修正しました")
    print("   - 実際の価格データから前営業日を取得")
    print("   - より正確な価格を使用")


def add_minimum_holding_period():
    """最低保有期間を追加"""
    print("\n=== 最低保有期間の追加 ===\n")
    
    strategy_file = Path("src/strategy/dividend_strategy.py")
    
    # バックアップ作成
    backup_file = strategy_file.with_suffix('.py.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(strategy_file, backup_file)
    print(f"バックアップ作成: {backup_file}")
    
    with open(strategy_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 最低保有期間のチェックを追加
    # check_exit_signal メソッド内の窓埋め判定部分を修正
    lines = content.split('\n')
    modified_lines = []
    
    for i, line in enumerate(lines):
        modified_lines.append(line)
        
        # 窓埋め判定の前に最低保有期間チェックを追加
        if 'if self.exit_config.take_profit_on_window_fill and current_price >= pre_ex_price:' in line:
            # インデントを取得
            indent = len(line) - len(line.lstrip())
            # 最低保有期間のチェックを追加
            modified_lines[-1] = ' ' * indent + '# 最低保有期間（3営業日）を追加'
            modified_lines.append(' ' * indent + 'min_holding_days = 3')
            modified_lines.append(' ' * indent + 'if self.exit_config.take_profit_on_window_fill and current_price >= pre_ex_price and holding_days >= min_holding_days:')
    
    # ファイルに書き込み
    with open(strategy_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(modified_lines))
    
    print("✅ 最低保有期間を追加しました")
    print("   - 窓埋め判定に3営業日の最低保有期間を追加")


def update_config_addition():
    """設定ファイルの買い増し機能を確認"""
    print("\n=== 買い増し機能の設定確認 ===\n")
    
    config_file = Path("config/config.yaml")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'enabled: true' in content and 'addition:' in content:
        print("⚠️ 買い増し機能が有効になっています")
        print("   これは戦略の意図通りですか？")
        print("\n買い増しを無効にする場合:")
        print("   config/config.yaml の addition.enabled を false に変更してください")
    else:
        print("✅ 買い増し機能の設定は適切です")


def create_test_config():
    """テスト用の設定ファイルを作成"""
    print("\n=== テスト用設定ファイルの作成 ===\n")
    
    test_config = """# 修正版テスト用設定ファイル

backtest:
  start_date: "2023-01-01"  # 1年間でテスト
  end_date: "2023-12-31"
  initial_capital: 10_000_000
  
data_source:
  primary: "yfinance"
  cache_dir: "./data/cache"
  cache_expire_hours: 24
  
strategy:
  entry:
    days_before_record: 3
    position_size: 1_000_000
    max_positions: 5  # 少なめに設定
  
  addition:
    enabled: false  # 買い増しを無効化してテスト
    add_ratio: 0.5
    add_on_drop: true
  
  exit:
    max_holding_days: 20
    stop_loss_pct: 0.1
    take_profit_on_window_fill: true
  
execution:
  slippage: 0.002
  slippage_ex_date: 0.005
  commission: 0.00055
  min_commission: 550
  max_commission: 1100
  tax_rate: 0.20315
  
universe:
  # テスト用に3銘柄のみ
  tickers:
    - "7203"  # トヨタ自動車
    - "6758"  # ソニーグループ
    - "8306"  # 三菱UFJフィナンシャル
  
logging:
  level: "DEBUG"  # デバッグレベル
  file: "./logs/test_backtest.log"
  format: "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
  
output:
  results_dir: "./data/results/test_fixed"
  report_format: ["json", "csv", "html"]
  save_trades: true
  save_portfolio_history: true
"""
    
    test_config_file = Path("config/test_fixed.yaml")
    with open(test_config_file, 'w', encoding='utf-8') as f:
        f.write(test_config)
    
    print(f"✅ テスト用設定ファイルを作成: {test_config_file}")


def main():
    """メイン処理"""
    print("配当取り戦略の主要な問題を修正")
    print("=" * 70)
    
    print("\n⚠️ 注意: このスクリプトはソースコードを直接修正します")
    response = input("続行しますか？ (y/n): ")
    
    if response.lower() != 'y':
        print("中止しました")
        return
    
    # 修正を実行
    fix_dividend_payment_date()
    fix_pre_ex_price_logic()
    add_minimum_holding_period()
    update_config_addition()
    create_test_config()
    
    print("\n\n=== 修正完了 ===")
    print("\n次のステップ:")
    print("1. キャッシュをクリア:")
    print("   del /s /q data\\cache\\*")
    print("\n2. テスト実行:")
    print("   python main.py --config config/test_fixed.yaml")
    print("\n3. 結果の確認:")
    print("   - 配当収入が計上されているか")
    print("   - 窓埋め判定が適切か")
    print("   - 全体的なパフォーマンスの改善")


if __name__ == "__main__":
    main()
