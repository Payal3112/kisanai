import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import json

# Page configuration
st.set_page_config(
    page_title="KisanAI - Satellite-Driven Crop Digital Twin",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2c3e50;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #3498db;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f8f9ff;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #3498db;
        margin: 0.5rem 0;
    }
    .recommendation-box {
        background-color: #e8f5e8;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #27ae60;
        margin: 1rem 0;
    }
    .alert-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
    .stButton>button {
        width: 100%;
        background-color: #3498db;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 5px;
    }
    .stButton>button:hover {
        background-color: #2980b9;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'location' not in st.session_state:
    st.session_state.location = "Punjab, India"
if 'crop' not in st.session_state:
    st.session_state.crop = "Wheat"
if 'last_updated' not in st.session_state:
    st.session_state.last_updated = datetime.now()

# Sidebar for inputs
with st.sidebar:
    st.markdown("<h2>🌾 KisanAI Control Panel</h2>", unsafe_allow_html=True)

    # Location selector
    location_options = [
        "Punjab, India", "Haryana, India", "Uttar Pradesh, India",
        "Madhya Pradesh, India", "Rajasthan, India", "Gujarat, India"
    ]
    st.session_state.location = st.selectbox(
        "Select Location",
        location_options,
        index=location_options.index(st.session_state.location)
    )

    # Crop selector
    crop_options = ["Wheat", "Rice", "Cotton", "Sugarcane", "Maize", "Pulses"]
    st.session_state.crop = st.selectbox(
        "Select Crop",
        crop_options,
        index=crop_options.index(st.session_state.crop)
    )

    # Date range selector
    st.markdown("### 📅 Analysis Period")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    date_range = st.date_input(
        "Select Date Range",
        value=(start_date, end_date),
        max_value=end_date
    )

    # Refresh button
    if st.button("🔄 Refresh Data"):
        st.session_state.last_updated = datetime.now()
        st.rerun()

    st.markdown(f"*Last updated: {st.session_state.last_updated.strftime('%Y-%m-%d*")

# Main header
st.markdown("<h1 class='main-header'>KisanAI</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #7f8c8d;'>Satellite-Driven Crop Digital Twin for Intelligent Crop Monitoring</p>", unsafe_allow_html=True)

# Load or generate mock data
@st.cache_data
def generate_mock_data(location, crop, days=90):
    """Generate mock satellite and weather data for demonstration"""
    np.random.seed(hash(location + crop) % 2**32)

    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # Generate realistic NDVI values (0.2 to 0.8 range for crops)
    base_ndvi = 0.5 if crop in ["Wheat", "Rice"] else 0.4
    seasonal_pattern = 0.2 * np.sin(2 * np.pi * np.arange(days) / days)
    noise = np.random.normal(0, 0.05, days)
    ndvi_values = np.clip(base_ndvi + seasonal_pattern + noise, 0.2, 0.8)

    # Generate NDWI (water index) - inversely related to water stress
    base_ndwi = 0.3
    water_stress_factor = np.random.beta(2, 5, days)  # Mostly low stress
    ndwi_values = np.clip(base_ndwi - 0.15 * water_stress_factor + np.random.normal(0, 0.03, days), 0.1, 0.5)

    # Generate EVI (enhanced vegetation index)
    evi_values = np.clip(ndvi_values * 1.2 + np.random.normal(0, 0.02, days), 0.1, 0.9)

    # Weather data
    rainfall = np.maximum(0, np.random.gamma(2, 2, days))  # mm/day
    temperature = 20 + 10 * np.sin(2 * np.pi * np.arange(days) / 365) + np.random.normal(0, 3, days)  # Celsius

    # Calculate derived metrics
    crop_health_score = np.clip((ndvi_values - 0.2) / 0.6 * 100, 0, 100)  # Normalize to 0-100
    water_stress_level = np.clip((0.4 - ndwi_values) / 0.3 * 100, 0, 100)  # Inverse of NDWI
    water_deficit = np.maximum(0, (5 - rainfall.cumsum() / 30) * 10)  # Simplified deficit calculation

    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'NDVI': ndvi_values,
        'NDWI': ndwi_values,
        'EVI': evi_values,
        'rainfall': rainfall,
        'temperature': temperature,
        'crop_health_score': crop_health_score,
        'water_stress_level': water_stress_level,
        'water_deficit_mm': water_deficit
    })

    return df

