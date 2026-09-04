import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("svgwrite", types.SimpleNamespace(Drawing=object))

from main import (
    BATCH_SIZE,
    MEMBERS_PER_RING,
    PAST_MASTER_FILL_COLOR,
    RETURNING_MASTER_FILL_COLOR,
    Lineage,
    Mason,
    build_lineage_batches,
    get_batch_filename,
    load_masons,
    parse_appointee_names,
    parse_years,
    wrap_name,
)


class FakeDrawing:
    def __init__(self, filename, **attributes):
        self.filename = filename
        self.elements = []

    def add(self, element):
        self.elements.append(element)

    def rect(self, **attributes):
        return "<rect />"

    def line(self, **attributes):
        return "<line />"

    def circle(self, **attributes):
        return "<circle />"

    def text(self, text, **attributes):
        return f"<text>{text}</text>"

    def save(self, pretty=True):
        Path(self.filename).write_text(
            f"<svg>{''.join(self.elements)}</svg>",
            encoding="utf-8",
        )


class ParseYearsTests(unittest.TestCase):
    def test_parses_single_year(self):
        self.assertEqual(parse_years("2024"), {2024})

    def test_parses_range_with_different_dashes(self):
        self.assertEqual(parse_years("2022–2024"), {2022, 2023, 2024})
        self.assertEqual(parse_years("2022—2024"), {2022, 2023, 2024})

    def test_parses_reversed_range(self):
        self.assertEqual(parse_years("2024-2022"), {2022, 2023, 2024})

    def test_handles_blank_and_invalid_years(self):
        self.assertEqual(parse_years(""), set())
        self.assertEqual(parse_years("unknown"), set())


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


class LoadMasonsTests(unittest.TestCase):
    def test_loads_rows_with_missing_columns(self):
        lineage = load_masons([[], [""], ["Joe Shoulak"]])

        self.assertEqual(len(lineage.masons), 1)
        self.assertEqual(lineage.masons[0].name, "Joe Shoulak")
        self.assertEqual(lineage.masons[0].year_as_master, "")

    def test_resolves_appointees_regardless_of_row_order(self):
        lineage = load_masons(
            [
                ["Past Master", "2024", "Future Officer"],
                ["Future Officer", ""],
            ]
        )

        self.assertEqual(
            [mason.name for mason in lineage.masons[0].appointees],
            ["Future Officer"],
        )

    def test_resolves_multiple_appointees(self):
        lineage = load_masons(
            [
                ["Officer One", ""],
                ["Officer Two", ""],
                ["Past Master", "2024", "Officer One, Officer Two"],
            ]
        )

        self.assertEqual(
            [mason.name for mason in lineage.masons[2].appointees],
            ["Officer One", "Officer Two"],
        )


class LineageLayoutTests(unittest.TestCase):
    def test_officer_ring_has_six_slots(self):
        lineage = load_masons([["Officer One"], ["Officer Two"]])

        lineage.parse_rings()

        self.assertEqual(len(lineage.rings), 1)
        self.assertEqual(len(lineage.rings[0]), MEMBERS_PER_RING)
        self.assertEqual(lineage.rings[0][0][0].name, "Officer One")
        self.assertEqual(lineage.rings[0][1][0].name, "Officer Two")

    def test_master_years_are_grouped_into_service_rings(self):
        lineage = load_masons(
            [
                ["Officer", ""],
                ["Older Master", "2016"],
                ["Newer Master", "2024"],
            ]
        )

        lineage.parse_rings()

        self.assertEqual(len(lineage.rings), 3)
        self.assertIn(lineage.masons[2], lineage.rings[1][0])
        self.assertIn(lineage.masons[1], lineage.rings[2][2])

    def test_calculates_a_position_for_every_mason(self):
        lineage = load_masons(
            [
                ["Officer One", ""],
                ["Officer Two", ""],
                ["Past Master", "2024", "Officer One"],
            ]
        )

        positions = lineage.calculate_positions()

        self.assertCountEqual(
            [mason for mason, _, _ in positions],
            lineage.masons,
        )


