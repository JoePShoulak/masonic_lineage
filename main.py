from __future__ import annotations

import csv
import math
import sys
import warnings
from collections.abc import Iterable
from io import TextIOWrapper
from pathlib import Path
from urllib.request import urlopen

import svgwrite

from lineage_data import (
    UnresolvedAppointeeWarning,
    parse_year,
    validate_mason_rows,
)

LINK = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRzUnSMbwWOyKb83-Ww6dhZR7P1849YEub-HegsdPOocTHKGbfpfx2OIMx5HiECricVZYhPzDWZ2Crk/pub?output=csv"
FILENAME = "Lineage.svg"
BATCH_DIRECTORY = "Lineage_batches"
BATCH_SIZE = 30
BATCH_OVERLAP_RINGS = 1
STARTING_MEMBER = "Darren Swenson"
CIRCLE_SIZE = 50
DRAWING_PADDING = 40
DRAWING_BACKGROUND_COLOR = "#111827"
MEMBERS_PER_RING = 6
FIRST_RING_RADIUS = 150
RING_SPACING = 140
CIRCLE_GAP = 20
OFFICER_FILL_COLOR = "#94a3b8"
RETURNING_MASTER_FILL_COLOR = "#3b82f6"
PAST_MASTER_FILL_COLOR = "#1e40af"
PAST_MASTER_CIRCLE_STROKE_COLOR = "#d4af37"
CIRCLE_STROKE_WIDTH = 3
FONT_COLOR = "white"
FONT_SIZE = "12px"
FONT_FAMILY = "Arial, sans-serif"
FONT_WEIGHT = "bold"
NAME_MAX_CHARACTERS_PER_LINE = 12
NAME_LINE_HEIGHT = 14
YEAR_FONT_SIZE = "10px"
YEAR_LINE_HEIGHT = 12
APPOINTEE_LINE_STROKE_COLOR = "#d1d5db"
APPOINTEE_LINE_STROKE_WIDTH = 4
RETURNING_MASTER_LINE_STROKE_WIDTH = 10


def wrap_name(name: str) -> list[str]:
    """Wrap a name at spaces so each rendered line fits inside its circle."""
    words = name.split()
    if not words:
        return [""]

    lines = [words[0]]
    for word in words[1:]:
        candidate = f"{lines[-1]} {word}"
        if len(candidate) <= NAME_MAX_CHARACTERS_PER_LINE:
            lines[-1] = candidate
        else:
            lines.append(word)
    return lines


