import math

from models import Lineage, Mason
from settings import (
    CIRCLE_GAP,
    CIRCLE_SIZE,
    DRAWING_PADDING,
    FIRST_RING_RADIUS,
    MEMBERS_PER_RING,
    RING_SPACING,
    SPIRAL_DIRECTION,
    STARTING_MEMBER,
)

Ring = list[list[Mason]]
Position = tuple[Mason, float, float]


def build_rings(lineage: Lineage) -> list[Ring]:
    officers = [mason for mason in lineage.masons if mason.year is None]
    masters = [mason for mason in lineage.masons if mason.year is not None]
    rings = build_officer_rings(officers)
    rings.extend(build_master_rings(masters))
    return rings


def build_officer_rings(officers: list[Mason]) -> list[Ring]:
    rings = []
    for index in range(0, len(officers), MEMBERS_PER_RING):
        ring = [[mason] for mason in officers[index:index + MEMBERS_PER_RING]]
        ring.extend([[] for _ in range(MEMBERS_PER_RING - len(ring))])
        rings.append(ring)
    return rings


def build_master_rings(masters: list[Mason]) -> list[Ring]:
    if not masters:
        return []

    newest_year = max(mason.year for mason in masters if mason.year is not None)
    oldest_year = min(mason.year for mason in masters if mason.year is not None)
    year_count = newest_year - oldest_year + 1
    ring_count = math.ceil(year_count / MEMBERS_PER_RING)
    service_years = list(
        range(
            newest_year,
            newest_year - ring_count * MEMBERS_PER_RING,
            -1,
        )
    )
    rings = []

    for index in range(0, ring_count * MEMBERS_PER_RING, MEMBERS_PER_RING):
        ring_years = service_years[index:index + MEMBERS_PER_RING]
        rings.append(
            [
                [mason for mason in masters if mason.year == year]
                for year in ring_years
            ]
        )

    return rings


def get_starting_angle(rings: list[Ring]) -> float:
    if not rings:
        return math.pi / 2

    inner_ring = rings[0]
    starting_member_index = next(
        (
            index
            for index, slot in enumerate(inner_ring)
            if any(mason.name == STARTING_MEMBER for mason in slot)
        ),
        0,
    )
    return -math.pi / 2 - starting_member_index * math.tau / len(inner_ring)


def get_ring_radius(ring: Ring, ring_index: int, previous_radius: float) -> float:
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


def group_masons_by_midpoint(ring: Ring) -> dict[float, list[Mason]]:
    positioned_masons = []
    for slot in ring:
        for mason in slot:
            if mason not in positioned_masons:
                positioned_masons.append(mason)

    groups = {}
    for mason in positioned_masons:
        occupied_slots = [index for index, slot in enumerate(ring) if mason in slot]
        midpoint = (occupied_slots[0] + occupied_slots[-1]) / 2
        groups.setdefault(midpoint, []).append(mason)
    return groups


def calculate_positions(lineage: Lineage) -> list[Position]:
    rings = build_rings(lineage)
    positions = []
    starting_angle = get_starting_angle(rings)
    previous_radius = 0.0
    slot_angle = math.tau / MEMBERS_PER_RING

    for ring_index, ring in enumerate(rings):
        radius = get_ring_radius(ring, ring_index, previous_radius)

        for midpoint, grouped_masons in group_masons_by_midpoint(ring).items():
            angular_spacing = 2 * math.asin(
                (CIRCLE_SIZE * 2 + CIRCLE_GAP) / (2 * radius)
            )
            for group_index, mason in enumerate(grouped_masons):
                offset = group_index - (len(grouped_masons) - 1) / 2
                ring_rotation = SPIRAL_DIRECTION * ring_index * slot_angle / 6
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


def fit_positions_to_canvas(
    positions: list[Position],
) -> tuple[list[Position], int, int]:
    if positions:
        min_x = min(x for _, x, _ in positions)
        max_x = max(x for _, x, _ in positions)
        min_y = min(y for _, _, y in positions)
        max_y = max(y for _, _, y in positions)
    else:
        min_x = max_x = min_y = max_y = 0

    margin = CIRCLE_SIZE + DRAWING_PADDING
    width = math.ceil(max_x - min_x + margin * 2)
    height = math.ceil(max_y - min_y + margin * 2)
    fitted_positions = [
        (mason, x - min_x + margin, y - min_y + margin)
        for mason, x, y in positions
    ]
    return fitted_positions, width, height
