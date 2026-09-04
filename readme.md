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

The complete lineage is written to `Lineage.svg`. Batch files are written to `Lineage_batches`, starting with the oldest master rows and containing 30 master rows each. Historical batches contain five master rings without the gray officer circles. Only the latest partial batch includes the current officers, starts at the same center as the complete lineage, and leaves its outer ring unfinished.

## Run the tests

```bash
python -m unittest -v
```
