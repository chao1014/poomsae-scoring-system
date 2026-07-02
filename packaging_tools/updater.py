# updater.py
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox

def check_and_update(exe_name, update_source_path):
    """
    檢查指定路徑下是否有新版執行檔，若有則提示使用者並進行自動覆寫更新。
    """
    if not update_source_path:
        return False
        
    # 確保更新來源路徑存在
    if not os.path.exists(update_source_path):
        return False

    # 本地 exe 路徑與遠端 exe 路徑
    local_exe = os.path.abspath(sys.argv[0])
    remote_exe = os.path.join(update_source_path, exe_name)

    # 確保遠端執行檔存在，且並非自己本身（防止開發環境下路徑指向同一處）
    if not os.path.exists(remote_exe) or os.path.normpath(local_exe) == os.path.normpath(remote_exe):
        return False

    try:
        # 讀取本地特徵
        local_size = os.path.getsize(local_exe)
        local_mtime = os.path.getmtime(local_exe)

        # 讀取遠端特徵
        remote_size = os.path.getsize(remote_exe)
        remote_mtime = os.path.getmtime(remote_exe)
        
        # 判定更新標準：大小不同，且遠端的修改時間大於本地（比本地新）
        # 為防範極微小的時間精度差，設定 remote_mtime - local_mtime > 1 秒才視為更新
        is_newer = (remote_mtime - local_mtime) > 1.0
        is_different_size = (remote_size != local_size)

        if not (is_different_size or is_newer):
            # 版本一致，直接通過，正常啟動
            return False

        # 彈出提示視窗
        root = tk.Tk()
        root.withdraw()
        
        msg = f"📢 偵測到伺服器上有最新版 {exe_name}！\n\n是否要立即進行自動同步更新？\n(更新只需數秒，系統將會重啟)"
        ans = messagebox.askyesno("系統更新提示", msg)
        
        if not ans:
            root.destroy()
            return False

        # 開始執行更新流程
        base_dir = os.path.dirname(local_exe)
        temp_dir = os.path.join(base_dir, "temp_update")
        os.makedirs(temp_dir, exist_ok=True)

        # 複製遠端 exe 到本地暫存
        temp_exe = os.path.join(temp_dir, exe_name)
        shutil.copy2(remote_exe, temp_exe)

        # 寫入防鎖定更新批次檔 (update_helper.bat)
        bat_path = os.path.join(temp_dir, "update_helper.bat")
        
        # 批次檔邏輯：
        # 1. 迴圈嘗試覆蓋，防止 PyInstaller 尚未完全關閉導致檔案被鎖定 (最多重試10次)
        # 2. 更新成功與失敗皆以 PowerShell 彈窗提示使用者
        # 3. 自我刪除並退出
        bat_content = f"""@echo off
set retry=0
:loop
ping 127.0.0.1 -n 2 > nul
copy /y "{temp_exe}" "{local_exe}" > nul
if %errorlevel% equ 0 goto success
set /a retry+=1
if %retry% geq 10 goto fail
goto loop

:success
powershell -WindowStyle Hidden -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('系統已更新完畢，請手動重新啟動程式。', '更新成功')"
goto end

:fail
powershell -WindowStyle Hidden -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('更新失敗，主程式可能仍被鎖定。請手動關閉程式後重試。', '更新失敗')"

:end
del "%~f0"
"""
        with open(bat_path, 'w', encoding='big5') as f:
            f.write(bat_content)

        # 在背景無聲啟動批次檔，加入 DETACHED_PROCESS 及 CREATE_NO_WINDOW 避免 PyInstaller 等待子程序
        CREATE_NO_WINDOW = 0x08000000
        DETACHED_PROCESS = 0x00000008
        
        # 清除 PyInstaller 環境變數，防止新啟動的程式繼承舊的 _MEIPASS 導致崩潰
        clean_env = os.environ.copy()
        clean_env.pop('_MEIPASS2', None)
        clean_env.pop('_MEIPASS', None)

        subprocess.Popen(
            f'"{bat_path}"', 
            shell=True, 
            cwd=base_dir, 
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
            env=clean_env
        )
        root.destroy()
        sys.exit(0)

    except Exception as e:
        print(f"自動更新過程出錯: {e}")
        
    return False
