"""
AirPulse AI - Explainable AI (XAI) & Root-Cause Attribution Engine
Provides intuitive feature contribution breakdowns and plain-English drivers
explaining why air quality is degrading or improving.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List


class PollutionExplainabilityEngine:
    def __init__(self):
        pass

    def explain_reading(self, row: pd.Series) -> Dict[str, Any]:
        """
        Computes normalized percentage feature contributions and plain-English root causes.
        """
        def safe_float(val, default):
            try:
                if val is None:
                    return default
                v = float(val)
                return default if (np.isnan(v) or np.isinf(v)) else v
            except (ValueError, TypeError):
                return default

        wind_speed = safe_float(row.get("wind_speed"), 2.5)
        traffic_idx = safe_float(row.get("traffic_density_idx"), 0.5)
        ind_idx = safe_float(row.get("industrial_activity_idx"), 0.3)
        inversion = safe_float(row.get("inversion_strength"), 0.1)
        humidity = safe_float(row.get("humidity"), 60.0)
        rainfall = safe_float(row.get("rainfall_mm"), 0.0)

        # 1. Physics-based attribution weights
        # Low wind = high trapping penalty
        stagnancy_weight = max(0.0, (4.5 - wind_speed) * 1.6)
        traffic_weight = traffic_idx * 5.2
        industrial_weight = ind_idx * 4.4
        inversion_weight = inversion * 6.5
        background_weight = 1.2 # Baseline natural particulates

        # Washout mitigation
        cleansing_weight = max(0.0, rainfall * 2.5 + max(0.0, wind_speed - 4.5) * 1.2)

        raw_drivers = [
            {
                "id": "wind_stagnancy",
                "name": "Wind Stagnancy & Dispersion Deficit",
                "category": "Meteorology",
                "raw_score": stagnancy_weight,
                "current_val": f"{wind_speed:.1f} m/s",
                "normal_val": "> 3.5 m/s",
                "explanation": f"Calm wind ({wind_speed:.1f} m/s) prevents horizontal atmospheric dispersion, trapping exhaust at street level."
            },
            {
                "id": "traffic_surge",
                "name": "Vehicular Emission Surge",
                "category": "Traffic",
                "raw_score": traffic_weight,
                "current_val": f"{int(traffic_idx*100)}% peak",
                "normal_val": "< 40%",
                "explanation": f"Elevated combustion activity ({int(traffic_idx*100)}% traffic density) generating high NO2 and fine carbon particulates."
            },
            {
                "id": "thermal_inversion",
                "name": "Nocturnal Inversion Layer",
                "category": "Atmospheric Dynamics",
                "raw_score": inversion_weight,
                "current_val": f"{inversion:.2f} index",
                "normal_val": "< 0.10",
                "explanation": f"Cold ground air capped by warmer aloft layer traps pollutants within a shallow 150m boundary layer."
            },
            {
                "id": "industrial_output",
                "name": "Industrial & Boiler Emissions",
                "category": "Industry",
                "raw_score": industrial_weight,
                "current_val": f"{int(ind_idx*100)}% load",
                "normal_val": "< 30%",
                "explanation": f"Point-source manufacturing and boiler activity elevating local SO2 and particulate levels."
            },
            {
                "id": "urban_background",
                "name": "Urban Background & Resuspension",
                "category": "Background",
                "raw_score": background_weight,
                "current_val": "Ambient",
                "normal_val": "Normal",
                "explanation": "Standard city baseline particulates, road dust resuspension, and regional background haze."
            }
        ]

        # Calculate percentage share
        total_score = sum(d["raw_score"] for d in raw_drivers) or 1.0

        driver_results = []
        for d in sorted(raw_drivers, key=lambda x: x["raw_score"], reverse=True):
            pct = round((d["raw_score"] / total_score) * 100, 1)
            if pct >= 5.0: # Only include significant drivers
                driver_results.append({
                    "id": d["id"],
                    "name": d["name"],
                    "category": d["category"],
                    "contribution_pct": pct,
                    "current_val": d["current_val"],
                    "normal_val": d["normal_val"],
                    "explanation": d["explanation"]
                })

        # Generate executive plain-English summary
        top_driver = driver_results[0]
        second_driver = driver_results[1] if len(driver_results) > 1 else None

        if top_driver["id"] == "wind_stagnancy":
            summary = f"Air quality degradation is primarily driven by Atmospheric Stagnancy ({top_driver['contribution_pct']}%), where calm wind conditions ({wind_speed:.1f} m/s) severely restrict pollutant dispersion."
        elif top_driver["id"] == "traffic_surge":
            summary = f"Pollution is predominantly driven by Vehicular Congestion ({top_driver['contribution_pct']}%), causing an intense spike in tailpipe NO2 and ultrafine PM2.5."
        elif top_driver["id"] == "thermal_inversion":
            summary = f"A Temperature Inversion Layer ({top_driver['contribution_pct']}%) is the primary culprit, trapping ground-level emissions under a stagnant thermal ceiling."
        else:
            summary = f"Air quality is impacted by a combination of Industrial Combustion ({top_driver['contribution_pct']}%) and local background emissions."

        if second_driver:
            summary += f" Secondary compounding factor is {second_driver['name']} ({second_driver['contribution_pct']}%)."

        return {
            "station_id": str(row.get("station_id", "STN-01")),
            "timestamp": str(row.get("timestamp", "")),
            "executive_summary": summary,
            "drivers": driver_results,
            "cleansing_factors": {
                "rainfall_cleansing": f"{rainfall:.1f} mm/h" if rainfall > 0 else "None",
                "ventilation_cleansing": "Active" if wind_speed > 4.0 else "Weak"
            }
        }
