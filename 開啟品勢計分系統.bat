@echo off
:: 啟動品勢計分系統 (無黑窗)

:: 切換到批次檔所在的目錄，確保能找到 .py 檔案
cd /d "%~dp0"

:: 使用 pythonw.exe 在背景執行 GUI 程式
:: "Poomsae Scoring System" 是在工作管理員中顯示的程序標題，方便管理
START "Poomsae Scoring" pythonw.exe app.py

exit
