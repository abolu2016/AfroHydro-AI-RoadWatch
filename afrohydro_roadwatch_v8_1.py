# AfroHydro AI RoadWatch V8 - Africa Explorer + Meta Model API
# Independent read-only application. Does not modify operational AfroHydro files.
# Python 3.12, Streamlit, GeoPandas, Rasterio, Folium, NetworkX.
from pathlib import Path
from datetime import datetime, timedelta
import json
import os
import re
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.warp import transform_bounds, reproject, Resampling
from rasterio.transform import from_bounds
from shapely.geometry import LineString, MultiLineString
from shapely.ops import substring
from pyproj import Transformer
import networkx as nx
import folium
from folium.plugins import Fullscreen
from streamlit_folium import st_folium
import streamlit as st

ROOT = Path(r'D:\Project_Africa\OPERATIONAL_ANALYSIS')
DAILY = ROOT / 'output' / 'daily'
CITIES = ROOT / 'Africa_Cities_All.shp'
AFRICA_ROADS = ROOT / 'RoadWatch_Prepared' / 'GRIP4_Africa_RoadWatch_Class1to4.gpkg'
NIGERIA_ROADS = ROOT / 'RoadWatch_Prepared' / 'Countries' / 'Nigeria' / 'Nigeria_RoadWatch_Roads.gpkg'
NIGERIA_BOUNDARY = ROOT / 'Countries' / 'Nigeria.shp'
COLORS = ['#eaf4ff', '#98c8e9', '#3c86bc', '#35a865', '#f4d35e', '#ef8a35', '#ca3036']
BINS = [0, 0.5, 2, 5, 10, 20, 50, np.inf]
LABELS = ['Very little (0-0.5)', 'Light (0.5-2)', 'Low (2-5)', 'Moderate (5-10)',
          'Elevated (10-20)', 'High (20-50)', 'Very high (50+)', 'Missing data']

st.set_page_config(page_title='AfroHydro RoadWatch V8', layout='wide')
st.title('AfroHydro AI RoadWatch V8.1 - Africa Explorer')
st.caption('Africa-wide named-city rainfall and selected GRIP4 road corridors | Read-only validation build')


def daily_path(day):
    return DAILY / day.strftime('%Y') / day.strftime('%m') / ('AfroHydro_Daily_' + day.strftime('%Y%m%d') + '.tif')


def color_for(value):
    if not np.isfinite(value):
        return '#888888'
    return COLORS[min(len(COLORS)-1, int(np.searchsorted(BINS[1:], max(0, float(value)), side='right')))]


@st.cache_data(show_spinner=False)
def load_cities(path, stamp):
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        raise ValueError('City shapefile has no CRS.')
    if not {'CITY_NAME', 'CNTRY_NAME'}.issubset(gdf.columns):
        raise ValueError('City shapefile must contain CITY_NAME and CNTRY_NAME.')
    gdf = gdf.to_crs(4326)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf['CITY_NAME'] = gdf['CITY_NAME'].astype(str).str.strip()
    gdf['CNTRY_NAME'] = gdf['CNTRY_NAME'].astype(str).str.strip()
    return gdf.sort_values(['CNTRY_NAME', 'CITY_NAME']).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def list_dates(folder):
    dates = set()
    for f in folder.glob('*/*/AfroHydro_Daily_*.tif'):
        match = re.search(r'(\d{8})\.tif$', f.name)
        if match:
            dates.add(match.group(1))
    return sorted(dates, reverse=True)


@st.cache_data(show_spinner=False, max_entries=20)
def city_history(lon, lat, end_str, days, signatures):
    end = datetime.strptime(end_str, '%Y%m%d')
    output = []
    for offset in range(days-1, -1, -1):
        date = end - timedelta(days=offset)
        file = daily_path(date)
        value = np.nan
        if file.exists():
            with rasterio.open(file) as src:
                if src.crs is not None:
                    xx, yy = rasterio.warp.transform('EPSG:4326', src.crs, [lon], [lat])
                    cell = next(src.sample([(xx[0], yy[0])], masked=True))[0]
                    if not np.ma.is_masked(cell):
                        candidate = float(cell)
                        if np.isfinite(candidate) and candidate >= 0 and not (src.nodata is not None and np.isfinite(src.nodata) and np.isclose(candidate, src.nodata)):
                            value = candidate
        output.append({'Date': date.strftime('%Y-%m-%d'), 'Rainfall (mm)': value})
    return pd.DataFrame(output)


