# KisanAI - Satellite-Driven Crop Digital Twin

A Streamlit-based frontend for the KisanAI project that provides satellite-driven crop monitoring and irrigation advisory services.
<img width="1812" height="843" alt="image" src="https://github.com/user-attachments/assets/990f9962-5e90-434f-98ad-6102529cadba" />
<img width="1822" height="787" alt="image" src="https://github.com/user-attachments/assets/6b171549-f05b-47c3-9559-663f8076c7a3" />
<img width="1823" height="776" alt="image" src="https://github.com/user-attachments/assets/f4891aa1-0472-4b02-86d9-97c35173a179" />
<img width="1851" height="792" alt="image" src="https://github.com/user-attachments/assets/7f9d7260-6153-4d3e-97e8-d976cb075edd" />


## Features

- 📊 Interactive dashboard with crop health metrics
- 💧 Water stress monitoring and analysis
- 🌦️ Weather intelligence integration
- 📥 Record data and download stats easily
- 🤖 AI-powered advisory engine with explainable recommendations
- 🗺️ Satellite map visualization with NDVI indicators
- 📈 Historical trends and analytics
- 📱 Responsive design for mobile and desktop

## Technology Stack

- **Frontend**: Streamlit
- **Visualization**: Plotly, Folium
- **Data Processing**: Pandas, NumPy
- **Mapping**: Streamlit-Folium integration

## Installation

1. Clone this repository
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the Streamlit application:
```bash
streamlit run kisanai_streamlit_app.py
```

The application will open in your default web browser at http://localhost:8501

## Application Structure

1. **Sidebar Controls**: Location and crop selection, date range picker, refresh button
2. **Main Dashboard**: Key metrics (crop health, water stress, rainfall, temperature)
3. **Tabs Interface**:
   - Dashboard: Overview charts and AI recommendations
   - Satellite Map: Interactive NDVI field visualization
   - AI Advisory: Detailed explanation and downloadable reports
   - Historical Trends: Time series analysis and correlations

## Sample Data

The application uses mock data that simulates real satellite and weather measurements for demonstration purposes. In a production implementation, this would be replaced with actual data from:
- Sentinel-2 satellite imagery (via Google Earth Engine or Copernicus)
- Weather forecasts (NASA POWER, OpenWeatherMap)
- Soil data (SoilGrids ISRIC)

## Customization

To adapt this for specific regions or crops:
1. Modify the `location_options` and `crop_options` in the sidebar
2. Adjust the mock data generation functions in `generate_mock_data()`
3. Update crop-specific thresholds in the recommendation logic
4. Modify the satellite map center coordinates for your target region

## Future Enhancements

- Integration with real satellite data APIs
- Machine learning models for crop classification and stress detection
- Voice/SMS alert system integration
- Ground sensor data incorporation
- Disease detection using leaf images (as mentioned in future features)

---

**KisanAI Project** • Smart Water, Crop & Advisory System • Track 4
