"""
AirPulse AI - Synthetic Multi-Station Atmospheric & Pollution Dataset Generator
Simulates realistic urban micro-climates, diurnal traffic cycles, photochemical reactions,
winter temperature inversions, and wind dispersion physics.
"""

import json
import math
import os
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# Load stations metadata
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
STATIONS_FILE = os.path.join(DATA_DIR, "stations.json")
OUTPUT_CSV = os.path.join(DATA_DIR, "aqi_timeseries.csv")


def calculate_sub_aqi_pm25(c: float) -> float:
    """EPA Standard AQI Breakpoint formula for PM2.5 (ug/m3)"""
    if c <= 12.0:
        return ((50 - 0) / (12.0 - 0.0)) * (c - 0.0) + 0
    elif c <= 35.4:
        return ((100 - 51) / (35.4 - 12.1)) * (c - 12.1) + 51
    elif c <= 55.4:
        return ((150 - 101) / (55.4 - 35.5)) * (c - 35.5) + 101
    elif c <= 150.4:
        return ((200 - 151) / (150.4 - 55.5)) * (c - 55.5) + 151
    elif c <= 250.4:
        return ((300 - 201) / (250.4 - 150.5)) * (c - 150.5) + 201
    elif c <= 350.4:
        return ((400 - 301) / (350.4 - 250.5)) * (c - 250.5) + 301
    else:
        return ((500 - 401) / (500.4 - 350.5)) * (min(c, 500.0) - 350.5) + 401


def calculate_sub_aqi_pm10(c: float) -> float:
    """EPA Standard AQI Breakpoint formula for PM10 (ug/m3)"""
    if c <= 54:
        return (50 / 54) * c
    elif c <= 154:
        return ((100 - 51) / (154 - 55)) * (c - 55) + 51
    elif c <= 254:
        return ((150 - 101) / (254 - 155)) * (c - 155) + 101
    elif c <= 354:
        return ((200 - 151) / (354 - 255)) * (c - 255) + 151
    elif c <= 424:
        return ((300 - 201) / (424 - 355)) * (c - 355) + 201
    else:
        return ((500 - 301) / (604 - 425)) * (min(c, 604) - 425) + 301


def get_aqi_category(aqi_val: float) -> str:
    """Returns official EPA AQI category"""
    if aqi_val <= 50:
        return "Good"
    elif aqi_val <= 100:
        return "Moderate"
    elif aqi_val <= 150:
        return "Unhealthy for Sensitive Groups"
    elif aqi_val <= 200:
        return "Unhealthy"
    elif aqi_val <= 300:
        return "Very Unhealthy"
    else:
        return "Hazardous"


