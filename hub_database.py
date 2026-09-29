"""Route incoming court snapshots to one SQLite database per tournament."""
from pathlib import Path
import threading

from excel_api import records_from_snapshot
from lan_records import RecordStore
from tournament_names import tournament_database_name


class HubDatabaseManager:
    def __init__(self, directory, legacy_json=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.legacy_json = Path(legacy_json) if legacy_json else None
        self.lock = threading.RLock()
        self.selected_name = None
        names = self.database_names()
        if names:
            self.selected_name = names[0]

    def database_names(self):
        return sorted(
            path.name for path in self.directory.glob('*.db')
            if path.is_file() and not path.is_symlink()
        )

    def select(self, name):
        with self.lock:
            if name not in self.database_names():
                raise ValueError('找不到選取的後台資料庫')
            self.selected_name = name

    def active_database_name(self):
        with self.lock:
            names = self.database_names()
            if self.selected_name not in names:
                self.selected_name = names[0] if names else None
            return self.selected_name

    def _store(self, name, import_legacy=False):
        legacy = self.legacy_json if import_legacy else None
        return RecordStore(self.directory / name, legacy)

    def accept(self, payload, address):
        name = tournament_database_name(payload.get('tournament'))
        with self.lock:
            import_legacy = not self.database_names()
            self._store(name, import_legacy=import_legacy).accept(payload, address)
            if self.selected_name is None:
                self.selected_name = name

    def snapshot(self):
        with self.lock:
            name = self.active_database_name()
            return self._store(name).snapshot() if name else {}

    def excel_records(self):
        return records_from_snapshot(self.snapshot())

