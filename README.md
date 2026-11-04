# AfroHydro AI RoadWatch

**Daily rainfall and road-access analysis for Africa, with Meta Muse Spark integration.**

AfroHydro AI RoadWatch combines daily AfroHydro rainfall estimates with African road-network data to assess road connectivity, rainfall exposure, and potential access constraints.

The application uses **Meta Muse Spark 1.3** to explain the analysis results in plain language.

## Demo Video

**YouTube:** [Watch the 3-minute demonstration](PASTE_YOUTUBE_URL_HERE)

## Features

- Daily rainfall visualization across Africa
- Road-corridor analysis between selected cities
- Route distance, detour ratio, and rainfall exposure estimates
- GREEN/RED indicators based on network-connectivity heuristics
- Meta Muse Spark integration for AI-assisted interpretation

## Technology

Python, Streamlit, GeoPandas, Rasterio, NetworkX, GRIP4 road-network data, AfroHydro rainfall data, and Meta Model API.

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your Meta Model API key:

```cmd
set MODEL_API_KEY=your_api_key
```

Run the application:

```bash
streamlit run afrohydro_roadwatch_v8_1.py
```

The application also requires the AfroHydro rainfall rasters, prepared GRIP4 road-network dataset, and African city locations.

## Meta Muse Spark

RoadWatch sends computed rainfall and road-network results to Muse Spark 1.3 for interpretation. Live API requests require an authorized Meta Model API account and access from a supported region.

If the API is unavailable, RoadWatch provides an evidence-based explanation without live AI inference.

## Limitations

Road-network connectivity is based on historical GRIP4 data. The indicators do not confirm road closures, flooding, or real-time travel safety.

## Hackathon

**Meta Global AI Developer Hackathon 2026**  
Track: Build for the World  
Team: GeoWade AI
