# 配当取り戦略バックテストシステム 実装計画書

## 1. 実装フェーズ

### フェーズ1: 基盤構築（1-2週間）
1. プロジェクト構造の作成
2. データ取得モジュールの実装
   - yfinanceクライアント（検証済みのコードを活用）
   - データキャッシュ機能
3. 営業日計算ユーティリティ
4. 基本的な単体テスト

### フェーズ2: 戦略実装（1週間）
1. 配当取り戦略ロジック
   - エントリールール
   - 買い増しルール
   - 決済ルール
2. ポジション管理
3. 戦略の単体テスト

### フェーズ3: バックテストエンジン（1-2週間）
1. ポートフォリオ管理
2. 取引実行モジュール
3. バックテストメインループ
4. 統合テスト

### フェーズ4: 評価・分析（1週間）
1. 評価指標計算
2. レポート生成
3. 可視化
4. 結果検証

### フェーズ5: 最適化・改善（継続的）
1. パフォーマンス最適化
2. パラメータ感度分析
3. 追加機能実装

## 2. 技術スタック

### 必須ライブラリ
```requirements.txt
# データ処理
pandas>=1.5.0
numpy>=1.23.0

# データ取得
yfinance>=0.2.18
requests>=2.28.0

# 日付処理
jpholiday>=0.1.8
python-dateutil>=2.8.2

# 設定管理
pyyaml>=6.0
python-dotenv>=0.21.0

# ロギング
loguru>=0.6.0

# データベース
sqlalchemy>=2.0.0
sqlite3  # 標準ライブラリ

# テスト
pytest>=7.2.0
pytest-cov>=4.0.0

# 可視化
matplotlib>=3.6.0
plotly>=5.11.0
seaborn>=0.12.0

# レポート生成
jinja2>=3.1.0
markdown>=3.4.0
```

### 開発環境
- Python 3.8以上
- Visual Studio Code / PyCharm
- Git for version control

## 3. 実装上の重要考慮事項

### 3.1 既存コードの活用
```python
# yfinance_topix500_verification.pyから活用可能な部分
class DividendDateCalculator:
    """権利落ち日から権利確定日を計算するクラス（既存）"""
    # このクラスはそのまま使用可能

class YFinanceDataChecker:
    """yfinanceでのデータ取得可能性を検証するクラス（改修して使用）"""
    # check_dividend_data, check_price_dataメソッドを
    # データ取得クラスのベースとして活用
```

### 3.2 データソースの優先順位
1. **初期実装**: yfinanceのみ（検証済み）
2. **将来拡張**: J-Quants API統合

### 3.3 エラーハンドリング戦略
```python
class BacktestError(Exception):
    """バックテスト基底例外クラス"""
    pass

class DataError(BacktestError):
    """データ関連エラー"""
    pass

class StrategyError(BacktestError):
    """戦略実行エラー"""
    pass

class ExecutionError(BacktestError):
    """取引実行エラー"""
    pass
```

## 4. サンプル実装

### 4.1 メインエントリーポイント
```python
# main.py
import argparse
from pathlib import Path
from src.backtest.engine import BacktestEngine
from src.utils.config import load_config

def main():
    parser = argparse.ArgumentParser(description='配当取り戦略バックテスト')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                        help='設定ファイルパス')
    parser.add_argument('--output', type=str, default='data/results',
                        help='結果出力ディレクトリ')
    args = parser.parse_args()
    
    # 設定読み込み
    config = load_config(args.config)
    
    # バックテスト実行
    engine = BacktestEngine(config)
    results = engine.run()
    
    # 結果保存
    output_dir = Path(args.output)
    results.save(output_dir)
    
    # サマリー表示
    print(results.summary())

if __name__ == '__main__':
    main()
```