@st.cache_data(show_spinner=False, max_entries=5)
def make_rain_grid(bounds, end_str, days, signatures, width=650):
    west, south, east, north = bounds
    height = max(180, min(650, round(width * (north-south)/max(east-west, .01))))
    transform = from_bounds(west, south, east, north, width, height)
    total = np.zeros((height, width), dtype=np.float32)
    valid = np.ones((height, width), dtype=bool)
    end = datetime.strptime(end_str, '%Y%m%d')
    for offset in range(days):
        with rasterio.open(daily_path(end-timedelta(days=offset))) as src:
            dest = np.full((height, width), np.nan, dtype=np.float32)
            reproject(rasterio.band(src, 1), dest, src_transform=src.transform,
                      src_crs=src.crs, src_nodata=src.nodata,
                      dst_transform=transform, dst_crs='EPSG:4326', dst_nodata=np.nan,
                      resampling=Resampling.nearest)
            good = np.isfinite(dest) & (dest >= 0)
            valid &= good
            total += np.where(good, dest, 0)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    for i, color in enumerate(COLORS):
        mask = valid & (total >= BINS[i]) & (total < BINS[i+1])
        rgb = tuple(int(color[k:k+2], 16) for k in (1, 3, 5))
        rgba[mask, 0] = rgb[0]
        rgba[mask, 1] = rgb[1]
        rgba[mask, 2] = rgb[2]
        rgba[mask, 3] = 255
    return rgba, total, valid, transform


def sample_grid(grid, valid, transform, lon, lat):
    from rasterio.transform import rowcol
    r, c = rowcol(transform, lon, lat)
    if 0 <= r < grid.shape[0] and 0 <= c < grid.shape[1] and valid[r, c]:
        return float(grid[r, c])
    return np.nan


@st.cache_data(show_spinner=False, max_entries=5)
def load_country_roads(path, stamp, bounds, max_classes):
    # GeoPandas handles bbox reprojection when a GeoSeries is supplied.
    # Avoid a hard dependency on Fiona, and preserve the file's native CRS.
    from shapely.geometry import box
    west, south, east, north = bounds
    query = gpd.GeoSeries([box(west, south, east, north)], crs='EPSG:4326')
    # Prefer pyogrio (installed with modern GeoPandas); fall back to default.
    try:
        import pyogrio
        metadata = pyogrio.read_info(path)
        source_crs = metadata.get('crs')
        if not source_crs:
            raise ValueError('Road GeoPackage is missing its CRS.')
        query_native = query.to_crs(source_crs)
        bbox_native = tuple(map(float, query_native.total_bounds))
        roads = gpd.read_file(path, bbox=bbox_native, engine='pyogrio')
    except ImportError:
        # GeoPandas can transform a GeoSeries bbox using its installed engine.
        roads = gpd.read_file(path, bbox=query)
    if roads.crs is None:
        raise ValueError('Road GeoPackage has no declared CRS.')
    roads = roads.to_crs('EPSG:4326')
    if 'road_class' in roads.columns:
        # GRIP4 prepared files may encode road_class as descriptive text.
        # Normalize both numeric and text classes without altering source files.
        class_map = {'highways': 1, 'highway': 1,
                     'primary roads': 2, 'primary': 2,
                     'secondary roads': 3, 'secondary': 3,
                     'tertiary roads': 4, 'tertiary': 4}
        raw_classes = roads['road_class']
        numeric_classes = pd.to_numeric(raw_classes, errors='coerce')
        text_classes = raw_classes.astype(str).str.strip().str.casefold().map(class_map)
        roads['road_class_code'] = numeric_classes.fillna(text_classes)
        roads = roads.loc[roads['road_class_code'].isin(max_classes)].copy()
    else:
        # A missing class field must not silently hide every road.
        roads.attrs['missing_road_class'] = True
    roads = roads.loc[roads.geometry.notna() & ~roads.geometry.is_empty].copy()
    roads = roads.loc[roads.geometry.geom_type.isin(['LineString', 'MultiLineString'])].copy()
    return roads


def make_graph(roads, snap_m=50):
    projected_crs = roads.estimate_utm_crs()
    if projected_crs is None:
        raise ValueError('Cannot determine a local metric projection for routing.')
    projected = roads.to_crs(projected_crs)
    graph = nx.Graph()
    for row in projected.itertuples(index=False):
        geom = row.geometry
        lines = list(geom.geoms) if isinstance(geom, MultiLineString) else [geom]
        for line in lines:
            if not isinstance(line, LineString) or line.is_empty or line.length < 1:
                continue
            a = (round(line.coords[0][0]/snap_m), round(line.coords[0][1]/snap_m))
            b = (round(line.coords[-1][0]/snap_m), round(line.coords[-1][1]/snap_m))
            if a == b:
                continue
            if not graph.has_edge(a, b) or line.length < graph[a][b]['weight']:
                graph.add_edge(a, b, weight=float(line.length), geometry=line)
    return graph, projected_crs


