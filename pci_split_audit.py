"""
Reproducible train/test audit for pci_localization.ipynb.

Same loaders, preprocess, engineer_features, prepare_ml_data, and
sklearn.model_selection.train_test_split(..., test_size=0.2, random_state=42).
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


def load_folder(folder_path: str, mode_label: str) -> pd.DataFrame:
    all_dfs = []
    for f in sorted(glob.glob(os.path.join(folder_path, "*.csv"))):
        df = pd.read_csv(f, na_values=["n/a", "", " "], low_memory=False)
        df.columns = df.columns.str.strip()
        for col in df.columns:
            if col == "Time":
                continue
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.strip()
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["source_file"] = os.path.basename(f)
        all_dfs.append(df)
    combined = pd.concat(all_dfs, ignore_index=True)
    combined["mode"] = mode_label
    return combined


def preprocess(df: pd.DataFrame):
    df = df.copy()
    df["Longitude"] = df.groupby("source_file")["Longitude"].ffill()
    df["Latitude"] = df.groupby("source_file")["Latitude"].ffill()
    df["Longitude"] = df.groupby("source_file")["Longitude"].bfill()
    df["Latitude"] = df.groupby("source_file")["Latitude"].bfill()
    df = df.dropna(subset=["Longitude", "Latitude"])
    feature_cols = []
    for col in df.columns:
        if any(
            k in col
            for k in [
                "RSRP",
                "RSSI",
                "RSRQ",
                "CQI",
                "Rank indication",
                "Pathloss",
                "Timing advance",
                "Physical cell identity",
                "Channel number",
            ]
        ):
            if "percentage" not in col:
                feature_cols.append(col)
    if "Velocity" in df.columns:
        feature_cols.append("Velocity")
    keep_cols = ["Time", "Longitude", "Latitude", "mode", "source_file"] + feature_cols
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols]
    group_cols = ["Time", "source_file", "mode"]
    agg_dict = {}
    for c in df.columns:
        if c in group_cols or c in ["Longitude", "Latitude"]:
            continue
        if "Physical cell" in c or "Channel number" in c:
            agg_dict[c] = "first"
        else:
            agg_dict[c] = "mean"
    agg_dict["Longitude"] = "first"
    agg_dict["Latitude"] = "first"
    df_agg = df.groupby(group_cols, sort=False).agg(agg_dict).reset_index()
    return df_agg, [c for c in feature_cols if c in df_agg.columns]


def engineer_features(X_df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
    valid_cols = [c for c in feature_cols if c in X_df.columns and X_df[c].notna().any()]
    X = X_df[valid_cols].copy()
    rsrp = [c for c in valid_cols if "RSRP" in c and "subband" not in c.lower()]
    if len(rsrp) >= 2:
        X["RSRP_mean"] = X[rsrp].mean(axis=1)
        X["RSRP_std"] = X[rsrp].std(axis=1)
        X["RSRP_max"] = X[rsrp].max(axis=1)
        X["RSRP_min"] = X[rsrp].min(axis=1)
        X["RSRP_range"] = X["RSRP_max"] - X["RSRP_min"]
        X["RSRP_nports"] = X[rsrp].notna().sum(axis=1)
        X["RSRP_dom"] = X["RSRP_max"] - X["RSRP_mean"]
    rssi = [c for c in valid_cols if "RSSI" in c]
    if len(rssi) >= 2:
        X["RSSI_mean"] = X[rssi].mean(axis=1)
        X["RSSI_std"] = X[rssi].std(axis=1)
        X["RSSI_range"] = X[rssi].max(axis=1) - X[rssi].min(axis=1)
    rsrq = [c for c in valid_cols if "RSRQ" in c]
    if len(rsrq) >= 2:
        X["RSRQ_mean"] = X[rsrq].mean(axis=1)
        X["RSRQ_std"] = X[rsrq].std(axis=1)
    cqi_wb = [c for c in valid_cols if "Wideband CQI" in c]
    if len(cqi_wb) >= 2:
        X["CQI_WB_mean"] = X[cqi_wb].mean(axis=1)
    cqi_sb = [c for c in valid_cols if "subband" in c.lower()]
    if len(cqi_sb) >= 2:
        X["CQI_SB_mean"] = X[cqi_sb].mean(axis=1)
        X["CQI_SB_std"] = X[cqi_sb].std(axis=1)
    if len(rsrp) >= 1 and len(rssi) >= 1:
        X["RSRP_RSSI_diff"] = X[rsrp[0]] - X[rssi[0]]
    ta_c = [c for c in valid_cols if "Timing advance" in c and "percentage" not in c.lower()]
    if ta_c:
        X["TA_feat"] = pd.to_numeric(X[ta_c[0]], errors="coerce")
    pl_c = [c for c in valid_cols if "Pathloss" in c and "pcell" in c.lower()]
    if not pl_c:
        pl_c = [c for c in valid_cols if "Pathloss" in c]
    if pl_c:
        X["Pathloss_feat"] = pd.to_numeric(X[pl_c[0]], errors="coerce")
    if "Velocity" in X.columns:
        X["Velocity_abs"] = pd.to_numeric(X["Velocity"], errors="coerce").abs()
    return X


def prepare_ml_data(df: pd.DataFrame, feature_cols: list):
    X_eng = engineer_features(df, feature_cols)
    y = df[["Longitude", "Latitude"]].copy()
    combined = pd.concat([X_eng.reset_index(drop=True), y.reset_index(drop=True)], axis=1)
    combined = combined.dropna(axis=1, how="all")
    combined = combined.dropna(subset=["Longitude", "Latitude"])
    feat = [c for c in combined.columns if c not in ["Longitude", "Latitude"]]
    return combined[feat].values, combined[["Longitude", "Latitude"]].values, feat


def load_kaust_preprocessed(base_dir: str):
    bus_raw = load_folder(os.path.join(base_dir, "bus_kaust"), "bus")
    car_raw = load_folder(os.path.join(base_dir, "car_kaust"), "car")
    walk_raw = load_folder(os.path.join(base_dir, "walk_kaust"), "walk")
    all_raw = pd.concat([bus_raw, car_raw, walk_raw], ignore_index=True)
    return preprocess(all_raw)


def train_test_audit_table(base_dir: str) -> pd.DataFrame:
    """Rows: Bus, Car, Walk, Combined — same n_train/n_test as pci_localization."""
    all_data, feature_cols = load_kaust_preprocessed(base_dir)
    bus_data = all_data[all_data["mode"] == "bus"].copy()
    car_data = all_data[all_data["mode"] == "car"].copy()
    walk_data = all_data[all_data["mode"] == "walk"].copy()
    rows = []
    for name, d in [
        ("Bus", bus_data),
        ("Car", car_data),
        ("Walk", walk_data),
        ("Combined", all_data),
    ]:
        _, y, _ = prepare_ml_data(d, feature_cols)
        n = len(y)
        idx = np.arange(n)
        tr_idx, te_idx = train_test_split(idx, test_size=0.2, random_state=42)
        assert len(set(tr_idx) & set(te_idx)) == 0
        assert len(tr_idx) + len(te_idx) == n
        lon_tr, lat_tr = y[tr_idx, 0], y[tr_idx, 1]
        lon_te, lat_te = y[te_idx, 0], y[te_idx, 1]
        rows.append(
            {
                "Dataset": name,
                "n_rows": n,
                "n_train": len(tr_idx),
                "n_test": len(te_idx),
                "test_frac_%": round(100.0 * len(te_idx) / n, 4),
                "lon_train_[min,max]": (round(float(lon_tr.min()), 5), round(float(lon_tr.max()), 5)),
                "lon_test_[min,max]": (round(float(lon_te.min()), 5), round(float(lon_te.max()), 5)),
                "lat_train_[min,max]": (round(float(lat_tr.min()), 5), round(float(lat_tr.max()), 5)),
                "lat_test_[min,max]": (round(float(lat_te.min()), 5), round(float(lat_te.max()), 5)),
            }
        )
    return pd.DataFrame(rows)


def assert_disjoint_splits(base_dir: str) -> None:
    train_test_audit_table(base_dir)  # raises if overlap
