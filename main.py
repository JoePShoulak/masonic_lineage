from __future__ import annotations

import csv
import math
import sys
from collections.abc import Iterable
from io import TextIOWrapper
from pathlib import Path
from urllib.request import urlopen

import svgwrite

LINK = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRzUnSMbwWOyKb83-Ww6dhZR7P1849YEub-HegsdPOocTHKGbfpfx2OIMx5HiECricVZYhPzDWZ2Crk/pub?output=csv"
FILENAME = "Lineage.svg"
BATCH_DIRECTORY = "Lineage_batches"
BATCH_SIZE = 30
STARTING_MEMBER = "Darren Swenson"
CIRCLE_SIZE = 50
DRAWING_PADDING = 40
MEMBERS_PER_RING = 6
FIRST_RING_RADIUS = 150
RING_SPACING = 140
CIRCLE_GAP = 20
OFFICER_FILL_COLOR = "#94a3b8"
RETURNING_MASTER_FILL_COLOR = "#3b82f6"
PAST_MASTER_FILL_COLOR = "#1e40af"
CIRCLE_STROKE_COLOR = "#1e3a8a"
CIRCLE_STROKE_WIDTH = 3
FONT_COLOR = "white"
FONT_SIZE = "12px"
FONT_FAMILY = "Arial, sans-serif"
FONT_WEIGHT = "bold"
NAME_MAX_CHARACTERS_PER_LINE = 12
NAME_LINE_HEIGHT = 14
YEAR_FONT_SIZE = "10px"
YEAR_LINE_HEIGHT = 12
LINE_STROKE_COLOR = "#374151"
LINE_STROKE_WIDTH = 4


def parse_years(year_text: str) -> set[int]:
    normalized_year = year_text.replace("–", "-").replace("—", "-").strip()
    if not normalized_year:
        return set()

    try:
        endpoints = [int(year.strip()) for year in normalized_year.split("-", 1)]
    except ValueError:
        return set()

    first_year = min(endpoints)
    last_year = max(endpoints)
    return set(range(first_year, last_year + 1))


