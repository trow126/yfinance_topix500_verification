#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
position_manager.pyの株数重複バグを修正
"""

import shutil
from pathlib import Path
from datetime import datetime


def fix_position_manager():
    """position_manager.pyの株数重複バグを修正"""
    position_manager_path = Path("src/strategy/position_manager.py")
    
    # バックアップ作成
    backup_path = Path(f"src/strategy/position_manager.py.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(position_manager_path, backup_path)
    print(f"✓ バックアップを作成: {backup_path}")
    
    # ファイル内容を読み込み
    with open(position_manager_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修正対象のコードを探す
    old_code = """        # ポジションを作成
        position = Position(
            ticker=ticker,
            status=PositionStatus.OPEN,
            entry_date=date,
            entry_price=price,
            total_shares=shares,
            average_price=price
        )"""
    
    # 修正後のコード（total_sharesを0で初期化）
    new_code = """        # ポジションを作成
        position = Position(
            ticker=ticker,
            status=PositionStatus.OPEN,
            entry_date=date,
            entry_price=price,
            total_shares=0,  # add_tradeで追加されるため0で初期化
            average_price=price
        )"""
    
    if old_code in content:
        # コードを置換
        fixed_content = content.replace(old_code, new_code)
        
        # ファイルに書き戻し
        with open(position_manager_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        print("✓ position_manager.pyを修正しました")
        print("\n【修正内容】")
        print("Positionオブジェクト作成時のtotal_sharesを0で初期化")
        print("（add_tradeメソッドで正しく加算されるようになります）")
        return True
    else:
        print("⚠️ 修正対象のコードが見つかりません")
        return False


def verify_fix():
    """修正が正しく適用されたか確認"""
    position_manager_path = Path("src/strategy/position_manager.py")
    
    with open(position_manager_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修正後のコードが存在するか確認
    if 'total_shares=0,  # add_tradeで追加されるため0で初期化' in content:
        print("\n✓ 修正が正しく適用されています")
        return True
    else:
        print("\n❌ 修正が適用されていません")
        return False


def alternative_fix():
    """代替修正案：add_tradeメソッドを修正"""
    print("\n\n=== 代替修正案 ===")
    print("もう一つの修正方法として、add_tradeメソッドを修正する方法もあります：")
    print("""
    def add_trade(self, trade: Trade) -> None:
        self.trades.append(trade)
        
        if trade.trade_type == TradeType.BUY:
            # 最初の取引の場合は代入、それ以外は加算
            if len(self.trades) == 1:
                self.total_shares = trade.shares
            else:
                total_cost = self.average_price * self.total_shares + trade.amount
                self.total_shares += trade.shares
                self.average_price = total_cost / self.total_shares if self.total_shares > 0 else 0
    """)


def test_fix_instructions():
    """修正後のテスト手順"""
    print("\n\n=== 修正後のテスト手順 ===")
    print("""
1. バックテストを再実行:
   python main.py --config config/minimal_debug.yaml

2. 結果を確認:
   - 取引履歴でBUY: 500株、SELL: 500株となることを確認
   - ログで株数不一致の警告が出ないことを確認

3. 詳細な追跡:
   python trace_share_changes.py
   - 株数が500のまま維持されることを確認

4. 最終確認:
   python detect_hidden_addition.py
   - 買い増しが実行されていないことを確認
""")


def main():
    """メイン処理"""
    print("=== position_manager.pyの株数重複バグ修正 ===\n")
    
    print("問題の原因:")
    print("- Positionオブジェクト作成時にtotal_shares=500で初期化")
    print("- add_tradeメソッドでさらに500株追加")
    print("- 結果として500 + 500 = 1000株になる")
    
    print("\n修正内容:")
    print("- Positionオブジェクト作成時のtotal_sharesを0で初期化")
    print("- add_tradeメソッドで正しく株数が設定される")
    
    # 修正を適用
    if fix_position_manager():
        verify_fix()
        alternative_fix()
        test_fix_instructions()
    
    print("\n修正が完了しました。バックテストを再実行して結果を確認してください。")


if __name__ == "__main__":
    main()
