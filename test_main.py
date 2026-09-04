import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("svgwrite", types.SimpleNamespace(Drawing=object))

from batching import build_lineage_batches, get_batch_filename
from drawing import (
    draw_appointee_lines,
    draw_lineage,
    get_fill_color,
    get_stroke_color,
    wrap_name,
)
from layout import build_rings, calculate_positions
from lineage_data import (
    LineageDataError,
    UnresolvedAppointeeWarning,
    load_masons,
    parse_appointee_names,
    parse_year,
)
from models import Lineage, Mason
from settings import (
    APPOINTEE_LINE_COLOR,
    APPOINTEE_LINE_WIDTH,
    BATCH_OVERLAP_RINGS,
    BATCH_SIZE,
    DRAWING_BACKGROUND_COLOR,
    MEMBERS_PER_RING,
    MASTER_STROKE_COLOR,
    PAST_MASTER_FILL_COLOR,
    CONSECUTIVE_TERM_LINE_WIDTH,
    RETURNING_MASTER_FILL_COLOR,
)


class FakeDrawing:
    def __init__(self, filename, **attributes):
        self.filename = filename
        self.elements = []
        self.lines = []
        self.circles = []
        self.rectangles = []
        self.paths = []

    def add(self, element):
        self.elements.append(element)

    def rect(self, **attributes):
        self.rectangles.append(attributes)
        return "<rect />"

    def line(self, **attributes):
        self.lines.append(attributes)
        return "<line />"

    def circle(self, **attributes):
        self.circles.append(attributes)
        return "<circle />"

    def path(self, **attributes):
        self.paths.append(attributes)
        return "<path />"

    def text(self, text, **attributes):
        return f"<text>{text}</text>"

    def save(self, pretty=True):
        Path(self.filename).write_text(
            f"<svg>{''.join(self.elements)}</svg>",
            encoding="utf-8",
        )


class ParseYearTests(unittest.TestCase):
    def test_parses_single_year(self):
        self.assertEqual(parse_year("2024"), 2024)

    def test_handles_blank_invalid_and_range_values(self):
        self.assertIsNone(parse_year(""))
        with self.assertRaises(ValueError):
            parse_year("unknown")
        with self.assertRaises(ValueError):
            parse_year("2022-2024")


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
    def test_skips_blank_rows(self):
        lineage = load_masons([[], ["", ""], ["Joe Shoulak", ""]])

        self.assertEqual(len(lineage.masons), 1)
        self.assertEqual(lineage.masons[0].name, "Joe Shoulak")
        self.assertEqual(lineage.masons[0].year_as_master, "")

    def test_rejects_rows_with_missing_columns(self):
        with self.assertRaisesRegex(LineageDataError, "Row 2"):
            load_masons([["Joe Shoulak"]])

    def test_rejects_a_missing_name(self):
        with self.assertRaisesRegex(LineageDataError, "Row 2: name is required"):
            load_masons([["", "2024"]])

    def test_rejects_an_invalid_year(self):
        with self.assertRaisesRegex(
            LineageDataError,
            "Row 3: invalid master year 'twenty twenty-four'",
        ):
            load_masons(
                [
                    ["Officer", ""],
                    ["Past Master", "twenty twenty-four"],
                ]
            )

    def test_rejects_duplicate_master_years(self):
        with self.assertRaisesRegex(
            LineageDataError,
            "Row 3: duplicate master year 2024; already used on row 2",
        ):
            load_masons(
                [
                    ["First Master", "2024"],
                    ["Second Master", "2024"],
                ]
            )

    def test_warns_about_an_unresolved_appointee(self):
        with self.assertWarnsRegex(
            UnresolvedAppointeeWarning,
            "Row 2: appointee 'Missing Officer' does not match any mason",
        ):
            lineage = load_masons(
                [["Past Master", "2024", "Missing Officer"]]
            )

        self.assertEqual(lineage.masons[0].appointees, [])

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
        lineage = load_masons([["Officer One", ""], ["Officer Two", ""]])

        rings = build_rings(lineage)

        self.assertEqual(len(rings), 1)
        self.assertEqual(len(rings[0]), MEMBERS_PER_RING)
        self.assertEqual(rings[0][0][0].name, "Officer One")
        self.assertEqual(rings[0][1][0].name, "Officer Two")

    def test_master_years_are_grouped_into_service_rings(self):
        lineage = load_masons(
            [
                ["Officer", ""],
                ["Older Master", "2016"],
                ["Newer Master", "2024"],
            ]
        )

        rings = build_rings(lineage)

        self.assertEqual(len(rings), 3)
        self.assertIn(lineage.masons[2], rings[1][0])
        self.assertIn(lineage.masons[1], rings[2][2])

    def test_calculates_a_position_for_every_mason(self):
        lineage = load_masons(
            [
                ["Officer One", ""],
                ["Officer Two", ""],
                ["Past Master", "2024", "Officer One"],
            ]
        )

        positions = calculate_positions(lineage)

        self.assertCountEqual(
            [mason for mason, _, _ in positions],
            lineage.masons,
        )


