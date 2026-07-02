# register_gui.py
# -*- coding: utf-8 -*-

import os
import shutil
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

def show_registration_window(module_name, machine_id, reason_text):
    """
    顯示授權註冊與匯入視窗。
    回傳: True (註冊/驗證成功), False (取消或關閉視窗)
    """
    result = {"success": False}
    
    root = tk.Tk()
    root.title(f"系統授權驗證 - {module_name}")
    root.geometry("520x350")
    root.resizable(False, False)
    
    # 設定視窗置中
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    # 樣式設定
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("Title.TLabel", font=("Microsoft JhengHei", 14, "bold"), foreground="#d9534f")
    style.configure("Content.TLabel", font=("Microsoft JhengHei", 10))
    style.configure("MachineID.TEntry", font=("Consolas", 11, "bold"), justify="center")
    style.configure("Action.TButton", font=("Microsoft JhengHei", 10, "bold"), padding=6)
    
    # 主容器
    main_frame = ttk.Frame(root, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # 標題
    title_label = ttk.Label(main_frame, text="⚠ 系統授權未驗證或已過期", style="Title.TLabel")
    title_label.pack(pady=(0, 10))
    
    # 原因說明
    reason_label = ttk.Label(
        main_frame, 
        text=f"本機設備尚未獲得授權，或授權驗證失敗。\n狀態說明: {reason_text}", 
        style="Content.TLabel", 
        justify="left",
        wraplength=480
    )
    reason_label.pack(pady=(0, 15))
    
    # 機器碼顯示區
    mid_frame = ttk.LabelFrame(main_frame, text=" 本機機器碼 (請提供給管理員) ", padding="10")
    mid_frame.pack(fill=tk.X, pady=(0, 20))
    
    machine_id_var = tk.StringVar(value=machine_id)
    entry_mid = ttk.Entry(mid_frame, textvariable=machine_id_var, state="readonly", style="MachineID.TEntry")
    entry_mid.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    
    def copy_to_clipboard():
        root.clipboard_clear()
        root.clipboard_append(machine_id)
        messagebox.showinfo("複製成功", "機器碼已複製到剪貼簿，請傳送給管理員。")
        
    btn_copy = ttk.Button(mid_frame, text="複製機器碼", command=copy_to_clipboard)
    btn_copy.pack(side=tk.RIGHT)
    
    # 按鈕控制區
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, pady=(10, 0))
    
    def import_license():
        # 開啟檔案選擇器尋找 license.lic 檔案
        file_path = filedialog.askopenfilename(
            title="選擇授權檔案",
            filetypes=[("License Files", "*.lic"), ("All Files", "*.*")]
        )
        if not file_path:
            return
            
        try:
            from packaging_tools.license_verifier import verify_license_data, calculate_signature, get_license_path
            import json
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lic_data = json.load(f)
                
            is_valid, err_code, detail = verify_license_data(lic_data, machine_id, module_name)
            
            if is_valid:
                # 複製授權檔到主程式目錄
                dest_path = get_license_path()
                shutil.copy2(file_path, dest_path)
                
                messagebox.showinfo(
                    "授權成功", 
                    f"授權驗證成功！\n"
                    f"授權對象: {lic_data.get('licensee')}\n"
                    f"到期日期: {lic_data.get('expire_date')}\n\n"
                    f"系統即將啟動。"
                )
                result["success"] = True
                root.destroy()
            else:
                messagebox.showerror("驗證失敗", f"該授權檔案無效。\n錯誤原因: {detail}")
        except Exception as e:
            messagebox.showerror("讀取失敗", f"無法解析所選取的授權檔案。\n錯誤資訊: {str(e)}")
            
    btn_import = ttk.Button(btn_frame, text="📥 匯入授權檔 (license.lic)", style="Action.TButton", command=import_license)
    btn_import.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    
    def cancel_registration():
        root.destroy()
        
    btn_cancel = ttk.Button(btn_frame, text="關閉退出", command=cancel_registration)
    btn_cancel.pack(side=tk.RIGHT)
    
    root.mainloop()
    return result["success"]

if __name__ == "__main__":
    # 測試用
    show_registration_window("poomsae", "TK-TEST-1234-5678-ABCD", "測試用錯誤說明")
