"""
Generate GPS localization maps for all 3 cities x 4 modes.
Shows actual (blue) vs predicted (red) vs error lines (gray) for points with <200m error.
Saves PNGs to report/figures/.
"""
import os, glob, warnings, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from sklearn.model_selection import train_test_split
from sklearn.ensemble import ExtraTreesRegressor
from math import radians, sin, cos, sqrt, atan2

warnings.filterwarnings('ignore')
plt.rcParams['figure.dpi'] = 150
plt.rcParams['font.size'] = 9

OUTPUT_DIR = '/Users/ahmadjaroush/Downloads/Kaust/report/figures'
os.makedirs(OUTPUT_DIR, exist_ok=True)

CITIES = {
    'kaust': {
        'base': '/Users/ahmadjaroush/Downloads/Kaust',
        'folders': {'bus': 'bus_kaust', 'car': 'car_kaust', 'walk': 'walk_kaust'},
        'label': 'KAUST',
    },
    'jeddah': {
        'base': '/Users/ahmadjaroush/Downloads/jedda',
        'folders': {'bus': 'bus_jeddah', 'car': 'car_jeddah', 'walk': 'walk_jeddah'},
        'label': 'Jeddah',
    },
    'mekkah': {
        'base': '/Users/ahmadjaroush/Downloads/mekkah',
        'folders': {'bus': 'bus_mekkah', 'car': 'car_mekkah', 'walk': 'walk_mekkah'},
        'label': 'Mekkah',
    },
}

# --------------- Pipeline functions (from pci_localization.ipynb) ---------------

def load_folder(folder_path, mode_label):
    all_dfs = []
    for f in sorted(glob.glob(os.path.join(folder_path, '*.csv'))):
        df = pd.read_csv(f, na_values=['n/a', '', ' '])
        df.columns = df.columns.str.strip()
        for col in df.columns:
            if col not in ['Time', 'source_file', 'mode']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df['source_file'] = os.path.basename(f)
        df['mode'] = mode_label
        df['Longitude'] = df['Longitude'].ffill().bfill()
        df['Latitude'] = df['Latitude'].ffill().bfill()
        all_dfs.append(df)
    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)


def preprocess(df):
    df = df.copy()
    df['Longitude'] = df.groupby('source_file')['Longitude'].ffill()
    df['Longitude'] = df.groupby('source_file')['Longitude'].bfill()
    df['Latitude'] = df.groupby('source_file')['Latitude'].ffill()
    df['Latitude'] = df.groupby('source_file')['Latitude'].bfill()
    df = df.dropna(subset=['Longitude', 'Latitude'])
    df = df[(df['Longitude'] != 0) & (df['Latitude'] != 0)]

    feature_cols = []
    for col in df.columns:
        if any(k in col for k in ['RSRP', 'RSSI', 'RSRQ', 'CQI', 'Rank indication',
                                   'Pathloss', 'Timing advance', 'Physical cell identity',
                                   'Channel number']):
            if 'percentage' not in col:
                feature_cols.append(col)
    if 'Velocity' in df.columns:
        feature_cols.append('Velocity')

    keep_cols = ['Time', 'Longitude', 'Latitude', 'mode', 'source_file'] + feature_cols
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols]

    group_cols = ['Time', 'source_file', 'mode']
    agg_dict = {}
    for c in df.columns:
        if c in group_cols:
            continue
        if c in ['Longitude', 'Latitude'] or 'Physical cell' in c or 'Channel number' in c:
            agg_dict[c] = 'first'
        else:
            agg_dict[c] = 'mean'
    df_agg = df.groupby(group_cols, as_index=False).agg(agg_dict)
    return df_agg, [c for c in feature_cols if c in df_agg.columns]


