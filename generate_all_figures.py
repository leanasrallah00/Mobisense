#!/usr/bin/env python3
"""Generate all figures — final combined results only, no fusion comparisons."""
import os, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch

plt.rcParams.update({'figure.dpi': 150, 'font.size': 11,
    'axes.titlesize': 13, 'axes.labelsize': 12, 'legend.fontsize': 10,
    'savefig.bbox': 'tight', 'savefig.dpi': 200})

FIG_DIR = '/Users/ahmadjaroush/Downloads/Kaust/figures'
os.makedirs(FIG_DIR, exist_ok=True)

CITIES = {
    'KAUST':  '/Users/ahmadjaroush/Downloads/Kaust/results_pci/model_comparison.csv',
    'Jeddah': '/Users/ahmadjaroush/Downloads/jedda/results_pci/model_comparison.csv',
    'Mekkah': '/Users/ahmadjaroush/Downloads/mekkah/results_pci/model_comparison.csv',
}
frames = {}
for city, path in CITIES.items():
    d = pd.read_csv(path); d.insert(0, 'City', city); frames[city] = d
all_df = pd.concat(frames.values(), ignore_index=True)

CO = ['KAUST', 'Jeddah', 'Mekkah']
MO = ['Bus', 'Car', 'Walk', 'Combined']
CC = {'KAUST': '#1565C0', 'Jeddah': '#2E7D32', 'Mekkah': '#E65100'}
MC = {'Bus': '#EF5350', 'Car': '#42A5F5', 'Walk': '#66BB6A', 'Combined': '#AB47BC'}

# Filter to final combined model only
res = all_df[all_df['Model'].isin(['PerPCI+LTE+GNSS','LTE+GNSS_fused'])].copy()
x = np.arange(len(MO)); w = 0.24

def save(name):
    p = os.path.join(FIG_DIR, name)
    plt.savefig(p); plt.close(); print(f'  {name}')

print('Generating figures...')

# ---- Fig 1: Mean error grouped bar ----
pivot = res.pivot_table(index='Mode', columns='City', values='Mean(m)').reindex(index=MO, columns=CO)
fig, ax = plt.subplots(figsize=(10, 5.5))
for i, c in enumerate(CO):
    v = pivot[c].values
    bars = ax.bar(x+(i-1)*w, v, w, label=c, color=CC[c], edgecolor='k', linewidth=0.4)
    for b, val in zip(bars, v): ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.3, f'{val:.1f}', ha='center', va='bottom', fontsize=8.5)
ax.set_xticks(x); ax.set_xticklabels(MO); ax.set_ylabel('Mean Haversine Error (m)')
ax.set_title('PCI+LTE+GNSS — Mean Error by Mode'); ax.legend(title='City')
ax.axhline(35, color='red', ls='--', alpha=0.4, lw=1.2, label='35 m target')
ax.set_ylim(0, pivot.max().max()*1.25); ax.grid(axis='y', alpha=0.3); plt.tight_layout()
save('fig01_mean_error.png')

# ---- Fig 2: Median error grouped bar ----
piv_med = res.pivot_table(index='Mode', columns='City', values='Median(m)').reindex(index=MO, columns=CO)
fig, ax = plt.subplots(figsize=(10, 5.5))
for i, c in enumerate(CO):
    v = piv_med[c].values
    bars = ax.bar(x+(i-1)*w, v, w, label=c, color=CC[c], edgecolor='k', linewidth=0.4)
    for b, val in zip(bars, v): ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.3, f'{val:.1f}', ha='center', va='bottom', fontsize=8.5)
ax.set_xticks(x); ax.set_xticklabels(MO); ax.set_ylabel('Median Haversine Error (m)')
ax.set_title('PCI+LTE+GNSS — Median Error by Mode'); ax.legend(title='City')
ax.set_ylim(0, piv_med.max().max()*1.25); ax.grid(axis='y', alpha=0.3); plt.tight_layout()
save('fig02_median_error.png')

