import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
from datetime import datetime, date, timedelta
import json
from pathlib import Path
import textwrap

# ---------------------------------------------------------------------------
# Robust Earth Engine & GIS Imports (No geemap dependency to avoid BoxKeyError)
# ---------------------------------------------------------------------------
try:
    import ee
    HAS_EE = True
except ImportError:
    HAS_EE = False

try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

# ---------------------------------------------------------------------------
# Scientific Parameters & Weights (From your Colab notebook)
# ---------------------------------------------------------------------------
WEIGHTS = {"NDVI": 0.30, "NDWI": 0.20, "EVI": 0.10, "SAVI": 0.10, "MSI": 0.20, "GCI": 0.10}
CLASS_LABELS = ["Critical", "Stressed", "Moderate", "Healthy", "Excellent"]
CLASS_VIS_COLORS = ["#800000", "#FF6600", "#FFFF00", "#66CC66", "#006600"]

# ---------------------------------------------------------------------------
# Boundary Manager Class
# ---------------------------------------------------------------------------
class BoundaryManager:
    def __init__(self, boundary_path):
        self.boundary_path = Path(boundary_path)
        self.boundaries = None

    def load(self):
        try:
            if self.boundary_path.exists():
                if HAS_GEOPANDAS:
                    self.boundaries = gpd.read_file(self.boundary_path)
                else:
                    with open(self.boundary_path, 'r') as f:
                        self.boundaries = json.load(f)
            else:
                self.boundaries = None
        except Exception:
            self.boundaries = None

    def get_district_ee_geometry(self, state, district):
        if self.boundaries is None:
            return None
        try:
            if HAS_GEOPANDAS:
                d = self.boundaries[
                    (self.boundaries["NAME_1"].str.lower() == state.lower()) &
                    (self.boundaries["NAME_2"].str.lower() == district.lower())
                ]
                if len(d) > 0:
                    geojson = json.loads(d.to_json())
                    return ee.FeatureCollection(geojson).geometry()
            else:
                for feature in self.boundaries.get("features", []):
                    props = feature.get("properties", {})
                    if (props.get("NAME_1", "").lower() == state.lower() and 
                        props.get("NAME_2", "").lower() == district.lower()):
                        return ee.Geometry(feature.get("geometry"))
        except Exception:
            pass
        return None

# Load boundaries safely
BOUNDARY_PATH = "data/india_districts.geojson"
bm = BoundaryManager(BOUNDARY_PATH)
bm.load()

# ---------------------------------------------------------------------------
# Earth Engine Helper Functions (From Colab notebook)
# ---------------------------------------------------------------------------
def mask_s2_clouds(image):
    qa = image.select("QA60")
    mask = qa.lt(1024)
    return image.updateMask(mask)

def compute_all_indices(img):
    B2 = img.select("B2")
    B3 = img.select("B3")
    B4 = img.select("B4")
    B8 = img.select("B8")
    B11 = img.select("B11")
    
    ndvi = B8.subtract(B4).divide(B8.add(B4)).rename("NDVI")
    ndwi = B3.subtract(B8).divide(B3.add(B8)).rename("NDWI")
    
    # EVI
    evi = img.expression(
        "2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)",
        {"NIR": B8, "RED": B4, "BLUE": B2},
    ).rename("EVI")
    
    # SAVI
    savi = img.expression(
        "((NIR - RED) / (NIR + RED + L)) * (1 + L)", 
        {"NIR": B8, "RED": B4, "L": 0.5}
    ).rename("SAVI")
    
    # MSI
    msi = B11.divide(B8).rename("MSI")
    
    # GCI
    gci = B8.divide(B3).subtract(1).rename("GCI")
    
    # CHIS
    chis = (
        ndvi.multiply(WEIGHTS["NDVI"])
        .add(ndwi.multiply(WEIGHTS["NDWI"]))
        .add(evi.multiply(WEIGHTS["EVI"]))
        .add(savi.multiply(WEIGHTS["SAVI"]))
        .add(msi.multiply(WEIGHTS["MSI"]))
        .add(gci.multiply(WEIGHTS["GCI"]))
    ).multiply(100).clamp(0, 100).rename("CHIS")
    
    # Classify CHIS
    class_img = (
        chis.multiply(0)
        .where(chis.gte(80), 4)
        .where(chis.gte(60), 3)
        .where(chis.gte(40), 2)
        .where(chis.gte(20), 1)
        .rename("HealthClass")
    )
    
    return ndvi, ndwi, evi, savi, msi, gci, chis, class_img