class Lineage:
    def __init__(self):
        self.masons: list[Mason] = []
        self.rings: list[list[list[Mason]]] = []
        self.drawing: svgwrite.Drawing | None = None

    def add(self, mason: Mason):
        mason.lineage = self
        self.masons.append(mason)

    def add_officer_rings(self, officers: list[Mason]):
        for index in range(0, len(officers), MEMBERS_PER_RING):
            ring = [
                [mason]
                for mason in officers[index:index + MEMBERS_PER_RING]
            ]
            ring.extend([[] for _ in range(MEMBERS_PER_RING - len(ring))])
            self.rings.append(ring)

    def get_service_years(self, masters: list[Mason]) -> list[int]:
        newest_year = max(mason.year for mason in masters if mason.year is not None)
        oldest_year = min(mason.year for mason in masters if mason.year is not None)
        service_year_count = newest_year - oldest_year + 1
        service_ring_count = math.ceil(service_year_count / MEMBERS_PER_RING)
        return list(
            range(newest_year, newest_year - service_ring_count * MEMBERS_PER_RING, -1)
        )

    def add_master_rings(self, masters: list[Mason]):
        service_years = self.get_service_years(masters)

        for year_index in range(0, len(service_years), MEMBERS_PER_RING):
            ring = []

            for year in service_years[year_index:year_index + MEMBERS_PER_RING]:
                masters_that_year = [
                    mason for mason in masters if mason.year == year
                ]
                ring.append(masters_that_year)

            self.rings.append(ring)

    def parse_rings(self):
        self.rings = []
        officers = [mason for mason in self.masons if mason.year is None]
        masters = [mason for mason in self.masons if mason.year is not None]

        self.add_officer_rings(officers)
        if masters:
            self.add_master_rings(masters)

    def get_starting_angle(self) -> float:
        if not self.rings:
            return math.pi / 2

        inner_ring = self.rings[0]
        starting_member_index = next(
            (
                index
                for index, slot in enumerate(inner_ring)
                if any(mason.name == STARTING_MEMBER for mason in slot)
            ),
            0,
        )
        return -math.pi / 2 - starting_member_index * math.tau / len(inner_ring)

    def get_ring_radius(
        self,
        ring: list[list[Mason]],
        ring_index: int,
        previous_radius: float,
    ) -> float:
        slot_angle = math.tau / MEMBERS_PER_RING
        minimum_radius = (CIRCLE_SIZE * 2 + CIRCLE_GAP) / (
            2 * math.sin(slot_angle / 2)
        )

        largest_slot = max(len(slot) for slot in ring)
        if largest_slot > 1:
            available_spacing = slot_angle * 0.7 / (largest_slot - 1)
            minimum_radius = max(
                minimum_radius,
                (CIRCLE_SIZE * 2 + CIRCLE_GAP)
                / (2 * math.sin(available_spacing / 2)),
            )

        return max(
            FIRST_RING_RADIUS if ring_index == 0 else previous_radius + RING_SPACING,
            minimum_radius,
        )

    def get_masons_by_midpoint(
        self,
        ring: list[list[Mason]],
    ) -> dict[float, list[Mason]]:
        positioned_masons = []
        for slot in ring:
            for mason in slot:
                if mason not in positioned_masons:
                    positioned_masons.append(mason)

        midpoint_groups = {}
        for mason in positioned_masons:
            occupied_positions = [
                index for index, slot in enumerate(ring) if mason in slot
            ]
            midpoint = (occupied_positions[0] + occupied_positions[-1]) / 2
            midpoint_groups.setdefault(midpoint, []).append(mason)
        return midpoint_groups

    def calculate_positions(self) -> list[tuple[Mason, float, float]]:
        self.parse_rings()
        positions = []
        starting_angle = self.get_starting_angle()
        previous_radius = 0.0
        slot_angle = math.tau / MEMBERS_PER_RING

        for ring_index, ring in enumerate(self.rings):
            radius = self.get_ring_radius(ring, ring_index, previous_radius)
            midpoint_groups = self.get_masons_by_midpoint(ring)

            for midpoint, grouped_masons in midpoint_groups.items():
                angular_spacing = 2 * math.asin(
                    (CIRCLE_SIZE * 2 + CIRCLE_GAP) / (2 * radius)
                )
                for group_index, mason in enumerate(grouped_masons):
                    offset = group_index - (len(grouped_masons) - 1) / 2
                    # A small cumulative turn creates six readable spiral arms.
                    ring_rotation = -ring_index * slot_angle / 6
                    angle = (
                        starting_angle
                        + ring_rotation
                        + midpoint * slot_angle
                        + offset * angular_spacing
                    )
                    positions.append(
                        (mason, radius * math.cos(angle), radius * math.sin(angle))
                    )

            previous_radius = radius

        return positions

    def place_masons(
        self,
        positions: list[tuple[Mason, float, float]],
    ) -> tuple[int, int]:
        if positions:
            min_x = min(x for _, x, _ in positions)
            max_x = max(x for _, x, _ in positions)
            min_y = min(y for _, _, y in positions)
            max_y = max(y for _, _, y in positions)
        else:
            min_x = max_x = min_y = max_y = 0

        margin = CIRCLE_SIZE + DRAWING_PADDING
        drawing_width = math.ceil(max_x - min_x + margin * 2)
        drawing_height = math.ceil(max_y - min_y + margin * 2)

        for mason, x, y in positions:
            mason.x = x - min_x + margin
            mason.y = y - min_y + margin

        return drawing_width, drawing_height

    def draw(self, filename: str = FILENAME):
        positions = self.calculate_positions()
        drawing_width, drawing_height = self.place_masons(positions)

        self.drawing = svgwrite.Drawing(
            filename=filename,
            size=(f"{drawing_width}px", f"{drawing_height}px"),
            viewBox=f"0 0 {drawing_width} {drawing_height}",
        )
        self.drawing.add(
            self.drawing.rect(
                insert=(0, 0),
                size=("100%", "100%"),
                fill=DRAWING_BACKGROUND_COLOR,
            )
        )

        for mason, _, _ in positions:
            mason.draw_appointee_connections()
        for mason, _, _ in positions:
            mason.draw_consecutive_term_connection()
        for mason, _, _ in positions:
            mason.draw()

        self.drawing.save(pretty=True)
        print(f"Saved {filename}")


