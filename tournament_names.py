"""Safe names shared by court LOG folders and central tournament databases."""
from pathlib import Path

_WINDOWS_RESERVED = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}


def safe_tournament_name(value):
    text = ''.join(
        character for character in str(value or '')
        if character.isalnum() or character in (' ', '-', '_')
    ).strip(' .')
    if not text:
        text = '未命名賽事'
    if text.upper() in _WINDOWS_RESERVED:
        text += '_'
    return text[:100]


def tournament_database_name(value):
    return safe_tournament_name(value) + '.db'


def tournament_log_folder(root, tournament, create=False):
    from folder_paths import localized_folder

    base = localized_folder('場次log', ('比賽紀錄', 'match_logs'), root=root)
    target = Path(base) / safe_tournament_name(tournament)

    # Earlier versions stored every LOG directly in 場次log. During upgrade,
    # those files belong to the tournament currently configured on that court.
    flat_logs = list(Path(base).glob('*.html')) if Path(base).exists() else []
    if flat_logs:
        target.mkdir(parents=True, exist_ok=True)
        for source in flat_logs:
            destination = target / source.name
            if not destination.exists():
                source.replace(destination)

    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target

