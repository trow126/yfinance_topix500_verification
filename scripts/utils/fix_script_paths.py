#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクリプトのインポートパスを修正
scriptsディレクトリ配下のファイルのパスを自動修正
"""

import os
from pathlib import Path
import re


def fix_import_paths(file_path: Path, depth: int) -> bool:
    """
    ファイル内のインポートパスを修正
    
    Args:
        file_path: 修正対象ファイル
        depth: プロジェクトルートまでの階層数
        
    Returns:
        修正を行った場合True
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 修正前のパターン
        old_patterns = [
            r'sys\.path\.append\(os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\)',
            r'sys\.path\.append\(os\.path\.dirname\(os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\)\)'
        ]
        
        # 修正後のパス（階層数に応じて）
        if depth == 1:
            new_path = 'sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))'
        elif depth == 2:
            new_path = 'sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))'
        else:
            return False
        
        modified = False
        for pattern in old_patterns:
            if re.search(pattern, content):
                content = re.sub(pattern, new_path, content)
                modified = True
        
        if modified:
            # コメントを追加
            content = content.replace(
                new_path,
                f'# プロジェクトルートをパスに追加（{depth}つ上のディレクトリ）\n{new_path}'
            )
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ 修正完了: {file_path}")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ エラー: {file_path} - {e}")
        return False


def main():
    """メイン処理"""
    print("スクリプトのインポートパスを修正します...\n")
    
    scripts_dir = Path("scripts")
    
    # 修正対象のパターン
    patterns = [
        (scripts_dir / "debug", 2),  # debug配下は2階層上
        (scripts_dir / "fix", 2),    # fix配下は2階層上
        (scripts_dir / "run", 2),    # run配下は2階層上
        (scripts_dir / "test", 2),   # test配下は2階層上
        (scripts_dir, 1),            # scripts直下は1階層上
    ]
    
    total_fixed = 0
    
    for target_dir, depth in patterns:
        if not target_dir.exists():
            continue
        
        print(f"\n【{target_dir}】")
        
        # .pyファイルを検索
        if target_dir.is_dir():
            py_files = list(target_dir.glob("*.py"))
        else:
            py_files = []
        
        for py_file in py_files:
            if py_file.name == "fix_script_paths.py":
                continue  # 自分自身はスキップ
            
            if fix_import_paths(py_file, depth):
                total_fixed += 1
    
    print(f"\n\n修正完了: {total_fixed}ファイル")
    
    # 確認のための表示
    print("\n修正後は以下のようにインポートできます:")
    print("  from src.utils.logger import log")
    print("  from src.data.data_manager import DataManager")
    print("  from src.strategy.dividend_strategy import DividendStrategy")


if __name__ == "__main__":
    main()