### 4.2 簡易バックテスト例
```python
# 簡易版の実装例（概念実証用）
import pandas as pd
from datetime import datetime, timedelta

class SimpleDividendBacktest:
    def __init__(self, ticker: str, start_date: str, end_date: str):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.trades = []
        
    def run(self):
        # データ取得
        price_data = self.get_price_data()
        dividend_data = self.get_dividend_data()
        
        # 各配当について処理
        for div_date, div_amount in dividend_data.items():
            # エントリー
            entry_date = self.get_entry_date(div_date)
            if entry_date in price_data.index:
                entry_price = price_data.loc[entry_date, 'Close']
                
                # 権利落ち日の処理
                ex_date = self.get_ex_dividend_date(div_date)
                if ex_date in price_data.index:
                    ex_price = price_data.loc[ex_date, 'Close']
                    
                    # 決済処理（簡略化）
                    exit_date, exit_price = self.find_exit(
                        price_data, ex_date, entry_price
                    )
                    
                    # 取引記録
                    self.trades.append({
                        'entry_date': entry_date,
                        'entry_price': entry_price,
                        'exit_date': exit_date,
                        'exit_price': exit_price,
                        'dividend': div_amount,
                        'pnl': (exit_price - entry_price) + div_amount
                    })
        
        return pd.DataFrame(self.trades)
```

## 5. テスト戦略

### 5.1 単体テストの例
```python
# tests/test_dividend_calculator.py
import pytest
from datetime import date
from src.utils.calendar import DividendDateCalculator

class TestDividendDateCalculator:
    def test_calculate_record_date_weekday(self):
        """平日の権利落ち日から権利確定日を計算"""
        ex_date = date(2023, 3, 29)  # 水曜日
        record_date = DividendDateCalculator.calculate_record_date(ex_date)
        assert record_date == date(2023, 3, 31)  # 金曜日
    
    def test_calculate_record_date_with_holiday(self):
        """祝日を挟む場合の計算"""
        # 実際の祝日データでテスト
        pass
```

### 5.2 統合テストの例
```python
# tests/test_backtest_integration.py
import pytest
from src.backtest.engine import BacktestEngine

class TestBacktestIntegration:
    def test_single_stock_backtest(self, sample_config):
        """単一銘柄のバックテスト"""
        engine = BacktestEngine(sample_config)
        results = engine.run()
        
        assert results.total_trades > 0
        assert results.total_return is not None
        assert results.sharpe_ratio is not None
```

## 6. 段階的実装アプローチ

### ステップ1: 最小実装（MVP）
- TOPIX500から主要10銘柄で実装
- yfinanceデータのみ使用
- 基本的な戦略ルールのみ
- シンプルなレポート出力

### ステップ2: 機能拡張
- 全TOPIX500銘柄対応
- 詳細な評価指標
- パラメータ感度分析
- 高度なレポート機能

### ステップ3: 本番対応
- J-Quants API統合
- リアルタイムデータ対応
- ウェブインターフェース
- 自動実行機能

## 7. リスク管理

### 7.1 開発リスク
- **データ品質**: yfinanceデータの信頼性検証
- **計算精度**: 金額計算の丸め誤差対策
- **パフォーマンス**: 大量データ処理の最適化

### 7.2 戦略リスク
- **過学習**: パラメータの過度な最適化を避ける
- **市場環境**: 異なる市場環境での検証
- **取引コスト**: 現実的なコスト設定

## 8. 次のアクション

1. **環境構築**
   ```bash
   # プロジェクトディレクトリ作成
   mkdir -p src/{data,strategy,backtest,utils}
   mkdir -p {config,data/{cache,results},notebooks,tests}
   
   # 仮想環境作成
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   
   # 依存関係インストール
   pip install -r requirements.txt
   ```

2. **初期実装**
   - データ取得モジュールの作成
   - 基本的な戦略ロジックの実装
   - 簡易バックテストの実行

3. **検証**
   - 既知の結果との照合
   - エッジケースのテスト
   - パフォーマンス測定

## 9. 成功指標

### 開発面
- [ ] 全テストがパス
- [ ] コードカバレッジ80%以上
- [ ] ドキュメント完備

### 機能面
- [ ] 10年分のデータで安定動作
- [ ] 500銘柄を1時間以内で処理
- [ ] 再現可能な結果

### ビジネス面
- [ ] 戦略の有効性を定量的に評価
- [ ] リスク特性の明確化
- [ ] 改善ポイントの特定
