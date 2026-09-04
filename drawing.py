import math

import svgwrite

from layout import calculate_positions, fit_positions_to_canvas
from models import Lineage, Mason
from settings import (
    APPOINTEE_LINE_COLOR,
    APPOINTEE_LINE_WIDTH,
    APPOINTEE_CURVE_OFFSET,
    APPOINTEE_CURVE_MIN_DISTANCE,
    CIRCLE_SIZE,
    CIRCLE_STROKE_WIDTH,
    CONSECUTIVE_TERM_LINE_WIDTH,
    CURVE_APPOINTEE_LINES,
    DRAWING_BACKGROUND_COLOR,
    FONT_COLOR,
    FONT_FAMILY,
    FONT_SIZE,
    FONT_WEIGHT,
    MASTER_STROKE_COLOR,
    NAME_LINE_HEIGHT,
    NAME_MAX_CHARACTERS_PER_LINE,
    OFFICER_FILL_COLOR,
    OVERALL_FILENAME,
    PAST_MASTER_FILL_COLOR,
    RETURNING_MASTER_FILL_COLOR,
    SPIRAL_DIRECTION,
    YEAR_FONT_SIZE,
    YEAR_LINE_HEIGHT,
)

Coordinates = dict[Mason, tuple[float, float]]


def wrap_name(name: str) -> list[str]:
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


def get_fill_color(mason: Mason) -> str:
    if mason.year is None:
        return OFFICER_FILL_COLOR
    if mason.is_returning_master:
        return RETURNING_MASTER_FILL_COLOR
    return PAST_MASTER_FILL_COLOR


def get_stroke_color(mason: Mason) -> str:
    if mason.year is None:
        return APPOINTEE_LINE_COLOR
    return MASTER_STROKE_COLOR


def draw_line(
    drawing: svgwrite.Drawing,
    coordinates: Coordinates,
    first_mason: Mason,
    second_mason: Mason,
    color: str,
    width: int,
) -> None:
    first_x, first_y = coordinates[first_mason]
    second_x, second_y = coordinates[second_mason]
    delta_x = second_x - first_x
    delta_y = second_y - first_y
    distance = math.hypot(delta_x, delta_y)
    if distance == 0:
        return

    unit_x = delta_x / distance
    unit_y = delta_y / distance
    drawing.add(
        drawing.line(
            start=(
                first_x + unit_x * CIRCLE_SIZE,
                first_y + unit_y * CIRCLE_SIZE,
            ),
            end=(
                second_x - unit_x * CIRCLE_SIZE,
                second_y - unit_y * CIRCLE_SIZE,
            ),
            stroke=color,
            stroke_width=width,
        )
    )


def draw_curve(
    drawing: svgwrite.Drawing,
    coordinates: Coordinates,
    first_mason: Mason,
    second_mason: Mason,
) -> None:
    first_x, first_y = coordinates[first_mason]
    second_x, second_y = coordinates[second_mason]
    delta_x = second_x - first_x
    delta_y = second_y - first_y
    distance = math.hypot(delta_x, delta_y)
    if distance == 0:
        return

    unit_x = delta_x / distance
    unit_y = delta_y / distance
    start_x = first_x + unit_x * CIRCLE_SIZE
    start_y = first_y + unit_y * CIRCLE_SIZE
    end_x = second_x - unit_x * CIRCLE_SIZE
    end_y = second_y - unit_y * CIRCLE_SIZE
    midpoint_x = (start_x + end_x) / 2
    midpoint_y = (start_y + end_y) / 2
    canvas_center_x = (
        min(x for x, _ in coordinates.values())
        + max(x for x, _ in coordinates.values())
    ) / 2
    canvas_center_y = (
        min(y for _, y in coordinates.values())
        + max(y for _, y in coordinates.values())
    ) / 2
    radial_x = midpoint_x - canvas_center_x
    radial_y = midpoint_y - canvas_center_y
    radial_distance = math.hypot(radial_x, radial_y)
    if radial_distance == 0:
        radial_x = first_x - canvas_center_x
        radial_y = first_y - canvas_center_y
        radial_distance = math.hypot(radial_x, radial_y)
    if radial_distance == 0:
        radial_x = 1
        radial_y = 0
        radial_distance = 1

    radial_x /= radial_distance
    radial_y /= radial_distance
    tangent_x = radial_y * SPIRAL_DIRECTION
    tangent_y = -radial_x * SPIRAL_DIRECTION
    curve_offset = min(APPOINTEE_CURVE_OFFSET, distance * 0.2)
    control_x = midpoint_x + tangent_x * curve_offset
    control_y = midpoint_y + tangent_y * curve_offset
    path_data = (
        f"M {start_x},{start_y} "
        f"Q {control_x},{control_y} {end_x},{end_y}"
    )
    drawing.add(
        drawing.path(
            d=path_data,
            fill="none",
            stroke=APPOINTEE_LINE_COLOR,
            stroke_width=APPOINTEE_LINE_WIDTH,
        )
    )


