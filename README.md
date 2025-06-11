# 配当取り戦略バックテストシステム

TOPIX500採用銘柄を対象とした配当取り戦略のバックテストシステムです。

## 概要

本システムは、配当権利確定日前後の価格変動を利用した投資戦略（配当取り戦略）の有効性を検証するためのバックテストシステムです。

### 戦略の概要

1. **エントリー**: 権利確定日の3営業日前に買い
2. **配当取得**: 権利確定日を跨いで配当権利を取得
3. **買い増し**: 権利落ち日の価格下落時に追加投資（オプション）
4. **決済**: 以下のいずれかの条件で決済
   - 窓埋め達成（権利落ち前の価格まで回復）
   - 最大保有期間（20営業日）経過
   - 損切りライン（-10%）到達

## 特徴

- ✅ yfinanceを使用した信頼性の高いデータ取得
- ✅ 日本の営業日・祝日を考慮した正確な日付計算
- ✅ 詳細なパフォーマンス分析とレポート生成
- ✅ HTMLレポートによる視覚的な結果表示
- ✅ 段階的な実装による拡張性

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/yourusername/yfinance_topix500_verification.git
cd yfinance_topix500_verification
```

### 2. Python環境の準備

Python 3.8以上が必要です。

```bash
# 仮想環境の作成（推奨）
python -m venv venv

# 仮想環境のアクティベート
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

## 使い方

### クイックスタート（推奨）

初めての方は、少数銘柄・短期間でのテストから始めることをお勧めします：

```bash
# 3銘柄、6ヶ月間のクイックテスト
python quickstart.py
```

### 基本的な実行

```bash
# デフォルト設定で実行
python main.py

# カスタム設定ファイルを指定
python main.py --config config/my_config.yaml

# 結果出力先を指定
python main.py --output results/my_test

# グラフ表示を無効化
python main.py --no-viz
```

### TOPIX500全銘柄バックテスト（大規模）

TOPIX500の主要構成銘柄（約450銘柄）を対象とした本格的なバックテスト：

```bash
# Python実行
python run_topix500_backtest.py

# Windows バッチファイル
run_topix500_backtest.bat
```

**大規模バックテストの仕様:**
- 対象銘柄: TOPIX500主要構成銘柄（約450銘柄）
- 期間: 2010年1月～2023年12月（14年間）
- 初期資本: 1億円
- 推定実行時間: 1-2時間
- 必要メモリ: 8GB以上推奨

### Windowsでの簡単実行

```bash
# 通常のバックテスト
run_backtest.bat

# TOPIX500全銘柄バックテスト
run_topix500_backtest.bat
```

## 設定

`config/config.yaml`ファイルで戦略パラメータを調整できます：

```yaml
backtest:
  start_date: "2019-01-01"  # バックテスト開始日
  end_date: "2023-12-31"    # バックテスト終了日
  initial_capital: 10_000_000  # 初期資本（円）

strategy:
  entry:
    days_before_record: 3      # 権利確定日の何営業日前にエントリー
    position_size: 1_000_000   # 1銘柄あたりの投資額
    max_positions: 10          # 最大同時保有銘柄数
  
  exit:
    max_holding_days: 20       # 最大保有期間（営業日）
    stop_loss_pct: 0.1         # 損切りライン（10%）
```

## 出力結果

バックテスト実行後、以下の結果が`data/results`フォルダに保存されます：

- **metrics_YYYYMMDD_HHMMSS.json**: パフォーマンス指標
- **trades_YYYYMMDD_HHMMSS.csv**: 取引履歴
- **portfolio_YYYYMMDD_HHMMSS.csv**: ポートフォリオ推移
- **backtest_report_YYYYMMDD_HHMMSS.html**: HTMLレポート
- **performance_chart_YYYYMMDD_HHMMSS.png**: パフォーマンスチャート

## プロジェクト構造

```
yfinance_topix500_verification/
├── src/
│   ├── data/               # データ取得・管理
│   ├── strategy/           # 戦略実装
│   ├── backtest/           # バックテストエンジン
│   └── utils/              # ユーティリティ
├── config/                 # 設定ファイル
├── data/
│   ├── cache/              # データキャッシュ
│   └── results/            # バックテスト結果
├── tests/                  # テストコード
├── docs/                   # ドキュメント
├── main.py                 # メインエントリーポイント
├── requirements.txt        # 依存パッケージ
└── README.md              # このファイル
```

## テストの実行

```bash
# 全テストを実行
pytest

# カバレッジレポート付きで実行
pytest --cov=src --cov-report=html

# 特定のテストのみ実行
pytest tests/test_strategy.py
```

## 注意事項

- このシステムは教育・研究目的で作成されています
- 実際の投資判断に使用する場合は自己責任でお願いします
- 過去のパフォーマンスは将来の結果を保証するものではありません
- 取引コスト（手数料、スリッページ）を考慮した現実的な設定を使用してください

## パフォーマンス考慮事項

### 大規模バックテストの実行時

#### システム要件
- **メモリ**: 8GB以上（16GB推奨）
- **CPU**: 4コア以上推奨
- **ストレージ**: 10GB以上の空き容量
- **ネットワーク**: 安定したインターネット接続

#### 実行時間の目安
| 銘柄数 | 期間 | 推定時間 |
|--------|------|----------|
| 10銘柄 | 5年 | 5-10分 |
| 50銘柄 | 5年 | 15-30分 |
| 100銘柄 | 10年 | 30-60分 |
| 450銘柄 | 14年 | 60-120分 |

#### パフォーマンス最適化のヒント
- 他の重いアプリケーションを終了する
- ウイルス対策ソフトのリアルタイムスキャンを一時的に無効化
- ノートPCの場合は電源アダプターを接続
- キャッシュディレクトリがSSD上にあることを確認

## トラブルシューティング

### yfinanceのデータ取得エラー

```bash
# yfinanceを最新版に更新
pip install --upgrade yfinance
```

### 日本の祝日データエラー

```bash
# jpholidayを再インストール
pip install --force-reinstall jpholiday
```

### メモリ不足エラー

- `config.yaml`で対象銘柄数を減らす
- バックテスト期間を短縮する
- 以下のコマンドでメモリ使用量を確認：
  ```python
  import psutil
  print(f"Available memory: {psutil.virtual_memory().available / (1024**3):.1f} GB")
  ```

### データ取得タイムアウト

- ネットワーク接続を確認
- VPNを使用している場合は一時的に無効化
- プロキシ設定を確認

### 大量データのキャッシュクリア

```bash
# キャッシュディレクトリをクリア
rm -rf data/cache/*  # Linux/Mac
del /s /q data\cache\*  # Windows
```

## 今後の拡張予定

- [ ] J-Quants APIへの対応
- [ ] リアルタイム実行機能
- [ ] 機械学習による戦略最適化
- [ ] Webダッシュボード
- [ ] より高度なリスク管理機能

## ライセンス

MIT License

## 貢献

プルリクエストを歓迎します。大きな変更の場合は、まずissueを作成して変更内容を議論してください。

## 作者

[Your Name]

## 謝辞

- yfinanceライブラリの開発者
- 日本の祝日データを提供するjpholidayの開発者