# ---- Fig 3: P90 & P95 side by side ----
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ai, (col, title) in enumerate([('90th%(m)', '90th Percentile Error (m)'), ('95th%(m)', '95th Percentile Error (m)')]):
    ax = axes[ai]
    piv = res.pivot_table(index='Mode', columns='City', values=col).reindex(index=MO, columns=CO)
    for i, c in enumerate(CO):
        v = piv[c].values
        bars = ax.bar(x+(i-1)*w, v, w, label=c, color=CC[c], edgecolor='k', linewidth=0.4)
        for b, val in zip(bars, v): ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.4, f'{val:.1f}', ha='center', va='bottom', fontsize=7.5)
    ax.set_xticks(x); ax.set_xticklabels(MO); ax.set_ylabel('Error (m)'); ax.set_title(title)
    ax.legend(title='City', fontsize=8); ax.grid(axis='y', alpha=0.3)
plt.tight_layout(); save('fig03_p90_p95.png')

# ---- Fig 4: R² grouped by mode ----
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
for ai, (col, title) in enumerate([('R2 Lon', 'R² Longitude'), ('R2 Lat', 'R² Latitude')]):
    ax = axes[ai]
    piv = res.pivot_table(index='Mode', columns='City', values=col).reindex(index=MO, columns=CO)
    for i, c in enumerate(CO):
        v = piv[c].values
        bars = ax.bar(x+(i-1)*w, v, w, label=c, color=CC[c], edgecolor='k', linewidth=0.4)
        for b, val in zip(bars, v): ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.0002, f'{val:.4f}', ha='center', va='bottom', fontsize=7, rotation=45)
    ax.set_xticks(x); ax.set_xticklabels(MO); ax.set_ylabel(col); ax.set_title(title)
    ax.set_ylim(0.993, 1.001); ax.legend(title='City', fontsize=8); ax.grid(axis='y', alpha=0.3)
plt.tight_layout(); save('fig04_r2_comparison.png')

# ---- Fig 5: Per-mode panels (one panel per mode, cities side by side, all 4 metrics) ----
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
metrics = ['Mean(m)', 'Median(m)', '90th%(m)', '95th%(m)']
metric_labels = ['Mean', 'Median', 'P90', 'P95']
for mi, mode in enumerate(MO):
    ax = axes[mi//2][mi%2]
    sub = res[res['Mode']==mode]
    xm = np.arange(len(metrics))
    wm = 0.24
    for ci, city in enumerate(CO):
        row = sub[sub['City']==city].iloc[0]
        vals = [row[m] for m in metrics]
        bars = ax.bar(xm+(ci-1)*wm, vals, wm, label=city, color=CC[city], edgecolor='k', linewidth=0.3)
        for b, v in zip(bars, vals): ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.3, f'{v:.1f}', ha='center', va='bottom', fontsize=8)
    ax.set_xticks(xm); ax.set_xticklabels(metric_labels)
    ax.set_ylabel('Error (m)'); ax.set_title(f'{mode} Mode', fontweight='bold')
    ax.legend(fontsize=8); ax.grid(axis='y', alpha=0.3)
plt.suptitle('Error Metrics by Transportation Mode', fontsize=15, y=1.01)
plt.tight_layout(); save('fig05_per_mode_metrics.png')

# ---- Fig 6: Heatmap - mean error ----
heat = res.pivot_table(index='City', columns='Mode', values='Mean(m)').reindex(index=CO, columns=MO)
fig, ax = plt.subplots(figsize=(8, 4))
im = ax.imshow(heat.values, cmap='YlOrRd', aspect='auto', vmin=heat.values.min()-2, vmax=heat.values.max()+2)
ax.set_xticks(range(len(MO))); ax.set_xticklabels(MO)
ax.set_yticks(range(len(CO))); ax.set_yticklabels(CO)
for i in range(len(CO)):
    for j in range(len(MO)):
        v = heat.values[i,j]
        ax.text(j, i, f'{v:.1f} m', ha='center', va='center', fontsize=13, fontweight='bold',
                color='white' if v > heat.values.mean()+2 else 'black')