def engineer_features(X_df, feature_cols):
    valid_cols = [c for c in feature_cols if c in X_df.columns and X_df[c].notna().any()]
    X = X_df[valid_cols].copy()
    rsrp = [c for c in valid_cols if 'RSRP' in c and 'subband' not in c.lower()]
    if len(rsrp) >= 2:
        X['RSRP_mean'] = X[rsrp].mean(axis=1)
        X['RSRP_std'] = X[rsrp].std(axis=1)
        X['RSRP_max'] = X[rsrp].max(axis=1)
        X['RSRP_min'] = X[rsrp].min(axis=1)
        X['RSRP_range'] = X['RSRP_max'] - X['RSRP_min']
    rssi = [c for c in valid_cols if 'RSSI' in c]
    if len(rssi) >= 2:
        X['RSSI_mean'] = X[rssi].mean(axis=1)
        X['RSSI_std'] = X[rssi].std(axis=1)
        X['RSSI_range'] = X[rssi].max(axis=1) - X[rssi].min(axis=1)
    rsrq = [c for c in valid_cols if 'RSRQ' in c]
    if len(rsrq) >= 2:
        X['RSRQ_mean'] = X[rsrq].mean(axis=1)
        X['RSRQ_std'] = X[rsrq].std(axis=1)
    cqi = [c for c in valid_cols if 'CQI' in c]
    if len(cqi) >= 2:
        X['CQI_mean'] = X[cqi].mean(axis=1)
        X['CQI_std'] = X[cqi].std(axis=1)
    if len(rsrp) >= 1 and len(rssi) >= 1:
        X['RSRP_RSSI_diff'] = X[rsrp[0]] - X[rssi[0]]
    return X


def prepare_ml_data(df, feature_cols):
    X_eng = engineer_features(df, feature_cols)
    y = df[['Longitude', 'Latitude']].copy()
    combined = pd.concat([X_eng.reset_index(drop=True), y.reset_index(drop=True)], axis=1)
    combined = combined.dropna(axis=1, how='all')
    combined = combined.dropna(subset=['Longitude', 'Latitude'])
    feat = [c for c in combined.columns if c not in ['Longitude', 'Latitude']]
    return combined[feat].values, combined[['Longitude', 'Latitude']].values, feat


def impute_after_split(X_train, X_test):
    medians = np.nanmedian(X_train, axis=0)
    fill = np.where(np.isnan(medians), 0.0, medians)
    X_train = np.where(np.isnan(X_train), fill, X_train)
    X_test = np.where(np.isnan(X_test), fill, X_test)
    return X_train, X_test


def add_pci_fingerprints(X_train, y_train, X_test, feat_names):
    id_cols = [(i, n) for i, n in enumerate(feat_names)
               if 'Physical cell' in n or 'Channel number' in n]
    if not id_cols:
        return X_train, X_test, feat_names

    new_names = list(feat_names)
    train_extras, test_extras = [], []

    for col_idx, col_name in id_cols:
        lookup = {}
        vals = X_train[:, col_idx]
        for v, lo, la in zip(vals, y_train[:, 0], y_train[:, 1]):
            if not np.isnan(v):
                lookup.setdefault(v, []).append((lo, la))
        lookup = {k: (np.mean([p[0] for p in v]), np.mean([p[1] for p in v]))
                  for k, v in lookup.items()}
        default_lon, default_lat = np.mean(y_train[:, 0]), np.mean(y_train[:, 1])

        def _enc(arr):
            lo = np.array([lookup.get(v, (default_lon, default_lat))[0]
                           if not np.isnan(v) else default_lon for v in arr])
            la = np.array([lookup.get(v, (default_lon, default_lat))[1]
                           if not np.isnan(v) else default_lat for v in arr])
            return lo, la

        tr_lo, tr_la = _enc(X_train[:, col_idx])
        te_lo, te_la = _enc(X_test[:, col_idx])
        train_extras.extend([tr_lo, tr_la])
        test_extras.extend([te_lo, te_la])
        short = col_name.replace('Physical cell identity ', 'PCI_').replace('Channel number ', 'CH_')
        new_names.extend([f'{short}_cLon', f'{short}_cLat'])

    X_train = np.hstack([X_train] + [e.reshape(-1, 1) for e in train_extras])
    X_test = np.hstack([X_test] + [e.reshape(-1, 1) for e in test_extras])
    return X_train, X_test, new_names


