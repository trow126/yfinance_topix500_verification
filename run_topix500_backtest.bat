@echo off
REM TOPIX500全銘柄バックテスト実行バッチファイル
REM 大規模バックテスト用の設定

echo ========================================
echo TOPIX500全銘柄バックテスト
echo Full-Scale Backtest System
echo ========================================
echo.

REM タイムスタンプ
echo 開始時刻: %date% %time%
echo.

REM Python環境の確認
python --version >nul 2>&1
if errorlevel 1 (
    echo エラー: Pythonがインストールされていません。
    echo Pythonをインストールしてから再度実行してください。
    pause
    exit /b 1
)

REM 仮想環境のアクティベート（存在する場合）
if exist "venv\Scripts\activate.bat" (
    echo 仮想環境をアクティベートしています...
    call venv\Scripts\activate.bat
)

REM 必要なパッケージの確認
echo 必要なパッケージを確認しています...
pip show yfinance >nul 2>&1
if errorlevel 1 (
    echo 必要なパッケージをインストールしています...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo パッケージのインストールに失敗しました。
        pause
        exit /b 1
    )
)

REM メモリ設定（大規模データ処理用）
echo.
echo システム設定を最適化しています...
set PYTHONHASHSEED=0

REM ログディレクトリの作成
if not exist "logs" mkdir logs

REM 実行確認
echo.
echo ========================================
echo 実行内容:
echo   - 対象銘柄: TOPIX500（約450銘柄）
echo   - 期間: 2010年～2023年（14年間）
echo   - 推定時間: 1～2時間
echo   - 必要メモリ: 8GB以上推奨
echo ========================================
echo.
echo 注意: 実行中はPCが重くなる可能性があります。
echo       他の重い作業は避けることをお勧めします。
echo.

set /p confirm="実行を開始しますか？ (Y/N): "
if /i not "%confirm%"=="Y" (
    echo 実行をキャンセルしました。
    pause
    exit /b 0
)

REM バックテストの実行
echo.
echo ========================================
echo バックテストを開始します...
echo ========================================
echo.

python run_topix500_backtest.py

REM 実行結果の確認
if errorlevel 1 (
    echo.
    echo ========================================
    echo エラーが発生しました。
    echo ログファイルを確認してください。
    echo   logs\topix500_backtest.log
    echo ========================================
) else (
    echo.
    echo ========================================
    echo バックテストが正常に完了しました！
    echo ========================================
    echo.
    echo 結果ファイル:
    echo   data\results\topix500_full\
    echo.
    echo 以下のファイルが生成されています:
    echo   - backtest_report_*.html （HTMLレポート）
    echo   - metrics_*.json （パフォーマンス指標）
    echo   - trades_*.csv （取引履歴）
    echo   - portfolio_*.csv （ポートフォリオ推移）
    echo ========================================
)

echo.
echo 終了時刻: %date% %time%
echo.
pause
