#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTMLレポート生成
バックテスト結果を見やすいHTML形式で出力
"""

from datetime import datetime
from pathlib import Path
from typing import Dict
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json


class HTMLReportGenerator:
    """HTMLレポート生成クラス"""
    
    @staticmethod
    def generate_report(results: Dict, config: Dict, output_path: Path) -> None:
        """
        HTMLレポートを生成
        
        Args:
            results: バックテスト結果
            config: バックテスト設定
            output_path: 出力パス
        """
        # タイムスタンプ
        timestamp = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
        
        # レポートHTML
        html_content = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>配当取り戦略バックテストレポート</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: 'メイリオ', 'Meiryo', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #2c3e50;
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .section {{
            background-color: white;
            padding: 30px;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }}
        .metric-card h3 {{
            margin: 0 0 10px 0;
            color: #7f8c8d;
            font-size: 0.9em;
            font-weight: normal;
        }}
        .metric-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .metric-card.positive .value {{
            color: #27ae60;
        }}
        .metric-card.negative .value {{
            color: #e74c3c;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: bold;
            color: #2c3e50;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .chart-container {{
            margin: 20px 0;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 10px;
        }}
        .config-table {{
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 10px;
        }}
        .config-table .label {{
            font-weight: bold;
            color: #7f8c8d;
        }}
        .footer {{
            text-align: center;
            color: #7f8c8d;
            margin-top: 50px;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>配当取り戦略バックテストレポート</h1>
        <p>生成日時: {timestamp}</p>
    </div>
"""
        
        # パフォーマンスサマリー
        html_content += HTMLReportGenerator._generate_performance_summary(results['metrics'])
        
        # パフォーマンスチャート
        html_content += HTMLReportGenerator._generate_performance_charts(results)
        
        # 取引統計
        html_content += HTMLReportGenerator._generate_trade_statistics(results)
        
        # 設定情報
        html_content += HTMLReportGenerator._generate_config_section(config)
        
        # フッター
        html_content += """
    <div class="footer">
        <p>このレポートは配当取り戦略バックテストシステムによって自動生成されました。</p>
        <p>投資は自己責任で行ってください。</p>
    </div>
</body>
</html>
"""
        
        # ファイルに保存
        report_file = output_path / f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return report_file
    
    @staticmethod
    def _generate_performance_summary(metrics: Dict) -> str:
        """パフォーマンスサマリーセクションを生成"""
        html = """
    <div class="section">
        <h2>パフォーマンスサマリー</h2>
        <div class="metrics-grid">
"""
        
        # 主要指標
        metrics_display = [
            {
                'label': '総リターン',
                'value': f"{metrics.get('total_return', 0):.1%}",
                'class': 'positive' if metrics.get('total_return', 0) > 0 else 'negative'
            },
            {
                'label': '年率リターン',
                'value': f"{metrics.get('annualized_return', 0):.1%}",
                'class': 'positive' if metrics.get('annualized_return', 0) > 0 else 'negative'
            },
            {
                'label': 'シャープレシオ',
                'value': f"{metrics.get('sharpe_ratio', 0):.2f}",
                'class': 'positive' if metrics.get('sharpe_ratio', 0) > 1 else ''
            },
            {
                'label': '最大ドローダウン',
                'value': f"{metrics.get('max_drawdown', 0):.1%}",
                'class': 'negative' if metrics.get('max_drawdown', 0) < -0.1 else ''
            },
            {
                'label': '勝率',
                'value': f"{metrics.get('win_rate', 0):.1%}",
                'class': 'positive' if metrics.get('win_rate', 0) > 0.5 else ''
            },
            {
                'label': '総取引回数',
                'value': f"{metrics.get('total_trades', 0):,}",
                'class': ''
            },
            {
                'label': '最終資産',
                'value': f"¥{metrics.get('final_value', 0):,.0f}",
                'class': 'positive' if metrics.get('final_value', 0) > 10_000_000 else ''
            },
            {
                'label': '受取配当総額',
                'value': f"¥{metrics.get('total_dividend', 0):,.0f}",
                'class': 'positive'
            }
        ]
        
        for metric in metrics_display:
            html += f"""
            <div class="metric-card {metric['class']}">
                <h3>{metric['label']}</h3>
                <div class="value">{metric['value']}</div>
            </div>
"""
        
        html += """
        </div>
    </div>
"""
        return html
    
    @staticmethod
    def _generate_performance_charts(results: Dict) -> str:
        """パフォーマンスチャートセクションを生成"""
        if results['portfolio_history'].empty:
            return ""
        
        # チャートデータの準備
        portfolio_df = results['portfolio_history'].reset_index()
        
        # 累積リターンチャート
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('ポートフォリオ価値', '累積リターン', 'ドローダウン', '月次リターン分布'),
            vertical_spacing=0.12,
            horizontal_spacing=0.1
        )
        
        # 1. ポートフォリオ価値
        fig.add_trace(
            go.Scatter(
                x=portfolio_df['date'],
                y=portfolio_df['total_value'],
                mode='lines',
                name='ポートフォリオ価値',
                line=dict(color='blue', width=2)
            ),
            row=1, col=1
        )
        
        # 2. 累積リターン
        cumulative_returns = (portfolio_df['total_value'] / portfolio_df['total_value'].iloc[0] - 1) * 100
        fig.add_trace(
            go.Scatter(
                x=portfolio_df['date'],
                y=cumulative_returns,
                mode='lines',
                name='累積リターン',
                line=dict(color='green', width=2)
            ),
            row=1, col=2
        )
        
        # 3. ドローダウン
        running_max = portfolio_df['total_value'].expanding().max()
        drawdown = (portfolio_df['total_value'] - running_max) / running_max * 100
        fig.add_trace(
            go.Scatter(
                x=portfolio_df['date'],
                y=drawdown,
                mode='lines',
                fill='tozeroy',
                name='ドローダウン',
                line=dict(color='red', width=1)
            ),
            row=2, col=1
        )
        
        # 4. 月次リターン分布
        portfolio_df['date'] = pd.to_datetime(portfolio_df['date'])
        portfolio_df.set_index('date', inplace=True)
        monthly_returns = portfolio_df['total_value'].resample('M').last().pct_change() * 100
        
        fig.add_trace(
            go.Histogram(
                x=monthly_returns.dropna(),
                name='月次リターン',
                nbinsx=20,
                marker_color='lightblue'
            ),
            row=2, col=2
        )
        
        # レイアウト設定
        fig.update_layout(
            height=800,
            showlegend=False,
            title_text="パフォーマンス分析",
            title_font_size=20
        )
        
        # 軸ラベル
        fig.update_xaxes(title_text="日付", row=1, col=1)
        fig.update_xaxes(title_text="日付", row=1, col=2)
        fig.update_xaxes(title_text="日付", row=2, col=1)
        fig.update_xaxes(title_text="リターン (%)", row=2, col=2)
        
        fig.update_yaxes(title_text="価値 (円)", row=1, col=1)
        fig.update_yaxes(title_text="リターン (%)", row=1, col=2)
        fig.update_yaxes(title_text="ドローダウン (%)", row=2, col=1)
        fig.update_yaxes(title_text="頻度", row=2, col=2)
        
        # HTMLに埋め込み
        chart_html = fig.to_html(full_html=False, include_plotlyjs=False)
        
        html = f"""
    <div class="section">
        <h2>パフォーマンス分析</h2>
        <div class="chart-container">
            {chart_html}
        </div>
    </div>
"""
        return html
    
    @staticmethod
    def _generate_trade_statistics(results: Dict) -> str:
        """取引統計セクションを生成"""
        html = """
    <div class="section">
        <h2>取引統計</h2>
"""
        
        # ポジションサマリー
        if not results['positions'].empty:
            closed_positions = results['positions'][results['positions']['status'] == 'CLOSED']
            
            if not closed_positions.empty:
                # 上位・下位5銘柄
                top_positions = closed_positions.nlargest(5, 'realized_pnl')[['ticker', 'entry_date', 'exit_date', 'realized_pnl']]
                bottom_positions = closed_positions.nsmallest(5, 'realized_pnl')[['ticker', 'entry_date', 'exit_date', 'realized_pnl']]
                
                html += """
        <h3>上位パフォーマンス銘柄</h3>
        <table>
            <thead>
                <tr>
                    <th>銘柄</th>
                    <th>エントリー日</th>
                    <th>決済日</th>
                    <th>実現損益</th>
                </tr>
            </thead>
            <tbody>
"""
                for _, row in top_positions.iterrows():
                    pnl_class = 'positive' if row['realized_pnl'] > 0 else 'negative'
                    html += f"""
                <tr>
                    <td>{row['ticker']}</td>
                    <td>{row['entry_date']}</td>
                    <td>{row['exit_date']}</td>
                    <td class="{pnl_class}">¥{row['realized_pnl']:,.0f}</td>
                </tr>
"""
                
                html += """
            </tbody>
        </table>
        
        <h3>下位パフォーマンス銘柄</h3>
        <table>
            <thead>
                <tr>
                    <th>銘柄</th>
                    <th>エントリー日</th>
                    <th>決済日</th>
                    <th>実現損益</th>
                </tr>
            </thead>
            <tbody>
"""
                for _, row in bottom_positions.iterrows():
                    pnl_class = 'positive' if row['realized_pnl'] > 0 else 'negative'
                    html += f"""
                <tr>
                    <td>{row['ticker']}</td>
                    <td>{row['entry_date']}</td>
                    <td>{row['exit_date']}</td>
                    <td class="{pnl_class}">¥{row['realized_pnl']:,.0f}</td>
                </tr>
"""
                
                html += """
            </tbody>
        </table>
"""
        
        html += """
    </div>
"""
        return html
    
    @staticmethod
    def _generate_config_section(config: Dict) -> str:
        """設定情報セクションを生成"""
        html = """
    <div class="section">
        <h2>バックテスト設定</h2>
        <div class="config-table">
"""
        
        config_items = [
            ('バックテスト期間', f"{config['backtest']['start_date']} ～ {config['backtest']['end_date']}"),
            ('初期資本', f"¥{config['backtest']['initial_capital']:,}"),
            ('対象銘柄', f"{len(config['universe']['tickers'])}銘柄"),
            ('1銘柄投資額', f"¥{config['strategy']['entry']['position_size']:,}"),
            ('最大保有銘柄数', f"{config['strategy']['entry']['max_positions']}"),
            ('エントリータイミング', f"権利確定日の{config['strategy']['entry']['days_before_record']}営業日前"),
            ('買い増し', '有効' if config['strategy']['addition']['enabled'] else '無効'),
            ('最大保有期間', f"{config['strategy']['exit']['max_holding_days']}営業日"),
            ('損切りライン', f"{config['strategy']['exit']['stop_loss_pct']*100:.0f}%"),
            ('手数料率', f"{config['execution']['commission']*100:.2f}%"),
            ('スリッページ', f"{config['execution']['slippage']*100:.2f}%")
        ]
        
        for label, value in config_items:
            html += f"""
            <div class="label">{label}:</div>
            <div>{value}</div>
"""
        
        html += """
        </div>
    </div>
"""
        return html


