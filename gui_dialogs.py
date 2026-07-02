import tkinter as tk
from tkinter import ttk, messagebox
import uuid
import qrcode
from PIL import Image, ImageTk
import config
import database

def open_settings(gui_parent):
    top = tk.Toplevel(gui_parent.root)
    top.title("系統設定")
    gui_parent.center_window(top, 660, 760)
    top.configure(bg="#f8f9fa")
    top.transient(gui_parent.root)
    top.grab_set()
    
    # 頂部精緻標題
    header_frame = tk.Frame(top, bg="#0099cc", height=50)
    header_frame.pack(fill="x", side="top")
    header_frame.pack_propagate(False)
    lbl_title = tk.Label(header_frame, text="⚙️ 系統參數設定", font=("Microsoft JhengHei", 12, "bold"), fg="#ffffff", bg="#0099cc")
    lbl_title.pack(pady=12)
    
    # 白底卡片容器
    card_frame = tk.Frame(top, bg="#ffffff", bd=1, relief="solid", highlightthickness=0)
    card_frame.pack(fill="both", expand=True, padx=20, pady=(15, 10))
    
    card_frame.columnconfigure(0, weight=1, minsize=120)
    card_frame.columnconfigure(1, weight=2)
    
    lbl_font = ("Microsoft JhengHei", 10, "bold")
    entry_font = ("Microsoft JhengHei", 10)
    lbl_fg = "#2c3e50"
    
    r = 0
    def create_section_header(title_text):
        nonlocal r
        lbl = tk.Label(card_frame, text=title_text, font=("Microsoft JhengHei", 9, "bold"), fg="#0099cc", bg="#ffffff", anchor="w")
        lbl.grid(row=r, column=0, columnspan=2, sticky="w", padx=(15, 0), pady=(12, 4))
        r += 1

    def create_form_row(label_text, var):
        nonlocal r
        lbl = tk.Label(card_frame, text=label_text, font=lbl_font, fg=lbl_fg, bg="#ffffff", anchor="e")
        lbl.grid(row=r, column=0, sticky="e", padx=(15, 8), pady=6)
        
        widget = tk.Entry(card_frame, textvariable=var, width=25, font=entry_font, relief="solid", bd=1, bg="#ffffff", highlightthickness=1)
        widget.config(highlightbackground="#cccccc", highlightcolor="#0099cc")
        widget.grid(row=r, column=1, sticky="w", padx=(8, 15), pady=6)
        r += 1
        return widget

    def create_button_selector_row(label_text, var, options, display_texts=None, btn_width=5):
        nonlocal r
        lbl = tk.Label(card_frame, text=label_text, font=lbl_font, fg=lbl_fg, bg="#ffffff", anchor="e")
        lbl.grid(row=r, column=0, sticky="e", padx=(15, 8), pady=6)
        
        btn_container = tk.Frame(card_frame, bg="#ffffff")
        btn_container.grid(row=r, column=1, sticky="w", padx=(8, 15), pady=6)
        
        buttons = []
        if display_texts is None:
            display_texts = [str(opt) for opt in options]
            
        def select_option(val):
            var.set(val)
            update_button_styles()
            
        def update_button_styles():
            current_val = var.get()
            for btn, opt_val in buttons:
                if str(current_val) == str(opt_val):
                    btn.config(bg="#0099cc", fg="white", font=("Microsoft JhengHei", 9, "bold"))
                else:
                    btn.config(bg="#f1f2f6", fg="#2c3e50", font=("Microsoft JhengHei", 9))
                    
        for opt_val, disp_text in zip(options, display_texts):
            btn = tk.Button(
                btn_container, 
                text=disp_text, 
                width=btn_width, 
                height=1, 
                padx=2, 
                pady=1,
                cursor="hand2",
                relief="flat",
                bd=0,
                highlightthickness=0
            )
            btn.config(command=lambda v=opt_val: select_option(v))
            btn.pack(side="left", padx=2)
            buttons.append((btn, opt_val))
            
            def make_hover(b, val):
                def on_enter(e):
                    if str(var.get()) != str(val):
                        b.config(bg="#dfe4ea")
                def on_leave(e):
                    if str(var.get()) != str(val):
                        b.config(bg="#f1f2f6")
                b.bind("<Enter>", on_enter)
                b.bind("<Leave>", on_leave)
            make_hover(btn, opt_val)
            
        update_button_styles()
        r += 1

    # 1. 基礎與場地設定
    create_section_header("📋 基礎與場地設定")
    
    var_name = tk.StringVar(value=config.system_settings["tournament_name"])
    create_form_row("賽事名稱:", var_name)
    
    var_court = tk.IntVar(value=config.system_settings["court_no"])
    create_form_row("場地編號:", var_court)
    
    # 2. 計分與展示設定
    create_section_header("⏱️ 計分與展示設定")
    
    var_judge = tk.IntVar(value=config.system_settings["judge_count"])
    create_button_selector_row("啟用裁判人數:", var_judge, [1, 3, 5, 7], ["1 人", "3 人", "5 人", "7 人"], btn_width=5)
    
    var_cd = tk.IntVar(value=config.system_settings["countdown_sec"])
    create_form_row("倒數秒數 (秒):", var_cd)
    
    var_slide = tk.IntVar(value=config.system_settings["slide_duration"])
    create_button_selector_row("展示每頁秒數:", var_slide, [1, 2, 3, 4, 5], ["1秒", "2秒", "3秒", "4秒", "5秒"], btn_width=5)
    
    # 2.5 PK 賽制設定
    create_section_header("🏆 PK 賽制專屬設定")
    
    var_pk_seq = tk.IntVar(value=config.system_settings.get("pk_sequence_mode", 1))
    create_button_selector_row("打分順序模式:", var_pk_seq, [0, 1, 2], ["同時上場", "交叉上場", "依序上場"], btn_width=8)
    
    # 3. 網路與雲端設定
    create_section_header("🌐 網路與雲端設定")
    
    var_cloud = tk.StringVar(value="啟用" if config.system_settings.get("enable_cloud", True) else "停用")
    create_button_selector_row("啟用雲端連線:", var_cloud, ["啟用", "停用"], ["啟用", "停用"], btn_width=6)
    
    # 4. 品勢型場設定
    create_section_header("🥋 品勢型場設定")
    
    var_excel = tk.StringVar(value=config.system_settings.get("poomsae_excel_path", ""))
    
    lbl_excel = tk.Label(card_frame, text="型場 Excel 路徑:", font=lbl_font, fg=lbl_fg, bg="#ffffff", anchor="e")
    lbl_excel.grid(row=r, column=0, sticky="e", padx=(15, 8), pady=6)
    
    excel_container = tk.Frame(card_frame, bg="#ffffff")
    excel_container.grid(row=r, column=1, sticky="ew", padx=(8, 15), pady=6)
    
    entry_excel = tk.Entry(excel_container, textvariable=var_excel, width=25, font=entry_font, relief="solid", bd=1, bg="#ffffff", highlightthickness=1)
    entry_excel.config(highlightbackground="#cccccc", highlightcolor="#0099cc")
    entry_excel.pack(side="left", fill="x", expand=True, padx=(0, 5))
    
    def browse_file():
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            parent=top,
            title="選擇型場 Excel 檔案",
            filetypes=[("Excel Files", "*.xlsx;*.xls"), ("All Files", "*.*")]
        )
        if file_path:
            var_excel.set(file_path)
            
    btn_browse = tk.Button(
        excel_container, 
        text="瀏覽...", 
        font=("Microsoft JhengHei", 9),
        bg="#f1f2f6", 
        fg="#2c3e50", 
        relief="flat",
        bd=0,
        cursor="hand2"
    )
    btn_browse.config(command=browse_file)
    btn_browse.pack(side="left")
    gui_parent.setup_hover(btn_browse, "#dfe4ea", "#f1f2f6")
    
    r += 1
    
    lbl_range = tk.Label(card_frame, text="抽籤範圍限制:", font=lbl_font, fg=lbl_fg, bg="#ffffff", anchor="e")
    lbl_range.grid(row=r, column=0, sticky="e", padx=(15, 8), pady=6)
    
    range_container = tk.Frame(card_frame, bg="#ffffff")
    range_container.grid(row=r, column=1, sticky="w", padx=(8, 15), pady=6)
    
    curr_start = config.system_settings.get("draw_range_start", "")
    curr_end = config.system_settings.get("draw_range_end", "")
    
    poomsae_opts = getattr(gui_parent, 'poomsae_list', [""])
    
    # 舊資料相容：若為數字，則轉換成對應 index 的型場名稱
    try:
        idx_s = int(curr_start)
        if 0 <= idx_s < len(poomsae_opts):
            curr_start = poomsae_opts[idx_s]
        else:
            curr_start = ""
    except ValueError:
        pass
        
    try:
        idx_e = int(curr_end)
        if 0 <= idx_e < len(poomsae_opts):
            curr_end = poomsae_opts[idx_e]
        else:
            curr_end = ""
    except ValueError:
        pass
        
    var_start = tk.StringVar(value=curr_start)
    var_end = tk.StringVar(value=curr_end)
    
    combo_start = ttk.Combobox(range_container, textvariable=var_start, values=poomsae_opts, font=entry_font, state="readonly", width=15)
    combo_start.pack(side="left")
    
    lbl_to = tk.Label(range_container, text=" 至 ", font=lbl_font, fg=lbl_fg, bg="#ffffff")
    lbl_to.pack(side="left", padx=3)
    
    combo_end = ttk.Combobox(range_container, textvariable=var_end, values=poomsae_opts, font=entry_font, state="readonly", width=15)
    combo_end.pack(side="left")
    
    r += 1
    
    # 5. 啟用型場抽選按鈕
    var_show_draw = tk.StringVar(value="啟用" if config.system_settings.get("show_draw_button", True) else "停用")
    create_button_selector_row("啟用抽選按鈕:", var_show_draw, ["啟用", "停用"], ["啟用", "停用"], btn_width=6)
    
    # 6. 清除型場記憶按鈕
    lbl_clean = tk.Label(card_frame, text="型場記憶管理:", font=lbl_font, fg=lbl_fg, bg="#ffffff", anchor="e")
    lbl_clean.grid(row=r, column=0, sticky="e", padx=(15, 8), pady=6)
    
    clean_container = tk.Frame(card_frame, bg="#ffffff")
    clean_container.grid(row=r, column=1, sticky="w", padx=(8, 15), pady=6)
    
    def clear_memory():
        confirm = messagebox.askyesno(
            "清除確認",
            "您確定要清除所有賽事與場次的型場記憶紀錄嗎？\n(清除後所有場次的自動帶入功能將重設)",
            parent=top
        )
        if confirm:
            config.system_settings["session_poomsae"] = {}
            config.save_settings()
            # 即時重置主畫面下拉選單
            if hasattr(gui_parent, 'combo_poomsae_1'):
                gui_parent.combo_poomsae_1.current(0)
            if hasattr(gui_parent, 'combo_poomsae_2'):
                gui_parent.combo_poomsae_2.current(0)
            if hasattr(gui_parent, 'proj_window') and gui_parent.proj_window and gui_parent.proj_window.winfo_exists():
                gui_parent.proj_window.refresh()
            gui_parent.update_button_states()
            messagebox.showinfo("成功", "已成功清除所有型場記憶紀錄！", parent=top)
            
    btn_clear = tk.Button(
        clean_container, 
        text="🗑️ 清除所有型場記憶", 
        font=("Microsoft JhengHei", 9, "bold"),
        bg="#e74c3c", 
        fg="white", 
        relief="flat",
        bd=0,
        cursor="hand2"
    )
    btn_clear.config(command=clear_memory)
    btn_clear.pack(side="left")
    gui_parent.setup_hover(btn_clear, "#c0392b", "#e74c3c")
    
    r += 1
    
    # 底部按鈕區
    btn_frame = tk.Frame(top, bg="#f8f9fa")
    btn_frame.pack(fill="x", side="bottom", pady=(0, 15))
    
    def save():
        try:
            cd_val = var_cd.get()
            slide_val = var_slide.get()
            judge_val = var_judge.get()
            court_val = var_court.get()
            name_val = var_name.get().strip()
            cloud_val = var_cloud.get()
            
            if not name_val:
                messagebox.showerror("錯誤", "賽事名稱不能為空", parent=top)
                return
            
            config.system_settings["countdown_sec"] = cd_val
            config.system_settings["slide_duration"] = slide_val
            config.system_settings["judge_count"] = judge_val
            config.system_settings["court_no"] = court_val
            config.system_settings["pk_sequence_mode"] = var_pk_seq.get()
            
            if name_val != config.system_settings["tournament_name"]:
                config.system_settings["tournament_name"] = name_val
                database.set_tournament_db(name_val)
            
            old_enable = config.system_settings.get("enable_cloud", True)
            new_enable = (cloud_val == "啟用")
            config.system_settings["enable_cloud"] = new_enable
            
            excel_val = var_excel.get().strip()
            config.system_settings["poomsae_excel_path"] = excel_val
            
            # 驗證起始型場順序不能在結束型場之後
            start_val = var_start.get()
            end_val = var_end.get()
            
            poomsae_opts_tmp = getattr(gui_parent, 'poomsae_list', [""])
            try:
                start_idx = poomsae_opts_tmp.index(start_val) if start_val in poomsae_opts_tmp else 0
                end_idx = poomsae_opts_tmp.index(end_val) if end_val in poomsae_opts_tmp else 0
                if start_idx > 0 and end_idx > 0 and start_idx > end_idx:
                    messagebox.showerror("錯誤", "起始型場順序不能在結束型場之後", parent=top)
                    return
            except ValueError:
                pass
                
            config.system_settings["draw_range_start"] = start_val
            config.system_settings["draw_range_end"] = end_val
            config.system_settings["show_draw_button"] = (var_show_draw.get() == "啟用")
            
            config.save_settings() # 儲存到 JSON
            gui_parent.update_court_label()
            gui_parent.refresh_judge_slots()
            
            import web_server
            web_server.kick_invalid_judges()
            
            # 更新主畫面的型場下拉選單
            if hasattr(gui_parent, 'update_poomsae_list'):
                gui_parent.update_poomsae_list()
                
            # 更新按鈕顯示隱藏
            if hasattr(gui_parent, 'refresh_bottom_buttons'):
                gui_parent.refresh_bottom_buttons()
            
            # 觸發雲端通道動態重啟或關閉
            if old_enable != new_enable:
                if new_enable:
                    if hasattr(gui_parent, 'start_tunnel_callback') and gui_parent.start_tunnel_callback:
                        import threading
                        threading.Thread(target=gui_parent.start_tunnel_callback, daemon=True).start()
                else:
                    if hasattr(gui_parent, 'stop_tunnel_callback') and gui_parent.stop_tunnel_callback:
                        gui_parent.stop_tunnel_callback()
            
            messagebox.showinfo("設定", "設定已成功儲存與應用！", parent=top)
            top.destroy()
        except Exception as ex:
            messagebox.showerror("錯誤", f"儲存失敗，請檢查輸入內容是否為有效數字。\n{ex}", parent=top)

    # 取消與儲存按鈕
    btn_cancel = tk.Button(btn_frame, text="取消設定", font=("Microsoft JhengHei", 10, "bold"), fg="#ffffff", bg="#7f8c8d", relief="flat", width=12, height=1, command=top.destroy)
    btn_cancel.pack(side="left", padx=30)
    gui_parent.setup_hover(btn_cancel, "#95a5a6", "#7f8c8d")
    
    btn_save = tk.Button(btn_frame, text="保存並應用", font=("Microsoft JhengHei", 10, "bold"), fg="#ffffff", bg="#0099cc", relief="flat", width=12, height=1, command=save)
    btn_save.pack(side="right", padx=30)
    gui_parent.setup_hover(btn_save, "#00b0f0", "#0099cc")