def draw_appointee_lines(
    drawing: svgwrite.Drawing,
    lineage: Lineage,
    coordinates: Coordinates,
) -> None:
    for mason in lineage.masons:
        for appointee in mason.appointees:
            if appointee in coordinates:
                first_x, first_y = coordinates[mason]
                second_x, second_y = coordinates[appointee]
                distance = math.hypot(second_x - first_x, second_y - first_y)
                should_curve = (
                    CURVE_APPOINTEE_LINES
                    and distance >= APPOINTEE_CURVE_MIN_DISTANCE
                )
                if should_curve:
                    draw_curve(
                        drawing,
                        coordinates,
                        mason,
                        appointee,
                    )
                else:
                    draw_line(
                        drawing,
                        coordinates,
                        mason,
                        appointee,
                        APPOINTEE_LINE_COLOR,
                        APPOINTEE_LINE_WIDTH,
                    )


def draw_consecutive_term_lines(
    drawing: svgwrite.Drawing,
    lineage: Lineage,
    coordinates: Coordinates,
) -> None:
    for mason in lineage.masons:
        if mason.year is None:
            continue

        previous_term = next(
            (
                other_mason
                for other_mason in lineage.masons
                if other_mason.name == mason.name
                and other_mason.year == mason.year - 1
            ),
            None,
        )
        if previous_term in coordinates:
            draw_line(
                drawing,
                coordinates,
                mason,
                previous_term,
                MASTER_STROKE_COLOR,
                CONSECUTIVE_TERM_LINE_WIDTH,
            )


def draw_label(
    drawing: svgwrite.Drawing,
    mason: Mason,
    x: float,
    y: float,
) -> None:
    name_lines = wrap_name(mason.name)
    label_height = len(name_lines) * NAME_LINE_HEIGHT
    if mason.year is not None:
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

    if mason.year is not None:
        drawing.add(
            drawing.text(
                str(mason.year),
                insert=(x, label_y + len(name_lines) * NAME_LINE_HEIGHT),
                text_anchor="middle",
                dominant_baseline="middle",
                fill=FONT_COLOR,
                font_size=YEAR_FONT_SIZE,
                font_family=FONT_FAMILY,
            )
        )


def draw_masons(
    drawing: svgwrite.Drawing,
    positions: list[tuple[Mason, float, float]],
) -> None:
    for mason, x, y in positions:
        drawing.add(
            drawing.circle(
                center=(x, y),
                r=CIRCLE_SIZE,
                fill=get_fill_color(mason),
                stroke=get_stroke_color(mason),
                stroke_width=CIRCLE_STROKE_WIDTH,
            )
        )
        draw_label(drawing, mason, x, y)


def draw_lineage(lineage: Lineage, filename: str = OVERALL_FILENAME) -> svgwrite.Drawing:
    positions = calculate_positions(lineage)
    positions, width, height = fit_positions_to_canvas(positions)
    coordinates = {mason: (x, y) for mason, x, y in positions}

    drawing = svgwrite.Drawing(
        filename=filename,
        size=(f"{width}px", f"{height}px"),
        viewBox=f"0 0 {width} {height}",
    )
    drawing.add(
        drawing.rect(
            insert=(0, 0),
            size=("100%", "100%"),
            fill=DRAWING_BACKGROUND_COLOR,
        )
    )
    draw_appointee_lines(drawing, lineage, coordinates)
    draw_consecutive_term_lines(drawing, lineage, coordinates)
    draw_masons(drawing, positions)
    drawing.save(pretty=True)
    print(f"Saved {filename}")
    return drawing
