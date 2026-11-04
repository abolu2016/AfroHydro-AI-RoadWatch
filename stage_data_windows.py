"""Copy (never delete) the latest 10 rainfall rasters and required geodata.
Run from the repository directory on the original Windows machine:
  .venv-roadwatch\Scripts\python.exe stage_data_windows.py
or use any Python 3.12 installation.
"""
from pathlib import Path
import shutil
import argparse
import re

DEFAULT_SOURCE = Path(r'D:\Project_Africa\OPERATIONAL_ANALYSIS')
TARGET = Path(__file__).resolve().parent / 'data'

def copy_one(source, target):
    if not source.is_file():
        print('MISSING:', source)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print('COPIED:', source, '->', target, f'({target.stat().st_size/1024/1024:.1f} MiB)')

def copy_shapefile(source, destination):
    for part in source.parent.glob(source.stem + '.*'):
        copy_one(part, destination / part.name)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--skip-roads', action='store_true', help='Skip potentially large road GeoPackages')
    args = parser.parse_args()
    root = args.source
    rain = root / 'output' / 'daily'
    candidates = []
    for f in rain.glob('*/*/AfroHydro_Daily_*.tif'):
        match = re.fullmatch(r'AfroHydro_Daily_(\d{8})\.tif', f.name)
        if match:
            candidates.append((match.group(1), f))
    for _, f in sorted(candidates, reverse=True)[:10]:
        copy_one(f, TARGET / f.relative_to(root))
    if not candidates:
        print('WARNING: No daily GeoTIFFs found.')
    copy_shapefile(root / 'Africa_Cities_All.shp', TARGET)
    copy_shapefile(root / 'Countries' / 'Nigeria.shp', TARGET / 'Countries')
    if not args.skip_roads:
        for rel in [Path('RoadWatch_Prepared/GRIP4_Africa_RoadWatch_Class1to4.gpkg'), Path('RoadWatch_Prepared/Countries/Nigeria/Nigeria_RoadWatch_Roads.gpkg')]:
            copy_one(root / rel, TARGET / rel)
    print('Finished staging. Review DATA.md, licences and file sizes before git add.')

if __name__ == '__main__':
    main()
