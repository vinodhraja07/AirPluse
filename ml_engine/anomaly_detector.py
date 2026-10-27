"""
AirPulse AI - Anomaly Detection & High-Risk Window Alert Engine
Identifies consecutive hazardous pollution windows, acute industrial bursts,
and automated early-warning alert triggers for municipal response.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from sklearn.ensemble import IsolationForest


class AnomalyAndAlertEngine:
    def __init__(self):
        self.iso_forest = IsolationForest(contamination=0.03, random_state=42)
        self.is_fitted = False

    def fit(self, df: pd.DataFrame):
        features = df[["pm25", "pm10", "no2", "so2", "co", "o3", "wind_speed"]].fillna(0.0)
        self.iso_forest.fit(features)
        self.is_fitted = True

    def scan_high_risk_windows(self, forecast_steps: List[Dict[str, Any]], station_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Scans future forecast trajectory for consecutive high-risk hours (AQI > 100)
        and generates actionable emergency intervention alerts.
        """
        alerts = []
        current_streak = []

        for step in forecast_steps:
            aqi = step["aqi"]
            if aqi >= 101: # USG or worse
                current_streak.append(step)
            else:
                if len(current_streak) >= 2:
                    alert = self._create_window_alert(current_streak, station_info)
                    if alert:
                        alerts.append(alert)
                current_streak = []

        # Handle trailing streak
        if len(current_streak) >= 2:
            alert = self._create_window_alert(current_streak, station_info)
            if alert:
                alerts.append(alert)

        # If no severe multi-hour window, check if any single step is elevated
        if not alerts:
            max_step = max(forecast_steps, key=lambda x: x["aqi"]) if forecast_steps else None
            if max_step and max_step["aqi"] > 100:
                alerts.append({
                    "id": f"ALT-{np.random.randint(1000, 9999)}",
                    "severity": "WARNING",
                    "severity_color": "#FBBF24",
                    "title": f"Elevated {max_step['dominant_pollutant']} Expected",
                    "time_window": f"Around {max_step['display_time']}",
                    "peak_aqi": max_step["aqi"],
                    "dominant_threat": max_step["dominant_pollutant"],
                    "affected_population": "Individuals with respiratory sensitivities",
                    "action_trigger": "Moderate outdoor sports duration during peak hours."
                })

        return alerts

    def _create_window_alert(self, streak: List[Dict[str, Any]], station: Dict[str, Any]) -> Dict[str, Any]:
        peak_step = max(streak, key=lambda x: x["aqi"])
        peak_aqi = peak_step["aqi"]
        start_time = streak[0]["display_time"]
        end_time = streak[-1]["display_time"]
        duration = len(streak)

        if peak_aqi >= 201:
            severity = "CRITICAL"
            color = "#8B5CF6"
            title = f"Severe Smog Inversion Window ({duration} Hours)"
            action = "Mandatory industrial output reduction (-40%) & heavy truck rerouting."
        elif peak_aqi >= 151:
            severity = "HIGH"
            color = "#EF4444"
            title = f"Unhealthy Air Quality Window ({duration} Hours)"
            action = "Deploy municipal mist spraying trucks & issue school outdoor recess bans."
        else:
            severity = "MODERATE"
            color = "#F97316"
            title = f"Sensitive Group Exposure Window ({duration} Hours)"
            action = "Broadcast vulnerable population health warnings (SDG 3)."

        return {
            "id": f"ALT-{np.random.randint(1000, 9999)}",
            "severity": severity,
            "severity_color": color,
            "title": title,
            "time_window": f"{start_time} → {end_time} ({duration} hrs)",
            "peak_aqi": peak_aqi,
            "dominant_threat": peak_step["dominant_pollutant"],
            "affected_population": "Children, elderly, asthmatics, and outdoor workers",
            "action_trigger": action
        }
