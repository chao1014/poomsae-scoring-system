from contextlib import closing
import copy
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import uuid

from lan_records import RecordStore, hub_url, make_receiver, push_snapshot, read_snapshot
from score_hub import ScoreHub


class LanRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / '前台資料庫').mkdir()
        self.db = self.root / '前台資料庫' / '測試.db'
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute('CREATE TABLE scores (id INTEGER PRIMARY KEY, player_name TEXT, total REAL, player_side INTEGER)')
            conn.execute("INSERT INTO scores VALUES (1, '選手', 8.5, 0)")
        (self.root / '場次log').mkdir()
        (self.root / '場次log' / 'log_101.html').write_text(
            '<html><table><tr><td>Court</td><td>Result</td></tr>'
            '<tr><td>第1場地</td><td>BLUE</td></tr></table></html>', encoding='utf-8')
        self.device = str(uuid.uuid4())
        self.store = RecordStore(self.root / 'received.db')

    def tearDown(self):
        self.temp.cleanup()

    def payload(self):
        return read_snapshot(self.root, {'court_no': 1, 'tournament_name': '測試賽事'}, self.device)

    def test_snapshot_only_contains_complete_logs(self):
        before = self.db.read_bytes()
        (self.root / '場次log' / 'partial.html').write_text('<html>writing')
        snapshot = self.payload()
        self.assertNotIn('databases', snapshot)
        self.assertEqual(snapshot['tournament'], '測試賽事')
        self.assertTrue((self.root / '場次log' / '測試賽事' / 'log_101.html').exists())
        self.assertEqual([r['name'] for r in snapshot['reports']], ['log_101.html'])
        self.assertEqual(self.db.read_bytes(), before)

    def test_http_push_without_key_and_persistence(self):
        receiver = make_receiver(self.store, '127.0.0.1', 0)
        worker = threading.Thread(target=receiver.serve_forever, daemon=True)
        worker.start()
        try:
            url = f'http://127.0.0.1:{receiver.server_port}/api/records'
            push_snapshot(url, self.payload())
            self.assertIn(self.device, RecordStore(self.store.path).snapshot())
            self.assertEqual(self.store.snapshot()[self.device]['snapshot']['reports'][0]['name'], 'log_101.html')
            invalid = self.payload()
            invalid['device_id'] = '../bad'
            with self.assertRaises(urllib.error.HTTPError) as error:
                push_snapshot(url, invalid)
            self.assertEqual(error.exception.code, 400)
            self.assertEqual(len(self.store.snapshot()), 1)
        finally:
            receiver.shutdown()
            receiver.server_close()
            worker.join()

    def test_sources_are_independent_and_reconnect_replaces_snapshot(self):
        payload = self.payload()
        self.store.accept(payload, '192.168.1.2')
        other = dict(payload, device_id=str(uuid.uuid4()))
        self.store.accept(other, '192.168.1.3')
        self.assertEqual(len(self.store.snapshot()), 2)
        self.store.accept(dict(payload, reports=[]), '192.168.1.9')
        self.assertEqual(self.store.snapshot()[self.device]['snapshot']['reports'], [])
        self.assertEqual(len(self.store.snapshot()[other['device_id']]['snapshot']['reports']), 1)

    def test_storage_failure_keeps_last_good_snapshot(self):
        self.store.accept(self.payload(), '127.0.0.1')
        previous = copy.deepcopy(self.store.snapshot())
        with patch.object(self.store, 'write_entry', side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError):
                self.store.accept(dict(self.payload(), reports=[]), '127.0.0.1')
        self.assertEqual(self.store.snapshot(), previous)

    def test_unrelated_database_failure_does_not_block_logs(self):
        (self.root / '前台資料庫' / 'broken.db').write_text('broken')
        self.assertEqual(len(self.payload()['reports']), 1)

    def test_desktop_auto_registration_offline_and_recovery(self):
        def receiver(store):
            return make_receiver(store, '127.0.0.1', 0)
        with patch('score_hub.ROOT', self.root), patch('score_hub.make_receiver', side_effect=receiver):
            hub = ScoreHub()
            hub.withdraw()
            try:
                hub.store.accept(self.payload(), '192.168.1.2')
                hub.process_events()
                self.assertEqual(len(hub.reports), 1)
                self.assertIn('測試賽事.db', hub.database_box['values'])
                self.assertEqual(len(hub.courts.get_children()), 1)
                self.assertEqual(len(hub.report_list.get_children()), 1)
                with patch('score_hub.open_log_file') as opened:
                    hub.open_report()
                    first_url = opened.call_args.args[0]
                    self.assertIn('BLUE', next((self.root / '後台資料庫' / '紀錄預覽').glob('*.html')).read_text(encoding='utf-8'))
                    other = dict(self.payload(), device_id=str(uuid.uuid4()))
                    hub.store.accept(other, '192.168.1.3')
                    hub.process_events()
                    other_key = next(key for key in hub.reports if hub.reports[key]['court'] != hub.report_content['court'])
                    hub.report_list.selection_set(other_key)
                    hub.show_report()
                    hub.open_report()
                    self.assertNotEqual(first_url, opened.call_args.args[0])
                hub.store.accept(dict(other, reports=[]), '192.168.1.3')
                hub.process_events()
                hub.query_var.set('does-not-match')
                self.assertEqual(len(hub.report_list.get_children()), 0)
                hub.query_var.set('')
                self.assertEqual(len(hub.report_list.get_children()), 1)
                with patch('score_hub.time.time', return_value=time.time() + 30):
                    hub.process_events()
                self.assertIn('未收到更新', hub.courts.item(self.device)['values'][2])
                self.assertEqual(len(hub.reports), 1)
                self.assertIn('測試賽事.db', hub.database_box['values'])
                hub.store.accept(dict(self.payload(), databases=[], reports=[]), '192.168.1.2')
                hub.process_events()
                self.assertEqual(hub.reports, {})
                self.assertEqual(str(hub.open_button['state']), 'disabled')
                self.assertEqual(hub.courts.item(self.device)['values'][2], '已連線')
            finally:
                hub.close()

    def test_legacy_json_import_is_once_and_keeps_original(self):
        import json
        legacy = self.root / 'legacy.json'
        payload = self.payload()
        legacy.write_text(json.dumps({self.device: dict(snapshot=payload, address='127.0.0.1',
                                                        updated='old', received=1)}), encoding='utf-8')
        target = self.root / 'migrated.db'
        migrated = RecordStore(target, legacy)
        self.assertEqual(len(migrated.snapshot()[self.device]['snapshot']['reports']), 1)
        self.assertTrue(legacy.exists())
        migrated.accept(dict(payload, reports=[]), '127.0.0.1')
        self.assertEqual(RecordStore(target, legacy).snapshot()[self.device]['snapshot']['reports'], [])

    def test_transaction_rolls_back_partial_update(self):
        self.store.accept(self.payload(), '127.0.0.1')
        original = self.store.snapshot()
        payload = self.payload()
        payload['reports'] *= 2
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.accept(payload, '192.168.1.10')
        self.assertEqual(RecordStore(self.store.path).snapshot(), original)

    def test_ip_validation(self):
        self.assertEqual(hub_url('192.168.1.20'), 'http://192.168.1.20:5004/api/records')
        for host in ('8.8.8.8', 'example.com', '0.0.0.0', '224.0.0.1', '192.168.1.2:5004'):
            with self.assertRaises(ValueError):
                hub_url(host)


if __name__ == '__main__':
    unittest.main()