class MasonColorTests(unittest.TestCase):
    def test_officers_have_gray_strokes(self):
        lineage = load_masons([["Officer", ""]])

        self.assertEqual(
            get_stroke_color(lineage.masons[0]),
            APPOINTEE_LINE_COLOR,
        )

    def test_past_masters_have_gold_strokes(self):
        lineage = load_masons([["Past Master", "2024"]])

        self.assertEqual(
            get_stroke_color(lineage.masons[0]),
            MASTER_STROKE_COLOR,
        )

    def test_returning_masters_have_gold_strokes(self):
        lineage = load_masons(
            [
                ["Returning Master", "2023"],
                ["Returning Master", "2024"],
            ]
        )

        self.assertEqual(
            get_stroke_color(lineage.masons[1]),
            MASTER_STROKE_COLOR,
        )

    def test_consecutive_returning_terms_are_light_blue(self):
        lineage = load_masons(
            [
                ["Returning Master", "2023"],
                ["Returning Master", "2024"],
            ]
        )

        self.assertEqual(get_fill_color(lineage.masons[0]), PAST_MASTER_FILL_COLOR)
        self.assertEqual(
            get_fill_color(lineage.masons[1]),
            RETURNING_MASTER_FILL_COLOR,
        )

    def test_non_consecutive_returning_terms_are_light_blue(self):
        lineage = load_masons(
            [
                ["Returning Master", "2020"],
                ["Returning Master", "2024"],
            ]
        )

        self.assertEqual(get_fill_color(lineage.masons[0]), PAST_MASTER_FILL_COLOR)
        self.assertEqual(
            get_fill_color(lineage.masons[1]),
            RETURNING_MASTER_FILL_COLOR,
        )


class ConsecutiveTermConnectionTests(unittest.TestCase):
    def draw_lineage(self, rows):
        lineage = load_masons(rows)
        with tempfile.TemporaryDirectory() as temporary_directory:
            filename = Path(temporary_directory) / "lineage.svg"
            with patch("drawing.svgwrite.Drawing", FakeDrawing):
                drawing = draw_lineage(lineage, str(filename))
        return drawing

    def test_connects_consecutive_terms_with_a_thick_gold_line(self):
        drawing = self.draw_lineage(
            [
                ["Returning Master", "2023"],
                ["Returning Master", "2024"],
            ]
        )

        self.assertEqual(len(drawing.lines), 1)
        self.assertEqual(
            drawing.lines[0]["stroke"],
            MASTER_STROKE_COLOR,
        )
        self.assertEqual(
            drawing.lines[0]["stroke_width"],
            CONSECUTIVE_TERM_LINE_WIDTH,
        )

    def test_does_not_connect_non_consecutive_terms(self):
        drawing = self.draw_lineage(
            [
                ["Returning Master", "2020"],
                ["Returning Master", "2024"],
            ]
        )

        self.assertEqual(drawing.lines, [])


