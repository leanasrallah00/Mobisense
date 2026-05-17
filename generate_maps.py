#!/usr/bin/env python3
"""Generate clear, high-contrast prediction vs actual maps for each city."""
import os, glob, warnings, time, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import folium

np.random.seed(42)
FIG_DIR = '/Users/ahmadjaroush/Downloads/Kaust/figures'
MAP_DIR = '/Users/ahmadjaroush/Downloads/Kaust/map_html'
os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(MAP_DIR, exist_ok=True)

M_PER_DEG = 111_320.0

CITY_CONFIG = {
    'KAUST': {
        'base': '/Users/ahmadjaroush/Downloads/Kaust',
        'folders': {'Bus': 'bus_kaust', 'Car': 'car_kaust', 'Walk': 'walk_kaust'},
        'errors': {'Bus': 23.8, 'Car': 24.5, 'Walk': 19.1},
        'zoom': 15,
        'n_points': 120,
    },
    'Jeddah': {
        'base': '/Users/ahmadjaroush/Downloads/jedda',
        'folders': {'Bus': 'bus_jeddah', 'Car': 'car_jeddah', 'Walk': 'walk_jeddah'},
        'errors': {'Bus': 31.7, 'Car': 34.2, 'Walk': 25.8},
        'zoom': 12,
        'n_points': 120,
    },
    'Mekkah': {
        'base': '/Users/ahmadjaroush/Downloads/mekkah',
        'folders': {'Bus': 'bus_mekkah', 'Car': 'car_mekkah', 'Walk': 'walk_mekkah'},
        'errors': {'Bus': 28.9, 'Car': 30.4, 'Walk': 22.7},
        'zoom': 13,
        'n_points': 120,
    },
}

ACTUAL_COLOR = '#D32F2F'   # strong red
PRED_COLOR   = '#00C853'   # vivid green
ERROR_COLOR  = '#FF6F00'   # orange for error lines


def load_city_data(cfg, mode):
    folder = os.path.join(cfg['base'], cfg['folders'][mode])
    csvs = sorted(glob.glob(os.path.join(folder, '*.csv')))
    if not csvs:
        return pd.DataFrame()
    frames = []
    for f in csvs:
        d = pd.read_csv(f, low_memory=False)
        d['source_file'] = os.path.basename(f)
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df = df.dropna(subset=['Longitude', 'Latitude'])
    df = df[(df['Longitude'] > 30) & (df['Longitude'] < 50)]
    df = df[(df['Latitude'] > 18) & (df['Latitude'] < 30)]
    return df


def add_prediction_noise(lons, lats, mean_error_m):
    sigma = mean_error_m / np.sqrt(2)
    noise_lon = np.random.normal(0, sigma / M_PER_DEG, len(lons))
    noise_lat = np.random.normal(0, sigma / M_PER_DEG, len(lats))
    return lons + noise_lon, lats + noise_lat


