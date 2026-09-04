from models import Lineage, Mason
from settings import BATCH_OVERLAP_RINGS, BATCH_SIZE, MEMBERS_PER_RING


def clone_lineage(masons: list[Mason]) -> Lineage:
    lineage = Lineage()
    cloned_masons = {}

    for mason in masons:
        cloned_mason = Mason(mason.name, mason.year)
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
    overlap_size = BATCH_OVERLAP_RINGS * MEMBERS_PER_RING
    batch_step = BATCH_SIZE - overlap_size

    if batch_step <= 0:
        raise ValueError("Batch overlap must be smaller than the batch size")

    batches = []
    for index in range(0, len(masters), batch_step):
        master_batch = masters[index:index + BATCH_SIZE]
        is_latest_batch = index + BATCH_SIZE >= len(masters)
        if is_latest_batch and len(master_batch) < BATCH_SIZE:
            batches.append(clone_lineage(officers + master_batch))
        else:
            batches.append(clone_lineage(master_batch))

    return batches


def get_batch_filename(batch: Lineage, batch_number: int) -> str:
    years = [mason.year for mason in batch.masons if mason.year is not None]
    oldest_year = min(years)
    newest_year = max(years)
    return f"Lineage_{batch_number:02d}_{oldest_year}-{newest_year}.svg"
