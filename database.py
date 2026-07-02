import sqlite3
from datetime import datetime
import os

# 預設資料庫名稱
current_db_name = "default_match.db"

def set_tournament_db(name):
    """
    切換賽事資料庫。
    資料庫名稱會自動附加當前日期，變成 '名稱_YYYY_MM_DD.db'。
    """
    global current_db_name
    # 移除檔名中不合法的字元
    safe_name = "".join([c for c in name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
    if not safe_name:
        safe_name = "default_match"
        
    # 自動附加當前日期
    date_str = datetime.now().strftime("%Y_%m_%d")
    current_db_name = f"{safe_name}_{date_str}.db"
    init_db() # 切換後確保該資料庫有建立表格
    return current_db_name

def get_db_path():
    os.makedirs("databases", exist_ok=True)
    return os.path.join("databases", current_db_name)

def init_db():
    """初始化當前選擇的資料庫"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    # 建立成績表 (配合新的比賽資訊欄位擴充)
    c.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_uuid TEXT,       -- 關聯到 Excel 匯入的 UUID
            category TEXT,         -- 組別
            player_name TEXT,      -- 選手姓名
            judge_id TEXT,         -- 裁判 ID
            accuracy REAL,         -- 正確性
            presentation REAL,     -- 表現性
            total REAL,            -- 總分
            round INTEGER,         -- 第幾品勢 (1 or 2)
            timestamp DATETIME,
            p1 REAL DEFAULT 0.0,   -- 速度與力量 (Speed & Power)
            p2 REAL DEFAULT 0.0,   -- 節奏與協調 (Rhythm & Tempo)
            p3 REAL DEFAULT 0.0,   -- 精神表現 (Expression of Energy)
            deduction REAL DEFAULT 0.0, -- 扣分 (Deduction)
            player_side INTEGER DEFAULT 0 -- 選手方位 (0: 青方/單人, 1: 紅方)
        )
    ''')
    
    # 自動檢測並補上評分細項與方位欄位，避免與舊資料庫格式衝突
    c.execute("PRAGMA table_info(scores)")
    columns = [col[1] for col in c.fetchall()]
    
    for p_col in ["p1", "p2", "p3", "deduction"]:
        if p_col not in columns:
            try:
                c.execute(f"ALTER TABLE scores ADD COLUMN {p_col} REAL DEFAULT 0.0")
            except Exception as e:
                print(f"Error adding column {p_col}: {e}")
                
    if "player_side" not in columns:
        try:
            c.execute("ALTER TABLE scores ADD COLUMN player_side INTEGER DEFAULT 0")
        except Exception as e:
            print(f"Error adding column player_side: {e}")
                
    # 建立索引以優化 match_uuid 查詢效能
    c.execute("CREATE INDEX IF NOT EXISTS idx_scores_match_uuid ON scores(match_uuid)")
    conn.commit()
    conn.close()

def save_score(match_uuid, category, player_name, judge_id, accuracy, presentation, total, round_num, p1=0.0, p2=0.0, p3=0.0, deduction=0.0, player_side=0):
    """儲存單一裁判分數，包含細項評分與方位，若已存在則覆蓋"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    # 先刪除同場次、同輪次、同裁判、同方位的舊分數，避免重複寫入
    c.execute("""
        DELETE FROM scores 
        WHERE match_uuid = ? AND round = ? AND judge_id = ? AND player_side = ?
    """, (match_uuid, round_num, judge_id, player_side))
    
    # 寫入新分數
    c.execute("""
        INSERT INTO scores 
        (match_uuid, category, player_name, judge_id, accuracy, presentation, total, round, timestamp, p1, p2, p3, deduction, player_side) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (match_uuid, category, player_name, judge_id, accuracy, presentation, total, round_num, datetime.now(), p1, p2, p3, deduction, player_side))
    conn.commit()
    conn.close()

def save_scores_batch(scores_list):
    """批次儲存多個裁判分數，所有操作在同一個交易 (Transaction) 中完成"""
    if not scores_list:
        return
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    try:
        for s in scores_list:
            match_uuid = s.get('match_uuid')
            round_num = s.get('round_num')
            judge_id = s.get('judge_id')
            player_side = s.get('player_side', 0)
            category = s.get('category', '')
            player_name = s.get('player_name', '')
            accuracy = s.get('acc', 0.0)
            presentation = s.get('pres', 0.0)
            total = s.get('total', 0.0)
            p1 = s.get('p1', 0.0)
            p2 = s.get('p2', 0.0)
            p3 = s.get('p3', 0.0)
            deduction = s.get('deduction', 0.0)

            # 先刪除同場次、同輪次、同裁判、同方位的舊分數，避免重複寫入
            c.execute("""
                DELETE FROM scores 
                WHERE match_uuid = ? AND round = ? AND judge_id = ? AND player_side = ?
            """, (match_uuid, round_num, judge_id, player_side))
            
            # 寫入新分數
            c.execute("""
                INSERT INTO scores 
                (match_uuid, category, player_name, judge_id, accuracy, presentation, total, round, timestamp, p1, p2, p3, deduction, player_side) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (match_uuid, category, player_name, judge_id, accuracy, presentation, total, round_num, datetime.now(), p1, p2, p3, deduction, player_side))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def clear_match_scores(match_uuid):
    """清除特定選手場次的所有分數紀錄"""
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("DELETE FROM scores WHERE match_uuid = ?", (match_uuid,))
    conn.commit()
    conn.close()