class AppointeeConnectionTests(unittest.TestCase):
    def make_lineage(self):
        return load_masons(
            [
                ["Officer", ""],
                ["Past Master", "2024", "Officer"],
            ]
        )

    def test_keeps_short_appointee_connections_straight(self):
        lineage = self.make_lineage()

        with tempfile.TemporaryDirectory() as temporary_directory:
            filename = Path(temporary_directory) / "lineage.svg"
            with patch("drawing.svgwrite.Drawing", FakeDrawing):
                drawing = draw_lineage(lineage, str(filename))

        self.assertEqual(len(drawing.lines), 1)
        self.assertEqual(drawing.paths, [])
        self.assertEqual(drawing.lines[0]["stroke"], APPOINTEE_LINE_COLOR)
        self.assertEqual(drawing.lines[0]["stroke_width"], APPOINTEE_LINE_WIDTH)

    def test_curves_long_appointee_connections(self):
        lineage = self.make_lineage()
        officer, past_master = lineage.masons
        drawing = FakeDrawing("unused.svg")
        coordinates = {
            officer: (0, 0),
            past_master: (500, 0),
        }

        draw_appointee_lines(drawing, lineage, coordinates)

        self.assertEqual(drawing.lines, [])
        self.assertEqual(len(drawing.paths), 1)
        self.assertIn(" Q ", drawing.paths[0]["d"])
        self.assertIn("Q 250.0,80.0", drawing.paths[0]["d"])

    def test_curve_direction_follows_the_spiral_setting(self):
        lineage = self.make_lineage()
        officer, past_master = lineage.masons
        drawing = FakeDrawing("unused.svg")
        coordinates = {
            officer: (0, 0),
            past_master: (500, 0),
        }

        with patch("drawing.SPIRAL_DIRECTION", 1):
            draw_appointee_lines(drawing, lineage, coordinates)

        self.assertIn("Q 250.0,-80.0", drawing.paths[0]["d"])

    def test_can_restore_straight_appointee_lines_with_one_setting(self):
        lineage = self.make_lineage()
        officer, past_master = lineage.masons
        drawing = FakeDrawing("unused.svg")
        coordinates = {
            officer: (0, 0),
            past_master: (500, 0),
        }

        with patch("drawing.CURVE_APPOINTEE_LINES", False):
            draw_appointee_lines(drawing, lineage, coordinates)

        self.assertEqual(len(drawing.lines), 1)
        self.assertEqual(drawing.paths, [])

    def test_uses_the_same_style_for_curved_connections(self):
        lineage = self.make_lineage()
        officer, past_master = lineage.masons
        drawing = FakeDrawing("unused.svg")
        draw_appointee_lines(
            drawing,
            lineage,
            {officer: (0, 0), past_master: (500, 0)},
        )

        self.assertEqual(len(drawing.paths), 1)
        self.assertEqual(
            drawing.paths[0]["stroke"],
            APPOINTEE_LINE_COLOR,
        )
        self.assertEqual(
            drawing.paths[0]["stroke_width"],
            APPOINTEE_LINE_WIDTH,
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

    def test_builds_overlapping_thirty_master_rows_per_batch(self):
        batches = build_lineage_batches(self.make_lineage(65))

        master_counts = [
            len([mason for mason in batch.masons if mason.year is not None])
            for batch in batches
        ]

        self.assertEqual(master_counts, [BATCH_SIZE, BATCH_SIZE, 17])

    def test_adjacent_batches_overlap_by_one_ring(self):
        batches = build_lineage_batches(self.make_lineage(65))
        overlap_size = BATCH_OVERLAP_RINGS * MEMBERS_PER_RING

        for older_batch, newer_batch in zip(batches, batches[1:]):
            older_years = sorted(
                mason.year
                for mason in older_batch.masons
                if mason.year is not None
            )
            newer_years = sorted(
                mason.year
                for mason in newer_batch.masons
                if mason.year is not None
            )

            self.assertEqual(
                older_years[-overlap_size:],
                newer_years[:overlap_size],
            )

    def test_only_the_latest_partial_batch_contains_officers(self):
        batches = build_lineage_batches(self.make_lineage(65))

        officer_counts = [
            len([mason for mason in batch.masons if mason.year is None])
            for batch in batches
        ]

        self.assertEqual(officer_counts, [0, 0, 6])

    def test_batches_have_no_more_than_five_rings(self):
        batches = build_lineage_batches(self.make_lineage(65))

        for batch in batches:
            rings = build_rings(batch)
            self.assertLessEqual(len(rings), 5)


    def test_batches_start_with_the_oldest_years(self):
        batches = build_lineage_batches(self.make_lineage(31))

        first_batch_years = {
            mason.year
            for mason in batches[0].masons
            if mason.year is not None
        }
        second_batch_years = {
            mason.year
            for mason in batches[1].masons
            if mason.year is not None
        }

        self.assertEqual(first_batch_years, set(range(1900, 1930)))
        self.assertEqual(second_batch_years, set(range(1924, 1931)))

    def test_latest_batch_matches_the_center_of_the_overall_lineage(self):
        lineage = self.make_lineage(65)
        latest_batch = build_lineage_batches(lineage)[-1]

        overall_positions = {
            (mason.name, mason.year_as_master): (x, y)
            for mason, x, y in calculate_positions(lineage)
        }
        batch_positions = {
            (mason.name, mason.year_as_master): (x, y)
            for mason, x, y in calculate_positions(latest_batch)
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
        lineage.add(Mason("Joe Shoulak", 2024))

        with tempfile.TemporaryDirectory() as temporary_directory:
            filename = Path(temporary_directory) / "lineage.svg"
            with patch("drawing.svgwrite.Drawing", FakeDrawing):
                drawing = draw_lineage(lineage, str(filename))

            svg = filename.read_text(encoding="utf-8")

        self.assertIn("<svg", svg)
        self.assertIn("Joe Shoulak", svg)
        self.assertEqual(
            drawing.rectangles[0]["fill"],
            DRAWING_BACKGROUND_COLOR,
        )

if __name__ == "__main__":
    unittest.main()