def find_corridor(roads, start, finish, snap_m=50, max_access_km=15):
    graph, crs = make_graph(roads, snap_m)
    if not graph.number_of_nodes():
        raise ValueError('No usable GRIP4 road endpoints in selected country.')
    pts = gpd.GeoSeries([start, finish], crs='EPSG:4326').to_crs(crs)
    nodes = list(graph.nodes)
    coords = np.asarray(nodes, dtype=float)*snap_m
    d1 = np.linalg.norm(coords - [pts.iloc[0].x, pts.iloc[0].y], axis=1)
    d2 = np.linalg.norm(coords - [pts.iloc[1].x, pts.iloc[1].y], axis=1)
    node_idx = {n: i for i, n in enumerate(nodes)}
    best = None
    for comp in nx.connected_components(graph):
        indices = [node_idx[n] for n in comp]
        i = min(indices, key=lambda k: d1[k])
        j = min(indices, key=lambda k: d2[k])
        if d1[i] > max_access_km*1000 or d2[j] > max_access_km*1000:
            continue
        score = float(d1[i] + d2[j])
        if best is None or score < best[0]:
            best = (score, nodes[i], nodes[j], float(d1[i]), float(d2[j]))
    if best is None:
        raise ValueError('No common connected road component is accessible from both cities within the allowed access distance. No route was invented.')
    _, a, b, gap1, gap2 = best
    if a == b:
        raise ValueError('Both cities snapped to the same node; no meaningful corridor found.')
    path = nx.shortest_path(graph, a, b, weight='weight')
    lines = [graph[u][v]['geometry'] for u, v in zip(path[:-1], path[1:])]
    route = gpd.GeoSeries(lines, crs=crs).to_crs(4326)
    length = sum(line.length for line in lines)/1000
    return route, length, gap1/1000, gap2/1000


def great_circle_km(point_a, point_b):
    # Haversine distance between city points in geographic coordinates.
    lat1, lon1 = np.radians([point_a.y, point_a.x])
    lat2, lon2 = np.radians([point_b.y, point_b.x])
    delta_lat, delta_lon = lat2-lat1, lon2-lon1
    h = np.sin(delta_lat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(delta_lon/2)**2
    return float(6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(h, 0, 1))))


def assess_route_quality(length_km, straight_km, gap1_km, gap2_km):
    # Screening thresholds, NOT proof of a correct or incorrect driving route.
    ratio = float(length_km / straight_km) if straight_km > 0.1 else float('inf')
    notes = []
    if ratio > 2.0:
        level = 'RED - major detour suspected'
        notes.append('Road length exceeds twice the city-to-city straight-line distance.')
    elif ratio > 1.5:
        level = 'AMBER - route review recommended'
        notes.append('Road length exceeds 1.5 times the straight-line distance.')
    else:
        level = 'GREEN - no major detour detected'
    if max(gap1_km, gap2_km) > 5:
        notes.append('At least one city access gap exceeds 5 km; this access is not included in the route.')
        if not level.startswith('RED'):
            level = 'AMBER - route review recommended'
    if not notes:
        notes.append('Distance screening passed; visual inspection and external verification are still needed.')
    return {'status': level, 'straight_line_km': round(straight_km, 2),
            'detour_ratio': round(ratio, 2), 'notes': notes,
            'method': 'Haversine distance and heuristic screening thresholds (1.5x and 2.0x).',
            'validated_driving_route': False}


def route_exposure(route, grid, valid, transform, spacing_km=2):
    metric_crs = route.estimate_utm_crs()
    projected = route.to_crs(metric_crs)
    records = []
    for line in projected:
        n = max(1, int(np.ceil(line.length/(spacing_km*1000))))
        for i in range(n):
            piece = substring(line, i*line.length/n, (i+1)*line.length/n)
            midpoint = piece.interpolate(.5, normalized=True)
            geo = gpd.GeoSeries([midpoint], crs=metric_crs).to_crs(4326).iloc[0]
            mm = sample_grid(grid, valid, transform, geo.x, geo.y)
            records.append((piece.length/1000, mm))
    total = sum(km for km, _ in records)
    known = [(km, mm) for km, mm in records if np.isfinite(mm)]
    by_bin = np.zeros(8)
    for km, mm in records:
        idx = 7 if not np.isfinite(mm) else min(6, int(np.searchsorted(BINS[1:], max(mm, 0), side='right')))
        by_bin[idx] += km
    mean = sum(km*mm for km, mm in known)/sum(km for km, _ in known) if known else np.nan
    peak = max((mm for _, mm in known), default=np.nan)
    return total, mean, peak, by_bin




