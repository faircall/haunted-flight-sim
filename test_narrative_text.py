import unittest
from types import SimpleNamespace
from unittest.mock import patch

import g_narrative_text as text


class NarrativeColorTests(unittest.TestCase):
    def test_nested_colors_and_unknown_tags(self):
        chars = list(text.styled_characters('[color=red]a[color=green]b[/color]c[/color]d'))
        self.assertEqual(chars, [('a', 'red'), ('b', 'green'), ('c', 'red'), ('d', None)])
        literal = '[color=unknown]word[/color]'
        self.assertEqual(''.join(c for c, _ in text.styled_characters(literal)), literal)

    def test_wrapping_preserves_colors_across_lines_and_paragraphs(self):
        with patch.object(text, 'plain_width', side_effect=lambda assets, value: len(value)):
            for value in ('one [color=red]two three four[/color] end',
                          '[color=green]一二三四五六\n七八九[/color]'):
                styled = text.wrap({}, value, 5)
                plain = ''.join(c for c, _ in text.styled_characters(value))
                unstyled = text.wrap({}, plain, 5)
                self.assertEqual([''.join(c for c, _ in text.styled_characters(line)) for line in styled], unstyled)
                expected = [(c, s) for c, s in text.styled_characters(value) if not c.isspace()]
                actual = [(c, s) for line in styled for c, s in text.styled_characters(line) if not c.isspace()]
                self.assertEqual(actual, expected)

    def test_color_runs_keep_fade_alpha_and_positions(self):
        with patch.object(text, 'font', return_value=object()), patch.object(text.pr, 'measure_text_ex', side_effect=lambda font, value, size, spacing: SimpleNamespace(x=len(value) * 6)), patch.object(text.pr, 'draw_text_ex') as draw:
            value = 'a [color=red]red[/color] z'
            self.assertEqual(text.width({}, value), 42)
            text.draw({}, value, 10, 20, text.pr.Color(255, 255, 255, 64))
            calls = draw.call_args_list
            self.assertEqual([call.args[1] for call in calls], ['a ', 'red', ' z'])
            self.assertEqual([call.args[2].x for call in calls], [10, 22, 40])
            self.assertTrue(all(call.args[-1].a == 64 for call in calls))
            red = calls[1].args[-1]
            self.assertEqual((red.r, red.g, red.b), text.data.TEXT_COLORS['red'])


if __name__ == '__main__':
    unittest.main()
