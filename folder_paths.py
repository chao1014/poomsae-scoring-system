"""Localized runtime folders with one-time migration from legacy names."""
from pathlib import Path
import shutil


def localized_folder(name, legacy_name=None, root=None, create=False):
    base = Path(root) if root is not None else Path.cwd()
    destination = base / name
    if legacy_name is None:
        legacy_names = ()
    elif isinstance(legacy_name, (str, Path)):
        legacy_names = (legacy_name,)
    else:
        legacy_names = tuple(legacy_name)

    for old_name in legacy_names:
        legacy = base / old_name
        if not legacy.exists():
            continue
        if not destination.exists():
            shutil.move(str(legacy), str(destination))
        elif legacy.is_dir() and destination.is_dir():
            for child in legacy.iterdir():
                target = destination / child.name
                if not target.exists():
                    shutil.move(str(child), str(target))
            try:
                legacy.rmdir()
            except OSError:
                pass

    if create:
        destination.mkdir(parents=True, exist_ok=True)
    return destination

