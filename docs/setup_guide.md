# セットアップガイド

## 前提条件

- Python 3.8以上
- Windows/Mac/Linux対応
- インターネット接続（データ取得のため）

## インストール手順

### 1. リポジトリのクローン

```bash
git clone https://github.com/yourusername/yfinance_topix500_verification.git
cd yfinance_topix500_verification
```

### 2. Python仮想環境の作成

#### Windows (PowerShell)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### Windows (コマンドプロンプト)
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

#### Mac/Linux
```bash
python -m venv venv
source venv/bin/activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

必要なパッケージ：
- yfinance: 株価・配当データの取得
- pandas: データ処理
- numpy: 数値計算
- matplotlib: グラフ作成
- jpholiday: 日本の祝日判定
- pyyaml: 設定ファイル読み込み
- loguru: ロギング

### 4. ディレクトリ構造の確認

以下のディレクトリが自動作成されます：
```
data/
├── cache/      # データキャッシュ
└── results/    # バックテスト結果
logs/           # ログファイル
```

## 初回実行

### 1. 設定ファイルの確認

`config/config.yaml`を開いて設定を確認：

```yaml
# 対象銘柄（初期設定は10銘柄）
universe:
  tickers:
    - "7203"  # トヨタ自動車
    - "6758"  # ソニーグループ
    # ...

# バックテスト期間
backtest:
  start_date: "2019-01-01"
  end_date: "2023-12-31"
```

### 2. クイックテストの実行

```bash
python scripts/run_quick_test.py
```

このスクリプトは：
- 環境チェック
- 3銘柄・1年間のミニバックテスト
- 結果の妥当性確認

### 3. 結果の確認

```
バックテスト結果
==============
【リターン指標】
  総リターン: -2.35%
  年率リターン: -2.35%

【リスク指標】
  最大ドローダウン: -8.72%
  シャープレシオ: -0.31
```

このような現実的な（やや悪い）結果が出れば正常です。

## トラブルシューティング

### エラー: ModuleNotFoundError

```bash
# パッケージの再インストール
pip install --upgrade -r requirements.txt
```

### エラー: yfinanceデータ取得エラー

```bash
# プロキシ設定が必要な場合
set HTTP_PROXY=http://proxy.example.com:8080
set HTTPS_PROXY=http://proxy.example.com:8080
```

### 警告: 結果が良すぎる

```bash
# キャッシュをクリアして再実行
del /s /q data\cache\*  # Windows
rm -rf data/cache/*     # Mac/Linux
```

## 推奨される開発環境

### VSCode設定

`.vscode/settings.json`:
```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ]
}
```

### PyCharm設定

1. Project Interpreter: 作成したvenv環境を選択
2. Project Structure: srcディレクトリをSourcesに設定
3. Run Configuration: main.pyを設定

## テスト実行

```bash
# 全テストを実行
pytest

# カバレッジ付き
pytest --cov=src --cov-report=html

# 特定のテストのみ
pytest tests/test_strategy.py -v
```

## デバッグ方法

### ログレベルの変更

`config/config.yaml`:
```yaml
logging:
  level: "DEBUG"  # INFO → DEBUG に変更
```

### 個別コンポーネントのテスト

```python
# Pythonインタープリタで
from src.data.yfinance_client import YFinanceClient

client = YFinanceClient()
data = client.get_price_data("7203", "2023-01-01", "2023-12-31")
print(data.head())
```

## パフォーマンス最適化

### 大規模バックテスト時の推奨事項

1. **メモリ管理**
   ```python
   # バッチ処理を有効化（開発中）
   config.backtest.batch_size = 100
   ```

2. **並列処理**
   ```python
   # マルチプロセッシング（開発中）
   config.backtest.n_jobs = 4
   ```

3. **キャッシュの活用**
   ```yaml
   data_source:
     cache_expire_hours: 168  # 1週間
   ```

## 次のステップ

1. **銘柄の追加**
   - `config/config.yaml`のtickersリストに追加

2. **戦略パラメータの調整**
   - エントリータイミング
   - ポジションサイズ
   - 損切りライン

3. **期間の延長**
   - より長期間でのバックテスト

4. **カスタム戦略の実装**
   - `src/strategy/`に新しい戦略クラスを作成
