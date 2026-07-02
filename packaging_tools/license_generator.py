# license_generator.py
# -*- coding: utf-8 -*-

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

# 為了能夠引用 license_verifier 內建的密鑰與簽章計算，我們把路徑加入 sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from license_verifier import calculate_signature
except ImportError:
    # 若導入失敗，在此重寫 signature 計算 (防範直接點擊時的 path 問題)
    import hmac
    import hashlib
    SECRET_KEY = b"PoomsaeScoringSystemKey2026_Sec"
    def calculate_signature(data_dict):
        serialized = {k: v for k, v in data_dict.items() if k != "signature"}
        data_str = json.dumps(serialized, sort_keys=True, ensure_ascii=False)
        mac = hmac.new(SECRET_KEY, data_str.encode('utf-8'), hashlib.sha256)
        return mac.hexdigest()

class LicenseGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("品勢計分系統 - 授權金鑰產生器 v1.0")
        self.root.geometry("560x420")
        self.root.resizable(False, False)
        
        # 設定視窗置中
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        self.create_widgets()

    def create_widgets(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Header.TLabel", font=("Microsoft JhengHei", 12, "bold"), foreground="#0275d8")
        style.configure("Btn.TButton", font=("Microsoft JhengHei", 10, "bold"), padding=6)
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 標題
        title_label = ttk.Label(main_frame, text="🔑 品勢計分系統授權金鑰管理系統", style="Header.TLabel")
        title_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
        
        # 授權對象
        ttk.Label(main_frame, text="授權對象名稱:").grid(row=1, column=0, sticky="w", pady=5)
        self.ent_licensee = ttk.Entry(main_frame, width=40)
        self.ent_licensee.insert(0, "特定跆拳道推廣中心 / 體育館")
        self.ent_licensee.grid(row=1, column=1, sticky="ew", pady=5)
        
        # 機器碼
        ttk.Label(main_frame, text="設備機器碼:").grid(row=2, column=0, sticky="w", pady=5)
        self.ent_machine_id = ttk.Entry(main_frame, width=40)
        self.ent_machine_id.insert(0, "TK-XXXX-XXXX-XXXX-XXXX")
        self.ent_machine_id.grid(row=2, column=1, sticky="ew", pady=5)
        
        # 到期時間
        ttk.Label(main_frame, text="授權到期日期:").grid(row=3, column=0, sticky="w", pady=5)
        self.ent_expire_date = ttk.Entry(main_frame, width=40)
        self.ent_expire_date.insert(0, "2026-12-31")
        self.ent_expire_date.grid(row=3, column=1, sticky="ew", pady=5)
        
        # 授權模組
        ttk.Label(main_frame, text="授權模組權限:").grid(row=4, column=0, sticky="nw", pady=5)
        
        modules_frame = ttk.LabelFrame(main_frame, text=" 選擇授權模組 ", padding="10")
        modules_frame.grid(row=4, column=1, sticky="nsew", pady=5)
        
        self.chk_all_var = tk.BooleanVar(value=True)
        self.chk_poomsae_var = tk.BooleanVar(value=True)
        
        # 全選勾選事件
        def toggle_all():
            val = self.chk_all_var.get()
            self.chk_poomsae_var.set(val)
            
        # 個別勾選事件
        def update_all_checkbox():
            if self.chk_poomsae_var.get():
                self.chk_all_var.set(True)
            else:
                self.chk_all_var.set(False)
            
        self.chk_all = ttk.Checkbutton(modules_frame, text="全選 / 全部模組通配 (*)", variable=self.chk_all_var, command=toggle_all)
        self.chk_all.pack(anchor="w", pady=2)
        
        ttk.Separator(modules_frame, orient="horizontal").pack(fill="x", pady=5)
        
        self.chk_poomsae = ttk.Checkbutton(modules_frame, text="品勢計分主系統 (poomsae)", variable=self.chk_poomsae_var, command=update_all_checkbox)
        self.chk_poomsae.pack(anchor="w", pady=2)
        
        # 產生按鈕
        btn_generate = ttk.Button(main_frame, text="⚙ 產生並儲存授權檔案 (license.lic)", style="Btn.TButton", command=self.generate_license)
        btn_generate.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(20, 0))
        
        # 視窗欄位權重調整
        main_frame.grid_columnconfigure(1, weight=1)

    def generate_license(self):
        licensee = self.ent_licensee.get().strip()
        machine_id = self.ent_machine_id.get().strip().upper()
        expire_date = self.ent_expire_date.get().strip()
        
        # 1. 欄位驗證
        if not licensee:
            messagebox.showerror("錯誤", "請輸入授權對象名稱！")
            return
        if not machine_id or machine_id == "TK-XXXX-XXXX-XXXX-XXXX":
            messagebox.showerror("錯誤", "請輸入有效的主機機器碼！")
            return
        
        # 檢查機器碼格式 (TK-XXXX-XXXX-XXXX-XXXX)
        parts = machine_id.split('-')
        if len(parts) != 5 or parts[0] != "TK" or not all(len(p) == 4 for p in parts[1:]):
            messagebox.showerror("錯誤", "機器碼格式不正確！正確格式為: TK-XXXX-XXXX-XXXX-XXXX")
            return
            
        try:
            datetime.strptime(expire_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("錯誤", "到期日期格式有誤！必須為 YYYY-MM-DD (例如: 2026-12-31)")
            return
            
        # 2. 模組列表
        modules = []
        if self.chk_all_var.get():
            modules.append("*")
        else:
            if self.chk_poomsae_var.get(): modules.append("poomsae")
            
        if not modules:
            messagebox.showerror("錯誤", "請至少選擇一項授權模組！")
            return
            
        # 3. 組裝資料
        lic_data = {
            "licensee": licensee,
            "machine_id": machine_id,
            "expire_date": expire_date,
            "authorized_modules": modules
        }
        
        # 4. 計算簽章
        signature = calculate_signature(lic_data)
        lic_data["signature"] = signature
        
        # 5. 儲存檔案
        file_path = filedialog.asksaveasfilename(
            title="儲存授權金鑰檔案",
            initialfile="license.lic",
            filetypes=[("License Files", "*.lic")]
        )
        if not file_path:
            return
            
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(lic_data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("成功", f"授權檔案已成功產生並儲存於：\n{file_path}")
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存檔案失敗: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = LicenseGeneratorGUI(root)
    root.mainloop()
