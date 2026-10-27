"""
AirPulse AI - Actionable Decision & Policy Engine (SDG 3 & 13)
Powers public health advisories, safe outdoor activity window finders,
and an interactive "What-If" municipal policy intervention simulator.
"""

from typing import Dict, Any, List
from ml_engine.aqi_calculator import calculate_overall_aqi, get_aqi_category_info


class DecisionAndPolicyEngine:
    def __init__(self):
        pass

    def get_population_health_advisory(self, current_aqi: float, dominant_pollutant: str) -> Dict[str, Any]:
        """
        SDG 3: Good Health & Well-being recommendations tailored per demographic.
        """
        cat_info = get_aqi_category_info(current_aqi)
        category = cat_info["category"]

        advisories = {
            "general_public": {
                "title": "General Population",
                "icon": "🚶",
                "status": "Safe" if current_aqi <= 100 else "Caution" if current_aqi <= 150 else "Restricted",
                "guidance": cat_info["general_public"],
                "mask_recommended": current_aqi > 150
            },
            "children_schools": {
                "title": "Children & School Sports",
                "icon": "🎒",
                "status": "Normal" if current_aqi <= 50 else "Caution" if current_aqi <= 100 else "Suspended Outdoor Activities",
                "guidance": "Outdoor recess and physical education sports should be moved indoors or rescheduled." if current_aqi > 100 else "Safe for outdoor sports and campus activities.",
                "mask_recommended": current_aqi > 100
            },
            "elderly_cardiac": {
                "title": "Elderly & Cardiovascular Patients",
                "icon": "❤️",
                "status": "Safe" if current_aqi <= 50 else "High Risk" if current_aqi > 100 else "Moderate Risk",
                "guidance": "Stay inside air-filtered rooms; monitor pulse and avoid exertion." if current_aqi > 100 else "Standard routine with hydration.",
                "mask_recommended": current_aqi > 100
            },
            "asthma_respiratory": {
                "title": "Asthmatics & Respiratory Sensitive",
                "icon": "🫁",
                "status": "Medical Alert" if current_aqi > 150 else "Elevated Risk" if current_aqi > 100 else "Manageable",
                "guidance": f"Keep quick-relief inhalers on hand. Dominant threat is {dominant_pollutant}." if current_aqi > 50 else "Low airborne irritation risk.",
                "mask_recommended": current_aqi > 100
            }
        }

        return {
            "aqi": current_aqi,
            "category": category,
            "color_hex": cat_info["color_hex"],
            "dominant_pollutant": dominant_pollutant,
            "summary": cat_info["health_summary"],
            "groups": advisories
        }

    def find_safe_activity_windows(self, forecast_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Scans future 24 hours to find the cleanest 2-to-3 hour window for outdoor exercise/sports.
        """
        if not forecast_steps:
            return {"best_window": None, "worst_window": None}

        # Consider next 24 steps
        steps = forecast_steps[:24]

        # Sliding 2-hour window average AQI
        best_avg = float("inf")
        best_idx = 0

        worst_avg = 0.0
        worst_idx = 0

        for i in range(len(steps) - 2):
            window_avg = (steps[i]["aqi"] + steps[i+1]["aqi"] + steps[i+2]["aqi"]) / 3.0
            if window_avg < best_avg:
                best_avg = window_avg
                best_idx = i
            if window_avg > worst_avg:
                worst_avg = window_avg
                worst_idx = i

        best_start = steps[best_idx]["display_time"]
        best_end = steps[min(len(steps)-1, best_idx+2)]["display_time"]

        worst_start = steps[worst_idx]["display_time"]
        worst_end = steps[min(len(steps)-1, worst_idx+2)]["display_time"]

        return {
            "optimal_outdoor_window": {
                "time_range": f"{best_start} – {best_end}",
                "expected_aqi": round(best_avg, 1),
                "category": get_aqi_category_info(best_avg)["category"],
                "recommendation": "Best window for jogging, cycling, school sports, and outdoor walking."
            },
            "peak_pollution_window": {
                "time_range": f"{worst_start} – {worst_end}",
                "expected_aqi": round(worst_avg, 1),
                "category": get_aqi_category_info(worst_avg)["category"],
                "recommendation": "Avoid prolonged outdoor exposure; keep windows closed."
            }
        }

    def simulate_policy_intervention(
        self,
        current_readings: Dict[str, float],
        traffic_reduction_pct: float = 0.0,
        industrial_curb_pct: float = 0.0,
        road_misting_pct: float = 0.0
    ) -> Dict[str, Any]:
        """
        SDG 13: What-If Policy Scenario Simulator
        Simulates the effect of municipal interventions on multi-pollutant levels and final AQI.
        """
        pm25_orig = float(current_readings.get("pm25", 45.0))
        pm10_orig = float(current_readings.get("pm10", 75.0))
        no2_orig = float(current_readings.get("no2", 40.0))
        so2_orig = float(current_readings.get("so2", 15.0))
        co_orig = float(current_readings.get("co", 1.0))
        o3_orig = float(current_readings.get("o3", 35.0))

        # Calculate baseline
        baseline = calculate_overall_aqi(pm25_orig, pm10_orig, no2_orig, so2_orig, co_orig, o3_orig)

        # 1. Traffic Reduction Effects (reduces NO2, CO, PM2.5 vehicular component)
        t_factor = min(max(traffic_reduction_pct, 0.0), 50.0) / 100.0
        no2_sim = max(5.0, no2_orig * (1.0 - 0.75 * t_factor))
        co_sim = max(0.2, co_orig * (1.0 - 0.70 * t_factor))
        pm25_traffic_cut = pm25_orig * 0.40 * t_factor # 40% of PM2.5 is vehicular

        # 2. Industrial Output Curbs (reduces SO2 and industrial PM)
        i_factor = min(max(industrial_curb_pct, 0.0), 60.0) / 100.0
        so2_sim = max(3.0, so2_orig * (1.0 - 0.85 * i_factor))
        pm25_ind_cut = pm25_orig * 0.35 * i_factor # 35% of PM2.5 is industrial

        # 3. Road Dust Misting & Sweeping (reduces coarse PM10)
        m_factor = min(max(road_misting_pct, 0.0), 100.0) / 100.0
        pm10_dust_cut = (pm10_orig - pm25_orig) * 0.55 * m_factor

        # Recomputed concentrations
        pm25_sim = max(6.0, pm25_orig - pm25_traffic_cut - pm25_ind_cut)
        pm10_sim = max(pm25_sim * 1.1, pm10_orig - pm25_traffic_cut - pm25_ind_cut - pm10_dust_cut)
        o3_sim = max(10.0, o3_orig * (1.0 - 0.25 * t_factor))

        simulated = calculate_overall_aqi(pm25_sim, pm10_sim, no2_sim, so2_sim, co_sim, o3_sim)

        aqi_delta = baseline["aqi"] - simulated["aqi"]
        pct_improvement = round((aqi_delta / max(baseline["aqi"], 1.0)) * 100, 1)

        # SDG Impact Estimates (Health economics approximation formulas)
        # Avoided emergency admissions: ~1.8 per 10 AQI reduction per 100k population
        avoided_admissions = max(0, int(round((aqi_delta / 10.0) * 1.8 * 3.5)))
        # CO2 reduction per day (kg) from traffic curbs
        co2_avoided_kg = round(t_factor * 12500.0 + i_factor * 8500.0, 1)

        interventions_active = []
        if traffic_reduction_pct > 0:
            interventions_active.append(f"Traffic Congestion Pricing / Rerouting (-{traffic_reduction_pct}%)")
        if industrial_curb_pct > 0:
            interventions_active.append(f"Industrial Emission Capping (-{industrial_curb_pct}%)")
        if road_misting_pct > 0:
            interventions_active.append(f"High-Pressure Road Dust Misting (-{road_misting_pct}%)")

        return {
            "baseline_aqi": baseline["aqi"],
            "baseline_category": baseline["category"],
            "baseline_color": baseline["color_hex"],
            "simulated_aqi": simulated["aqi"],
            "simulated_category": simulated["category"],
            "simulated_color": simulated["color_hex"],
            "aqi_reduction_pts": round(aqi_delta, 1),
            "aqi_reduction_pct": pct_improvement,
            "avoided_emergency_admissions_est": avoided_admissions,
            "co2_mitigation_kg_est": co2_avoided_kg,
            "simulated_pollutants": {
                "pm25": round(pm25_sim, 1),
                "pm10": round(pm10_sim, 1),
                "no2": round(no2_sim, 1),
                "so2": round(so2_sim, 1),
                "co": round(co_sim, 2),
                "o3": round(o3_sim, 1)
            },
            "active_interventions": interventions_active or ["Baseline Ambient (No Active Intervention)"]
        }
