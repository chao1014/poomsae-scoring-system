"""Render existing LOG tables as safe text, preserving their original values."""
from html import escape
from html.parser import HTMLParser


class LogTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.span = 1
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if self.hidden:
            return
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []
            try:
                self.span = max(1, min(8, int(dict(attrs).get('colspan', 1))))
            except ValueError:
                self.span = 1
        elif tag == 'br' and self.cell is not None:
            self.cell.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if self.hidden:
            return
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append((''.join(self.cell).strip(), self.span))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if not self.hidden and self.cell is not None:
            self.cell.append(data)


def parse_log(content):
    parser = LogTableParser()
    parser.feed(content)
    return parser.rows


def safe_log_html(title, content):
    rows = parse_log(content)
    table = ''.join('<tr>' + ''.join(
        f'<td colspan="{span}">{escape(text).replace(chr(10), "<br>")}</td>'
        for text, span in row) + '</tr>' for row in rows)
    return ('<!doctype html><html lang="zh-Hant"><meta charset="utf-8">'
            '<title>' + escape(title) + '</title><style>'
            'body{font-family:Arial,"Microsoft JhengHei",sans-serif;padding:24px;background:#f5f7fb}'
            'table{border-collapse:collapse;width:100%;background:white;table-layout:fixed}'
            'td{border:1px solid #c7d2de;padding:8px;text-align:center;overflow-wrap:anywhere}'
            'tr:nth-child(-n+7){background:#e8eff8;font-weight:bold}'
            'h1{text-align:center} @media print{body{padding:0;background:white}td{font-size:10px;padding:4px}}'
            '</style><h1>GAME RESULT</h1><p>' + escape(title) + '</p><table>' +
            table + '</table></html>')

