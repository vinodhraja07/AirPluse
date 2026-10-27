"""
AirPulse AI - EPA / International Standard AQI Calculator & Health Category Classifier
Computes sub-indices for PM2.5, PM10, NO2, SO2, CO, O3 and identifies dominant drivers.
"""

from typing import Dict, Any, Tuple


# EPA / CPCB Standard Breakpoints: (C_low, C_high, I_low, I_high)
BREAKPOINTS_PM25 = [
    (0.0, 12.0, 0, 50),
    (12.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 150.4, 151, 200),
    (150.5, 250.4, 201, 300),
    (250.5, 350.4, 301, 400),
    (350.5, 500.4, 401, 500),
]

BREAKPOINTS_PM10 = [
    (0.0, 54.0, 0, 50),
    (55.0, 154.0, 51, 100),
    (155.0, 254.0, 101, 150),
    (255.0, 354.0, 151, 200),
    (355.0, 424.0, 201, 300),
    (425.0, 504.0, 301, 400),
    (505.0, 604.0, 401, 500),
]

BREAKPOINTS_NO2 = [
    (0.0, 53.0, 0, 50),
    (54.0, 100.0, 51, 100),
    (101.0, 360.0, 101, 150),
    (361.0, 649.0, 151, 200),
    (650.0, 1249.0, 201, 300),
    (1250.0, 1649.0, 301, 400),
    (1650.0, 2049.0, 401, 500),
]

BREAKPOINTS_SO2 = [
    (0.0, 35.0, 0, 50),
    (36.0, 75.0, 51, 100),
    (76.0, 185.0, 101, 150),
    (186.0, 304.0, 151, 200),
    (305.0, 604.0, 201, 300),
    (605.0, 804.0, 301, 400),
    (805.0, 1004.0, 401, 500),
]

BREAKPOINTS_CO = [ # in mg/m3
    (0.0, 4.4, 0, 50),
    (4.5, 9.4, 51, 100),
    (9.5, 12.4, 101, 150),
    (12.5, 15.4, 151, 200),
    (15.5, 30.4, 201, 300),
    (30.5, 40.4, 301, 400),
    (40.5, 50.4, 401, 500),
]

BREAKPOINTS_O3 = [
    (0.0, 54.0, 0, 50),
    (55.0, 70.0, 51, 100),
    (71.0, 85.0, 101, 150),
    (86.0, 105.0, 151, 200),
    (106.0, 200.0, 201, 300),
    (201.0, 300.0, 301, 400),
    (301.0, 400.0, 401, 500),
]


def _linear_interpolate(conc: float, breakpoints: list) -> float:
    """Standard AQI interpolation formula: I = ((I_high - I_low) / (C_high - C_low)) * (C - C_low) + I_low"""
    if conc <= 0.0:
        return 0.0
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= conc <= c_high:
            return round(((i_high - i_low) / (c_high - c_low)) * (conc - c_low) + i_low, 1)
    # If exceeding max scale
    c_low, c_high, i_low, i_high = breakpoints[-1]
    return 500.0


def calculate_sub_indices(
    pm25: float,
    pm10: float,
    no2: float,
    so2: float,
    co: float,
    o3: float
) -> Dict[str, float]:
    """Computes individual AQI sub-index for each pollutant."""
    return {
        "PM2.5": _linear_interpolate(pm25, BREAKPOINTS_PM25),
        "PM10": _linear_interpolate(pm10, BREAKPOINTS_PM10),
        "NO2": _linear_interpolate(no2, BREAKPOINTS_NO2),
        "SO2": _linear_interpolate(so2, BREAKPOINTS_SO2),
        "CO": _linear_interpolate(co, BREAKPOINTS_CO),
        "O3": _linear_interpolate(o3, BREAKPOINTS_O3),
    }