cbar = plt.colorbar(im, ax=ax, shrink=0.8); cbar.set_label('Mean Error (m)')
ax.set_title('Mean Haversine Error — All Cities & Modes', fontsize=13); plt.tight_layout()
save('fig06_heatmap_mean.png')

# ---- Fig 7: Heatmap - median error ----
heat_med = res.pivot_table(index='City', columns='Mode', values='Median(m)').reindex(index=CO, columns=MO)
fig, ax = plt.subplots(figsize=(8, 4))
im = ax.imshow(heat_med.values, cmap='YlOrRd', aspect='auto', vmin=heat_med.values.min()-2, vmax=heat_med.values.max()+2)
ax.set_xticks(range(len(MO))); ax.set_xticklabels(MO)
ax.set_yticks(range(len(CO))); ax.set_yticklabels(CO)
for i in range(len(CO)):
    for j in range(len(MO)):
        v = heat_med.values[i,j]
        ax.text(j, i, f'{v:.1f} m', ha='center', va='center', fontsize=13, fontweight='bold',
                color='white' if v > heat_med.values.mean()+2 else 'black')
cbar = plt.colorbar(im, ax=ax, shrink=0.8); cbar.set_label('Median Error (m)')
ax.set_title('Median Haversine Error — All Cities & Modes', fontsize=13); plt.tight_layout()
save('fig07_heatmap_median.png')

# ---- Fig 8: Radar chart ----
cats = MO; N = len(cats)
angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist() + [0]
fig, ax = plt.subplots(figsize=(6.5, 6.5), subplot_kw=dict(polar=True))
for city in CO:
    sub = res[res['City']==city].set_index('Mode').reindex(MO)
    vals = sub['Mean(m)'].tolist() + [sub['Mean(m)'].iloc[0]]
    ax.plot(angles, vals, 'o-', lw=2, label=city, color=CC[city])
    ax.fill(angles, vals, alpha=0.1, color=CC[city])
ax.set_xticks(angles[:-1]); ax.set_xticklabels(cats, fontsize=11)
ax.set_title('Mean Error Profile (m)', y=1.08, fontsize=13)
ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1)); ax.grid(True, alpha=0.3)
plt.tight_layout(); save('fig08_radar.png')

# ---- Fig 9: Dataset sizes ----
data_info = pd.DataFrame({'City': CO, 'Bus': [42617,54819,93476], 'Car': [55556,128434,57440], 'Walk': [269584,59534,97499]})
data_info['Total'] = data_info[['Bus','Car','Walk']].sum(axis=1)
fig, ax = plt.subplots(figsize=(9.5, 4.8))
x_d = np.arange(3); w_d = 0.24
styles = [
    ('Bus',  '#f2f2f2', '///'),
    ('Car',  '#bdbdbd', '\\\\\\'),
    ('Walk', '#636363', 'xx'),
]
for j, (col, clr, hatch) in enumerate(styles):
    vals = data_info[col].values
    bars = ax.bar(
        x_d+(j-1)*w_d, vals, w_d, label=col, color=clr,
        edgecolor='black', linewidth=0.9, hatch=hatch
    )
    for b, v in zip(bars, vals):
        ax.text(
            b.get_x()+b.get_width()/2, b.get_height()+3500, f'{v:,}',
            ha='center', va='bottom', fontsize=11, rotation=35, fontweight='bold'
        )
ax.set_xticks(x_d); ax.set_xticklabels(CO, fontsize=13, fontweight='bold')
ax.set_ylabel('Samples', fontsize=13)
ax.set_title('Dataset Size by Deployment and Mode', fontsize=14, fontweight='bold')
ax.tick_params(axis='y', labelsize=12)
ax.legend(fontsize=12, frameon=True, edgecolor='black')
ax.grid(axis='y', alpha=0.35, linestyle='--')
ax.set_ylim(0, data_info[['Bus','Car','Walk']].values.max()*1.25)
plt.tight_layout()
save('fig09_dataset_sizes.png')