# Get data
df = generate_mock_data(st.session_state.location, st.session_state.crop)

# Main dashboard metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    latest_health = df['crop_health_score'].iloc[-1]
    health_delta = df['crop_health_score'].iloc[-1] - df['crop_health_score'].iloc[-7]
    st.metric(
        label="🌱 Crop Health Score",
        value=f"{latest_health:.0f}%",
        delta=f"{health_delta:+.1f}%" if len(df) >= 7 else None
    )

with col2:
    latest_stress = df['water_stress_level'].iloc[-1]
    stress_delta = df['water_stress_level'].iloc[-1] - df['water_stress_level'].iloc[-7]
    stress_label = "LOW" if latest_stress < 30 else "MEDIUM" if latest_stress < 60 else "HIGH"
    st.metric(
        label="💧 Water Stress Level",
        value=stress_label,
        delta=f"{stress_delta:+.1f}%" if len(df) >= 7 else None
    )

with col3:
    latest_rainfall = df['rainfall'].iloc[-7:].sum()  # Weekly rainfall
    st.metric(
        label="🌧️ Rainfall (Last 7 Days)",
        value=f"{latest_rainfall:.1f} mm",
        delta=None
    )

with col4:
    latest_temp = df['temperature'].iloc[-1]
    temp_delta = df['temperature'].iloc[-1] - df['temperature'].iloc[-7]
    st.metric(
        label="🌡️ Temperature",
        value=f"{latest_temp:.1f}°C",
        delta=f"{temp_delta:+.1f}°C" if len(df) >= 7 else None
    )

# Create tabs for different views
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🗺️ Satellite Map", "🤖 AI Advisory", "📈 Historical Trends"])