def colored_corridor_pieces(route, grid, valid, transform, spacing_km=2):
    # Preserve original GRIP4 geometry. Subdivide each edge into <= 2 km
    # pieces and sample accumulated rainfall at each piece midpoint.
    metric_crs = route.estimate_utm_crs()
    projected = route.to_crs(metric_crs)
    to_geo = Transformer.from_crs(metric_crs, 'EPSG:4326', always_xy=True)
    pieces = []
    for road in projected:
        if road is None or road.is_empty:
            continue
        lines = list(road.geoms) if isinstance(road, MultiLineString) else [road]
        for line in lines:
            if line.is_empty or line.length <= 0:
                continue
            n = max(1, int(np.ceil(line.length / (spacing_km * 1000))))
            for i in range(n):
                piece = substring(line, i * line.length / n, (i + 1) * line.length / n)
                mid = piece.interpolate(.5, normalized=True)
                lon, lat = to_geo.transform(mid.x, mid.y)
                mm = sample_grid(grid, valid, transform, lon, lat)
                if np.isfinite(mm):
                    idx = min(6, int(np.searchsorted(BINS[1:], max(mm, 0), side='right')))
                else:
                    idx = 7
                pieces.append({'geometry': piece, 'rain_mm': float(mm) if np.isfinite(mm) else None,
                               'category': LABELS[idx], 'line_color': COLORS[idx] if idx < 7 else '#888888',
                               'piece_km': round(float(piece.length / 1000), 3)})
    if not pieces:
        raise ValueError('Route contains no measurable road sections.')
    return gpd.GeoDataFrame(pieces, geometry='geometry', crs=metric_crs).to_crs(4326)


def facts_to_text(facts):
    return json.dumps(facts, ensure_ascii=True, allow_nan=False, indent=2)


if not CITIES.exists():
    st.error(f'City shapefile not found: {CITIES}')
    st.stop()
try:
    cities = load_cities(str(CITIES), CITIES.stat().st_mtime_ns)
except Exception as exc:
    st.error(f'Cannot load city data: {exc}')
    st.stop()

available_dates = list_dates(DAILY)
if not available_dates:
    st.error(f'No AfroHydro daily GeoTIFFs found under {DAILY}')
    st.stop()

countries = sorted(cities['CNTRY_NAME'].dropna().unique())
with st.sidebar:
    st.header('Africa Explorer V8')
    country = st.selectbox('Country', countries, index=countries.index('Nigeria') if 'Nigeria' in countries else 0)
    days = st.selectbox('Accumulation period', [1, 3, 7], index=0,
                        format_func=lambda d: f'{d} day(s)')
    # Only offer end dates with a complete consecutive sequence of rasters.
    complete_dates = []
    for candidate in available_dates:
        dt = datetime.strptime(candidate, '%Y%m%d')
        if all(daily_path(dt - timedelta(days=i)).exists() for i in range(days)):
            complete_dates.append(candidate)
    if not complete_dates:
        st.error(f'No complete {days}-day rainfall windows available. Choose a shorter accumulation period.')
        st.stop()
    date_str = st.selectbox('Rainfall end date (complete windows only)', complete_dates)
    show_raster = st.checkbox('Show rainfall raster', value=True)
    show_roads = st.checkbox('Show historical GRIP4 roads', value=True)
    show_legend = st.checkbox('Show rainfall legend', value=True)
    road_classes = st.multiselect('Road classes', [1, 2, 3, 4], default=[1, 2, 3, 4])
    raster_opacity = st.slider('Rainfall overlay opacity', 0.1, 1.0, .68, .05)
    st.caption('Missing days are never silently treated as zero. Select a complete date window.')

selected = cities[cities['CNTRY_NAME'] == country].copy()
if selected.empty:
    st.error('No cities for this country.')
    st.stop()
labels = selected['CITY_NAME'].tolist()
# Use city extents with generous margin; Nigeria uses its actual country boundary.
if country == 'Nigeria' and NIGERIA_BOUNDARY.exists():
    border = gpd.read_file(NIGERIA_BOUNDARY).to_crs(4326)
    west, south, east, north = map(float, border.total_bounds)
else:
    west, south, east, north = map(float, selected.total_bounds)
    dx, dy = max(1.5, (east-west)*.2), max(1.5, (north-south)*.2)
    west, south, east, north = west-dx, south-dy, east+dx, north+dy
    border = None
