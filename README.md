# Mobisense

Mobisense contains Python scripts for cellular, PCI/LTE/GNSS, and trajectory-based localization experiments.

## Contents

- `run_pci_pipeline.py` runs the PCI + LTE + GNSS localization pipeline.
- `run_tracking_pipeline.py` runs the tracking-window localization pipeline.
- `generate_all_figures.py` and `generate_tracking_figures.py` create publication figures from pipeline outputs.
- `generate_maps.py`, `generate_gps_maps.py`, `capture_maps.py`, `filter_maps.py`, and `screenshot_maps.py` generate and capture map visualizations.
- `pci_split_audit.py` audits train/test splits.
- `scripts/export_fused_train_test_metrics.py` exports fused train/test metrics.
- `MAIDSTECH_API_REFERENCE.md` and `MAIDSTECH_PTC_API.md` document related API usage.

Datasets, generated results, notebooks, figures, archives, and map outputs are intentionally excluded from Git.

## Data

Raw route datasets should remain local and are not versioned in this repository. Regenerate result files and figures from the scripts after placing the required city data folders beside the code.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The scripts expect the raw city route data folders to exist locally, for example `bus_kaust`, `car_kaust`, and `walk_kaust`.