class MasonColorTests(unittest.TestCase):
    def test_consecutive_returning_terms_are_light_blue(self):
        lineage = load_masons(
            [
                ["Returning Master", "2023"],
                ["Returning Master", "2024"],
            ]
        )

        self.assertEqual(lineage.masons[0].get_fill_color(), PAST_MASTER_FILL_COLOR)
        self.assertEqual(
            lineage.masons[1].get_fill_color(),
            RETURNING_MASTER_FILL_COLOR,
        )

    def test_non_consecutive_returning_terms_are_light_blue(self):
        lineage = load_masons(
            [
                ["Returning Master", "2020"],
                ["Returning Master", "2024"],
            ]
        )

        self.assertEqual(lineage.masons[0].get_fill_color(), PAST_MASTER_FILL_COLOR)
        self.assertEqual(
            lineage.masons[1].get_fill_color(),
            RETURNING_MASTER_FILL_COLOR,
        )


class LineageBatchTests(unittest.TestCase):
    def make_lineage(self, master_count):
        rows = [
            ["Mike Johnson", ""],
            ["Brett Mhyre", ""],
            ["Bill Emery", ""],
            ["Joe Shoulak", ""],
            ["Jake Shoulak", ""],
            ["Darren Swenson", ""],
        ]
        rows.extend(
            [f"Master {index}", str(1900 + index)]
            for index in range(master_count)
        )
        return load_masons(rows)

    def test_builds_thirty_master_rows_per_batch(self):
        batches = build_lineage_batches(self.make_lineage(65))

        master_counts = [
            len([mason for mason in batch.masons if mason.years_as_master])
            for batch in batches
        ]

        self.assertEqual(master_counts, [BATCH_SIZE, BATCH_SIZE, 5])

    def test_only_the_latest_partial_batch_contains_officers(self):
        batches = build_lineage_batches(self.make_lineage(65))

        officer_counts = [
            len([mason for mason in batch.masons if not mason.years_as_master])
            for batch in batches
        ]

        self.assertEqual(officer_counts, [0, 0, 6])

    def test_batches_have_no_more_than_five_rings(self):
        batches = build_lineage_batches(self.make_lineage(65))

        for batch in batches:
            batch.parse_rings()

        self.assertTrue(all(len(batch.rings) <= 5 for batch in batches))

    def test_batches_start_with_the_oldest_years(self):
        batches = build_lineage_batches(self.make_lineage(31))

        first_batch_years = {
            min(mason.years_as_master)
            for mason in batches[0].masons
            if mason.years_as_master
        }
        second_batch_years = {
            min(mason.years_as_master)
            for mason in batches[1].masons
            if mason.years_as_master
        }

        self.assertEqual(first_batch_years, set(range(1900, 1930)))
        self.assertEqual(second_batch_years, {1930})

    def test_latest_batch_matches_the_center_of_the_overall_lineage(self):
        lineage = self.make_lineage(65)
        latest_batch = build_lineage_batches(lineage)[-1]

        overall_positions = {
            (mason.name, mason.year_as_master): (x, y)
            for mason, x, y in lineage.calculate_positions()
        }
        batch_positions = {
            (mason.name, mason.year_as_master): (x, y)
            for mason, x, y in latest_batch.calculate_positions()
        }

        for mason_key, position in batch_positions.items():
            self.assertAlmostEqual(position[0], overall_positions[mason_key][0])
            self.assertAlmostEqual(position[1], overall_positions[mason_key][1])

    def test_batch_filename_includes_number_and_years(self):
        batch = build_lineage_batches(self.make_lineage(2))[0]

        self.assertEqual(
            get_batch_filename(batch, 1),
            "Lineage_01_1900-1901.svg",
        )

class SvgDrawingTests(unittest.TestCase):
    def test_draws_an_svg_file(self):
        lineage = Lineage()
        lineage.add(Mason("Joe Shoulak", "2024"))

        with tempfile.TemporaryDirectory() as temporary_directory:
            filename = Path(temporary_directory) / "lineage.svg"
            with patch("main.svgwrite.Drawing", FakeDrawing):
                lineage.draw(str(filename))

            svg = filename.read_text(encoding="utf-8")

        self.assertIn("<svg", svg)
        self.assertIn("Joe Shoulak", svg)

if __name__ == "__main__":
    unittest.main()