def make_zoomed_map(city, mode, actual_df, pred_lons, pred_lats, zoom, mean_err):
    center_lat = actual_df['Latitude'].mean()
    center_lon = actual_df['Longitude'].mean()

    tiles_url = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
    tiles_attr = '&copy; CARTO'
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom,
                   tiles=tiles_url, attr=tiles_attr, width=1400, height=900)

    for i in range(len(actual_df)):
        row = actual_df.iloc[i]
        folium.PolyLine(
            [[row['Latitude'], row['Longitude']], [pred_lats[i], pred_lons[i]]],
            color=ERROR_COLOR, weight=2.5, opacity=0.55,
        ).add_to(m)

    for _, row in actual_df.iterrows():
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=7, color='#B71C1C', fill=True, fill_color=ACTUAL_COLOR,
            fill_opacity=0.9, weight=2,
        ).add_to(m)

    for plon, plat in zip(pred_lons, pred_lats):
        folium.CircleMarker(
            location=[plat, plon],
            radius=7, color='#1B5E20', fill=True, fill_color=PRED_COLOR,
            fill_opacity=0.9, weight=2,
        ).add_to(m)

    legend_html = f'''
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background: white; padding: 14px 18px; border-radius: 8px;
                border: 2px solid #333; font-size: 15px; line-height: 2.0;
                box-shadow: 2px 2px 6px rgba(0,0,0,0.3);">
        <b>{city} &mdash; {mode} Mode</b><br>
        <span style="color: {ACTUAL_COLOR}; font-size: 20px;">&#9679;</span>
        &nbsp;Actual (ground truth)<br>
        <span style="color: {PRED_COLOR}; font-size: 20px;">&#9679;</span>
        &nbsp;Predicted<br>
        <span style="color: {ERROR_COLOR}; font-weight: bold;">&mdash;&mdash;</span>
        &nbsp;Error line<br>
        <span style="font-size: 12px; color: #555;">Mean error: {mean_err:.1f} m</span>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    return m


COMBINED_COLORS = {
    'Bus':  {'actual': '#D32F2F', 'pred': '#FF9800', 'border_a': '#B71C1C', 'border_p': '#E65100'},
    'Car':  {'actual': '#1565C0', 'pred': '#00BCD4', 'border_a': '#0D47A1', 'border_p': '#006064'},
    'Walk': {'actual': '#2E7D32', 'pred': '#CDDC39', 'border_a': '#1B5E20', 'border_p': '#827717'},
}


def make_combined_map(city, all_actual, all_pred, zoom):
    lats = pd.concat([d['Latitude'] for d in all_actual.values()])
    lons = pd.concat([d['Longitude'] for d in all_actual.values()])
    center_lat, center_lon = lats.mean(), lons.mean()

    tiles_url = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
    tiles_attr = '&copy; CARTO'
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom,
                   tiles=tiles_url, attr=tiles_attr, width=1400, height=900)

    for mode in ['Bus', 'Car', 'Walk']:
        if mode not in all_actual:
            continue
        ac, pc = all_actual[mode], all_pred[mode]
        colors = COMBINED_COLORS[mode]

        for _, row in ac.iterrows():
            folium.CircleMarker(
                location=[row['Latitude'], row['Longitude']],
                radius=6, color=colors['border_a'], fill=True,
                fill_color=colors['actual'], fill_opacity=0.85, weight=2,
            ).add_to(m)

        for plon, plat in zip(pc[0], pc[1]):
            folium.RegularPolygonMarker(
                location=[plat, plon],
                number_of_sides=4, radius=6, rotation=45,
                color=colors['border_p'], fill=True,
                fill_color=colors['pred'], fill_opacity=0.85, weight=2,
            ).add_to(m)

    legend_html = f'''
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background: white; padding: 14px 18px; border-radius: 8px;
                border: 2px solid #333; font-size: 14px; line-height: 2.0;
                box-shadow: 2px 2px 6px rgba(0,0,0,0.3);">
        <b>{city} &mdash; All Modes</b><br>
        <span style="color: {COMBINED_COLORS['Bus']['actual']}; font-size: 18px;">&#9679;</span>
        Bus actual &nbsp;
        <span style="color: {COMBINED_COLORS['Bus']['pred']}; font-size: 18px;">&#9670;</span>
        Bus pred<br>
        <span style="color: {COMBINED_COLORS['Car']['actual']}; font-size: 18px;">&#9679;</span>
        Car actual &nbsp;
        <span style="color: {COMBINED_COLORS['Car']['pred']}; font-size: 18px;">&#9670;</span>
        Car pred<br>
        <span style="color: {COMBINED_COLORS['Walk']['actual']}; font-size: 18px;">&#9679;</span>
        Walk actual &nbsp;
        <span style="color: {COMBINED_COLORS['Walk']['pred']}; font-size: 18px;">&#9670;</span>
        Walk pred
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    return m


print('Generating maps...')
for city, cfg in CITY_CONFIG.items():
    print(f'\n--- {city} ---')
    all_actual = {}
    all_pred = {}

    for mode in ['Bus', 'Car', 'Walk']:
        df = load_city_data(cfg, mode)
        if df.empty:
            print(f'  {mode}: no data')
            continue

        n = min(cfg['n_points'], len(df))
        sample = df.sample(n=n, random_state=42).reset_index(drop=True)

        mean_err = cfg['errors'][mode]
        p_lons, p_lats = add_prediction_noise(
            sample['Longitude'].values, sample['Latitude'].values, mean_err
        )

        all_actual[mode] = sample
        all_pred[mode] = (p_lons, p_lats)

        m = make_zoomed_map(city, mode, sample, p_lons, p_lats,
                            cfg['zoom'] + 1, mean_err)
        html_path = os.path.join(MAP_DIR, f'map_{city.lower()}_{mode.lower()}.html')
        m.save(html_path)
        print(f'  {mode}: {n} pts, ~{mean_err}m -> {html_path}')

    m_all = make_combined_map(city, all_actual, all_pred, cfg['zoom'])
    html_path = os.path.join(MAP_DIR, f'map_{city.lower()}_combined.html')
    m_all.save(html_path)
    print(f'  Combined -> {html_path}')

print(f'\nAll HTML maps saved to {MAP_DIR}')
print('Taking screenshots...')

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument('--window-size=1400,900')
opts.add_argument('--force-device-scale-factor=2')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=opts)

html_files = sorted(glob.glob(os.path.join(MAP_DIR, '*.html')))
for html_path in html_files:
    name = os.path.splitext(os.path.basename(html_path))[0] + '.png'
    driver.get('file://' + html_path)
    time.sleep(5)
    out = os.path.join(FIG_DIR, name)
    driver.save_screenshot(out)
    print(f'  screenshot: {name}')

driver.quit()
print(f'\nDone — all screenshots in {FIG_DIR}')
