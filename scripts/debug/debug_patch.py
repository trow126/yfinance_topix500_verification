#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
デバッグパッチ適用スクリプト
売却株数2倍問題を解決するための修正
"""

import shutil
from pathlib import Path


def create_debug_engine():
    """デバッグ版engine.pyを作成"""
    print("=== デバッグ版engine.pyの作成 ===\n")
    
    # オリジナルをバックアップ
    original = Path("src/backtest/engine.py")
    backup = Path("src/backtest/engine.py.backup")
    
    if not backup.exists():
        shutil.copy(original, backup)
        print(f"バックアップ作成: {backup}")
    
    # デバッグコードを挿入する場所を探す
    with open(original, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # _execute_exitメソッドを探す
    for i, line in enumerate(lines):
        if "def _execute_exit" in line:
            print(f"_execute_exitメソッドを発見: 行{i+1}")
            
            # デバッグコードを挿入
            insert_pos = i + 5  # メソッド定義の少し後
            debug_code = '''        # デバッグ: 売却前の株数を確認
        position = self.portfolio.position_manager.get_position(signal.ticker)
        if position:
            log.warning(f"[DEBUG] {signal.ticker}: 売却前 - position.total_shares={position.total_shares}, signal.shares={signal.shares}")
            if position.total_shares != signal.shares:
                log.error(f"[DEBUG] 株数不一致！ position={position.total_shares}, signal={signal.shares}")
        
'''
            lines.insert(insert_pos, debug_code)
            break
    
    # 保存するか確認
    print("\nデバッグコードを挿入しますか？ (y/n): ", end='')
    response = input()
    
    if response.lower() == 'y':
        with open(original, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("✓ デバッグコードを挿入しました")
        return True
    
    return False


def create_fixed_position_manager():
    """修正版position_manager.pyの提案"""
    print("\n\n=== 修正版position_manager.pyの提案 ===\n")
    
    fix_code = '''
# src/strategy/position_manager.py の to_dict メソッドを修正

def to_dict(self) -> Dict:
    """辞書形式に変換（修正版）"""
    # デバッグ: 売却後のtotal_sharesを確認
    if self.status == PositionStatus.CLOSED:
        # クローズ後は売却した株数を記録
        sold_shares = sum(t.shares for t in self.trades if t.trade_type == TradeType.SELL)
        bought_shares = sum(t.shares for t in self.trades if t.trade_type == TradeType.BUY)
        log.debug(f"{self.ticker}: 買い合計={bought_shares}, 売り合計={sold_shares}")
    
    return {
        'ticker': self.ticker,
        'status': self.status.value,
        'entry_date': self.entry_date.strftime('%Y-%m-%d'),
        'entry_price': self.entry_price,
        'total_shares': self.total_shares,  # クローズ後は0になっているはず
        'average_price': self.average_price,
        'exit_date': self.exit_date.strftime('%Y-%m-%d') if self.exit_date else None,
        'exit_price': self.exit_price,
        'exit_reason': self.exit_reason,
        'realized_pnl': self.realized_pnl,
        'dividend_received': self.dividend_received,
        'total_commission': self.total_commission,
        'trade_count': len(self.trades)
    }
'''
    
    print(fix_code)


def suggest_immediate_fix():
    """即効性のある修正案"""
    print("\n\n=== 即効性のある修正案 ===\n")
    
    print("1. **買い増し機能を正しく有効化**")
    print("   - 配当取り戦略の本来のコンセプトに沿う")
    print("   - addition.enabled: true")
    print("   - add_ratio: 1.0（同額まで買い増し）")
    
    print("\n2. **エンジンの買い増し処理を確認**")
    print("   - _process_existing_positionsメソッド")
    print("   - 権利落ち日の処理部分")
    
    print("\n3. **シグナルの株数を明示的にチェック**")
    print("   - check_exit_signalで返される株数")
    print("   - position.total_sharesとの一致を確認")


def run_verification_test():
    """検証テストの実行"""
    print("\n\n=== 検証テストの提案 ===\n")
    
    print("以下のテストを順番に実行してください：")
    print()
    print("1. デバッグパッチを適用")
    print("   python debug_patch.py")
    print()
    print("2. 買い増し有効版でテスト")
    print("   python main.py --config config/addition_test.yaml")
    print()
    print("3. ログファイルを確認")
    print("   logs/addition_test.log")
    print()
    print("4. 取引履歴を確認")
    print("   - 「Add position」の記録があるか")
    print("   - 売却株数が正しいか")


if __name__ == "__main__":
    print("売却株数2倍問題 - デバッグパッチ")
    print("=" * 60)
    
    # デバッグ版エンジンの作成
    success = create_debug_engine()
    
    # 修正案の提示
    create_fixed_position_manager()
    suggest_immediate_fix()
    run_verification_test()
    
    if success:
        print("\n" + "=" * 60)
        print("デバッグパッチが適用されました。")
        print("次のコマンドでテストを実行してください：")
        print("  python main.py --config config/minimal_debug.yaml --no-viz")
