#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当取り戦略バックテスト - クイックスタート
少数銘柄・短期間でのテスト実行
"""

import sys
from pathlib import Path
import yaml

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.append(str(project_root))


def create_quick_config():
    """クイックスタート用の設定を作成"""
    config = {
        'backtest': {
            'start_date': '2023-01-01',
            'end_date': '2023-06-30',  # 6ヶ月間のみ
            'initial_capital': 10_000_000
        },
        'data_source': {
            'primary': 'yfinance',
            'cache_dir': './data/cache',
            'cache_expire_hours': 24
        },
        'strategy': {
            'entry': {
                'days_before_record': 3,
                'position_size': 2_000_000,  # 銘柄数が少ないので増額
                'max_positions': 5
            },
            'addition': {
                'enabled': True,
                'add_ratio': 0.5,
                'add_on_drop': True
            },
            'exit': {
                'max_holding_days': 20,
                'stop_loss_pct': 0.1,
                'take_profit_on_window_fill': True
            }
        },
        'execution': {
            'slippage': 0.001,
            'commission': 0.0005,
            'min_commission': 100
        },
        'universe': {
            'tickers': [
                '7203',  # トヨタ自動車
                '6758',  # ソニーグループ
                '9432',  # 日本電信電話
            ]
        },
        'logging': {
            'level': 'INFO',
            'file': './logs/quickstart.log',
            'format': '{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}'
        },
        'output': {
            'results_dir': './data/results/quickstart',
            'report_format': ['json', 'csv', 'html'],
            'save_trades': True,
            'save_portfolio_history': True
        }
    }
    
    # 設定ファイルを保存
    config_path = Path('config/quickstart_config.yaml')
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    return config_path


def main():
    """クイックスタート実行"""
    print("=" * 60)
    print("配当取り戦略バックテスト - クイックスタート")
    print("=" * 60)
    print()
    print("少数銘柄・短期間でのテスト実行を行います。")
    print("対象銘柄: トヨタ、ソニー、NTT")
    print("期間: 2023年1月～6月（6ヶ月）")
    print()
    
    # 設定ファイルを作成
    config_path = create_quick_config()
    print(f"設定ファイルを作成しました: {config_path}")
    print()
    
    # バックテストを実行
    try:
        from main import run_backtest
        
        print("バックテストを開始します...")
        print("-" * 60)
        
        run_backtest(
            config_path=str(config_path),
            output_dir='./data/results/quickstart',
            visualize=True
        )
        
        print()
        print("=" * 60)
        print("クイックスタートが完了しました！")
        print()
        print("結果は以下のフォルダに保存されています:")
        print("  ./data/results/quickstart/")
        print()
        print("次のステップ:")
        print("1. config/config.yaml を編集して、より多くの銘柄を追加")
        print("2. バックテスト期間を延長")
        print("3. 戦略パラメータを調整")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        print("\n以下を確認してください:")
        print("1. 必要なパッケージがインストールされているか")
        print("   pip install -r requirements.txt")
        print("2. インターネット接続が正常か（yfinanceのデータ取得のため）")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