# Helper to add GEE layers to Folium
def add_ee_layer(folium_map, ee_image_object, vis_params, name):
    try:
        map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
        folium.raster_layers.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr='Google Earth Engine',
            name=name,
            overlay=True,
            control=True
        ).add_to(folium_map)
    except Exception as e:
        st.error(f"Error adding GEE layer '{name}': {e}")

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="KisanAI - Crop Digital Twin",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Custom CSS for Premium Design & Visual Accents
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main-header {
        font-size: 2.8rem;
        background: linear-gradient(135deg, #1b4d3e, #2e7d32, #00897b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #558b2f;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    
    /* Dashboard Cards */
    .premium-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        border: 1px solid #e8f5e9;
        margin-bottom: 20px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .premium-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
    }
    
    .problem-card {
        border-left: 5px solid #e53935;
        background-color: #ffebee;
    }
    .solution-card {
        border-left: 5px solid #2e7d32;
        background-color: #e8f5e9;
    }
    .difference-card {
        border-left: 5px solid #1e88e5;
        background-color: #e3f2fd;
    }
    .usp-card {
        border-left: 5px solid #f9a825;
        background-color: #fffde7;
    }
    
    .badge-stress {
        background-color: #ffe0b2;
        color: #e65100;
        padding: 6px 14px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 1.1em;
        display: inline-block;
        border: 1px solid #ffb74d;
    }
    
    /* Feature Flow Styles */
    .flow-container {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        margin: 20px 0;
    }
    .flow-node {
        background: #e8f5e9;
        border: 2px solid #2e7d32;
        border-radius: 12px;
        padding: 12px 18px;
        text-align: center;
        font-weight: 600;
        color: #1b4d3e;
        min-width: 120px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin: 10px;
    }
    .flow-arrow {
        color: #2e7d32;
        font-weight: bold;
        font-size: 1.5rem;
    }
    
    /* Stepper/Timeline for Process Flow */
    .timeline-container {
        border-left: 3px solid #81c784;
        padding-left: 20px;
        margin-left: 10px;
    }
    .timeline-item {
        position: relative;
        margin-bottom: 25px;
    }
    .timeline-badge {
        position: absolute;
        left: -31px;
        top: 2px;
        background: #2e7d32;
        color: white;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.7em;
        border: 2px solid white;
    }
    
    /* Wireframe Retro Mockup style */
    .wireframe-outline {
        border: 2px solid #2e7d32;
        background-color: #ffffff;
        border-radius: 12px;
        padding: 25px;
        max-width: 700px;
        margin: 0 auto;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.05);
    }
    .wireframe-section-header {
        font-size: 1.5em;
        color: #1b4d3e;
        border-bottom: 2px solid #a5d6a7;
        margin-bottom: 12px;
        padding-bottom: 4px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Initialize Session State
# ---------------------------------------------------------------------------
if 'location' not in st.session_state:
    st.session_state.location = "Punjab"
if 'district' not in st.session_state:
    st.session_state.district = "Ludhiana"
if 'crop' not in st.session_state:
    st.session_state.crop = "Wheat"
if 'gcp_project_id' not in st.session_state:
    st.session_state.gcp_project_id = ""
if 'gee_initialized' not in st.session_state:
    st.session_state.gee_initialized = False
if 'gee_error' not in st.session_state:
    st.session_state.gee_error = None

# Analysis cache parameters
if 'crop_health' not in st.session_state:
    st.session_state.crop_health = 82.0
if 'water_stress' not in st.session_state:
    st.session_state.water_stress = "MEDIUM"
if 'rainfall_val' not in st.session_state:
    st.session_state.rainfall_val = 18.0
if 'recommendations' not in st.session_state:
    st.session_state.recommendations = ["✓ Irrigate after 2 days", "✓ Nitrogen application advised"]
if 'ts_dates' not in st.session_state:
    st.session_state.ts_dates = [date.today() - timedelta(days=x) for x in range(90, 0, -15)]
if 'ts_means' not in st.session_state:
    st.session_state.ts_means = [58, 62, 70, 75, 80, 82]
if 'class_distribution' not in st.session_state:
    st.session_state.class_distribution = {"Critical": 5, "Stressed": 10, "Moderate": 25, "Healthy": 45, "Excellent": 15}
if 'image_layers' not in st.session_state:
    st.session_state.image_layers = None

# Coordinates for map center of selected state/district
LOCATION_COORDS = {
    "Punjab": {"center": [30.9, 75.85], "district": "Ludhiana"},
    "Haryana": {"center": [28.9, 76.6], "district": "Rohtak"},
    "Uttar Pradesh": {"center": [26.85, 80.94], "district": "Lucknow"},
    "Rajasthan": {"center": [26.9, 75.8], "district": "Jaipur"},
    "Gujarat": {"center": [23.0, 72.57], "district": "Ahmedabad"},
    "Madhya Pradesh": {"center": [23.25, 77.4], "district": "Bhopal"}
}

# ---------------------------------------------------------------------------
# Attempt Earth Engine Initialization (Safe Fallback)
# ---------------------------------------------------------------------------
def try_init_gee(project_id=None):
    if not HAS_EE:
        return False, "earthengine-api library is not installed."
    try:
        if project_id and project_id.strip() != "":
            ee.Initialize(project=project_id.strip())
        else:
            ee.Initialize()
        st.session_state.gee_initialized = True
        st.session_state.gee_error = None
        return True, None
    except Exception as e:
        st.session_state.gee_initialized = False
        st.session_state.gee_error = str(e)
        return False, str(e)

# Run default GEE init on first load
if not st.session_state.gee_initialized and HAS_EE:
    try_init_gee()

# ---------------------------------------------------------------------------
# Sidebar Input Panel
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🌾 KisanAI Controls")
    
    # State selector
    state_list = list(LOCATION_COORDS.keys())
    state = st.selectbox(
        "Location (State)", 
        state_list, 
        index=state_list.index(st.session_state.location) if st.session_state.location in state_list else 0
    )
    st.session_state.location = state
    
    # District selector
    district_default = LOCATION_COORDS[state]["district"]
    district = st.selectbox("District", [district_default], index=0)
    st.session_state.district = district
    
    # Crop selector
    crop_options = ["Wheat", "Rice", "Cotton", "Sugarcane", "Maize", "Pulses"]
    crop = st.selectbox(
        "Crop Select", 
        crop_options,
        index=crop_options.index(st.session_state.crop) if st.session_state.crop in crop_options else 0
    )
    st.session_state.crop = crop
    
    st.markdown("---")
    
    # GEE mode choice
    st.markdown("### ⚙️ Satellite Engine Mode")
    engine_mode = st.radio(
        "Source",
        ["Simulated/Demo Mode", "Real Earth Engine API"],
        index=0 if not st.session_state.gee_initialized else 1,
        disabled=not st.session_state.gee_initialized
    )
    
    col_sd1, col_sd2 = st.columns(2)
    start_date = col_sd1.date_input("Start", date.today() - timedelta(days=90))
    end_date = col_sd2.date_input("End", date.today())
    
    cloud_pct = st.slider("Cloud filter (%)", 0, 100, 20)
    
    run_analysis = st.button("Run Satellite Analysis", type="primary", use_container_width=True)
    
    st.markdown("---")
    
    # Earth Engine Connection Details
    st.markdown("### 🔌 Earth Engine Status")
    if st.session_state.gee_initialized:
        st.success("🟢 Connected to Earth Engine")
    else:
        st.warning("🟡 GEE Offline (Demo Mode)")
        gcp_id = st.text_input("GCP Project ID", value=st.session_state.gcp_project_id, key="gcp_input")
        if st.button("🔗 Connect to GEE"):
            st.session_state.gcp_project_id = gcp_id
            success, err = try_init_gee(gcp_id)
            if success:
                st.success("Connected!")
                st.rerun()
            else:
                st.error(f"Error: {err[:60]}...")
                
    st.markdown("---")
    st.markdown("<div style='text-align: center; color: gray; font-size: 0.8em;'>KisanAI v1.0.0 • ISRO Hackathon</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data Analysis Logic (GEE execution pipeline from your Colab)
# ---------------------------------------------------------------------------
if run_analysis:
    with st.spinner("Processing satellite imagery and computing indices..."):
        coords = LOCATION_COORDS[state]["center"]
        
        if engine_mode == "Real Earth Engine API" and st.session_state.gee_initialized:
            try:
                # 1. Resolve district ROI boundary
                roi = bm.get_district_ee_geometry(state, district)
                if roi is None:
                    roi = ee.Geometry.Point(coords[1], coords[0]).buffer(15000)
                
                # 2. Query Sentinel-2 surface reflectance
                collection = (
                    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                    .filterBounds(roi)
                    .filterDate(str(start_date), str(end_date))
                    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_pct))
                    .map(mask_s2_clouds)
                )
                
                size = collection.size().getInfo()
                if size == 0:
                    st.error("No cloud-free Sentinel-2 images found in date range. Try extending the period.")
                else:
                    image = collection.median().clip(roi)
                    
                    # 3. Compute scientific indices & CHIS
                    ndvi, ndwi, evi, savi, msi, gci, chis, class_img = compute_all_indices(image)
                    
                    # 4. Reduce region to get average metrics
                    mean_chis_val = chis.reduceRegion(
                        ee.Reducer.mean(), roi, 10, maxPixels=1e13, bestEffort=True
                    ).getInfo().get("CHIS")
                    
                    mean_ndwi_val = ndwi.reduceRegion(
                        ee.Reducer.mean(), roi, 10, maxPixels=1e13, bestEffort=True
                    ).getInfo().get("NDWI")
                    
                    hist = class_img.reduceRegion(
                        ee.Reducer.frequencyHistogram(), roi, 10, maxPixels=1e13, bestEffort=True
                    ).getInfo().get("HealthClass", {})
                    
                    # Convert GEE histogram to class labels
                    dist_dict = {"Critical": 0, "Stressed": 0, "Moderate": 0, "Healthy": 0, "Excellent": 0}
                    total_pixels = sum(hist.values()) if hist else 1
                    for k, v in hist.items():
                        idx = int(float(k))
                        if 0 <= idx < len(CLASS_LABELS):
                            dist_dict[CLASS_LABELS[idx]] = round((v / total_pixels) * 100)
                    
                    # 5. Compile time-series composites (15-day composites)
                    ts_dates, ts_means = [], []
                    cur = start_date
                    while cur < end_date:
                        nxt = min(cur + timedelta(days=15), end_date)
                        comp = collection.filterDate(str(cur), str(nxt)).median().clip(roi)
                        
                        # Verify bands are available before computation
                        band_names = comp.bandNames().getInfo()
                        if "B8" in band_names:
                            _, _, _, _, _, _, c_chis, _ = compute_all_indices(comp)
                            val = c_chis.reduceRegion(
                                ee.Reducer.mean(), roi, 20, maxPixels=1e12, bestEffort=True
                            ).getInfo().get("CHIS")
                            if val is not None:
                                ts_dates.append(cur)
                                ts_means.append(round(val))
                        cur = nxt
                        
                    # Calculate dynamic advisories based on GEE outputs
                    stress_val = "LOW"
                    if mean_ndwi_val is not None:
                        # NDWI threshold classification
                        if mean_ndwi_val < 0.15:
                            stress_val = "HIGH"
                        elif mean_ndwi_val < 0.25:
                            stress_val = "MEDIUM"
                            
                    recs_list = []
                    if mean_chis_val is not None and mean_chis_val < 70:
                        recs_list.append("✓ Nitrogen application advised")
                    else:
                        recs_list.append("✓ Crop vigor healthy; continue normal management")
                        
                    if stress_val in ["MEDIUM", "HIGH"]:
                        recs_list.append("✓ Irrigate after 2 days")
                    else:
                        recs_list.append("✓ Moisture levels adequate")
                        
                    # Save results in session state
                    st.session_state.crop_health = mean_chis_val if mean_chis_val is not None else 82.0
                    st.session_state.water_stress = stress_val
                    st.session_state.recommendations = recs_list
                    st.session_state.ts_dates = ts_dates
                    st.session_state.ts_means = ts_means
                    st.session_state.class_distribution = dist_dict
                    st.session_state.image_layers = {
                        "rgb": image,
                        "ndvi": ndvi,
                        "chis": chis,
                        "class": class_img
                    }
                    st.success("Earth Engine computation completed successfully!")
            except Exception as ex:
                st.error(f"Failed GEE processing pipeline: {ex}. Reverting to simulated mode.")
                
        else:
            # Seed based simulated analytics
            np.random.seed(hash(state + crop) % 2**32)
            st.session_state.crop_health = round(float(np.random.uniform(72, 88)), 1)
            st.session_state.water_stress = np.random.choice(["LOW", "MEDIUM", "HIGH"], p=[0.2, 0.6, 0.2])
            
            rec_options = {
                "LOW": ["✓ Moisture levels adequate", "✓ Monitor crop density profile"],
                "MEDIUM": ["✓ Irrigate after 2 days", "✓ Nitrogen application advised"],
                "HIGH": ["✓ Irrigate immediately", "✓ Water deficit critical, avoid fertilizer top-dressing"]
            }
            st.session_state.recommendations = rec_options[st.session_state.water_stress]
            st.session_state.rainfall_val = round(float(np.random.uniform(8, 28)), 1)
            
            # Simulate historical timeline
            st.session_state.ts_dates = [date.today() - timedelta(days=x) for x in range(90, 0, -15)]
            base_trend = st.session_state.crop_health - 15
            st.session_state.ts_means = [round(base_trend + (idx * 3) + np.random.uniform(-4, 4)) for idx in range(6)]
            
            # Simulate histogram
            st.session_state.class_distribution = {
                "Critical": 2, "Stressed": 8, "Moderate": 25, "Healthy": 48, "Excellent": 17
            }
            st.session_state.image_layers = None
            st.success("Demo Mode simulation calculated successfully!")

