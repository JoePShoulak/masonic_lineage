# Masonic Lineage

Generates `Lineage.svg` from the lodge lineage published in the Google Sheet configured by `LINK` in `main.py`.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
```

## Generate the lineage

Generate both the complete lineage and the 30-year batch files:

```bash
python main.py
```

Generate only the complete lineage:

```bash
python main.py all
```

Generate only the batch files:

```bash
python main.py batches
```

The complete lineage is written to `Lineage.svg`. Batch files are written to `Lineage_batches`, starting with the oldest master rows and containing up to 30 master rows each. Adjacent batches overlap by one six-member ring, so the inner ring of an older batch is repeated as the outer ring of the next newer batch. Historical batches contain five master rings without the gray officer circles. Only the latest partial batch includes the current officers, starts at the same center as the complete lineage, and leaves its outer ring unfinished.

Set `BATCH_OVERLAP_RINGS` to `0` in `main.py` to restore non-overlapping batches.

## Spreadsheet requirements

Each non-empty row must contain a name column and a year column. Current officers use a blank year. Every past-master row must contain one numeric year, and a year can only appear once.

The script stops before drawing if a row has a missing name, missing column, invalid year, or duplicate year. An appointee name that does not match any row produces a warning with the spreadsheet row number.

## Run the tests

```bash
python -m unittest -v
```