def generate_atmospheric_dataset(
    start_date: str = "2025-01-01",
    days: int = 365,
    seed: int = 42,
    output_path: str = OUTPUT_CSV
) -> pd.DataFrame:
    """
    Generates synthetic realistic hourly air quality & meteorological dataset for 5 stations.
    """
    np.random.seed(seed)

    with open(STATIONS_FILE, "r", encoding="utf-8") as f:
        stations = json.load(f)

    start = datetime.strptime(start_date, "%Y-%m-%d")
    total_hours = days * 24

    records = []

    # Pre-generate macro weather wave patterns (synoptic weather across region)
    day_indices = np.arange(total_hours) / 24.0

    # Seasonal base temperatures (cold in Jan/Feb/Dec, hot in May/Jun)
    seasonal_temp_base = 26.0 + 8.0 * np.sin(2 * np.pi * (day_indices - 100) / 365.0)

    # Multi-day synoptic weather fronts (5 to 10 day cycles)
    synoptic_pressure = 1012.0 + 7.0 * np.sin(2 * np.pi * day_indices / 7.2)
    synoptic_wind_speed = 3.2 + 1.8 * np.sin(2 * np.pi * day_indices / 5.5) + np.random.normal(0, 0.4, total_hours)
    synoptic_wind_speed = np.clip(synoptic_wind_speed, 0.2, 12.0)

    # Synoptic wind direction (dominant NE in winter, SW in summer/monsoon)
    seasonal_wind_dir = 50.0 + 160.0 * (0.5 + 0.5 * np.sin(2 * np.pi * (day_indices - 120) / 365.0))

    # Rain event occurrences (clustered in monsoon months day 150-300)
    rain_prob = 0.05 + 0.15 * np.maximum(0, np.sin(np.pi * (day_indices - 150) / 150.0))
    rain_events = (np.random.rand(total_hours) < rain_prob * 0.1).astype(float)
    rain_amount = rain_events * np.random.exponential(4.0, total_hours)

    for stn in stations:
        stn_id = stn["id"]
        stn_name = stn["name"]
        stn_type = stn["type"]

        # Station-specific emission baselines and multipliers
        if stn_type == "traffic":
            traffic_mult = 1.6
            ind_mult = 0.7
            pm_base = 42.0
            no2_base = 48.0
            so2_base = 12.0
        elif stn_type == "industrial":
            traffic_mult = 0.9
            ind_mult = 1.9
            pm_base = 65.0
            no2_base = 35.0
            so2_base = 45.0
        elif stn_type == "residential":
            traffic_mult = 0.7
            ind_mult = 0.3
            pm_base = 25.0
            no2_base = 20.0
            so2_base = 8.0
        elif stn_type == "corridor":
            traffic_mult = 1.8
            ind_mult = 1.2
            pm_base = 55.0
            no2_base = 52.0
            so2_base = 22.0
        else: # sensitive/healthcare
            traffic_mult = 0.8
            ind_mult = 0.4
            pm_base = 28.0
            no2_base = 24.0
            so2_base = 10.0

        for h in range(total_hours):
            current_time = start + timedelta(hours=h)
            hour = current_time.hour
            d_idx = h / 24.0
            month = current_time.month
            dow = current_time.weekday() # 0=Mon, 6=Sun

            # Diurnal Solar Cycle (Temp peaks at 2-3 PM (14:00), lowest at 5 AM)
            solar_phase = (hour - 5) % 24
            diurnal_temp = 6.5 * np.sin(np.pi * np.clip(solar_phase, 0, 18) / 18.0) - 2.5 * (1 - np.sin(np.pi * np.clip(solar_phase, 0, 18) / 18.0))
            temperature = seasonal_temp_base[h] + diurnal_temp + np.random.normal(0, 0.6)

            # Relative humidity (inversely related to temperature)
            humidity = np.clip(92.0 - 1.8 * (temperature - 18.0) + (15.0 if rain_amount[h] > 0 else 0) + np.random.normal(0, 3.0), 20.0, 99.0)

            # Pressure
            pressure = synoptic_pressure[h] + 1.5 * np.sin(2 * np.pi * hour / 12.0) + np.random.normal(0, 0.3)

            # Wind speed with daytime thermal turbulence
            wind_speed = synoptic_wind_speed[h] * (1.0 + 0.35 * np.sin(np.pi * max(0, hour - 7) / 12.0))
            wind_speed = max(0.2, wind_speed + np.random.normal(0, 0.2))

            # Wind direction
            wind_dir = (seasonal_wind_dir[h] + 25.0 * np.sin(2 * np.pi * hour / 24.0) + np.random.normal(0, 15.0)) % 360.0

            # Traffic profile (Double peak: 7-10 AM and 5-9 PM, lower on weekends)
            is_weekend = dow >= 5
            weekend_factor = 0.65 if is_weekend else 1.0
            morning_rush = np.exp(-((hour - 8.5) ** 2) / 2.8)
            evening_rush = np.exp(-((hour - 18.5) ** 2) / 3.5)
            midday = 0.45 * (1.0 if 10 <= hour <= 16 else 0.0)
            night_traffic = 0.15
            traffic_density = np.clip((morning_rush + evening_rush + midday + night_traffic) * weekend_factor * traffic_mult + np.random.normal(0, 0.05), 0.05, 1.0)

            # Industrial activity (Active weekday daytime + occasional nocturnal venting 11pm-4am)
            industrial_shift = 0.8 if (8 <= hour <= 19 and not is_weekend) else 0.4
            nocturnal_venting = 0.7 if (stn_type == "industrial" and (hour >= 23 or hour <= 4) and np.random.rand() < 0.25) else 0.0
            industrial_activity = np.clip((industrial_shift + nocturnal_venting) * ind_mult + np.random.normal(0, 0.05), 0.1, 1.0)

            # Winter Temperature Inversion Layer (Nov, Dec, Jan, Feb)
            # Cold night ground + calm wind = trapped pollutants
            is_winter = month in [11, 12, 1, 2]
            night_early_morning = (hour >= 22 or hour <= 7)
            if is_winter and night_early_morning and wind_speed < 1.8:
                inversion_strength = np.clip((1.8 - wind_speed) / 1.8 * (1.0 + (30.0 - temperature) / 20.0), 0.3, 1.0)
            else:
                inversion_strength = 0.05 * np.random.rand()

            # Wind Dispersion Dilution Factor (High wind cleanses air, calm wind traps)
            dispersion_factor = 1.0 / (1.0 + 0.55 * wind_speed)

            # Rain washout factor
            washout = np.exp(-0.4 * rain_amount[h])

            # --- Pollutant Concentrations ---
            # 1. PM2.5 (Fine particulate matter: traffic + industry + winter inversion)
            pm25_emission = (pm_base * (0.5 + 0.8 * traffic_density + 0.6 * industrial_activity))
            pm25 = (pm25_emission * dispersion_factor * (1.0 + 1.8 * inversion_strength) * washout) + np.random.normal(0, 3.0)
            pm25 = max(4.0, pm25)

            # 2. PM10 (Coarse + Fine: includes mechanical road dust, construction)
            coarse_dust = 22.0 * traffic_density + 15.0 * (1.0 if wind_speed > 4.5 else 0.4)
            pm10 = pm25 * 1.55 + coarse_dust * dispersion_factor * washout + np.random.normal(0, 5.0)
            pm10 = max(pm25 * 1.1, pm10)

            # 3. NO2 (Nitrogen Dioxide: primary vehicular indicator)
            no2_emission = no2_base * (0.3 + 1.2 * traffic_density + 0.4 * industrial_activity)
            # Sunlight causes photochemical photolysis of NO2 into O3 in afternoon
            sunlight_intensity = max(0.0, np.sin(np.pi * max(0, hour - 6) / 12.0))
            no2 = (no2_emission * dispersion_factor * (1.0 - 0.25 * sunlight_intensity) * (1.0 + 1.0 * inversion_strength) * washout)
            no2 = max(3.0, no2 + np.random.normal(0, 2.5))

            # 4. SO2 (Sulfur Dioxide: heavy industrial & shipping)
            so2_emission = so2_base * (0.3 + 1.4 * industrial_activity)
            so2 = (so2_emission * dispersion_factor * (1.0 + 1.2 * inversion_strength) * washout) + np.random.normal(0, 2.0)
            so2 = max(2.0, so2)

            # 5. CO (Carbon Monoxide, in mg/m3)
            co = (0.3 + 1.8 * traffic_density * dispersion_factor * (1.0 + 1.4 * inversion_strength)) + np.random.normal(0, 0.05)
            co = max(0.1, co)

            # 6. O3 (Ozone: Photochemical secondary pollutant, peaks 1-4 PM with sunlight & heat)
            o3_precursor = (no2 / 40.0) * (temperature / 28.0)
            o3 = (15.0 + 65.0 * (sunlight_intensity ** 1.3) * o3_precursor * washout) + np.random.normal(0, 3.0)
            o3 = max(4.0, o3)

            # Calculate Ground Composite AQI & Category
            aqi_pm25 = calculate_sub_aqi_pm25(pm25)
            aqi_pm10 = calculate_sub_aqi_pm10(pm10)
            ground_aqi = round(max(aqi_pm25, aqi_pm10), 1)
            category = get_aqi_category(ground_aqi)

            records.append({
                "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "station_id": stn_id,
                "station_name": stn_name,
                "station_type": stn_type,
                "pm25": round(pm25, 2),
                "pm10": round(pm10, 2),
                "no2": round(no2, 2),
                "so2": round(so2, 2),
                "co": round(co, 2),
                "o3": round(o3, 2),
                "temperature": round(temperature, 1),
                "humidity": round(humidity, 1),
                "pressure_hpa": round(pressure, 1),
                "wind_speed": round(wind_speed, 2),
                "wind_direction": round(wind_dir, 1),
                "rainfall_mm": round(rain_amount[h], 1),
                "traffic_density_idx": round(traffic_density, 3),
                "industrial_activity_idx": round(industrial_activity, 3),
                "inversion_strength": round(inversion_strength, 3),
                "ground_aqi": ground_aqi,
                "aqi_category": category
            })

    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} records across {len(stations)} stations saved to: {output_path}")
    return df


if __name__ == "__main__":
    generate_atmospheric_dataset()
