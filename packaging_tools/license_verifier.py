# license_verifier.py
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import hashlib
import hmac
import json
import uuid
from datetime import datetime

# 全域設定
SECRET_KEY = b"PoomsaeScoringSystemKey2026_Sec"
LICENSE_FILE_NAME = "license.lic"

def get_hardware_info():
    """
    獲取硬體特徵資訊。
    優先使用主機板 UUID 與 CPU ID，若無效或取得失敗則退回使用 MAC 位址。
    """
    uuid_str = ""
    cpu_str = ""
    
    # 1. 嘗試獲取主機板 UUID
    try:
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        output = subprocess.check_output(
            "wmic csproduct get uuid", 
            shell=True, 
            startupinfo=startupinfo,
            stderr=subprocess.DEVNULL
        ).decode('utf-8', errors='ignore')
        
        lines = [line.strip() for line in output.split('\n') if line.strip()]
        if len(lines) > 1:
            val = lines[1].strip()
            # 排除無效或預設的 UUID
            if val and "00000000" not in val and "FFFFFFFF" not in val:
                uuid_str = val
    except Exception:
        pass

    # 2. 嘗試獲取 CPU ID
    try:
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        output = subprocess.check_output(
            "wmic cpu get processorid", 
            shell=True, 
            startupinfo=startupinfo,
            stderr=subprocess.DEVNULL
        ).decode('utf-8', errors='ignore')
        
        lines = [line.strip() for line in output.split('\n') if line.strip()]
        if len(lines) > 1:
            cpu_str = lines[1].strip()
    except Exception:
        pass

    # 3. 組合硬體資訊
    hardware_concat = f"{uuid_str}_{cpu_str}".strip("_")
    
    # 4. 若皆無效，則使用 MAC 位址
    if not hardware_concat or len(hardware_concat) < 5:
        mac_num = uuid.getnode()
        hardware_concat = f"MAC-{mac_num}"
        
    return hardware_concat

def generate_machine_id():
    """
    根據硬體特徵生成唯一的 16 碼機器碼 (格式: TK-XXXX-XXXX-XXXX-XXXX)
    """
    hardware_str = get_hardware_info()
    sha = hashlib.sha256(hardware_str.encode('utf-8')).hexdigest().upper()
    # 取前 16 碼並分段
    part1 = sha[0:4]
    part2 = sha[4:8]
    part3 = sha[8:12]
    part4 = sha[12:16]
    return f"TK-{part1}-{part2}-{part3}-{part4}"

def calculate_signature(data_dict):
    """
    為授權資料計算 HMAC-SHA256 簽章。
    """
    # 排除 signature 欄位，並將其餘欄位鍵值排序序列化
    serialized = {k: v for k, v in data_dict.items() if k != "signature"}
    data_str = json.dumps(serialized, sort_keys=True, ensure_ascii=False)
    
    mac = hmac.new(SECRET_KEY, data_str.encode('utf-8'), hashlib.sha256)
    return mac.hexdigest()

def verify_license_data(lic_data, current_machine_id, module_name):
    """
    驗證授權檔案資料的有效性。
    回傳: (is_valid, error_code, detail)
    """
    # 1. 檢查必要欄位
    required_fields = ["machine_id", "expire_date", "licensee", "authorized_modules", "signature"]
    if not all(field in lic_data for field in required_fields):
        return False, "INVALID_FORMAT", "授權檔格式損壞或欄位遺漏"

    # 2. 驗證 HMAC 簽章，防竄改
    expected_sig = calculate_signature(lic_data)
    if not hmac.compare_digest(lic_data["signature"], expected_sig):
        return False, "SIGNATURE_MISMATCH", "授權檔簽章錯誤（可能已被惡意竄改）"

    # 3. 驗證機器碼
    if lic_data["machine_id"] != current_machine_id:
        return False, "MACHINE_MISMATCH", f"授權機器碼與本機不符"

    # 4. 驗證模組授權
    if module_name not in lic_data["authorized_modules"] and "*" not in lic_data["authorized_modules"]:
        return False, "MODULE_UNAUTHORIZED", f"本模組 ({module_name}) 未獲得授權"

    # 5. 驗證過期時間
    try:
        expire_date = datetime.strptime(lic_data["expire_date"], "%Y-%m-%d").date()
        today = datetime.now().date()
        if today > expire_date:
            return False, "EXPIRED", f"授權已於 {lic_data['expire_date']} 到期"
    except ValueError:
        return False, "INVALID_DATE_FORMAT", "過期日期格式有誤 (必須為 YYYY-MM-DD)"

    # 6. 驗證簽發時間（防止將時間調到簽發之前）
    # 向下相容：若無 issue_date 欄位，預設為 "2026-01-01"
    issue_date_str = lic_data.get("issue_date", "2026-01-01")
    try:
        issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
        if today < issue_date:
            return False, "TIME_TRAVEL_BACKWARD_BEFORE_ISSUE", f"系統時間異常，不得早於授權簽發日期 {issue_date_str}"
    except ValueError:
        return False, "INVALID_ISSUE_DATE_FORMAT", "授權簽發日期格式有誤 (必須為 YYYY-MM-DD)"

    return True, "SUCCESS", lic_data

