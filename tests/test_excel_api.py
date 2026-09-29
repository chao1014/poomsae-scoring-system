from pathlib import Path
import csv
import io
import json
import tempfile
import threading
import unittest
import urllib.request
import uuid

from excel_api import EXCEL_COLUMNS, records_from_log
from hub_database import HubDatabaseManager
from lan_records import make_receiver


def sample_log(blue='青方選手', red='紅方選手'):
    headers = ''.join('<tr><td>header</td></tr>' for _ in range(7))
    meta = '<tr>' + ''.join(f'<td>{value}</td>' for value in (
        '1', '12', 'Tournaments', 'Individual', 'Senior Male', 'Final', 'Round 1', '20260907112233')) + '</tr>'
    players = '<tr>' + ''.join(f'<td>{value}</td>' for value in (
        'TPE', '青方單位', blue, 'KOR', '紅方單位', red, 'End', 'BLUE')) + '</tr>'
    scores = '<tr>' + ''.join(f'<td>{value}</td>' for value in (
        '3.100 / 5.100 / 0.1 / 8.100 / 24.6',
        '3.200 / 5.200 / 0.0 / 8.400 / 25.2',
        '3.150 / 5.150 / 0.1 / 8.250 / 49.8',
        '3.000 / 5.000 / 0.2 / 7.800 / 24.0',
        '3.300 / 5.300 / 0.0 / 8.600 / 25.8',
        '3.150 / 5.150 / 0.1 / 8.200 / 49.8')) + '</tr>'
    return '<html><table>' + headers + meta + players + scores + '</table></html>'


def payload(tournament, name='青方選手'):
    return {
        'version': 2,
        'device_id': str(uuid.uuid4()),
        'court': '1',
        'tournament': tournament,
        'reports': [{'name': 'log_101.html', 'html': sample_log(name),
                     'updated': '2026-09-07 11:22:33'}],
    }


class ExcelApiTests(unittest.TestCase):
    def test_exact_columns_and_blue_red_values(self):
        rows = records_from_log('log_101.html', sample_log())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(tuple(row), EXCEL_COLUMNS)
        self.assertEqual(len(row), 30)
        self.assertEqual(row['組別'], 'Individual / Senior Male / Final / Round 1')
        self.assertEqual(row['場次'], '101')
        self.assertEqual(row['籤號'], '12')
        self.assertEqual(row['青方姓名'], '青方選手')
        self.assertEqual(row['紅方姓名'], '紅方選手')
        self.assertEqual(row['青方總計_總分'], 8.25)
        self.assertEqual(row['青方原始總分'], 49.8)
        self.assertEqual(row['青方R2_正確性'], 3.2)
        self.assertEqual(row['紅方總計_總分'], 8.2)
        self.assertEqual(row['紅方R1_表現性'], 5.0)
        self.assertEqual(row['紅方R2_平均分'], 8.6)
        self.assertEqual(row['名次'], 'BLUE')
        self.assertEqual(row['狀態'], 'End')
        self.assertEqual(row['結束時間'], '20260907112233')

    def test_tournaments_route_to_matching_databases_and_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = HubDatabaseManager(Path(directory))
            manager.accept(payload('全國賽', '甲'), '192.168.1.2')
            manager.accept(payload('市長盃', '乙'), '192.168.1.3')
            self.assertEqual(manager.database_names(), ['全國賽.db', '市長盃.db'])
            manager.select('市長盃.db')
            self.assertEqual(manager.excel_records()[0]['青方姓名'], '乙')
            manager.select('全國賽.db')
            self.assertEqual(manager.excel_records()[0]['青方姓名'], '甲')
            with self.assertRaises(ValueError):
                manager.select('../other.db')

    def test_excel_json_url_returns_selected_database_as_utf8_json(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = HubDatabaseManager(Path(directory))
            manager.accept(payload('測試賽事'), '127.0.0.1')
            receiver = make_receiver(manager, '127.0.0.1', 0)
            worker = threading.Thread(target=receiver.serve_forever, daemon=True)
            worker.start()
            try:
                url = f'http://127.0.0.1:{receiver.server_port}/api/excel-data.json'
                with urllib.request.urlopen(url, timeout=3) as response:
                    self.assertEqual(response.headers.get_content_type(), 'application/json')
                    rows = json.loads(response.read())
                self.assertEqual(rows[0]['青方姓名'], '青方選手')
                self.assertEqual(tuple(rows[0]), EXCEL_COLUMNS)
            finally:
                receiver.shutdown()
                receiver.server_close()
                worker.join()

    def test_excel_csv_url_returns_direct_utf8_table(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = HubDatabaseManager(Path(directory))
            manager.accept(payload('測試賽事'), '127.0.0.1')
            receiver = make_receiver(manager, '127.0.0.1', 0)
            worker = threading.Thread(target=receiver.serve_forever, daemon=True)
            worker.start()
            try:
                url = f'http://127.0.0.1:{receiver.server_port}/api/excel-data.csv'
                with urllib.request.urlopen(url, timeout=3) as response:
                    self.assertEqual(response.headers.get_content_type(), 'text/csv')
                    text = response.read().decode('utf-8-sig')
                rows = list(csv.DictReader(io.StringIO(text)))
                self.assertEqual(tuple(rows[0]), EXCEL_COLUMNS)
                self.assertEqual(rows[0]['青方姓名'], '青方選手')
                self.assertEqual(rows[0]['青方總計_總分'], '8.250')
                self.assertEqual(rows[0]['青方R1_正確性'], '3.100')
                self.assertEqual(rows[0]['紅方R2_平均分'], '8.600')
            finally:
                receiver.shutdown()
                receiver.server_close()
                worker.join()

if __name__ == '__main__':
    unittest.main()





