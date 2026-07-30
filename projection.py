import tkinter as tk
import os
import socket
import config

system_settings = config.system_settings
current_state = config.current_state

def log_refresh_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            from datetime import datetime
            import traceback
            with open("error.log", "a", encoding="utf-8") as err_f:
                err_f.write(f"--- REFRESH ERROR AT {datetime.now()} ---\n")
                traceback.print_exc(file=err_f)
            raise e
    return wrapper

def format_pk_score(val):
    try:
        val_f = float(val)
        if abs(val_f - 10.0) < 0.0001:
            return "10.00"
        return f"{val_f:.3f}"
    except Exception:
        return str(val)

class ProjectionWindow(tk.Toplevel):
    def __init__(self, master, x=0, y=0, width=1920, height=1080):
        super().__init__(master)
        self.title("Score Projection")
        self.configure(bg="black")
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.overrideredirect(True) 
        self.attributes('-topmost', True)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Double-Button-1>", lambda e: self.destroy()) 
        self.pack_propagate(False) 
        
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.width = width
        self.height = height
        self.poomsae_lang_mode = 0  # 0: 中文, 1: 英文
        self.current_group_raw_text = ""
        self.is_marquee_active = False
        self.is_marquee_scroll_running = False
        self.current_team_raw_text = ""
        self.is_team_marquee_active = False
        self.is_team_marquee_scroll_running = False
        self.team_scroll_x = 0
        self.team_scroll_threshold_dist = 0
        self.team_marquee_delay_id = None
        self.current_score_slide = 0
        self.score_slide_timer_id = None
        self.status_text = ""
        self.group_text_width = 0
        self.group_scroll_x = 0
        self.scroll_threshold_dist = 0
        self.marquee_delay_id = None
        self.flash_row_idx = -1
        self.flash_timer_id = None
        self.flash_state = False
        self.score_slide_show_finished = False
        self.last_is_showing_score = False
        
        self.judge_rects = []
        self.judge_texts = []
        self.txt_no = None
        self.txt_group = None
        self.txt_team = None
        self.txt_player = None
        self.txt_status = None
        self.txt_1r = None
        self.txt_2r = None
        
        # 繪製背景與建立物件
        self.draw_background()
        
        # 品勢語言切換定時器 (5 秒)
        self.after(5000, self.poomsae_tick)
        
        # 排行榜分頁定時器 (獨立 10 秒)
        self.leaderboard_page_timer_id = self.after(10000, self.leaderboard_page_tick)
        
        # 綁定視窗大小改變事件以重新適應版面實現等比例自適應
        self.bind("<Configure>", self.on_resize)
        
        self.refresh()
        self.update()

    def hex_to_rgb(self, hex_str):
        """解析十六進位色彩字串為 RGB 8-bit 三元組，替代 winfo_rgb 以免在 headless 環境下崩潰"""
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])
        return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)

    def draw_gradient_y_on_canvas(self, canvas, x1, y1, x2, y2, color1, color2):
        """在指定的 Canvas 上繪製垂直漸層並回傳建立的矩形 ID 列表"""
        ids = []
        r1 = self.hex_to_rgb(color1)
        r1, g1, b1 = r1[0], r1[1], r1[2]
        r2, g2, b2 = self.hex_to_rgb(color2)
        
        h = y2 - y1
        if h <= 0: return ids
        step = 2
        for y in range(0, int(h), step):
            ratio = y / h
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            color = f"#{r:02x}{g:02x}{b:02x}"
            rect = canvas.create_rectangle(x1, y1 + y, x2, y1 + y + step, fill=color, outline="")
            ids.append(rect)
        return ids

    def draw_gradient_y(self, x1, y1, x2, y2, color1, color2):
        """在主 Canvas 上繪製垂直漸層並回傳建立的矩形 ID 列表"""
        return self.draw_gradient_y_on_canvas(self.canvas, x1, y1, x2, y2, color1, color2)

    def draw_background(self):
        """依據比例與圖層順序繪製投影畫面各區塊，並建立文字與裁判燈物件。
        透過圖層順序（後畫的壓在先畫的上方）實現跑馬燈文字的邊界遮罩，避免文字溢出。
        """
        W = self.width
        H = self.height
        
        self.canvas.delete("all")
        self.judge_rects.clear()
        self.judge_texts.clear()
        self.is_marquee_active = False  # 重設跑馬燈定時狀態
        self.current_group_raw_text = ""
        
        # === 圖片像素精確分析比例常數 ===
        Rw = max(120, int(W * 0.094)) # 右側裁判狀態欄寬度 (9.4%)
        Lw = W - Rw                   # 左側主區域寬度 (90.6%)
        Th = max(80, int(H * 0.155))  # 頂部欄高度 (15.5%)
        Bh = max(120, int(H * 0.160)) # 底部欄高度 (16.0%)
        Mh = H - Th - Bh              # 中間區域高度 (68.5%)
        Uh = int(Mh * 0.214)          # 中間上層單位高度 (21.4%)
        Nh = Mh - Uh                  # 中間下層姓名高度 (78.6%)
        
        # --- 圖層 1: 底層背景 ---
        self.normal_layout_items = []
        self.general_bg_items = []
        
        # 中間上層（單位）：黃褐色漸層
        g1 = self.draw_gradient_y(0, Th, Lw, Th + Uh, "#90680a", "#5a3f02")
        self.normal_layout_items.extend(g1)
        # 中間下層（姓名）：深黃褐色漸層
        g2 = self.draw_gradient_y(0, Th + Uh, Lw, Th + Mh, "#7a5502", "#402a01")
        self.normal_layout_items.extend(g2)
        
        # 頂部右側（組別資訊）背景 (常駐)
        x_top_split = int(Lw * 0.139)
        top_r_bg = self.draw_gradient_y(x_top_split, 0, W, Th, "#3a3a3a", "#151515")
        self.general_bg_items.extend(top_r_bg)
        
        # --- 圖層 2: 組別資訊文字 (將被圖層 3 的籤號與裁判背景遮蓋以實現裁剪) ---
        self.txt_group = self.canvas.create_text(
            x_top_split + (W - x_top_split) / 2, Th / 2, 
            text="", 
            font=("Microsoft JhengHei", int(Th * 0.35), "bold"), 
            fill="#ffffff", 
            anchor="center"
        )
        
        # --- 圖層 3: 頂層背景與文字 (遮罩層) ---
        # 頂部左側（籤號）背景與文字
        top_l_bg = self.draw_gradient_y(0, 0, x_top_split, Th, "#242424", "#0a0a0a")
        self.general_bg_items.extend(top_l_bg)
        self.txt_no = self.canvas.create_text(
            x_top_split / 2, Th / 2, 
            text="", 
            font=("Microsoft JhengHei", int(Th * 0.35), "bold"), 
            fill="#ffffff", 
            justify="center"
        )
        
        # 底部三格（狀態/時間、1R、2R）背景與文字
        x_bot1 = int(Lw * 0.329)
        x_bot2 = int(Lw * 0.666)
        bot_bg1 = self.draw_gradient_y(0, H - Bh, x_bot1, H, "#252525", "#0c0c0c")
        bot_bg2 = self.draw_gradient_y(x_bot1, H - Bh, x_bot2, H, "#252525", "#0c0c0c")
        bot_bg3 = self.draw_gradient_y(x_bot2, H - Bh, Lw, H, "#252525", "#0c0c0c")
        self.general_bg_items.extend(bot_bg1 + bot_bg2 + bot_bg3)
        
        self.txt_status = self.canvas.create_text(
            x_bot1 / 2, H - Bh / 2, 
            text="", 
            font=("Microsoft JhengHei", int(Bh * 0.33), "bold"), 
            fill="#ffff00", 
            justify="center"
        )
        self.txt_1r = self.canvas.create_text(
            x_bot1 + (x_bot2 - x_bot1) / 2, H - Bh / 2, 
            text="", 
            font=("Microsoft JhengHei", int(Bh * 0.28), "bold"), 
            fill="#ffffff", 
            justify="center"
        )
        self.txt_2r = self.canvas.create_text(
            x_bot2 + (Lw - x_bot2) / 2, H - Bh / 2, 
            text="", 
            font=("Microsoft JhengHei", int(Bh * 0.28), "bold"), 
            fill="#ffffff", 
            justify="center"
        )
        
        # 中間的單位與姓名文字
        self.txt_team = self.canvas.create_text(
            Lw / 2, Th + Uh / 2, 
            text="", 
            font=("Microsoft JhengHei", int(Uh * 0.38), "bold"), 
            fill="#ffffff", 
            justify="center"
        )
        self.txt_player = self.canvas.create_text(
            Lw / 2, Th + Uh + Nh / 2, 
            text="", 
            font=("Microsoft JhengHei", int(Nh * 0.22), "bold"), 
            fill="#ffffff", 
            justify="center",
            width=Lw - 80
        )
        self.normal_layout_items.extend([self.txt_team, self.txt_player])
        
        # --- 分數表格版面元件初始化 ---
        self.score_layout_items = []
        h_name = Mh * 0.14
        y_name_top = Th
        y_name_bot = Th + h_name
        
        # 姓名單位窄條背景 (黑灰色漸層)
        g_name = self.draw_gradient_y(0, y_name_top, Lw, y_name_bot, "#2a2a2a", "#111111")
        self.score_layout_items.extend(g_name)
        
        # 姓名單位窄條文字
        self.txt_score_player = self.canvas.create_text(
            Lw / 2, y_name_top + h_name / 2,
            text="",
            font=("Microsoft JhengHei", int(h_name * 0.45), "bold"),
            fill="#ffffff",
            anchor="center"
        )
        self.txt_score_team = self.canvas.create_text(
            0, 0, text="", state="hidden"
        )
        self.score_layout_items.extend([self.txt_score_player, self.txt_score_team])
        
        # 預先建立 5 行 8 列的表格格線與文字
        self.table_rects = []
        self.table_texts = []
        for r in range(5):
            row_rects = []
            row_texts = []
            for c in range(8):
                rect = self.canvas.create_rectangle(0, 0, 0, 0, fill="", outline="", width=2)
                text = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="")
                row_rects.append(rect)
                row_texts.append(text)
                self.score_layout_items.append(rect)
                self.score_layout_items.append(text)
            self.table_rects.append(row_rects)
            self.table_texts.append(row_texts)
            
        # 1. 單輪得分結果版面 (SingleRound) 元件
        self.layout_single_round_items = []
        self.rect_single_acc = self.canvas.create_rectangle(0, 0, 0, 0, fill="#c00000", outline="", width=0)
        self.txt_single_acc = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#ffffff")
        self.rect_single_pres = self.canvas.create_rectangle(0, 0, 0, 0, fill="#00b0f0", outline="", width=0)
        self.txt_single_pres = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#ffffff")
        self.txt_single_final = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#8cd21b")
        self.txt_single_raw_sum = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#ffffff")
        self.layout_single_round_items.extend([
            self.rect_single_acc, self.txt_single_acc,
            self.rect_single_pres, self.txt_single_pres,
            self.txt_single_final, self.txt_single_raw_sum
        ])
        self.score_layout_items.extend(self.layout_single_round_items)
        
        # 2. 雙輪對照總計版面 (DoubleRound) 元件
        self.layout_double_round_items = []
        self.rects_1r = []
        self.texts_1r = []
        self.rects_2r = []
        self.texts_2r = []
        for i in range(4):
            r1 = self.canvas.create_rectangle(0, 0, 0, 0, fill="", outline="#000000", width=2)
            t1 = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="")
            self.rects_1r.append(r1)
            self.texts_1r.append(t1)
            self.layout_double_round_items.extend([r1, t1])
            
            r2 = self.canvas.create_rectangle(0, 0, 0, 0, fill="", outline="#000000", width=2)
            t2 = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="")
            self.rects_2r.append(r2)
            self.texts_2r.append(t2)
            self.layout_double_round_items.extend([r2, t2])
            
        self.txt_double_final = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#8cd21b")
        self.txt_double_pres = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#00b0f0")
        self.txt_double_acc = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#c00000")
        self.layout_double_round_items.extend([self.txt_double_final, self.txt_double_pres, self.txt_double_acc])
        self.score_layout_items.extend(self.layout_double_round_items)
        
        # 3. 總排行榜版面 (Leaderboard) 元件
        self.layout_leaderboard_items = []
        self.rect_leaderboard_title = self.canvas.create_rectangle(0, 0, 0, 0, fill="#151515", outline="#555555", width=2)
        self.txt_leaderboard_title = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#ffffff")
        self.layout_leaderboard_items.extend([self.rect_leaderboard_title, self.txt_leaderboard_title])
        
        self.leaderboard_bg_rects = []
        self.leaderboard_rank_rects = []
        self.leaderboard_rank_texts = []
        self.leaderboard_name_texts = []
        self.leaderboard_team_texts = []
        self.leaderboard_score_texts = []
        for idx in range(8):
            bg = self.canvas.create_rectangle(0, 0, 0, 0, fill="#05143a", outline="#0a225c", width=1)
            rank_rect = self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill="#0056cc", outline="")
            rank_text = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#ffffff")
            name_text = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#ffffff", anchor="w")
            team_text = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#ffff00", anchor="w")
            score_text = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 12, "bold"), fill="#ffff00", anchor="e")
            
            self.leaderboard_bg_rects.append(bg)
            self.leaderboard_rank_rects.append(rank_rect)
            self.leaderboard_rank_texts.append(rank_text)
            self.leaderboard_name_texts.append(name_text)
            self.leaderboard_team_texts.append(team_text)
            self.leaderboard_score_texts.append(score_text)
            
            self.layout_leaderboard_items.extend([bg, rank_rect, rank_text, name_text, team_text, score_text])
        self.score_layout_items.extend(self.layout_leaderboard_items)
        
        # 右側裁判狀態欄背景與 7 個狀態燈
        right_bg = self.draw_gradient_y(Lw, Th, W, H, "#22123a", "#0d051c")
        self.general_bg_items.extend(right_bg)
        
        Jh = (H - Th) / 7
        for i in range(7):
            jx1 = Lw + 8
            jy1 = Th + i * Jh + 6
            jx2 = W - 8
            jy2 = Th + (i + 1) * Jh - 6
            
            rect_id = self.canvas.create_rectangle(
                jx1, jy1, jx2, jy2, 
                fill="#201035", 
                outline="#3b255d", 
                width=2
            )
            text_id = self.canvas.create_text(
                (jx1 + jx2) / 2, (jy1 + jy2) / 2, 
                text=str(i + 1), 
                font=("Microsoft JhengHei", int(Jh * 0.35), "bold"), 
                fill="#ffffff"
            )
            self.judge_rects.append(rect_id)
            self.judge_texts.append(text_id)
            
        # --- 圖層 4: 分隔邊框與線條 (最上層) ---
        # 橫向分隔線
        self.general_bg_items.append(self.canvas.create_line(0, Th, W, Th, fill="#555555", width=2))
        self.normal_layout_items.append(self.canvas.create_line(0, Th + Uh, Lw, Th + Uh, fill="#886611", width=2))
        self.general_bg_items.append(self.canvas.create_line(0, H - Bh, Lw, H - Bh, fill="#555555", width=2))
        
        # 縱向分隔線
        self.general_bg_items.append(self.canvas.create_line(x_top_split, 0, x_top_split, Th, fill="#555555", width=2))
        self.general_bg_items.append(self.canvas.create_line(Lw, Th, Lw, H, fill="#555555", width=2))
        self.general_bg_items.append(self.canvas.create_line(x_bot1, H - Bh, x_bot1, H, fill="#444444", width=2))
        self.general_bg_items.append(self.canvas.create_line(x_bot2, H - Bh, x_bot2, H, fill="#444444", width=2))

    def poomsae_tick(self):
        """品勢語言每 5 秒切換，處理欄位翻譯顯示"""
        if not self.winfo_exists(): return
        self.poomsae_lang_mode = 1 - self.poomsae_lang_mode
        self.refresh()
        self.after(5000, self.poomsae_tick)
        
    def leaderboard_page_tick(self):
        """獨立的排行榜分頁定時器，每 10 秒執行一次翻頁（僅在投影正顯示排行榜畫面時才刷新）"""
        if not self.winfo_exists(): return
        # 只有目前大螢幕實際顯示排行榜（slide 3）時才進行翻頁與查詢，避免無謂的計算
        is_showing_leaderboard = (getattr(self, 'current_score_slide', -1) == 3)
        if is_showing_leaderboard and hasattr(self, 'leaderboard_data_len') and self.leaderboard_data_len > 8:
            total_pages = (self.leaderboard_data_len + 7) // 8
            self.leaderboard_page = (getattr(self, 'leaderboard_page', 0) + 1) % total_pages
            self.refresh()
        self.leaderboard_page_timer_id = self.after(10000, self.leaderboard_page_tick)

    def start_marquee_scroll(self):
        """延遲過後開始讓跑馬燈滾動"""
        if not self.winfo_exists() or not self.is_marquee_active: return
        self.is_marquee_scroll_running = True
        self.marquee_delay_id = None
        self.marquee_tick()

    def start_team_marquee_scroll(self):
        """延遲過後開始讓單位跑馬燈滾動"""
        if not self.winfo_exists() or not getattr(self, 'is_team_marquee_active', False): return
        self.is_team_marquee_scroll_running = True
        self.team_marquee_delay_id = None
        self.team_marquee_tick()

    def marquee_tick(self):
        """組別跑馬燈定時滾動，每 30 毫秒位移，達到流暢滾動"""
        if not self.winfo_exists() or not self.is_marquee_active or not self.is_marquee_scroll_running: return
        
        self.group_scroll_x -= 1.5
        
        # 計算邊界與起點
        W = self.width
        Rw = max(120, int(W * 0.094))
        Lw = W - Rw
        x_top_split = int(Lw * 0.139)
        start_x = x_top_split + 20
        
        # 當位移超過一個單元 (文字長度 + 空格長度) 時，瞬間重置回起點，達到首尾無縫循環
        if self.group_scroll_x <= start_x - self.scroll_threshold_dist:
            self.group_scroll_x = start_x
            
        # 更新文字坐標 (Y 軸置中)
        Th = max(80, int(self.height * 0.155))
        self.canvas.coords(self.txt_group, self.group_scroll_x, Th / 2)
        
        self.after(30, self.marquee_tick)

    def team_marquee_tick(self):
        """單位跑馬燈定時滾動"""
        if not self.winfo_exists() or not getattr(self, 'is_team_marquee_active', False) or not getattr(self, 'is_team_marquee_scroll_running', False): return
        
        self.team_scroll_x -= 1.5
        team_start_x = 40
        
        if self.team_scroll_x <= team_start_x - getattr(self, 'team_scroll_threshold_dist', 0):
            self.team_scroll_x = team_start_x
            
        W = self.width
        H = self.height
        Th = max(80, int(H * 0.155))
        Bh = max(120, int(H * 0.160))
        Uh = int((H - Th - Bh) * 0.214)
        self.canvas.coords(self.txt_team, self.team_scroll_x, Th + Uh / 2)
        
        self.after(30, self.team_marquee_tick)

    def get_judge_status(self, judge_num):
        """取得特定裁判號碼的連線與送分狀態"""
        connected = False
        submitted = False
        for sid, jdata in current_state['judges'].items():
            jid = jdata.get('id', '')
            # 必須符合對應號碼，且必須處於連線狀態 (或是手動產生的 manual 連線)
            if (jid == f"J{judge_num}" or jid == f"manual_J{judge_num}") and (jdata.get('connected', False) or sid.startswith('manual_')):
                connected = True
                if jdata.get('submitted', False):
                    submitted = True
                    break
        return connected, submitted

    def get_available_slides(self, gui):
        """依據總輪數與目前階段判定可用的播放頁面"""
        if not gui: return [0, 1]
        
        total_rounds = 2
        if gui.current_match_data:
            try: total_rounds = int(gui.current_match_data.get("Round", 2))
            except: pass
        if hasattr(gui, 'combo_poomsae_2') and str(gui.combo_poomsae_2['state']) == 'disabled':
            total_rounds = 1
            
        if total_rounds == 1:
            return [0, 1, 2, 3]
        else:
            if gui.current_stage == 1:
                return [0, 1]
            else:
                return [0, 1, 2, 3]

    def stop_leaderboard_flash(self):
        """停止排行榜閃爍"""
        if hasattr(self, 'flash_timer_id') and self.flash_timer_id:
            try: self.after_cancel(self.flash_timer_id)
            except: pass
        self.flash_timer_id = None
        self.flash_row_idx = -1

    def leaderboard_flash_tick(self):
        """排行榜剛完賽選手那行進行閃爍提示"""
        if not self.winfo_exists(): return
        if self.current_score_slide != 3:
            self.stop_leaderboard_flash()
            return
            
        if self.flash_row_idx != -1:
            bg_id = self.leaderboard_bg_rects[self.flash_row_idx]
            self.flash_state = not self.flash_state
            if self.flash_state:
                # 亮狀態：底色亮藍，邊框亮黃
                self.canvas.itemconfigure(bg_id, fill="#122c6e", outline="#ffff00")
            else:
                # 暗狀態：恢復預設暗藍底色與暗藍邊框
                self.canvas.itemconfigure(bg_id, fill="#05143a", outline="#0a225c")
            self.flash_timer_id = self.after(500, self.leaderboard_flash_tick)

    @log_refresh_errors
    def refresh(self):
        """自主 GUI 讀取所有最新狀態並更新投影畫面"""
        if not self.winfo_exists(): return
        
        gui = None
        if hasattr(self, 'main_gui') and self.main_gui:
            gui = self.main_gui
        elif 'gui' in globals() and globals()['gui']:
            gui = globals()['gui']
            
        if not gui:
            return
            
        # 1. 取得選手與賽事基本資料
        match_data = gui.current_match_data
        if match_data:
            no_text = str(match_data.get("No", ""))
            
            parts = []
            for k in ["Category", "Division", "Phase"]:
                val = match_data.get(k, "")
                if val: parts.append(str(val))
            group_text = " - ".join(parts)
            
            team_text = str(match_data.get("C_Team", ""))
            player_text = str(match_data.get("C_Name", ""))
        else:
            no_text = ""
            group_text = ""
            team_text = ""
            player_text = ""
            
        # 計算相關版面高度與寬度以決定姓名區域
        W = self.width
        H = self.height
        Rw = max(120, int(W * 0.094))
        Lw = W - Rw
        Th = max(80, int(H * 0.155))
        Bh = max(120, int(H * 0.160))
        Mh = H - Th - Bh
        Uh = int(Mh * 0.214)
        Nh = Mh - Uh

        self.canvas.itemconfig(self.txt_no, text=no_text)

        # 計算選手姓名動態字型大小，可換行，若高度超出才自動縮小
        max_player_w = Lw - 80
        max_player_h = Nh * 0.8
        base_font_size = int(Nh * 0.22)
        import tkinter.font as tkfont
        
        current_player_font_size = base_font_size
        for size in range(base_font_size, 8, -2):
            f_player = tkfont.Font(family="Microsoft JhengHei", size=size, weight="bold")
            line_height = f_player.metrics("linespace")
            lines = 0
            current_line_w = 0
            for char in player_text:
                char_w = f_player.measure(char)
                if current_line_w + char_w > max_player_w:
                    lines += 1
                    current_line_w = char_w
                else:
                    current_line_w += char_w
            if current_line_w > 0:
                lines += 1
            total_h = lines * line_height
            
            if total_h <= max_player_h:
                current_player_font_size = size
                break
        else:
            current_player_font_size = 8

        self.canvas.itemconfig(self.txt_player, text=player_text, font=("Microsoft JhengHei", current_player_font_size, "bold"))
        
        # 2. 更新組別資訊的跑馬燈與遮罩遮擋邏輯
        W = self.width
        H = self.height
        Rw = max(120, int(W * 0.094))
        Lw = W - Rw
        Th = max(80, int(H * 0.155))
        x_top_split = int(Lw * 0.139)
        Gw = W - x_top_split
        max_w = Gw - 40
        
        import tkinter.font as tkfont
        font_size = int(Th * 0.35)
        f = tkfont.Font(family="Microsoft JhengHei", size=font_size, weight="bold")
        text_width = f.measure(group_text)
        
        text_changed = (group_text != getattr(self, 'current_group_raw_text', None))
        
        if text_changed:
            self.current_group_raw_text = group_text
            if text_width <= max_w:
                # 不需要跑馬燈，置中對齊
                self.is_marquee_active = False
                self.is_marquee_scroll_running = False
                if hasattr(self, 'marquee_delay_id') and self.marquee_delay_id:
                    try: self.after_cancel(self.marquee_delay_id)
                    except: pass
                    self.marquee_delay_id = None
                self.canvas.itemconfig(self.txt_group, text=group_text, anchor="center")
                self.canvas.coords(self.txt_group, x_top_split + Gw / 2, Th / 2)
            else:
                # 需要跑馬燈，首尾無縫拼接
                space_str = " " * 6
                space_width = f.measure(space_str)
                display_text = group_text + space_str + group_text
                
                self.group_text_width = f.measure(display_text)
                self.scroll_threshold_dist = text_width + space_width
                
                start_x = x_top_split + 20
                
                # 1. 停止既有定時器與滾動
                self.is_marquee_active = False
                self.is_marquee_scroll_running = False
                if hasattr(self, 'marquee_delay_id') and self.marquee_delay_id:
                    try: self.after_cancel(self.marquee_delay_id)
                    except: pass
                    self.marquee_delay_id = None
                
                # 2. 先完全呈現首段文字，靠左起點對齊
                self.group_scroll_x = start_x
                self.canvas.itemconfig(self.txt_group, text=display_text, anchor="w")
                self.canvas.coords(self.txt_group, self.group_scroll_x, Th / 2)
                
                # 3. 啟用跑馬燈，設定 1.5 秒後再開始滾動
                self.is_marquee_active = True
                self.marquee_delay_id = self.after(1500, self.start_marquee_scroll)
                
        # 2.5 更新單位 (Team) 的跑馬燈邏輯
        Bh = max(120, int(H * 0.160))
        Mh = H - Th - Bh
        Uh = int(Mh * 0.214)
        f_team = tkfont.Font(family="Microsoft JhengHei", size=int(Uh * 0.38), weight="bold")
        team_text_width = f_team.measure(team_text)
        team_text_changed = (team_text != getattr(self, 'current_team_raw_text', None))
        
        if team_text_changed:
            self.current_team_raw_text = team_text
            if team_text_width <= Lw - 80:
                self.is_team_marquee_active = False
                self.is_team_marquee_scroll_running = False
                if hasattr(self, 'team_marquee_delay_id') and self.team_marquee_delay_id:
                    try: self.after_cancel(self.team_marquee_delay_id)
                    except: pass
                    self.team_marquee_delay_id = None
                self.canvas.itemconfig(self.txt_team, text=team_text, anchor="center")
                self.canvas.coords(self.txt_team, Lw / 2, Th + Uh / 2)
            else:
                space_str = " " * 6
                space_width = f_team.measure(space_str)
                display_text = team_text + space_str + team_text
                
                self.team_scroll_threshold_dist = team_text_width + space_width
                start_x = 40
                
                self.is_team_marquee_active = False
                self.is_team_marquee_scroll_running = False
                if hasattr(self, 'team_marquee_delay_id') and self.team_marquee_delay_id:
                    try: self.after_cancel(self.team_marquee_delay_id)
                    except: pass
                    self.team_marquee_delay_id = None
                
                self.team_scroll_x = start_x
                self.canvas.itemconfig(self.txt_team, text=display_text, anchor="w")
                self.canvas.coords(self.txt_team, self.team_scroll_x, Th + Uh / 2)
                
                self.is_team_marquee_active = True
                self.team_marquee_delay_id = self.after(1500, self.start_team_marquee_scroll)
        
        # 3. 狀態或時間顯示邏輯
        status_display = ""
        current_status_text = getattr(self, 'status_text', '')
        if not match_data:
            status_display = "Waiting..."
        else:
            if current_status_text == "Final Score":
                status_display = "Score"
            elif gui.timer_running or (gui.is_locked and current_status_text != "Waiting..."):
                mins, secs = divmod(gui.timer_seconds, 60)
                status_display = f"{mins:02}:{secs:02}"
            else:
                status_display = current_status_text if current_status_text else match_data.get("Status", "Ready")
        
        self.canvas.itemconfig(self.txt_status, text=status_display)
        
        # 3.5 雙版面與四畫面自動輪播切換邏輯
        is_showing_score = (status_display == "Score")
        
        last_showing = getattr(self, 'last_is_showing_score', False)
        if is_showing_score and not last_showing:
            self.score_slide_show_finished = False
            self.current_score_slide = 0
        self.last_is_showing_score = is_showing_score
        
        if is_showing_score:
            if not self.score_slide_timer_id and not getattr(self, 'score_slide_show_finished', False):
                self.start_score_slide_show()
        else:
            self.stop_score_slide_show()
            self.current_score_slide = 0
            self.stop_leaderboard_flash()
            
            # 確保從排行榜完賽結束退回時，常駐背景、籤號、組別、狀態文字與裁判燈元件皆能恢復顯示
            self.canvas.itemconfigure(self.txt_no, state="normal")
            self.canvas.itemconfigure(self.txt_group, state="normal")
            self.canvas.itemconfigure(self.txt_status, state="normal")
            self.canvas.itemconfigure(self.txt_1r, state="normal")
            self.canvas.itemconfigure(self.txt_2r, state="normal")
            if hasattr(self, 'general_bg_items'):
                for item in self.general_bg_items:
                    self.canvas.itemconfigure(item, state="normal")
            for r_id in self.judge_rects: self.canvas.itemconfigure(r_id, state="normal")
            for t_id in self.judge_texts: self.canvas.itemconfigure(t_id, state="normal")
            
        normal_state = "hidden" if is_showing_score else "normal"
        score_state = "normal" if is_showing_score else "hidden"
        
        if hasattr(self, 'normal_layout_items'):
            for item in self.normal_layout_items:
                self.canvas.itemconfigure(item, state=normal_state)
                
        if hasattr(self, 'score_layout_items'):
            for item in self.score_layout_items:
                self.canvas.itemconfigure(item, state=score_state)
                
        if is_showing_score:
            # 取得 2R 分數以判斷可用的 slide 列表
            # 依據總輪數與當前階段取得可用的播放頁面
            available_slides = self.get_available_slides(gui)
                
            if self.current_score_slide not in available_slides:
                self.current_score_slide = available_slides[0]
                
            is_leaderboard = (self.current_score_slide == 3)
            if not is_leaderboard:
                self.stop_leaderboard_flash()
            
            # 若為排行榜：隱藏右側裁判燈、底部欄與常駐頂部資訊
            general_frame_state = "hidden" if is_leaderboard else "normal"
            self.canvas.itemconfigure(self.txt_no, state=general_frame_state)
            self.canvas.itemconfigure(self.txt_group, state=general_frame_state)
            self.canvas.itemconfigure(self.txt_status, state=general_frame_state)
            self.canvas.itemconfigure(self.txt_1r, state=general_frame_state)
            self.canvas.itemconfigure(self.txt_2r, state=general_frame_state)
            
            # 若為排行榜：隱藏一般畫面的背景漸層與邊框線條
            bg_state = "hidden" if is_leaderboard else "normal"
            if hasattr(self, 'general_bg_items'):
                for item in self.general_bg_items:
                    self.canvas.itemconfigure(item, state=bg_state)
            
            for r_id in self.judge_rects: self.canvas.itemconfigure(r_id, state=general_frame_state)
            for t_id in self.judge_texts: self.canvas.itemconfigure(t_id, state=general_frame_state)
            
            # 先預設隱藏全部子畫面的元件
            for r in range(5):
                for c in range(8):
                    self.canvas.itemconfigure(self.table_rects[r][c], state="hidden")
                    self.canvas.itemconfigure(self.table_texts[r][c], state="hidden")
                    
            for item in self.layout_single_round_items:
                self.canvas.itemconfigure(item, state="hidden")
            for item in self.layout_double_round_items:
                self.canvas.itemconfigure(item, state="hidden")
            for item in self.layout_leaderboard_items:
                self.canvas.itemconfigure(item, state="hidden")
                
            if not is_leaderboard:
                h_name = Mh * 0.14
                score_name_font = tkfont.Font(family="Microsoft JhengHei", size=int(h_name * 0.45), weight="bold")
                max_w = Lw - 40
                
                # 組合成 姓名 單位
                if player_text and team_text:
                    combined_text = f"{player_text} - {team_text}"
                else:
                    combined_text = f"{player_text}{team_text}".strip()
                disp_text = combined_text
                
                if score_name_font.measure(combined_text) > max_w:
                    while len(disp_text) > 0 and score_name_font.measure(disp_text) > max_w:
                        disp_text = disp_text[:-1]
                    self.canvas.itemconfig(self.txt_score_player, text=disp_text, anchor="w")
                    self.canvas.coords(self.txt_score_player, 20, Th + h_name / 2)
                else:
                    self.canvas.itemconfig(self.txt_score_player, text=disp_text, anchor="center")
                    self.canvas.coords(self.txt_score_player, Lw / 2, Th + h_name / 2)
                
                self.canvas.itemconfig(self.txt_score_team, text="")
                self.canvas.itemconfigure(self.txt_score_player, state="normal")
            else:
                self.canvas.itemconfigure(self.txt_score_team, state="hidden")
                self.canvas.itemconfigure(self.txt_score_player, state="hidden")
                
            Th = max(80, int(H * 0.155))
            Bh = max(120, int(H * 0.160))
            Mh = H - Th - Bh
            judge_count = int(system_settings.get("judge_count", 5))
            
            if self.current_score_slide == 0:
                # === 畫面 0：裁判評分詳細大表格 ===
                has_p123 = False
                for jd in current_state['judges'].values():
                    if jd.get('submitted', False) and 'p1' in jd:
                        has_p123 = True
                        break
                        
                if has_p123:
                    row_headers = ["", "Accuracy", "Presentation 1", "Presentation 2", "Presentation 3"]
                    row_keys = [None, "acc", "p1", "p2", "p3"]
                    row_bg_colors = [None, "#c00000", "#00b0f0", "#00b0f0", "#00b0f0"]
                else:
                    row_headers = ["", "Accuracy", "Presentation"]
                    row_keys = [None, "acc", "pres"]
                    row_bg_colors = [None, "#c00000", "#00b0f0"]
                    
                num_rows = len(row_headers)
                h_name = Mh * 0.14
                y_name_bot = Th + h_name
                RowH = (Mh - h_name) / num_rows
                ColW = Lw / 8
                
                row_gray_indices = {}
                for r in range(1, num_rows):
                    key = row_keys[r]
                    valid_scores = []
                    for c in range(1, 8):
                        judge_num = c
                        is_active = (judge_num <= judge_count)
                        
                        jd_found = None
                        manual_key = f"manual_J{judge_num}"
                        if manual_key in current_state['judges'] and current_state['judges'][manual_key].get('submitted', False):
                            jd_found = current_state['judges'][manual_key]
                        if not jd_found:
                            for jd in current_state['judges'].values():
                                if jd.get('id') == f"J{judge_num}" and jd.get('submitted', False):
                                    jd_found = jd
                                    break
                        if not jd_found and manual_key in current_state['judges']:
                            jd_found = current_state['judges'][manual_key]
                        if not jd_found:
                            for jd in current_state['judges'].values():
                                if jd.get('id') == f"J{judge_num}":
                                    jd_found = jd
                                    break
                                
                        if is_active and jd_found and jd_found.get('submitted', False):
                            val = float(jd_found.get(key, 0.0))
                            valid_scores.append((c, val))
                            
                    gray_set = set()
                    if len(valid_scores) > 3:
                        scores_only = [item[1] for item in valid_scores]
                        min_val = min(scores_only)
                        max_val = max(scores_only)
                        
                        min_col = -1
                        max_col = -1
                        for c, val in valid_scores:
                            if val == min_val and min_col == -1:
                                min_col = c
                        for c, val in valid_scores:
                            if val == max_val and max_col == -1 and c != min_col:
                                max_col = c
                        if min_col != -1: gray_set.add(min_col)
                        if max_col != -1: gray_set.add(max_col)
                        
                    row_gray_indices[r] = gray_set
                    
                for r in range(num_rows):
                    for c in range(judge_count + 1):
                        rect_id = self.table_rects[r][c]
                        text_id = self.table_texts[r][c]
                        
                        x1 = c * ColW
                        y1 = y_name_bot + r * RowH
                        x2 = (c + 1) * ColW
                        y2 = y_name_bot + (r + 1) * RowH
                        
                        self.canvas.coords(rect_id, x1, y1, x2, y2)
                        self.canvas.coords(text_id, (x1 + x2) / 2, (y1 + y2) / 2)
                        self.canvas.itemconfigure(rect_id, state="normal")
                        self.canvas.itemconfigure(text_id, state="normal")
                        
                        if r == 0:
                            if c == 0:
                                self.canvas.itemconfigure(rect_id, fill="#ffc000", outline="#000000")
                                self.canvas.itemconfigure(text_id, text="")
                            else:
                                self.canvas.itemconfigure(rect_id, fill="#ffc000", outline="#000000")
                                self.canvas.itemconfigure(text_id, text=f"Judge {c}", fill="#000000", font=("Microsoft JhengHei", int(RowH * 0.20), "bold"))
                        else:
                            if c == 0:
                                self.canvas.itemconfigure(rect_id, fill="#ffc000", outline="#000000")
                                header_text = row_headers[r]
                                font_size = int(RowH * 0.12) if "Presentation" in header_text else int(RowH * 0.18)
                                self.canvas.itemconfigure(text_id, text=header_text, fill="#000000", font=("Microsoft JhengHei", font_size, "bold"))
                            else:
                                judge_num = c
                                jd_found = None
                                manual_key = f"manual_J{judge_num}"
                                if manual_key in current_state['judges'] and current_state['judges'][manual_key].get('submitted', False):
                                    jd_found = current_state['judges'][manual_key]
                                if not jd_found:
                                    for jd in current_state['judges'].values():
                                        if jd.get('id') == f"J{judge_num}" and jd.get('submitted', False):
                                            jd_found = jd
                                            break
                                if not jd_found and manual_key in current_state['judges']:
                                    jd_found = current_state['judges'][manual_key]
                                if not jd_found:
                                    for jd in current_state['judges'].values():
                                        if jd.get('id') == f"J{judge_num}":
                                            jd_found = jd
                                            break
                                        
                                val_str = ""
                                text_color = "#ffffff"
                                
                                if jd_found and jd_found.get('submitted', False):
                                    key = row_keys[r]
                                    val = float(jd_found.get(key, 0.0))
                                    val_str = f"{val:.1f}"
                                    if c in row_gray_indices.get(r, set()):
                                        text_color = "#7f7f7f"
                                else:
                                    if jd_found:
                                        key = row_keys[r]
                                        val = float(jd_found.get(key, 0.0))
                                        val_str = f"{val:.1f}"
                                    text_color = "#7f7f7f"
                                    
                                self.canvas.itemconfigure(rect_id, fill=row_bg_colors[r], outline="#000000")
                                self.canvas.itemconfigure(text_id, text=val_str, fill=text_color, font=("Microsoft JhengHei", int(RowH * 0.45), "bold"))
                                
            elif self.current_score_slide == 1:
                # === 畫面 1：單輪得分結果 ===
                for item in self.layout_single_round_items:
                    self.canvas.itemconfigure(item, state="normal")
                    
                col_idx = 0 if gui.current_stage == 1 else 1
                acc_val = gui.left_labels[0][col_idx].cget("text") if hasattr(gui, 'left_labels') else "0.00"
                pres_val = gui.left_labels[1][col_idx].cget("text") if hasattr(gui, 'left_labels') else "0.00"
                final_val = gui.left_labels[3][col_idx].cget("text") if hasattr(gui, 'left_labels') else "0.00"
                raw_sum_val = f"{gui.score_1r_raw:.1f}" if gui.current_stage == 1 else f"{gui.score_2r_raw:.1f}"
                
                # 將單輪結果中的 Accuracy、Presentation、Final 格式化為三位小數（滿分10分時顯示兩位）
                try: acc_val_3f = format_pk_score(acc_val)
                except: acc_val_3f = acc_val
                try: pres_val_3f = format_pk_score(pres_val)
                except: pres_val_3f = pres_val
                try: final_val_3f = format_pk_score(final_val)
                except: final_val_3f = final_val
                
                h_name = Mh * 0.14
                y_name_bot = Th + h_name
                RectW = Lw * 0.21
                RectH = Mh * 0.22
                
                # Accuracy 框
                x1_acc = Lw * 0.03
                y1_acc = y_name_bot + Mh * 0.33
                self.canvas.coords(self.rect_single_acc, x1_acc, y1_acc, x1_acc + RectW, y1_acc + RectH)
                self.canvas.coords(self.txt_single_acc, x1_acc + RectW/2, y1_acc + RectH/2)
                self.canvas.itemconfig(self.txt_single_acc, text=acc_val_3f, font=("Microsoft JhengHei", int(RectH * 0.5), "bold"))
                
                # Presentation 框
                x1_pres = Lw * 0.27
                y1_pres = y_name_bot + Mh * 0.33
                self.canvas.coords(self.rect_single_pres, x1_pres, y1_pres, x1_pres + RectW, y1_pres + RectH)
                self.canvas.coords(self.txt_single_pres, x1_pres + RectW/2, y1_pres + RectH/2)
                self.canvas.itemconfig(self.txt_single_pres, text=pres_val_3f, font=("Microsoft JhengHei", int(RectH * 0.5), "bold"))
                
                # 右側大最終得分字
                self.canvas.coords(self.txt_single_final, Lw * 0.75, y_name_bot + Mh * 0.33)
                self.canvas.itemconfig(self.txt_single_final, text=final_val_3f, font=("Microsoft JhengHei", int(Mh * 0.21), "bold"))
                
                # 右側大原始總分字 (保持原樣，顯示 1 位小數的 raw_sum_val)
                self.canvas.coords(self.txt_single_raw_sum, Lw * 0.75, y_name_bot + Mh * 0.65)
                self.canvas.itemconfig(self.txt_single_raw_sum, text=raw_sum_val, font=("Microsoft JhengHei", int(Mh * 0.16), "bold"))
                
            elif self.current_score_slide == 2:
                # === 畫面 2：雙輪對照與總計 ===
                for item in self.layout_double_round_items:
                    self.canvas.itemconfigure(item, state="normal")
                    
                r1_acc = gui.left_labels[0][0].cget("text") if hasattr(gui, 'left_labels') else ""
                r1_pres = gui.left_labels[1][0].cget("text") if hasattr(gui, 'left_labels') else ""
                r1_total = gui.left_labels[3][0].cget("text") if hasattr(gui, 'left_labels') else ""
                
                r2_acc = gui.left_labels[0][1].cget("text") if hasattr(gui, 'left_labels') else ""
                r2_pres = gui.left_labels[1][1].cget("text") if hasattr(gui, 'left_labels') else ""
                r2_total = gui.left_labels[3][1].cget("text") if hasattr(gui, 'left_labels') else ""
                
                total_avg = gui.left_merged_labels[4].cget("text") if hasattr(gui, 'left_merged_labels') else ""
                
                # 建立三位小數格式化輔助函式
                def to_3f(val_str):
                    if not val_str or val_str in ["", "-"]:
                        return ""
                    try: return format_pk_score(val_str)
                    except: return val_str
                
                r1_acc_3f = to_3f(r1_acc)
                r1_pres_3f = to_3f(r1_pres)
                r1_total_3f = to_3f(r1_total)
                
                r2_acc_3f = to_3f(r2_acc)
                r2_pres_3f = to_3f(r2_pres)
                r2_total_3f = to_3f(r2_total)
                
                total_avg_3f = to_3f(total_avg)
                
                try:
                    total_pres_3f = format_pk_score((float(r1_pres) + float(r2_pres))/2) if (r1_pres and r2_pres) else ""
                    total_acc_3f = format_pk_score((float(r1_acc) + float(r2_acc))/2) if (r1_acc and r2_acc) else ""
                except:
                    total_pres_3f = ""
                    total_acc_3f = ""
                    
                # 依據是否有 2R 分數決定右側大字顯示雙輪平均或僅顯示 1R 分數
                has_2r_score = (r2_total not in ["", "-", "0.00", "0.000"])
                if has_2r_score:
                    disp_final = total_avg_3f
                    disp_pres = total_pres_3f
                    disp_acc = total_acc_3f
                else:
                    disp_final = r1_total_3f
                    disp_pres = r1_pres_3f
                    disp_acc = r1_acc_3f
                    
                h_name = Mh * 0.14
                y_name_bot = Th + h_name
                ColW = Lw * 0.19
                RowH = Mh * 0.16
                
                x_1r = Lw * 0.06
                for idx in range(4):
                    y1 = y_name_bot + Mh * 0.08 + idx * RowH
                    y2 = y1 + RowH
                    self.canvas.coords(self.rects_1r[idx], x_1r, y1, x_1r + ColW, y2)
                    self.canvas.coords(self.texts_1r[idx], x_1r + ColW/2, (y1 + y2)/2)
                    
                    if idx == 0:
                        self.canvas.itemconfigure(self.rects_1r[idx], fill="#ffc000")
                        self.canvas.itemconfigure(self.texts_1r[idx], text="1", fill="#000000", font=("Microsoft JhengHei", int(RowH * 0.40), "bold"))
                    elif idx == 1:
                        self.canvas.itemconfigure(self.rects_1r[idx], fill="#252525")
                        self.canvas.itemconfigure(self.texts_1r[idx], text=r1_total_3f, fill="#8cd21b", font=("Microsoft JhengHei", int(RowH * 0.42), "bold"))
                    elif idx == 2:
                        self.canvas.itemconfigure(self.rects_1r[idx], fill="#252525")
                        self.canvas.itemconfigure(self.texts_1r[idx], text=r1_pres_3f, fill="#00b0f0", font=("Microsoft JhengHei", int(RowH * 0.42), "bold"))
                    elif idx == 3:
                        self.canvas.itemconfigure(self.rects_1r[idx], fill="#252525")
                        self.canvas.itemconfigure(self.texts_1r[idx], text=r1_acc_3f, fill="#c00000", font=("Microsoft JhengHei", int(RowH * 0.42), "bold"))
                        
                x_2r = Lw * 0.26
                for idx in range(4):
                    y1 = y_name_bot + Mh * 0.08 + idx * RowH
                    y2 = y1 + RowH
                    self.canvas.coords(self.rects_2r[idx], x_2r, y1, x_2r + ColW, y2)
                    self.canvas.coords(self.texts_2r[idx], x_2r + ColW/2, (y1 + y2)/2)
                    
                    if idx == 0:
                        self.canvas.itemconfigure(self.rects_2r[idx], fill="#ffc000")
                        self.canvas.itemconfigure(self.texts_2r[idx], text="2", fill="#000000", font=("Microsoft JhengHei", int(RowH * 0.40), "bold"))
                    elif idx == 1:
                        self.canvas.itemconfigure(self.rects_2r[idx], fill="#252525")
                        self.canvas.itemconfigure(self.texts_2r[idx], text=r2_total_3f, fill="#8cd21b", font=("Microsoft JhengHei", int(RowH * 0.42), "bold"))
                    elif idx == 2:
                        self.canvas.itemconfigure(self.rects_2r[idx], fill="#252525")
                        self.canvas.itemconfigure(self.texts_2r[idx], text=r2_pres_3f, fill="#00b0f0", font=("Microsoft JhengHei", int(RowH * 0.42), "bold"))
                    elif idx == 3:
                        self.canvas.itemconfigure(self.rects_2r[idx], fill="#252525")
                        self.canvas.itemconfigure(self.texts_2r[idx], text=r2_acc_3f, fill="#c00000", font=("Microsoft JhengHei", int(RowH * 0.42), "bold"))
                        
                self.canvas.coords(self.txt_double_final, Lw * 0.70, y_name_bot + Mh * 0.17)
                self.canvas.itemconfig(self.txt_double_final, text=disp_final, font=("Microsoft JhengHei", int(Mh * 0.20), "bold"))
                
                self.canvas.coords(self.txt_double_pres, Lw * 0.70, y_name_bot + Mh * 0.43)
                self.canvas.itemconfig(self.txt_double_pres, text=disp_pres, font=("Microsoft JhengHei", int(Mh * 0.14), "bold"))
                
                self.canvas.coords(self.txt_double_acc, Lw * 0.70, y_name_bot + Mh * 0.68)
                self.canvas.itemconfig(self.txt_double_acc, text=disp_acc, font=("Microsoft JhengHei", int(Mh * 0.14), "bold"))
                
            elif self.current_score_slide == 3:
                # === 畫面 3：總排行榜 ===
                for item in self.layout_leaderboard_items:
                    self.canvas.itemconfigure(item, state="normal")
                    
                self.canvas.coords(self.rect_leaderboard_title, 0, 0, W, Th)
                self.canvas.coords(self.txt_leaderboard_title, W / 2, Th / 2)
                
                leaderboard_title = " / ".join([str(match_data.get(k, "")) for k in ["Category", "Division", "Phase"] if match_data.get(k, "")])
                self.canvas.itemconfig(self.txt_leaderboard_title, text=leaderboard_title, font=("Microsoft JhengHei", int(Th * 0.35), "bold"))
                
                leaderboard = self.query_leaderboard_data()
                self.leaderboard_data_len = len(leaderboard)
                
                # 分頁計算
                current_page = getattr(self, 'leaderboard_page', 0)
                total_pages = (len(leaderboard) + 7) // 8 if len(leaderboard) > 0 else 1
                if current_page >= total_pages:
                    current_page = 0
                    self.leaderboard_page = 0
                
                start_idx = current_page * 8
                
                # 【借位滿版邏輯】如果這頁顯示的數量不夠 8 筆，且總人數超過 8 人，則往前借位
                if len(leaderboard) > 8 and start_idx + 8 > len(leaderboard):
                    start_idx = len(leaderboard) - 8
                
                # 找出剛完賽選手在排行榜哪一頁
                current_player_name = gui.current_match_data.get("C_Name", "") if gui.current_match_data else ""
                self.flash_row_idx = -1
                for idx, player in enumerate(leaderboard):
                    if player["name"] == current_player_name:
                        player_page = idx // 8
                        # 若尚未閃爍過，強制將頁面切換至該選手所在頁
                        if not self.flash_timer_id and not self.flash_state:
                            self.leaderboard_page = player_page
                            current_page = player_page
                            start_idx = current_page * 8
                            if len(leaderboard) > 8 and start_idx + 8 > len(leaderboard):
                                start_idx = len(leaderboard) - 8
                            
                            # 完賽第一時間聚焦時，重置 10 秒翻頁計時器
                            if hasattr(self, 'leaderboard_page_timer_id') and self.leaderboard_page_timer_id:
                                self.after_cancel(self.leaderboard_page_timer_id)
                            self.leaderboard_page_timer_id = self.after(10000, self.leaderboard_page_tick)
                        
                        # 若選手在目前這頁的顯示範圍內，設定閃爍索引
                        if start_idx <= idx < start_idx + 8:
                            self.flash_row_idx = idx - start_idx
                        break
                        
                RowH = (H - Th - 20) / 8
                for idx in range(8):
                    bg_id = self.leaderboard_bg_rects[idx]
                    rank_rect_id = self.leaderboard_rank_rects[idx]
                    rank_text_id = self.leaderboard_rank_texts[idx]
                    name_text_id = self.leaderboard_name_texts[idx]
                    team_text_id = self.leaderboard_team_texts[idx]
                    score_text_id = self.leaderboard_score_texts[idx]
                    
                    # 無論有無資料，都為背景橫條與斜切名次框定位並顯示，以維持畫面精美的表格外觀
                    y1 = Th + idx * RowH + 4
                    y2 = Th + (idx + 1) * RowH - 4
                    
                    # 左右用滿空間：x1由0.01改為0，x2由0.99改為W
                    self.canvas.coords(bg_id, 0, y1, W, y2)
                    
                    # 重新計算斜切名次框以配合完全佔滿的邊界
                    px1 = 0
                    py1 = y1
                    px2 = W * 0.08
                    py2 = y1
                    px3 = W * 0.06
                    py3 = y2
                    px4 = 0
                    py4 = y2
                    self.canvas.coords(rank_rect_id, px1, py1, px2, py2, px3, py3, px4, py4)
                    
                    self.canvas.coords(rank_text_id, (0 + W * 0.07) / 2, (y1 + y2) / 2)
                    self.canvas.coords(name_text_id, W * 0.10, (y1 + y2) / 2)
                    self.canvas.coords(team_text_id, W * 0.43, (y1 + y2) / 2)
                    self.canvas.coords(score_text_id, W * 0.985, (y1 + y2) / 2)
                    
                    self.canvas.itemconfigure(bg_id, state="normal")
                    self.canvas.itemconfigure(rank_rect_id, state="normal")
                    
                    # 初始化該行的背景色：若是閃爍行，根據目前閃爍狀態著色；否則設為預設暗色
                    if idx == self.flash_row_idx:
                        if getattr(self, 'flash_state', False):
                            self.canvas.itemconfigure(bg_id, fill="#122c6e", outline="#ffff00")
                        else:
                            self.canvas.itemconfigure(bg_id, fill="#05143a", outline="#0a225c")
                    else:
                        self.canvas.itemconfigure(bg_id, fill="#05143a", outline="#0a225c")
                    
                    data_idx = start_idx + idx
                    if data_idx < len(leaderboard):
                        player = leaderboard[data_idx]
                        
                        # 決定字體顏色：剛完賽的選手為黃色，其他人為白色
                        text_color = "#ffff00" if idx == self.flash_row_idx else "#ffffff"
                        
                        rank_str = str(player.get("rank", data_idx + 1))
                        score_str = format_pk_score(player['score'])
                        if player.get('name') and player.get('team'):
                            combined_text = f"{player['name']} - {player['team']}"
                        else:
                            combined_text = f"{player.get('name', '')}{player.get('team', '')}".strip()
                        
                        name_font = tkfont.Font(family="Microsoft JhengHei", size=int(RowH * 0.40), weight="bold")
                        score_font = tkfont.Font(family="Microsoft JhengHei", size=int(RowH * 0.45), weight="bold")
                        score_width = score_font.measure(score_str)
                        
                        max_name_w = (W * 0.985) - score_width - (W * 0.10) - 40 # 40 for padding between name and score
                        
                        disp_text = combined_text
                        if name_font.measure(disp_text) > max_name_w:
                            while len(disp_text) > 0 and name_font.measure(disp_text) > max_name_w:
                                disp_text = disp_text[:-1]
                                
                        self.canvas.itemconfig(rank_text_id, text=rank_str, font=("Microsoft JhengHei", int(RowH * 0.40), "bold"), fill=text_color)
                        self.canvas.itemconfig(name_text_id, text=disp_text, font=name_font, fill=text_color)
                        self.canvas.itemconfig(team_text_id, text="", font=("Microsoft JhengHei", int(RowH * 0.35), "bold"), fill=text_color)
                        self.canvas.itemconfig(score_text_id, text=score_str, font=score_font, fill=text_color)
                        
                        self.canvas.itemconfigure(rank_text_id, state="normal")
                        self.canvas.itemconfigure(name_text_id, state="normal")
                        self.canvas.itemconfigure(team_text_id, state="hidden")
                        self.canvas.itemconfigure(score_text_id, state="normal")
                    else:
                        # 沒有資料的空行：僅隱藏文字元件，保留背景橫條與名次框
                        self.canvas.itemconfigure(rank_text_id, state="hidden")
                        self.canvas.itemconfigure(name_text_id, state="hidden")
                        self.canvas.itemconfigure(team_text_id, state="hidden")
                        self.canvas.itemconfigure(score_text_id, state="hidden")
                
                # 啟動閃爍定時器
                if self.flash_row_idx != -1 and not self.flash_timer_id:
                    self.flash_state = False
                    self.leaderboard_flash_tick()
        
        # 4. 1R 與 2R 品勢中英文顯示邏輯
        p1_full = gui.combo_poomsae_1.get() if hasattr(gui, 'combo_poomsae_1') else ""
        p2_full = gui.combo_poomsae_2.get() if hasattr(gui, 'combo_poomsae_2') else ""
        
        is_2r_active = True
        if hasattr(gui, 'combo_poomsae_2'):
            if str(gui.combo_poomsae_2['state']) == 'disabled':
                is_2r_active = False
        
        def get_display_name(poomsae_str):
            if not poomsae_str: return ""
            p_parts = poomsae_str.split(' ', 1)
            if len(p_parts) == 2:
                return p_parts[self.poomsae_lang_mode]
            return poomsae_str
            
        p1_display = get_display_name(p1_full)
        p2_display = get_display_name(p2_full) if is_2r_active else ""
        
        self.canvas.itemconfig(self.txt_1r, text=p1_display)
        self.canvas.itemconfig(self.txt_2r, text=p2_display)
        
        # 5. 更新裁判狀態燈
        judge_count = int(system_settings.get("judge_count", 5))
        for i in range(7):
            judge_num = i + 1
            rect_id = self.judge_rects[i]
            text_id = self.judge_texts[i]
            
            if judge_num <= judge_count:
                connected, submitted = self.get_judge_status(judge_num)
                if not connected:
                    fill_color = "#201035"
                    text_color = "#ffffff"
                    outline_color = "#3b255d"
                else:
                    if not submitted:
                        fill_color = "#201035"
                        text_color = "#39ff14"  # 亮螢光綠
                        outline_color = "#3b255d"  # 邊框不變為綠色，與未連線相同（不需要有綠色）
                    else:
                        # 裁判已送分：底色變為黃色，數字變為深綠色
                        fill_color = "#ffff00"
                        text_color = "#006600"
                        outline_color = "#cccc00"
                self.canvas.itemconfig(rect_id, fill=fill_color, outline=outline_color)
                self.canvas.itemconfig(text_id, text=str(judge_num), fill=text_color)
            else:
                # 未啟用之裁判格：清空數字並重設回暗色未啟用狀態
                self.canvas.itemconfig(rect_id, fill="#201035", outline="#3b255d")
                self.canvas.itemconfig(text_id, text="", fill="#ffffff")

    def on_resize(self, event):
        """當視窗大小改變時重繪漸層背景並更新文字位置"""
        if event.width != self.width or event.height != self.height:
            self.width = event.width
            self.height = event.height
            self.draw_background()
            self.refresh()

    def update_data(self, info_text="", player_text="", team_text="", score_text="-"):
        """相容舊的 update_data 呼召，直接導向 refresh"""
        if self.current_score_slide != 0 and info_text not in ["", "score_slide_show"]:
            self.stop_score_slide_show()
        self.status_text = info_text
        self.refresh()

    def query_leaderboard_data(self):
        """從資料庫與快取中載入並計算目前組別所有完賽選手的排行榜資料"""
        gui = self.main_gui if (hasattr(self, 'main_gui') and self.main_gui) else globals().get('gui')
        if gui:
            data = gui.query_leaderboard_data()
            try:
                with open("debug_scores.log", "a", encoding="utf-8") as f:
                    f.write("--- projection leaderboard query ---\n")
                    for item in data:
                        f.write(f"  Player: {item.get('name')}, Rank: {item.get('rank')}, Score: {item.get('score')}, Pres: {item.get('presentation_score')}, Raw: {item.get('raw_total_score')}\n")
            except Exception as e:
                pass
            return data
        return []

    def get_final_score(self, gui, uid, mdata):
        """獲取已完賽選手的最終得分，直接委託主 GUI 的 get_final_score"""
        if gui:
            return gui.get_final_score(uid, mdata)
        return 0.0

    def emit_slide_changed(self):
        try:
            import web_server
            ld_data = self.query_leaderboard_data() if self.current_score_slide == 3 else []
            gui = self.main_gui if (hasattr(self, 'main_gui') and self.main_gui) else globals().get('gui')
            ld_title = ""
            if gui and gui.current_match_data:
                ld_title = " / ".join([str(gui.current_match_data.get(k, "")) for k in ["Category", "Division", "Phase"] if gui.current_match_data.get(k, "")])
                
            flash_idx = getattr(self, 'flash_row_idx', -1)
            slide_data = {
                'slide': self.current_score_slide,
                'leaderboard': ld_data,
                'leaderboard_title': ld_title,
                'flash_row_idx': flash_idx
            }
            current_state['projection_slide_data'] = slide_data
            web_server.socketio.emit('projection_slide_changed', slide_data, namespace='/')
        except Exception as e:
            print(f"Failed to emit projection_slide_changed: {e}")

    def start_score_slide_show(self):
        self.stop_score_slide_show()
        self.emit_slide_changed()
        duration = int(system_settings.get("slide_duration", 3)) * 1000
        self.score_slide_timer_id = self.after(duration, self.next_score_slide)
        
    def stop_score_slide_show(self):
        if hasattr(self, 'score_slide_timer_id') and self.score_slide_timer_id:
            try: self.after_cancel(self.score_slide_timer_id)
            except: pass
        self.score_slide_timer_id = None
        self.current_score_slide = 0
        self.emit_slide_changed()
        
    def next_score_slide(self):
        if not self.winfo_exists(): return
        gui = self.main_gui if (hasattr(self, 'main_gui') and self.main_gui) else globals().get('gui')
        if not gui: return
        
        available_slides = self.get_available_slides(gui)
            
        try:
            curr_idx = available_slides.index(self.current_score_slide)
            next_idx = (curr_idx + 1) % len(available_slides)
            self.current_score_slide = available_slides[next_idx]
        except:
            self.current_score_slide = available_slides[0]
            
        self.refresh()
        self.emit_slide_changed()
        
        if gui:
            gui.last_proj_score_slide = self.current_score_slide
            gui.last_proj_slide_finished = False
        
        # 如果播到可用 slide 列表的最後一個，停止輪播
        if self.current_score_slide == available_slides[-1]:
            # 這已經是最後一張投影片（例如：單輪得分結果頁或總排行榜）。
            # 為了等它播放完指定秒數，在此處再等待一次 duration 後，才設定播放完成並更新按鈕。
            duration = int(system_settings.get("slide_duration", 3)) * 1000
            def finish_slide_show():
                if not self.winfo_exists(): return
                self.score_slide_timer_id = None
                self.score_slide_show_finished = True
                if gui:
                    gui.last_proj_slide_finished = True
                    gui.update_button_states()
            self.score_slide_timer_id = self.after(duration, finish_slide_show)
        else:
            duration = int(system_settings.get("slide_duration", 3)) * 1000
            self.score_slide_timer_id = self.after(duration, self.next_score_slide)


