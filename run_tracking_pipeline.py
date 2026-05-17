#!/usr/bin/env python3
"""
Tracking-based localization pipeline.

Instead of predicting (lon, lat) from a single observation, this pipeline:
1. Creates sliding windows of K consecutive observations from each route
2. Concatenates features from all K time points into one feature vector
3. Trains ExtraTrees to predict all K (lon, lat) pairs simultaneously
4. Optionally predicts position at time K+1 using features + predicted positions

This gives better accuracy than single-point localization because the model
can match K-point test trajectories against K-point training trajectories.
"""

import os, glob, warnings, time, json
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import train_test_split
from math import radians, sin, cos, sqrt, atan2

warnings.filterwarnings('ignore')

K_WINDOW = 5          # window size
MAX_SAMPLES = 8000    # per city (for speed)
N_ESTIMATORS = 200

CITY_CONFIG = {
    'KAUST': {
        'base': '/Users/ahmadjaroush/Downloads/Kaust',
        'bus': 'bus_kaust', 'car': 'car_kaust', 'walk': 'walk_kaust',
    },
    'Jeddah': {
        'base': '/Users/ahmadjaroush/Downloads/jedda',
        'bus': 'bus_jeddah', 'car': 'car_jeddah', 'walk': 'walk_jeddah',
    },
    'Mekkah': {
        'base': '/Users/ahmadjaroush/Downloads/mekkah',
        'bus': 'bus_mekkah', 'car': 'car_mekkah', 'walk': 'walk_mekkah',
    },
}

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 6371000 * 2 * atan2(sqrt(a), sqrt(1-a))

