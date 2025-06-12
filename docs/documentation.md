# 配当取り戦略バックテストシステム ドキュメント

## システム概要

本システムは、日本株式市場における配当取り戦略のバックテストを行うためのPythonベースのシステムです。

## 主な改善点（2024年版）

### 1. 配当調整問題の修正

最も重要な改善点は、yfinanceから取得する株価データに関する問題の修正です：

- **問題**: yfinanceのデフォルト設定では配当調整済み価格が返される
- **影響**: 配当落ちの株価下落が見えなくなり、非現実的に良い結果となる
- **解決**: `auto_adjust=False`を使用して未調整価格を取得

```python
# 修正前（問題あり）
hist = stock.history(start=start_date, end=end_date)

# 修正後（正しい）
hist = stock.history(start=start_date, end=end_date, auto_adjust=False)
```

### 2. 現実的な取引コスト

実際の証券会社の手数料体系を反映：

- スリッページ: 0.2%（通常）、0.5%（権利落ち日前後）
- 手数料: 0.055%（税込）
- 最低手数料: 550円
- 上限手数料: 1,100円

### 3. 配当支払いタイミング

日本企業の実際の配当支払いサイクルを反映：

- 3月決算: 6月下旬支払い
- 9月中間配当: 12月上旬支払い
- その他: 権利確定日から約2.5ヶ月後

### 4. 配当課税

源泉徴収税率20.315%を適用し、税引後配当金のみをポートフォリオに追加。

## アーキテクチャ

### ディレクトリ構造

```
yfinance_topix500_verification/
├── src/
│   ├── data/          # データ取得・管理
│   ├── strategy/      # 戦略実装
│   ├── backtest/      # バックテストエンジン
│   └── utils/         # ユーティリティ
├── config/            # 設定ファイル
├── data/              # データ保存
├── scripts/           # 実行スクリプト
└── tests/             # テストコード
```

### 主要コンポーネント

1. **DataManager** (`src/data/data_manager.py`)
   - yfinanceからのデータ取得
   - キャッシュ管理
   - データ検証

2. **DividendStrategy** (`src/strategy/dividend_strategy.py`)
   - エントリー/エグジット判定
   - ポジション管理
   - シグナル生成

3. **BacktestEngine** (`src/backtest/engine.py`)
   - 日次シミュレーション
   - 取引執行
   - パフォーマンス計算

4. **Portfolio** (`src/backtest/portfolio.py`)
   - 資金管理
   - ポジション追跡
   - 損益計算

## 使用方法

### 1. 環境セットアップ

```bash
# 仮想環境の作成
python -m venv venv

# アクティベート
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# 依存関係のインストール
pip install -r requirements.txt
```

### 2. クイックテスト

```bash
# キャッシュのクリア（重要）
del /s /q data\cache\*

# 3銘柄・1年間のテスト
python scripts/run_quick_test.py
```

### 3. 本格的なバックテスト

```bash
# 10銘柄・5年間
python main.py

# TOPIX500・14年間
python run_topix500_backtest.py
```

## 設定ファイルの詳細

`config/config.yaml`の主要設定：

```yaml
backtest:
  start_date: "2019-01-01"
  end_date: "2023-12-31"
  initial_capital: 10_000_000

strategy:
  entry:
    days_before_record: 3      # 権利確定日の3営業日前にエントリー
    position_size: 1_000_000   # 1銘柄あたり100万円
    max_positions: 10          # 最大10銘柄保有

execution:
  slippage: 0.002             # 通常時0.2%
  slippage_ex_date: 0.005     # 権利落ち日前後0.5%
  commission: 0.00055         # 手数料0.055%
  min_commission: 550         # 最低550円
  max_commission: 1100        # 上限1,100円
  tax_rate: 0.20315          # 配当税20.315%
```

## 期待される結果

修正後の現実的なバックテスト結果：

- **年率リターン**: -5% ～ +5%
- **勝率**: 40% ～ 55%
- **最大ドローダウン**: -10% ～ -20%
- **シャープレシオ**: 0 ～ 0.8

もし年率リターンが15%を超えるような結果が出た場合は、設定やデータに問題がある可能性があります。

## トラブルシューティング

### 結果が良すぎる場合

1. キャッシュを完全にクリア
2. `scripts/verify_adjustments.py`を実行して未調整価格を確認
3. 取引コストの設定を確認

### メモリ不足

1. 銘柄数を減らす
2. バックテスト期間を短縮
3. より多くのメモリを搭載したマシンを使用

### データ取得エラー

1. インターネット接続を確認
2. yfinanceを最新版に更新
3. API制限に達していないか確認（時間を置いて再実行）

## 今後の改善案

1. **流動性制約**
   - 出来高に基づくポジションサイズ制限
   - マーケットインパクトモデル

2. **より詳細な税制**
   - NISA口座の考慮
   - 損益通算

3. **リスク管理**
   - ポートフォリオ最適化
   - セクター分散

4. **機械学習**
   - 最適なエントリータイミングの学習
   - 銘柄選択の改善
