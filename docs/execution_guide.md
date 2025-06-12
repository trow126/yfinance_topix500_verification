# 配当取り戦略バックテスト実行ガイド

## 目次
1. [初回セットアップ](#初回セットアップ)
2. [実行前の重要な確認事項](#実行前の重要な確認事項)
3. [段階的な実行手順](#段階的な実行手順)
4. [実行コマンド一覧](#実行コマンド一覧)
5. [結果の確認方法](#結果の確認方法)
6. [トラブルシューティング](#トラブルシューティング)

## 初回セットアップ

### 1. リポジトリのクローン
```bash
git clone https://github.com/yourusername/yfinance_topix500_verification.git
cd yfinance_topix500_verification
```

### 2. Python仮想環境の作成と有効化

**Windows (PowerShell)**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (コマンドプロンプト)**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**Mac/Linux**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. 依存パッケージのインストール
```bash
pip install -r requirements.txt
```

## 実行前の重要な確認事項

### ⚠️ キャッシュのクリア（必須）

以前の調整済み価格データが残っていると、正しい結果が得られません：

**Windows**
```cmd
del /s /q data\cache\*
```

**Mac/Linux**
```bash
rm -rf data/cache/*
```

### 環境確認
```bash
python scripts/check_project.py
```

## 段階的な実行手順

### Step 1: 検証スクリプトの実行（推奨）

修正内容が正しく適用されているか確認：

```bash
python scripts/verify_adjustments.py
```

期待される出力：
- 調整済み価格と未調整価格の差が表示される
- 取引コストの比較が表示される
- 配当支払いタイミングの確認

### Step 2: クイックテスト（3銘柄・1年間）

```bash
python scripts/run_quick_test.py
```

このスクリプトは以下を実行：
- 環境チェック
- 3銘柄（トヨタ、ソニー、NTT）での1年間バックテスト
- 結果の妥当性チェック

**期待される結果**
```
【リターン指標】
  総リターン: -2% ～ +3%
  年率リターン: -2% ～ +3%

【リスク指標】
  最大ドローダウン: -5% ～ -15%
  シャープレシオ: -0.5 ～ 0.5
```

### Step 3: 通常のバックテスト（10銘柄・5年間）

```bash
python main.py
```

デフォルト設定：
- 銘柄数: 10（主要銘柄）
- 期間: 2019-01-01 ～ 2023-12-31
- 初期資本: 1,000万円

**実行時間**: 約5-10分

### Step 4: TOPIX500バックテスト（大規模）

```bash
# 事前にメモリを確認
python -c "import psutil; print(f'利用可能メモリ: {psutil.virtual_memory().available / (1024**3):.1f} GB')"

# 実行（1-2時間かかります）
python run_topix500_backtest.py
```

**注意事項**:
- メモリ8GB以上推奨
- 約450銘柄、14年間のデータ
- 初期資本: 1億円

## 実行コマンド一覧

### 基本コマンド

| コマンド | 説明 | 実行時間 |
|---------|------|----------|
| `python scripts/verify_adjustments.py` | 修正内容の検証 | 1分未満 |
| `python scripts/run_quick_test.py` | クイックテスト（3銘柄） | 2-3分 |
| `python main.py` | 通常バックテスト（10銘柄） | 5-10分 |
| `python run_topix500_backtest.py` | 大規模バックテスト | 1-2時間 |

### オプション付き実行

```bash
# カスタム設定ファイルを指定
python main.py --config config/my_config.yaml

# 結果出力先を指定
python main.py --output results/test_20240101

# グラフ表示を無効化
python main.py --no-viz

# ログレベルを変更
python main.py --log-level DEBUG
```

### Windows用バッチファイル

```cmd
# 通常のバックテスト
run_backtest.bat

# TOPIX500バックテスト
run_topix500_backtest.bat
```

## 結果の確認方法

### 1. コンソール出力

実行中に以下の情報が表示されます：
```
Progress: 20.0% (2020-03-15)
Progress: 40.0% (2021-01-10)
...
Backtest completed

=== Backtest Results ===
total_return: -2.35%
annualized_return: -0.47%
sharpe_ratio: -0.15
max_drawdown: -12.34%
```

### 2. 保存されるファイル

結果は`data/results/`ディレクトリに保存されます：

- **metrics_YYYYMMDD_HHMMSS.json** - パフォーマンス指標
- **trades_YYYYMMDD_HHMMSS.csv** - 全取引履歴
- **portfolio_YYYYMMDD_HHMMSS.csv** - ポートフォリオ推移
- **backtest_report_YYYYMMDD_HHMMSS.html** - HTMLレポート
- **performance_chart_YYYYMMDD_HHMMSS.png** - パフォーマンスチャート

### 3. HTMLレポートの確認

```bash
# Windowsの場合
start data\results\backtest_report_*.html

# Mac/Linuxの場合
open data/results/backtest_report_*.html
```

### 4. 結果の分析

```bash
python scripts/analyze_results.py
```

## トラブルシューティング

### 問題: 結果が良すぎる（年率リターン > 15%）

**原因**: キャッシュに古い調整済み価格データが残っている

**解決方法**:
```bash
# 1. キャッシュを完全にクリア
del /s /q data\cache\*

# 2. 検証スクリプトを実行
python scripts/verify_adjustments.py

# 3. 再度バックテストを実行
python main.py
```

### 問題: yfinanceデータ取得エラー

**原因**: ネットワーク接続またはAPI制限

**解決方法**:
```bash
# 1. yfinanceを更新
pip install --upgrade yfinance

# 2. プロキシ設定（必要な場合）
set HTTP_PROXY=http://proxy.example.com:8080
set HTTPS_PROXY=http://proxy.example.com:8080

# 3. 時間を置いて再実行
```

### 問題: メモリ不足エラー

**原因**: TOPIX500の大規模データ処理

**解決方法**:
1. 銘柄数を減らす（config.yamlを編集）
2. 期間を短縮する
3. 他のアプリケーションを終了する

### 問題: ModuleNotFoundError

**原因**: パッケージが正しくインストールされていない

**解決方法**:
```bash
# 仮想環境が有効化されているか確認
which python  # Mac/Linux
where python  # Windows

# パッケージを再インストール
pip install --upgrade -r requirements.txt
```

## 推奨実行フロー

1. **初回実行時**
   ```bash
   # 1. 環境確認
   python scripts/check_project.py
   
   # 2. キャッシュクリア
   del /s /q data\cache\*
   
   # 3. 検証
   python scripts/verify_adjustments.py
   
   # 4. クイックテスト
   python scripts/run_quick_test.py
   ```

2. **通常の実行時**
   ```bash
   # 1. キャッシュクリア（任意）
   del /s /q data\cache\*
   
   # 2. バックテスト実行
   python main.py
   ```

3. **詳細な分析時**
   ```bash
   # 1. 大規模バックテスト
   python run_topix500_backtest.py
   
   # 2. 結果分析
   python scripts/analyze_results.py
   ```

## 次のステップ

バックテストが正常に実行できたら：

1. **設定の調整** - `config/config.yaml`を編集
2. **銘柄の追加** - より多くの銘柄でテスト
3. **期間の延長** - より長期間でのバックテスト
4. **戦略の改良** - パラメータの最適化

詳細は[ドキュメント](docs/documentation.md)を参照してください。
