"""Convert existing GAME RESULT LOG tables to Excel-friendly records."""
from pathlib import Path

from log_view import parse_log

EXCEL_COLUMNS = (
    '組別', '場次', '籤號', '青方姓名', '青方單位', '紅方姓名', '紅方單位', '名次',
    '青方總計_正確性', '青方總計_表現性', '青方總計_總分', '青方原始總分',
    '青方R1_正確性', '青方R1_表現性', '青方R1_平均分',
    '青方R2_正確性', '青方R2_表現性', '青方R2_平均分',
    '紅方總計_正確性', '紅方總計_表現性', '紅方總計_總分', '紅方原始總分',
    '紅方R1_正確性', '紅方R1_表現性', '紅方R1_平均分',
    '紅方R2_正確性', '紅方R2_表現性', '紅方R2_平均分',
    '狀態', '結束時間',
)

SCORE_COLUMNS = EXCEL_COLUMNS[8:28]


def format_csv_records(records):
    return [
        {
            column: (f'{value:.3f}' if column in SCORE_COLUMNS and value is not None else value)
            for column, value in record.items()
        }
        for record in records
    ]


def _cells(row):
    return [text.strip() for text, _span in row]


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score(value):
    parts = [part.strip() for part in str(value or '').split('/')]
    parts += [''] * (5 - len(parts))
    return {'accuracy': _number(parts[0]), 'presentation': _number(parts[1]),
            'average': _number(parts[3]), 'raw': _number(parts[4])}

def _session_name(filename):
    name = Path(filename).stem
    return name[4:] if name.lower().startswith('log_') else name


def records_from_log(filename, html):
    rows = parse_log(html)
    records = []
    for index in range(7, len(rows) - 1):
        meta = _cells(rows[index])
        if len(meta) < 8 or meta[0] in ('', 'Court') or meta[2] not in ('Cutoff', 'Tournaments'):
            continue
        players = _cells(rows[index + 1])
        if len(players) < 8:
            continue
        score_values = _cells(rows[index + 2]) if index + 2 < len(rows) else []
        score_values += [''] * (6 - len(score_values))
        blue_r1, blue_r2, blue_total = map(_score, score_values[:3])
        red_r1, red_r2, red_total = map(_score, score_values[3:6])
        values = (
            ' / '.join(value for value in meta[3:7] if value),
            _session_name(filename), meta[1],
            players[2], players[1], players[5], players[4], players[7],
            blue_total['accuracy'], blue_total['presentation'], blue_total['average'], blue_total['raw'],
            blue_r1['accuracy'], blue_r1['presentation'], blue_r1['average'],
            blue_r2['accuracy'], blue_r2['presentation'], blue_r2['average'],
            red_total['accuracy'], red_total['presentation'], red_total['average'], red_total['raw'],
            red_r1['accuracy'], red_r1['presentation'], red_r1['average'],
            red_r2['accuracy'], red_r2['presentation'], red_r2['average'],
            players[6], meta[7],
        )
        records.append(dict(zip(EXCEL_COLUMNS, values)))
    return records


def records_from_snapshot(snapshot):
    records = []
    for device_id, entry in sorted(snapshot.items(), key=lambda item: (
            str(item[1]['snapshot'].get('court', '')), item[0])):
        for report in entry['snapshot'].get('reports', []):
            records.extend(records_from_log(report['name'], report['html']))
    return records


