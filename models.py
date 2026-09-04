class Lineage:
    def __init__(self):
        self.masons: list[Mason] = []

    def add(self, mason: "Mason") -> None:
        self.masons.append(mason)


class Mason:
    def __init__(self, name: str, year: int | None) -> None:
        self.name = name
        self.year = year
        self.is_returning_master = False
        self.appointees: list[Mason] = []

    @property
    def year_as_master(self) -> str:
        if self.year is None:
            return ""
        return str(self.year)
