import sys
from pathlib import Path

from batching import build_lineage_batches, get_batch_filename
from drawing import draw_lineage
from lineage_data import load_lineage
from settings import BATCH_DIRECTORY


def generate_overall_lineage() -> None:
    lineage = load_lineage()
    draw_lineage(lineage)


def generate_lineage_batches() -> None:
    lineage = load_lineage()
    batches = build_lineage_batches(lineage)
    batch_directory = Path(BATCH_DIRECTORY)
    batch_directory.mkdir(exist_ok=True)

    for old_batch_file in batch_directory.glob("Lineage_*.svg"):
        old_batch_file.unlink()

    for batch_number, batch in enumerate(batches, start=1):
        filename = batch_directory / get_batch_filename(batch, batch_number)
        draw_lineage(batch, str(filename))


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
