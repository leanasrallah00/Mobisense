#!/usr/bin/env python3
import os, time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from chromedriver_py import binary_path

OUT = '/Users/ahmadjaroush/Downloads/Kaust/report/figures'
opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1400,900')
opts.add_argument('--disable-gpu')
opts.add_argument('--no-sandbox')
svc = Service(executable_path=binary_path)
driver = webdriver.Chrome(service=svc, options=opts)

maps = [
    ('/Users/ahmadjaroush/Downloads/Kaust/results/map_walk_localization.html', 'map_kaust_walk.png'),
    ('/Users/ahmadjaroush/Downloads/Kaust/results/map_bus_localization.html', 'map_kaust_bus.png'),
    ('/Users/ahmadjaroush/Downloads/jedda/results_pci/map_walk.html', 'map_jeddah_walk.png'),
    ('/Users/ahmadjaroush/Downloads/jedda/results_pci/map_bus.html', 'map_jeddah_bus.png'),
    ('/Users/ahmadjaroush/Downloads/mekkah/results_pci/map_walk.html', 'map_mekkah_walk.png'),
    ('/Users/ahmadjaroush/Downloads/mekkah/results_pci/map_bus.html', 'map_mekkah_bus.png'),
]

for html_path, out_name in maps:
    if not os.path.exists(html_path):
        print(f'SKIP: {html_path}')
        continue
    driver.get('file://' + os.path.abspath(html_path))
    time.sleep(3)
    out_path = os.path.join(OUT, out_name)
    driver.save_screenshot(out_path)
    print(f'OK: {out_name} ({os.path.getsize(out_path)//1024} KB)')

driver.quit()
print('Done.')
