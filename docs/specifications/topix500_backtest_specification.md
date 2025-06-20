# TOPIX500全銘柄バックテスト仕様書

## 概要

本ドキュメントでは、TOPIX500構成銘柄を対象とした大規模バックテストの詳細仕様を説明します。

## 対象銘柄

### 銘柄数
- **総数**: 約450銘柄（TOPIX500主要構成銘柄）
- **業種分類**: 全33業種を網羅

### 業種別内訳

| 業種 | 銘柄数（概算） | 代表銘柄 |
|------|---------------|----------|
| 電気機器 | 15 | ソニー、キーエンス、キヤノン |
| 輸送用機器 | 10 | トヨタ、ホンダ、日産 |
| 情報・通信業 | 10 | NTT、KDDI、ソフトバンク |
| 銀行業 | 10 | 三菱UFJ、三井住友、みずほ |
| 医薬品 | 10 | 武田薬品、アステラス、中外製薬 |
| 卸売業 | 10 | 三菱商事、伊藤忠、三井物産 |
| 小売業 | 10 | セブン&アイ、イオン、ファーストリテイリング |
| 化学 | 10 | 信越化学、旭化成、住友化学 |
| 食料品 | 10 | アサヒ、キリン、味の素 |
| 機械 | 10 | SMC、ダイキン、コマツ |
| その他 | 355 | 各業種の主要銘柄 |

## バックテスト設定

### 期間
- **開始日**: 2010年1月1日
- **終了日**: 2023年12月31日
- **期間**: 14年間（約3,500営業日）
- **総データポイント**: 約1,575,000（450銘柄 × 3,500日）

### 資金管理
- **初期資本**: 1億円
- **1銘柄投資額**: 200万円
- **最大同時保有**: 50銘柄
- **最大投資額**: 1億円（50銘柄 × 200万円）

### 戦略パラメータ
- **エントリー**: 権利確定日の3営業日前
- **買い増し**: 初期投資額の30%まで（権利落ち日の下落時）
- **決済条件**:
  - 窓埋め達成（権利落ち前価格まで回復）
  - 最大保有期間: 20営業日
  - 損切りライン: -8%

### 取引コスト
- **手数料**: 0.025%（機関投資家レート）
- **最低手数料**: 100円
- **スリッページ**: 0.15%（流動性考慮）

## システム要件

### ハードウェア
- **最小要件**:
  - メモリ: 8GB
  - CPU: 4コア
  - ストレージ: 10GB空き容量

- **推奨要件**:
  - メモリ: 16GB以上
  - CPU: 8コア以上
  - ストレージ: SSD 20GB以上
  - ネットワーク: 高速インターネット接続

### 実行時間（推定）

| フェーズ | 推定時間 | 詳細 |
|---------|---------|------|
| データ取得 | 30-60分 | 450銘柄の14年分の価格・配当データ |
| キャッシュ処理 | 5-10分 | SQLiteデータベースへの保存 |
| バックテスト計算 | 20-40分 | 日次シミュレーション実行 |
| レポート生成 | 5-10分 | HTML/CSV/JSON形式の出力 |
| **合計** | **60-120分** | 環境により変動 |

## メモリ使用量

### 推定メモリ使用量
- **価格データ**: 約2GB（450銘柄 × 3,500日 × 5項目）
- **配当データ**: 約200MB
- **ポートフォリオ履歴**: 約500MB
- **取引履歴**: 約300MB
- **その他**: 約1GB
- **合計**: 約4GB（ピーク時: 6-8GB）

### メモリ最適化
- データのバッチ処理
- 不要なオブジェクトの定期的な削除
- ガベージコレクションの明示的実行

## 出力結果

### ファイル構成
```
data/results/topix500_full/
├── metrics_YYYYMMDD_HHMMSS.json       # パフォーマンス指標
├── trades_YYYYMMDD_HHMMSS.csv         # 全取引履歴（推定10万件以上）
├── portfolio_YYYYMMDD_HHMMSS.csv      # 日次ポートフォリオ（3,500行）
├── backtest_report_YYYYMMDD_HHMMSS.html   # インタラクティブレポート
├── backtest_report_YYYYMMDD_HHMMSS.txt    # テキストサマリー
└── performance_chart_YYYYMMDD_HHMMSS.png  # パフォーマンスグラフ
```

### 主要評価指標
- **リターン指標**:
  - 総リターン
  - 年率リターン
  - 月次平均リターン

- **リスク指標**:
  - 年率ボラティリティ
  - 最大ドローダウン
  - VaR（95%信頼区間）

- **リスク調整後リターン**:
  - シャープレシオ
  - ソルティノレシオ
  - カルマーレシオ

- **取引統計**:
  - 総取引回数
  - 勝率
  - プロフィットファクター
  - 平均保有期間

## 実行方法

### コマンドライン
```bash
python run_topix500_backtest.py
```

### Windows バッチファイル
```
run_topix500_backtest.bat
```

### カスタム設定での実行
```bash
python main.py --config config/topix500_full_config.yaml
```

## 注意事項

1. **実行前の準備**:
   - 他の重いアプリケーションを終了
   - 十分な空きディスク容量を確保
   - 安定したインターネット接続を確認

2. **実行中の注意**:
   - PCがスリープしないように設定
   - 実行中は他の重い作業を避ける
   - 進捗はログファイルで確認可能

3. **データの信頼性**:
   - yfinanceのデータは参考値
   - 実際の投資判断には追加検証が必要
   - 配当データは権利落ち日ベース

## トラブルシューティング

### メモリ不足エラー
```python
# メモリ使用量を確認
import psutil
print(f"Available: {psutil.virtual_memory().available / (1024**3):.1f} GB")
```

### データ取得エラー
- ネットワーク接続を確認
- yfinanceを最新版に更新
- キャッシュをクリアして再実行

### 実行時間が長い場合
- 銘柄数を段階的に増やしてテスト
- 期間を短縮してテスト
- SSDの使用を推奨

## 参考情報

- **TOPIX500**: 東証株価指数を構成する上位500銘柄
- **配当権利確定**: 通常、決算期末の2営業日前
- **権利落ち**: 配当相当額だけ理論的に株価が下落
- **窓埋め**: 権利落ちで下落した株価が元の水準まで回復

## 更新履歴

- 2024-06-11: 初版作成
- 設定ファイル: `config/topix500_full_config.yaml`
- 実行スクリプト: `run_topix500_backtest.py`