bounds = (west, south, east, north)
end = datetime.strptime(date_str, '%Y%m%d')
files = [daily_path(end-timedelta(days=i)) for i in range(days)]
missing = [f.name for f in files if not f.exists()]
grid = valid = transform = rgba = None
if missing:
    st.warning('Missing daily rasters for the selected accumulation: ' + ', '.join(missing))
else:
    signatures = tuple((str(f), f.stat().st_mtime_ns) for f in files)
    try:
        rgba, grid, valid, transform = make_rain_grid(bounds, date_str, days, signatures)
    except Exception as exc:
        st.warning(f'Rainfall grid could not be prepared: {exc}')

roads = None
roads_path = NIGERIA_ROADS if country == 'Nigeria' and NIGERIA_ROADS.exists() else AFRICA_ROADS
st.subheader(f'{country} | {date_str} | {days}-day rainfall')
st.info('Map is below the city and corridor panels. Layer switches request roads and rainfall, but the map only shows layers that load successfully. Check the feature count and warnings below.')
map_view = folium.Map(location=[(south+north)/2, (west+east)/2], zoom_start=6 if country=='Nigeria' else 5,
                      tiles='OpenStreetMap', control_scale=True, prefer_canvas=True)
Fullscreen().add_to(map_view)
if show_raster and rgba is not None:
    folium.raster_layers.ImageOverlay(rgba, bounds=[[south, west], [north, east]], opacity=raster_opacity,
                                      name=f'AfroHydro {days}-day rainfall').add_to(map_view)
if border is not None:
    folium.GeoJson(json.loads(border.to_json()), name='Nigeria boundary',
                   style_function=lambda _: {'color': '#222222', 'weight': 2.5, 'fill': False}).add_to(map_view)
for row in selected.itertuples(index=False):
    folium.CircleMarker([row.geometry.y, row.geometry.x], radius=3, color='#173b59', fill=True,
                        fill_opacity=.8, tooltip=str(row.CITY_NAME)).add_to(map_view)

if show_roads:
    if not roads_path.exists():
        st.warning(f'Road GeoPackage not found: {roads_path}')
    else:
        try:
            with st.spinner('Loading roads in selected country view...'):
                roads = load_country_roads(str(roads_path), roads_path.stat().st_mtime_ns, bounds, tuple(road_classes))
            st.caption(f'{len(roads):,} historical GRIP4 road features loaded within the view from {roads_path.name}.')
            if not roads.empty and 'road_class_code' in roads.columns:
                st.caption('Loaded road classes: ' + ', '.join(f'{int(k)}: {v:,}' for k, v in roads['road_class_code'].value_counts().sort_index().items()))
            if 'road_class' not in roads.columns:
                st.warning('The road dataset has no road_class field; class filtering was skipped.')
            if roads.empty:
                st.warning('No road lines intersect this view after filtering. Try selecting all road classes or checking the GeoPackage extent.')
            if not roads.empty:
                # Render a bounded number of full original features for responsiveness;
                # never randomly drop local segments or imply complete coverage when limited.
                display_limit = 12000
                display_roads = roads.head(display_limit)
                if len(roads) > display_limit:
                    st.warning(f'Overview displays the first {display_limit:,} of {len(roads):,} features. Select a smaller country/view for detailed coverage.')
                # Preserve full road geometries in the selected view; show local rainfall
                # categories when an accumulation grid is available.
                display_roads = display_roads.copy()
                if grid is not None:
                    centers = display_roads.geometry.interpolate(0.5, normalized=True)
                    display_roads['line_color'] = [color_for(sample_grid(grid, valid, transform, p.x, p.y))
                                                   for p in centers]
                else:
                    display_roads['line_color'] = '#777777'
                folium.GeoJson(json.loads(display_roads[['line_color', 'geometry']].to_json()),
                               name='GRIP4 roads (rainfall exposure)',
                               style_function=lambda feat: {'color': feat['properties']['line_color'],
                                                            'weight': 2.6, 'opacity': .95}).add_to(map_view)
        except Exception as exc:
            st.error(f'Road loading failed: {exc}')

