# 実行手順の記載場所一覧

## 📍 実行手順が記載されているドキュメント

### 1. **[実行ガイド](execution_guide.md)** 【最も詳細】
- **場所**: `docs/execution_guide.md`
- **内容**: 
  - 初回セットアップから実行まで完全ガイド
  - 段階的な実行手順（Step 1～4）
  - 実行コマンド一覧表
  - トラブルシューティング
  - 推奨実行フロー

### 2. **[README.md](../README.md)** 【基本的な使い方】
- **場所**: プロジェクトルート
- **内容**:
  - クイックスタート（3銘柄テスト）
  - 基本的な実行方法
  - TOPIX500バックテスト
  - Windows用バッチファイル

### 3. **[セットアップガイド](setup_guide.md)** 【環境構築中心】
- **場所**: `docs/setup_guide.md`
- **内容**:
  - Python環境のセットアップ
  - 依存パッケージのインストール
  - 初回実行の手順

### 4. **[バックテスト検証ガイド](documentation.md)** 【概要】
- **場所**: `docs/documentation.md`
- **内容**:
  - システムの使用方法概要
  - アーキテクチャ説明

## 🚀 クイック実行コマンド

### 最速で試したい場合
```bash
# 1. キャッシュクリア（必須）
del /s /q data\cache\*

# 2. クイックテスト実行
python scripts/run_quick_test.py
```

### 通常の実行
```bash
python main.py
```

### 大規模バックテスト
```bash
python run_topix500_backtest.py
```

## 📋 推奨される参照順序

1. **初めての方**
   - [セットアップガイド](setup_guide.md) → 環境構築
   - [実行ガイド](execution_guide.md) → 実行方法

2. **環境構築済みの方**
   - [実行ガイド](execution_guide.md) → 直接参照

3. **トラブルシューティング**
   - [実行ガイド](execution_guide.md#トラブルシューティング)
   - [README.md](../README.md#トラブルシューティング)

## 📌 重要な注意事項

**キャッシュのクリアを忘れずに！**

修正前の調整済み価格データが残っていると、非現実的に良い結果が出ます：

```bash
# Windows
del /s /q data\cache\*

# Mac/Linux
rm -rf data/cache/*
```