def get_aqi_category_info(aqi_val: float) -> Dict[str, Any]:
    """Returns visual tokens, color schemes, and health guidance for AQI score."""
    if aqi_val <= 50:
        return {
            "category": "Good",
            "level": 1,
            "color_hex": "#10B981", # Emerald green
            "color_name": "emerald",
            "badge_class": "badge-good",
            "health_summary": "Air quality is satisfactory and poses little or no risk.",
            "general_public": "Ideal conditions for all outdoor activities and exercise.",
            "sensitive_groups": "No special precautions needed.",
            "sdg_action": "Maintain clean urban mobility baselines."
        }
    elif aqi_val <= 100:
        return {
            "category": "Moderate",
            "level": 2,
            "color_hex": "#FBBF24", # Amber yellow
            "color_name": "amber",
            "badge_class": "badge-moderate",
            "health_summary": "Air quality is acceptable; slight concern for very sensitive individuals.",
            "general_public": "Safe for regular outdoor activities.",
            "sensitive_groups": "Unusually sensitive people should consider reducing prolonged heavy exertion.",
            "sdg_action": "Encourage public transit over private vehicles."
        }
    elif aqi_val <= 150:
        return {
            "category": "Unhealthy for Sensitive Groups",
            "level": 3,
            "color_hex": "#F97316", # Orange
            "color_name": "orange",
            "badge_class": "badge-usg",
            "health_summary": "Members of sensitive groups may experience health effects.",
            "general_public": "General public is less likely to be affected.",
            "sensitive_groups": "Children, elderly, and asthmatics should limit prolonged outdoor exertion.",
            "sdg_action": "Trigger municipal road-dust misting and school outdoor sports caution."
        }
    elif aqi_val <= 200:
        return {
            "category": "Unhealthy",
            "level": 4,
            "color_hex": "#EF4444", # Red
            "color_name": "red",
            "badge_class": "badge-unhealthy",
            "health_summary": "Everyone may begin to experience health effects; serious for sensitive groups.",
            "general_public": "Active children and adults should avoid prolonged outdoor exertion.",
            "sensitive_groups": "Wear N95 masks; keep indoor windows closed with air filtration.",
            "sdg_action": "Activate municipal traffic diversion & heavy diesel truck restrictions."
        }
    elif aqi_val <= 300:
        return {
            "category": "Very Unhealthy",
            "level": 5,
            "color_hex": "#8B5CF6", # Purple
            "color_name": "purple",
            "badge_class": "badge-very-unhealthy",
            "health_summary": "Health alert: The entire population is more likely to be affected.",
            "general_public": "Avoid all outdoor physical exertion; stay indoors.",
            "sensitive_groups": "Remain indoors with HEPA purification; emergency inhalers ready.",
            "sdg_action": "Enact industrial capacity curbs (-30%) and odd-even vehicular restrictions."
        }
    else:
        return {
            "category": "Hazardous",
            "level": 6,
            "color_hex": "#7F1D1D", # Deep maroon
            "color_name": "maroon",
            "badge_class": "badge-hazardous",
            "health_summary": "Health warning of emergency conditions: Serious risk of respiratory distress.",
            "general_public": "Mandatory stay-at-home advisory for non-essential travel.",
            "sensitive_groups": "Strict medical alert; activate hospital surge response for respiratory cases.",
            "sdg_action": "Emergency city shutdown of non-essential polluting industries and construction."
        }


def calculate_overall_aqi(
    pm25: float,
    pm10: float,
    no2: float = 0.0,
    so2: float = 0.0,
    co: float = 0.0,
    o3: float = 0.0
) -> Dict[str, Any]:
    """
    Computes overall composite AQI, dominant pollutant, sub-indices, and full health guidance.
    """
    sub_indices = calculate_sub_indices(pm25, pm10, no2, so2, co, o3)

    # Dominant pollutant is the one with the highest sub-index
    dominant_pollutant = max(sub_indices, key=sub_indices.get)
    max_aqi = round(sub_indices[dominant_pollutant], 1)

    category_info = get_aqi_category_info(max_aqi)

    return {
        "aqi": max_aqi,
        "dominant_pollutant": dominant_pollutant,
        "sub_indices": sub_indices,
        **category_info
    }


def get_dominant_pollutant(sub_indices: Dict[str, float]) -> Tuple[str, float]:
    """Returns (pollutant_name, sub_index)"""
    dominant = max(sub_indices, key=sub_indices.get)
    return dominant, sub_indices[dominant]
