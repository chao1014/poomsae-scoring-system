import tkinter as tk
import os
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
                err_f.write(f"--- PK REFRESH ERROR AT {datetime.now()} ---\n")
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

class PKProjectionWindow(tk.Toplevel):
    def __init__(self, master, x=0, y=0, width=1920, height=1080):
        super().__init__(master)
        self.title("PK Score Projection")
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
        
        self.status_text = ""
        self.current_score_slide = 0
        self.score_slide_show_finished = False
        self.last_is_showing_score = False
        self.score_slide_timer_id = None
        self.active_match_uuid = None
        self._blink_on = True
        self._blink_timer_id = None
        
        self.judge_rects = []
        self.judge_texts = []
        
        # 青紅兩方的單位跑馬燈狀態與定時器 ID 初始化
        self.is_chung_team_marquee_active = False
        self.is_chung_team_marquee_scroll_running = False
        self.chung_team_marquee_delay_id = None
        
        self.is_hong_team_marquee_active = False
        self.is_hong_team_marquee_scroll_running = False
        self.hong_team_marquee_delay_id = None
        
        self.draw_background()
        
        self.bind("<Configure>", self.on_resize)
        
        self.refresh()
        self.update()

    def hex_to_rgb(self, hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])
        return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)

    def draw_gradient_y_on_canvas(self, canvas, x1, y1, x2, y2, color1, color2):
        ids = []
        r1, g1, b1 = self.hex_to_rgb(color1)
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

    def draw_background(self):
        self.canvas.delete("all")
        W = self.width
        H = self.height
        
        Th = max(80, int(H * 0.155))  # Top bar height
        Bh = max(120, int(H * 0.160)) # Bottom bar height
        Mh = H - Th - Bh              # Middle area height
        
        # 裁判區塊在中間
        Jw = max(120, int(W * 0.08))  # Judge column width
        Lw = int((W - Jw) / 2)        # Left width (Chung)
        Rw = W - Lw - Jw              # Right width (Hong)
        
        self.general_bg_items = []
        
        # --- 左側 (青方) 漸層 ---
        bg_chung = self.draw_gradient_y_on_canvas(self.canvas, 0, Th, Lw, H - Bh, "#0f2b5a", "#051124")
        
        # --- 右側 (紅方) 漸層 ---
        bg_hong = self.draw_gradient_y_on_canvas(self.canvas, Lw + Jw, Th, W, H - Bh, "#5a0f18", "#240509")
        
        # --- 中間 (裁判) 漸層 ---
        bg_judge = self.draw_gradient_y_on_canvas(self.canvas, Lw, Th, Lw + Jw, H - Bh, "#1a1a1a", "#050505")
        
        self.general_bg_items.extend(bg_chung + bg_hong + bg_judge)
        
        # 中間裁判燈 (1~7)
        Jh = Mh / 7
        self.judge_rects = []
        self.judge_texts = []
        for i in range(7):
            jx1 = Lw + 8
            jy1 = Th + i * Jh + 6
            jx2 = Lw + Jw - 8
            jy2 = Th + (i + 1) * Jh - 6
            
            rect_id = self.canvas.create_rectangle(
                jx1, jy1, jx2, jy2, 
                fill="#202020", outline="#444444", width=2
            )
            text_id = self.canvas.create_text(
                (jx1 + jx2) / 2, (jy1 + jy2) / 2, 
                text=str(i + 1), 
                font=("Microsoft JhengHei", int(Jh * 0.35), "bold"), 
                fill="#ffffff"
            )
            self.judge_rects.append(rect_id)
            self.judge_texts.append(text_id)
            
        # --- 頂部區塊 ---
        x_top_split = int(W * 0.139)
        bg_top1 = self.draw_gradient_y_on_canvas(self.canvas, 0, 0, x_top_split, Th, "#242424", "#0a0a0a")
        bg_top2 = self.draw_gradient_y_on_canvas(self.canvas, x_top_split, 0, W, Th, "#3a3a3a", "#151515")
        self.general_bg_items.extend(bg_top1 + bg_top2)
        
        self.txt_no = self.canvas.create_text(
            x_top_split / 2, Th / 2, text="", 
            font=("Microsoft JhengHei", int(Th * 0.35), "bold"), fill="#ffffff", justify="center"
        )
        self.txt_group = self.canvas.create_text(
            x_top_split + (W - x_top_split) / 2, Th / 2, text="", 
            font=("Microsoft JhengHei", int(Th * 0.35), "bold"), fill="#ffffff", anchor="center"
        )
        
        # --- 底部區塊 (占滿整行) ---
        x_bot1 = int(W * 0.333)
        x_bot2 = int(W * 0.666)
        
        # 1. 繪製三格背景
        self.bot_three_bg = []
        bg1 = self.draw_gradient_y_on_canvas(self.canvas, 0, H - Bh, x_bot1, H, "#252525", "#0c0c0c")
        bg2 = self.draw_gradient_y_on_canvas(self.canvas, x_bot1, H - Bh, x_bot2, H, "#252525", "#0c0c0c")
        bg3 = self.draw_gradient_y_on_canvas(self.canvas, x_bot2, H - Bh, W, H, "#252525", "#0c0c0c")
        self.bot_three_bg.extend(bg1 + bg2 + bg3)
        
        # 三格文字
        self.txt_status = self.canvas.create_text(
            x_bot1 / 2, H - Bh / 2, text="Waiting...", 
            font=("Microsoft JhengHei", int(Bh * 0.33), "bold"), fill="#ffff00", justify="center"
        )
        self.txt_1r = self.canvas.create_text(
            x_bot1 + (x_bot2 - x_bot1) / 2, H - Bh / 2, text="", 
            font=("Microsoft JhengHei", int(Bh * 0.28), "bold"), fill="#ffffff", justify="center"
        )
        self.txt_2r = self.canvas.create_text(
            x_bot2 + (W - x_bot2) / 2, H - Bh / 2, text="", 
            font=("Microsoft JhengHei", int(Bh * 0.28), "bold"), fill="#ffffff", justify="center"
        )
        
        # 2. 繪製兩格背景 (Slide 2 得分對照頁)
        self.bot_two_bg = []
        bg_two1 = self.draw_gradient_y_on_canvas(self.canvas, 0, H - Bh, W / 2, H, "#202020", "#080808")
        bg_two2 = self.draw_gradient_y_on_canvas(self.canvas, W / 2, H - Bh, W, H, "#202020", "#080808")
        self.bot_two_bg.extend(bg_two1 + bg_two2)
        
        # 繪製與建立兩側 2 x 4 表格 (1R 與 2R 的 Acc, Pres, Final 明細)
        tb_w = int(Lw * 0.96)  # 表格寬度 (放大)
        tb_h = int(Bh * 0.90)  # 表格高度 (放大)
        
        y_tb_start = H - Bh + int((Bh - tb_h) / 2)
        
        x_tb_start_chung = int((Lw - tb_w) / 2)
        x_tb_start_hong = Lw + Jw + int((Rw - tb_w) / 2)
        
        col_ratios = [0.12, 0.293, 0.293, 0.294]
        
        self.chung_bot_table_rects = []
        self.chung_bot_table_texts = []
        self.hong_bot_table_rects = []
        self.hong_bot_table_texts = []
        
        for r in range(2):
            chung_row_rects = []
            chung_row_texts = []
            hong_row_rects = []
            hong_row_texts = []
            
            y1 = y_tb_start + r * (tb_h / 2)
            y2 = y_tb_start + (r + 1) * (tb_h / 2)
            
            # 青方明細表
            curr_x = x_tb_start_chung
            for col in range(4):
                w = tb_w * col_ratios[col]
                x1 = curr_x
                x2 = curr_x + w
                curr_x = x2
                
                bg_color = "#f1c40f" if col == 0 else "#101010"
                rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill=bg_color, outline="#888888", width=4, state="hidden")
                
                text_val = str(r + 1) if col == 0 else ""
                text_color = "#000000" if col == 0 else "#ffffff"
                text = self.canvas.create_text(
                    (x1 + x2)/2, (y1 + y2)/2, text=text_val, 
                    font=("Microsoft JhengHei", int((tb_h/2) * 0.50), "bold"), 
                    fill=text_color, state="hidden"
                )
                
                chung_row_rects.append(rect)
                chung_row_texts.append(text)
                
            # 紅方明細表
            curr_x = x_tb_start_hong
            for col in range(4):
                w = tb_w * col_ratios[col]
                x1 = curr_x
                x2 = curr_x + w
                curr_x = x2
                
                bg_color = "#f1c40f" if col == 0 else "#101010"
                rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill=bg_color, outline="#888888", width=4, state="hidden")
                
                text_val = str(r + 1) if col == 0 else ""
                text_color = "#000000" if col == 0 else "#ffffff"
                text = self.canvas.create_text(
                    (x1 + x2)/2, (y1 + y2)/2, text=text_val, 
                    font=("Microsoft JhengHei", int((tb_h/2) * 0.50), "bold"), 
                    fill=text_color, state="hidden"
                )
                hong_row_rects.append(rect)
                hong_row_texts.append(text)
                
            self.chung_bot_table_rects.append(chung_row_rects)
            self.chung_bot_table_texts.append(chung_row_texts)
            self.hong_bot_table_rects.append(hong_row_rects)
            self.hong_bot_table_texts.append(hong_row_texts)
        
        # --- 中間選手資料文字 ---
        Uh = int(Mh * 0.214)
        Nh = Mh - Uh
        
        # 青方 (左側) 遮罩層 (解決跑馬燈超出邊界)
        self.cvs_chung_team = tk.Canvas(self.canvas, bg="#0e2854", highlightthickness=0, bd=0)
        self.canvas.create_window(0, Th, window=self.cvs_chung_team, anchor="nw", width=Lw, height=Uh)
        self.txt_chung_team = self.cvs_chung_team.create_text(
            Lw / 2, Uh / 2, text="", 
            font=("Microsoft JhengHei", int(Uh * 0.38), "bold"), fill="#00ccff", justify="center"
        )
        self.txt_chung_player = self.canvas.create_text(
            Lw / 2, Th + Uh + Nh / 2, text="", 
            font=("Microsoft JhengHei", int(Nh * 0.15), "bold"), fill="#ffffff", justify="center", width=Lw - 40
        )
        
        # 紅方 (右側) 遮罩層
        self.cvs_hong_team = tk.Canvas(self.canvas, bg="#540e16", highlightthickness=0, bd=0)
        self.canvas.create_window(Lw + Jw, Th, window=self.cvs_hong_team, anchor="nw", width=Rw, height=Uh)
        self.txt_hong_team = self.cvs_hong_team.create_text(
            Rw / 2, Uh / 2, text="", 
            font=("Microsoft JhengHei", int(Uh * 0.38), "bold"), fill="#ff3366", justify="center"
        )
        self.txt_hong_player = self.canvas.create_text(
            Lw + Jw + Rw / 2, Th + Uh + Nh / 2, text="", 
            font=("Microsoft JhengHei", int(Nh * 0.15), "bold"), fill="#ffffff", justify="center", width=Rw - 40
        )
        
        # --- 狀態燈 (交叉/依序上場模式下閃爍，表示目前正在進行評分的一方) ---
        # 青方狀態燈：在青方姓名大字區塊的左上角（随隔離線分隔區域下方）
        light_r = max(12, int(min(Lw, Mh) * 0.03))  # 燈的半徑
        cx_light = 12 + light_r             # 青方：距左邊界
        cy_light = Th + Uh + 12 + light_r  # 在姓名大字區塊頂端（随隘區分隔線下方）
        self.txt_chung_status_light = self.canvas.create_oval(
            cx_light - light_r, cy_light - light_r,
            cx_light + light_r, cy_light + light_r,
            fill="#00ff44", outline="#00aa22", width=2, state="hidden"
        )
        # 紅方狀態燈：在紅方姓名大字區塊的右上角
        cx_light_r = W - 12 - light_r
        self.txt_hong_status_light = self.canvas.create_oval(
            cx_light_r - light_r, cy_light - light_r,
            cx_light_r + light_r, cy_light + light_r,
            fill="#00ff44", outline="#00aa22", width=2, state="hidden"
        )
        
        # --- 分隔線 ---
        line1 = self.canvas.create_line(0, Th, W, Th, fill="#555555", width=2)
        line2 = self.canvas.create_line(0, H - Bh, W, H - Bh, fill="#555555", width=2)
        line3 = self.canvas.create_line(x_top_split, 0, x_top_split, Th, fill="#555555", width=2)
        
        # 三格的分割線
        self.bot_three_lines = []
        l1 = self.canvas.create_line(x_bot1, H - Bh, x_bot1, H, fill="#444444", width=2)
        l2 = self.canvas.create_line(x_bot2, H - Bh, x_bot2, H, fill="#444444", width=2)
        self.bot_three_lines.extend([l1, l2])
        
        # 兩格的分割線
        self.bot_two_lines = []
        l_mid = self.canvas.create_line(W / 2, H - Bh, W / 2, H, fill="#444444", width=2)
        self.bot_two_lines.append(l_mid)
        
        # 裁判區塊垂直邊界
        line4 = self.canvas.create_line(Lw, Th, Lw, H - Bh, fill="#444444", width=2)
        line5 = self.canvas.create_line(Lw + Jw, Th, Lw + Jw, H - Bh, fill="#444444", width=2)
        
        # 隊伍與姓名分隔線
        line6 = self.canvas.create_line(0, Th + Uh, Lw, Th + Uh, fill="#2c5194", width=2)
        line7 = self.canvas.create_line(Lw + Jw, Th + Uh, W, Th + Uh, fill="#942c38", width=2)
        
        self.general_bg_items.extend([line1, line2, line3, line4, line5, line6, line7])
        
        # PK 賽制詳細評分表元件 (青方與紅方)
        self.chung_table_rects = []
        self.chung_table_texts = []
        self.hong_table_rects = []
        self.hong_table_texts = []
        
        # 建立青方 5x7 表格
        for r in range(5):
            row_rects = []
            row_texts = []
            for c in range(7):
                rect = self.canvas.create_rectangle(0, 0, 0, 0, fill="", outline="", width=1)
                text = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="")
                row_rects.append(rect)
                row_texts.append(text)
            self.chung_table_rects.append(row_rects)
            self.chung_table_texts.append(row_texts)
            
        # 建立紅方 5x7 表格
        for r in range(5):
            row_rects = []
            row_texts = []
            for c in range(7):
                rect = self.canvas.create_rectangle(0, 0, 0, 0, fill="", outline="", width=1)
                text = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="")
                row_rects.append(rect)
                row_texts.append(text)
            self.hong_table_rects.append(row_rects)
            self.hong_table_texts.append(row_texts)

        # === Slide 1 元件 (PK 單輪得分結果頁) ===
        # 青方 Slide 1
        self.txt_chung_final = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#39ff14", state="hidden")
        self.txt_chung_raw_lbl = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#aaaaaa", state="hidden")
        self.txt_chung_raw_val = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#ffffff", state="hidden")
        
        self.rect_chung_acc = self.canvas.create_rectangle(0, 0, 0, 0, fill="#3a2810", outline="#b8860b", width=2, state="hidden")
        self.txt_chung_acc_lbl = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#aaaaaa", state="hidden")
        self.txt_chung_acc_val = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#ffffff", state="hidden")
        
        self.rect_chung_pres = self.canvas.create_rectangle(0, 0, 0, 0, fill="#221230", outline="#8a2be2", width=2, state="hidden")
        self.txt_chung_pres_lbl = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#aaaaaa", state="hidden")
        self.txt_chung_pres_val = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#ffffff", state="hidden")
        
        # 紅方 Slide 1
        self.txt_hong_final = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#39ff14", state="hidden")
        self.txt_hong_raw_lbl = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#aaaaaa", state="hidden")
        self.txt_hong_raw_val = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#ffffff", state="hidden")
        
        self.rect_hong_acc = self.canvas.create_rectangle(0, 0, 0, 0, fill="#3a2810", outline="#b8860b", width=2, state="hidden")
        self.txt_hong_acc_lbl = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#aaaaaa", state="hidden")
        self.txt_hong_acc_val = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#ffffff", state="hidden")
        
        self.rect_hong_pres = self.canvas.create_rectangle(0, 0, 0, 0, fill="#221230", outline="#8a2be2", width=2, state="hidden")
        self.txt_hong_pres_lbl = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#aaaaaa", state="hidden")
        self.txt_hong_pres_val = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 10, "bold"), fill="#ffffff", state="hidden")

        # Winner Block (Slide 2)
        self.rect_winner = self.canvas.create_rectangle(0, 0, 0, 0, fill="#222222", outline="#ffffff", width=3, state="hidden")
        self.txt_winner = self.canvas.create_text(0, 0, text="", font=("Microsoft JhengHei", 20, "bold"), fill="#ffffff", justify="center", state="hidden")

    def get_judge_status(self, judge_num):
        connected = False
        submitted = False
        for sid, jdata in current_state['judges'].items():
            jid = jdata.get('id', '')
            if (jid == f"J{judge_num}" or jid == f"manual_J{judge_num}") and (jdata.get('connected', False) or sid.startswith('manual_')):
                connected = True
                if jdata.get('submitted', False):
                    submitted = True
                    break
        return connected, submitted

    def get_judge_scores(self, judge_num):
        """取得特定裁判對青方與紅方的詳細分數"""
        chung_scores = {'acc': 0.0, 'pres': 0.0, 'p1': 0.0, 'p2': 0.0, 'p3': 0.0, 'submitted': False}
        hong_scores = {'acc': 0.0, 'pres': 0.0, 'p1': 0.0, 'p2': 0.0, 'p3': 0.0, 'submitted': False}
        
        best_data = None
        manual_key = f"manual_J{judge_num}"
        if manual_key in current_state['judges'] and current_state['judges'][manual_key].get('submitted', False):
            best_data = current_state['judges'][manual_key]
        else:
            for sid, jdata in current_state['judges'].items():
                if jdata.get('id') == f"J{judge_num}" and jdata.get('submitted', False):
                    best_data = jdata
                    break
                    
        if best_data:
            gui = None
            if hasattr(self, 'main_gui') and self.main_gui:
                gui = self.main_gui
            is_pk = (gui.mode_var.get() == 1) if (gui and hasattr(gui, 'mode_var')) else False
            pk_seq = int(config.system_settings.get('pk_sequence_mode', 0))
            is_pk_seq = is_pk and (pk_seq == 1 or pk_seq == 2)
            
            chung_submitted = best_data.get('chung_submitted', best_data.get('submitted', False))
            hong_submitted = best_data.get('hong_submitted', False)
            
            if not is_pk_seq:
                # 同時上場或非 PK 賽制，兩邊的 submission 狀態等同於全域 submitted
                chung_submitted = best_data.get('submitted', False)
                hong_submitted = best_data.get('submitted', False)

            chung_scores = {
                'acc': float(best_data.get('acc', 0.0)),
                'pres': float(best_data.get('pres', 0.0)),
                'p1': float(best_data.get('p1', 0.0)),
                'p2': float(best_data.get('p2', 0.0)),
                'p3': float(best_data.get('p3', 0.0)),
                'submitted': chung_submitted
            }
            hong_scores = {
                'acc': float(best_data.get('hong_acc', 0.0)),
                'pres': float(best_data.get('hong_pres', 0.0)),
                'p1': float(best_data.get('hong_p1', 0.0)),
                'p2': float(best_data.get('hong_p2', 0.0)),
                'p3': float(best_data.get('hong_p3', 0.0)),
                'submitted': hong_submitted
            }
        return chung_scores, hong_scores

    def start_chung_team_marquee_scroll(self):
        """延遲過後開始讓青方單位跑馬燈滾動"""
        if not self.winfo_exists() or not getattr(self, 'is_chung_team_marquee_active', False): return
        self.is_chung_team_marquee_scroll_running = True
        self.chung_team_marquee_delay_id = None
        self.chung_team_marquee_tick()

    def chung_team_marquee_tick(self):
        """青方單位跑馬燈定時滾動"""
        if not self.winfo_exists() or not getattr(self, 'is_chung_team_marquee_active', False) or not getattr(self, 'is_chung_team_marquee_scroll_running', False): return
        
        self.chung_team_scroll_x -= 1.5
        chung_start_x = 20
        
        if self.chung_team_scroll_x <= chung_start_x - getattr(self, 'chung_team_scroll_threshold_dist', 0):
            self.chung_team_scroll_x = chung_start_x
            
        W = self.width
        H = self.height
        Th = max(80, int(H * 0.155))
        Bh = max(120, int(H * 0.160))
        Mh = H - Th - Bh
        Uh = int(Mh * 0.214)
        self.cvs_chung_team.coords(self.txt_chung_team, self.chung_team_scroll_x, Uh / 2)
        
        self.after(30, self.chung_team_marquee_tick)

    def start_hong_team_marquee_scroll(self):
        """延遲過後開始讓紅方單位跑馬燈滾動"""
        if not self.winfo_exists() or not getattr(self, 'is_hong_team_marquee_active', False): return
        self.is_hong_team_marquee_scroll_running = True
        self.hong_team_marquee_delay_id = None
        self.hong_team_marquee_tick()

    def hong_team_marquee_tick(self):
        """紅方單位跑馬燈定時滾動"""
        if not self.winfo_exists() or not getattr(self, 'is_hong_team_marquee_active', False) or not getattr(self, 'is_hong_team_marquee_scroll_running', False): return
        
        self.hong_team_scroll_x -= 1.5
        W = self.width
        Jw = max(120, int(W * 0.08))
        Lw = int((W - Jw) / 2)
        hong_start_x = Lw + Jw + 20
        
        if self.hong_team_scroll_x <= hong_start_x - getattr(self, 'hong_team_scroll_threshold_dist', 0):
            self.hong_team_scroll_x = hong_start_x
            
        H = self.height
        Th = max(80, int(H * 0.155))
        Bh = max(120, int(H * 0.160))
        Mh = H - Th - Bh
        Uh = int(Mh * 0.214)
        self.cvs_hong_team.coords(self.txt_hong_team, self.hong_team_scroll_x - (Lw + Jw), Uh / 2)
        
        self.after(30, self.hong_team_marquee_tick)

    @log_refresh_errors
    def refresh(self):
        if not self.winfo_exists(): return
        
        gui = None
        if hasattr(self, 'main_gui') and self.main_gui:
            gui = self.main_gui
            
        # 更新裁判燈狀態
        judge_count = int(system_settings.get("judge_count", 5))
        for i in range(7):
            judge_num = i + 1
            if judge_num > judge_count:
                self.canvas.itemconfigure(self.judge_rects[i], fill="#111111", outline="#222222")
                self.canvas.itemconfigure(self.judge_texts[i], text="")
            else:
                self.canvas.itemconfigure(self.judge_texts[i], text=str(judge_num))
                connected, submitted = self.get_judge_status(judge_num)
                if submitted:
                    self.canvas.itemconfigure(self.judge_rects[i], fill="#ff9900", outline="#ffcc00")
                    self.canvas.itemconfigure(self.judge_texts[i], fill="#00ff55")
                elif connected:
                    self.canvas.itemconfigure(self.judge_rects[i], fill="#202020", outline="#444444")
                    self.canvas.itemconfigure(self.judge_texts[i], fill="#00ff55")
                else:
                    self.canvas.itemconfigure(self.judge_rects[i], fill="#202020", outline="#444444")
                    self.canvas.itemconfigure(self.judge_texts[i], fill="#ffffff")

        if not gui: return
        
        if gui.current_match_uuid:
            self.active_match_uuid = gui.current_match_uuid
        
        match_data = gui.current_match_data
        
        # 1. 狀態 / 時間顯示邏輯
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
        is_showing_score = (status_display == "Score")
        
        last_showing = getattr(self, 'last_is_showing_score', False)
        if is_showing_score and not last_showing:
            self.score_slide_show_finished = False
            self.current_score_slide = 0
        self.last_is_showing_score = is_showing_score
        
        if is_showing_score:
            available_slides = self.get_available_slides(gui)
            if self.current_score_slide not in available_slides:
                self.current_score_slide = available_slides[0]
            
            if not getattr(self, 'score_slide_timer_id', None) and not getattr(self, 'score_slide_show_finished', False):
                self.start_score_slide_show()
        else:
            self.stop_score_slide_show()
            self.current_score_slide = 0
            
        is_leaderboard = False
        general_frame_state = "normal"
        bg_state = "normal"
        
        self.canvas.itemconfigure(self.txt_no, state=general_frame_state)
        self.canvas.itemconfigure(self.txt_group, state=general_frame_state)
        
        # 裁判燈
        for r_id in self.judge_rects: self.canvas.itemconfigure(r_id, state=general_frame_state)
        for t_id in self.judge_texts: self.canvas.itemconfigure(t_id, state=general_frame_state)
        
        # 漸層與分隔線
        if hasattr(self, 'general_bg_items'):
            for item in self.general_bg_items:
                self.canvas.itemconfigure(item, state=bg_state)
        
        # 2. 選手資料與姓名合併邏輯
        if match_data:
            self.canvas.itemconfig(self.txt_no, text=str(match_data.get("No", "")))
            
            parts = []
            for k in ["Category", "Division", "Phase"]:
                val = match_data.get(k, "")
                if val: parts.append(str(val))
            self.canvas.itemconfig(self.txt_group, text=" - ".join(parts))
            
            c_name = str(match_data.get("C_Name", ""))
            c_team = str(match_data.get("C_Team", ""))
            h_name = str(match_data.get("H_Name", ""))
            h_team = str(match_data.get("H_Team", ""))
            
            if is_showing_score:
                # 分數展示頁面：停止狀態燈閃爍
                self._stop_blink()
                
                # 清理跑馬燈以防衝突
                self.is_chung_team_marquee_active = False
                self.is_chung_team_marquee_scroll_running = False
                if hasattr(self, 'chung_team_marquee_delay_id') and self.chung_team_marquee_delay_id:
                    try: self.after_cancel(self.chung_team_marquee_delay_id)
                    except: pass
                    self.chung_team_marquee_delay_id = None
                
                self.is_hong_team_marquee_active = False
                self.is_hong_team_marquee_scroll_running = False
                if hasattr(self, 'hong_team_marquee_delay_id') and self.hong_team_marquee_delay_id:
                    try: self.after_cancel(self.hong_team_marquee_delay_id)
                    except: pass
                    self.hong_team_marquee_delay_id = None
                # 詳細裁判評分表頁面：合併姓名與單位，過長截斷
                chung_disp = f"{c_name} - {c_team}" if (c_name and c_team) else f"{c_name}{c_team}".strip()
                hong_disp = f"{h_name} - {h_team}" if (h_name and h_team) else f"{h_name}{h_team}".strip()
                
                import tkinter.font as tkfont
                W = self.width
                Jw = max(120, int(W * 0.08))
                Lw = int((W - Jw) / 2)
                max_w = Lw - 40
                
                Th = max(80, int(self.height * 0.155))
                Bh = max(120, int(self.height * 0.160))
                Mh = self.height - Th - Bh
                Uh = int(Mh * 0.214)
                f_title = tkfont.Font(family="Microsoft JhengHei", size=int(Uh * 0.38), weight="bold")
                
                while len(chung_disp) > 0 and f_title.measure(chung_disp) > max_w:
                    chung_disp = chung_disp[:-1]
                while len(hong_disp) > 0 and f_title.measure(hong_disp) > max_w:
                    hong_disp = hong_disp[:-1]
                    
                self.cvs_chung_team.itemconfig(self.txt_chung_team, text=chung_disp)
                self.cvs_hong_team.itemconfig(self.txt_hong_team, text=hong_disp)
                self.cvs_chung_team.itemconfigure(self.txt_chung_team, fill="#ffffff", state=general_frame_state)
                self.cvs_hong_team.itemconfigure(self.txt_hong_team, fill="#ffffff", state=general_frame_state)
                self.canvas.itemconfigure(self.txt_chung_player, state="hidden")
                self.canvas.itemconfigure(self.txt_hong_player, state="hidden")
            else:
                # 計算相關版面高度與寬度以決定姓名與單位區域
                W = self.width
                Jw = max(120, int(W * 0.08))
                Lw = int((W - Jw) / 2)
                Rw = Lw  # 左右對稱
                
                Th = max(80, int(self.height * 0.155))
                Bh = max(120, int(self.height * 0.160))
                Mh = self.height - Th - Bh
                Uh = int(Mh * 0.214)
                Nh = Mh - Uh
                
                # 選手介紹頁面：依據當前打分方位調整顏色與狀態燈
                pk_seq_mode = int(config.system_settings.get('pk_sequence_mode', 0))
                current_side = config.current_state.get('current_player_side', -1)
                
                # 判斷是否為交叉/依序上場且正在評分中
                is_sequential = (pk_seq_mode in (1, 2)) and config.current_state.get('is_scoring', False)
                
                if is_sequential:
                    # 進行中的方：正常亮色；未出賽方：調暗
                    if current_side == 0:  # 青方進行中
                        chung_team_color = "#00ccff"
                        chung_name_color = "#ffffff"
                        hong_team_color = "#663344"
                        hong_name_color = "#666666"
                        self._start_blink('chung')
                    else:  # 紅方進行中
                        chung_team_color = "#004455"
                        chung_name_color = "#666666"
                        hong_team_color = "#ff3366"
                        hong_name_color = "#ffffff"
                        self._start_blink('hong')
                else:
                    chung_team_color = "#00ccff"
                    chung_name_color = "#ffffff"
                    hong_team_color = "#ff3366"
                    hong_name_color = "#ffffff"
                    self._stop_blink()

                # --- 單位跑馬燈邏輯 (參考一般賽制) ---
                import tkinter.font as tkfont
                f_team_font = tkfont.Font(family="Microsoft JhengHei", size=int(Uh * 0.38), weight="bold")
                
                # 1. 青方單位跑馬燈
                chung_team_w = f_team_font.measure(c_team)
                chung_team_changed = (c_team != getattr(self, 'current_chung_team_raw', None))
                if chung_team_changed:
                    self.current_chung_team_raw = c_team
                    if chung_team_w <= Lw - 40:
                        self.is_chung_team_marquee_active = False
                        self.is_chung_team_marquee_scroll_running = False
                        if hasattr(self, 'chung_team_marquee_delay_id') and self.chung_team_marquee_delay_id:
                            try: self.after_cancel(self.chung_team_marquee_delay_id)
                            except: pass
                            self.chung_team_marquee_delay_id = None
                        self.cvs_chung_team.itemconfig(self.txt_chung_team, text=c_team, anchor="center")
                        self.cvs_chung_team.coords(self.txt_chung_team, Lw / 2, Uh / 2)
                    else:
                        space_str = " " * 6
                        space_width = f_team_font.measure(space_str)
                        display_text = c_team + space_str + c_team
                        self.chung_team_scroll_threshold_dist = chung_team_w + space_width
                        start_x = 20
                        
                        self.is_chung_team_marquee_active = False
                        self.is_chung_team_marquee_scroll_running = False
                        if hasattr(self, 'chung_team_marquee_delay_id') and self.chung_team_marquee_delay_id:
                            try: self.after_cancel(self.chung_team_marquee_delay_id)
                            except: pass
                            self.chung_team_marquee_delay_id = None
                            
                        self.chung_team_scroll_x = start_x
                        self.cvs_chung_team.itemconfig(self.txt_chung_team, text=display_text, anchor="w")
                        self.cvs_chung_team.coords(self.txt_chung_team, self.chung_team_scroll_x, Uh / 2)
                        
                        self.is_chung_team_marquee_active = True
                        self.chung_team_marquee_delay_id = self.after(1500, self.start_chung_team_marquee_scroll)
                
                # 2. 紅方單位跑馬燈
                hong_team_w = f_team_font.measure(h_team)
                hong_team_changed = (h_team != getattr(self, 'current_hong_team_raw', None))
                if hong_team_changed:
                    self.current_hong_team_raw = h_team
                    if hong_team_w <= Lw - 40:
                        self.is_hong_team_marquee_active = False
                        self.is_hong_team_marquee_scroll_running = False
                        if hasattr(self, 'hong_team_marquee_delay_id') and self.hong_team_marquee_delay_id:
                            try: self.after_cancel(self.hong_team_marquee_delay_id)
                            except: pass
                            self.hong_team_marquee_delay_id = None
                        self.cvs_hong_team.itemconfig(self.txt_hong_team, text=h_team, anchor="center")
                        self.cvs_hong_team.coords(self.txt_hong_team, Rw / 2, Uh / 2)
                    else:
                        space_str = " " * 6
                        space_width = f_team_font.measure(space_str)
                        display_text = h_team + space_str + h_team
                        self.hong_team_scroll_threshold_dist = hong_team_w + space_width
                        start_x = Lw + Jw + 20
                        
                        self.is_hong_team_marquee_active = False
                        self.is_hong_team_marquee_scroll_running = False
                        if hasattr(self, 'hong_team_marquee_delay_id') and self.hong_team_marquee_delay_id:
                            try: self.after_cancel(self.hong_team_marquee_delay_id)
                            except: pass
                            self.hong_team_marquee_delay_id = None
                            
                        self.hong_team_scroll_x = start_x
                        self.cvs_hong_team.itemconfig(self.txt_hong_team, text=display_text, anchor="w")
                        self.cvs_hong_team.coords(self.txt_hong_team, self.hong_team_scroll_x - (Lw + Jw), Uh / 2)
                        
                        self.is_hong_team_marquee_active = True
                        self.hong_team_marquee_delay_id = self.after(1500, self.start_hong_team_marquee_scroll)

                # 套用配色與顯示狀態到單位欄位
                self.cvs_chung_team.itemconfigure(self.txt_chung_team, fill=chung_team_color, state=general_frame_state)
                self.cvs_hong_team.itemconfigure(self.txt_hong_team, fill=hong_team_color, state=general_frame_state)

                # --- 姓名自動縮小字型邏輯 (支援換行，高度超出才縮小) ---
                max_player_w = Lw - 40
                max_player_h = Nh * 0.75
                base_font_size = int(Nh * 0.15)
                
                # 計算青方姓名縮小字型
                current_chung_font_size = base_font_size
                for size in range(base_font_size, 8, -2):
                    f_p = tkfont.Font(family="Microsoft JhengHei", size=size, weight="bold")
                    line_height = f_p.metrics("linespace")
                    lines = 0
                    current_line_w = 0
                    for char in c_name:
                        char_w = f_p.measure(char)
                        if current_line_w + char_w > max_player_w:
                            lines += 1
                            current_line_w = char_w
                        else:
                            current_line_w += char_w
                    if current_line_w > 0:
                        lines += 1
                    total_h = lines * line_height
                    if total_h <= max_player_h:
                        current_chung_font_size = size
                        break
                else:
                    current_chung_font_size = 8
                    
                # 計算紅方姓名縮小字型
                current_hong_font_size = base_font_size
                for size in range(base_font_size, 8, -2):
                    f_p = tkfont.Font(family="Microsoft JhengHei", size=size, weight="bold")
                    line_height = f_p.metrics("linespace")
                    lines = 0
                    current_line_w = 0
                    for char in h_name:
                        char_w = f_p.measure(char)
                        if current_line_w + char_w > max_player_w:
                            lines += 1
                            current_line_w = char_w
                        else:
                            current_line_w += char_w
                    if current_line_w > 0:
                        lines += 1
                    total_h = lines * line_height
                    if total_h <= max_player_h:
                        current_hong_font_size = size
                        break
                else:
                    current_hong_font_size = 8

                self.canvas.itemconfig(self.txt_chung_player, text=c_name, font=("Microsoft JhengHei", current_chung_font_size, "bold"))
                self.canvas.itemconfigure(self.txt_chung_player, fill=chung_name_color, state=general_frame_state)
                
                self.canvas.itemconfig(self.txt_hong_player, text=h_name, font=("Microsoft JhengHei", current_hong_font_size, "bold"))
                self.canvas.itemconfigure(self.txt_hong_player, fill=hong_name_color, state=general_frame_state)
                
            # 更新 1R, 2R 品勢名稱
            try:
                if hasattr(gui, 'combo_poomsae_1'): p1 = gui.combo_poomsae_1.get()
                else: p1 = match_data.get("Poomsae 1", "")
                
                if hasattr(gui, 'combo_poomsae_2'): p2 = gui.combo_poomsae_2.get()
                else: p2 = match_data.get("Poomsae 2", "")
                
                if p1: p1 = p1.split(' ')[0]
                if p2 and "不需選擇" not in p2: p2 = p2.split(' ')[0]
                else: p2 = ""
                
                self.canvas.itemconfig(self.txt_1r, text=p1 if p1 else "---")
                self.canvas.itemconfig(self.txt_2r, text=p2 if p2 else "---")
                self.canvas.itemconfigure(self.txt_1r, state=general_frame_state)
                self.canvas.itemconfigure(self.txt_2r, state=general_frame_state)
            except: pass
            
        else:
            self.canvas.itemconfig(self.txt_no, text="")
            self.canvas.itemconfig(self.txt_group, text="")
            self.cvs_chung_team.itemconfig(self.txt_chung_team, text="")
            self.canvas.itemconfig(self.txt_chung_player, text="")
            self.canvas.itemconfigure(self.txt_chung_player, state=general_frame_state)
            self.cvs_hong_team.itemconfig(self.txt_hong_team, text="")
            self.canvas.itemconfig(self.txt_hong_player, text="")
            self.canvas.itemconfigure(self.txt_hong_player, state=general_frame_state)
            self.canvas.itemconfig(self.txt_1r, text="---")
            self.canvas.itemconfig(self.txt_2r, text="---")
            self.canvas.itemconfigure(self.txt_1r, state=general_frame_state)
            self.canvas.itemconfigure(self.txt_2r, state=general_frame_state)
            self._stop_blink()
            
            # 清除跑馬燈
            self.is_chung_team_marquee_active = False
            self.is_chung_team_marquee_scroll_running = False
            if hasattr(self, 'chung_team_marquee_delay_id') and self.chung_team_marquee_delay_id:
                try: self.after_cancel(self.chung_team_marquee_delay_id)
                except: pass
                self.chung_team_marquee_delay_id = None
            
            self.is_hong_team_marquee_active = False
            self.is_hong_team_marquee_scroll_running = False
            if hasattr(self, 'hong_team_marquee_delay_id') and self.hong_team_marquee_delay_id:
                try: self.after_cancel(self.hong_team_marquee_delay_id)
                except: pass
                self.hong_team_marquee_delay_id = None
            
        # 3. 裁判詳細分數表格邏輯
        # 首先預設隱藏所有表格元件
        for r in range(5):
            for c in range(7):
                self.canvas.itemconfigure(self.chung_table_rects[r][c], state="hidden")
                self.canvas.itemconfigure(self.chung_table_texts[r][c], state="hidden")
                self.canvas.itemconfigure(self.hong_table_rects[r][c], state="hidden")
                self.canvas.itemconfigure(self.hong_table_texts[r][c], state="hidden")
                
        # 預設隱藏 Slide 1 的所有元件
        slide1_items = [
            self.txt_chung_final, self.txt_chung_raw_lbl, self.txt_chung_raw_val,
            self.rect_chung_acc, self.txt_chung_acc_lbl, self.txt_chung_acc_val,
            self.rect_chung_pres, self.txt_chung_pres_lbl, self.txt_chung_pres_val,
            self.txt_hong_final, self.txt_hong_raw_lbl, self.txt_hong_raw_val,
            self.rect_hong_acc, self.txt_hong_acc_lbl, self.txt_hong_acc_val,
            self.rect_hong_pres, self.txt_hong_pres_lbl, self.txt_hong_pres_val
        ]
        for item in slide1_items:
            self.canvas.itemconfigure(item, state="hidden")
            
        if hasattr(self, 'rect_winner'):
            self.canvas.itemconfigure(self.rect_winner, state="hidden")
            self.canvas.itemconfigure(self.txt_winner, state="hidden")
            
        # 底欄顯示與隱藏狀態
        bot_three_state = "hidden" if (self.current_score_slide == 2) else "normal"
        bot_two_state = "normal" if (self.current_score_slide == 2) else "hidden"
        
        for item in self.bot_two_bg:
            self.canvas.itemconfigure(item, state=bot_two_state)
        for item in self.bot_two_lines:
            self.canvas.itemconfigure(item, state=bot_two_state)
        if hasattr(self, 'chung_bot_table_rects'):
            for r in range(2):
                for c in range(4):
                    self.canvas.itemconfigure(self.chung_bot_table_rects[r][c], state=bot_two_state)
                    self.canvas.itemconfigure(self.chung_bot_table_texts[r][c], state=bot_two_state)
                    self.canvas.itemconfigure(self.hong_bot_table_rects[r][c], state=bot_two_state)
                    self.canvas.itemconfigure(self.hong_bot_table_texts[r][c], state=bot_two_state)
        
        for item in self.bot_three_bg:
            self.canvas.itemconfigure(item, state=bot_three_state)
        for item in self.bot_three_lines:
            self.canvas.itemconfigure(item, state=bot_three_state)
        self.canvas.itemconfigure(self.txt_status, state=bot_three_state)
        self.canvas.itemconfigure(self.txt_1r, state=bot_three_state)
        self.canvas.itemconfigure(self.txt_2r, state=bot_three_state)
                
        if is_showing_score and match_data:
            # 優先嘗試從 temp_scores 或是資料庫中讀取當前輪數的存檔分數
            match_uuid = self.active_match_uuid or (match_data.get("match_uuid", gui.current_match_uuid) if match_data else gui.current_match_uuid)
            curr_round = gui.current_stage if gui else 1
            
            rows = []
            temp_scores = config.current_state.get('temp_scores', getattr(gui, 'temp_scores_to_save', {}))
            if temp_scores:
                for r_num, scores_list in temp_scores.items():
                    for s in scores_list:
                        if s.get('match_uuid') == match_uuid:
                            rows.append((
                                s['round_num'],
                                s.get('player_side', 0),
                                s['judge_id'],
                                s['acc'],
                                s['pres'],
                                s.get('p1', 0.0),
                                s.get('p2', 0.0),
                                s.get('p3', 0.0),
                                s.get('deduction', 0.0),
                                s['total']
                            ))
            if not rows:
                try:
                    import sqlite3
                    import database
                    conn = sqlite3.connect(database.get_db_path())
                    c = conn.cursor()
                    c.execute("""
                        SELECT round, player_side, judge_id, accuracy, presentation, p1, p2, p3, deduction, total
                        FROM scores
                        WHERE match_uuid = ?
                    """, (match_uuid,))
                    rows = c.fetchall()
                    conn.close()
                except Exception as db_err:
                    print(f"Error querying scores for PK projection: {db_err}")
                    rows = []

            if self.current_score_slide == 0:
                # 固定為 5 行（標題、Acc、P1、P2、P3）
                num_rows = 5
                row_keys = [None, 'acc', 'p1', 'p2', 'p3']
                row_bg_colors_chung = [None, "#004d66", "#006680", "#006680", "#006680"]
                row_bg_colors_hong = [None, "#660011", "#80001a", "#80001a", "#80001a"]
                
                # 建立以裁判編號 (1~7) 為 key 的分數字典，用於 Slide 0
                chung_by_judge = {}
                hong_by_judge = {}
                
                for row in rows:
                    r_num, side, j_id, acc, pres, p1, p2, p3, ded, tot = row
                    if r_num == curr_round:
                        try:
                            j_num_str = j_id.split('_')[-1] # 處理 manual_J1 -> J1
                            j_num = int(j_num_str[1:])
                        except:
                            continue
                        
                        score_dict = {
                            'acc': acc,
                            'pres': pres,
                            'p1': p1,
                            'p2': p2,
                            'p3': p3,
                            'total': tot,
                            'submitted': True
                        }
                        if side == 0:
                            chung_by_judge[j_num] = score_dict
                        elif side == 1:
                            hong_by_judge[j_num] = score_dict
                
                def get_gray_indices(scores_dict):
                    gray_set = set()
                    valid_scores = [(j_num, val) for j_num, val in scores_dict.items()]
                    if len(valid_scores) > 3:
                        scores_only = [item[1] for item in valid_scores]
                        min_val = min(scores_only)
                        max_val = max(scores_only)
                        
                        min_judge = -1
                        max_judge = -1
                        for j_num, val in valid_scores:
                            if val == min_val and min_judge == -1:
                                min_judge = j_num
                        for j_num, val in valid_scores:
                            if val == max_val and max_judge == -1 and j_num != min_judge:
                                max_judge = j_num
                        if min_judge != -1: gray_set.add(min_judge)
                        if max_judge != -1: gray_set.add(max_judge)
                    return gray_set
                    
                row_gray_chung = {}
                row_gray_hong = {}
                for r in range(1, num_rows):
                    key = row_keys[r]
                    chung_row_scores = {}
                    hong_row_scores = {}
                    for j_num in range(1, judge_count + 1):
                        if chung_by_judge and j_num in chung_by_judge:
                            c_scores = chung_by_judge[j_num]
                        else:
                            c_scores, _ = self.get_judge_scores(j_num)
                            
                        if hong_by_judge and j_num in hong_by_judge:
                            h_scores = hong_by_judge[j_num]
                        else:
                            _, h_scores = self.get_judge_scores(j_num)
                            
                        if c_scores['submitted']:
                            chung_row_scores[j_num] = c_scores[key]
                        if h_scores['submitted']:
                            hong_row_scores[j_num] = h_scores[key]
                            
                    row_gray_chung[r] = get_gray_indices(chung_row_scores)
                    row_gray_hong[r] = get_gray_indices(hong_row_scores)
                    
                W = self.width
                H = self.height
                Th = max(80, int(H * 0.155))
                Bh = max(120, int(H * 0.160))
                Mh = H - Th - Bh
                Jw = max(120, int(W * 0.08))
                Lw = int((W - Jw) / 2)
                Uh = int(Mh * 0.214)
                
                y_start = Th + Uh + 10
                y_end = H - Bh - 10
                row_h = (y_end - y_start) / num_rows
                
                # 依據裁判人數動態調整字體大小，7人時微調縮小以利排版
                font_title_size = int(row_h * 0.30) if judge_count == 7 else int(row_h * 0.40)
                font_score_size = int(row_h * 0.35) if judge_count == 7 else int(row_h * 0.45)
                
                # 青方表格佈局 (寬度自適應 1/3/5 居中；1,3人時靠左對齊)
                x_start_chung = 20
                x_end_chung = Lw - 20
                avail_w_chung = x_end_chung - x_start_chung
                divisor_chung = 7 if judge_count == 7 else 5
                col_w_chung = avail_w_chung / divisor_chung
                if judge_count in [1, 3]:
                    x_offset_chung = 0
                else:
                    x_offset_chung = (avail_w_chung - judge_count * col_w_chung) / 2
                
                for r in range(num_rows):
                    for c in range(judge_count):
                        judge_num = c + 1
                        rect_id = self.chung_table_rects[r][c]
                        text_id = self.chung_table_texts[r][c]
                        
                        x1 = x_start_chung + x_offset_chung + c * col_w_chung
                        y1 = y_start + r * row_h
                        x2 = x1 + col_w_chung
                        y2 = y1 + row_h
                        
                        self.canvas.coords(rect_id, x1, y1, x2, y2)
                        self.canvas.coords(text_id, (x1 + x2) / 2, (y1 + y2) / 2)
                        self.canvas.itemconfigure(rect_id, state="normal")
                        self.canvas.itemconfigure(text_id, state="normal")
                        
                        if r == 0:
                            # 標題行：深青藍底、黑色外框、大字白字
                            self.canvas.itemconfigure(rect_id, fill="#003344", outline="#000000")
                            self.canvas.itemconfigure(text_id, text=f"J{judge_num}", fill="#ffffff", font=("Microsoft JhengHei", font_title_size, "bold"))
                        else:
                            if chung_by_judge and judge_num in chung_by_judge:
                                c_scores = chung_by_judge[judge_num]
                            else:
                                c_scores, _ = self.get_judge_scores(judge_num)
                                
                            val_str = ""
                            text_color = "#ffffff"
                            if c_scores['submitted']:
                                key = row_keys[r]
                                val = c_scores[key]
                                val_str = f"{val:.1f}"
                                if judge_num in row_gray_chung.get(r, set()):
                                    text_color = "#7f7f7f"
                            else:
                                text_color = "#7f7f7f"
                                
                            self.canvas.itemconfigure(rect_id, fill=row_bg_colors_chung[r], outline="#000000")
                            self.canvas.itemconfigure(text_id, text=val_str, fill=text_color, font=("Microsoft JhengHei", font_score_size, "bold"))
                            
                # 紅方表格佈局 (寬度自適應 1/3/5 居中；1,3人時靠右對齊)
                x_start_hong = Lw + Jw + 20
                x_end_hong = W - 20
                avail_w_hong = x_end_hong - x_start_hong
                divisor_hong = 7 if judge_count == 7 else 5
                col_w_hong = avail_w_hong / divisor_hong
                if judge_count in [1, 3]:
                    x_offset_hong = avail_w_hong - judge_count * col_w_hong
                else:
                    x_offset_hong = (avail_w_hong - judge_count * col_w_hong) / 2
                
                for r in range(num_rows):
                    for c in range(judge_count):
                        judge_num = c + 1
                        rect_id = self.hong_table_rects[r][c]
                        text_id = self.hong_table_texts[r][c]
                        
                        # 紅方裁判從右往左排
                        visual_c = judge_count - 1 - c
                        x1 = x_start_hong + x_offset_hong + visual_c * col_w_hong
                        y1 = y_start + r * row_h
                        x2 = x1 + col_w_hong
                        y2 = y1 + row_h
                        
                        self.canvas.coords(rect_id, x1, y1, x2, y2)
                        self.canvas.coords(text_id, (x1 + x2) / 2, (y1 + y2) / 2)
                        self.canvas.itemconfigure(rect_id, state="normal")
                        self.canvas.itemconfigure(text_id, state="normal")
                        
                        if r == 0:
                            # 標題行：深紅黑底、黑色外框、大字白字
                            self.canvas.itemconfigure(rect_id, fill="#4d000d", outline="#000000")
                            self.canvas.itemconfigure(text_id, text=f"J{judge_num}", fill="#ffffff", font=("Microsoft JhengHei", font_title_size, "bold"))
                        else:
                            if hong_by_judge and judge_num in hong_by_judge:
                                h_scores = hong_by_judge[judge_num]
                            else:
                                _, h_scores = self.get_judge_scores(judge_num)
                                
                            val_str = ""
                            text_color = "#ffffff"
                            if h_scores['submitted']:
                                key = row_keys[r]
                                val = h_scores[key]
                                val_str = f"{val:.1f}"
                                if judge_num in row_gray_hong.get(r, set()):
                                    text_color = "#7f7f7f"
                            else:
                                text_color = "#7f7f7f"
                                
                            self.canvas.itemconfigure(rect_id, fill=row_bg_colors_hong[r], outline="#000000")
                            self.canvas.itemconfigure(text_id, text=val_str, fill=text_color, font=("Microsoft JhengHei", font_score_size, "bold"))

            elif self.current_score_slide == 1:
                # 顯示 Slide 1 的所有元件
                for item in slide1_items:
                    self.canvas.itemconfigure(item, state="normal")
                    
                # 計算分數
                chung_accs = []
                chung_press = []
                chung_totals = []
                chung_deds = []
                
                hong_accs = []
                hong_press = []
                hong_totals = []
                hong_deds = []
                
                for row in rows:
                    r_num, side, j_id, acc, pres, p1, p2, p3, ded, tot = row
                    if r_num == curr_round:
                        if side == 0: # 青方
                            chung_accs.append(acc)
                            chung_press.append(pres)
                            chung_totals.append(acc + pres)
                            chung_deds.append(ded)
                        elif side == 1: # 紅方
                            hong_accs.append(acc)
                            hong_press.append(pres)
                            hong_totals.append(acc + pres)
                            hong_deds.append(ded)
                            
                def get_trimmed_avg(val_list):
                    if not val_list: return 0.0
                    if len(val_list) <= 3: return sum(val_list) / len(val_list)
                    val_list.sort()
                    return sum(val_list[1:-1]) / len(val_list[1:-1])
                    
                if chung_accs or hong_accs:
                    chung_avg_acc = get_trimmed_avg(chung_accs)
                    chung_avg_pres = get_trimmed_avg(chung_press)
                    chung_raw_total = sum(chung_totals)
                    chung_deduction = max(chung_deds) if chung_deds else 0.0
                    
                    hong_avg_acc = get_trimmed_avg(hong_accs)
                    hong_avg_pres = get_trimmed_avg(hong_press)
                    hong_raw_total = sum(hong_totals)
                    hong_deduction = max(hong_deds) if hong_deds else 0.0
                else:
                    # Fallback: 使用當前記憶體中的即時分數
                    for j_num in range(1, judge_count + 1):
                        c_scores, h_scores = self.get_judge_scores(j_num)
                        if c_scores['submitted']:
                            chung_accs.append(c_scores['acc'])
                            chung_press.append(c_scores['pres'])
                            chung_totals.append(c_scores['acc'] + c_scores['pres'])
                        if h_scores['submitted']:
                            hong_accs.append(h_scores['acc'])
                            hong_press.append(h_scores['pres'])
                            hong_totals.append(h_scores['acc'] + h_scores['pres'])
                            
                    chung_avg_acc = get_trimmed_avg(chung_accs)
                    chung_avg_pres = get_trimmed_avg(chung_press)
                    chung_raw_total = sum(chung_totals)
                    
                    hong_avg_acc = get_trimmed_avg(hong_accs)
                    hong_avg_pres = get_trimmed_avg(hong_press)
                    hong_raw_total = sum(hong_totals)
                    
                    chung_deduction = 0.0
                    if gui and hasattr(gui, 'lbl_deduction_val'):
                        try: chung_deduction = float(gui.lbl_deduction_val.cget("text"))
                        except: pass
                    hong_deduction = 0.0
                    if gui and hasattr(gui, 'lbl_deduction_val_R'):
                        try: hong_deduction = float(gui.lbl_deduction_val_R.cget("text"))
                        except: pass
                    
                # 最終得分
                chung_final = chung_avg_acc + chung_avg_pres - chung_deduction
                hong_final = hong_avg_acc + hong_avg_pres - hong_deduction
                
                # 版面參數計算
                W = self.width
                H = self.height
                Th = max(80, int(H * 0.155))
                Bh = max(120, int(H * 0.160))
                Mh = H - Th - Bh
                Jw = max(120, int(W * 0.08))
                Lw = int((W - Jw) / 2)
                Uh = int(Mh * 0.214)
                
                y_start = Th + Uh + 10
                y_end = H - Bh - 10
                avail_h = y_end - y_start
                
                # 字型大小與間距
                font_final_size = int(avail_h * 0.22)
                font_raw_val_size = int(avail_h * 0.12)
                
                # --- 青方 Slide 1 更新 ---
                x_left_chung = 20
                x_right_chung = Lw - 20
                x_center_chung = (x_left_chung + x_right_chung) / 2
                
                y_final_chung = y_start + avail_h * 0.25
                y_raw_val_chung = y_start + avail_h * 0.54
                
                self.canvas.itemconfig(self.txt_chung_final, text=format_pk_score(chung_final), font=("Microsoft JhengHei", font_final_size, "bold"), anchor="center")
                self.canvas.coords(self.txt_chung_final, x_center_chung, y_final_chung)
                
                self.canvas.itemconfig(self.txt_chung_raw_val, text=f"{chung_raw_total:.1f}", font=("Microsoft JhengHei", font_raw_val_size, "bold"), anchor="center")
                self.canvas.coords(self.txt_chung_raw_val, x_center_chung, y_raw_val_chung)
                
                # 正確性與表現性框
                box_w = (x_right_chung - x_left_chung) * 0.38
                box_h = avail_h * 0.18
                y_box_center = y_start + avail_h * 0.82
                y1_box = y_box_center - box_h / 2
                y2_box = y_box_center + box_h / 2
                
                font_box_val_size = int(box_h * 0.55)
                
                # 青方正確性
                x1_c_acc = x_left_chung + (x_right_chung - x_left_chung) * 0.08
                x2_c_acc = x1_c_acc + box_w
                self.canvas.coords(self.rect_chung_acc, x1_c_acc, y1_box, x2_c_acc, y2_box)
                self.canvas.itemconfig(self.txt_chung_acc_val, text=format_pk_score(chung_avg_acc), font=("Microsoft JhengHei", font_box_val_size, "bold"))
                self.canvas.coords(self.txt_chung_acc_val, (x1_c_acc + x2_c_acc)/2, (y1_box + y2_box)/2)
                
                # 青方表現性
                x1_c_pres = x_right_chung - (x_right_chung - x_left_chung) * 0.08 - box_w
                x2_c_pres = x1_c_pres + box_w
                self.canvas.coords(self.rect_chung_pres, x1_c_pres, y1_box, x2_c_pres, y2_box)
                self.canvas.itemconfig(self.txt_chung_pres_val, text=format_pk_score(chung_avg_pres), font=("Microsoft JhengHei", font_box_val_size, "bold"))
                self.canvas.coords(self.txt_chung_pres_val, (x1_c_pres + x2_c_pres)/2, (y1_box + y2_box)/2)
                
                # --- 紅方 Slide 1 更新 ---
                x_left_hong = Lw + Jw + 20
                x_right_hong = W - 20
                x_center_hong = (x_left_hong + x_right_hong) / 2
                
                y_final_hong = y_start + avail_h * 0.25
                y_raw_val_hong = y_start + avail_h * 0.54
                
                self.canvas.itemconfig(self.txt_hong_final, text=format_pk_score(hong_final), font=("Microsoft JhengHei", font_final_size, "bold"), anchor="center")
                self.canvas.coords(self.txt_hong_final, x_center_hong, y_final_hong)
                
                self.canvas.itemconfig(self.txt_hong_raw_val, text=f"{hong_raw_total:.1f}", font=("Microsoft JhengHei", font_raw_val_size, "bold"), anchor="center")
                self.canvas.coords(self.txt_hong_raw_val, x_center_hong, y_raw_val_hong)
                
                # 紅方正確性
                x1_h_acc = x_left_hong + (x_right_hong - x_left_hong) * 0.08
                x2_h_acc = x1_h_acc + box_w
                self.canvas.coords(self.rect_hong_acc, x1_h_acc, y1_box, x2_h_acc, y2_box)
                self.canvas.itemconfig(self.txt_hong_acc_val, text=format_pk_score(hong_avg_acc), font=("Microsoft JhengHei", font_box_val_size, "bold"))
                self.canvas.coords(self.txt_hong_acc_val, (x1_h_acc + x2_h_acc)/2, (y1_box + y2_box)/2)
                
                # 紅方表現性
                x1_h_pres = x_right_hong - (x_right_hong - x_left_hong) * 0.08 - box_w
                x2_h_pres = x1_h_pres + box_w
                self.canvas.coords(self.rect_hong_pres, x1_h_pres, y1_box, x2_h_pres, y2_box)
                self.canvas.itemconfig(self.txt_hong_pres_val, text=format_pk_score(hong_avg_pres), font=("Microsoft JhengHei", font_box_val_size, "bold"))
                self.canvas.coords(self.txt_hong_pres_val, (x1_h_pres + x2_h_pres)/2, (y1_box + y2_box)/2)
            elif self.current_score_slide == 2:
                # 顯示 Slide 1 的所有元件，但隱藏 Acc 元件
                for item in slide1_items:
                    self.canvas.itemconfigure(item, state="normal")
                self.canvas.itemconfigure(self.rect_chung_acc, state="hidden")
                self.canvas.itemconfigure(self.txt_chung_acc_lbl, state="hidden")
                self.canvas.itemconfigure(self.txt_chung_acc_val, state="hidden")
                self.canvas.itemconfigure(self.rect_hong_acc, state="hidden")
                self.canvas.itemconfigure(self.txt_hong_acc_lbl, state="hidden")
                self.canvas.itemconfigure(self.txt_hong_acc_val, state="hidden")
                
                # 隱藏底部三格，顯示兩格
                for item in self.bot_three_bg:
                    self.canvas.itemconfigure(item, state="hidden")
                for item in self.bot_three_lines:
                    self.canvas.itemconfigure(item, state="hidden")
                self.canvas.itemconfigure(self.txt_status, state="hidden")
                self.canvas.itemconfigure(self.txt_1r, state="hidden")
                self.canvas.itemconfigure(self.txt_2r, state="hidden")
                
                for item in self.bot_two_bg:
                    self.canvas.itemconfigure(item, state="normal")
                for item in self.bot_two_lines:
                    self.canvas.itemconfigure(item, state="normal")
                if hasattr(self, 'chung_bot_table_rects'):
                    for r in range(2):
                        for c in range(4):
                            self.canvas.itemconfigure(self.chung_bot_table_rects[r][c], state="normal")
                            self.canvas.itemconfigure(self.chung_bot_table_texts[r][c], state="normal")
                            self.canvas.itemconfigure(self.hong_bot_table_rects[r][c], state="normal")
                            self.canvas.itemconfigure(self.hong_bot_table_texts[r][c], state="normal")
                
                # 從資料庫中讀取 1R 與 2R 的分數
                import sqlite3
                import database
                
                chung_1r = {'acc': 0.0, 'pres': 0.0, 'ded': 0.0, 'total': 0.0, 'raw_sum': 0.0}
                chung_2r = {'acc': 0.0, 'pres': 0.0, 'ded': 0.0, 'total': 0.0, 'raw_sum': 0.0}
                hong_1r  = {'acc': 0.0, 'pres': 0.0, 'ded': 0.0, 'total': 0.0, 'raw_sum': 0.0}
                hong_2r  = {'acc': 0.0, 'pres': 0.0, 'ded': 0.0, 'total': 0.0, 'raw_sum': 0.0}
                
                match_uuid = self.active_match_uuid or (match_data.get("match_uuid", gui.current_match_uuid) if match_data else gui.current_match_uuid)
                
                rows = []
                temp_scores = config.current_state.get('temp_scores', getattr(gui, 'temp_scores_to_save', {}))
                if temp_scores:
                    for r_num, scores_list in temp_scores.items():
                        for s in scores_list:
                            if s.get('match_uuid') == match_uuid:
                                rows.append((
                                    s['round_num'],
                                    s.get('player_side', 0),
                                    s['acc'],
                                    s['pres'],
                                    s['deduction'],
                                    s['total']
                                ))
                                
                with open("projection_debug.log", "a", encoding="utf-8") as f:
                    import json
                    f.write(f"Projection rows: {json.dumps(rows, ensure_ascii=False)}\n")
                if not rows:
                    try:
                        conn = sqlite3.connect(database.get_db_path())
                        c = conn.cursor()
                        c.execute("""
                            SELECT round, player_side, accuracy, presentation, deduction, total
                            FROM scores
                            WHERE match_uuid = ?
                        """, (match_uuid,))
                        rows = c.fetchall()
                        conn.close()
                    except Exception as db_err:
                        print(f"Error querying scores for Slide 2: {db_err}")
                        rows = []
                    
                scores_by_grp = {}
                for row in rows:
                    r_num, side, acc, pres, ded, tot = row
                    grp_key = (r_num, side)
                    if grp_key not in scores_by_grp:
                        scores_by_grp[grp_key] = {'acc': [], 'pres': [], 'total': [], 'ded': []}
                    scores_by_grp[grp_key]['acc'].append(acc)
                    scores_by_grp[grp_key]['pres'].append(pres)
                    scores_by_grp[grp_key]['total'].append(tot)
                    scores_by_grp[grp_key]['ded'].append(ded)
                    
                def calc_avg(scores):
                    if not scores: return 0.0
                    if len(scores) <= 3: return sum(scores) / len(scores)
                    else:
                        scores_only = list(scores)
                        scores_only.sort()
                        valid = scores_only[1:-1]
                        return sum(valid) / len(valid)
                        
                def calc_group_metrics(grp_data):
                    if not grp_data: return {'acc': 0.0, 'pres': 0.0, 'ded': 0.0, 'total': 0.0, 'raw_sum': 0.0}
                    accs = grp_data['acc']
                    press = grp_data['pres']
                    totals = grp_data['total']
                    deds = grp_data['ded']
                    
                    avg_acc = calc_avg(accs)
                    avg_pres = calc_avg(press)
                    deduction = max(deds) if deds else 0.0
                    
                    final = avg_acc + avg_pres - deduction
                    raw_sum = sum(totals)
                    
                    return {
                        'acc': avg_acc,
                        'pres': avg_pres,
                        'ded': deduction,
                        'total': final,
                        'raw_sum': raw_sum
                    }
                    
                chung_1r = calc_group_metrics(scores_by_grp.get((1, 0)))
                chung_2r = calc_group_metrics(scores_by_grp.get((2, 0)))
                hong_1r  = calc_group_metrics(scores_by_grp.get((1, 1)))
                hong_2r  = calc_group_metrics(scores_by_grp.get((2, 1)))
                
                # 計算雙輪加總與平均
                has_chung_1 = (chung_1r['raw_sum'] > 0.0)
                has_chung_2 = (chung_2r['raw_sum'] > 0.0)
                has_hong_1  = (hong_1r['raw_sum'] > 0.0)
                has_hong_2  = (hong_2r['raw_sum'] > 0.0)
                
                if has_chung_1 and has_chung_2:
                    chung_final = (chung_1r['total'] + chung_2r['total']) / 2
                    chung_pres = (chung_1r['pres'] + chung_2r['pres']) / 2
                elif has_chung_1:
                    chung_final = chung_1r['total']
                    chung_pres = chung_1r['pres']
                else:
                    chung_final = 0.0
                    chung_pres = 0.0
                    
                if has_hong_1 and has_hong_2:
                    hong_final = (hong_1r['total'] + hong_2r['total']) / 2
                    hong_pres = (hong_1r['pres'] + hong_2r['pres']) / 2
                elif has_hong_1:
                    hong_final = hong_1r['total']
                    hong_pres = hong_1r['pres']
                else:
                    hong_final = 0.0
                    hong_pres = 0.0
                    
                chung_raw_total = chung_1r['raw_sum'] + chung_2r['raw_sum']
                hong_raw_total  = hong_1r['raw_sum'] + hong_2r['raw_sum']
                
                # 版面參數計算
                W = self.width
                H = self.height
                Th = max(80, int(H * 0.155))
                Bh = max(120, int(H * 0.160))
                Mh = H - Th - Bh
                Jw = max(120, int(W * 0.08))
                Lw = int((W - Jw) / 2)
                Uh = int(Mh * 0.214)
                
                y_start = Th + Uh + 10
                y_end = H - Bh - 10
                avail_h = y_end - y_start
                
                font_final_size = int(avail_h * 0.22)
                font_raw_val_size = int(avail_h * 0.12)
                
                # --- 青方大字與表現性更新 ---
                x_left_chung = 20
                x_right_chung = Lw - 20
                
                y_final_chung = y_start + avail_h * 0.22
                y_box_center = y_start + avail_h * 0.56
                y_raw_val_chung = y_start + avail_h * 0.82
                
                self.canvas.itemconfig(self.txt_chung_final, text=format_pk_score(chung_final), font=("Microsoft JhengHei", font_final_size, "bold"), anchor="w")
                self.canvas.coords(self.txt_chung_final, x_left_chung + 40, y_final_chung)
                
                box_w = (x_right_chung - x_left_chung) * 0.38
                box_h = avail_h * 0.18
                y1_box = y_box_center - box_h / 2
                y2_box = y_box_center + box_h / 2
                
                font_box_val_size = font_raw_val_size
                
                x1_c_pres = x_left_chung + 40
                x2_c_pres = x1_c_pres + box_w
                self.canvas.coords(self.rect_chung_pres, x1_c_pres, y1_box, x2_c_pres, y2_box)
                self.canvas.itemconfig(self.txt_chung_pres_val, text=format_pk_score(chung_pres), font=("Microsoft JhengHei", font_box_val_size, "bold"))
                self.canvas.coords(self.txt_chung_pres_val, (x1_c_pres + x2_c_pres)/2, (y1_box + y2_box)/2)
                
                self.canvas.itemconfig(self.txt_chung_raw_val, text=f"{chung_raw_total:.1f}", font=("Microsoft JhengHei", font_raw_val_size, "bold"), anchor="w")
                self.canvas.coords(self.txt_chung_raw_val, x_left_chung + 40, y_raw_val_chung)
                
                # --- 紅方大字與表現性更新 ---
                x_left_hong = Lw + Jw + 20
                x_right_hong = W - 20
                
                y_final_hong = y_start + avail_h * 0.22
                y_box_center_hong = y_start + avail_h * 0.56
                y_raw_val_hong = y_start + avail_h * 0.82
                
                self.canvas.itemconfig(self.txt_hong_final, text=format_pk_score(hong_final), font=("Microsoft JhengHei", font_final_size, "bold"), anchor="e")
                self.canvas.coords(self.txt_hong_final, x_right_hong - 40, y_final_hong)
                
                y1_box_h = y_box_center_hong - box_h / 2
                y2_box_h = y_box_center_hong + box_h / 2
                
                x2_h_pres = x_right_hong - 40
                x1_h_pres = x2_h_pres - box_w
                self.canvas.coords(self.rect_hong_pres, x1_h_pres, y1_box_h, x2_h_pres, y2_box_h)
                self.canvas.itemconfig(self.txt_hong_pres_val, text=format_pk_score(hong_pres), font=("Microsoft JhengHei", font_box_val_size, "bold"))
                self.canvas.coords(self.txt_hong_pres_val, (x1_h_pres + x2_h_pres)/2, (y1_box_h + y2_box_h)/2)
                
                self.canvas.itemconfig(self.txt_hong_raw_val, text=f"{hong_raw_total:.1f}", font=("Microsoft JhengHei", font_raw_val_size, "bold"), anchor="e")
                self.canvas.coords(self.txt_hong_raw_val, x_right_hong - 40, y_raw_val_hong)
                
                # Winner Block
                win_text = "DRAW"
                win_color = "#ffffff"
                win_bg = "#444444"
                if chung_final > hong_final:
                    win_text = "WINNER\nBLUE"
                    win_color = "#00ccff"
                    win_bg = "#001a33"
                elif hong_final > chung_final:
                    win_text = "WINNER\nRED"
                    win_color = "#ff3366"
                    win_bg = "#330011"
                else:
                    # 第二決勝：表現力去尾平均分
                    if chung_pres > hong_pres:
                        win_text = "WINNER\nBLUE"
                        win_color = "#00ccff"
                        win_bg = "#001a33"
                    elif hong_pres > chung_pres:
                        win_text = "WINNER\nRED"
                        win_color = "#ff3366"
                        win_bg = "#330011"
                    else:
                        # 第三決勝：原始總分 (Raw Total)
                        if chung_raw_total > hong_raw_total:
                            win_text = "WINNER\nBLUE"
                            win_color = "#00ccff"
                            win_bg = "#001a33"
                        elif hong_raw_total > chung_raw_total:
                            win_text = "WINNER\nRED"
                            win_color = "#ff3366"
                            win_bg = "#330011"
                        # 三者皆同 → DRAW (維持預設值)

                if hasattr(self, 'rect_winner'):
                    cy = y_start + avail_h * 0.45
                    cx = Lw + Jw / 2
                    
                    win_box_h = avail_h * 0.65
                    font_size = int(win_box_h * 0.16)
                    
                    self.canvas.coords(self.txt_winner, cx, cy)
                    self.canvas.itemconfig(self.txt_winner, text=win_text, fill=win_color, font=("Microsoft JhengHei", font_size, "bold"))
                    
                    # 使用 bbox 動態計算文字範圍，確保框線完全包覆文字
                    bbox = self.canvas.bbox(self.txt_winner)
                    if bbox:
                        pad_x = 15
                        pad_y = 5
                        self.canvas.coords(self.rect_winner, bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y)
                    else:
                        win_box_w = max(Jw * 4.0, W * 0.3)
                        self.canvas.coords(self.rect_winner, cx - win_box_w/2, cy - win_box_h/2, cx + win_box_w/2, cy + win_box_h/2)
                        
                    self.canvas.itemconfig(self.rect_winner, fill=win_bg, outline=win_color, width=6)
                    
                    self.canvas.itemconfigure(self.rect_winner, state="normal")
                    self.canvas.itemconfigure(self.txt_winner, state="normal")
                    self.canvas.tag_raise(self.rect_winner)
                    self.canvas.tag_raise(self.txt_winner)

                # --- 底部表格明細更新 ---
                def update_bot_table_row(table_texts, row_idx, metrics):
                    if metrics['acc'] == 0.0 and metrics['pres'] == 0.0 and metrics['total'] == 0.0:
                        acc_str = "---"
                        pres_str = "---"
                        tot_str = "---"
                    else:
                        acc_str = format_pk_score(metrics['acc'])
                        pres_str = format_pk_score(metrics['pres'])
                        tot_str = format_pk_score(metrics['total'])
                    
                    # 第二欄：Accuracy (橘紅色)
                    self.canvas.itemconfig(table_texts[row_idx][1], text=acc_str, fill="#ff5533")
                    # 第三欄：Presentation (天藍色)
                    self.canvas.itemconfig(table_texts[row_idx][2], text=pres_str, fill="#00ccff")
                    # 第四欄：Final Score (亮綠色)
                    self.canvas.itemconfig(table_texts[row_idx][3], text=tot_str, fill="#39ff14")
                
                if hasattr(self, 'chung_bot_table_texts'):
                    update_bot_table_row(self.chung_bot_table_texts, 0, chung_1r)
                    update_bot_table_row(self.chung_bot_table_texts, 1, chung_2r)
                    update_bot_table_row(self.hong_bot_table_texts, 0, hong_1r)
                    update_bot_table_row(self.hong_bot_table_texts, 1, hong_2r)


    def _start_blink(self, side):
        """啟動指定方位的狀態燈閃爍效果（side: 'chung' 或 'hong'）"""
        # 若已在閃爍相同方位則直接返回，避免重複計時器
        if getattr(self, '_blink_side', None) == side and self._blink_timer_id is not None:
            return
        self._stop_blink()
        self._blink_side = side
        # 隱藏另一方的狀態燈
        if side == 'chung':
            self.canvas.itemconfigure(self.txt_hong_status_light, state="hidden")
        else:
            self.canvas.itemconfigure(self.txt_chung_status_light, state="hidden")
        self._blink_on = True
        self._do_blink()

    def _do_blink(self):
        """實際的閃爍動作，每 600ms 切換一次顯示/隱藏"""
        if not self.winfo_exists(): return
        side = getattr(self, '_blink_side', None)
        if side is None: return
        light_id = self.txt_chung_status_light if side == 'chung' else self.txt_hong_status_light
        if self._blink_on:
            self.canvas.itemconfigure(light_id, state="normal")
        else:
            self.canvas.itemconfigure(light_id, state="hidden")
        self._blink_on = not self._blink_on
        self._blink_timer_id = self.after(600, self._do_blink)

    def _stop_blink(self):
        """停止狀態燈閃爍並隱藏兩個狀態燈"""
        if self._blink_timer_id is not None:
            try: self.after_cancel(self._blink_timer_id)
            except: pass
            self._blink_timer_id = None
        self._blink_side = None
        if hasattr(self, 'txt_chung_status_light'):
            self.canvas.itemconfigure(self.txt_chung_status_light, state="hidden")
        if hasattr(self, 'txt_hong_status_light'):
            self.canvas.itemconfigure(self.txt_hong_status_light, state="hidden")

    def on_resize(self, event):
        if event.widget == self and (event.width != self.width or event.height != self.height):
            self._stop_blink()
            self.width = event.width
            self.height = event.height
            self.draw_background()
            self.refresh()

    def update_data(self, status, player_name, player_team, score):
        self.status_text = status
        self.refresh()

    def start_score_slide_show(self):
        self.stop_score_slide_show()
        duration = int(system_settings.get("slide_duration", 3)) * 1000
        self.score_slide_timer_id = self.after(duration, self.next_score_slide)
        
    def stop_score_slide_show(self):
        if hasattr(self, 'score_slide_timer_id') and self.score_slide_timer_id:
            try: self.after_cancel(self.score_slide_timer_id)
            except: pass
        self.score_slide_timer_id = None
        
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
        
        if gui:
            gui.last_proj_score_slide = self.current_score_slide
            gui.last_proj_slide_finished = False
        
        if self.current_score_slide == available_slides[-1]:
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

    def get_available_slides(self, gui):
        if not gui: return [0, 1]
        
        total_rounds = 2
        if gui.current_match_data:
            try: total_rounds = int(gui.current_match_data.get("Round", 2))
            except: pass
        if hasattr(gui, 'combo_poomsae_2') and str(gui.combo_poomsae_2['state']) == 'disabled':
            total_rounds = 1
            
        if total_rounds == 1:
            return [0, 1, 2]
        else:
            if gui.current_stage == 1:
                return [0, 1]
            else:
                return [0, 1, 2]
