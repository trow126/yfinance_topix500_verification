#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
隠れた買い増し問題の根本的な修正
portfolio.execute_buyメソッドの修正
"""

import shutil
from pathlib import Path
from datetime import datetime


def apply_portfolio_fix():
    """portfolio.pyを修正して、意図しない買い増しを防ぐ"""
    portfolio_path = Path("src/backtest/portfolio.py")
    
    # バックアップ作成
    backup_path = Path(f"src/backtest/portfolio.py.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(portfolio_path, backup_path)
    print(f"✓ バックアップを作成: {backup_path}")
    
    # ファイル内容を読み込み
    with open(portfolio_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修正対象のコードを探す
    old_code = """        # ポジションの有無をチェック
        if self.position_manager.get_position(ticker):
            # 既存ポジションに追加
            self.position_manager.add_to_position(
                ticker=ticker,
                date=date,
                price=price,
                shares=shares,
                commission=commission,
                reason=reason
            )"""
    
    # 修正後のコード
    new_code = """        # ポジションの有無をチェック
        if self.position_manager.get_position(ticker):
            # 買い増し理由を明示的にチェック
            if reason and ("Add" in reason or "add" in reason):
                # 買い増しの場合のみ追加
                self.position_manager.add_to_position(
                    ticker=ticker,
                    date=date,
                    price=price,
                    shares=shares,
                    commission=commission,
                    reason=reason
                )
            else:
                # 既存ポジションがある場合はスキップ
                log.warning(f"Position already exists for {ticker}, skipping duplicate buy. Reason: {reason}")
                return False"""
    
    if old_code in content:
        # コードを置換
        fixed_content = content.replace(old_code, new_code)
        
        # ファイルに書き戻し
        with open(portfolio_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        print("✓ portfolio.pyを修正しました")
        return True
    else:
        print("⚠️ 修正対象のコードが見つかりません")
        return False


def verify_fix():
    """修正が正しく適用されたか確認"""
    portfolio_path = Path("src/backtest/portfolio.py")
    
    with open(portfolio_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修正後のコードが存在するか確認
    if 'if reason and ("Add" in reason or "add" in reason):' in content:
        print("\n✓ 修正が正しく適用されています")
        print("  - 買い増し理由のチェックが追加されました")
        print("  - 重複買いの警告が追加されました")
        return True
    else:
        print("\n❌ 修正が適用されていません")
        return False


def test_fix():
    """修正のテストコード"""
    print("\n=== 修正のテスト ===")
    print("""
テスト方法:
1. バックテストを再実行:
   python main.py --config config/minimal_debug.yaml

2. 結果を確認:
   - 取引履歴で500株のままであることを確認
   - ログで重複買いの警告が出ることを確認

3. 買い増しが有効な設定でもテスト:
   python main.py --config config/config.yaml
   
4. 問題が解決したか確認:
   python detect_hidden_addition.py
""")


def create_comprehensive_fix():
    """より包括的な修正案"""
    print("\n=== より包括的な修正案 ===")
    
    fix_code = '''
# engine.pyも修正する場合のコード

def _execute_entry(self, signal, execution_price: float, dividend_info: Optional[Dict] = None) -> None:
    """エントリー（買い）を実行"""
    
    # SignalTypeによる分岐を追加
    if signal.signal_type == SignalType.ENTRY:
        # 新規エントリーの場合、既存ポジションがないことを確認
        if self.portfolio.position_manager.get_position(signal.ticker):
            log.warning(f"Duplicate entry signal for {signal.ticker}, skipping")
            return
    elif signal.signal_type == SignalType.ADD:
        # 買い増しの場合、既存ポジションが必要
        if not self.portfolio.position_manager.get_position(signal.ticker):
            log.error(f"No position to add for {signal.ticker}")
            return
    
    # 以下、既存の処理...
'''
    print(fix_code)


def main():
    """メイン処理"""
    print("=== 隠れた買い増し問題の根本的修正 ===\n")
    
    print("問題の原因:")
    print("- portfolio.execute_buyが既存ポジションに無条件で追加")
    print("- エントリーシグナルが重複して処理される可能性")
    print("- SignalTypeが考慮されていない")
    
    print("\n修正内容:")
    print("- 買い増し理由（'Add'を含む）の明示的チェック")
    print("- 重複買いの警告とスキップ")
    
    # 修正を適用
    if apply_portfolio_fix():
        verify_fix()
        test_fix()
        create_comprehensive_fix()
    
    print("\n修正が完了しました。バックテストを再実行して結果を確認してください。")


if __name__ == "__main__":
    main()