st.subheader('City rainfall and road corridor questions')
tab_city, tab_route, tab_ai = st.tabs(['City rainfall', 'Intercity road corridor', 'Ask RoadWatch AI'])
latest_facts = None
city_facts = None
route_facts = None
with tab_city:
    city_name = st.selectbox('City', labels, index=labels.index('Lagos') if 'Lagos' in labels else 0)
    city = selected[selected['CITY_NAME'] == city_name].iloc[0]
    history = city_history(float(city.geometry.x), float(city.geometry.y), date_str, days,
                           tuple((str(f), f.stat().st_mtime_ns if f.exists() else -1) for f in files))
    st.dataframe(history, use_container_width=True, hide_index=True)
    if history['Rainfall (mm)'].notna().all():
        mm = float(history['Rainfall (mm)'].sum())
        st.success(f'{city_name}, {country}: {mm:.2f} mm accumulated in {days} day(s). Display category: {LABELS[min(6, int(np.searchsorted(BINS[1:], mm, side="right")))]}.')
        city_facts = {'kind': 'city_rainfall', 'city': city_name, 'country': country,
                        'end_date': date_str, 'days': days, 'accumulated_mm': round(mm, 3),
                        'daily': history.where(pd.notna(history), None).to_dict('records')}
    else:
        st.warning('Incomplete rainfall history. No accumulated total is reported.')
    st.caption('City value represents one AfroHydro grid cell, not an in-situ rain gauge. Display categories are not climatological anomalies.')

with tab_route:
    c1, c2 = st.columns(2)
    with c1:
        origin = st.selectbox('From', labels, index=labels.index('Lagos') if 'Lagos' in labels else 0)
    with c2:
        destination = st.selectbox('To', labels, index=labels.index('Ibadan') if 'Ibadan' in labels else min(1, len(labels)-1))
    if st.button('Analyse GRIP4 corridor', type='primary'):
        if origin == destination:
            st.error('Choose two different cities.')
        elif grid is None:
            st.error('Rainfall grid unavailable for selected period.')
        elif not roads_path.exists():
            st.error('Road data file is missing.')
        else:
            try:
                with st.spinner('Building connected road network and sampling local rainfall...'):
                    routing_roads = roads if roads is not None and set(road_classes)=={1,2,3,4} else load_country_roads(
                        str(roads_path), roads_path.stat().st_mtime_ns, bounds, (1,2,3,4))
                    a = selected[selected['CITY_NAME'] == origin].iloc[0]
                    b = selected[selected['CITY_NAME'] == destination].iloc[0]
                    route, length, gap1, gap2 = find_corridor(routing_roads, a.geometry, b.geometry,
                                                              max_access_km=30 if country=='Nigeria' else 15)
                    measured_length, mean, maximum, by_bin = route_exposure(route, grid, valid, transform)
                    quality = assess_route_quality(length, great_circle_km(a.geometry, b.geometry), gap1, gap2)
                result = {'country': country, 'from': origin, 'to': destination,
                          'end_date': date_str, 'days': days, 'length_km': round(length, 2),
                          'sampled_length_km': round(measured_length, 2),
                          'mean_mm': round(mean, 3) if np.isfinite(mean) else None,
                          'max_mm': round(maximum, 3) if np.isfinite(maximum) else None,
                          'access_gaps_km': [round(gap1, 2), round(gap2, 2)],
                          'route_quality': quality,
                          'exposure_km': {LABELS[i]: round(float(v), 2) for i, v in enumerate(by_bin)}}
                st.session_state['v7_route'] = (result, route.to_json())
            except Exception as exc:
                st.session_state.pop('v7_route', None)
                st.error(f'Cannot establish a reliable GRIP4 corridor: {exc}')
    saved = st.session_state.get('v7_route')
    if saved:
        result, geojson_route = saved
        if (result['country'], result['from'], result['to'], result['end_date'], result['days']) == (country, origin, destination, date_str, days):
            route_facts = result
            st.success(f"{origin} to {destination}: {result['length_km']:.1f} km of connected historical GRIP4 roads. Mean rainfall: {result['mean_mm']} mm; maximum: {result['max_mm']} mm.")
            quality = result.get('route_quality', {})
            if quality:
                status = quality['status']
                details = (f"Route quality: {status}. Straight-line distance: "
                           f"{quality['straight_line_km']:.1f} km; detour ratio: "
                           f"{quality['detour_ratio']:.2f}x. " + ' '.join(quality['notes']))
                if status.startswith('RED'):
                    st.error(details)
                    st.warning('The rainfall results apply to the DISPLAYED historical GRIP4 detour only, not necessarily the normal driving corridor.')
                elif status.startswith('AMBER'):
                    st.warning(details)
                else:
                    st.info(details)
                st.caption('Route quality is heuristic screening, not independently verified road navigation.')
            st.dataframe(pd.DataFrame([{'Category': k, 'Route length (km)': v,
                                       'Route share (%)': round(100*v/max(result['length_km'], .001), 1)}
                                      for k, v in result['exposure_km'].items()]), hide_index=True, use_container_width=True)
            st.caption(f"City-to-network access gaps (excluded from route): {result['access_gaps_km'][0]} and {result['access_gaps_km'][1]} km.")
            st.warning('GRIP4 is historical and may be disconnected or inaccurate. This is rainfall exposure, not confirmed road flooding, road closure, or driving safety.')
            # Draw a thin purple corridor outline underneath rainfall-coloured pieces.
            folium.GeoJson(json.loads(geojson_route), name='Corridor outline (purple)',
                           style_function=lambda _: {'color': '#9200c9', 'weight': 9, 'opacity': .85}).add_to(map_view)
            try:
                route_shapes = gpd.GeoDataFrame.from_features(json.loads(geojson_route)['features'], crs='EPSG:4326')
                with st.spinner('Colouring the selected corridor at 2 km intervals...'):
                    colored = colored_corridor_pieces(route_shapes.geometry, grid, valid, transform, spacing_km=2)
                folium.GeoJson(
                    json.loads(colored[['rain_mm', 'category', 'piece_km', 'line_color', 'geometry']].to_json()),
                    name='Corridor rainfall (2 km)',
                    style_function=lambda feat: {'color': feat['properties']['line_color'], 'weight': 5.5, 'opacity': 1},
                    highlight_function=lambda feat: {'weight': 8, 'color': '#ff00ff', 'opacity': 1},
                    tooltip=folium.GeoJsonTooltip(fields=['category', 'rain_mm', 'piece_km'],
                        aliases=['Rainfall category', 'Accumulated rainfall (mm)', 'Section length (km)'])
                ).add_to(map_view)
                st.caption(f'Corridor coloured along {len(colored):,} local road sections (maximum 2 km each). Hover over a section for its rainfall.')
            except Exception as exc:
                st.warning(f'Local corridor colouring unavailable: {exc}. Purple route outline remains visible.')

