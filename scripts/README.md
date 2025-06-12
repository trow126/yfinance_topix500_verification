# スクリプトディレクトリ構成

このディレクトリには、配当取り戦略バックテストシステムで使用する各種スクリプトが整理されています。

## ディレクトリ構成

```
scripts/
├── debug/         # デバッグ・分析用スクリプト
├── fix/           # バグ修正・パッチ適用スクリプト
├── run/           # バックテスト実行スクリプト
├── test/          # テスト・検証スクリプト
├── utils/         # ユーティリティスクリプト
└── README.md      # このファイル
```

## 各ディレクトリの説明

### debug/ - デバッグ・分析スクリプト

問題の調査や分析に使用するスクリプト群：

- `analyze_problems.py` - 問題の総合分析
- `analyze_share_issue.py` - 株数計算の問題を分析
- `analyze_trading_pairs.py` - 取引ペアの分析
- `check_csv_structure.py` - CSVファイル構造の確認
- `check_dividend_setup.py` - 配当情報の設定状況確認
- `check_outputs.py` - 出力結果の確認
- `check_project.py` - プロジェクト全体の確認
- `debug_code_state.py` - コードの状態をデバッグ
- `debug_dividend_issue.py` - 配当関連の問題をデバッグ
- `debug_dividend_payment.py` - 配当支払い処理のデバッグ
- `debug_double_shares.py` - 売却株数2倍問題の調査
- `debug_hidden_addition.py` - 隠れた買い増し問題の調査
- `debug_patch.py` - パッチ適用のデバッグ
- `debug_trading_flow.py` - 取引フローの追跡
- `debug_window_fill.py` - 窓埋め判定ロジックのデバッグ
- `detect_hidden_addition.py` - 隠れた買い増しの検出
- `diagnose_issues.py` - 問題の診断
- `find_real_results.py` - 実際の結果ファイルの検索
- `identify_double_buy_issue.py` - 二重買い問題の特定
- `trace_dividend_payment.py` - 配当支払い処理の追跡
- `trace_share_changes.py` - 株数変更の追跡

### fix/ - 修正・パッチスクリプト

バグ修正やコードの自動修正を行うスクリプト群：

- `fix_dividend_immediate.py` - 配当を権利落ち日に即座に計上する修正
- `fix_dividend_strategy.py` - 配当取り戦略の主要な問題を修正
- `fix_hidden_addition.py` - 隠れた買い増し問題の修正
- `fix_issues_now.py` - 緊急修正の適用
- `fix_portfolio_duplicate_buy.py` - ポートフォリオの重複購入修正
- `fix_position_duplicate_shares.py` - ポジションの重複株数修正

### run/ - 実行スクリプト

バックテストを実行するためのスクリプト群：

- `run_backtest.py` - 標準的なバックテスト実行
- `run_fixed_backtest.py` - 修正版バックテスト実行
- `run_simple_fix.py` - シンプルな修正版実行
- `run_topix500_backtest.py` - TOPIX500全銘柄バックテスト

### test/ - テスト・検証スクリプト

機能のテストや動作検証を行うスクリプト群：

- `minimal_debug_test.py` - 最小限のデバッグテスト
- `run_quick_test.py` - クイックテストの実行
- `test_addition_behavior.py` - 買い増し機能の動作テスト
- `verify_adjustments.py` - 調整値の検証
- `yfinance_verification.py` - yfinanceデータの検証

### utils/ - ユーティリティスクリプト

汎用的なユーティリティスクリプト：

- `fix_script_paths.py` - スクリプトのインポートパスを修正

## 使用方法

### デバッグスクリプトの実行例

```bash
# 隠れた買い増し問題を検出
python scripts/debug/detect_hidden_addition.py

# 売却株数2倍問題を調査
python scripts/debug/debug_double_shares.py
```

### 修正スクリプトの実行例

```bash
# 隠れた買い増し問題を修正
python scripts/fix/fix_hidden_addition.py
```

### バックテストの実行例

```bash
# 標準的なバックテスト
python scripts/run/run_backtest.py

# TOPIX500全銘柄バックテスト
python scripts/run/run_topix500_backtest.py
```

### テストの実行例

```bash
# 最小限のデバッグテスト
python scripts/test/minimal_debug_test.py
```

## 注意事項

1. **実行前の確認**
   - 修正スクリプトは自動的にコードを変更するため、実行前にバックアップを取ることを推奨
   - 大規模バックテストは実行に時間がかかるため、十分な時間を確保してから実行

2. **パスの修正**
   - ルートディレクトリから移動したスクリプトは、相対パスの調整が必要な場合があります
   - 問題が発生した場合は、`sys.path`の設定を確認してください

3. **依存関係**
   - すべてのスクリプトは、プロジェクトルートの`requirements.txt`に記載された依存関係が必要です
   - 仮想環境の使用を推奨します