def show_qr_popup(gui_parent, event=None):
    try:
        enable_cloud = config.system_settings.get("enable_cloud", True)
        
        top = tk.Toplevel(gui_parent.root)
        top.title("掃描連線")
        
        # 依據是否啟用雲端動態調整寬度
        window_width = 860 if enable_cloud else 550
        window_height = 600
        gui_parent.center_window(top, window_width, window_height)
        top.configure(bg="white")
        
        lbl_title = tk.Label(top, text="📱 請裁判使用手機掃描以下二維碼連線", font=("Microsoft JhengHei", 16, "bold"), bg="white")
        lbl_title.pack(pady=15)
        
        # 建立左右或單一容器
        container = tk.Frame(top, bg="white")
        container.pack(fill="both", expand=True, padx=20, pady=5)
        
        # 偵測 Pillow 的縮放過濾器名稱 (相容新舊版本)
        try:
            resample_filter = Image.Resampling.LANCZOS
        except AttributeError:
            resample_filter = Image.ANTIALIAS
        
        # 1. 區網連線 (區域網路 Wi-Fi)
        left_frame = tk.Frame(container, bg="white", padx=10, pady=10, bd=1, relief="groove")
        left_frame.pack(side="left", fill="both", expand=True, padx=10)
        
        lbl_left_title = tk.Label(left_frame, text="⚡ 區網連線 (推薦/超低延遲)", font=("Microsoft JhengHei", 12, "bold"), bg="white", fg="#27ae60")
        lbl_left_title.pack(pady=5)
        
        local_ip = gui_parent.get_local_ip()
        local_url = f"http://{local_ip}:5003"
        
        qr_local = qrcode.QRCode(version=1, box_size=8, border=2)
        qr_local.add_data(local_url)
        qr_local.make(fit=True)
        img_local = qr_local.make_image(fill_color="black", back_color="white")
        img_local = img_local.resize((260, 260), resample_filter)
        qr_local_photo = ImageTk.PhotoImage(img_local)
        
        lbl_qr_local = tk.Label(left_frame, image=qr_local_photo, bg="white")
        lbl_qr_local.image = qr_local_photo  # keep reference
        lbl_qr_local.pack(expand=True)
        
        lbl_local_url = tk.Label(left_frame, text=local_url, font=("Consolas", 9, "bold"), bg="white", fg="blue")
        lbl_local_url.pack(pady=5)
        
        lbl_local_tip = tk.Label(left_frame, text="* 手機需與本主控電腦連接同一個 Wi-Fi 分享器", font=("Microsoft JhengHei", 8), bg="white", fg="gray")
        lbl_local_tip.pack(pady=2)

        # 2. 雲端連線 (僅在啟用雲端時顯示)
        if enable_cloud:
            right_frame = tk.Frame(container, bg="white", padx=10, pady=10, bd=1, relief="groove")
            right_frame.pack(side="right", fill="both", expand=True, padx=10)
            
            lbl_right_title = tk.Label(right_frame, text="🌐 雲端連線 (網際網路安全通道)", font=("Microsoft JhengHei", 12, "bold"), bg="white", fg="#8e58ff")
            lbl_right_title.pack(pady=5)
            
            cloud_url = gui_parent.cloudflare_url if (hasattr(gui_parent, 'cloudflare_url') and gui_parent.cloudflare_url) else ""
            
            if cloud_url:
                qr_cloud = qrcode.QRCode(version=1, box_size=8, border=2)
                qr_cloud.add_data(cloud_url)
                qr_cloud.make(fit=True)
                img_cloud = qr_cloud.make_image(fill_color="black", back_color="white")
                img_cloud = img_cloud.resize((260, 260), resample_filter)
                qr_cloud_photo = ImageTk.PhotoImage(img_cloud)
                
                lbl_qr_cloud = tk.Label(right_frame, image=qr_cloud_photo, bg="white")
                lbl_qr_cloud.image = qr_cloud_photo  # keep reference
                lbl_qr_cloud.pack(expand=True)
                
                lbl_cloud_url = tk.Label(right_frame, text=cloud_url, font=("Consolas", 9, "bold"), bg="white", fg="purple")
                lbl_cloud_url.pack(pady=5)
            else:
                lbl_no_cloud = tk.Label(right_frame, text="通道尚未啟動\n或啟動失敗", font=("Microsoft JhengHei", 12), bg="white", fg="red")
                lbl_no_cloud.pack(expand=True)
                
            lbl_cloud_tip = tk.Label(right_frame, text="* 適用於無法連接同一個 Wi-Fi 時跨網路連線\n* 手機與本主控電腦皆必須連通網際網路 (可開 4G/5G)", font=("Microsoft JhengHei", 8), bg="white", fg="gray", justify="left")
            lbl_cloud_tip.pack(pady=2)
            
        return top
    except Exception as e:
        print(f"QR Code 彈窗失敗: {e}")
        return None


