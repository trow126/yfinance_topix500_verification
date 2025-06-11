#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配当取り戦略バックテストシステム
メインエントリーポイント
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent))

from src.utils.config import load_config
from src.utils.logger import BacktestLogger, log
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import MetricsCalculator, BacktestVisualizer


def setup_logging(config_path: str) -> None:
    """ロギングの設定"""
    try:
        config = load_config(config_path)
        logger = BacktestLogger()
        logger.setup_logger(
            log_level=config.logging.level,
            log_file=config.logging.file,
            format_string=config.logging.format
        )
    except Exception as e:
        # 設定ファイルが読めない場合はデフォルト設定
        logger = BacktestLogger()
        logger.setup_logger(log_level="INFO")
        log.warning(f"Could not load logging config: {e}")


def print_banner() -> None:
    """バナー表示"""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║         配当取り戦略バックテストシステム v1.0              ║
    ║         Dividend Capture Strategy Backtest System         ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_config_summary(config) -> None:
    """設定サマリーを表示"""
    print("\n【バックテスト設定】")
    print(f"  期間: {config.backtest.start_date} ～ {config.backtest.end_date}")
    print(f"  初期資本: {config.backtest.initial_capital:,} 円")
    print(f"  対象銘柄数: {len(config.universe.tickers)}")
    print(f"  1銘柄投資額: {config.strategy.entry.position_size:,} 円")
    print(f"  最大保有銘柄: {config.strategy.entry.max_positions}")
    print(f"  エントリー: 権利確定日の{config.strategy.entry.days_before_record}営業日前")
    print(f"  最大保有期間: {config.strategy.exit.max_holding_days}営業日")
    print(f"  損切りライン: {config.strategy.exit.stop_loss_pct*100:.0f}%")
    print()


def run_backtest(config_path: str, output_dir: str = None, visualize: bool = True) -> None:
    """
    バックテストを実行
    
    Args:
        config_path: 設定ファイルパス
        output_dir: 出力ディレクトリ（指定しない場合は設定ファイルの値を使用）
        visualize: グラフを表示するか
    """
    # 設定を読み込み
    log.info(f"Loading configuration from: {config_path}")
    config = load_config(config_path)
    
    # 出力ディレクトリの上書き
    if output_dir:
        config.output.results_dir = output_dir
    
    # 設定サマリーを表示
    print_config_summary(config)
    
    # バックテストエンジンを初期化
    log.info("Initializing backtest engine...")
    engine = BacktestEngine(config)
    
    # バックテスト実行
    print("バックテストを実行中...")
    start_time = datetime.now()
    
    try:
        results = engine.run()
        
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        print(f"\nバックテスト完了！ (実行時間: {elapsed_time:.1f}秒)")
        
        # 結果サマリーを表示
        display_results(results)
        
        # グラフの生成と表示
        if visualize and not results['portfolio_history'].empty:
            print("\nパフォーマンスグラフを生成中...")
            
            output_path = Path(config.output.results_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # タイムスタンプ付きのファイル名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            chart_path = output_path / f"performance_chart_{timestamp}.png"
            
            BacktestVisualizer.plot_portfolio_performance(
                results['portfolio_history'],
                save_path=chart_path
            )
            
            print(f"グラフを保存しました: {chart_path}")
        
        # 詳細レポートの生成
        generate_report(results, config)
        
    except Exception as e:
        log.error(f"Backtest failed: {str(e)}")
        raise


def display_results(results: Dict) -> None:
    """結果を表示"""
    metrics = results.get('metrics', {})
    
    print("\n" + "="*60)
    print("【バックテスト結果サマリー】")
    print("="*60)
    
    # リターン
    print("\n■ リターン")
    print(f"  総リターン: {metrics.get('total_return', 0):.2%}")
    print(f"  年率リターン: {metrics.get('annualized_return', 0):.2%}")
    
    # リスク
    print("\n■ リスク")
    print(f"  年率ボラティリティ: {metrics.get('annualized_volatility', 0):.2%}")
    print(f"  最大ドローダウン: {metrics.get('max_drawdown', 0):.2%}")
    
    # リスク調整後リターン
    print("\n■ リスク調整後リターン")
    print(f"  シャープレシオ: {metrics.get('sharpe_ratio', 0):.2f}")
    print(f"  ソルティノレシオ: {metrics.get('sortino_ratio', 0):.2f}")
    
    # 取引統計
    print("\n■ 取引統計")
    print(f"  総取引回数: {metrics.get('total_trades', 0)}")
    print(f"  勝率: {metrics.get('win_rate', 0):.1%}")
    print(f"  プロフィットファクター: {metrics.get('profit_factor', 0):.2f}")
    
    # 配当
    print("\n■ 配当")
    print(f"  受取配当総額: {metrics.get('total_dividend', 0):,.0f} 円")
    
    # 最終結果
    print("\n■ 最終結果")
    print(f"  最終ポートフォリオ価値: {metrics.get('final_value', 0):,.0f} 円")
    print(f"  支払手数料総額: {metrics.get('total_commission', 0):,.0f} 円")
    
    print("\n" + "="*60)


def generate_report(results: Dict, config) -> None:
    """詳細レポートを生成"""
    from src.backtest.metrics import MetricsCalculator
    from src.utils.report_generator import generate_html_report
    
    # テキストレポートの生成
    report_content = MetricsCalculator.generate_summary_report(results)
    
    # ファイルに保存
    output_path = Path(config.output.results_dir)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = output_path / f"backtest_report_{timestamp}.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    log.info(f"Text report saved to: {report_file}")
    
    # HTMLレポートの生成
    if 'html' in config.output.report_format:
        try:
            html_report_path = generate_html_report(results, config, config.output.results_dir)
            log.info(f"HTML report saved to: {html_report_path}")
            print(f"\nHTMLレポートを生成しました: {html_report_path}")
        except Exception as e:
            log.warning(f"Failed to generate HTML report: {e}")


def main():
    """メイン関数"""
    # コマンドライン引数のパース
    parser = argparse.ArgumentParser(
        description='配当取り戦略バックテストシステム',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='設定ファイルのパス (default: config/config.yaml)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='結果出力ディレクトリ (default: 設定ファイルの値を使用)'
    )
    
    parser.add_argument(
        '--no-viz',
        action='store_true',
        help='グラフ表示を無効化'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='ログ出力を最小限に'
    )
    
    args = parser.parse_args()
    
    # バナー表示
    if not args.quiet:
        print_banner()
    
    # ロギング設定
    setup_logging(args.config)
    
    if args.quiet:
        # quietモードの場合はログレベルを変更
        logger = BacktestLogger()
        logger.setup_logger(log_level="WARNING")
    
    try:
        # バックテスト実行
        run_backtest(
            config_path=args.config,
            output_dir=args.output,
            visualize=not args.no_viz
        )
        
        print("\n✅ バックテストが正常に完了しました。")
        
    except FileNotFoundError as e:
        print(f"\n❌ エラー: ファイルが見つかりません - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
