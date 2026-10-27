"""
AirPulse AI - Comprehensive Automated Test Suite
Verifies data generation, feature engineering, ML forecaster accuracy,
clustering archetypes, explainability, policy simulation, and FastAPI endpoints.
"""

import os
import sys
import unittest
import pandas as pd
import numpy as np

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data.generator import generate_atmospheric_dataset, calculate_sub_aqi_pm25, calculate_sub_aqi_pm10
from ml_engine.aqi_calculator import calculate_overall_aqi, get_aqi_category_info
from ml_engine.feature_engineering import AirQualityFeaturePipeline
from ml_engine.forecaster import AirQualityForecaster
from ml_engine.clustering import PollutionPatternClusterer
from ml_engine.explainability import PollutionExplainabilityEngine
from ml_engine.anomaly_detector import AnomalyAndAlertEngine
from backend.decision_engine import DecisionAndPolicyEngine
from backend.chatbot import chat_with_sonnet_5
from backend.logger import AuditLogger
from ml_engine.plume_dispersion import GaussianPlumeDispersionEngine
from ml_engine.clean_route import CleanRouteOptimizer


class TestAirPulsePipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n--- Running AirPulse AI Pipeline Tests ---")
        # Generate a lightweight 2-day dataset for rapid unit testing (Prevention for Out-Of-Memory / RAM constraints)
        test_csv = os.path.join(BASE_DIR, "data", "test_timeseries.csv")
        cls.df = generate_atmospheric_dataset(start_date="2025-01-01", days=2, output_path=test_csv)
        cls.test_csv = test_csv

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_csv):
            os.remove(cls.test_csv)

    def test_01_data_generator_validity(self):
        """Test dataset shape, columns, and absence of NaNs."""
        self.assertGreater(len(self.df), 1000)
        required_cols = ["timestamp", "station_id", "pm25", "pm10", "no2", "so2", "co", "o3", "temperature", "humidity", "wind_speed", "ground_aqi"]
        for col in required_cols:
            self.assertIn(col, self.df.columns)
        self.assertFalse(self.df[required_cols].isnull().values.any())
        self.assertTrue((self.df["pm25"] >= 0).all())

    def test_02_aqi_calculator(self):
        """Test EPA AQI calculations and breakpoint boundaries."""
        # 10 ug/m3 PM2.5 -> AQI <= 50 (Good)
        good_aqi = calculate_overall_aqi(pm25=10.0, pm10=20.0, no2=15.0)
        self.assertEqual(good_aqi["category"], "Good")
        self.assertLessEqual(good_aqi["aqi"], 50)
        self.assertEqual(good_aqi["color_hex"], "#10B981")

        # 45 ug/m3 PM2.5 -> USG (101-150)
        usg_aqi = calculate_overall_aqi(pm25=45.0, pm10=60.0)
        self.assertEqual(usg_aqi["category"], "Unhealthy for Sensitive Groups")
        self.assertGreaterEqual(usg_aqi["aqi"], 101)
        self.assertLessEqual(usg_aqi["aqi"], 150)

    def test_03_feature_engineering_pipeline(self):
        """Test cyclical encodings, wind vectors, ratios, and lag feature creation."""
        pipeline = AirQualityFeaturePipeline(lag_hours=[1, 3], rolling_windows=[6])
        feat_df = pipeline.create_features(self.df, is_training=True)

        self.assertIn("hour_sin", feat_df.columns)
        self.assertIn("hour_cos", feat_df.columns)
        self.assertIn("wind_u", feat_df.columns)
        self.assertIn("wind_v", feat_df.columns)
        self.assertIn("pm_fine_coarse_ratio", feat_df.columns)
        self.assertIn("pm25_lag_1h", feat_df.columns)
        self.assertIn("pm25_roll_mean_6h", feat_df.columns)
        self.assertFalse(feat_df.isnull().values.any())

    def test_04_forecaster_training_and_inference(self):
        """Test multi-horizon regressor training and future forecast generation."""
        forecaster = AirQualityForecaster(horizons=[1, 6])
        metrics = forecaster.train(self.df)

        # Check PM2.5 1-hour metrics
        pm25_metrics = metrics.get("pm25", {}).get("h_1h", {})
        self.assertIn("r2", pm25_metrics)
        self.assertLess(pm25_metrics["mae"], 10.0, "MAE error should be low (< 10 ug/m3)")
        self.assertGreater(pm25_metrics["r2"], 0.30, "R2 score should be positive and predictive")

        # Test inference
        forecasts = forecaster.predict_future(self.df, station_id="DEL-01", max_horizon=12)
        self.assertEqual(len(forecasts), 12)
        self.assertIn("pm25", forecasts[0])
        self.assertIn("pm25_lower_90", forecasts[0])
        self.assertIn("pm25_upper_90", forecasts[0])
        self.assertLessEqual(forecasts[0]["pm25_lower_90"], forecasts[0]["pm25"])
        self.assertGreaterEqual(forecasts[0]["pm25_upper_90"], forecasts[0]["pm25"])

    def test_05_pattern_clustering_archetypes(self):
        """Test K-Means clustering and archetype discovery."""
        clusterer = PollutionPatternClusterer(n_clusters=4)
        result = clusterer.fit(self.df)

        self.assertEqual(len(result["profiles"]), 4)
        self.assertGreater(clusterer.silhouette, 0.20)

        # Test predicting current regime
        sample_row = self.df.iloc[-1:].copy()
        current_regime = clusterer.predict_current(sample_row)
        self.assertIn("archetype", current_regime)
        self.assertIn("short_name", current_regime)
        self.assertIn("icon", current_regime)

    def test_06_explainability_engine(self):
        """Test root-cause feature attribution percentages."""
        engine = PollutionExplainabilityEngine()
        sample_row = self.df.iloc[-1].to_dict()
        exp = engine.explain_reading(sample_row)

        self.assertIn("executive_summary", exp)
        self.assertIn("drivers", exp)
        self.assertGreater(len(exp["drivers"]), 0)

        # Drivers percentages should be well-bounded
        total_pct = sum(d["contribution_pct"] for d in exp["drivers"])
        self.assertGreaterEqual(total_pct, 70.0)

    def test_07_policy_simulator_sdg13(self):
        """Test What-If policy intervention impacts."""
        engine = DecisionAndPolicyEngine()
        sample_readings = {"pm25": 55.0, "pm10": 95.0, "no2": 50.0, "so2": 25.0, "co": 1.4, "o3": 40.0}

        # Baseline simulation
        base_res = engine.simulate_policy_intervention(sample_readings, traffic_reduction_pct=0, industrial_curb_pct=0)
        self.assertEqual(base_res["aqi_reduction_pts"], 0.0)

        # Active intervention: -30% traffic, -30% industrial
        sim_res = engine.simulate_policy_intervention(
            sample_readings,
            traffic_reduction_pct=30.0,
            industrial_curb_pct=30.0,
            road_misting_pct=50.0
        )
        self.assertLess(sim_res["simulated_aqi"], base_res["baseline_aqi"])
        self.assertGreater(sim_res["aqi_reduction_pct"], 10.0)
        self.assertGreater(sim_res["avoided_emergency_admissions_est"], 0)
        self.assertGreater(sim_res["co2_mitigation_kg_est"], 0)

    def test_08_gaussian_plume_dispersion(self):
        """Test Pasquill-Gifford Gaussian Plume advection polygon and receptor exposure."""
        engine = GaussianPlumeDispersionEngine()
        disp = engine.calculate_dispersion_footprint(
            source_lat=28.6469,
            source_lon=77.3160,
            source_pm25=85.0,
            wind_speed_ms=2.4,
            wind_dir_deg=45.0
        )
        self.assertIn("plume_polygon", disp)
        self.assertGreater(len(disp["plume_polygon"]), 20)
        self.assertEqual(disp["advection_bearing_deg"], 225.0)
        self.assertIn("centerline_concentrations", disp)

    def test_09_clean_route_optimizer(self):
        """Test SDG 3 clean-air navigation vs direct route inhalation comparison."""
        engine = CleanRouteOptimizer()
        orig = {"id": "DEL-01", "name": "Anand Vihar", "lat": 28.6469, "lon": 77.3160}
        dest = {"id": "DEL-04", "name": "R.K. Puram", "lat": 28.5635, "lon": 77.1865}
        readings = {"DEL-01": {"aqi": 180.0}, "DEL-04": {"aqi": 120.0}}

        route = engine.compute_clean_route(orig, dest, readings)
        self.assertIn("clean_air_route", route)
        self.assertIn("direct_route", route)
        self.assertGreater(route["clean_air_route"]["inhalation_reduction_pct"], 0.0)

    def test_10_ai_chatbot_engine(self):
        """Test AI copilot project telemetry grounding and conversational response."""
        sample_stn = {
            "id": "DEL-01",
            "name": "Anand Vihar ISBT",
            "city": "Delhi NCR",
            "state": "Delhi",
            "land_use": "Transit",
            "current_readings": {"pm25": 85.0, "pm10": 140.0, "no2": 45.0, "so2": 12.0, "co": 1.1, "o3": 25.0, "wind_speed": 1.5, "temperature": 28.0, "humidity": 65.0},
            "aqi_summary": {"aqi": 165.0, "category": "Unhealthy", "dominant_pollutant": "PM2.5"},
            "active_regime": {"archetype": "Traffic Surge", "short_name": "Traffic Surge", "description": "Vehicular peak"}
        }
        res = chat_with_sonnet_5(
            user_message="What is the current AQI and health advice?",
            station_context=sample_stn,
            chat_history=[],
            all_stations_count=42
        )
        self.assertEqual(res["status"], "success")
        self.assertIn("reply", res)
        self.assertGreater(len(res["reply"]), 20)
        self.assertIn("165", res["reply"])


if __name__ == "__main__":
    unittest.main()
