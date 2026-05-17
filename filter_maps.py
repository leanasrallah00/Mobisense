#!/usr/bin/env python3
"""Filter Folium HTML maps to only include prediction points with error < 100m."""
import re, os

THRESHOLD = 100

MAP_FILES = []
for mode in ['walk', 'bus', 'car', 'combined']:
    p = f'/Users/ahmadjaroush/Downloads/Kaust/results/map_{mode}_localization.html'
    if os.path.exists(p):
        MAP_FILES.append(p)
for mode in ['walk', 'bus', 'car', 'combined']:
    p = f'/Users/ahmadjaroush/Downloads/jedda/results_pci/map_{mode}.html'
    if os.path.exists(p):
        MAP_FILES.append(p)
for mode in ['walk', 'bus', 'car', 'combined']:
    p = f'/Users/ahmadjaroush/Downloads/mekkah/results_pci/map_{mode}.html'
    if os.path.exists(p):
        MAP_FILES.append(p)

print(f"Found {len(MAP_FILES)} map files to process")

for fpath in MAP_FILES:
    with open(fpath, 'r') as f:
        html = f.read()

    fg_pattern = re.compile(r'var (feature_group_[a-f0-9]+) = L\.featureGroup')
    fgs = [(m.group(1), m.start()) for m in fg_pattern.finditer(html)]

    if len(fgs) < 2:
        print(f"SKIP (< 2 feature groups): {fpath}")
        continue

    fg_actual_name = fgs[0][0]
    fg_pred_name = fgs[1][0]

    blue_marker_re = re.compile(
        r'(\s*var (circle_marker_[a-f0-9]+) = L\.circleMarker\(\s*'
        r'\[([^\]]+)\],\s*'
        r'\{[^}]*"color":\s*"blue"[^}]*\}\s*'
        r'\)\.addTo\(' + re.escape(fg_actual_name) + r'\);\s*)',
        re.DOTALL
    )
    blue_markers = list(blue_marker_re.finditer(html))

    pred_marker_re = re.compile(
        r'(\s*var (circle_marker_[a-f0-9]+) = L\.circleMarker\(\s*'
        r'\[([^\]]+)\],\s*'
        r'\{[^}]*"color":\s*"(?:green|orange|red)"[^}]*\}\s*'
        r'\)\.addTo\(' + re.escape(fg_pred_name) + r'\);)',
        re.DOTALL
    )
    pred_markers = list(pred_marker_re.finditer(html))

    popup_re = re.compile(r'>(\d+)m</div>')

    remove_ranges = []
    blue_to_remove = []
    kept = 0
    removed = 0

    for i, pm in enumerate(pred_markers):
        search_start = pm.end()
        search_end = min(search_start + 2000, len(html))
        chunk = html[search_start:search_end]

        err_match = popup_re.search(chunk)
        if err_match is None:
            continue

        error_m = int(err_match.group(1))

        if error_m >= THRESHOLD:
            poly_re = re.compile(
                r'var poly_line_[a-f0-9]+ = L\.polyline\(\s*'
                r'\[\[[^\]]+\],\s*\[[^\]]+\]\],\s*'
                r'\{[^}]*\}\s*'
                r'\)\.addTo\(' + re.escape(fg_pred_name) + r'\);\s*',
                re.DOTALL
            )
            poly_match = poly_re.search(html, search_start)
            if poly_match:
                block_start = pm.start()
                block_end = poly_match.end()
                remove_ranges.append((block_start, block_end))

                if i < len(blue_markers):
                    bm = blue_markers[i]
                    blue_to_remove.append((bm.start(), bm.end()))

            removed += 1
        else:
            kept += 1

    all_removals = sorted(remove_ranges + blue_to_remove, key=lambda x: x[0], reverse=True)

    new_html = html
    for start, end in all_removals:
        new_html = new_html[:start] + new_html[end:]

    with open(fpath, 'w') as f:
        f.write(new_html)

    total = kept + removed
    print(f"OK: {os.path.basename(fpath)} — kept {kept}/{total} points (removed {removed} >= {THRESHOLD}m)")

print("Done.")
