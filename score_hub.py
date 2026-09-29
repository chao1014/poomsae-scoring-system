"""Central LAN record viewer. Run independently of the scoring application."""
import os
import sqlite3
import hashlib
import webbrowser
from log_view import parse_log
from pathlib import Path
import socket
import shutil
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from lan_records import make_receiver, PORT
from hub_database import HubDatabaseManager
from folder_paths import localized_folder

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent

def prepare_data_directory(root):
    """Create the hub data folder and migrate files from earlier versions."""
    data_dir = localized_folder('後台資料庫', ('後台資料', 'score_hub_data'), root=root, create=True)
    old_database = root / 'score_hub.db'
    new_database = data_dir / 'score_hub.db'
    if old_database.exists() and not new_database.exists():
        shutil.move(str(old_database), str(new_database))
    new_previews = data_dir / '紀錄預覽'
    for old_previews in (data_dir / 'log_previews', root / 'hub_log_previews'):
        if old_previews.exists() and not new_previews.exists():
            shutil.move(str(old_previews), str(new_previews))
    return data_dir

def open_log_file(path):
    if os.name == 'nt':
        os.startfile(str(path.resolve()))
    elif not webbrowser.open(path.resolve().as_uri()):
        raise OSError('找不到可開啟 LOG 的瀏覽器，請設定預設瀏覽器。')