def ask_meta_model(question, evidence, model, base_url, timeout=90):
    # Use Meta's documented OpenAI-compatible SDK. Never display the API key.
    try:
        from openai import OpenAI, APIStatusError, APITimeoutError, APIConnectionError
    except ImportError:
        raise RuntimeError('OpenAI SDK is missing. Install with: .venv-roadwatch\\Scripts\\python.exe -m pip install -U openai') from None
    key = os.environ.get('MODEL_API_KEY', '').strip()
    if not key:
        raise RuntimeError('MODEL_API_KEY is not available. Open a new CMD window after setx.')
    instructions = (
        'You are AfroHydro AI RoadWatch, an evidence-grounded geospatial rainfall assistant. '
        'Answer using only the supplied JSON evidence. Never invent numerical measurements, '
        'dates, current road conditions, flooding, road closures, or forecasts. '
        'AfroHydro values are raster estimates, not rain-gauge observations. '
        'Historical GRIP4 rainfall exposure is not proof of flooding or driving safety. '
        'For RED routes, explain the suspected detour and that the exposure describes only '
        'the displayed route, not the usual driving corridor. GREEN and AMBER remain heuristic. '
        'When evidence is insufficient, say so. Be concise and use only supported numbers.'
    )
    client = OpenAI(base_url=base_url.rstrip('/'), api_key=key, timeout=timeout, max_retries=1)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'developer', 'content': instructions},
                {'role': 'user', 'content': 'RoadWatch evidence (JSON):\n' + facts_to_text(evidence)
                 + '\n\nQuestion: ' + question},
            ],
            # Leave output-token limit unset: reasoning can consume the budget
            # before any visible answer is produced.
        )
    except APIStatusError as exc:
        code = exc.status_code
        hint = ('Check API key and account permissions.' if code in (401, 403)
                else 'Check account limits or billing.' if code == 429
                else 'Check request settings and model access.' if code == 400
                else 'Meta service error; try again shortly.')
        raise RuntimeError(f'Meta API HTTP {code}. {hint}') from None
    except APITimeoutError:
        raise RuntimeError('Meta API request timed out. Try again.') from None
    except APIConnectionError:
        raise RuntimeError('Cannot connect to Meta API. Check network and API base URL.') from None
    except Exception as exc:
        raise RuntimeError(f'Meta API request failed ({type(exc).__name__}).') from None
    choices = getattr(response, 'choices', None)
    if not choices:
        raise RuntimeError('Meta returned no completion choices. Check API service status.')
    choice = choices[0]
    finish = getattr(choice, 'finish_reason', None)
    content = getattr(choice.message, 'content', None) if getattr(choice, 'message', None) else None
    if isinstance(content, list):
        content = '\n'.join(str(getattr(part, 'text', '') or (part.get('text', '') if isinstance(part, dict) else '')) for part in content)
    if isinstance(content, str) and content.strip():
        return content.strip()
    if finish == 'length':
        raise RuntimeError('Meta reached its generation limit before returning visible text. Retry the question.')
    if finish == 'content_filter':
        raise RuntimeError('Meta filtered the response. Rephrase the question.')
    if finish == 'tool_calls':
        raise RuntimeError('Meta requested a tool call, but this RoadWatch build uses text-only answers.')
    raise RuntimeError(f'Meta returned no visible answer (finish_reason={finish!r}). Try again or check the model dashboard.')