def open_match_editor(gui_parent, match_id=None):
    top = tk.Toplevel(gui_parent.root)
    is_edit = bool(match_id)
    top.title("編輯比賽" if is_edit else "建立新比賽")
    gui_parent.center_window(top, 700, 540)
    top.configure(bg="#f8f9fa")
    top.transient(gui_parent.root)
    top.grab_set()

    # 頂部標題
    header_frame = tk.Frame(top, bg="#0099cc", height=50)
    header_frame.pack(fill="x", side="top")
    header_frame.pack_propagate(False)
    title_text = "📝 編輯比賽資料" if is_edit else "➕ 建立新比賽"
    lbl_title = tk.Label(header_frame, text=title_text, font=("Microsoft JhengHei", 12, "bold"), fg="#ffffff", bg="#0099cc")
    lbl_title.pack(pady=12)

    # 欄位變數（籤號 No 放入 fields，但不在基本資訊區）
    fields = {
        "Game": tk.StringVar(value="0"), "Court": tk.StringVar(value="1"),
        "No": tk.StringVar(), "Round": tk.StringVar(value="2"),
        "Type": tk.StringVar(), "Category": tk.StringVar(),
        "Division": tk.StringVar(), "Phase": tk.StringVar(),
        "C_Name": tk.StringVar(), "C_NOC": tk.StringVar(), "C_Team": tk.StringVar(),
        "H_Name": tk.StringVar(), "H_NOC": tk.StringVar(), "H_Team": tk.StringVar()
    }
    var_session = tk.StringVar()

    # 載入現有資料
    if match_id and match_id in gui_parent.imported_matches:
        data = gui_parent.imported_matches[match_id]
        for key in fields:
            if key in data:
                fields[key].set(str(data[key]))
        var_session.set(data.get("SourceFile", ""))
    else:
        # 新建模式：若主畫面已選取場次，自動帶入
        current_session = gui_parent.cb_session_select.get().strip()
        if current_session:
            var_session.set(current_session)

    # 主容器
    container = tk.Frame(top, bg="#f8f9fa", padx=15, pady=8)
    container.pack(fill="both", expand=True)

    lbl_style = {"font": ("Microsoft JhengHei", 9, "bold"), "fg": "#2c3e50", "bg": "#ffffff"}
    entry_style = {"font": ("Microsoft JhengHei", 9), "relief": "solid", "bd": 1, "bg": "#ffffff", "highlightthickness": 1}

    def config_entry_border(entry, color="#0099cc"):
        entry.config(highlightbackground="#cccccc", highlightcolor=color)

    # ── 0. 場次設定 ──
    sess_frame = tk.LabelFrame(container, text="🗂️ 場次設定",
                                font=("Microsoft JhengHei", 10, "bold"),
                                fg="#7f5af0", bg="#f3f0ff", bd=1, relief="solid", padx=10, pady=8)
    sess_frame.pack(fill="x", pady=(0, 8))
    sess_lbl_style = {"font": ("Microsoft JhengHei", 9, "bold"), "fg": "#2c3e50", "bg": "#f3f0ff"}

    tk.Label(sess_frame, text="場次名稱:", **sess_lbl_style).grid(row=0, column=0, sticky="e", padx=(5, 10))

    if is_edit:
        lbl_sess_val = tk.Label(sess_frame, textvariable=var_session,
                                font=("Microsoft JhengHei", 9), fg="#555555", bg="#f3f0ff", anchor="w")
        lbl_sess_val.grid(row=0, column=1, sticky="w")
        tk.Label(sess_frame, text="（編輯模式下場次不可變更）",
                 font=("Microsoft JhengHei", 8), fg="#aaaaaa", bg="#f3f0ff").grid(row=0, column=2, sticky="w", padx=(12, 0))
    else:
        existing_sessions = sorted(
            set(d.get("SourceFile", "") for d in gui_parent.imported_matches.values()
                if d.get("SourceFile", "") and d.get("SourceFile", "") != "手動建立"),
            key=gui_parent.session_sort_key
        )
        sess_cb = ttk.Combobox(sess_frame, textvariable=var_session, values=existing_sessions,
                               font=("Microsoft JhengHei", 9), width=28)
        sess_cb.grid(row=0, column=1, sticky="w")
        tk.Label(sess_frame, text="（可輸入新場次名稱，或從清單選擇現有場次）",
                 font=("Microsoft JhengHei", 8), fg="#888888", bg="#f3f0ff").grid(row=0, column=2, sticky="w", padx=(10, 0))

        def on_session_selected(event=None):
            selected = var_session.get().strip()
            if not selected:
                return
            max_no = 0
            found_data = False
            for uid, mdata in gui_parent.imported_matches.items():
                if mdata.get("SourceFile", "") == selected:
                    # 計算最大籤號
                    try:
                        no_val = int(mdata.get("No", 0))
                        if no_val > max_no:
                            max_no = no_val
                    except Exception:
                        pass
                    # 帶入第一筆資訊
                    if not found_data:
                        try:
                            mode_cb.current(int(mdata.get("Game", 0)))
                        except Exception:
                            mode_cb.current(0)
                        fields["Court"].set(str(mdata.get("Court", "")))
                        fields["Round"].set(str(mdata.get("Round", "")))
                        fields["Type"].set(str(mdata.get("Type", "")))
                        fields["Category"].set(str(mdata.get("Category", "")))
                        fields["Division"].set(str(mdata.get("Division", "")))
                        fields["Phase"].set(str(mdata.get("Phase", "")))
                        found_data = True
            
            # 若不是編輯模式，設定最大籤號 + 1
            if not is_edit:
                fields["No"].set(str(max_no + 1))

        sess_cb.bind("<<ComboboxSelected>>", on_session_selected)

    # ── 1. 基本賽事資訊（已移除籤號） ──
    info_frame = tk.LabelFrame(container, text="📋 基本賽事資訊",
                                font=("Microsoft JhengHei", 10, "bold"),
                                fg="#2c3e50", bg="#ffffff", bd=1, relief="solid", padx=10, pady=8)
    info_frame.pack(fill="x", pady=(0, 6))
    info_frame.columnconfigure(1, weight=1)
    info_frame.columnconfigure(3, weight=1)

    # Row 0: 賽制模式 & 場地編號
    tk.Label(info_frame, text="賽制模式:", **lbl_style).grid(row=0, column=0, sticky="e", padx=(5, 10), pady=5)
    mode_cb = ttk.Combobox(info_frame, values=["Cutoff", "PK", "Freestyle", "Fast"],
                            state="readonly", font=("Microsoft JhengHei", 9), width=18)
    try:
        mode_cb.current(int(fields["Game"].get()))
    except Exception:
        mode_cb.current(0)
    mode_cb.grid(row=0, column=1, sticky="w", padx=(0, 15), pady=5)

    tk.Label(info_frame, text="場地編號 (Court):", **lbl_style).grid(row=0, column=2, sticky="e", padx=(5, 10), pady=5)
    court_entry = tk.Entry(info_frame, textvariable=fields["Court"], width=20, **entry_style)
    config_entry_border(court_entry)
    court_entry.grid(row=0, column=3, sticky="w", pady=5)

    # Row 1: 籤號 & 輪次
    tk.Label(info_frame, text="籤號 (No):", **lbl_style).grid(row=1, column=0, sticky="e", padx=(5, 10), pady=5)
    no_entry = tk.Entry(info_frame, textvariable=fields["No"], width=20, **entry_style)
    config_entry_border(no_entry)
    no_entry.grid(row=1, column=1, sticky="w", padx=(0, 15), pady=5)

    tk.Label(info_frame, text="輪次 (Round):", **lbl_style).grid(row=1, column=2, sticky="e", padx=(5, 10), pady=5)
    round_entry = tk.Entry(info_frame, textvariable=fields["Round"], width=20, **entry_style)
    config_entry_border(round_entry)
    round_entry.grid(row=1, column=3, sticky="w", pady=5)

    # Row 2: 組別類型 & 項目名稱
    tk.Label(info_frame, text="組別類型 (Type):", **lbl_style).grid(row=2, column=0, sticky="e", padx=(5, 10), pady=5)
    type_entry = tk.Entry(info_frame, textvariable=fields["Type"], width=20, **entry_style)
    config_entry_border(type_entry)
    type_entry.grid(row=2, column=1, sticky="w", padx=(0, 15), pady=5)

    tk.Label(info_frame, text="項目名稱 (Category):", **lbl_style).grid(row=2, column=2, sticky="e", padx=(5, 10), pady=5)
    cat_entry = tk.Entry(info_frame, textvariable=fields["Category"], width=20, **entry_style)
    config_entry_border(cat_entry)
    cat_entry.grid(row=2, column=3, sticky="w", pady=5)

    # Row 3: 組別分組 & 組別階段
    tk.Label(info_frame, text="組別分組 (Division):", **lbl_style).grid(row=3, column=0, sticky="e", padx=(5, 10), pady=5)
    div_entry = tk.Entry(info_frame, textvariable=fields["Division"], width=20, **entry_style)
    config_entry_border(div_entry)
    div_entry.grid(row=3, column=1, sticky="w", padx=(0, 15), pady=5)

    tk.Label(info_frame, text="組別階段 (Phase):", **lbl_style).grid(row=3, column=2, sticky="e", padx=(5, 10), pady=5)
    phase_entry = tk.Entry(info_frame, textvariable=fields["Phase"], width=20, **entry_style)
    config_entry_border(phase_entry)
    phase_entry.grid(row=3, column=3, sticky="w", pady=5)

    # ── 3. 青方選手資訊 ──
    c_frame = tk.LabelFrame(container, text="🔵 青方選手資訊 (Chung)",
                             font=("Microsoft JhengHei", 10, "bold"),
                             fg="#0099cc", bg="#e6f7ff", bd=1, relief="solid", padx=10, pady=8)
    c_frame.pack(fill="x", pady=(0, 6))
    c_frame.columnconfigure(1, weight=2)
    c_frame.columnconfigure(3, weight=1)
    c_frame.columnconfigure(5, weight=2)

    c_lbl_style = {"font": ("Microsoft JhengHei", 9, "bold"), "fg": "#2c3e50", "bg": "#e6f7ff"}

    tk.Label(c_frame, text="姓名:", **c_lbl_style).grid(row=0, column=0, sticky="e", padx=(2, 5))
    c_name_entry = tk.Entry(c_frame, textvariable=fields["C_Name"], **entry_style)
    config_entry_border(c_name_entry, "#0099cc")
    c_name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))

    tk.Label(c_frame, text="國家代碼:", **c_lbl_style).grid(row=0, column=2, sticky="e", padx=(2, 5))
    c_noc_entry = tk.Entry(c_frame, textvariable=fields["C_NOC"], **entry_style)
    config_entry_border(c_noc_entry, "#0099cc")
    c_noc_entry.grid(row=0, column=3, sticky="ew", padx=(0, 10))

    tk.Label(c_frame, text="單位名稱:", **c_lbl_style).grid(row=0, column=4, sticky="e", padx=(2, 5))
    c_team_entry = tk.Entry(c_frame, textvariable=fields["C_Team"], **entry_style)
    config_entry_border(c_team_entry, "#0099cc")
    c_team_entry.grid(row=0, column=5, sticky="ew")

    # ── 3. 紅方選手資訊 ──
    h_frame = tk.LabelFrame(container, text="🔴 紅方選手資訊 (Hong - PK賽制用)",
                             font=("Microsoft JhengHei", 10, "bold"),
                             fg="#cc0000", bg="#fff1f0", bd=1, relief="solid", padx=10, pady=8)
    h_frame.pack(fill="x", pady=(0, 5))
    h_frame.columnconfigure(1, weight=2)
    h_frame.columnconfigure(3, weight=1)
    h_frame.columnconfigure(5, weight=2)

    h_lbl_style = {"font": ("Microsoft JhengHei", 9, "bold"), "fg": "#2c3e50", "bg": "#fff1f0"}

    tk.Label(h_frame, text="姓名:", **h_lbl_style).grid(row=0, column=0, sticky="e", padx=(2, 5))
    h_name_entry = tk.Entry(h_frame, textvariable=fields["H_Name"], **entry_style)
    config_entry_border(h_name_entry, "#cc0000")
    h_name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))

    tk.Label(h_frame, text="國家代碼:", **h_lbl_style).grid(row=0, column=2, sticky="e", padx=(2, 5))
    h_noc_entry = tk.Entry(h_frame, textvariable=fields["H_NOC"], **entry_style)
    config_entry_border(h_noc_entry, "#cc0000")
    h_noc_entry.grid(row=0, column=3, sticky="ew", padx=(0, 10))

    tk.Label(h_frame, text="單位名稱:", **h_lbl_style).grid(row=0, column=4, sticky="e", padx=(2, 5))
    h_team_entry = tk.Entry(h_frame, textvariable=fields["H_Team"], **entry_style)
    config_entry_border(h_team_entry, "#cc0000")
    h_team_entry.grid(row=0, column=5, sticky="ew")

    # 底部按鈕
    btn_frame = tk.Frame(top, bg="#f8f9fa")
    btn_frame.pack(fill="x", side="bottom", pady=12)

    def save_match():
        mode_idx = mode_cb.current()
        new_data = {k: v.get().strip() for k, v in fields.items()}
        new_data["Game"] = mode_idx
        new_data["Status"] = "Ready"

        if not new_data["C_Name"] and mode_idx != 3:
            if not messagebox.askyesno("提示", "青方姓名目前為空，是否確定儲存？", parent=top):
                return

        if match_id:
            # 編輯模式：保留原有 SourceFile 與狀態，回寫 Excel
            original = gui_parent.imported_matches.get(match_id, {})
            new_data["SourceFile"] = original.get("SourceFile", "手動建立")
            new_data["Status"] = original.get("Status", "Ready")
            gui_parent.imported_matches[match_id] = new_data
            import threading
            threading.Thread(
                target=gui_parent.write_match_back_to_excel,
                args=(match_id, new_data),
                daemon=True
            ).start()
        else:
            # 新建模式：需要場次名稱，並同步 append 到 Excel
            session_name = var_session.get().strip()
            if not session_name:
                messagebox.showerror("錯誤", "請先填寫「場次名稱」，才能建立新比賽。", parent=top)
                return

            new_data["SourceFile"] = session_name

            row_index = gui_parent.append_match_to_excel(session_name, new_data)

            if row_index is not None:
                uid = session_name + "_" + str(row_index)
            else:
                uid = str(uuid.uuid4())

            gui_parent.imported_matches[uid] = new_data
            # 切換到該場次
            gui_parent.cb_session_select.set(session_name)

        gui_parent.update_session_combobox()
        gui_parent.update_tree_columns()
        top.destroy()

    btn_cancel = tk.Button(btn_frame, text="取消編輯" if is_edit else "取消",
                           font=("Microsoft JhengHei", 10, "bold"), fg="#ffffff", bg="#7f8c8d",
                           relief="flat", width=12, height=1, command=top.destroy)
    btn_cancel.pack(side="left", padx=45)
    gui_parent.setup_hover(btn_cancel, "#95a5a6", "#7f8c8d")

    btn_save = tk.Button(btn_frame, text="儲存並關閉",
                         font=("Microsoft JhengHei", 10, "bold"), fg="#ffffff", bg="#0099cc",
                         relief="flat", width=12, height=1, command=save_match)
    btn_save.pack(side="right", padx=45)
    gui_parent.setup_hover(btn_save, "#00b0f0", "#0099cc")

    # 新建模式：若預設場次已有資料，立即帶入基本資訊與最大籤號
    if not is_edit and var_session.get():
        on_session_selected()


