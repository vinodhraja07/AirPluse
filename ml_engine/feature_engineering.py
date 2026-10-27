"""
AirPulse AI - Feature Engineering & Atmospheric Dynamics Pipeline
Computes cyclical temporal encodings, wind vectors, inversion metrics,
pollutant cross-ratios, and multi-step autoregressive lag windows.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Optional


class AirQualityFeaturePipeline:
    def __init__(self, lag_hours: List[int] = None, rolling_windows: List[int] = None):
        self.lag_hours = lag_hours or [1, 2, 3, 6, 12, 24]
        self.rolling_windows = rolling_windows or [6, 24]
        self.pollutant_cols = ["pm25", "pm10", "no2", "so2", "co", "o3"]
        self.meteo_cols = ["temperature", "humidity", "pressure_hpa", "wind_speed", "wind_direction", "rainfall_mm"]
        self.feature_columns: List[str] = []

    def create_features(self, df: pd.DataFrame, is_training: bool = True) -> pd.DataFrame:
        """
        Transforms raw time-series into rich feature matrix per station.
        """
        df = df.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values(by=["station_id", "timestamp"]).reset_index(drop=True)

            # 1. Cyclical Time Encodings
            hour = df["timestamp"].dt.hour
            dow = df["timestamp"].dt.dayofweek
            month = df["timestamp"].dt.month

            df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
            df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
            df["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
            df["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)
            df["month_sin"] = np.sin(2 * np.pi * (month - 1) / 12.0)
            df["month_cos"] = np.cos(2 * np.pi * (month - 1) / 12.0)
            df["is_weekend"] = (dow >= 5).astype(float)

            # Peak traffic indicator flags
            df["is_morning_rush"] = ((hour >= 7) & (hour <= 10)).astype(float)
            df["is_evening_rush"] = ((hour >= 17) & (hour <= 21)).astype(float)

        # 2. Wind Vector Decomposition (u=East/West, v=North/South)
        if "wind_speed" in df.columns and "wind_direction" in df.columns:
            wind_rad = np.deg2rad(df["wind_direction"])
            df["wind_u"] = -df["wind_speed"] * np.sin(wind_rad)
            df["wind_v"] = -df["wind_speed"] * np.cos(wind_rad)
            df["wind_stagnancy_idx"] = np.clip(1.0 / (df["wind_speed"] + 0.4), 0.0, 5.0)

        # 3. Chemical Ratios & Atmospheric Dynamics
        if "pm25" in df.columns and "pm10" in df.columns:
            df["pm_fine_coarse_ratio"] = df["pm25"] / (df["pm10"] + 1e-5)

        if "no2" in df.columns and "o3" in df.columns:
            df["photochemical_ratio"] = df["no2"] / (df["o3"] + 1e-5)

        if "temperature" in df.columns and "humidity" in df.columns:
            # Dewpoint approximation (Magnus-Tetens formula simplified)
            df["dew_point_diff"] = df["temperature"] - ((100 - df["humidity"]) / 5.0)

        # 4. Lag and Rolling features (calculated per station to avoid data leakage)
        feature_dfs = []
        for station_id, group in df.groupby("station_id"):
            group = group.copy().sort_values(by="timestamp")

            # Target pollutants & meteo lags
            targets = [c for c in self.pollutant_cols + ["wind_speed", "temperature", "humidity"] if c in group.columns]
            new_cols = {}

            for col in targets:
                for lag in self.lag_hours:
                    new_cols[f"{col}_lag_{lag}h"] = group[col].shift(lag)

                for w in self.rolling_windows:
                    new_cols[f"{col}_roll_mean_{w}h"] = group[col].rolling(window=w, min_periods=1).mean()
                    new_cols[f"{col}_roll_std_{w}h"] = group[col].rolling(window=w, min_periods=1).std().fillna(0)
                    new_cols[f"{col}_roll_max_{w}h"] = group[col].rolling(window=w, min_periods=1).max()

            new_cols_df = pd.DataFrame(new_cols, index=group.index)
            group = pd.concat([group, new_cols_df], axis=1)

            # Inversion proxy: 24h max temp minus current temp divided by wind
            if "temperature_roll_max_24h" in group.columns and "wind_speed" in group.columns:
                group["thermal_inversion_proxy"] = (group["temperature_roll_max_24h"] - group["temperature"]) / (group["wind_speed"] + 0.5)

            feature_dfs.append(group)

        full_features_df = pd.concat(feature_dfs).sort_index()

        # Drop initial rows with NaNs from lag creation if training
        if is_training:
            full_features_df = full_features_df.dropna().reset_index(drop=True)

        # Store feature columns (exclude non-feature metadata and station_id)
        ignore_cols = ["timestamp", "station_id", "station_name", "station_type", "aqi_category", "ground_aqi"] + self.pollutant_cols
        self.feature_columns = [c for c in full_features_df.columns if c not in ignore_cols and not c.startswith("target_")]

        return full_features_df

    def get_feature_names(self) -> List[str]:
        return self.feature_columns
