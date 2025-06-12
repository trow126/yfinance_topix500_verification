#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
バックテスト実行スクリプト
簡単な実行例
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from main import main


if __name__ == "__main__":
    # デフォルト設定でバックテストを実行
    print("配当取り戦略バックテストを開始します...")
    print("-" * 60)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nバックテストを中断しました。")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nエラーが発生しました: {e}")
        sys.exit(1)
