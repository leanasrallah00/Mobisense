#!/usr/bin/env python3
"""
PCI + LTE + GNSS localization — lean pipeline for all cities.
Usage: python run_pci_pipeline.py [KAUST|Jeddah|Mekkah|ALL]
"""
import os, sys, glob, warnings, time
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import r2_score

warnings.filterwarnings('ignore')

CITY_CONFIG = {
    'KAUST': {
        'base': '/Users/ahmadjaroush/Downloads/Kaust',
        'bus': 'bus_kaust', 'car': 'car_kaust', 'walk': 'walk_kaust',
        'gnss_sigma': 22.0,
    },
    'Jeddah': {
        'base': '/Users/ahmadjaroush/Downloads/jedda',
        'bus': 'bus_jeddah', 'car': 'car_jeddah', 'walk': 'walk_jeddah',
        'gnss_sigma': 22.0,
    },
    'Mekkah': {
        'base': '/Users/ahmadjaroush/Downloads/mekkah',
        'bus': 'bus_mekkah', 'car': 'car_mekkah', 'walk': 'walk_mekkah',
        'gnss_sigma': 22.0,
    },
}
M_PER_DEG = 111_320.0

def haversine_error(y_true, y_pred):
    lon1, lat1 = np.radians(y_true[:,0]), np.radians(y_true[:,1])
    lon2, lat2 = np.radians(y_pred[:,0]), np.radians(y_pred[:,1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 6_371_000 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

def stats_dict(name, yt, yp):
    de = haversine_error(yt, yp)
    return {'Model': name,
            'R2_Lon': round(r2_score(yt[:,0], yp[:,0]), 4),
            'R2_Lat': round(r2_score(yt[:,1], yp[:,1]), 4),
            'Mean_m': round(float(np.mean(de)), 1),
            'Median_m': round(float(np.median(de)), 1),
            'P90_m': round(float(np.percentile(de, 90)), 1),
            'P95_m': round(float(np.percentile(de, 95)), 1),
            'dist_errors': de}

def load_folder(folder, mode):
    dfs = []
    for f in sorted(glob.glob(os.path.join(folder, '*.csv'))):
        df = pd.read_csv(f, na_values=['n/a', '', ' '])
        df.columns = df.columns.str.strip()
        for c in df.columns:
            if c == 'Time': continue
            if df[c].dtype == object:
                df[c] = pd.to_numeric(df[c].astype(str).str.strip(), errors='coerce')
        df['source_file'] = os.path.basename(f)
        dfs.append(df)
    out = pd.concat(dfs, ignore_index=True)
    out['mode'] = mode
    return out

def preprocess(df):
    df = df.copy()
    df['Longitude'] = df.groupby('source_file')['Longitude'].ffill().bfill()
    df['Latitude']  = df.groupby('source_file')['Latitude'].ffill().bfill()
    df = df.dropna(subset=['Longitude', 'Latitude'])
    feat_cols = []
    for c in df.columns:
        if any(k in c for k in ['RSRP','RSSI','RSRQ','CQI','Rank indication',
                                 'Pathloss','Timing advance','Physical cell identity',
                                 'Channel number']):
            if 'percentage' not in c:
                feat_cols.append(c)
    if 'Velocity' in df.columns:
        feat_cols.append('Velocity')
    keep = ['Time','Longitude','Latitude','mode','source_file'] + feat_cols
    keep = [c for c in keep if c in df.columns]
    df = df[keep]
    grp = ['Time','source_file','mode']
    agg = {}
    for c in df.columns:
        if c in grp or c in ['Longitude','Latitude']: continue
        agg[c] = 'first' if ('Physical cell' in c or 'Channel number' in c) else 'mean'
    agg['Longitude'] = 'first'; agg['Latitude'] = 'first'
    return df.groupby(grp, sort=False).agg(agg).reset_index(), \
           [c for c in feat_cols if c in df.columns]

def engineer(X_df, feat_cols):
    vc = [c for c in feat_cols if c in X_df.columns and X_df[c].notna().any()]
    X = X_df[vc].copy()
    rsrp = [c for c in vc if 'RSRP' in c and 'subband' not in c.lower()]
    if len(rsrp) >= 2:
        X['RSRP_mean'] = X[rsrp].mean(axis=1)
        X['RSRP_std']  = X[rsrp].std(axis=1)
        X['RSRP_range']= X[rsrp].max(axis=1) - X[rsrp].min(axis=1)
    rssi = [c for c in vc if 'RSSI' in c]
    if len(rssi) >= 2:
        X['RSSI_mean'] = X[rssi].mean(axis=1)
        X['RSSI_std']  = X[rssi].std(axis=1)
    rsrq = [c for c in vc if 'RSRQ' in c]
    if len(rsrq) >= 2:
        X['RSRQ_mean'] = X[rsrq].mean(axis=1)
    cqi = [c for c in vc if 'Wideband CQI' in c]
    if len(cqi) >= 2:
        X['CQI_WB_mean'] = X[cqi].mean(axis=1)
    ta = [c for c in vc if 'Timing advance' in c and 'percentage' not in c.lower()]
    if ta: X['TA_feat'] = pd.to_numeric(X[ta[0]], errors='coerce')
    pl = [c for c in vc if 'Pathloss' in c]
    if pl: X['PL_feat'] = pd.to_numeric(X[pl[0]], errors='coerce')
    if 'Velocity' in X.columns:
        X['Vel_abs'] = pd.to_numeric(X['Velocity'], errors='coerce').abs()
    return X

def prepare_data(df, feat_cols):
    X_eng = engineer(df, feat_cols)
    y = df[['Longitude','Latitude']].copy()
    comb = pd.concat([X_eng.reset_index(drop=True), y.reset_index(drop=True)], axis=1)
    comb = comb.dropna(axis=1, how='all').dropna(subset=['Longitude','Latitude'])
    feat = [c for c in comb.columns if c not in ['Longitude','Latitude']]
    pci_col = None
    for c in comb.columns:
        if 'Physical cell identity' in c and 'pcell' in c.lower():
            pci_col = c; break
    if not pci_col:
        for c in comb.columns:
            if 'Physical cell identity' in c:
                pci_col = c; break
    pci = pd.to_numeric(comb[pci_col], errors='coerce').values if pci_col else np.full(len(comb), np.nan)
    return comb[feat].values, comb[['Longitude','Latitude']].values, feat, pci

def impute(X_tr, X_te):
    med = np.nanmedian(X_tr, axis=0)
    fill = np.where(np.isnan(med), 0.0, med)
    return np.where(np.isnan(X_tr), fill, X_tr), np.where(np.isnan(X_te), fill, X_te)

def add_pci_fp(X_tr, y_tr, X_te, feat):
    id_cols = [(i,n) for i,n in enumerate(feat) if 'Physical cell' in n or 'Channel number' in n]
    if not id_cols: return X_tr, X_te, feat
    dlon, dlat = np.nanmean(y_tr[:,0]), np.nanmean(y_tr[:,1])
    etr, ete, en = [], [], []
    for ci, cn in id_cols:
        lk = {}
        for v in np.unique(X_tr[:,ci][~np.isnan(X_tr[:,ci])]):
            m = X_tr[:,ci] == v
            lk[v] = (np.mean(y_tr[m,0]), np.mean(y_tr[m,1]))
        def enc(arr):
            lo = np.array([lk.get(v,(dlon,dlat))[0] if not np.isnan(v) else dlon for v in arr])
            la = np.array([lk.get(v,(dlon,dlat))[1] if not np.isnan(v) else dlat for v in arr])
            return lo, la
        tlo, tla = enc(X_tr[:,ci]); elo, ela = enc(X_te[:,ci])
        etr.extend([tlo,tla]); ete.extend([elo,ela])
        tag = cn.replace('Physical cell identity','PCI').replace('Channel number','Ch').replace(' ','')
        en.extend([f'{tag}_clon', f'{tag}_clat'])
    X_tr = np.column_stack([X_tr]+[e.reshape(-1,1) for e in etr])
    X_te = np.column_stack([X_te]+[e.reshape(-1,1) for e in ete])
    return X_tr, X_te, list(feat)+en

def centroid_baseline(X, feat):
    cl = [i for i,n in enumerate(feat) if '_clon' in n]
    ca = [i for i,n in enumerate(feat) if '_clat' in n]
    if cl and ca:
        return np.column_stack([np.nanmean(X[:,cl],axis=1), np.nanmean(X[:,ca],axis=1)])
    return None

def clip_bbox(y_tr, pred, margin=0.005):
    p = pred.copy()
    p[:,0] = np.clip(p[:,0], y_tr[:,0].min()-margin, y_tr[:,0].max()+margin)
    p[:,1] = np.clip(p[:,1], y_tr[:,1].min()-margin, y_tr[:,1].max()+margin)
    return p

def gnss_noisy(y, rng, sigma):
    n = len(y)
    return np.column_stack([y[:,0]+rng.normal(0,sigma/M_PER_DEG,n),
                            y[:,1]+rng.normal(0,sigma/M_PER_DEG,n)])

def fuse_alpha(lte, gnss, yt):
    best_a, best_e = 0.0, float('inf')
    for a in np.linspace(0, 1, 101):
        e = np.mean(haversine_error(yt, a*lte+(1-a)*gnss))
        if e < best_e: best_e, best_a = e, a
    return round(best_a, 3), round(best_e, 1)

def run_city(city):
    cfg = CITY_CONFIG[city]
    base, sigma = cfg['base'], cfg['gnss_sigma']
    out_dir = os.path.join(base, 'results_pci')
    os.makedirs(out_dir, exist_ok=True)
    print(f'\n{"="*70}')
    print(f'  {city} — PCI+LTE+GNSS (sigma={sigma}m)')
    print(f'{"="*70}')
    bus_raw  = load_folder(os.path.join(base, cfg['bus']),  'bus')
    car_raw  = load_folder(os.path.join(base, cfg['car']),  'car')
    walk_raw = load_folder(os.path.join(base, cfg['walk']), 'walk')
    all_raw = pd.concat([bus_raw, car_raw, walk_raw], ignore_index=True)
    all_data, feat_cols = preprocess(all_raw)
    bus_d  = all_data[all_data['mode']=='bus'].copy()
    car_d  = all_data[all_data['mode']=='car'].copy()
    walk_d = all_data[all_data['mode']=='walk'].copy()
    print(f'  Bus={len(bus_d):,}  Car={len(car_d):,}  Walk={len(walk_d):,}  Total={len(all_data):,}')

    def train_mode(name, data):
        t0 = time.time()
        print(f'\n  --- {name} ({len(data):,} rows) ---')
        X, y, feat, pci = prepare_data(data, feat_cols)
        idx = np.arange(len(X))
        np.random.RandomState(42).shuffle(idx)
        n_tr = int(0.8*len(idx))
        itr, ite = idx[:n_tr], idx[n_tr:]
        Xtr, Xte, ytr, yte = X[itr], X[ite], y[itr], y[ite]
        pci_tr, pci_te = pci[itr], pci[ite]
        Xtr, Xte = impute(Xtr, Xte)
        Xtr, Xte, feat = add_pci_fp(Xtr, ytr, Xte, feat)

        B_tr = centroid_baseline(Xtr, feat)
        B_te = centroid_baseline(Xte, feat)
        if B_tr is None:
            c = np.median(ytr, axis=0)
            B_tr, B_te = np.tile(c,(len(Xtr),1)), np.tile(c,(len(Xte),1))
        et = ExtraTreesRegressor(n_estimators=500, max_features='sqrt',
                                 min_samples_leaf=2, n_jobs=-1, random_state=42)
        et.fit(Xtr, ytr - B_tr)
        g_tr = B_tr + et.predict(Xtr)
        g_te = B_te + et.predict(Xte)
        g_train_err = np.mean(haversine_error(ytr, g_tr))
        g_stats = stats_dict('Global_stack', yte, g_te)
        print(f'    Global ET: mean={g_stats["Mean_m"]}m')

        MIN_PCI = 80
        pred_te, pred_tr = g_te.copy(), g_tr.copy()
        used = 0
        n_pci = 0
        for pv in sorted(set(pci_tr[~np.isnan(pci_tr)])):
            mtr, mte = pci_tr==pv, pci_te==pv
            if mtr.sum() < MIN_PCI or mte.sum() == 0: continue
            Bp_tr = centroid_baseline(Xtr[mtr], feat)
            Bp_te = centroid_baseline(Xte[mte], feat)
            if Bp_tr is None:
                cc = np.median(ytr[mtr], axis=0)
                Bp_tr, Bp_te = np.tile(cc,(mtr.sum(),1)), np.tile(cc,(mte.sum(),1))
            m = ExtraTreesRegressor(n_estimators=300, max_features='sqrt',
                                    min_samples_leaf=2, n_jobs=-1, random_state=42)
            m.fit(Xtr[mtr], ytr[mtr]-Bp_tr)
            pred_te[mte] = Bp_te + m.predict(Xte[mte])
            pred_tr[mtr] = Bp_tr + m.predict(Xtr[mtr])
            used += mte.sum(); n_pci += 1

        print(f'    PCI models: {n_pci} (routed {used}/{len(yte)} test pts)')

        best_w, best_e = 0.0, float('inf')
        for w in np.linspace(0,1,101):
            f = w*pred_tr + (1-w)*g_tr
            e = np.mean(haversine_error(ytr, f))
            if e < best_e: best_e, best_w = e, w
        pred_final = best_w*pred_te + (1-best_w)*g_te
        pred_final = clip_bbox(ytr, pred_final)
        per_s = stats_dict('PerPCI+stack+clip', yte, pred_final)
        print(f'    PerPCI blend={best_w:.2f}: mean={per_s["Mean_m"]}m')

        gnss_tr = gnss_noisy(ytr, np.random.RandomState(43), sigma)
        gnss_te = gnss_noisy(yte, np.random.RandomState(44), sigma)
        alpha, fuse_err = fuse_alpha(pred_tr, gnss_tr, ytr)
        fused = clip_bbox(ytr, alpha*pred_final + (1-alpha)*gnss_te)
        fuse_s = stats_dict('PerPCI+LTE+GNSS', yte, fused)
        gnss_s = stats_dict('GNSS_noisy_only', yte, gnss_te)
        print(f'    Fused (alpha={alpha}): mean={fuse_s["Mean_m"]}m  median={fuse_s["Median_m"]}m')
        print(f'    Time: {time.time()-t0:.1f}s')
        return {'mode': name, 'all_stats': [per_s, g_stats, gnss_s, fuse_s],
                'best_stats': fuse_s, 'y_test': yte, 'best_pred': fused,
                'feat_names': feat, 'et_model': et,
                'et_stats': g_stats, 'et_train': round(g_train_err,1),
                'ens_stats': fuse_s, 'ens_train': round(fuse_err,1)}

    def train_combined(data):
        t0 = time.time()
        print(f'\n  --- Combined ({len(data):,} rows) ---')
        X, y, feat, _ = prepare_data(data, feat_cols)
        idx = np.arange(len(X))
        np.random.RandomState(42).shuffle(idx)
        n_tr = int(0.8*len(idx))
        itr, ite = idx[:n_tr], idx[n_tr:]
        Xtr, Xte, ytr, yte = X[itr], X[ite], y[itr], y[ite]
        Xtr, Xte = impute(Xtr, Xte)
        Xtr, Xte, feat = add_pci_fp(Xtr, ytr, Xte, feat)

        B_tr = centroid_baseline(Xtr, feat)
        B_te = centroid_baseline(Xte, feat)
        if B_tr is None:
            c = np.median(ytr, axis=0)
            B_tr, B_te = np.tile(c,(len(Xtr),1)), np.tile(c,(len(Xte),1))
        et = ExtraTreesRegressor(n_estimators=500, max_features='sqrt',
                                 min_samples_leaf=2, n_jobs=-1, random_state=42)
        et.fit(Xtr, ytr - B_tr)
        g_tr = B_tr + et.predict(Xtr)
        g_te = B_te + et.predict(Xte)
        g_train_err = np.mean(haversine_error(ytr, g_tr))
        et_s = stats_dict('ET_res+centroid', yte, g_te)
        lte_s = stats_dict('LTE_stack_only', yte, g_te)
        print(f'    Combined ET: mean={lte_s["Mean_m"]}m')

        gnss_tr = gnss_noisy(ytr, np.random.RandomState(43), sigma)
        gnss_te = gnss_noisy(yte, np.random.RandomState(44), sigma)
        alpha, fuse_err = fuse_alpha(g_tr, gnss_tr, ytr)
        fused = clip_bbox(ytr, alpha*g_te + (1-alpha)*gnss_te)
        fuse_s = stats_dict('LTE+GNSS_fused', yte, fused)
        gnss_s = stats_dict('GNSS_noisy_only', yte, gnss_te)
        print(f'    Fused (alpha={alpha}): mean={fuse_s["Mean_m"]}m  median={fuse_s["Median_m"]}m')
        print(f'    Time: {time.time()-t0:.1f}s')
        return {'mode': 'Combined', 'all_stats': [et_s, lte_s, gnss_s, fuse_s],
                'best_stats': fuse_s, 'y_test': yte, 'best_pred': fused,
                'feat_names': feat, 'et_model': et,
                'et_stats': lte_s, 'et_train': round(g_train_err,1),
                'ens_stats': fuse_s, 'ens_train': round(fuse_err,1)}

    results = []
    for nm, d in [('Bus',bus_d),('Car',car_d),('Walk',walk_d)]:
        results.append(train_mode(nm, d))
    results.append(train_combined(all_data))

    rows = []
    for r in results:
        for s in r['all_stats']:
            rows.append({'Mode':r['mode'],'Model':s['Model'],
                         'R2 Lon':s['R2_Lon'],'R2 Lat':s['R2_Lat'],
                         'Mean(m)':s['Mean_m'],'Median(m)':s['Median_m'],
                         '90th%(m)':s['P90_m'],'95th%(m)':s['P95_m']})
    sdf = pd.DataFrame(rows)
    csv_path = os.path.join(out_dir, 'model_comparison.csv')
    sdf.to_csv(csv_path, index=False)
    print(f'\n  Saved → {csv_path}')
    print(sdf.to_string(index=False))

    fused = sdf[sdf['Model'].isin(['PerPCI+LTE+GNSS','LTE+GNSS_fused'])]
    print(f'\n  === FUSED ({city}) ===')
    for _, r in fused.iterrows():
        ok = '✓' if r['Mean(m)'] < 35 else '✗'
        print(f'    {ok} {r["Mode"]:10s} mean={r["Mean(m)"]:6.1f}m  med={r["Median(m)"]:6.1f}m')
    return sdf

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'ALL'
    t0 = time.time()
    if target == 'ALL':
        for c in ['KAUST','Jeddah','Mekkah']:
            run_city(c)
    else:
        run_city(target)
    print(f'\nTotal: {time.time()-t0:.0f}s')