# Main Title Header
st.markdown("<h1 class='main-header'>KISAN AI</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Satellite-Driven Crop Digital Twin for Intelligent Crop Monitoring and Explainable Irrigation Advisory</p>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main Page Navigation tabs
# ---------------------------------------------------------------------------
tab_wireframe, tab_charts, tab_features, tab_pipeline, tab_architecture, tab_tech_costs = st.tabs([
    "📊 Live Dashboard Wireframe",
    "📈 Analytics Charts",
    "✨ Opportunity & Features",
    "⚙️ Process Flow Pipeline",
    "🏗️ System Architecture",
    "🛠️ Technology & Cost Analysis"
])

# ---------------------------------------------------------------------------
# TAB 1: Live Dashboard Wireframe
# ---------------------------------------------------------------------------
with tab_wireframe:
    
    # We use textwrap.dedent and align to the left to prevent markdown from rendering HTML as a code block.
    # Note: Indenting HTML inside st.markdown multi-line strings triggers markdown code-block rendering.
    html_markup = textwrap.dedent(f"""
    <div class="wireframe-outline">
    <div style="text-align: center; border-bottom: 2px solid #2e7d32; padding-bottom:10px; margin-bottom:20px;">
    <h2 style="color: #1b4d3e; margin:0; font-weight:700; letter-spacing: 2px;">KISAN AI</h2>
    </div>
    <div class="wireframe-section-header">📍 Location & Crop</div>
    <div style="display: flex; justify-content: space-between; padding: 10px 0; font-size:1.2em;">
    <div><strong>Location:</strong> {state} ({district})</div>
    <div><strong>Crop:</strong> {crop}</div>
    </div>
    <div class="wireframe-section-header">🌱 Crop Health</div>
    <div style="padding: 10px 0;">
    <div style="font-family: monospace; font-size: 1.3rem; font-weight: bold; color: #2e7d32; margin-bottom:8px;">
    █████████░ {st.session_state.crop_health:.0f}%
    </div>
    </div>
    <div class="wireframe-section-header">💧 Water Stress</div>
    <div style="padding: 10px 0;">
    <span class="badge-stress">{st.session_state.water_stress}</span>
    </div>
    <div class="wireframe-section-header">🌦️ Weather Forecast</div>
    <div style="padding: 10px 0; font-size: 1.15em;">
    Rainfall Next 7 Days: <strong>{st.session_state.rainfall_val} mm</strong>
    </div>
    <div class="wireframe-section-header">📋 Recommendations</div>
    <div style="padding: 10px 0; font-size: 1.15em; line-height: 1.8;">
    """)
    
    st.markdown(html_markup, unsafe_allow_html=True)
    
    # Recommendations render loop (safely styled)
    for rec in st.session_state.recommendations:
        st.markdown(f"<div style='color: #2e7d32; font-weight: 500; font-size:1.15em;'>{rec}</div>", unsafe_allow_html=True)
        
    html_markup_bottom = textwrap.dedent("""
    </div>
    <div class="wireframe-section-header">🗺️ Satellite Map</div>
    <div style="margin-top: 15px;">
    """)
    st.markdown(html_markup_bottom, unsafe_allow_html=True)
    
    # Embed Map inside the wireframe view
    coords = LOCATION_COORDS[state]["center"]
    
    if engine_mode == "Real Earth Engine API" and st.session_state.gee_initialized and st.session_state.image_layers is not None:
        try:
            m = folium.Map(location=coords, zoom_start=12)
            folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri Satellite',
                name='Esri Satellite',
                overlay=False
            ).add_to(m)
            
            layers = st.session_state.image_layers
            add_ee_layer(m, layers["rgb"], {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}, "Sentinel RGB")
            add_ee_layer(m, layers["ndvi"], {"min": -1, "max": 1, "palette": ["gray", "blue", "green"]}, "NDVI Map")
            add_ee_layer(m, layers["chis"], {"min": 0, "max": 100, "palette": ["red", "yellow", "green"]}, "CHIS Health index")
            add_ee_layer(m, layers["class"], {"min": 0, "max": 4, "palette": CLASS_VIS_COLORS}, "Health Classes")
            folium.LayerControl().add_to(m)
            
            st_folium(m, height=350, use_container_width=True)
        except Exception as e:
            st.error(f"Map rendering error: {e}. Falling back to default.")
    else:
        # Fallback to simulated mapping directly
        folium_map = folium.Map(location=coords, zoom_start=13)
        
        poly_coords = [
            [coords[0] - 0.004, coords[1] - 0.004],
            [coords[0] + 0.004, coords[1] - 0.004],
            [coords[0] + 0.004, coords[1] + 0.004],
            [coords[0] - 0.004, coords[1] + 0.004],
            [coords[0] - 0.004, coords[1] - 0.004]
        ]
        
        status_color = "#2e7d32" if st.session_state.crop_health > 75 else "#ffeb3b" if st.session_state.crop_health > 50 else "#f44336"
        
        folium.Polygon(
            locations=poly_coords,
            popup=f"{district} Field boundary<br>Crop: {crop}<br>Health: {st.session_state.crop_health:.0f}%",
            color=status_color,
            fill=True,
            fill_color=status_color,
            fill_opacity=0.6
        ).add_to(folium_map)
        
        folium.TileLayer('OpenStreetMap', name='Street Map').add_to(folium_map)
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri Satellite',
            name='Satellite',
            overlay=True
        ).add_to(folium_map)
        folium.LayerControl().add_to(folium_map)
        
        st_folium(folium_map, height=350, use_container_width=True)
        
    st.markdown("</div></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TAB 2: Analytics Charts
# ---------------------------------------------------------------------------
with tab_charts:
    st.markdown("### 📊 Crop Vigor & Classification Trends")
    
    col_chart_a, col_chart_b = st.columns(2)
    
    with col_chart_a:
        # Time series of CHIS index
        fig_ts = go.Figure()
        fig_ts.add_trace(go.Scatter(
            x=st.session_state.ts_dates,
            y=st.session_state.ts_means,
            mode='lines+markers',
            name='Crop Vigor (CHIS)',
            line=dict(color='#2e7d32', width=3),
            marker=dict(size=6)
        ))
        fig_ts.update_layout(
            title="Temporal Crop Health Index Score (CHIS) Trend",
            xaxis_title="Timeline",
            yaxis_title="CHIS (0-100%)",
            yaxis=dict(range=[0, 100]),
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_ts, use_container_width=True)
        
    with col_chart_b:
        # Histogram distribution
        dist = st.session_state.class_distribution
        fig_dist = go.Figure(go.Bar(
            x=list(dist.keys()),
            y=list(dist.values()),
            marker_color=CLASS_VIS_COLORS
        ))
        fig_dist.update_layout(
            title="Acreage Classification Distribution (%)",
            xaxis_title="Vigor Class",
            yaxis_title="Percentage Coverage",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_dist, use_container_width=True)

# ---------------------------------------------------------------------------
# TAB 3: Opportunity & Features
# ---------------------------------------------------------------------------
with tab_features:
    col_opp_a, col_opp_b = st.columns(2)
    
    with col_opp_a:
        html_opp_a = textwrap.dedent("""
        <div class="premium-card problem-card" style="height: 380px;">
            <h3 style="color:#c62828; margin-top:0;">⚠️ Opportunity / Problem Statement</h3>
            <p>Small and marginal farmers often make crop and irrigation decisions based on experience rather than data. Limited access to satellite intelligence, weather forecasts, soil information and expert guidance leads to:</p>
            <ul>
                <li>Incorrect crop selection</li>
                <li>Excess irrigation</li>
                <li>Delayed stress detection</li>
                <li>Reduced crop yield</li>
                <li>Increased production costs</li>
            </ul>
        </div>
        """)
        st.markdown(html_opp_a, unsafe_allow_html=True)
        
    with col_opp_b:
        html_opp_b = textwrap.dedent("""
        <div class="premium-card solution-card" style="height: 380px;">
            <h3 style="color:#2e7d32; margin-top:0;">💡 Proposed Solution</h3>
            <p>KisanAI integrates multi-source satellite imagery, weather forecasts, soil information and AI models to continuously monitor crop conditions and generate explainable irrigation and crop management advisories.</p>
            <p><strong>Value Proposition:</strong> Rather than simply recommending a crop, KisanAI continuously monitors crop health throughout the growing season and provides proactive recommendations before visible damage occurs.</p>
        </div>
        """)
        st.markdown(html_opp_b, unsafe_allow_html=True)

    col_diff_a, col_diff_b = st.columns(2)
    
    with col_diff_a:
        html_diff_a = textwrap.dedent("""
        <div class="premium-card difference-card" style="height: 380px;">
            <h3 style="color:#1565c0; margin-top:0;">🔄 How is it Different?</h3>
            <p>Unlike existing farmer advisory systems that rely primarily on weather forecasts or static crop recommendation models, KisanAI introduces a <strong>Crop Digital Twin</strong> approach.</p>
            <p>Our solution combines:</p>
            <ul>
                <li>Multi-temporal satellite imagery</li>
                <li>Optical + future SAR compatibility</li>
                <li>Growth-stage aware crop monitoring</li>
                <li>Moisture stress prediction</li>
                <li>Explainable AI recommendations</li>
                <li>Multilingual advisory delivery</li>
            </ul>
        </div>
        """)
        st.markdown(html_diff_a, unsafe_allow_html=True)
        
    with col_diff_b:
        html_diff_b = textwrap.dedent("""
        <div class="premium-card usp-card" style="height: 380px;">
            <h3 style="color:#f57f17; margin-top:0;">🏆 USP (Unique Selling Proposition)</h3>
            <ul style="list-style-type: none; padding-left: 0;">
                <li style="margin-bottom: 8px;">✔️ Satellite-driven monitoring instead of manual inspection</li>
                <li style="margin-bottom: 8px;">✔️ Growth-stage aware irrigation advisory</li>
                <li style="margin-bottom: 8px;">✔️ Explainable AI recommendations</li>
                <li style="margin-bottom: 8px;">✔️ Near real-time monitoring</li>
                <li style="margin-bottom: 8px;">✔️ Modular architecture for nationwide scaling</li>
            </ul>
        </div>
        """)
        st.markdown(html_diff_b, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ⚙️ System Features")
    
    col_feat_a, col_feat_b = st.columns(2)
    
    with col_feat_a:
        html_feat_a = textwrap.dedent("""
        <div class="premium-card solution-card">
            <h4 style="margin-top:0; color:#1b4d3e;">✔️ Core Features</h4>
            <p><strong>Satellite Crop Mapping:</strong> Automatic crop identification & Multi-season crop monitoring</p>
            <p><strong>Crop Health Monitoring:</strong> NDVI-based vegetation monitoring, Moisture stress detection, crop health scoring</p>
            <p><strong>Weather Intelligence:</strong> Rainfall forecasting, Temperature monitoring, Water deficit estimation</p>
            <p><strong>AI Advisory Engine:</strong> Irrigation scheduling, Water stress alerts, Crop management suggestions</p>
            <p><strong>Explainable AI:</strong> Confidence score, contributing factors, satellite evidence</p>
            <p><strong>Farmer Dashboard:</strong> Crop health map, Time-series graphs, Stress alerts, Advisory history</p>
        </div>
        """)
        st.markdown(html_feat_a, unsafe_allow_html=True)
        
    with col_feat_b:
        html_feat_b = textwrap.dedent("""
        <div class="premium-card usp-card">
            <h4 style="margin-top:0; color:#e65100;">🚀 Future Features</h4>
            <ul>
                <li>Voice assistant integration</li>
                <li>WhatsApp/SMS alerts</li>
                <li>Disease detection using leaf images</li>
                <li>Ground sensor integration</li>
            </ul>
        </div>
        """)
        st.markdown(html_feat_b, unsafe_allow_html=True)

    st.markdown("### 📊 Feature Diagram")
    html_feat_flow = textwrap.dedent("""
    <div class="flow-container">
        <div class="flow-node">Satellite Data 🛰️</div>
        <div class="flow-arrow">➔</div>
        <div class="flow-node">Crop Mapping 🗺️</div>
        <div class="flow-arrow">➔</div>
        <div class="flow-node">Stress Detection 💧</div>
        <div class="flow-arrow">➔</div>
        <div class="flow-node">Weather Analysis 🌦️</div>
        <div class="flow-arrow">➔</div>
        <div class="flow-node">AI Advisory 🤖</div>
        <div class="flow-arrow">➔</div>
        <div class="flow-node">Farmer Dashboard 📱</div>
    </div>
    """)
    st.markdown(html_feat_flow, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TAB 4: Process Flow Pipeline
# ---------------------------------------------------------------------------
with tab_pipeline:
    st.markdown("### ⚙️ End-to-End Process Flow Pipeline")
    st.write("Below is the structural step-by-step data extraction pipeline:")
    
    html_pipeline = textwrap.dedent("""
    <div class="timeline-container">
        <div class="timeline-item">
            <div class="timeline-badge">1</div>
            <strong>Satellite Images (Sentinel-2)</strong><br>
            <span style='color:gray;'>Acquire Sentinel-2 optical imagery bands.</span>
        </div>
        <div class="timeline-item">
            <div class="timeline-badge">2</div>
            <strong>Image Preprocessing</strong><br>
            <span style='color:gray;'>Cloud masking and median composite creation.</span>
        </div>
        <div class="timeline-item">
            <div class="timeline-badge">3</div>
            <strong>Feature Extraction (NDVI, NDWI, EVI)</strong><br>
            <span style='color:gray;'>Calculate key spectral indices from raw bands.</span>
        </div>
        <div class="timeline-item">
            <div class="timeline-badge">4</div>
            <strong>Crop Classification</strong><br>
            <span style='color:gray;'>Identify crop types using temporal signatures.</span>
        </div>
        <div class="timeline-item">
            <div class="timeline-badge">5</div>
            <strong>Crop Health Analysis</strong><br>
            <span style='color:gray;'>Score crop vigor index values.</span>
        </div>
        <div class="timeline-item">
            <div class="timeline-badge">6</div>
            <strong>Weather Integration</strong><br>
            <span style='color:gray;'>Fetch rainfall forecasts and temperatures.</span>
        </div>
        <div class="timeline-item">
            <div class="timeline-badge">7</div>
            <strong>Moisture Stress Detection</strong><br>
            <span style='color:gray;'>Correlate index data for moisture indicators.</span>
        </div>
        <div class="timeline-item">
            <div class="timeline-badge">8</div>
            <strong>Water Deficit Estimation</strong><br>
            <span style='color:gray;'>Model soil moisture depletion rates.</span>
        </div>
        <div class="timeline-item">
            <div class="timeline-badge">9</div>
            <strong>AI Recommendation Engine</strong><br>
            <span style='color:gray;'>Formulate crop advisories and irrigation schedulers.</span>
        </div>
        <div class="timeline-item">
            <div class="timeline-badge">10</div>
            <strong>Farmer Dashboard / Alerts</strong><br>
            <span style='color:gray;'>Output visual widgets, Voice messages, or SMS alerts.</span>
        </div>
    </div>
    """)
    st.markdown(html_pipeline, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TAB 5: System Architecture
# ---------------------------------------------------------------------------
with tab_architecture:
    st.markdown("### 🏗️ System Architecture Flowchart")
    
    html_arch_box = textwrap.dedent("""
    <div class='premium-card solution-card'>
        <div style="font-family: monospace; white-space: pre-wrap; font-size: 0.95rem; line-height: 1.3;">
                  Farmer / User Interface
                     │
       Dashboard / SMS Alert / Voice Call
                     │
    ──────────────────────────────────────────
                 Advisory Engine
    ──────────────────────────────────────────
            │                        │
            ▼                        ▼
       Crop Intelligence     Weather Engine
            │                        │
            └───────────┬────────────┘
                        │
                        ▼
                AI Decision Engine
                        │
    ──────────────────────────────────────────
                  Data Layers
     [Sentinel-2]   [NASA POWER]   [SoilGrids]
    ──────────────────────────────────────────
                        │
                        ▼
                     Outputs
     [Crop Map] [Stress Map] [Irrigation Guide]
        </div>
    </div>
    """)
    st.markdown(html_arch_box, unsafe_allow_html=True)
    
    try:
        st.markdown("""
        ```mermaid
        graph TD
            U[Farmer / User] <--> DB[Streamlit Dashboard / SMS]
            DB <--> AE[Advisory Engine]
            AE --> CI[Crop Intelligence Engine]
            AE --> WE[Weather Engine]
            CI & WE --> ADE[AI Decision Engine]
            
            subgraph Data Layer Inputs
                ADE --> GEE[Sentinel-2 / Sentinel-1 SAR]
                ADE --> WAPI[NASA POWER / OpenWeather API]
                ADE --> SDB[SoilGrids Database]
            end
            
            subgraph Project Outputs
                AE --> CM[Crop Map]
                AE --> SM[Stress Map]
                AE --> IA[Irrigation Advisory]
                AE --> HT[Health Timeline]
            end
            
            style U fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
            style DB fill:#e3f2fd,stroke:#1e88e5,stroke-width:2px
            style AE fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
            style ADE fill:#ffccbc,stroke:#d84315,stroke-width:2px
        ```
        """, unsafe_allow_html=True)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# TAB 6: Technology & Cost Analysis
# ---------------------------------------------------------------------------
with tab_tech_costs:
    col_tech, col_costs = st.columns(2)
    
    with col_tech:
        st.markdown("### 🛠️ Technology Stack")
        tech_data = {
            "Component": [
                "Programming Language",
                "Frontend Dashboard",
                "Satellite Processing",
                "GIS Mapping Libraries",
                "Machine Learning",
                "Future Predictive Models",
                "Visualization Engine",
                "Explainability API",
                "Weather Data Source",
                "Satellite Data Band",
                "Soil Parameter Source",
                "Deployment Engine"
            ],
            "Technology Choice": [
                "Python",
                "Streamlit",
                "Google Earth Engine",
                "GeoPandas, Rasterio, Folium",
                "Scikit-learn",
                "XGBoost, LSTM",
                "Plotly, Matplotlib",
                "SHAP (Shapley Explanations)",
                "NASA POWER / OpenWeather",
                "Sentinel-2",
                "SoilGrids",
                "Streamlit Cloud / Docker"
            ]
        }
        st.table(pd.DataFrame(tech_data))
        
    with col_costs:
        st.markdown("### 💰 Prototype Cost & Scaling")
        html_cost_table = textwrap.dedent("""
        <table style='width:100%; border-collapse:collapse; margin-bottom: 20px;'>
            <tr style='border-bottom:1px solid #ccc; padding:8px 0;'>
                <th style='text-align:left; padding:8px;'>Item</th>
                <th style='text-align:right; padding:8px;'>Cost (INR)</th>
            </tr>
            <tr>
                <td style='padding:8px;'>Google Earth Engine API</td>
                <td style='text-align:right; padding:8px; color:green; font-weight:bold;'>₹0 (Research)</td>
            </tr>
            <tr>
                <td style='padding:8px;'>Python & Streamlit</td>
                <td style='text-align:right; padding:8px; color:green; font-weight:bold;'>₹0</td>
            </tr>
            <tr>
                <td style='padding:8px;'>Sentinel-2 Satellite Data</td>
                <td style='text-align:right; padding:8px; color:green; font-weight:bold;'>₹0</td>
            </tr>
            <tr>
                <td style='padding:8px;'>NASA POWER Weather API</td>
                <td style='text-align:right; padding:8px; color:green; font-weight:bold;'>₹0</td>
            </tr>
            <tr>
                <td style='padding:8px;'>SoilGrids Database</td>
                <td style='text-align:right; padding:8px; color:green; font-weight:bold;'>₹0</td>
            </tr>
            <tr style='border-top:2px solid #2e7d32; font-weight:bold;'>
                <td style='padding:8px;'>Total Prototype Cost</td>
                <td style='text-align:right; padding:8px; color:#2e7d32;'>≈ ₹0–₹2,000</td>
            </tr>
        </table>
        
        <h4>🚀 Production Deployment (Future)</h4>
        <ul>
            <li>☁️ <strong>Cloud hosting:</strong> Scalable server instances (₹2,500/month).</li>
            <li>💬 <strong>SMS Gateway:</strong> Alert delivery system (₹0.15/SMS).</li>
            <li>🗄️ <strong>Database:</strong> Dedicated spatial server (₹1,500/month).</li>
            <li>📱 <strong>Mobile Application:</strong> Flutter deployment.</li>
            <li>🔌 <strong>Ground IoT sensors:</strong> Optional node calibrations.</li>
        </ul>
        """)
        st.markdown(html_cost_table, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown(
    f"<p style='text-align: center; color: gray; font-size:0.9em;'>"
    f"KisanAI • Smart Water, Crop & Advisory System • Date: {datetime.now().strftime('%Y-%m-%d')}"
    f"</p>",
    unsafe_allow_html=True
)