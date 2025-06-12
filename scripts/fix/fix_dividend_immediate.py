#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当処理を簡略化して即座に計上する修正
"""

import sys
import os
# プロジェクトルートをパスに追加（2つ上のディレクトリ）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pathlib import Path
from datetime import datetime
import shutil


def fix_dividend_immediate_payment():
    """配当を権利落ち日に即座に計上するように修正"""
    print("=== 配当処理を簡略化（権利落ち日に即座に計上）===\n")
    
    engine_file = Path("src/backtest/engine.py")
    
    # バックアップ作成
    backup_file = engine_file.with_suffix('.py.backup_dividend_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(engine_file, backup_file)
    print(f"バックアップ作成: {backup_file}")
    
    with open(engine_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # _process_dividendsメソッドを探して置換
    lines = content.split('\n')
    new_lines = []
    in_process_dividends = False
    method_indent = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # _process_dividendsメソッドの開始を検出
        if 'def _process_dividends(self, current_date: datetime) -> None:' in line:
            in_process_dividends = True
            method_indent = len(line) - len(line.lstrip())
            new_lines.append(line)
            i += 1
            
            # docstringをスキップ
            if i < len(lines) and '"""' in lines[i]:
                new_lines.append(lines[i])
                i += 1
                while i < len(lines) and '"""' not in lines[i]:
                    new_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    new_lines.append(lines[i])
                    i += 1
            
            # 新しい実装を挿入
            indent = ' ' * (method_indent + 4)
            new_lines.append(f'{indent}positions = self.portfolio.position_manager.get_open_positions()')
            new_lines.append('')
            new_lines.append(f'{indent}for position in positions:')
            new_lines.append(f'{indent}    # 権利落ち日に配当を即座に計上（簡略化版）')
            new_lines.append(f'{indent}    if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():')
            new_lines.append(f'{indent}        if position.dividend_amount and position.dividend_amount > 0:')
            new_lines.append(f'{indent}            # 税引後配当金を計算')
            new_lines.append(f'{indent}            net_dividend_per_share = position.dividend_amount * (1 - self.execution_config.tax_rate)')
            new_lines.append(f'{indent}            ')
            new_lines.append(f'{indent}            log.info(f"Dividend payment: {{position.ticker}} - {{position.dividend_amount:.2f}} x {{position.total_shares}} shares")')
            new_lines.append(f'{indent}            ')
            new_lines.append(f'{indent}            self.portfolio.update_dividend(')
            new_lines.append(f'{indent}                ticker=position.ticker,')
            new_lines.append(f'{indent}                dividend_per_share=net_dividend_per_share,')
            new_lines.append(f'{indent}                date=current_date')
            new_lines.append(f'{indent}            )')
            
            # 元のメソッドの残りをスキップ
            while i < len(lines):
                if i + 1 < len(lines) and lines[i + 1].strip() != '' and not lines[i + 1].startswith(' '):
                    break
                i += 1
            
            in_process_dividends = False
        else:
            new_lines.append(line)
            i += 1
    
    # ファイルに書き込み
    with open(engine_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    
    print("✅ 配当処理を修正しました（権利落ち日に即座に計上）")


def verify_position_dividend_info():
    """ポジションに配当情報が正しく設定されているか確認"""
    print("\n=== ポジションの配当情報設定を確認 ===\n")
    
    # data_manager.pyのget_next_dividendメソッドも確認
    data_manager_file = Path("src/data/data_manager.py")
    
    with open(data_manager_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'get_next_dividend' in content:
        print("✅ get_next_dividendメソッドが存在")
        
        # 配当情報の辞書形式を確認
        print("\n配当情報の辞書には以下が含まれる必要があります:")
        print("- ex_dividend_date: 権利落ち日")
        print("- record_date: 権利確定日")
        print("- dividend_amount: 配当金額")
    else:
        print("❌ get_next_dividendメソッドが見つかりません")


def main():
    """メイン処理"""
    print("配当処理の簡略化修正")
    print("=" * 70)
    
    print("\n⚠️ 注意: このスクリプトはengine.pyを修正します")
    response = input("続行しますか？ (y/n): ")
    
    if response.lower() != 'y':
        print("中止しました")
        return
    
    fix_dividend_immediate_payment()
    verify_position_dividend_info()
    
    print("\n\n=== 修正完了 ===")
    print("\n次のステップ:")
    print("1. キャッシュをクリア:")
    print("   del /s /q data\\cache\\*")
    print("\n2. テスト実行:")
    print("   python main.py --config config/test_fixed.yaml")
    print("\n3. 配当収入を確認:")
    print("   total_dividendが0より大きくなっているはずです")


if __name__ == "__main__":
    main()
