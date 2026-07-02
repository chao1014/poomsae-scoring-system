import os
import json

# === 全域設定檔案路徑 ===
SETTINGS_FILE = "settings.json"

# === 網路與 SSL 配置中心 ===
PORT = 5003
USE_SSL = False
INTERNAL_SCHEME = "http"
INTERNAL_SSL_CTX = None

# === 預設與當前設定 ===
default_settings = {
    "countdown_sec": 90,
    "slide_duration": 3,
    "judge_count": 5,           
    "court_no": 1,
    "tournament_name": "Default",
    "enable_cloud": True,
    "poomsae_excel_path": "style.xlsx",
    "draw_range_start": "",
    "draw_range_end": "",
    "session_poomsae": {},
    "show_draw_button": True,
    "pk_sequence_mode": 1,  # 0: 同時上場, 1: 交叉上場, 2: 依序上場
    "last_excel_directory": ""
}

system_settings = default_settings.copy()

# === 全域計分與裁判連線狀態 ===
current_state = {
    "is_scoring": False,
    "current_player": "",
    "judges": {},
    "current_player_payload": None,
    "current_player_side": 0,  # 當前正在進行打分的選手方位 (0: 青方/單人, 1: 紅方)
    "pk_seq_state": 0  # 依序上場專用狀態機 (0:青1R, 1:青2R, 2:紅1R, 3:紅2R)
}

# === 系統統一配色配置 ===
colors = {
    "header_bg": "#ffffff", 
    "bar_blue": "#0099cc", 
    "bar_green": "#669900", 
    "bar_red": "#cc0000",
    "table_purple": "#e6ccff", 
    "table_header": "#d9b3ff", 
    "cyan_header": "#008fb3", 
    "judge_blue": "#0099cc",
    "judge_done": "#CC9933", 
    "lime_green": "#99cc00", 
    "lime_dark": "#668000", 
    "lime_val_bg": "#f2ffcc",
    "btn_yellow": "#ffff99", 
    "btn_orange": "#ffcc00", 
    "btn_pink": "#ffcccc",
    "info_bg": "#e6f7ff", 
    "timer_bg": "#000000", 
    "timer_fg": "#ffff00"
}

# === 載入設定函式 ===
def load_settings():
    global system_settings
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                system_settings.update(saved)
        except Exception as e:
            print(f"載入設定失敗: {e}")

# === 儲存設定函式 ===
def save_settings():
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(system_settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"儲存設定失敗: {e}")
