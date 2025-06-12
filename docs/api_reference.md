# APIリファレンス

## データ管理 (src.data)

### YFinanceClient

```python
class YFinanceClient(cache_dir: str = "./data/cache", cache_expire_hours: int = 24)
```

yfinanceからのデータ取得とキャッシュ管理を行うクライアント。

#### メソッド

- `get_price_data(ticker: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame`
  - 株価データ（OHLCV）を取得
  - **重要**: `auto_adjust=False`で未調整価格を取得

- `get_dividend_data(ticker: str, use_cache: bool = True) -> pd.DataFrame`
  - 配当データを取得し、権利確定日を計算

- `clear_cache() -> None`
  - キャッシュをクリア

### DataManager

```python
class DataManager(config: DataSourceConfig)
```

複数銘柄のデータを管理し、バックテストエンジンに提供。

#### メソッド

- `load_data(tickers: List[str], start_date: str, end_date: str) -> None`
  - 指定銘柄のデータを一括ロード

- `get_price_on_date(ticker: str, date: datetime) -> Optional[float]`
  - 特定日の終値を取得

- `get_next_dividend(ticker: str, current_date: datetime) -> Optional[Dict]`
  - 次の配当情報を取得

## 戦略 (src.strategy)

### DividendStrategy

```python
class DividendStrategy(config: StrategyConfig)
```

配当取り戦略のロジックを実装。

#### メソッド

- `check_entry_signal(ticker: str, current_date: datetime, dividend_info: Dict, current_price: float) -> Optional[Signal]`
  - エントリーシグナルの判定

- `check_exit_signal(ticker: str, current_date: datetime, position_info: Dict, current_price: float) -> Optional[Signal]`
  - 決済シグナルの判定

- `check_addition_signal(ticker: str, current_date: datetime, position_info: Dict, current_price: float, pre_ex_price: float) -> Optional[Signal]`
  - 買い増しシグナルの判定

### PositionManager

```python
class PositionManager()
```

ポジション情報の管理。

#### メソッド

- `open_position(ticker: str, date: datetime, price: float, shares: int, **kwargs) -> Position`
  - 新規ポジションを開く

- `close_position(ticker: str, date: datetime, price: float) -> Optional[Trade]`
  - ポジションをクローズ

- `get_open_positions() -> List[Position]`
  - オープンポジションのリストを取得

## バックテスト (src.backtest)

### BacktestEngine

```python
class BacktestEngine(config: Config)
```

バックテストの実行エンジン。

#### メソッド

- `run() -> Dict`
  - バックテストを実行し、結果を返す

- `_process_day(current_date: datetime) -> None`
  - 1日の処理（内部メソッド）

- `_execute_entry(signal: Signal, execution_price: float, dividend_info: Optional[Dict] = None) -> None`
  - エントリー注文の執行

- `_execute_exit(signal: Signal, execution_price: float) -> None`
  - 決済注文の執行

### Portfolio

```python
class Portfolio(initial_capital: float)
```

ポートフォリオの管理。

#### プロパティ

- `cash: float` - 現金残高
- `total_value: float` - 総資産価値
- `positions: Dict[str, Position]` - 現在のポジション

#### メソッド

- `execute_buy(ticker: str, date: datetime, price: float, shares: int, commission: float, **kwargs) -> bool`
  - 買い注文を執行

- `execute_sell(ticker: str, date: datetime, price: float, commission: float, **kwargs) -> bool`
  - 売り注文を執行

- `update_dividend(ticker: str, dividend_per_share: float, date: datetime) -> None`
  - 配当金を受け取る（税引後）

- `mark_to_market(date: datetime, prices: Dict[str, float]) -> Dict`
  - 時価評価を実行

- `get_performance_metrics() -> Dict`
  - パフォーマンス指標を計算

## ユーティリティ (src.utils)

### DividendDateCalculator

```python
class DividendDateCalculator
```

配当関連の日付計算。

#### 静的メソッド

- `calculate_record_date(ex_dividend_date: datetime) -> datetime`
  - 権利落ち日から権利確定日を計算（T+2）

- `calculate_entry_date(record_date: datetime, days_before: int) -> datetime`
  - エントリー日を計算

### BusinessDayCalculator

```python
class BusinessDayCalculator
```

営業日計算（日本の祝日を考慮）。

#### 静的メソッド

- `add_business_days(date: datetime, days: int) -> datetime`
  - 営業日を加算/減算

- `calculate_business_days(start_date: datetime, end_date: datetime) -> int`
  - 営業日数を計算

### Config関連クラス

設定管理用のデータクラス群：

- `BacktestConfig` - バックテスト設定
- `StrategyConfig` - 戦略設定
- `ExecutionConfig` - 執行設定
- `UniverseConfig` - 銘柄ユニバース設定

## 使用例

```python
from src.utils.config import load_config
from src.backtest.engine import BacktestEngine

# 設定読み込み
config = load_config("config/config.yaml")

# バックテスト実行
engine = BacktestEngine(config)
results = engine.run()

# 結果の確認
print(f"総リターン: {results['metrics']['total_return']:.2%}")
print(f"シャープレシオ: {results['metrics']['sharpe_ratio']:.2f}")
```