class Mason:
    def __init__(
        self,
        name: str,
        year_as_master: str,
        appointees: list[Mason] | None = None,
    ) -> None:
        self.name = name
        self.year_as_master = year_as_master
        self.year = parse_year(year_as_master)
        self.is_returning_master = False
        self.appointees = appointees or []
        self.x: float | None = None
        self.y: float | None = None
        self.lineage: Lineage | None = None

    def get_drawing(self) -> svgwrite.Drawing:
        assert self.lineage is not None
        assert self.lineage.drawing is not None
        return self.lineage.drawing

    def get_fill_color(self) -> str:
        if self.year is None:
            return OFFICER_FILL_COLOR

        if self.is_returning_master:
            return RETURNING_MASTER_FILL_COLOR
        return PAST_MASTER_FILL_COLOR

    def get_stroke_color(self) -> str:
        if self.year is None:
            return APPOINTEE_LINE_STROKE_COLOR
        return PAST_MASTER_CIRCLE_STROKE_COLOR

    def draw_line_to(self, mason: Mason, color: str, width: int) -> None:
        drawing = self.get_drawing()
        assert self.x is not None and self.y is not None
        assert mason.x is not None and mason.y is not None

        delta_x = mason.x - self.x
        delta_y = mason.y - self.y
        distance = math.hypot(delta_x, delta_y)
        if distance == 0:
            return

        unit_x = delta_x / distance
        unit_y = delta_y / distance
        drawing.add(
            drawing.line(
                start=(
                    self.x + unit_x * CIRCLE_SIZE,
                    self.y + unit_y * CIRCLE_SIZE,
                ),
                end=(
                    mason.x - unit_x * CIRCLE_SIZE,
                    mason.y - unit_y * CIRCLE_SIZE,
                ),
                stroke=color,
                stroke_width=width,
            )
        )

    def draw_appointee_connections(self) -> None:
        assert self.lineage is not None

        for appointee in self.appointees:
            if appointee not in self.lineage.masons:
                continue
            self.draw_line_to(
                appointee,
                APPOINTEE_LINE_STROKE_COLOR,
                APPOINTEE_LINE_STROKE_WIDTH,
            )

    def draw_consecutive_term_connection(self) -> None:
        if self.year is None:
            return

        assert self.lineage is not None
        previous_term = next(
            (
                mason
                for mason in self.lineage.masons
                if mason.name == self.name
                and mason.year == self.year - 1
            ),
            None,
        )
        if previous_term is None:
            return

        self.draw_line_to(
            previous_term,
            PAST_MASTER_CIRCLE_STROKE_COLOR,
            RETURNING_MASTER_LINE_STROKE_WIDTH,
        )

    def draw_label(self) -> None:
        drawing = self.get_drawing()
        assert self.x is not None and self.y is not None

        name_lines = wrap_name(self.name)
        label_height = len(name_lines) * NAME_LINE_HEIGHT
        if self.year_as_master:
            label_height += YEAR_LINE_HEIGHT
        label_y = self.y - label_height / 2 + NAME_LINE_HEIGHT / 2

        for line_index, line in enumerate(name_lines):
            drawing.add(
                drawing.text(
                    line,
                    insert=(self.x, label_y + line_index * NAME_LINE_HEIGHT),
                    text_anchor="middle",
                    dominant_baseline="middle",
                    fill=FONT_COLOR,
                    font_size=FONT_SIZE,
                    font_family=FONT_FAMILY,
                    font_weight=FONT_WEIGHT,
                )
            )

        if self.year_as_master:
            drawing.add(
                drawing.text(
                    self.year_as_master,
                    insert=(self.x, label_y + len(name_lines) * NAME_LINE_HEIGHT),
                    text_anchor="middle",
                    dominant_baseline="middle",
                    fill=FONT_COLOR,
                    font_size=YEAR_FONT_SIZE,
                    font_family=FONT_FAMILY,
                )
            )

    def draw(self) -> None:
        drawing = self.get_drawing()
        assert self.x is not None and self.y is not None

        drawing.add(
            drawing.circle(
                center=(self.x, self.y),
                r=CIRCLE_SIZE,
                fill=self.get_fill_color(),
                stroke=self.get_stroke_color(),
                stroke_width=CIRCLE_STROKE_WIDTH,
            )
        )
        self.draw_label()


