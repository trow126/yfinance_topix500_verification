# 配当取り戦略バックテストシステム 詳細仕様書

## 1. システム概要

### 1.1 目的
TOPIX500採用銘柄を対象に、配当取り戦略（権利確定日前の買い→配当受取→配当落ちでの買い増し→窓埋めでの決済）のバックテストを実施し、戦略の有効性を定量的に評価するシステムを構築する。

### 1.2 システム構成
```
├── src/
│   ├── data/
│   │   ├── __init__.py
│   │   ├── jquants_client.py      # J-Quants API クライアント
│   │   ├── yfinance_client.py     # yfinance クライアント（代替データソース）
│   │   └── data_manager.py        # データ管理・キャッシュ
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── dividend_strategy.py   # 配当取り戦略ロジック
│   │   └── position_manager.py    # ポジション管理
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── engine.py             # バックテストエンジン
│   │   ├── portfolio.py          # ポートフォリオ管理
│   │   └── metrics.py            # 評価指標計算
│   └── utils/
│       ├── __init__.py
│       ├── calendar.py           # 営業日計算
│       └── logger.py             # ロギング
├── config/
│   └── config.yaml               # 設定ファイル
├── data/
│   ├── cache/                    # APIデータキャッシュ
│   └── results/                  # バックテスト結果
├── notebooks/
│   └── analysis.ipynb            # 結果分析用ノートブック
├── tests/
│   └── test_*.py                 # 単体テスト
└── main.py                       # メインエントリーポイント
```

## 2. データ仕様

### 2.1 必要なデータ

#### 株価データ
- **形式**: 日足OHLCV（始値、高値、安値、終値、出来高）
- **期間**: 2014-01-01 ～ 2023-12-31（調整可能）
- **調整**: 株式分割・併合調整済み

#### 配当データ
- **権利確定日**: 配当を受け取る権利が確定する日
- **権利落ち日**: 配当権利が落ちる日（権利確定日の2営業日前）
- **配当金額**: 1株あたりの配当金額
- **配当回数**: 年間配当回数

#### 銘柄リスト
- **TOPIX500構成銘柄**: テスト期間中の構成銘柄変更を考慮
- **銘柄コード**: 4桁の証券コード
- **銘柄名**: 日本語名称

### 2.2 データソース

#### 主要データソース（J-Quants API）
```python
class JQuantsDataSource:
    """J-Quants APIからのデータ取得"""
    
    def get_price_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """株価データ取得"""
        pass
    
    def get_dividend_data(self, ticker: str) -> pd.DataFrame:
        """配当データ取得"""
        pass
    
    def get_topix500_constituents(self, date: str) -> List[str]:
        """TOPIX500構成銘柄リスト取得"""
        pass
```

#### 代替データソース（yfinance）
```python
class YFinanceDataSource:
    """yfinanceからのデータ取得（バックアップ用）"""
    
    def get_price_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """株価データ取得"""
        pass
    
    def get_dividend_data(self, ticker: str) -> pd.DataFrame:
        """配当データ取得（権利落ち日から権利確定日を計算）"""
        pass
```

## 3. 戦略仕様

### 3.1 エントリールール

```python
class EntryRule:
    def __init__(self, days_before_record: int = 3, position_size: float = 1_000_000):
        self.days_before_record = days_before_record  # 権利確定日のN営業日前
        self.position_size = position_size            # 1銘柄あたりの投資額
    
    def check_entry_signal(self, current_date: date, record_date: date) -> bool:
        """エントリーシグナルチェック"""
        business_days_diff = calculate_business_days(current_date, record_date)
        return business_days_diff == self.days_before_record
    
    def calculate_shares(self, price: float, unit_shares: int = 100) -> int:
        """購入株数計算（単元株考慮）"""
        max_shares = int(self.position_size / price)
        return (max_shares // unit_shares) * unit_shares
```

### 3.2 買い増しルール

```python
class AddPositionRule:
    def __init__(self, add_ratio: float = 0.5):
        self.add_ratio = add_ratio  # 初期投資額に対する買い増し比率
    
    def check_add_signal(self, ex_date_price: float, pre_ex_close: float) -> bool:
        """買い増しシグナルチェック（配当落ちで下落した場合）"""
        return ex_date_price < pre_ex_close
    
    def calculate_add_shares(self, initial_position: Position) -> int:
        """買い増し株数計算"""
        add_amount = initial_position.initial_value * self.add_ratio
        return calculate_shares(current_price, add_amount)
```

### 3.3 決済ルール

```python
class ExitRule:
    def __init__(self, max_holding_days: int = 20, stop_loss_pct: float = 0.1):
        self.max_holding_days = max_holding_days
        self.stop_loss_pct = stop_loss_pct
    
    def check_exit_signals(self, position: Position, current_price: float) -> ExitSignal:
        """決済シグナルチェック"""
        # 窓埋め達成
        if current_price >= position.pre_ex_dividend_price:
            return ExitSignal.WINDOW_FILLED
        
        # 最大保有期間
        if position.holding_days >= self.max_holding_days:
            return ExitSignal.MAX_HOLDING_PERIOD
        
        # 損切りライン
        if current_price < position.average_price * (1 - self.stop_loss_pct):
            return ExitSignal.STOP_LOSS
        
        return ExitSignal.NONE
```

## 4. バックテストエンジン仕様

### 4.1 メインループ

