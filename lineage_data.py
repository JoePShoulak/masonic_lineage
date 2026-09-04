from dataclasses import dataclass
from collections.abc import Iterable


class LineageDataError(ValueError):
    pass


class UnresolvedAppointeeWarning(UserWarning):
    pass


@dataclass(frozen=True)
class MasonRow:
    row_number: int
    name: str
    year_text: str
    year: int | None
    appointee_names: list[str]


def parse_year(year_text: str) -> int | None:
    year_text = year_text.strip()
    if not year_text:
        return None
    return int(year_text)


def parse_appointee_names(appointee_cells: list[str]) -> list[str]:
    """Return individual names from comma-separated appointee cells."""
    return [
        name.strip()
        for cell in appointee_cells
        for name in cell.split(",")
        if name.strip()
    ]


def validate_mason_rows(
    rows: Iterable[list[str]],
    first_row_number: int = 2,
) -> list[MasonRow]:
    mason_rows = []
    row_by_master_year = {}

    for row_number, row in enumerate(rows, start=first_row_number):
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) < 2:
            raise LineageDataError(
                f"Row {row_number}: expected at least a name and year column"
            )

        name = row[0].strip()
        if not name:
            raise LineageDataError(f"Row {row_number}: name is required")

        year_text = row[1].strip()
        try:
            year = parse_year(year_text)
        except ValueError as error:
            raise LineageDataError(
                f"Row {row_number}: invalid master year {year_text!r}"
            ) from error

        if year is not None:
            if year in row_by_master_year:
                previous_row = row_by_master_year[year]
                raise LineageDataError(
                    f"Row {row_number}: duplicate master year {year}; "
                    f"already used on row {previous_row}"
                )
            row_by_master_year[year] = row_number

        mason_rows.append(
            MasonRow(
                row_number=row_number,
                name=name,
                year_text=year_text,
                year=year,
                appointee_names=parse_appointee_names(row[2:]),
            )
        )

    return mason_rows