def center_window(window, width, height):
    window.update_idletasks()
    x = max(0, (window.winfo_screenwidth() - width) // 2)
    y = max(0, (window.winfo_screenheight() - height) // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')


class ScoreHub(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('多場地比分紀錄後台')
        self.geometry('1050x680')
        self.data_dir = prepare_data_directory(ROOT)
        self.store = HubDatabaseManager(self.data_dir, ROOT / 'score_hub_received.json')
        self.cache = self.store.snapshot()
        self.sources = []
        self.filter_var = tk.StringVar()
        self.query_var = tk.StringVar()
        self.status_var = tk.StringVar(value='等待場地傳送比分；斷線時保留最後收到的紀錄。')
        ttk.Label(self, text='多場地比分紀錄', font=('', 20, 'bold')).pack(anchor='w', padx=16, pady=12)
        try:
            addresses = sorted({entry[4][0] for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
        except OSError:
            addresses = []
        self.addresses = addresses
        ttk.Label(self, text='後台 IP：' + ('、'.join(addresses) or '請用 ipconfig 查看') +
                  f'　接收連接埠：{PORT}　請在各場地「系統設定 → 設定後台 IP」輸入本機 IP。').pack(anchor='w', padx=16)
        database_bar = ttk.Frame(self)
        database_bar.pack(fill='x', padx=16, pady=(10, 0))
        ttk.Label(database_bar, text='目前資料庫').pack(side='left')
        self.database_var = tk.StringVar()
        self.database_box = ttk.Combobox(database_bar, textvariable=self.database_var, state='readonly', width=30)
        self.database_box.pack(side='left', padx=6)
        self.database_box.bind('<<ComboboxSelected>>', self.select_database)
        ttk.Button(database_bar, text='開啟資料庫位置', command=self.open_database_folder).pack(side='left', padx=4)
        ttk.Button(database_bar, text='複製 Excel 表格網址', command=self.copy_api_url).pack(side='left', padx=4)
        self.api_text = tk.StringVar(value=self._api_text())
        ttk.Label(self, textvariable=self.api_text).pack(anchor='w', padx=16, pady=(4, 0))
        self.courts = ttk.Treeview(self, columns=('name', 'url', 'state', 'updated'), show='headings', height=5)
        for key, label in zip(('name', 'url', 'state', 'updated'), ('場地', '位址', '連線狀態', '最後成功同步')):
            self.courts.heading(key, text=label)
        self.courts.pack(fill='x', padx=16, pady=12)
        filters = ttk.Frame(self)
        filters.pack(fill='x', padx=16)
        ttk.Label(filters, text='場地').pack(side='left')
        self.filter_box = ttk.Combobox(filters, textvariable=self.filter_var, state='readonly', width=18)
        self.filter_box.pack(side='left', padx=6)
        ttk.Label(filters, text='搜尋場次／選手').pack(side='left')
        ttk.Entry(filters, textvariable=self.query_var, width=32).pack(side='left', padx=6)
        self.open_button = ttk.Button(filters, text='開啟選取場次 LOG', command=self.open_report, state='disabled')
        self.open_button.pack(side='right')
        self.reports = {}
        self.report_content = None
        log_page = ttk.Frame(self)
        log_page.pack(fill='both', expand=True, padx=16, pady=12)
        self.report_list = ttk.Treeview(log_page, columns=('court', 'name', 'updated'), show='headings', selectmode='browse')
        for column, label in zip(('court', 'name', 'updated'), ('場地', '場次 LOG 檔案', '檔案更新時間')):
            self.report_list.heading(column, text=label)
            self.report_list.column(column, width=240)
        scrollbar = ttk.Scrollbar(log_page, orient='vertical', command=self.report_list.yview)
        self.report_list.configure(yscrollcommand=scrollbar.set)
        self.report_list.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.report_list.bind('<<TreeviewSelect>>', self.show_report)
        self.report_list.bind('<Double-1>', lambda event: self.open_report())
        self.report_list.bind('<Return>', lambda event: self.open_report())
        self.report_hint = tk.StringVar(value='選擇場地與場次後，雙擊即可開啟 LOG 網頁。')
        ttk.Label(self, textvariable=self.report_hint).pack(anchor='w', padx=16)
        ttk.Label(self, textvariable=self.status_var).pack(anchor='w', padx=16, pady=10)
        self.filter_var.trace_add('write', lambda *_: self.render())
        self.query_var.trace_add('write', lambda *_: self.render())
        self.receiver = make_receiver(self.store)
        threading.Thread(target=self.receiver.serve_forever, daemon=True).start()
        self.protocol('WM_DELETE_WINDOW', self.close)
        center_window(self, 1050, 680)
        self.process_events()

    def _api_text(self):
        if not self.addresses:
            return f'Excel 表格：http://後台IP:{PORT}/api/excel-data.csv'
        return 'Excel 表格：' + '　'.join(f'http://{address}:{PORT}/api/excel-data.csv' for address in self.addresses)

    def copy_api_url(self):
        if not self.addresses:
            messagebox.showinfo('Excel API', '目前無法判斷本機區域網路 IP。', parent=self)
            return
        url = f'http://{self.addresses[0]}:{PORT}/api/excel-data.csv'
        self.clipboard_clear()
        self.clipboard_append(url)
        self.status_var.set('已複製 Excel 表格網址：' + url)

    def select_database(self, event=None):
        try:
            self.store.select(self.database_var.get())
            self.cache = {}
            self.sources = []
            self.report_content = None
            self.process_events(schedule=False)
        except ValueError as exc:
            messagebox.showerror('無法開啟資料庫', str(exc), parent=self)

    def close(self):
        self.receiver.shutdown()
        self.receiver.server_close()
        self.destroy()

    def process_events(self, schedule=True):
        names = self.store.database_names()
        self.database_box['values'] = names
        active = self.store.active_database_name()
        if self.database_var.get() != (active or ''):
            self.database_var.set(active or '')
        current = self.store.snapshot()
        changed = current != self.cache or not self.sources
        self.cache = current
        self.sources = [dict(url=device_id,
                            name=f"第 {entry['snapshot']['court']} 場地（{device_id[:6]}）")
                        for device_id, entry in sorted(self.cache.items())]
        valid_devices = {source['url'] for source in self.sources}
        for item in self.courts.get_children():
            if item not in valid_devices:
                self.courts.delete(item)
        for source in self.sources:
            device_id = source['url']
            entry = self.cache[device_id]
            state = '已連線' if time.time() - entry['received'] < 20 else '未收到更新（保留上次資料）'
            values = (source['name'], entry['address'], state, entry['updated'])
            if self.courts.exists(device_id):
                self.courts.item(device_id, values=values)
            else:
                self.courts.insert('', 'end', iid=device_id, values=values)
        values = ['全部場地'] + [s['name'] for s in self.sources]
        self.filter_box['values'] = values
        if self.filter_var.get() not in values:
            self.filter_var.set('全部場地')
        if changed:
            self.render()
        if schedule:
            self.after(1000, self.process_events)

    def render(self):
        self.render_reports()
        self.status_var.set(f"資料庫：{self.store.active_database_name() or '尚無資料庫'}　共 {len(self.reports)} 份 LOG。Excel API 會輸出目前資料庫。")

    def render_reports(self):
        selected = self.report_list.selection()
        old = selected[0] if selected else None
        self.reports = {}
        query = self.query_var.get().strip().casefold()
        for source in self.sources:
            if self.filter_var.get() not in ('', '全部場地', source['name']):
                continue
            for report in self.cache[source['url']]['snapshot'].get('reports', []):
                searchable = report['name'] + ' '.join(text for row in parse_log(report['html']) for text, _ in row)
                if query and query not in searchable.casefold():
                    continue
                key = hashlib.sha256((source['url'] + '/' + report['name']).encode()).hexdigest()
                self.reports[key] = dict(report, court=source['name'], file_id=key)
        self.report_list.delete(*self.report_list.get_children())
        for key, report in self.reports.items():
            self.report_list.insert('', 'end', iid=key, values=(report['court'], report['name'], report['updated']))
        if self.reports:
            key = old if old in self.reports else next(iter(self.reports))
            self.report_list.selection_set(key)
            self.show_report()
        else:
            self.report_content = None
            self.open_button.configure(state='disabled')
            self.report_hint.set('尚無符合的 LOG；請確認場地已產生 LOG 並完成同步。')

    def show_report(self, event=None):
        selected = self.report_list.selection()
        self.report_content = self.reports.get(selected[0]) if selected else None
        self.open_button.configure(state='normal' if self.report_content else 'disabled')
        if self.report_content:
            self.report_hint.set(self.report_content['court'] + ' · ' + self.report_content['name'] + '　雙擊或按 Enter 開啟')

    def open_database_folder(self):
        try:
            os.startfile(str(self.data_dir.resolve()))
        except OSError as exc:
            messagebox.showerror('無法開啟資料庫位置', str(exc), parent=self)

    def open_report(self):
        self.show_report()
        if not self.report_content:
            messagebox.showinfo('開啟 LOG', '請先選取一個 LOG 場次。', parent=self)
            return
        report = self.report_content
        path = self.data_dir / '紀錄預覽' / (report['file_id'] + '.html')
        try:
            folder = self.data_dir / '紀錄預覽'
            folder.mkdir(exist_ok=True)
            # Each court/session has its own file, so opening another LOG does not replace it.
            path = folder / (report['file_id'] + '.html')
            # Preserve the original LOG layout while disabling active content and network loads.
            policy = '<meta http-equiv="Content-Security-Policy" content="default-src &apos;none&apos;; style-src &apos;unsafe-inline&apos;; img-src data:">'
            content = report['html']
            position = content.lower().find('<head>')
            if position >= 0:
                content = content[:position+6] + policy + content[position+6:]
            else:
                content = policy + content
            path.write_text(content, encoding='utf-8')
            open_log_file(path)
            self.report_hint.set('已交由系統開啟：' + report['name'])
        except OSError as exc:
            messagebox.showerror('無法開啟 LOG', f'{exc}\n\n請確認 Windows 已設定 HTML 預設開啟程式。\n檔案：{path}', parent=self)

if __name__ == '__main__':
    try:
        from packaging_tools.license_verifier import check_and_enforce
        check_and_enforce("score_hub")
        ScoreHub().mainloop()
    except (ValueError, OSError, sqlite3.Error) as exc:
        messagebox.showerror('後台無法啟動', f'無法讀取資料或啟動接收服務（請確認 5004 未被占用）：{exc}')



