#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
プロジェクト構造確認スクリプト
実装されたファイルとディレクトリ構造を表示
"""

import os
from pathlib import Path


def print_tree(directory, prefix="", is_last=True, ignore_dirs=None):
    """ディレクトリツリーを表示"""
    if ignore_dirs is None:
        ignore_dirs = {'.git', '__pycache__', '.pytest_cache', 'venv', '.idea'}
    
    path = Path(directory)
    
    if path.name in ignore_dirs:
        return
    
    # 現在のディレクトリ/ファイルを表示
    connector = "└── " if is_last else "├── "
    print(prefix + connector + path.name)
    
    # ディレクトリの場合は中身を表示
    if path.is_dir():
        extension = "    " if is_last else "│   "
        
        # ディレクトリ内のアイテムを取得してソート
        items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
        
        for i, item in enumerate(items):
            is_last_item = i == len(items) - 1
            print_tree(item, prefix + extension, is_last_item, ignore_dirs)


def main():
    """メイン関数"""
    print("=" * 60)
    print("配当取り戦略バックテストシステム - プロジェクト構造")
    print("=" * 60)
    print()
    
    # プロジェクトルート
    project_root = Path(__file__).parent
    
    # 主要ディレクトリ
    print("【ディレクトリ構造】")
    print("yfinance_topix500_verification/")
    
    # 各ディレクトリを表示
    main_dirs = ['src', 'config', 'data', 'tests', 'docs']
    
    for i, dir_name in enumerate(main_dirs):
        dir_path = project_root / dir_name
        if dir_path.exists():
            is_last = i == len(main_dirs) - 1
            print_tree(dir_path, "", is_last)
    
    print()
    print("【主要ファイル】")
    
    # 主要ファイルの存在確認
    main_files = [
        'main.py',
        'quickstart.py',
        'run_backtest.py',
        'run_backtest.bat',
        'requirements.txt',
        'README.md'
    ]
    
    for file_name in main_files:
        file_path = project_root / file_name
        status = "✓" if file_path.exists() else "✗"
        print(f"  {status} {file_name}")
    
    print()
    print("【統計情報】")
    
    # ファイル数をカウント
    py_files = list(project_root.glob("**/*.py"))
    py_files = [f for f in py_files if "__pycache__" not in str(f) and "venv" not in str(f)]
    
    print(f"  Pythonファイル数: {len(py_files)}")
    
    # 行数をカウント
    total_lines = 0
    for py_file in py_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                lines = len(f.readlines())
                total_lines += lines
        except:
            pass
    
    print(f"  総行数: {total_lines:,}")
    
    # モジュール一覧
    print()
    print("【実装モジュール】")
    
    modules = {
        'データ管理': ['src/data/yfinance_client.py', 'src/data/data_manager.py'],
        '戦略': ['src/strategy/dividend_strategy.py', 'src/strategy/position_manager.py'],
        'バックテスト': ['src/backtest/engine.py', 'src/backtest/portfolio.py', 'src/backtest/metrics.py'],
        'ユーティリティ': ['src/utils/calendar.py', 'src/utils/logger.py', 'src/utils/config.py', 'src/utils/report_generator.py']
    }
    
    for category, files in modules.items():
        print(f"\n  {category}:")
        for file_path in files:
            full_path = project_root / file_path
            if full_path.exists():
                print(f"    ✓ {file_path}")
            else:
                print(f"    ✗ {file_path}")
    
    print()
    print("=" * 60)
    print("実装完了！")
    print()
    print("次のコマンドでバックテストを実行できます:")
    print("  python quickstart.py    # クイックスタート")
    print("  python main.py          # フル実行")
    print("=" * 60)


if __name__ == "__main__":
    main()
