# AfroHydro AI RoadWatch

**Daily rainfall, historical road connectivity and Meta Muse Spark 1.3 for Africa.**

[Watch the 3-minute demonstration](https://youtu.be/HZsCreY3ZL0)

AfroHydro AI RoadWatch combines daily AfroHydro rainfall estimates, GRIP4 historical road networks and Meta Model API to screen intercity corridors and explain the evidence. The app maps rainfall, samples rainfall along connected road paths, and uses a transparent detour-ratio heuristic to flag routes GREEN, AMBER or RED. Muse Spark 1.3 interprets the calculated JSON evidence and explains uncertainties.

The demo compares **Nairobi–Kakamega, Kenya** (GREEN; 1.28× detour ratio) with **Benguela–Kuito, Angola** (RED; 3.02×). RED means a suspected detour in the historical network—not a confirmed flood or road closure. Rainfall on a displayed detour is not necessarily rainfall on the normal driving corridor.

## Run locally

Python 3.12 is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Set MODEL_API_KEY in your operating-system environment before launching.
streamlit run afrohydro_roadwatch_v8_2.py
```

**Data required:** The code is public, but the application also needs the datasets described in [`DATA.md`](DATA.md). If the `data/Africa_Cities_All.shp` file exists, the app uses bundled `data/`; otherwise it retains the original local Windows path for the verified demonstration installation. You can override the data root with `ROADWATCH_DATA_ROOT`. Without the required datasets, the app cannot run. API access also depends on Meta account permissions and geographic availability.

## Data and limitations

- AfroHydro rasters: daily estimates, not rain-gauge observations or flood confirmation.
- GRIP4: historical connectivity; calculated paths are not verified driving directions.
- GREEN/AMBER/RED: heuristic route screening, not safety classifications.
- AI: Muse Spark 1.3 is used to explain structured results, not to calculate road distances or rainfall.

**Hackathon:** Meta AI Developer Hackathon 2026 · Build for Your World · **Team GeoWade AI**.
