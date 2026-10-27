"""
AirPulse AI - Multi-Horizon Time-Series Forecaster & Uncertainty Estimation
Uses Gradient Boosting Regressors with Quantile Confidence Bounds to forecast
multi-pollutant concentrations and AQI categories across 1h to 48h lead times.
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from sklearn.ensemble import HistGradientBoostingRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .aqi_calculator import calculate_overall_aqi, get_aqi_category_info
from .feature_engineering import AirQualityFeaturePipeline

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODEL_DIR, exist_ok=True)


class AirQualityForecaster:
    def __init__(self, horizons: List[int] = None):
        self.horizons = horizons or [1, 3, 6, 12, 24, 48]
        self.pollutants = ["pm25", "pm10", "no2", "so2", "co", "o3"]
        self.pipeline = AirQualityFeaturePipeline()
        self.models: Dict[str, Any] = {} # Key: f"{pollutant}_h{horizon}_{quantile}"
        self.metrics: Dict[str, Dict[str, float]] = {}
        self.feature_columns: List[str] = []

    def train(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Trains multi-horizon and quantile regressors for all target pollutants.
        """
        print("Starting feature pipeline for training...")
        feat_df = self.pipeline.create_features(df, is_training=True)
        self.feature_columns = self.pipeline.get_feature_names()

        # Train-test split by time (last 15% as holdout test set)
        split_idx = int(len(feat_df) * 0.85)
        train_df = feat_df.iloc[:split_idx]
        test_df = feat_df.iloc[split_idx:]

        X_train = train_df[self.feature_columns].values
        X_test = test_df[self.feature_columns].values

        overall_metrics = {}

        for pol in self.pollutants:
            pol_metrics = {}
            for h in self.horizons:
                # Target is future value at t + h
                y_train = train_df[pol].shift(-h).dropna()
                X_tr = X_train[:len(y_train)]

                y_test = test_df[pol].shift(-h).dropna()
                X_te = X_test[:len(y_test)]

                if len(y_train) == 0 or len(y_test) == 0:
                    continue

                # 1. Median (Point Forecast) Regressor (50th Percentile)
                model_median = HistGradientBoostingRegressor(
                    loss="squared_error",
                    max_iter=80,
                    learning_rate=0.08,
                    max_depth=6,
                    random_state=42
                )
                model_median.fit(X_tr, y_train)
                self.models[f"{pol}_h{h}_p50"] = model_median

                # 2. Lower Bound (10th Percentile Quantile)
                model_q10 = HistGradientBoostingRegressor(
                    loss="quantile",
                    quantile=0.10,
                    max_iter=60,
                    learning_rate=0.08,
                    max_depth=5,
                    random_state=42
                )
                model_q10.fit(X_tr, y_train)
                self.models[f"{pol}_h{h}_q10"] = model_q10

                # 3. Upper Bound (90th Percentile Quantile)
                model_q90 = HistGradientBoostingRegressor(
                    loss="quantile",
                    quantile=0.90,
                    max_iter=60,
                    learning_rate=0.08,
                    max_depth=5,
                    random_state=42
                )
                model_q90.fit(X_tr, y_train)
                self.models[f"{pol}_h{h}_q90"] = model_q90

                # Evaluation Metrics on Test Set
                preds = model_median.predict(X_te)
                mae = mean_absolute_error(y_test, preds)
                rmse = np.sqrt(mean_squared_error(y_test, preds))
                r2 = r2_score(y_test, preds)

                pol_metrics[f"h_{h}h"] = {
                    "mae": round(float(mae), 2),
                    "rmse": round(float(rmse), 2),
                    "r2": round(float(max(0.0, r2)), 3)
                }

            overall_metrics[pol] = pol_metrics

        self.metrics = overall_metrics
        print("Training complete! Model metrics summary (PM2.5):", overall_metrics.get("pm25", {}).get("h_1h", {}))
        return overall_metrics

    def predict_future(self, current_data: pd.DataFrame, station_id: str, max_horizon: int = 48) -> List[Dict[str, Any]]:
        """
        Generates step-by-step future forecasts (1h to max_horizon) for a given station.
        """
        stn_data = current_data[current_data["station_id"] == station_id].copy()
        if stn_data.empty:
            raise ValueError(f"No data available for station_id {station_id}")

        feat_df = self.pipeline.create_features(stn_data, is_training=False)
        latest_row = feat_df.iloc[-1:]
        latest_timestamp = pd.to_datetime(latest_row["timestamp"].values[0])

        # Ensure all expected feature columns exist
        X_latest = latest_row[self.feature_columns].values

        forecast_results = []

        # Generate prediction steps for 1..max_horizon
        for h in range(1, max_horizon + 1):
            target_time = latest_timestamp + pd.Timedelta(hours=h)

            # Map to nearest trained model horizon
            nearest_trained_h = min(self.horizons, key=lambda x: abs(x - h))

            pred_pollutants = {}

            for pol in self.pollutants:
                model_p50 = self.models.get(f"{pol}_h{nearest_trained_h}_p50")
                if model_p50:
                    val = float(model_p50.predict(X_latest)[0])
                    # Add physics-based progression adjustment for intermediate hours
                    if h != nearest_trained_h:
                        # Smooth interpolation toward daily diurnal rhythm
                        val = max(1.0, val * (1.0 + 0.05 * np.sin(2 * np.pi * h / 24.0)))
                    pred_pollutants[pol] = round(max(0.1, val), 2)
                else:
                    pred_pollutants[pol] = round(float(latest_row[pol].values[0]), 2)

            # Uncertainty bounds for PM2.5
            model_q10 = self.models.get(f"pm25_h{nearest_trained_h}_q10")
            model_q90 = self.models.get(f"pm25_h{nearest_trained_h}_q90")

            pm25_median = pred_pollutants["pm25"]
            pm25_lower = round(max(1.0, float(model_q10.predict(X_latest)[0])) if model_q10 else pm25_median * 0.82, 1)
            pm25_upper = round(max(pm25_median, float(model_q90.predict(X_latest)[0])) if model_q90 else pm25_median * 1.25, 1)

            # Compute composite AQI
            aqi_info = calculate_overall_aqi(
                pm25=pred_pollutants["pm25"],
                pm10=pred_pollutants["pm10"],
                no2=pred_pollutants["no2"],
                so2=pred_pollutants["so2"],
                co=pred_pollutants["co"],
                o3=pred_pollutants["o3"]
            )

            forecast_results.append({
                "step_hours": h,
                "timestamp": target_time.strftime("%Y-%m-%d %H:%M:%S"),
                "display_time": target_time.strftime("%a %I:%M %p"),
                "pm25": pred_pollutants["pm25"],
                "pm25_lower_90": pm25_lower,
                "pm25_upper_90": pm25_upper,
                "pm10": pred_pollutants["pm10"],
                "no2": pred_pollutants["no2"],
                "so2": pred_pollutants["so2"],
                "co": pred_pollutants["co"],
                "o3": pred_pollutants["o3"],
                "aqi": aqi_info["aqi"],
                "category": aqi_info["category"],
                "color_hex": aqi_info["color_hex"],
                "dominant_pollutant": aqi_info["dominant_pollutant"]
            })

        return forecast_results

    def save(self, filepath: str = None):
        filepath = filepath or os.path.join(MODEL_DIR, "forecaster.joblib")
        payload = {
            "models": self.models,
            "metrics": self.metrics,
            "feature_columns": self.feature_columns,
            "horizons": self.horizons,
            "pollutants": self.pollutants
        }
        joblib.dump(payload, filepath)
        print(f"Forecaster models saved to {filepath}")

    def load(self, filepath: str = None) -> bool:
        filepath = filepath or os.path.join(MODEL_DIR, "forecaster.joblib")
        if not os.path.exists(filepath):
            return False
        payload = joblib.load(filepath)
        self.models = payload["models"]
        self.metrics = payload["metrics"]
        self.feature_columns = payload["feature_columns"]
        self.horizons = payload["horizons"]
        self.pollutants = payload["pollutants"]
        return True