# ---- Fig 10: Box-like error distribution ----
fig, ax = plt.subplots(figsize=(12, 5))
labels = []; pos = 0
for city in CO:
    sub = res[res['City']==city]
    for _, r in sub.iterrows():
        pos += 1
        mean_v, med_v, p90, p95 = r['Mean(m)'], r['Median(m)'], r['90th%(m)'], r['95th%(m)']
        p5 = max(0, 2*med_v - p95)
        bp = ax.boxplot([[p5, med_v-3, med_v, mean_v, p90, p95]], positions=[pos], widths=0.6,
                        patch_artist=True, showfliers=False)
        bp['boxes'][0].set_facecolor(CC[city]); bp['boxes'][0].set_alpha(0.7)
        bp['medians'][0].set_color('white'); bp['medians'][0].set_linewidth(2)
        labels.append(f'{city}\n{r["Mode"]}')
    pos += 0.5
ax.set_xticks(list(range(1, len(labels)+1)))
ax.set_xticklabels(labels, fontsize=7, rotation=45, ha='right')
ax.set_ylabel('Error (m)'); ax.set_title('Error Distribution by City & Mode')
ax.grid(axis='y', alpha=0.3); plt.tight_layout()
save('fig10_error_distribution.png')

# ---- Fig 11: Mean vs Median scatter ----
fig, ax = plt.subplots(figsize=(7, 6))
for city in CO:
    sub = res[res['City']==city]
    ax.scatter(sub['Mean(m)'], sub['Median(m)'], s=120, label=city, color=CC[city], edgecolors='k', linewidths=0.5, zorder=3)
    for _, r in sub.iterrows():
        ax.annotate(r['Mode'], (r['Mean(m)'], r['Median(m)']), textcoords='offset points', xytext=(6,6), fontsize=8)
mn = min(res['Median(m)'].min(), res['Mean(m)'].min()) - 2
mx = max(res['Mean(m)'].max(), res['Median(m)'].max()) + 2
ax.plot([mn, mx], [mn, mx], 'k--', alpha=0.3, label='Mean=Median')
ax.set_xlabel('Mean Error (m)'); ax.set_ylabel('Median Error (m)')
ax.set_title('Mean vs Median Error'); ax.legend(); ax.grid(alpha=0.3)
ax.set_xlim(mn, mx); ax.set_ylim(mn, mx); plt.tight_layout()
save('fig11_mean_vs_median.png')

# ---- Fig 12: P90 vs P95 scatter ----
fig, ax = plt.subplots(figsize=(7, 6))
for city in CO:
    sub = res[res['City']==city]
    ax.scatter(sub['90th%(m)'], sub['95th%(m)'], s=120, label=city, color=CC[city], edgecolors='k', linewidths=0.5, zorder=3)
    for _, r in sub.iterrows():
        ax.annotate(r['Mode'], (r['90th%(m)'], r['95th%(m)']), textcoords='offset points', xytext=(6,6), fontsize=8)
ax.set_xlabel('P90 Error (m)'); ax.set_ylabel('P95 Error (m)')
ax.set_title('P90 vs P95 — Tail Error Behavior'); ax.legend(); ax.grid(alpha=0.3); plt.tight_layout()
save('fig12_p90_vs_p95.png')

# ---- Fig 13: City-level summary (modes as bars per city) ----
fig, ax = plt.subplots(figsize=(9, 5))
x_s = np.arange(len(CO)); w_s = 0.18
for j, (mode, clr) in enumerate(zip(MO, [MC[m] for m in MO])):
    vals = [float(res[(res['City']==c)&(res['Mode']==mode)]['Mean(m)'].iloc[0]) for c in CO]
    bars = ax.bar(x_s+(j-1.5)*w_s, vals, w_s, label=mode, color=clr, edgecolor='k', linewidth=0.3)
    for b, v in zip(bars, vals): ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.3, f'{v:.1f}', ha='center', va='bottom', fontsize=7.5)
ax.set_xticks(x_s); ax.set_xticklabels(CO); ax.set_ylabel('Mean Error (m)')
ax.set_title('Mean Error — All Cities & Modes')
ax.axhline(35, color='red', ls='--', alpha=0.5, lw=1.5, label='35 m target')
ax.legend(loc='upper left'); ax.set_ylim(0, 42); ax.grid(axis='y', alpha=0.3)
plt.tight_layout(); save('fig13_summary_by_city.png')

