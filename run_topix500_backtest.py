#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TOPIX500全銘柄バックテスト実行スクリプト
大規模データ処理に対応した実行環境
"""

import sys
import os
import gc
import psutil
import time
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from main import run_backtest
from src.utils.logger import log


def check_system_resources():
    """システムリソースをチェック"""
    # メモリ情報
    memory = psutil.virtual_memory()
    total_gb = memory.total / (1024**3)
    available_gb = memory.available / (1024**3)
    used_percent = memory.percent
    
    print("=" * 60)
    print("システムリソース情報")
    print("=" * 60)
    print(f"総メモリ: {total_gb:.1f} GB")
    print(f"利用可能: {available_gb:.1f} GB")
    print(f"使用率: {used_percent:.1f}%")
    
    # CPU情報
    cpu_count = psutil.cpu_count()
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"\nCPUコア数: {cpu_count}")
    print(f"CPU使用率: {cpu_percent:.1f}%")
    
    # 推奨事項
    print("\n推奨環境:")
    print("- メモリ: 16GB以上")
    print("- CPU: 4コア以上")
    print("- ストレージ: 10GB以上の空き容量")
    
    # 警告
    if available_gb < 8:
        print("\n⚠️ 警告: 利用可能メモリが8GB未満です。")
        print("   大規模バックテストではメモリ不足になる可能性があります。")
    
    return available_gb >= 4  # 最低4GBは必要


def optimize_memory():
    """メモリ最適化"""
    gc.collect()
    
    # Pythonのメモリ使用量を取得
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / (1024**2)
    
    print(f"\n現在のメモリ使用量: {memory_mb:.1f} MB")
    
    if memory_mb > 4096:  # 4GB以上使用している場合
        print("メモリ使用量が多いため、ガベージコレクションを実行します...")
        gc.collect()
        time.sleep(1)
        
        # 再度チェック
        memory_mb = process.memory_info().rss / (1024**2)
        print(f"最適化後のメモリ使用量: {memory_mb:.1f} MB")


def print_execution_plan():
    """実行計画を表示"""
    print("\n" + "=" * 60)
    print("TOPIX500全銘柄バックテスト実行計画")
    print("=" * 60)
    
    print("\n【対象】")
    print("- 銘柄数: 約450銘柄（TOPIX500主要構成銘柄）")
    print("- 期間: 2010年1月～2023年12月（14年間）")
    print("- 初期資本: 1億円")
    
    print("\n【戦略パラメータ】")
    print("- エントリー: 権利確定日の3営業日前")
    print("- 1銘柄投資額: 200万円")
    print("- 最大保有銘柄: 50")
    print("- 買い増し: 権利落ち日の下落時（30%まで）")
    print("- 損切り: -8%")
    print("- 最大保有期間: 20営業日")
    
    print("\n【推定実行時間】")
    print("- データ取得: 30-60分")
    print("- バックテスト計算: 20-40分")
    print("- レポート生成: 5-10分")
    print("- 合計: 1-2時間")
    
    print("\n【出力】")
    print("- 取引履歴CSV")
    print("- ポートフォリオ推移CSV")
    print("- パフォーマンス指標JSON")
    print("- HTMLレポート（グラフ付き）")
    print("- 結果保存先: ./data/results/topix500_full/")


def monitor_progress(start_time):
    """進捗モニタリング"""
    elapsed = time.time() - start_time
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)
    
    # メモリ使用量
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / (1024**2)
    
    return f"経過時間: {hours:02d}:{minutes:02d}:{seconds:02d} | メモリ: {memory_mb:.0f}MB"


def main():
    """メイン実行関数"""
    print("\n" + "=" * 70)
    print("TOPIX500全銘柄 配当取り戦略バックテスト")
    print("Full-Scale Dividend Capture Strategy Backtest")
    print("=" * 70)
    
    # システムリソースチェック
    if not check_system_resources():
        response = input("\nメモリが不足している可能性があります。続行しますか？ (y/n): ")
        if response.lower() != 'y':
            print("実行を中止しました。")
            return 1
    
    # 実行計画表示
    print_execution_plan()
    
    # 確認
    print("\n" + "=" * 60)
    response = input("上記の内容でバックテストを開始しますか？ (y/n): ")
    if response.lower() != 'y':
        print("実行を中止しました。")
        return 0
    
    # 開始時刻記録
    start_time = time.time()
    print(f"\n開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    try:
        # メモリ最適化
        optimize_memory()
        
        # バックテスト実行
        print("\nバックテストを開始します...")
        print("（進捗状況は ./logs/topix500_backtest.log で確認できます）")
        
        config_path = "config/topix500_full_config.yaml"
        output_dir = "./data/results/topix500_full"
        
        # 出力ディレクトリ作成
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 定期的な進捗表示のためのコールバック設定
        def progress_callback():
            status = monitor_progress(start_time)
            print(f"\r{status}", end='', flush=True)
        
        # バックテスト実行
        run_backtest(
            config_path=config_path,
            output_dir=output_dir,
            visualize=True  # 大規模でもグラフは生成
        )
        
        # 完了
        end_time = time.time()
        elapsed_time = end_time - start_time
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        
        print("\n\n" + "=" * 60)
        print("✅ バックテスト完了！")
        print("=" * 60)
        print(f"終了時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"実行時間: {hours}時間{minutes}分{seconds}秒")
        
        # 最終メモリ使用量
        optimize_memory()
        
        print("\n結果ファイル:")
        results_path = Path(output_dir)
        for file in sorted(results_path.glob("*")):
            if file.is_file():
                size_mb = file.stat().st_size / (1024**2)
                print(f"  - {file.name} ({size_mb:.1f}MB)")
        
        print("\n" + "=" * 60)
        print("📊 HTMLレポートをブラウザで開いて結果を確認してください。")
        print("=" * 60)
        
        # HTMLレポートを自動で開く（オプション）
        html_files = list(results_path.glob("*.html"))
        if html_files:
            latest_html = max(html_files, key=lambda x: x.stat().st_mtime)
            print(f"\nHTMLレポート: {latest_html}")
            
            response = input("\nブラウザで開きますか？ (y/n): ")
            if response.lower() == 'y':
                import webbrowser
                webbrowser.open(str(latest_html))
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️ ユーザーによって中断されました。")
        elapsed = monitor_progress(start_time)
        print(f"中断時の状況: {elapsed}")
        return 1
        
    except Exception as e:
        print(f"\n\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        
        # エラー時のメモリ状況
        optimize_memory()
        
        return 1
    
    finally:
        # クリーンアップ
        gc.collect()


if __name__ == "__main__":
    sys.exit(main())