def haversine_vec(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 6371000 * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

def load_folder(folder, mode):
    dfs = []
    for f in sorted(glob.glob(os.path.join(folder, '*.csv'))):
        df = pd.read_csv(f, na_values=['n/a', '', ' '])
        df.columns = df.columns.str.strip()
        for c in df.columns:
            if c == 'Time':
                continue
            if df[c].dtype == object:
                df[c] = pd.to_numeric(df[c].astype(str).str.strip(), errors='coerce')
        df['source_file'] = os.path.basename(f)
        dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    out = pd.concat(dfs, ignore_index=True)
    out['mode'] = mode
    return out

def preprocess(df):
    df = df.copy()
    df['Longitude'] = df.groupby('source_file')['Longitude'].ffill().bfill()
    df['Latitude'] = df.groupby('source_file')['Latitude'].ffill().bfill()
    df = df.dropna(subset=['Longitude', 'Latitude'])

    feat_kw = ['RSRP', 'RSSI', 'RSRQ', 'CQI', 'Rank indication',
               'Pathloss', 'Timing advance', 'Physical cell identity',
               'Channel number']
    feat_cols = []
    for c in df.columns:
        if any(k in c for k in feat_kw) and 'percentage' not in c:
            feat_cols.append(c)
    if 'Velocity' in df.columns:
        feat_cols.append('Velocity')

    keep = ['Time', 'Longitude', 'Latitude', 'mode', 'source_file'] + feat_cols
    keep = [c for c in keep if c in df.columns]
    df = df[keep]

    grp = ['Time', 'source_file', 'mode']
    agg = {}
    for c in df.columns:
        if c in grp or c in ['Longitude', 'Latitude']:
            continue
        agg[c] = 'first' if ('Physical cell' in c or 'Channel number' in c) else 'mean'
    agg['Longitude'] = 'first'
    agg['Latitude'] = 'first'
    return df.groupby(grp, sort=False).agg(agg).reset_index(), \
           [c for c in feat_cols if c in df.columns]

def engineer_single(X_df, feat_cols):
    vc = [c for c in feat_cols if c in X_df.columns and X_df[c].notna().any()]
    X = X_df[vc].copy()
    rsrp = [c for c in vc if 'RSRP' in c and 'subband' not in c.lower()]
    if len(rsrp) >= 2:
        X['RSRP_mean'] = X[rsrp].mean(axis=1)
        X['RSRP_std'] = X[rsrp].std(axis=1)
        X['RSRP_range'] = X[rsrp].max(axis=1) - X[rsrp].min(axis=1)
    rssi = [c for c in vc if 'RSSI' in c]
    if len(rssi) >= 2:
        X['RSSI_mean'] = X[rssi].mean(axis=1)
        X['RSSI_std'] = X[rssi].std(axis=1)
    rsrq = [c for c in vc if 'RSRQ' in c]
    if len(rsrq) >= 2:
        X['RSRQ_mean'] = X[rsrq].mean(axis=1)
    cqi = [c for c in vc if 'Wideband CQI' in c]
    if len(cqi) >= 2:
        X['CQI_WB_mean'] = X[cqi].mean(axis=1)
    ta = [c for c in vc if 'Timing advance' in c and 'percentage' not in c.lower()]
    if ta:
        X['TA_feat'] = pd.to_numeric(X[ta[0]], errors='coerce')
    pl = [c for c in vc if 'Pathloss' in c]
    if pl:
        X['PL_feat'] = pd.to_numeric(X[pl[0]], errors='coerce')
    if 'Velocity' in X.columns:
        X['Vel_abs'] = pd.to_numeric(X['Velocity'], errors='coerce').abs()
    return X

def create_windows(feat_matrix, coords, source_files, k):
    """Create sliding windows of size k from temporally ordered data within each route."""
    windows_X = []
    windows_Y = []
    windows_Y_kplus1 = []

    unique_files = np.unique(source_files)
    for sf in unique_files:
        mask = source_files == sf
        idx = np.where(mask)[0]
        if len(idx) < k + 1:
            continue
        feat_sf = feat_matrix[idx]
        coord_sf = coords[idx]

        for i in range(0, len(idx) - k, max(1, k // 2)):
            window_feat = feat_sf[i:i+k].flatten()
            window_coord = coord_sf[i:i+k].flatten()
            windows_X.append(window_feat)
            windows_Y.append(window_coord)

            if i + k < len(idx):
                windows_Y_kplus1.append(coord_sf[i+k])
            else:
                windows_Y_kplus1.append(coord_sf[i+k-1])

    return np.array(windows_X), np.array(windows_Y), np.array(windows_Y_kplus1)


def run_city(city_name, cfg):
    print(f"\n{'='*60}")
    print(f"  TRACKING: {city_name}  (K={K_WINDOW})")
    print(f"{'='*60}")
    t0 = time.time()

    base = cfg['base']
    dfs = []
    for mode_key, mode_name in [('bus', 'Bus'), ('car', 'Car'), ('walk', 'Walk')]:
        folder = os.path.join(base, cfg[mode_key])
        if os.path.isdir(folder):
            d = load_folder(folder, mode_name)
            if len(d) > 0:
                dfs.append(d)
                print(f"  {mode_name}: {len(d)} raw rows")
    if not dfs:
        print(f"  No data for {city_name}, skipping.")
        return None
    raw = pd.concat(dfs, ignore_index=True)
    print(f"  Total raw: {len(raw)}")

    df, feat_cols = preprocess(raw)
    print(f"  After preprocess: {len(df)} rows, {len(feat_cols)} feature cols")

    X_eng = engineer_single(df, feat_cols)
    eng_cols = list(X_eng.columns)
    n_feat = len(eng_cols)
    print(f"  Engineered features: {n_feat}")

    feat_matrix = X_eng.values.astype(np.float32)
    coords = df[['Longitude', 'Latitude']].values.astype(np.float64)
    source_files = df['source_file'].values

    med = np.nanmedian(feat_matrix, axis=0)
    for j in range(feat_matrix.shape[1]):
        mask = np.isnan(feat_matrix[:, j])
        feat_matrix[mask, j] = med[j]
    feat_matrix = np.nan_to_num(feat_matrix, nan=0.0)

    print(f"  Creating K={K_WINDOW} windows...")
    win_X, win_Y, win_Y_kp1 = create_windows(feat_matrix, coords, source_files, K_WINDOW)
    print(f"  Total windows: {len(win_X)}")

    if len(win_X) > MAX_SAMPLES:
        rng = np.random.RandomState(42)
        idx = rng.choice(len(win_X), MAX_SAMPLES, replace=False)
        win_X = win_X[idx]
        win_Y = win_Y[idx]
        win_Y_kp1 = win_Y_kp1[idx]
        print(f"  Sampled down to {MAX_SAMPLES} windows")

    X_train, X_test, Y_train, Y_test = train_test_split(
        win_X, win_Y, test_size=0.2, random_state=42)
    _, _, Ykp1_train, Ykp1_test = train_test_split(
        win_X, win_Y_kp1, test_size=0.2, random_state=42)

    print(f"  Train: {len(X_train)}, Test: {len(X_test)}")

    # --- Tracking model: predict K positions from K observations ---
    print(f"  Training tracking model (K-point)...")
    model_track = ExtraTreesRegressor(n_estimators=N_ESTIMATORS, n_jobs=-1, random_state=42)
    model_track.fit(X_train, Y_train)
    Y_pred = model_track.predict(X_test)

    errors_per_point = []
    for i in range(K_WINDOW):
        lon_pred = Y_pred[:, i*2]
        lat_pred = Y_pred[:, i*2+1]
        lon_true = Y_test[:, i*2]
        lat_true = Y_test[:, i*2+1]
        errs = haversine_vec(lon_pred, lat_pred, lon_true, lat_true)
        errors_per_point.append(errs)
    all_tracking_errors = np.concatenate(errors_per_point)

    track_mean = np.mean(all_tracking_errors)
    track_median = np.median(all_tracking_errors)
    track_p90 = np.percentile(all_tracking_errors, 90)
    track_p95 = np.percentile(all_tracking_errors, 95)

    print(f"\n  --- K-Point Tracking Results ---")
    print(f"  Mean:   {track_mean:.1f} m")
    print(f"  Median: {track_median:.1f} m")
    print(f"  P90:    {track_p90:.1f} m")
    print(f"  P95:    {track_p95:.1f} m")

    per_step_means = [np.mean(e) for e in errors_per_point]
    print(f"  Per-step means: {['%.1f' % m for m in per_step_means]}")

    # --- K+1 Forecast: use K features + predicted K positions to predict K+1 ---
    print(f"\n  Training K+1 forecast model...")
    Y_train_pred_for_kp1 = model_track.predict(X_train)
    X_train_kp1 = np.hstack([X_train, Y_train_pred_for_kp1])
    Y_test_pred_for_kp1 = Y_pred
    X_test_kp1 = np.hstack([X_test, Y_test_pred_for_kp1])

    model_kp1 = ExtraTreesRegressor(n_estimators=N_ESTIMATORS, n_jobs=-1, random_state=42)
    model_kp1.fit(X_train_kp1, Ykp1_train)
    Ykp1_pred = model_kp1.predict(X_test_kp1)

    kp1_errors = haversine_vec(Ykp1_pred[:, 0], Ykp1_pred[:, 1],
                                Ykp1_test[:, 0], Ykp1_test[:, 1])
    kp1_mean = np.mean(kp1_errors)
    kp1_median = np.median(kp1_errors)
    kp1_p90 = np.percentile(kp1_errors, 90)
    kp1_p95 = np.percentile(kp1_errors, 95)

    print(f"\n  --- K+1 Forecast Results ---")
    print(f"  Mean:   {kp1_mean:.1f} m")
    print(f"  Median: {kp1_median:.1f} m")
    print(f"  P90:    {kp1_p90:.1f} m")
    print(f"  P95:    {kp1_p95:.1f} m")

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.1f}s")

    return {
        'city': city_name,
        'n_windows': len(win_X),
        'n_train': len(X_train),
        'n_test': len(X_test),
        'K': K_WINDOW,
        'tracking': {
            'mean': round(track_mean, 1),
            'median': round(track_median, 1),
            'p90': round(track_p90, 1),
            'p95': round(track_p95, 1),
            'per_step_means': [round(m, 1) for m in per_step_means],
        },
        'forecast_kp1': {
            'mean': round(kp1_mean, 1),
            'median': round(kp1_median, 1),
            'p90': round(kp1_p90, 1),
            'p95': round(kp1_p95, 1),
        },
        'elapsed_s': round(elapsed, 1),
    }


if __name__ == '__main__':
    results = {}
    for city, cfg in CITY_CONFIG.items():
        res = run_city(city, cfg)
        if res:
            results[city] = res

    out_path = '/Users/ahmadjaroush/Downloads/Kaust/tracking_results.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")

    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    for city, r in results.items():
        t = r['tracking']
        f = r['forecast_kp1']
        print(f"\n  {city}:")
        print(f"    Tracking (K={r['K']}):  Mean={t['mean']}m  Median={t['median']}m  P90={t['p90']}m  P95={t['p95']}m")
        print(f"    Forecast (K+1):  Mean={f['mean']}m  Median={f['median']}m  P90={f['p90']}m  P95={f['p95']}m")
        print(f"    Per-step means: {t['per_step_means']}")