with tab_ai:
    st.caption('Muse Spark answers questions using the selected RoadWatch evidence, not unverified measurements.')
    evidence_options = {}
    if city_facts is not None:
        evidence_options['Selected city rainfall'] = city_facts
    if route_facts is not None:
        evidence_options['Calculated road corridor'] = route_facts
    if not evidence_options:
        st.warning('Select a city with complete rainfall history or analyse a road corridor first.')
    else:
        choice = st.radio('Evidence to use', list(evidence_options), horizontal=True,
                          index=len(evidence_options)-1)
        facts = evidence_options[choice]
        with st.expander('Verified data supplied to the AI'):
            st.json(facts)
        st.download_button('Download verified AI evidence (JSON)', facts_to_text(facts),
                           file_name='roadwatch_verified_evidence.json', mime='application/json')
        key_ready = bool(os.environ.get('MODEL_API_KEY', '').strip())
        if key_ready:
            st.success('Meta API key detected in this Streamlit process (secret not displayed).')
        else:
            st.warning('MODEL_API_KEY not detected. Offline evidence summary remains available.')
        with st.expander('Meta Model API settings'):
            model_name = st.text_input('Model identifier', value='muse-spark-1.3')
            base_url = st.text_input('API base URL', value='https://api.meta.ai/v1',
                                     help='Change only if Meta documentation specifies a different endpoint.')
            st.caption('Meta API is pay-as-you-go. Each successful request may incur a charge.')
        question = st.text_input('Ask RoadWatch AI',
                                 placeholder='Why is the Benguela to Kuito corridor flagged RED?')
        if st.button('Ask Muse Spark', disabled=not bool(question.strip()) or not key_ready):
            if not base_url.startswith('https://'):
                st.error('The API base URL must start with https://')
            else:
                with st.spinner('Asking Meta Muse Spark with verified RoadWatch evidence...'):
                    try:
                        answer = ask_meta_model(question.strip(), facts, model_name.strip(), base_url.strip())
                        st.session_state['v8_answer'] = (question.strip(), choice, facts, answer)
                    except Exception as exc:
                        st.error(str(exc))
        saved_answer = st.session_state.get('v8_answer')
        if saved_answer and saved_answer[:3] == (question.strip(), choice, facts):
            st.markdown('**Muse Spark response**')
            st.write(saved_answer[3])
        st.markdown('**Offline, evidence-only summary**')
        if facts.get('kind') == 'city_rainfall':
            st.write(f"{facts['city']}, {facts['country']}: {facts['accumulated_mm']:.2f} mm accumulated over {facts['days']} day(s) ending {facts['end_date']}. This is a raster estimate, not a gauge observation.")
        else:
            quality = facts.get('route_quality', {})
            if quality.get('status', '').startswith('RED'):
                st.error(f"The historical GRIP4 path from {facts['from']} to {facts['to']} is flagged RED ({quality.get('detour_ratio')}x straight-line distance). Its {facts['length_km']:.1f} km route and sampled rainfall apply ONLY to the displayed detour, not a verified normal driving route.")
            else:
                st.write(f"Historical GRIP4 corridor {facts['from']} to {facts['to']}: {facts['length_km']:.1f} km; mean sampled rainfall {facts['mean_mm']} mm over {facts['days']} day(s). Screening: {quality.get('status', 'not assessed')}. This is rainfall exposure, not verified road safety.")

folium.LayerControl(collapsed=False).add_to(map_view)
map_view.fit_bounds([[south, west], [north, east]])
st.subheader('Africa Explorer map - scroll here to see rainfall and roads')
st_folium(map_view, height=620, width=None, returned_objects=[],
          key=f'v8_{country}_{date_str}_{days}_{show_raster}_{show_roads}_{raster_opacity}_{tuple(road_classes)}_{origin}_{destination}_{bool(saved)}')
legend = '<div style="display:flex;flex-wrap:wrap;gap:10px;padding:10px;background:#f3f7f9">'
for col, label in zip(COLORS+['#888888'], LABELS):
    legend += f'<span><span style="display:inline-block;width:18px;height:12px;background:{col};border:1px solid #666"></span> {label} mm</span>'
if show_legend:
    st.markdown(legend+'</div>', unsafe_allow_html=True)
st.caption('Rainfall categories describe accumulated depth over the selected period, not unusualness or flood probability. Africa-wide routing is experimental.')