# レポート生成関数
def generate_html_report(results: Dict, config, output_dir: str) -> Path:
    """
    HTMLレポートを生成する便利関数
    
    Args:
        results: バックテスト結果
        config: バックテスト設定
        output_dir: 出力ディレクトリ
        
    Returns:
        生成されたレポートファイルパス
    """
    import dataclasses
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 設定を辞書形式に変換
    config_dict = dataclasses.asdict(config)
    
    # レポート生成
    report_path = HTMLReportGenerator.generate_report(results, config_dict, output_path)
    
    return report_path


# テスト用コード
if __name__ == "__main__":
    # サンプルデータでテスト
    import numpy as np
    
    # サンプル結果
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    portfolio_values = 10_000_000 * (1 + np.random.randn(len(dates)).cumsum() * 0.001)
    
    sample_results = {
        'metrics': {
            'total_return': 0.152,
            'annualized_return': 0.148,
            'sharpe_ratio': 1.25,
            'max_drawdown': -0.082,
            'win_rate': 0.623,
            'total_trades': 45,
            'final_value': 11_520_000,
            'total_dividend': 320_000
        },
        'portfolio_history': pd.DataFrame({
            'date': dates,
            'total_value': portfolio_values
        }),
        'positions': pd.DataFrame(),
        'trades': pd.DataFrame()
    }
    
    # サンプル設定
    sample_config = {
        'backtest': {
            'start_date': '2023-01-01',
            'end_date': '2023-12-31',
            'initial_capital': 10_000_000
        },
        'strategy': {
            'entry': {
                'position_size': 1_000_000,
                'max_positions': 10,
                'days_before_record': 3
            },
            'addition': {
                'enabled': True
            },
            'exit': {
                'max_holding_days': 20,
                'stop_loss_pct': 0.1
            }
        },
        'execution': {
            'commission': 0.0005,
            'slippage': 0.001
        },
        'universe': {
            'tickers': ['7203', '6758', '9432', '6861', '8306']
        }
    }
    
    # レポート生成
    report_path = HTMLReportGenerator.generate_report(
        sample_results,
        sample_config,
        Path('./data/results')
    )
    
    print(f"レポートを生成しました: {report_path}")