def get_license_path():
    """
    獲取授權檔路徑。
    優先序：
    1. 與執行檔同級的 license.lic
    2. 執行檔上一級目錄的 license.lic
    預設回傳：執行檔上一級目錄的 license.lic (為了使 dist/ 底下共用一個授權檔)
    """
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    same_dir_path = os.path.join(base_dir, LICENSE_FILE_NAME)
    parent_dir_path = os.path.join(os.path.dirname(base_dir), LICENSE_FILE_NAME)
    
    # 1. 如果同級目錄已有，優先使用同級
    if os.path.exists(same_dir_path):
        return same_dir_path
    # 2. 如果上一級目錄已有，使用上一級的
    if os.path.exists(parent_dir_path):
        return parent_dir_path
        
    # 3. 若皆不存在，檢查上一級目錄是否為 dist，如果是則預設回傳上一級目錄
    parent_dir_name = os.path.basename(os.path.dirname(base_dir))
    if parent_dir_name.lower() == "dist":
        return parent_dir_path
        
    # 開發環境下，預設回傳同級目錄
    return same_dir_path

def load_and_verify(module_name):
    """
    載入並驗證授權檔案，以及校驗「最後執行時間」防篡改。
    回傳: (is_valid, error_code, detail, current_machine_id)
    """
    current_machine_id = generate_machine_id()
    lic_path = get_license_path()
    
    if not os.path.exists(lic_path):
        return False, "LICENSE_NOT_FOUND", "找不到授權檔案", current_machine_id

    try:
        with open(lic_path, 'r', encoding='utf-8') as f:
            lic_data = json.load(f)
    except Exception as e:
        return False, "LOAD_FAILED", f"讀取授權檔失敗: {str(e)}", current_machine_id

    is_valid, err_code, detail = verify_license_data(lic_data, current_machine_id, module_name)
    if not is_valid:
        return False, err_code, detail, current_machine_id

    # 授權基本驗證通過後，開始「最後執行時間」的校驗
    sys_time_path = os.path.join(os.path.dirname(lic_path), ".sys_time.dat")
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if os.path.exists(sys_time_path):
        try:
            with open(sys_time_path, 'r', encoding='utf-8') as f:
                time_data = json.load(f)
                
            # 驗證時間檔的簽章
            expected_sig = calculate_signature(time_data)
            if not hmac.compare_digest(time_data.get("signature", ""), expected_sig):
                return False, "TIME_RECORD_TAMPERED", "系統時間紀錄檔已被竄改", current_machine_id
                
            last_run_str = time_data.get("last_run", "")
            last_run = datetime.strptime(last_run_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            
            if today < last_run:
                return False, "TIME_TRAVEL_BACKWARD", f"系統偵測到本機時間異常，目前時間不得早於上次使用時間 ({last_run_str})", current_machine_id
                
        except Exception as e:
            return False, "TIME_RECORD_ERROR", f"校驗時間紀錄檔時出錯: {str(e)}", current_machine_id
            
    # 驗證都通過，或者檔案不存在（首次運行），則更新/建立時間紀錄檔
    try:
        new_time_data = {
            "last_run": today_str
        }
        new_time_data["signature"] = calculate_signature(new_time_data)
        with open(sys_time_path, 'w', encoding='utf-8') as f:
            json.dump(new_time_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        # 寫入失敗可能是權限問題，但不該因此阻擋使用者開啟
        print(f"寫入時間紀錄檔失敗: {e}")

    return True, "SUCCESS", detail, current_machine_id

def check_and_enforce(module_name):
    """
    供主程式呼叫的簡化入口。
    驗證授權，若驗證失敗，自動調用 register_gui 進行授權註冊，
    並在註冊失敗/關閉視窗時強制終止程式。
    """
    is_valid, err_code, detail, machine_id = load_and_verify(module_name)
    if is_valid:
        return detail
        
    # 授權失敗，尋求註冊介面
    try:
        from packaging_tools.register_gui import show_registration_window
        success = show_registration_window(module_name, machine_id, f"錯誤代碼: {err_code} ({detail})")
        if success:
            # 註冊成功後重新載入並回傳授權資訊
            is_valid, err_code, detail, machine_id = load_and_verify(module_name)
            if is_valid:
                return detail
            return True
    except ImportError:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "授權驗證失敗", 
            f"模組: {module_name}\n"
            f"機器碼: {machine_id}\n\n"
            f"錯誤: {detail}\n\n"
            "請將機器碼複製並提供給管理員以獲取授權。"
        )
        
    # 驗證失敗且使用者未註冊成功，強制結束
    sys.exit(1)

if __name__ == '__main__':
    print("==========================================")
    print("  設備硬體指紋讀取工具 (品勢計分系統)")
    print("==========================================")
    print(f"本機設備機器碼: {generate_machine_id()}")
    print("==========================================")
