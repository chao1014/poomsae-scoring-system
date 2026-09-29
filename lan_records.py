"""LAN push synchronization: courts send snapshots to one central receiver."""
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import closing
import csv
import io
import sqlite3
import ipaddress
import json
from pathlib import Path
import threading
import time
import urllib.request
import uuid
from tournament_names import safe_tournament_name, tournament_log_folder
from excel_api import EXCEL_COLUMNS, format_csv_records

PORT = 5004
LIMIT = 32 * 1024 * 1024
status = '未設定後台 IP'
_worker = None
_worker_lock = threading.Lock()


def hub_url(host):
    address = ipaddress.IPv4Address(host.strip())
    if not (address.is_private or address.is_loopback) or address.is_unspecified or address.is_multicast:
        raise ValueError('請輸入後台電腦的區域網路 IPv4 位址')
    return f'http://{address}:{PORT}/api/records'


def save_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def read_snapshot(root, settings, device_id):
    tournament = safe_tournament_name(settings.get('tournament_name'))
    reports = []
    for path in sorted(tournament_log_folder(root, tournament).glob('*.html')):
        if path.is_symlink():
            continue
        content = path.read_text(encoding='utf-8-sig')
        # An export may still be writing; only transmit complete documents.
        if '</html>' in content.lower():
            reports.append(dict(name=path.name, html=content,
                                updated=datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')))
    return dict(version=2, device_id=device_id, court=str(settings.get('court_no', 1)),
                tournament=tournament, reports=reports)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('後台位址不可重新導向')


def push_snapshot(url, payload):
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(body) > LIMIT:
        raise ValueError('比分紀錄超過 32 MB')
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=5) as response:
        result = json.loads(response.read(4096))
        if result.get('ok') is not True:
            raise ValueError('後台尚未確認接收')


def start_sync(root, settings):
    global _worker
    with _worker_lock:
        if _worker is not None and _worker.is_alive():
            return
        def run():
            global status
            device_id = None
            while True:
                try:
                    current = dict(settings())
                    host = current.get('score_hub_ip', '').strip()
                    if not host:
                        status = '未設定後台 IP（未同步）'
                    else:
                        if device_id is None:
                            path = Path(root) / 'court_device_id.txt'
                            if not path.exists():
                                path.write_text(str(uuid.uuid4()), encoding='utf-8')
                            device_id = str(uuid.UUID(path.read_text(encoding='utf-8').strip()))
                        url = hub_url(host)
                        status = '正在同步至 ' + host
                        push_snapshot(url, read_snapshot(root, current, device_id))
                        status = '已同步至 ' + host + '　' + datetime.now().strftime('%H:%M:%S')
                except Exception as exc:
                    status = '同步失敗，5 秒後重試：' + str(exc)[:100]
                time.sleep(5)
        _worker = threading.Thread(target=run, daemon=True)
        _worker.start()


def validate_snapshot(payload):
    if not isinstance(payload, dict) or payload.get('version') != 2:
        raise ValueError('不支援的紀錄格式')
    uuid.UUID(payload.get('device_id', ''))
    if not isinstance(payload.get('tournament', ''), str) or len(payload.get('tournament', '')) > 100:
        raise ValueError('賽事名稱無效')
    if not isinstance(payload.get('court'), str) or not 1 <= len(payload['court']) <= 40:
        raise ValueError('場地編號無效')
    databases = payload.get('databases', [])
    if not isinstance(databases, list):
        raise ValueError('資料庫格式無效')
    reports = payload.get('reports', [])
    if not isinstance(reports, list):
        raise ValueError('LOG 格式無效')
    for report in reports:
        if not isinstance(report, dict) or any(not isinstance(report.get(key), str) for key in ('name', 'html', 'updated')):
            raise ValueError('LOG 格式無效')
    names = set()
    for db in databases:
        if not isinstance(db, dict) or not isinstance(db.get('name'), str) or not isinstance(db.get('scores'), list):
            raise ValueError('資料庫格式無效')
        if db['name'] in names:
            raise ValueError('資料庫名稱重複')
        names.add(db['name'])
        for row in db['scores']:
            if not isinstance(row, dict) or any(isinstance(v, (dict, list)) for v in row.values()):
                raise ValueError('評分格式無效')


class RecordStore:
    """Central SQLite storage, independent of all court scoring databases."""
    def __init__(self, path, legacy_path=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        with closing(self.connect()) as conn, conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS courts (
                    device_id TEXT PRIMARY KEY, court TEXT NOT NULL,
                    address TEXT NOT NULL, updated TEXT NOT NULL, received REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS logs (
                    device_id TEXT NOT NULL REFERENCES courts(device_id),
                    name TEXT NOT NULL, html TEXT NOT NULL, updated TEXT NOT NULL,
                    PRIMARY KEY(device_id, name));
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            if legacy_path and Path(legacy_path).exists() and not conn.execute(
                    "SELECT 1 FROM metadata WHERE key='legacy_imported'").fetchone():
                old = json.loads(Path(legacy_path).read_text(encoding='utf-8-sig'))
                for device_id, entry in old.items():
                    # Never overwrite a court already synchronized into SQLite.
                    if not conn.execute("SELECT 1 FROM courts WHERE device_id=?", (device_id,)).fetchone():
                        self.write_entry(conn, entry['snapshot'], entry.get('address', ''),
                                         entry.get('updated', ''), entry.get('received', 0))
                conn.execute("INSERT INTO metadata VALUES ('legacy_imported','1')")
        self.records = self.load_records()

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=5000')
        return conn

    def write_entry(self, conn, payload, address, updated, received):
        validate_snapshot(payload)
        device_id = payload['device_id']
        conn.execute("""INSERT INTO courts VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(device_id) DO UPDATE SET court=excluded.court,
                        address=excluded.address, updated=excluded.updated, received=excluded.received""",
                     (device_id, payload['court'], address, updated, received))
        conn.execute('DELETE FROM logs WHERE device_id=?', (device_id,))
        conn.executemany('INSERT INTO logs VALUES (?, ?, ?, ?)',
                         [(device_id, r['name'], r['html'], r['updated']) for r in payload.get('reports', [])])

    def load_records(self):
        records = {}
        with closing(self.connect()) as conn:
            conn.execute('BEGIN')
            for device_id, court, address, updated, received in conn.execute('SELECT * FROM courts'):
                reports = [dict(name=name, html=html, updated=stamp) for name, html, stamp in
                           conn.execute('SELECT name, html, updated FROM logs WHERE device_id=? ORDER BY name',
                                        (device_id,))]
                records[device_id] = dict(snapshot=dict(version=2, device_id=device_id, court=court, reports=reports),
                                          address=address, updated=updated, received=received)
        return records

    def accept(self, payload, address):
        validate_snapshot(payload)
        with self.lock:
            with closing(self.connect()) as conn, conn:
                self.write_entry(conn, payload, address,
                                 datetime.now().strftime('%Y-%m-%d %H:%M:%S'), time.time())
            self.records = self.load_records()

    def snapshot(self):
        with self.lock:
            return dict(self.records)


def make_receiver(store, host='0.0.0.0', port=PORT):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def do_GET(self):
            path = self.path.split('?', 1)[0]
            if path not in ('/api/excel-data', '/api/excel-data.json', '/api/excel-data.csv'):
                self.send_error(404)
                return
            try:
                address = ipaddress.ip_address(self.client_address[0])
                if not (address.is_private or address.is_loopback):
                    self.send_error(403)
                    return
                records = store.excel_records()
                if path == '/api/excel-data.csv':
                    output = io.StringIO(newline='')
                    writer = csv.DictWriter(output, fieldnames=EXCEL_COLUMNS, lineterminator='\r\n')
                    writer.writeheader()
                    writer.writerows(format_csv_records(records))
                    body = output.getvalue().encode('utf-8-sig')
                    content_type = 'text/csv; charset=utf-8'
                else:
                    body = json.dumps(records, ensure_ascii=False, allow_nan=False).encode('utf-8')
                    content_type = 'application/json; charset=utf-8'
            except (ValueError, OSError, sqlite3.Error, AttributeError):
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_POST(self):
            if self.path != '/api/records':
                self.send_error(404)
                return
            address = ipaddress.ip_address(self.client_address[0])
            if not (address.is_private or address.is_loopback):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= LIMIT:
                    self.send_error(413)
                    return
                payload = json.loads(self.rfile.read(length))
                store.accept(payload, str(address))
            except (ValueError, TypeError, AttributeError, UnicodeError):
                self.send_error(400)
                return
            except (OSError, sqlite3.Error):
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', '12')
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *args):
            pass
    return ThreadingHTTPServer((host, port), Handler)