def haversine_error(y_true, y_pred):
    R = 6371000
    lon1, lat1 = np.radians(y_true[:, 0]), np.radians(y_true[:, 1])
    lon2, lat2 = np.radians(y_pred[:, 0]), np.radians(y_pred[:, 1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def train_model(mode_name, df, feature_cols, max_samples=50000):
    print(f'  Training {mode_name} ({len(df):,} rows)...', end=' ', flush=True)
    X, y, feat_names = prepare_ml_data(df, feature_cols)
    if len(X) > max_samples:
        idx = np.random.RandomState(42).choice(len(X), max_samples, replace=False)
        X, y = X[idx], y[idx]

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    X_tr, X_te = impute_after_split(X_tr, X_te)
    X_tr, X_te, feat_names = add_pci_fingerprints(X_tr, y_tr, X_te, feat_names)

    best_err, best_pred = float('inf'), None
    for mf in [1.0, 0.7, 'sqrt']:
        m = ExtraTreesRegressor(n_estimators=500, max_features=mf, min_samples_leaf=1,
                                n_jobs=-1, random_state=42)
        m.fit(X_tr, y_tr)
        pred = m.predict(X_te)
        err = np.mean(haversine_error(y_te, pred))
        if err < best_err:
            best_err = err
            best_pred = pred

    print(f'mean error = {best_err:.1f}m')
    return {'mode': mode_name, 'y_test': y_te, 'best_pred': best_pred, 'mean_err': best_err}


def make_gps_map(res, city_label, filename, max_pts=600, error_thresh=200):
    yt, yp = res['y_test'], res['best_pred']
    de = haversine_error(yt, yp)

    mask = de < error_thresh
    yt, yp, de = yt[mask], yp[mask], de[mask]

    if len(yt) > max_pts:
        idx = np.random.RandomState(42).choice(len(yt), max_pts, replace=False)
        yt, yp, de = yt[idx], yp[idx], de[idx]

    sort_idx = np.argsort(de)[::-1]
    yt, yp, de = yt[sort_idx], yp[sort_idx], de[sort_idx]

    fig, ax = plt.subplots(figsize=(5.5, 4.5))

    for i in range(len(yt)):
        alpha = 0.15 + 0.35 * (de[i] / max(de.max(), 1))
        ax.plot([yt[i, 0], yp[i, 0]], [yt[i, 1], yp[i, 1]],
                color='#999999', linewidth=0.4, alpha=alpha)

    ax.scatter(yt[:, 0], yt[:, 1], s=6, c='#2166ac', alpha=0.7, zorder=3, label='Actual')
    sc = ax.scatter(yp[:, 0], yp[:, 1], s=6, c=de, cmap='RdYlGn_r',
                    vmin=0, vmax=min(error_thresh, de.max()), alpha=0.7, zorder=4)

    cbar = plt.colorbar(sc, ax=ax, shrink=0.75, pad=0.02)
    cbar.set_label('Error (m)', fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#2166ac',
               markersize=5, label='Actual GPS'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#d73027',
               markersize=5, label='Predicted GPS'),
        Line2D([0], [0], color='#999999', linewidth=1, label='Error line'),
    ]
    ax.legend(handles=legend_elements, loc='best', fontsize=7, framealpha=0.85)

    n_shown = mask.sum()
    n_total = len(res['y_test'])
    ax.set_title(f'{city_label} — {res["mode"]} Mode\n'
                 f'Mean error: {res["mean_err"]:.1f}m  |  '
                 f'Showing {n_shown}/{n_total} pts (<{error_thresh}m)',
                 fontsize=9, fontweight='bold')
    ax.set_xlabel('Longitude', fontsize=8)
    ax.set_ylabel('Latitude', fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f'    Saved {filename}')


# --------------- Main ---------------

def process_city(city_key, city_cfg):
    print(f'\n{"="*60}')
    print(f'  {city_cfg["label"].upper()}')
    print(f'{"="*60}')

    base = city_cfg['base']
    folders = city_cfg['folders']

    bus_raw = load_folder(os.path.join(base, folders['bus']), 'bus')
    car_raw = load_folder(os.path.join(base, folders['car']), 'car')
    walk_raw = load_folder(os.path.join(base, folders['walk']), 'walk')

    all_raw = pd.concat([bus_raw, car_raw, walk_raw], ignore_index=True)
    all_data, feature_cols = preprocess(all_raw)

    bus_data = all_data[all_data['mode'] == 'bus'].copy()
    car_data = all_data[all_data['mode'] == 'car'].copy()
    walk_data = all_data[all_data['mode'] == 'walk'].copy()

    print(f'  Data: Bus={len(bus_data):,}  Car={len(car_data):,}  Walk={len(walk_data):,}  Total={len(all_data):,}')

    results = {}
    for mode_name, mode_data in [('Bus', bus_data), ('Car', car_data),
                                  ('Walk', walk_data), ('Combined', all_data)]:
        if len(mode_data) < 50:
            print(f'  Skipping {mode_name} (too few samples)')
            continue
        res = train_model(mode_name, mode_data, feature_cols)
        results[mode_name] = res
        fname = f'map_{city_key}_{mode_name.lower()}.png'
        make_gps_map(res, city_cfg['label'], fname)

    return results


if __name__ == '__main__':
    for city_key, city_cfg in CITIES.items():
        process_city(city_key, city_cfg)
    print('\nDone! All maps saved to', OUTPUT_DIR)
