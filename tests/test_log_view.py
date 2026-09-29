import unittest
from log_view import parse_log, safe_log_html


class LogViewTests(unittest.TestCase):
    def test_preserves_values_spans_and_linebreaks(self):
        content = '<table><tr><td colspan="2">青方 &amp; 紅方<br>8.500</td></tr></table>'
        self.assertEqual(parse_log(content), [[('青方 & 紅方\n8.500', 2)]])
        self.assertIn('colspan="2"', safe_log_html('比賽', content))

    def test_scripts_links_and_event_handlers_are_not_executed(self):
        content = '<table><tr><td onclick="evil()">選手<script>evil()</script><img src=x onerror=evil()> &lt;b&gt;</td></tr></table>'
        output = safe_log_html('<script>title</script>', content)
        self.assertNotIn('<script>', output)
        self.assertNotIn('onclick', output)
        self.assertNotIn('<img', output)
        self.assertIn('選手 &lt;b&gt;', output)

    def test_invalid_colspan_has_bounded_fallback(self):
        self.assertEqual(parse_log('<tr><td colspan="bad">A</td><td colspan="999">B</td></tr>'),
                         [[('A', 1), ('B', 8)]])

