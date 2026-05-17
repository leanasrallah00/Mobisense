#!/usr/bin/env python3
"""Run pci_localization training pipeline with reduced max_samples and write train_test_fused_mean_error.csv.

Usage (from repo root):
  python scripts/export_fused_train_test_metrics.py

Requires same dependencies as pci_localization.ipynb. Uses max_samples=12000 for speed.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

NB = os.path.join(ROOT, "pci_localization.ipynb")


def main():
    nb = json.load(open(NB))
    ns = {"__name__": "__main__"}
    # Setup cell
    exec(compile("".join(nb["cells"][2]["source"]).replace("%matplotlib inline", "#"), "<setup>", "exec"), ns)
    # Load data
    exec(compile("".join(nb["cells"][4]["source"]), "<load>", "exec"), ns)
    # Utilities
    exec(compile("".join(nb["cells"][6]["source"]), "<utils>", "exec"), ns)
    # Training defs
    exec(compile("".join(nb["cells"][8]["source"]), "<train>", "exec"), ns)

    ms = 12000
    code = f"""
bus_results  = train_model_per_pci('Bus',  bus_data,  feature_cols, max_samples={ms})
car_results  = train_model_per_pci('Car',  car_data,  feature_cols, max_samples={ms})
walk_results = train_model_per_pci('Walk', walk_data, feature_cols, max_samples={ms})
combined_results = train_model('Combined', all_data, feature_cols, max_samples={ms})
all_res = [bus_results, car_results, walk_results, combined_results]
"""
    exec(compile(code, "<run>", "exec"), ns)

    out_dir = ns["OUTPUT_DIR"]
    rows = []
    for res in ns["all_res"]:
        if "ens_stats" in res and "ens_train" in res:
            rows.append(
                {
                    "Mode": res["mode"],
                    "Model": res["ens_stats"]["Model"],
                    "Train_mean_m": float(res["ens_train"]),
                    "Test_mean_m": float(res["ens_stats"]["Mean_m"]),
                }
            )
    import pandas as pd

    path = os.path.join(out_dir, "train_test_fused_mean_error.csv")
    pd.DataFrame(rows).to_csv(path, index=False)
    print("Wrote", path)
    print(pd.DataFrame(rows))


if __name__ == "__main__":
    main()
