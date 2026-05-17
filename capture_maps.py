#!/usr/bin/env python3
"""Capture screenshots from folium HTML maps using headless Chrome."""
import os, time, warnings
warnings.filterwarnings('ignore')

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

FIG_DIR = '/Users/ahmadjaroush/Downloads/Kaust/figures'
os.makedirs(FIG_DIR, exist_ok=True)

maps = [
    ('/Users/ahmadjaroush/Downloads/Kaust/results_pci/map_bus.html', 'map_kaust_bus.png'),
    ('/Users/ahmadjaroush/Downloads/Kaust/results_pci/map_car.html', 'map_kaust_car.png'),
    ('/Users/ahmadjaroush/Downloads/Kaust/results_pci/map_walk.html', 'map_kaust_walk.png'),
    ('/Users/ahmadjaroush/Downloads/Kaust/results_pci/map_combined.html', 'map_kaust_combined.png'),
    ('/Users/ahmadjaroush/Downloads/Kaust/results_pci/full_generalization_pred_vs_actual_map.html', 'map_kaust_pred_vs_actual.png'),
]

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument('--window-size=1400,1000')
opts.add_argument('--force-device-scale-factor=2')

print('Starting Chrome...')
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=opts)

for html_path, out_name in maps:
    if not os.path.exists(html_path):
        print(f'  SKIP {html_path} (not found)')
        continue
    url = 'file://' + html_path
    driver.get(url)
    time.sleep(3)
    out = os.path.join(FIG_DIR, out_name)
    driver.save_screenshot(out)
    print(f'  {out_name}')

driver.quit()
print('Done')