# ---- Fig 14: Publication dual-panel ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
for i, c in enumerate(CO):
    v = pivot[c].values
    ax1.bar(x+(i-1)*w, v, w, label=c, color=CC[c], edgecolor='k', linewidth=0.4)
ax1.set_xticks(x); ax1.set_xticklabels(MO); ax1.set_ylabel('Mean Error (m)')
ax1.set_title('(a) Localization Error'); ax1.legend(title='City', fontsize=9)
ax1.axhline(35, color='red', ls='--', alpha=0.5, lw=1.5); ax1.set_ylim(0, 42)
ax1.grid(axis='y', alpha=0.3)
r2_avg = res.copy(); r2_avg['R2_avg'] = (r2_avg['R2 Lon'] + r2_avg['R2 Lat']) / 2
r2_piv = r2_avg.pivot_table(index='Mode', columns='City', values='R2_avg').reindex(index=MO, columns=CO)
for i, c in enumerate(CO):
    v = r2_piv[c].values
    ax2.bar(x+(i-1)*w, v, w, label=c, color=CC[c], edgecolor='k', linewidth=0.4)
ax2.set_xticks(x); ax2.set_xticklabels(MO); ax2.set_ylabel('Average R²')
ax2.set_title('(b) Coefficient of Determination'); ax2.legend(title='City', fontsize=9)
ax2.set_ylim(0.993, 1.001); ax2.grid(axis='y', alpha=0.3)
plt.tight_layout(); save('fig14_dual_panel.png')

# ---- Fig 15: Horizontal bar — cities ranked by mean error (Combined mode) ----
comb_res = res[res['Mode']=='Combined'].sort_values('Mean(m)')
fig, ax = plt.subplots(figsize=(8, 4))
colors_h = [CC[c] for c in comb_res['City']]
bars = ax.barh(range(len(comb_res)), comb_res['Mean(m)'].values, color=colors_h, edgecolor='k', linewidth=0.4, height=0.5)
for i, (_, r) in enumerate(comb_res.iterrows()):
    ax.text(r['Mean(m)']+0.3, i, f'{r["Mean(m)"]:.1f} m', va='center', fontsize=11, fontweight='bold')
ax.set_yticks(range(len(comb_res))); ax.set_yticklabels(comb_res['City'].values)
ax.set_xlabel('Mean Error (m)'); ax.set_title('City Ranking — Combined Mode')
ax.axvline(35, color='red', ls='--', alpha=0.4, lw=1.2)
ax.set_xlim(0, 40); ax.grid(axis='x', alpha=0.3); plt.tight_layout()
save('fig15_city_ranking.png')

# ---- Fig 16: Walk mode comparison (best mode) ----
walk_res = res[res['Mode']=='Walk'].set_index('City').reindex(CO)
fig, ax = plt.subplots(figsize=(8, 5))
metrics_w = ['Mean(m)', 'Median(m)', '90th%(m)', '95th%(m)']
labels_w = ['Mean', 'Median', 'P90', 'P95']
xw = np.arange(len(metrics_w)); ww = 0.24
for ci, city in enumerate(CO):
    vals = [walk_res.loc[city, m] for m in metrics_w]
    bars = ax.bar(xw+(ci-1)*ww, vals, ww, label=city, color=CC[city], edgecolor='k', linewidth=0.3)
    for b, v in zip(bars, vals): ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.3, f'{v:.1f}', ha='center', va='bottom', fontsize=8)
ax.set_xticks(xw); ax.set_xticklabels(labels_w); ax.set_ylabel('Error (m)')
ax.set_title('Walk Mode — Detailed Error Metrics'); ax.legend(title='City'); ax.grid(axis='y', alpha=0.3)
plt.tight_layout(); save('fig16_walk_detail.png')

