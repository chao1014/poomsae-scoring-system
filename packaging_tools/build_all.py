# build_all.py
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
import json

# 定義目錄結構
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 品勢計分系統根目錄
PACKAGING_DIR = os.path.join(BASE_DIR, "packaging_tools")
BUILD_DIR = os.path.join(BASE_DIR, "build")
DIST_DIR = os.path.join(BASE_DIR, "dist")

def install_requirements():
    """檢查並安裝 PyInstaller 與 PyArmor"""
    # 1. 檢查 PyInstaller
    try:
        import PyInstaller
        print("[OK] 偵測到已安裝 PyInstaller。")
    except ImportError:
        print("[!] 未偵測到 PyInstaller，正在嘗試安裝...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("[OK] PyInstaller 安裝成功！")
        except Exception as e:
            print(f"[ERR] 安裝 PyInstaller 失敗，請手動執行 pip install pyinstaller。錯誤: {e}")
            sys.exit(1)
            
    # 2. 檢查 PyArmor
    try:
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        subprocess.check_output("pyarmor --version", shell=True, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        print("[OK] 偵測到已安裝 PyArmor。")
    except Exception:
        print("[!] 未偵測到 PyArmor，正在嘗試安裝...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyarmor"])
            print("[OK] PyArmor 安裝成功！")
        except Exception as e:
            print(f"[ERR] 安裝 PyArmor 失敗，請手動執行 pip install pyarmor。錯誤: {e}")
            sys.exit(1)

def clean_previous_builds():
    """清理先前的 build 與 dist 資料夾，並強制結束可能的殘留進程"""
    print("[*] 正在強制終止可能被鎖定的品勢系統進程...")
    exes = ["PoomsaeScoringSystem", "app"]
    for exe in exes:
        try:
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(f"taskkill /F /IM {exe}.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        except Exception:
            pass

    print("[*] 正在清理先前的編譯暫存...")
    for dir_path in [BUILD_DIR, DIST_DIR]:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                print(f"  - 已刪除舊資料夾: {os.path.basename(dir_path)}")
            except Exception as e:
                print(f"  - 無法刪除 {dir_path} (可能仍有檔案被系統鎖定): {e}")

def extract_imports_from_files(file_paths):
    """
    從給定的 Python 檔案列表中，自動提取所有的 import 宣告。
    """
    import_lines = []
    for path in file_paths:
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('import ') or stripped.startswith('from '):
                    if '..' not in stripped and ' .' not in stripped and not stripped.startswith('from .'):
                        import_lines.append(stripped)
    return list(set(import_lines)) # 去重

def parse_modules_from_imports(import_statements):
    """
    將 import 語句解析成可以被 PyInstaller 識別的 --hidden-import 模組清單。
    """
    modules = set()
    for stmt in import_statements:
        if stmt.startswith('import '):
            parts = stmt[7:].split(',')
            for p in parts:
                mod = p.split('as')[0].strip()
                if mod:
                    modules.add(mod)
        elif stmt.startswith('from '):
            parts = stmt[5:].split(' import ')
            if len(parts) >= 2:
                parent_mod = parts[0].strip()
                sub_parts = parts[1].split(',')
                modules.add(parent_mod.split('.')[0])
                modules.add(parent_mod)
                for sp in sub_parts:
                    sub_item = sp.split('as')[0].strip()
                    if sub_item:
                        modules.add(f"{parent_mod}.{sub_item}")
    return list(modules)

def run_pyinstaller(script_name, exe_name, is_gui=False):
    """執行 PyArmor 混淆並透過 PyInstaller 打包。若混淆失敗則自動降級為一般打包。"""
    script_path = os.path.join(BASE_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"[ERR] 找不到腳本: {script_name}，跳過打包。")
        return False
        
    startupinfo = None
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # 1. 嘗試 PyArmor 加密混淆
    print(f"[*] 正在準備安全加固打包 {script_name}...")
    obf_out_dir = os.path.join(BUILD_DIR, "obf", exe_name)
    if os.path.exists(obf_out_dir):
        shutil.rmtree(obf_out_dir)
    os.makedirs(obf_out_dir, exist_ok=True)
    
    pyarmor_cmd = [
        "pyarmor", "gen",
        "-O", obf_out_dir,
        script_name,
        "packaging_tools/license_verifier.py",
        "packaging_tools/register_gui.py"
    ]
    
    use_obfuscated = False
    hidden_imports = []
    
    try:
        # 自動提取所有依賴，在 PyInstaller 參數中傳入 --hidden-import，防止加密後丟失
        import_stmts = extract_imports_from_files([
            script_path, 
            os.path.join(BASE_DIR, "packaging_tools", "license_verifier.py"),
            os.path.join(BASE_DIR, "packaging_tools", "register_gui.py")
        ])
        hidden_imports = parse_modules_from_imports(import_stmts)
        
        # 執行混淆
        subprocess.check_call(pyarmor_cmd, cwd=BASE_DIR, startupinfo=startupinfo)
        print("  - 程式碼混淆加密完成，重整套件目錄結構...")
        
        # 重建套件結構
        pkg_tools_dst = os.path.join(obf_out_dir, "packaging_tools")
        os.makedirs(pkg_tools_dst, exist_ok=True)
        
        for lic_file in ["license_verifier.py", "register_gui.py"]:
            src_file = os.path.join(obf_out_dir, lic_file)
            if os.path.exists(src_file):
                shutil.move(src_file, os.path.join(pkg_tools_dst, lic_file))
                
        use_obfuscated = True
    except Exception as e:
        print(f"  - [WARN] 該腳本混淆加固失敗 (原因: 免費版 PyArmor 檔案大小限制或環境問題)。")
        print(f"  - [WARN] 系統將自動降級為標準 PyInstaller 安全打包流程...")
        use_obfuscated = False

    # 2. 設定打包源檔案與命令 (使用 --onefile 模式)
    cmd = [
        "pyinstaller",
        "--clean",
        "-y",
        "--onefile",
        "--paths", BASE_DIR,
        "--specpath", PACKAGING_DIR,
        "--workpath", BUILD_DIR,
        "--distpath", DIST_DIR,
        "--name", exe_name,
        # 品勢計分系統特有的資源與子模組參數
        "--add-data", f"{os.path.join(BASE_DIR, 'static')};static",
        "--add-data", f"{os.path.join(BASE_DIR, 'templates')};templates",
        "--collect-submodules", "dns",
        "--collect-submodules", "eventlet",
        "--collect-submodules", "engineio",
        "--hidden-import", "xlrd",
        "--hidden-import", "openpyxl",
    ]

    # 若是使用混淆代碼，將先前解析出來的所有 hidden imports 傳給 PyInstaller 進行打包
    if use_obfuscated:
        target_script = os.path.join(obf_out_dir, script_name)
        for mod in hidden_imports:
            cmd.append(f"--hidden-import={mod}")
    else:
        target_script = script_path

    if is_gui:
        cmd.append("--noconsole")
        
    cmd.append(target_script)
    
    try:
        subprocess.check_call(cmd, cwd=BASE_DIR, startupinfo=startupinfo)
        tag = "已混淆加密" if use_obfuscated else "標準安全"
        print(f"[OK] 成功打包 {exe_name} ({tag})！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERR] 打包 {exe_name} 失敗！錯誤碼: {e.returncode}")
        return False

def copy_config_files():
    """複製 Ngrok 設定檔範本到 dist/ 目錄，以便使用者直接修改"""
    print("[*] 正在複製設定檔範本到 dist 目錄...")
    
    # 確保發布目錄存在
    if not os.path.exists(DIST_DIR):
        os.makedirs(DIST_DIR, exist_ok=True)

    # 1. 同步 ngrok_config.json
    config_src = os.path.join(BASE_DIR, "ngrok_config.json")
    if os.path.exists(config_src):
        config_dst = os.path.join(DIST_DIR, "ngrok_config.json")
        shutil.copy2(config_src, config_dst)
        print("  - 設定檔 ngrok_config.json 已成功複製到 dist 目錄。")
    else:
        # 如果不存在，建立一個預設範本
        default_config = {
            "auth_token": "請在此填寫您的_Auth_Token",
            "domain": "請在此填寫您的_固定網域.ngrok-free.dev"
        }
        config_dst = os.path.join(DIST_DIR, "ngrok_config.json")
        try:
            with open(config_dst, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            print("  - 已在 dist 目錄下產生預設 ngrok_config.json 檔案。")
        except Exception as e:
            print(f"  - [WARN] 產生 ngrok_config.json 失敗: {e}")

    # 2. 智慧合併 settings.json（保留使用者已有設定，補上開發端新增欄位）
    settings_src = os.path.join(BASE_DIR, "settings.json")
    settings_dst = os.path.join(DIST_DIR, "settings.json")
    try:
        with open(settings_src, 'r', encoding='utf-8') as f:
            src_settings = json.load(f)

        # 若 dist/ 已有 settings.json，以使用者設定為主，僅補上缺少的欄位
        if os.path.exists(settings_dst):
            with open(settings_dst, 'r', encoding='utf-8') as f:
                dst_settings = json.load(f)
            # 將開發端有而 dist 沒有的欄位補進去（不覆蓋已有的使用者設定）
            updated = False
            for key, val in src_settings.items():
                if key not in dst_settings:
                    dst_settings[key] = val
                    updated = True
            if updated:
                with open(settings_dst, 'w', encoding='utf-8') as f:
                    json.dump(dst_settings, f, indent=4, ensure_ascii=False)
                print("  - settings.json 已補入新欄位（保留使用者原有設定）。")
            else:
                print("  - settings.json 無需更新。")
        else:
            # dist/ 尚無 settings.json，直接複製
            shutil.copy2(settings_src, settings_dst)
            print("  - settings.json 已複製到 dist 目錄。")
    except Exception as e:
        print(f"  - [WARN] 同步 settings.json 失敗: {e}")

def main():
    print("==========================================")
    print("      品勢計分系統 一鍵加固打包腳本 v1.0")
    print("==========================================")
    
    install_requirements()
    clean_previous_builds()
    
    # 打包主程式 app.py 為 PoomsaeScoringSystem.exe (保留命令提示字元控制台，is_gui=False)
    success = run_pyinstaller("app.py", "PoomsaeScoringSystem", is_gui=False)
            
    if success:
        copy_config_files()
        print("\n==========================================")
        print(f"[OK] 打包流程結束！成功生成品勢計分系統執行檔。")
        print(f"    最終發布檔案位於: {DIST_DIR}/PoomsaeScoringSystem.exe")
        print(f"    請注意：執行時必須將 license.lic 放在該執行檔同級目錄下。")
        print("==========================================")
    else:
        print("\n[ERR] 打包失敗，未成功生成程式。")

if __name__ == "__main__":
    main()
