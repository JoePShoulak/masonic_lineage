import csv
import warnings
from dataclasses import dataclass
from collections.abc import Iterable
from io import TextIOWrapper
from urllib.request import urlopen

from models import Lineage, Mason
from settings import LINEAGE_URL


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


def load_masons(rows: Iterable[list[str]]) -> Lineage:
    lineage = Lineage()
    source_rows = []

    for mason_row in validate_mason_rows(rows):
        mason = Mason(mason_row.name, mason_row.year)
        lineage.add(mason)
        source_rows.append((mason, mason_row))

    known_names = {mason.name for mason in lineage.masons}
    for mason, mason_row in source_rows:
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
    masters = sorted(
        (mason for mason in lineage.masons if mason.year is not None),
        key=lambda mason: mason.year,
    )
    for mason in masters:
        mason.is_returning_master = mason.name in first_term_by_name
        first_term_by_name.setdefault(mason.name, mason)

    return lineage


def load_lineage(url: str = LINEAGE_URL) -> Lineage:
    with urlopen(url) as response:
        rows = csv.reader(TextIOWrapper(response, encoding="utf-8"))
        next(rows, None)
        lineage = load_masons(rows)

    master_count = len([mason for mason in lineage.masons if mason.year is not None])
    officer_count = len(lineage.masons) - master_count
    print(f"Loaded {master_count} masters and {officer_count} officers")
    return lineage
