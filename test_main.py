import sys
import types
import unittest

sys.modules.setdefault("svgwrite", types.SimpleNamespace(Drawing=object))

from main import parse_appointee_names, wrap_name


class ParseAppointeeNamesTests(unittest.TestCase):
    def test_splits_multiple_names_in_one_cell(self):
        self.assertEqual(
            parse_appointee_names(["Joe Shoulak,Jake Shoulak"]),
            ["Joe Shoulak", "Jake Shoulak"],
        )

    def test_handles_whitespace_empty_values_and_extra_columns(self):
        self.assertEqual(
            parse_appointee_names([" Joe Shoulak, Jake Shoulak ", "", "Darren Swenson"]),
            ["Joe Shoulak", "Jake Shoulak", "Darren Swenson"],
        )


class WrapNameTests(unittest.TestCase):
    def test_keeps_short_names_on_one_line(self):
        self.assertEqual(wrap_name("Tim Galvin"), ["Tim Galvin"])

    def test_wraps_long_names_at_spaces(self):
        self.assertEqual(
            wrap_name("Terrance M. Schaffer"),
            ["Terrance M.", "Schaffer"],
        )

    def test_preserves_every_word(self):
        name = "John M. Johnson III"
        self.assertEqual(" ".join(wrap_name(name)), name)

if __name__ == "__main__":
    unittest.main()