```python
class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.portfolio = Portfolio(initial_capital=config.initial_capital)
        self.strategy = DividendStrategy(config.strategy_params)
        self.data_manager = DataManager(config.data_source)
    
    def run(self) -> BacktestResult:
        """バックテスト実行"""
        for current_date in self.trading_days:
            # 1. 既存ポジションの決済チェック
            self._check_exits(current_date)
            
            # 2. 新規エントリーチェック
            self._check_entries(current_date)
            
            # 3. 買い増しチェック
            self._check_additions(current_date)
            
            # 4. ポートフォリオ評価
            self.portfolio.mark_to_market(current_date)
            
            # 5. メトリクス記録
            self._record_metrics(current_date)
        
        return self._generate_results()
```

### 4.2 取引実行

```python
class TradeExecutor:
    def __init__(self, slippage: float = 0.001, commission: float = 0.0005):
        self.slippage = slippage      # スリッページ率
        self.commission = commission   # 手数料率
    
    def execute_buy(self, ticker: str, shares: int, price: float) -> Trade:
        """買い注文実行"""
        execution_price = price * (1 + self.slippage)
        commission = execution_price * shares * self.commission
        
        return Trade(
            ticker=ticker,
            direction='BUY',
            shares=shares,
            price=execution_price,
            commission=commission,
            timestamp=datetime.now()
        )
    
    def execute_sell(self, ticker: str, shares: int, price: float) -> Trade:
        """売り注文実行"""
        execution_price = price * (1 - self.slippage)
        commission = execution_price * shares * self.commission
        
        return Trade(
            ticker=ticker,
            direction='SELL',
            shares=shares,
            price=execution_price,
            commission=commission,
            timestamp=datetime.now()
        )
```

## 5. 評価指標仕様

### 5.1 リターン指標

```python
class ReturnMetrics:
    @staticmethod
    def calculate_total_return(portfolio_values: pd.Series) -> float:
        """総リターン計算"""
        return (portfolio_values.iloc[-1] / portfolio_values.iloc[0] - 1) * 100
    
    @staticmethod
    def calculate_annualized_return(total_return: float, years: float) -> float:
        """年率リターン計算"""
        return ((1 + total_return / 100) ** (1 / years) - 1) * 100
    
    @staticmethod
    def calculate_profit_factor(trades: List[Trade]) -> float:
        """プロフィットファクター計算"""
        profits = sum(t.pnl for t in trades if t.pnl > 0)
        losses = abs(sum(t.pnl for t in trades if t.pnl < 0))
        return profits / losses if losses > 0 else float('inf')
```

### 5.2 リスク指標

```python
class RiskMetrics:
    @staticmethod
    def calculate_max_drawdown(portfolio_values: pd.Series) -> float:
        """最大ドローダウン計算"""
        cumulative_returns = (1 + portfolio_values.pct_change()).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        return drawdown.min() * 100
    
    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.01) -> float:
        """シャープレシオ計算"""
        excess_returns = returns - risk_free_rate / 252
        return np.sqrt(252) * excess_returns.mean() / excess_returns.std()
    
    @staticmethod
    def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.01) -> float:
        """ソルティノレシオ計算"""
        excess_returns = returns - risk_free_rate / 252
        downside_returns = excess_returns[excess_returns < 0]
        downside_std = np.sqrt(np.mean(downside_returns ** 2))
        return np.sqrt(252) * excess_returns.mean() / downside_std
```

## 6. 設定ファイル仕様

```yaml
# config/config.yaml
backtest:
  start_date: "2014-01-01"
  end_date: "2023-12-31"
  initial_capital: 10_000_000
  
data_source:
  primary: "jquants"  # or "yfinance"
  api_key: "${JQUANTS_API_KEY}"
  cache_dir: "./data/cache"
  
strategy:
  entry:
    days_before_record: 3
    position_size: 1_000_000
  
  addition:
    enabled: true
    add_ratio: 0.5
  
  exit:
    max_holding_days: 20
    stop_loss_pct: 0.1
  
execution:
  slippage: 0.001
  commission: 0.0005
  
universe:
  index: "TOPIX500"
  rebalance_frequency: "quarterly"
```

## 7. 実装上の注意事項

### 7.1 データ品質
- 欠損値処理：前営業日の終値で補完
- 異常値検出：前日比±50%以上の変動は要確認
- タイムゾーン：全て日本時間（JST）で統一

### 7.2 計算精度
- 金額計算：decimal.Decimalを使用
- 株数計算：単元株数を考慮（端数切り捨て）
- 手数料計算：最低手数料を考慮

### 7.3 エラーハンドリング
- API接続エラー：リトライ機能実装（最大3回）
- データ不整合：ログ記録して処理継続
- 計算エラー：該当取引をスキップして警告

### 7.4 パフォーマンス最適化
- データキャッシュ：SQLiteでローカル保存
- 並列処理：銘柄ごとの処理を並列化
- メモリ管理：大量データの分割処理

## 8. テスト仕様

### 8.1 単体テスト
- 戦略ロジックの正確性
- 評価指標計算の検証
- エッジケースの処理

### 8.2 統合テスト
- エンドツーエンドのバックテスト実行
- 既知の結果との照合
- パフォーマンステスト

## 9. 出力仕様

### 9.1 取引ログ
```json
{
  "trade_id": "20230401_7203_001",
  "ticker": "7203",
  "action": "BUY",
  "shares": 1000,
  "price": 2000.0,
  "commission": 1000.0,
  "timestamp": "2023-04-01 09:00:00"
}
```

### 9.2 パフォーマンスレポート
- 総合サマリー（JSON/CSV形式）
- 取引明細（CSV形式）
- パフォーマンスグラフ（PNG/HTML形式）
- 統計分析レポート（HTML形式）

## 10. 拡張性

### 10.1 戦略の拡張
- 複数戦略の同時実行
- パラメータの動的最適化
- 機械学習モデルの組み込み

### 10.2 データソースの拡張
- 複数APIの統合
- リアルタイムデータ対応
- 代替データの活用
