@echo off
REM 配当取り戦略バックテスト実行バッチファイル

echo ========================================
echo 配当取り戦略バックテストシステム
echo ========================================
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

REM 必要なパッケージのインストール確認
echo 必要なパッケージを確認しています...
pip show yfinance >nul 2>&1
if errorlevel 1 (
    echo 必要なパッケージをインストールしています...
    pip install -r requirements.txt
)

REM バックテストの実行
echo.
echo バックテストを開始します...
echo.
python main.py

echo.
echo バックテストが完了しました。
echo 結果は data\results フォルダに保存されています。
echo.
pause
