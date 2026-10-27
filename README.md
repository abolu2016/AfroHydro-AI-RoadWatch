# AfroHydro AI RoadWatch
### Explainable rainfall exposure intelligence for African road corridors

**GeoWade AI | Meta Global AI Developer Hackathon 2026 | Build for the World**

AfroHydro AI RoadWatch is a research prototype that combines daily AfroHydro rainfall estimates, historical GRIP4 roads, and **Meta Muse Spark 1.3** to explain precipitation exposure along selected African intercity road corridors.

> **Important:** This is **rainfall exposure**, not confirmed flooding, road closure, a weather forecast, or driving-safety advice. Historical GRIP4 routes are not verified navigation routes.

## What it does

- Explore AfroHydro rainfall for African countries and named cities.
- Display rainfall overlays and historical GRIP4 roads on an interactive map.
- Calculate a connected historical road corridor between selected cities.
- Sample accumulated rainfall along approximately 2 km corridor sections.
- Report route length, length-weighted mean rainfall, maximum sampled rainfall, and exposure-category distances.
- Screen potential detours using road-length / straight-line distance (GREEN <=1.5; AMBER >1.5; RED >2.0). These are **heuristics**, not independent route validation.
- Ask Muse Spark 1.3 questions grounded in the application's structured numerical evidence.
- Show an offline evidence-only summary if the API is unavailable.

## Demonstration

**3-minute demo:** _Add YouTube link here before submission._

### Two tested examples (1-day rainfall ending 2026-10-26)

| Corridor | GRIP4 distance | Detour ratio | Screening | Mean / max rainfall |
|---|---:|---:|---|---|
| Nairobi–Kakamega, Kenya | 367.4 km | 1.28x | GREEN | 4.146 / 6.951 mm |
| Benguela–Kuito, Angola | 1,159.74 km | 3.02x | RED | 4.960 / 14.174 mm |

The RED example illustrates why an apparently connected historical road-network path may be unsuitable for representing the usual driving corridor. These figures are **historical test outputs**, not live conditions.

## Architecture

```text
AfroHydro daily GeoTIFFs ──> Rasterio ───────┐
                                               ├──> Streamlit + Folium map
GRIP4 historical road GeoPackage ─> GeoPandas ┤
                                               ├──> NetworkX route + 2 km rainfall samples
African cities shapefile ──────────────────────┘                 │
                                                                 v
                                              Route-quality screening + evidence JSON
                                                                 │
                                                                 v
                                                  Meta Model API / Muse Spark 1.3
                                                                 │
                                                                 v
                                                Grounded natural-language explanation
```

The RoadWatch application is **read-only**: it does not change the operational AfroHydro rainfall-production pipeline.

## Requirements

- Windows / Python 3.12 (tested locally by the developer)
- Packages in `requirements.txt`
- A Meta Model API key for AI responses (optional for offline mode)
- Local datasets described below; **the repository does not include large or third-party geospatial datasets**

## Quick start (Windows CMD)

```cmd
cd /d D:\Project_Africa\OPERATIONAL_ANALYSIS
py -3.12 -m venv .venv-roadwatch
.venv-roadwatch\Scripts\python.exe -m pip install -r requirements.txt
.venv-roadwatch\Scripts\python.exe -m streamlit run afrohydro_roadwatch_v8_1.py
```

**API key:** Set the `MODEL_API_KEY` environment variable on your own computer. Do not commit it to GitHub. For a temporary CMD session, use `set /p MODEL_API_KEY=Enter API key: ` (input is visible as you type), or use a secure local secrets manager. The application defaults to `https://api.meta.ai/v1` and `muse-spark-1.3`.

### Data locations

The current prototype uses paths relative to the `ROOT` constant at the top of the Python script. The default is `D:\Project_Africa\OPERATIONAL_ANALYSIS`; **edit `ROOT` for your own machine**.

Expected files:

```text
ROOT/
  Africa_Cities_All.shp              # plus shapefile companion files
  Countries/Nigeria.shp              # optional Nigeria boundary + companion files
  RoadWatch_Prepared/
    GRIP4_Africa_RoadWatch_Class1to4.gpkg
    Countries/Nigeria/Nigeria_RoadWatch_Roads.gpkg  # optional Nigeria-specific roads
  output/daily/YYYY/MM/AfroHydro_Daily_YYYYMMDD.tif
```

Daily rasters must exist for **every day** in a selected 1-, 3-, or 7-day window. Missing days are not silently treated as zero. The rainfall data, city shapefile, and road files are not bundled; users must supply appropriately licensed datasets and follow their respective access conditions. This repository is therefore **not a fully self-contained installation**.

## Responsible interpretation

- AfroHydro grid-cell values are modeled/satellite-informed rainfall estimates, not local gauge measurements.
- GRIP4 is a historical road dataset. Connected paths can be implausibly long or disconnected.
- GREEN means only that the distance-screen did not detect a major detour; it does **not** establish a correct route or safe travel.
- RED means a large detour is suspected. Rainfall statistics then describe **only the displayed historical path**.
- No live traffic, closure, verified flood reports, or forecast feeds are included.
- Muse Spark is instructed to explain supplied evidence, not invent measurements or road conditions.

## Project status

**Hackathon research prototype.** Successfully exercised with Meta Muse Spark 1.3 on Kenya and Angola corridor examples. Broader independent validation and deployment remain future work.

## Technology

Python, Streamlit, GeoPandas, Rasterio, NetworkX, Folium, OpenAI-compatible SDK, Meta Model API (Muse Spark 1.3).

## Acknowledgments and data

AfroHydro rainfall research and RoadWatch prototype: GeoWade AI. GRIP4 road data and background OpenStreetMap map tiles are third-party resources; follow their original licenses and attribution requirements. Do not redistribute source datasets without confirming permission.

## License

No open-source license has been selected yet. The code is publicly viewable when the repository is public, but **reuse rights are not granted automatically**. Add an appropriate `LICENSE` file only after deciding how you want the code licensed.