# --- 主 UI 類別 ---
class PoomsaeReplicaGUI:
    instance = None
    def query_leaderboard_data(self):
        """從資料庫與快取中載入並計算目前組別所有完賽選手的排行榜資料，支援並列名次"""
        if not self.current_match_data: return []
        
        current_cat = self.current_match_data.get("Category", "")
        current_div = self.current_match_data.get("Division", "")
        current_phase = self.current_match_data.get("Phase", "")
        
        # 篩選同組完賽選手
        try:
            rounds = int(self.current_match_data.get("Round", 2))
        except:
            rounds = 2

        group_players = []
        for uid, mdata in self.imported_matches.items():
            if (mdata.get("Category") == current_cat and 
                mdata.get("Division") == current_div and 
                mdata.get("Phase") == current_phase):
                
                if mdata.get("Status") == "End":
                    group_players.append((uid, mdata))
                elif uid == self.current_match_uuid:
                    # 當前選手：必須確認已經完成該賽事要求的總輪數，才可列入大螢幕排行榜
                    if rounds == 1:
                        score_1r_text = self.left_labels[3][0].cget("text") if hasattr(self, 'left_labels') else ""
                        has_1r_score = (score_1r_text not in ["", "-"])
                        if has_1r_score:
                            group_players.append((uid, mdata))
                    else:
                        score_2r_text = self.left_labels[3][1].cget("text") if hasattr(self, 'left_labels') else ""
                        has_2r_score = (score_2r_text not in ["", "-"])
                        if self.current_stage == 2 and has_2r_score:
                            group_players.append((uid, mdata))
                
        leaderboard = []
        for uid, mdata in group_players:
            score_val = self.get_final_score(uid, mdata)
            if score_val >= 0:
                leaderboard.append({
                    "name": mdata.get("C_Name", ""),
                    "team": mdata.get("C_Team", ""),
                    "score": score_val,
                    "presentation_score": mdata.get("presentation_score", 0.0),
                    "raw_total_score": mdata.get("raw_total_score", 0.0)
                })
        # 依據規則排序：最終得分(Avg) -> 技術分(P) -> 原始總加總分(Tot)
        leaderboard.sort(key=lambda x: (round(x["score"], 3), round(x["presentation_score"], 3), x["raw_total_score"]), reverse=True)
        
        # 計算並列名次：只有三項分數皆相同時才算並列
        # 使用畫面顯示的三位小數判定同分，避免隱藏小數先決定名次
        def scores_eq(a, b):
            return round(a, 3) == round(b, 3)
        
        for idx, item in enumerate(leaderboard):
            if idx > 0 and (
                scores_eq(item["score"], leaderboard[idx - 1]["score"]) and
                scores_eq(item["presentation_score"], leaderboard[idx - 1]["presentation_score"]) and
                scores_eq(item["raw_total_score"], leaderboard[idx - 1]["raw_total_score"])
            ):
                item["rank"] = leaderboard[idx - 1]["rank"]
            else:
                item["rank"] = idx + 1
        return leaderboard

