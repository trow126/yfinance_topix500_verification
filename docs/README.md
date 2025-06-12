# ドキュメント一覧

このディレクトリには、配当取り戦略バックテストシステムに関する各種ドキュメントが整理されています。

## ディレクトリ構成

```
docs/
├── guides/         # 各種ガイド
├── specifications/ # 仕様書・計画書
├── issues/         # 問題と解決策
└── README.md       # このファイル
```

## 各カテゴリの説明

### guides/ - ガイドドキュメント

システムの使い方やセットアップ方法を説明するガイド：

- **[setup_guide.md](guides/setup_guide.md)** - セットアップガイド
  - Python環境の準備
  - 依存パッケージのインストール
  - 初期設定

- **[execution_guide.md](guides/execution_guide.md)** - 実行ガイド
  - バックテストの実行方法
  - パラメータの調整
  - 結果の確認方法

### specifications/ - 仕様書・計画書

システムの詳細な仕様や実装計画：

- **[detailed_specification.md](specifications/detailed_specification.md)** - 詳細仕様書
  - システムアーキテクチャ
  - コンポーネントの詳細
  - データフロー

- **[topix500_backtest_specification.md](specifications/topix500_backtest_specification.md)** - TOPIX500バックテスト仕様
  - 大規模バックテストの要件
  - パフォーマンス考慮事項
  - 実行手順

- **[implementation_plan.md](specifications/implementation_plan.md)** - 実装計画
  - 開発フェーズ
  - マイルストーン
  - 今後の拡張計画

### issues/ - 問題と解決策

開発中に発生した問題とその解決策：

- **[hidden_addition_issue.md](issues/hidden_addition_issue.md)** - 隠れた買い増し問題
  - 設定を無視して買い増しが実行される問題
  - 原因と修正方法

- **[dividend_payment_issue.md](issues/dividend_payment_issue.md)** - 配当支払い問題
  - 配当収入が0円になる問題
  - 原因と解決策

- **[window_fill_issue.md](issues/window_fill_issue.md)** - 窓埋め判定問題
  - 権利落ち日にすぐ窓埋めと判定される問題
  - 原因と部分的な解決策

## その他の重要ドキュメント

- **[documentation.md](documentation.md)** - システム全体のドキュメント
- **[project_summary.md](project_summary.md)** - プロジェクトサマリー
- **[api_reference.md](api_reference.md)** - APIリファレンス

## クイックリンク

### 初めての方へ
1. [セットアップガイド](guides/setup_guide.md)
2. [実行ガイド](guides/execution_guide.md)
3. [プロジェクトサマリー](project_summary.md)

### 開発者向け
1. [詳細仕様書](specifications/detailed_specification.md)
2. [APIリファレンス](api_reference.md)
3. [問題と解決策](issues/)

### トラブルシューティング
1. [配当支払い問題](issues/dividend_payment_issue.md)
2. [隠れた買い増し問題](issues/hidden_addition_issue.md)
3. [窓埋め判定問題](issues/window_fill_issue.md)