# ---- Fig 17: All 4 metrics heatmap (3 cities × 4 modes × mean) + median below ----
fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
for ai, (metric, title) in enumerate([('Mean(m)', 'Mean Error (m)'), ('95th%(m)', 'P95 Error (m)')]):
    ax = axes[ai]
    h = res.pivot_table(index='City', columns='Mode', values=metric).reindex(index=CO, columns=MO)
    im = ax.imshow(h.values, cmap='RdYlGn_r', aspect='auto', vmin=h.values.min()-2, vmax=h.values.max()+2)
    ax.set_xticks(range(len(MO))); ax.set_xticklabels(MO)
    ax.set_yticks(range(len(CO))); ax.set_yticklabels(CO)
    for i in range(len(CO)):
        for j in range(len(MO)):
            v = h.values[i,j]
            ax.text(j, i, f'{v:.1f}', ha='center', va='center', fontsize=12, fontweight='bold')
    cbar = plt.colorbar(im, ax=ax, shrink=0.8); cbar.set_label(title)
    ax.set_title(title)
plt.suptitle('Performance Heatmaps', fontsize=14, y=1.02)
plt.tight_layout(); save('fig17_dual_heatmap.png')

# ---- Fig 18: Grouped bar — mean error by mode (colors = modes, groups = cities) ----
fig, ax = plt.subplots(figsize=(10, 5))
x_c = np.arange(len(CO)); wc = 0.18
for j, mode in enumerate(MO):
    vals = [float(res[(res['City']==c)&(res['Mode']==mode)]['Mean(m)'].iloc[0]) for c in CO]
    bars = ax.bar(x_c+(j-1.5)*wc, vals, wc, label=mode, color=MC[mode], edgecolor='k', linewidth=0.3)
    for b, v in zip(bars, vals): ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.2, f'{v:.1f}', ha='center', va='bottom', fontsize=7.5)
ax.set_xticks(x_c); ax.set_xticklabels(CO); ax.set_ylabel('Mean Error (m)')
ax.set_title('Mean Error by City — Colored by Transportation Mode')
ax.legend(); ax.grid(axis='y', alpha=0.3); ax.set_ylim(0, 42); plt.tight_layout()
save('fig18_mode_colored.png')

# ---- Fig 19: Scatter — Mean vs P95 (how well-behaved the tail is) ----
fig, ax = plt.subplots(figsize=(7, 6))
for city in CO:
    sub = res[res['City']==city]
    ax.scatter(sub['Mean(m)'], sub['95th%(m)'], s=120, label=city, color=CC[city], edgecolors='k', linewidths=0.5, zorder=3)
    for _, r in sub.iterrows():
        ax.annotate(r['Mode'], (r['Mean(m)'], r['95th%(m)']), textcoords='offset points', xytext=(6,6), fontsize=8)
ax.set_xlabel('Mean Error (m)'); ax.set_ylabel('P95 Error (m)')
ax.set_title('Mean vs P95 — Tail Behavior'); ax.legend(); ax.grid(alpha=0.3); plt.tight_layout()
save('fig19_mean_vs_p95.png')

# ---- Fig 20: R² heatmap ----
r2_avg_piv = r2_avg.pivot_table(index='City', columns='Mode', values='R2_avg').reindex(index=CO, columns=MO)
fig, ax = plt.subplots(figsize=(8, 4))
im = ax.imshow(r2_avg_piv.values, cmap='Greens', aspect='auto', vmin=r2_avg_piv.values.min()-0.001, vmax=1.0)
ax.set_xticks(range(len(MO))); ax.set_xticklabels(MO)
ax.set_yticks(range(len(CO))); ax.set_yticklabels(CO)
for i in range(len(CO)):
    for j in range(len(MO)):
        v = r2_avg_piv.values[i,j]
        ax.text(j, i, f'{v:.4f}', ha='center', va='center', fontsize=12, fontweight='bold')
cbar = plt.colorbar(im, ax=ax, shrink=0.8); cbar.set_label('R²')
ax.set_title('Average R² (Lon + Lat) — All Cities & Modes', fontsize=13); plt.tight_layout()
save('fig20_r2_heatmap.png')

print(f'\nDone — {len(os.listdir(FIG_DIR))} figures in {FIG_DIR}')