def parse_appointee_names(appointee_cells: list[str]) -> list[str]:
    """Return individual names from comma-separated appointee cells."""
    return [
        name.strip()
        for cell in appointee_cells
        for name in cell.split(",")
        if name.strip()
    ]


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
        newest_year = max(year for mason in masters for year in mason.years_as_master)
        oldest_year = min(year for mason in masters for year in mason.years_as_master)
        service_year_count = newest_year - oldest_year + 1
        service_ring_count = math.ceil(service_year_count / MEMBERS_PER_RING)
        return list(
            range(newest_year, newest_year - service_ring_count * MEMBERS_PER_RING, -1)
        )

    def choose_master_rings(
        self,
        masters: list[Mason],
        year_to_ring: dict[int, int],
    ) -> dict[Mason, int]:
        chosen_rings = {}
        for mason in masters:
            years_per_ring = {}
            for year in mason.years_as_master:
                ring_index = year_to_ring[year]
                years_per_ring[ring_index] = years_per_ring.get(ring_index, 0) + 1

            chosen_rings[mason] = min(
                years_per_ring,
                key=lambda ring_index: (-years_per_ring[ring_index], ring_index),
            )
        return chosen_rings

    def add_master_rings(self, masters: list[Mason]):
        service_years = self.get_service_years(masters)
        officer_ring_count = len(self.rings)
        year_to_ring = {
            year: officer_ring_count + index // MEMBERS_PER_RING
            for index, year in enumerate(service_years)
        }
        chosen_rings = self.choose_master_rings(masters, year_to_ring)

        for year_index in range(0, len(service_years), MEMBERS_PER_RING):
            ring_index = officer_ring_count + year_index // MEMBERS_PER_RING
            ring = []

            for year in service_years[year_index:year_index + MEMBERS_PER_RING]:
                masters_that_year = [
                    mason for mason in masters if year in mason.years_as_master
                ]
                masters_in_this_ring = [
                    mason
                    for mason in masters_that_year
                    if chosen_rings[mason] == ring_index
                ]
                ring.append(masters_in_this_ring)

            self.rings.append(ring)

    def parse_rings(self):
        self.rings = []
        officers = [mason for mason in self.masons if not mason.years_as_master]
        masters = [mason for mason in self.masons if mason.years_as_master]

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
                    ring_rotation = ring_index * slot_angle / 6
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
                fill="white",
            )
        )

        for mason, _, _ in positions:
            mason.draw_connections()
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
        self.years_as_master = parse_years(year_as_master)
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
        if not self.years_as_master:
            return OFFICER_FILL_COLOR

        if self.is_returning_master:
            return RETURNING_MASTER_FILL_COLOR
        return PAST_MASTER_FILL_COLOR

    def draw_connections(self) -> None:
        drawing = self.get_drawing()
        assert self.x is not None and self.y is not None

        for appointee in self.appointees:
            if appointee not in self.lineage.masons:
                continue
            assert appointee.x is not None and appointee.y is not None
            delta_x = appointee.x - self.x
            delta_y = appointee.y - self.y
            distance = math.hypot(delta_x, delta_y)
            if distance == 0:
                continue

            unit_x = delta_x / distance
            unit_y = delta_y / distance
            drawing.add(
                drawing.line(
                    start=(
                        self.x + unit_x * CIRCLE_SIZE,
                        self.y + unit_y * CIRCLE_SIZE,
                    ),
                    end=(
                        appointee.x - unit_x * CIRCLE_SIZE,
                        appointee.y - unit_y * CIRCLE_SIZE,
                    ),
                    stroke=LINE_STROKE_COLOR,
                    stroke_width=LINE_STROKE_WIDTH,
                )
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
                stroke=CIRCLE_STROKE_COLOR,
                stroke_width=CIRCLE_STROKE_WIDTH,
            )
        )
        self.draw_label()


def load_masons(rows: Iterable[list[str]]) -> Lineage:
    lineage = Lineage()
    appointee_names_by_mason = []

    for row in rows:
        if not row or not row[0].strip():
            continue

        name = row[0].strip()
        year_as_master = row[1].strip() if len(row) > 1 else ""
        mason = Mason(name, year_as_master)
        lineage.add(mason)
        appointee_names_by_mason.append((mason, parse_appointee_names(row[2:])))

    for mason, appointee_names in appointee_names_by_mason:
        mason.appointees = [
            appointee
            for appointee in lineage.masons
            if appointee.name in appointee_names
        ]

    first_term_by_name = {}
    for mason in sorted(
        (mason for mason in lineage.masons if mason.years_as_master),
        key=lambda mason: min(mason.years_as_master),
    ):
        mason.is_returning_master = mason.name in first_term_by_name
        first_term_by_name.setdefault(mason.name, mason)

    return lineage


def load_lineage(link: str = LINK) -> Lineage:
    with urlopen(link) as response:
        mason_data = csv.reader(TextIOWrapper(response, encoding="utf-8"))
        next(mason_data, None)
        return load_masons(mason_data)


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
    officers = [mason for mason in lineage.masons if not mason.years_as_master]
    masters = sorted(
        (mason for mason in lineage.masons if mason.years_as_master),
        key=lambda mason: min(mason.years_as_master),
    )
    batches = []

    for index in range(0, len(masters), BATCH_SIZE):
        master_batch = masters[index:index + BATCH_SIZE]
        is_latest_batch = index + BATCH_SIZE >= len(masters)
        if is_latest_batch and len(master_batch) < BATCH_SIZE:
            batches.append(clone_lineage(officers + master_batch))
        else:
            batches.append(clone_lineage(master_batch))

    return batches


def get_batch_filename(batch: Lineage, batch_number: int) -> str:
    years = [
        year
        for mason in batch.masons
        for year in mason.years_as_master
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