def load_masons(rows: Iterable[list[str]]) -> Lineage:
    lineage = Lineage()
    appointee_names_by_mason = []

    for mason_row in validate_mason_rows(rows):
        mason = Mason(mason_row.name, mason_row.year_text)
        lineage.add(mason)
        appointee_names_by_mason.append((mason, mason_row))

    known_names = {mason.name for mason in lineage.masons}
    for mason, mason_row in appointee_names_by_mason:
        missing_names = [
            name for name in mason_row.appointee_names if name not in known_names
        ]
        for missing_name in missing_names:
            warnings.warn(
                f"Row {mason_row.row_number}: appointee {missing_name!r} "
                "does not match any mason",
                UnresolvedAppointeeWarning,
            )

        mason.appointees = [
            appointee
            for appointee in lineage.masons
            if appointee.name in mason_row.appointee_names
        ]

    first_term_by_name = {}
    for mason in sorted(
        (mason for mason in lineage.masons if mason.year is not None),
        key=lambda mason: mason.year,
    ):
        mason.is_returning_master = mason.name in first_term_by_name
        first_term_by_name.setdefault(mason.name, mason)

    return lineage


def load_lineage(link: str = LINK) -> Lineage:
    with urlopen(link) as response:
        mason_data = csv.reader(TextIOWrapper(response, encoding="utf-8"))
        next(mason_data, None)
        lineage = load_masons(mason_data)

    master_count = len([mason for mason in lineage.masons if mason.year is not None])
    officer_count = len(lineage.masons) - master_count
    print(f"Loaded {master_count} masters and {officer_count} officers")
    return lineage


def clone_lineage(masons: list[Mason]) -> Lineage:
    lineage = Lineage()
    cloned_masons = {}

    for mason in masons:
        cloned_mason = Mason(mason.name, mason.year_as_master)
        cloned_mason.is_returning_master = mason.is_returning_master
        cloned_masons[mason] = cloned_mason
        lineage.add(cloned_mason)

    for mason, cloned_mason in cloned_masons.items():
        cloned_mason.appointees = [
            cloned_masons[appointee]
            for appointee in mason.appointees
            if appointee in cloned_masons
        ]

    return lineage


def build_lineage_batches(lineage: Lineage) -> list[Lineage]:
    officers = [mason for mason in lineage.masons if mason.year is None]
    masters = sorted(
        (mason for mason in lineage.masons if mason.year is not None),
        key=lambda mason: mason.year,
    )
    batches = []
    overlap_size = BATCH_OVERLAP_RINGS * MEMBERS_PER_RING
    batch_step = BATCH_SIZE - overlap_size

    if batch_step <= 0:
        raise ValueError("Batch overlap must be smaller than the batch size")

    for index in range(0, len(masters), batch_step):
        master_batch = masters[index:index + BATCH_SIZE]
        is_latest_batch = index + BATCH_SIZE >= len(masters)
        if is_latest_batch and len(master_batch) < BATCH_SIZE:
            batches.append(clone_lineage(officers + master_batch))
        else:
            batches.append(clone_lineage(master_batch))

    return batches


def get_batch_filename(batch: Lineage, batch_number: int) -> str:
    years = [
        mason.year
        for mason in batch.masons
        if mason.year is not None
    ]
    oldest_year = min(years)
    newest_year = max(years)
    return f"Lineage_{batch_number:02d}_{oldest_year}-{newest_year}.svg"


def generate_overall_lineage() -> None:
    lineage = load_lineage()
    lineage.draw()


def generate_lineage_batches() -> None:
    lineage = load_lineage()
    batches = build_lineage_batches(lineage)
    batch_directory = Path(BATCH_DIRECTORY)
    batch_directory.mkdir(exist_ok=True)

    for old_batch_file in batch_directory.glob("Lineage_*.svg"):
        old_batch_file.unlink()

    for batch_number, batch in enumerate(batches, start=1):
        filename = batch_directory / get_batch_filename(batch, batch_number)
        batch.draw(str(filename))


def main() -> None:
    option = sys.argv[1].lower() if len(sys.argv) > 1 else "both"

    if option in {"all", "both"}:
        generate_overall_lineage()
    if option in {"batches", "both"}:
        generate_lineage_batches()
    if option not in {"all", "batches", "both"}:
        raise SystemExit("Choose one option: all, batches, or both")


if __name__ == "__main__":
    main()
