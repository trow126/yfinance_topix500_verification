# スクリプトディレクトリ構成

このディレクトリには、配当取り戦略バックテストシステムで使用する各種スクリプトが整理されています。

## ディレクトリ構成

```
scripts/
├── run/           # バックテスト実行スクリプト
├── test/          # テスト・検証スクリプト
├── utils/         # ユーティリティスクリプト
└── README.md      # このファイル
```

## 各ディレクトリの説明

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
   - 過去の一時的な修正・デバッグスクリプト（fix/, debug/）は修正がsrcに反映済みのため削除しました（git履歴から参照可能）
   - 大規模バックテストは実行に時間がかかるため、十分な時間を確保してから実行

2. **パスの修正**
   - ルートディレクトリから移動したスクリプトは、相対パスの調整が必要な場合があります
   - 問題が発生した場合は、`sys.path`の設定を確認してください

3. **依存関係**
   - すべてのスクリプトは、プロジェクトルートの`requirements.txt`に記載された依存関係が必要です
   - 仮想環境の使用を推奨します