with tab1:
    st.markdown("<h2 class='sub-header'>Field Overview</h2>", unsafe_allow_html=True)

    # Two columns for charts and recommendations
    col_chart, col_advice = st.columns([2, 1])

    with col_chart:
        # Crop health trend
        fig_health = go.Figure()
        fig_health.add_trace(go.Scatter(
            x=df['date'],
            y=df['crop_health_score'],
            mode='lines',
            name='Crop Health Score',
            line=dict(color='#27ae60', width=3)
        ))
        fig_health.update_layout(
            title="Crop Health Trend (NDVI-based)",
            xaxis_title="Date",
            yaxis_title="Health Score (%)",
            yaxis=dict(range=[0, 100]),
            height=300
        )
        st.plotly_chart(fig_health, use_container_width=True)

        # Water stress and rainfall
        fig_water = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Water Stress Level', 'Daily Rainfall'),
            vertical_spacing=0.1
        )

        fig_water.add_trace(
            go.Scatter(x=df['date'], y=df['water_stress_level'],
                      mode='lines', name='Water Stress',
                      line=dict(color='#e74c3c', width=2)),
            row=1, col=1
        )

        fig_water.add_trace(
            go.Bar(x=df['date'], y=df['rainfall'],
                   name='Rainfall', marker_color='#3498db'),
            row=2, col=1
        )

        fig_water.update_layout(height=400, showlegend=False)
        fig_water.update_yaxes(title_text="Stress Level (%)", row=1, col=1)
        fig_water.update_yaxes(title_text="Rainfall (mm)", row=2, col=1)
        st.plotly_chart(fig_water, use_container_width=True)

    with col_advice:
        # Recommendations section
        st.markdown("<h3>🤖 AI Recommendations</h3>", unsafe_allow_html=True)

        # Determine recommendations based on latest data
        latest = df.iloc[-1]
        recommendations = []

        if latest['crop_health_score'] < 70:
            recommendations.append({
                'action': 'Consider foliar nutrient application',
                'reason': 'Crop health score below optimal threshold',
                'confidence': 0.85,
                'evidence': f'NDVI: {latest["NDVI"]:.3f} (threshold: 0.5)'
            })

        if latest['water_stress_level'] > 50:
            recommendations.append({
                'action': 'Irrigate after 2 days',
                'reason': 'Moderate to high water stress detected',
                'confidence': 0.92,
                'evidence': f'NDWI: {latest["NDWI"]:.3f} (stress indicator)'
            })
        elif latest['water_deficit_mm'] > 10:
            recommendations.append({
                'action': 'Schedule irrigation for 15-20mm water application',
                'reason': f'Estimated water deficit: {latest["water_deficit_mm"]:.1f}mm',
                'confidence': 0.88,
                'evidence': f'Cumulative deficit: {latest["water_deficit_mm"]:.1f}mm'
            })

        if latest['temperature'] > 35:
            recommendations.append({
                'action': 'Monitor for heat stress signs',
                'reason': 'Temperature exceeding crop-specific threshold',
                'confidence': 0.78,
                'evidence': f'Temperature: {latest["temperature"]:.1f}°C'
            })

        # Default recommendations if none triggered
        if not recommendations:
            recommendations = [
                {
                    'action': 'Continue current irrigation schedule',
                    'reason': 'Crop health and water status within normal ranges',
                    'confidence': 0.80,
                    'evidence': f'NDVI: {latest["NDVI"]:.3f}, NDWI: {latest["NDWI"]:.3f}'
                },
                {
                    'action': 'Schedule next field inspection in 3 days',
                    'reason': 'Routine monitoring recommended',
                    'confidence': 0.75,
                    'evidence': 'Standard advisory interval'
                }
            ]

        # Display recommendations
        for i, rec in enumerate(recommendations):
            confidence_color = "#27ae60" if rec['confidence'] > 0.85 else "#f39c12" if rec['confidence'] > 0.7 else "#e74c3c"
            st.markdown(f"""
            <div class="recommendation-box">
                <strong>✓ {rec['action']}</strong><br>
                <small>{rec['reason']}</small><br>
                <small>Confidence: <span style='color: {confidence_color}'>{rec['confidence']*100:.0f}%</span></small><br>
                <small>Evidence: {rec['evidence']}</small>
            </div>
            """, unsafe_allow_html=True)

        # Explainable AI section
        st.markdown("<h4>🔍 Explainable AI Factors</h4>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="metric-card">
            <strong>Primary Indicators:</strong><br>
            • NDVI (Vegetation Health): {latest['NDVI']:.3f} <br>
            • NDWI (Water Content): {latest['NDWI']:.3f}<br>
            • Temperature Stress: {latest['temperature']:.1f}°C<br>
            • 7-day Rainfall: {df['rainfall'].iloc[-7:].sum():.1f}mm
        </div>
        """, unsafe_allow_html=True)

with tab2:
    st.markdown("<h2 class='sub-header'>Satellite Imagery & NDVI Map</h2>", unsafe_allow_html=True)

    # Create a mock map centered on India (adjust for real location)
    m = folium.Map(location=[28.6139, 77.2090], zoom_start=5)  # Delhi coordinates as center

    # Add some mock field polygons with NDVI values
    import random
    field_centers = [
        [28.6, 77.2], [28.7, 77.3], [28.5, 77.1], [28.6, 77.2], [28.7, 77.3], [28.5, 77.1], [28.65, 77.25]
    ]

    for i, center in enumerate(field_centers):
        # Generate mock NDVI value for this field
        field_ndvi = 0.3 + 0.4 * random.random()  # Between 0.3 and 0.7
        color = f'#{int(255*(1-field_ndvi)):02x}{int(255*field_ndvi):02x}00'  # Red to green gradient

        folium.CircleMarker(
            location=center,
            radius=8,
            popup=f"Field {i+1}<br>NDVI: {field_ndvi:.3f}<br>Health: {field_ndvi*100:.0f}%",
            color=color,
            fill=True,
            fillColor=color
        ).add_to(m)

    # Add tile layers
    folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)

    folium.LayerControl().add_to(m)

    # Display the map
    st_data = st_folium(m, width=700, height=500)

    # Map legend
    st.markdown("""
    <div style='background-color: #f8f9f9; padding: 1rem; border-radius: 10px; margin-top: 1rem;'>
        <h4>NDVI Legend</h4>
        <div style='display: flex; align-items: center; margin: 0.5rem 0;'>
            <div style='width: 20px; height: 20px; background-color: #ff0000; margin-right: 0.5rem;'></div>
            <span>Low Vegetation (NDVI < 0.3)</span>
        </div>
        <div style='display: flex; align-items: center; margin: 0.5rem 0;'>
            <div style='width: 20px; height: 20px; background-color: #ffff00; margin-right: 0.5rem;'></div>
            <span>Moderate Vegetation (NDVI 0.3-0.6)</span>
        </div>
        <div style='display: flex; align-items: center; margin: 0.5rem 0;'>
            <div style='width: 20px; height: 20px; background-color: #00ff00; margin-right: 0.5rem;'></div>
            <span>High Vegetation (NDVI > 0.6)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with tab3:
    st.markdown("<h2 class='sub-header'>AI Advisory Engine</h2>", unsafe_allow_html=True)

    # Detailed advisory explanation
    col_explain, col_details = st.columns([1, 1])

    with col_explain:
        st.markdown("### How Recommendations Are Generated")
        st.markdown("""
        Our AI advisory engine uses a multi-layered approach:

        1. **Data Fusion**: Combines satellite indices (NDVI, NDWI, EVI) with weather forecasts
        2. **Threshold Analysis**: Compares values against crop-specific optimal ranges
        3. **Trend Analysis**: Examines temporal patterns to predict future conditions
        4. **Risk Assessment**: Evaluates potential yield impact of detected issues
        5. **Recommendation Generation**: Creates actionable advice with confidence scores
        """)

        # Show feature importance
        st.markdown("### Feature Importance for Today's Advisory")
        features = ['NDVI (Vegetation Health)', 'NDWI (Water Stress)', 'Temperature', 'Rainfall Forecast', 'Soil Moisture Estimate']
        importance = [0.35, 0.25, 0.15, 0.15, 0.10]  # Mock importance scores

        fig_importance = go.Figure(go.Bar(
            x=importance,
            y=features,
            orientation='h',
            marker_color='#3498db'
        ))
        fig_importance.update_layout(
            title="Relative Contribution to Today's Recommendation",
            xaxis_title="Importance Score",
            height=300
        )
        st.plotly_chart(fig_importance, use_container_width=True)

    with col_details:
        st.markdown("### 📋 Detailed Advisory Report")

        # Generate a comprehensive advisory
        latest = df.iloc[-1]
        week_ago = df.iloc[-7] if len(df) >= 7 else df.iloc[0]

        advisory_report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "location": st.session_state.location,
            "crop": st.session_state.crop,
            "growth_stage": "Tillering" if st.session_state.crop == "Wheat" else "Vegetative",
            "key_findings": {
                "vegetation_health": {
                    "value": f"{latest['NDVI']:.3f}",
                    "status": "Good" if latest['NDVI'] > 0.5 else "Moderate" if latest['NDVI'] > 0.3 else "Poor",
                    "change_vs_week": f"{((latest['NDVI'] - week_ago['NDVI']) / week_ago['NDVI'] * 100):+.1f}%"
                },
                "water_status": {
                    "ndwi_value": f"{latest['NDWI']:.3f}",
                    "status": "Adequate" if latest['NDWI'] > 0.25 else "Moderate Stress" if latest['NDWI'] > 0.15 else "High Stress",
                    "deficit_mm": f"{latest['water_deficit_mm']:.1f} mm"
                },
                "weather_impact": {
                    "temperature": f"{latest['temperature']:.1f}°C",
                    "weekly_rainfall": f"{df['rainfall'].iloc[-7:].sum():.1f} mm",
                    "stress_risk": "Low" if latest['temperature'] < 30 else "Moderate" if latest['temperature'] < 35 else "High"
                }
            },
            "recommendations": [
                {
                    "priority": "High",
                    "action": "Irrigation scheduling",
                    "details": "Apply 15-20mm water in 2 days based on NDWI deficit",
                    "expected_impact": "Prevent 10-15% yield loss from water stress"
                },
                {
                    "priority": "Medium",
                    "action": "Nutrient management",
                    "details": "Consider nitrogen top-dressing if NDVI shows declining trend",
                    "expected_impact": "Maintain optimal vegetative growth"
                },
                {
                    "priority": "Low",
                    "action": "Monitoring",
                    "details": "Weekly satellite monitoring recommended",
                    "expected_impact": "Early detection of any emerging issues"
                }
            ]
        }

        # Display the report in a nice format
        st.json(advisory_report, expanded=False)

        # Download button for report
        report_json = json.dumps(advisory_report, indent=2)
        st.download_button(
            label="📥 Download Advisory Report (JSON)",
            data=report_json,
            file_name=f"kisanai_advisory_{st.session_state.location.replace(', ', '_')}_{st.session_state.crop}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )

with tab4:
    st.markdown("<h2 class='sub-header'>Historical Trends & Analytics</h2>", unsafe_allow_html=True)

    # Time series analysis
    col_ts1, col_ts2 = st.columns(2)

    with col_ts1:
        # Monthly averages
        df_monthly = df.copy()
        df_monthly['month'] = df_monthly['date'].dt.to_period('M')
        monthly_avg = df_monthly.groupby('month').agg({
            'NDVI': 'mean',
            'NDWI': 'mean',
            'rainfall': 'sum',
            'temperature': 'mean'
        }).reset_index()
        monthly_avg['month_str'] = monthly_avg['month'].astype(str)

        fig_monthly = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Monthly NDVI Avg', 'Monthly NDWI Avg', 'Monthly Rainfall', 'Monthly Temperature'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )

        fig_monthly.add_trace(
            go.Scatter(x=monthly_avg['month_str'], y=monthly_avg['NDVI'],
                      name='NDVI', line=dict(color='#27ae60')),
            row=1, col=1
        )
        fig_monthly.add_trace(
            go.Scatter(x=monthly_avg['month_str'], y=monthly_avg['NDWI'],
                      name='NDWI', line=dict(color='#3498db')),
            row=1, col=2
        )
        fig_monthly.add_trace(
            go.Bar(x=monthly_avg['month_str'], y=monthly_avg['rainfall'],
                   name='Rainfall', marker_color='#e67e22'),
            row=2, col=1
        )
        fig_monthly.add_trace(
            go.Scatter(x=monthly_avg['month_str'], y=monthly_avg['temperature'],
                      name='Temperature', line=dict(color='#e74c3c')),
            row=2, col=2
        )

        fig_monthly.update_layout(height=500, showlegend=False)
        fig_monthly.update_yaxes(title_text="NDVI", row=1, col=1)
        fig_monthly.update_yaxes(title_text="NDWI", row=1, col=2)
        fig_monthly.update_yaxes(title_text="Rainfall (mm)", row=2, col=1)
        fig_monthly.update_yaxes(title_text="Temperature (°C)", row=2, col=2)
        st.plotly_chart(fig_monthly, use_container_width=True)

    with col_ts2:
        # Correlation matrix
        st.markdown("### 🔗 Variable Correlations")
        corr_df = df[['NDVI', 'NDWI', 'EVI', 'rainfall', 'temperature', 'crop_health_score', 'water_stress_level']].corr()

        fig_corr = go.Figure(data=go.Heatmap(
            z=corr_df.values,
            x=corr_df.columns,
            y=corr_df.columns,
            colorscale='RdBu',
            zmid=0,
            text=np.round(corr_df.values, 2),
            texttemplate="%{text}",
            textfont={"size": 10}
        ))
        fig_corr.update_layout(
            title="Correlation Matrix of Key Variables",
            height=400
        )
        st.plotly_chart(fig_corr, use_container_width=True)

        # Statistics summary
        st.markdown("### 📊 Summary Statistics")
        stats_df = df.describe()[['NDVI', 'NDWI', 'crop_health_score', 'water_stress_level']].round(3)
        st.dataframe(stats_df, use_container_width=True)

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #95a5a6;'>"
    "KisanAI • Satellite-Driven Crop Digital Twin • "
    f"Data as of {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    "</p>",
    unsafe_allow_html=True
)