# 権利落ち日の隠れた買い増し問題

## 問題の概要

設定ファイルで買い増し機能を無効（`addition.enabled: false`）にしているにも関わらず、実際のバックテストでは権利落ち日に買い増しが実行されてしまう問題が発見されました。

## 問題の原因

`src/backtest/engine.py`の`_process_existing_positions`メソッドにおいて、買い増し処理の条件チェックが不完全でした：

```python
# 問題のあるコード
if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():
    # 買い増し処理...
```

このコードでは、`self.config.strategy.addition.enabled`のチェックが行われていないため、設定に関わらず権利落ち日には必ず買い増し処理が実行されてしまいます。

## 影響

1. **ポジションサイズの意図しない増加**
   - 500株でエントリーしたポジションが、権利落ち日に1000株に増える
   - 資金管理が狂い、リスクが増大する

2. **バックテスト結果の歪み**
   - 実際の戦略とは異なる結果が出力される
   - パフォーマンス指標が正確でなくなる

3. **設定の無視**
   - ユーザーが意図的に買い増しを無効にしても反映されない

## 修正方法

### 自動修正

```bash
python fix_hidden_addition.py
```

このスクリプトは以下を実行します：
1. engine.pyのバックアップを作成
2. 買い増し処理の条件を修正
3. 修正が正しく適用されたか検証

### 手動修正

`src/backtest/engine.py`の約150行目付近を以下のように修正：

**修正前：**
```python
# 買い増しシグナルをチェック（権利落ち日のみ）
if position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():
```

**修正後：**
```python
# 買い増しシグナルをチェック（権利落ち日のみ）
if self.config.strategy.addition.enabled and position.ex_dividend_date and current_date.date() == position.ex_dividend_date.date():
```

## 検証方法

修正後、以下のコマンドでテストを実行：

```bash
# 最小限のテスト（買い増し無効）
python main.py --config config/minimal_debug.yaml

# 買い増し検出スクリプトを再実行
python detect_hidden_addition.py
```

正しく修正されていれば、ポジション株数は500株のまま変化しないはずです。

## 追加の推奨事項

1. **単体テストの追加**
   - 買い増し機能のON/OFFが正しく動作することを確認するテストケースを追加

2. **設定バリデーション**
   - 矛盾する設定（enabled=false だが add_ratio>0 など）を検出する機能を追加

3. **ログの強化**
   - 買い増し処理の実行時に、設定値と実行理由をログに出力

## 関連ファイル

- `src/backtest/engine.py` - バックテストエンジン（修正対象）
- `src/strategy/dividend_strategy.py` - 戦略実装
- `config/minimal_debug.yaml` - テスト用設定ファイル
- `detect_hidden_addition.py` - 問題検出スクリプト
- `fix_hidden_addition.py` - 自動修正スクリプト
