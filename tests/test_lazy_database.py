from contextlib import closing
import os
from pathlib import Path
import tempfile
import unittest

import database


class LazyDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        self.old_name = database.current_db_name
        os.chdir(self.temp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        database.current_db_name = self.old_name
        self.temp.cleanup()

    def test_setup_reads_clears_and_empty_saves_create_no_file(self):
        database.set_tournament_db('初始名稱')
        database.init_db()
        database.set_tournament_db('正式賽事')
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM scores').fetchone()[0], 0)
            conn.execute("UPDATE scores SET deduction=0.3 WHERE match_uuid='absent'")
            conn.commit()
        database.clear_match_scores('absent')
        database.save_scores_batch([])
        self.assertFalse(Path('前台資料庫').exists())

    def test_first_completed_batch_uses_latest_name_and_preserves_results(self):
        database.set_tournament_db('初始名稱')
        selected = database.set_tournament_db('正式賽事')
        row = dict(match_uuid='m1', judge_id='1', round_num=1, total=8.5, acc=3, pres=5.5)
        database.save_scores_batch([row])
        self.assertEqual([p.name for p in Path('前台資料庫').glob('*.db')], [selected])
        database.set_tournament_db('正式賽事')
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute('SELECT total FROM scores').fetchone()[0], 8.5)
        database.save_scores_batch([dict(row, total=9)])
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*), total FROM scores').fetchone(), (1, 9))
        database.clear_match_scores('m1')
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM scores').fetchone()[0], 0)

    def test_single_score_write_and_switch_to_unstarted_tournament(self):
        saved = database.set_tournament_db('已開賽')
        database.save_score('m1', '組別', '選手', '1', 4, 6, 10, 1)
        pending = database.set_tournament_db('尚未開賽')
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM scores').fetchone()[0], 0)
        self.assertFalse(Path('前台資料庫', pending).exists())
        self.assertTrue(Path('前台資料庫', saved).exists())


if __name__ == '__main__':
    unittest.main()

