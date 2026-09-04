from __future__ import annotations

import svgwrite
import csv
import math
from io import TextIOWrapper
from urllib.request import urlopen

LINK = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRzUnSMbwWOyKb83-Ww6dhZR7P1849YEub-HegsdPOocTHKGbfpfx2OIMx5HiECricVZYhPzDWZ2Crk/pub?output=csv"
FILENAME = "Lineage.svg"
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

    def parse_rings(self):
        self.rings = []
        officers = [mason for mason in self.masons if not mason.years_as_master]
        masters = [mason for mason in self.masons if mason.years_as_master]

        for index in range(0, len(officers), MEMBERS_PER_RING):
            ring = [
                [mason]
                for mason in officers[index:index + MEMBERS_PER_RING]
            ]
            ring.extend([[] for _ in range(MEMBERS_PER_RING - len(ring))])
            self.rings.append(ring)

        if not masters:
            return

        newest_year = max(year for mason in masters for year in mason.years_as_master)
        oldest_year = min(year for mason in masters for year in mason.years_as_master)
        service_year_count = newest_year - oldest_year + 1
        service_ring_count = math.ceil(service_year_count / MEMBERS_PER_RING)
        service_years = list(
            range(newest_year, newest_year - service_ring_count * MEMBERS_PER_RING, -1)
        )
        officer_ring_count = len(self.rings)
        year_to_ring = {
            year: officer_ring_count + index // MEMBERS_PER_RING
            for index, year in enumerate(service_years)
        }

        chosen_ring = {}
        for mason in masters:
            years_per_ring = {}
            for year in mason.years_as_master:
                ring_index = year_to_ring[year]
                years_per_ring[ring_index] = years_per_ring.get(ring_index, 0) + 1

            chosen_ring[mason] = min(
                years_per_ring,
                key=lambda ring_index: (-years_per_ring[ring_index], ring_index),
            )

        for year_index in range(0, len(service_years), MEMBERS_PER_RING):
            ring_index = officer_ring_count + year_index // MEMBERS_PER_RING
            ring: list[list[Mason]] = []

            for year in service_years[year_index:year_index + MEMBERS_PER_RING]:
                masters_that_year = [
                    mason for mason in masters if year in mason.years_as_master
                ]
                masters_in_this_ring = [
                    mason
                    for mason in masters_that_year
                    if chosen_ring[mason] == ring_index
                ]

                ring.append(masters_in_this_ring)

            self.rings.append(ring)

    def draw(self):
        self.parse_rings()
        positions = []
        starting_angle = math.pi / 2
        if self.rings:
            inner_ring = self.rings[0]
            darren_index = next(
                (
                    index
                    for index, slot in enumerate(inner_ring)
                    if any(mason.name == "Darren Swenson" for mason in slot)
                ),
                0,
            )
            starting_angle = -math.pi / 2 - darren_index * math.tau / len(inner_ring)

        previous_radius = 0
        for ring_index, ring in enumerate(self.rings):
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
            radius = max(
                FIRST_RING_RADIUS if ring_index == 0 else previous_radius + RING_SPACING,
                minimum_radius,
            )
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

        # Create the drawing (canvas)
        self.drawing = svgwrite.Drawing(
            filename=FILENAME,
            size=(f"{drawing_width}px", f"{drawing_height}px"),
            viewBox=f"0 0 {drawing_width} {drawing_height}",
        )

        # Make a white background
        self.drawing.add(
            self.drawing.rect(
                insert=(0, 0),
                size=("100%", "100%"),
                fill="white",
            )
        )

        # Shift all rings into the canvas and assign coordinates before lines are drawn.
        for mason, x, y in positions:
            mason.x = x - min_x + margin
            mason.y = y - min_y + margin

        for mason, _, _ in positions:
            assert mason.x is not None and mason.y is not None
            mason.draw(mason.x, mason.y)

        # Save the drawing
        self.drawing.save(pretty=True)
        print(f"Saved {FILENAME}")

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
        self.appointees = appointees or []
        self.x = None
        self.y = None
        self.lineage: Lineage | None = None
            
    def draw(self, x: int, y: int) -> None:
        assert self.lineage is not None
        drawing = self.lineage.drawing
        assert drawing is not None

        self.x = x
        self.y = y
        circle_fill = OFFICER_FILL_COLOR
        if self.years_as_master:
            first_year_as_master = min(
                year
                for mason in self.lineage.masons
                if mason.name == self.name
                for year in mason.years_as_master
            )
            if first_year_as_master in self.years_as_master:
                circle_fill = PAST_MASTER_FILL_COLOR
            else:
                circle_fill = RETURNING_MASTER_FILL_COLOR

        # Add shape
        drawing.add(
            drawing.circle(
                center=(x, y),
                r=CIRCLE_SIZE,
                fill=circle_fill,
                stroke=CIRCLE_STROKE_COLOR,
                stroke_width=CIRCLE_STROKE_WIDTH
            )
        )
        # Wrap and center the complete label inside the circle.
        name_lines = wrap_name(self.name)
        label_height = len(name_lines) * NAME_LINE_HEIGHT
        if self.year_as_master:
            label_height += YEAR_LINE_HEIGHT
        label_y = y - label_height / 2 + NAME_LINE_HEIGHT / 2

        for line_index, line in enumerate(name_lines):
            drawing.add(
                drawing.text(
                    line,
                    insert=(x, label_y + line_index * NAME_LINE_HEIGHT),
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
                    insert=(x, label_y + len(name_lines) * NAME_LINE_HEIGHT),
                    text_anchor="middle",
                    dominant_baseline="middle",
                    fill=FONT_COLOR,
                    font_size="10px",
                    font_family=FONT_FAMILY,
                )
            )
        # Add a line for each appointee
        for appointee in self.appointees:
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

if __name__ == "__main__":
    with urlopen(LINK) as response:
        mason_data = csv.reader(TextIOWrapper(response, encoding="utf-8"))
        next(mason_data)  # Skip the header

        lineage = Lineage()

        for row in mason_data:
            if not row or not row[0].strip():
                continue

            name = row[0].strip()
            year_as_master = row[1].strip() if len(row) > 1 else ""
            appointee_names = parse_appointee_names(row[2:])
            appointees = [
                mason
                for mason in lineage.masons
                if mason.name in appointee_names
            ]
            mason = Mason(name, year_as_master, appointees)
            lineage.add(mason)

    lineage.draw()
