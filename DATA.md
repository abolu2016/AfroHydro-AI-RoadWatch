# Reproducing RoadWatch data

The original RoadWatch installation reads from `D:\Project_Africa\OPERATIONAL_ANALYSIS`. Run `stage_data_windows.py` on that machine to **copy**, never move or delete, the newest 10 daily GeoTIFFs, city shapefile components, prepared road GeoPackages, and optional Nigeria boundary shapefile into this repository's `data/` directory.

Expected layout:

```
data/
  Africa_Cities_All.shp (.shx, .dbf, .prj and other sidecars)
  output/daily/YYYY/MM/AfroHydro_Daily_YYYYMMDD.tif
  RoadWatch_Prepared/GRIP4_Africa_RoadWatch_Class1to4.gpkg
  RoadWatch_Prepared/Countries/Nigeria/Nigeria_RoadWatch_Roads.gpkg  [optional]
  Countries/Nigeria.shp (+ sidecars) [optional]
```

**Before publication:** Verify licences and redistribution rights for GRIP4 and all ancillary datasets. Check file sizes: ordinary GitHub Git pushes reject individual files above 100 MiB. Use Git LFS for permitted large files or publish them separately with documented download instructions. The complete road network may be very large; copying it is not the same as publishing it. Never commit `MODEL_API_KEY` or a real `.env` file.

The ten most recent **available** rasters are staged; this does not guarantee ten consecutive calendar days. The app requires complete windows for 3- and 7-day accumulations. The code uses the available date selector.
