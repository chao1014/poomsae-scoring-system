@echo off
:: 啟動設備授權產生器 (無命令提示字元黑視窗)

:: 切換到批次檔所在的目錄，確保能找到相應檔案
cd /d "%~dp0"

:: 使用 pythonw.exe 執行 GUI 程式
START "License Generator" pythonw.exe packaging_tools\license_generator.py

exit
