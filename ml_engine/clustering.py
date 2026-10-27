"""
AirPulse AI - Pollution Pattern Intelligence & Regime Clustering
Discovers recurring pollution archetypes using K-Means and PCA for visualization.
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score


MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODEL_DIR, exist_ok=True)

ARCHETYPES = {
    0: {
        "name": "Morning Vehicular Rush",
        "short_name": "Traffic Surge",
        "description": "Elevated NO2, CO, and fine PM during commuter peaks with moderate wind stagnancy.",
        "icon": "🚗",
        "color": "#F97316",
        "action": "Prioritize traffic diversions and public transit incentives."
    },
    1: {
        "name": "Winter Stagnant Inversion",
        "short_name": "Inversion Trap",
        "description": "Cold, humid, calm-air conditions trap PM2.5 and PM10 close to the ground for multi-hour episodes.",
        "icon": "🌫️",
        "color": "#8B5CF6",
        "action": "Issue sensitive-group warnings and pause high-dust construction."
    },
    2: {
        "name": "Photochemical Ozone Peak",
        "short_name": "Ozone Bloom",
        "description": "Strong afternoon sunlight converts NO2 precursors into elevated ground-level ozone.",
        "icon": "☀️",
        "color": "#FBBF24",
        "action": "Recommend outdoor activity before 11 AM or after sunset."
    },
    3: {
        "name": "Nocturnal Industrial Discharge",
        "short_name": "Industry Venting",
        "description": "Night-time industrial activity elevates SO2 and particulate concentrations in a stable boundary layer.",
        "icon": "🏭",
        "color": "#EF4444",
        "action": "Trigger source inspection and enforce overnight emission caps."
    }
}


class PollutionPatternClusterer:
    def __init__(self, n_clusters: int = 4):
        self.n_clusters = n_clusters
        self.model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=2, random_state=42)
        self.feature_cols = [
            "pm25", "pm10", "no2", "so2", "co", "o3",
            "temperature", "humidity", "wind_speed",
            "traffic_density_idx", "industrial_activity_idx", "inversion_strength"
        ]
        self.cluster_profiles: Dict[int, Any] = {}
        self.silhouette = 0.0
        self.is_trained = False

    def fit(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Trains K-Means on atmospheric and emission profiles."""
        available_cols = [c for c in self.feature_cols if c in df.columns]
        features = df[available_cols].fillna(0.0)

        # Downsample for clustering to save RAM directly
        if len(features) > 10000:
            features = features.sample(10000, random_state=42)

        scaled = self.scaler.fit_transform(features)
        labels = self.model.fit_predict(scaled)

        if len(set(labels)) > 1:
            # Calculate silhouette on bounded subset to prevent memory thrashing
            sil_len = min(4000, len(scaled))
            self.silhouette = float(silhouette_score(scaled[:sil_len], labels[:sil_len]))
        else:
            self.silhouette = 0.0

        # PCA projection for 2D scatter plots
        pca_coords = self.pca.fit_transform(scaled)

        # Derive cluster profiles based on normalized feature means
        raw_centers = self.scaler.inverse_transform(self.model.cluster_centers_)
        self.cluster_profiles = {}

        # Heuristic mapping to ensure named archetypes align with physical signals
        mapping = self._map_clusters_to_archetypes(pd.DataFrame(raw_centers, columns=available_cols))

        total_pts = len(labels)
        for cluster_idx in range(self.n_clusters):
            archetype_idx = mapping.get(cluster_idx, cluster_idx)
            profile = ARCHETYPES.get(archetype_idx, ARCHETYPES[0])
            cluster_mask = (labels == cluster_idx)
            cluster_count = int(np.sum(cluster_mask))
            pop_share = round((cluster_count / max(1, total_pts)) * 100, 1)

            pca_x = round(float(np.mean(pca_coords[cluster_mask, 0])), 3) if cluster_count > 0 else 0.0
            pca_y = round(float(np.mean(pca_coords[cluster_mask, 1])), 3) if cluster_count > 0 else 0.0

            centroid_dict = {col: round(float(raw_centers[cluster_idx][i]), 2) for i, col in enumerate(available_cols)}
            self.cluster_profiles[cluster_idx] = {
                "cluster_id": cluster_idx,
                "archetype_id": archetype_idx,
                "archetype": profile["name"],
                "short_name": profile["short_name"],
                "description": profile["description"],
                "icon": profile["icon"],
                "color": profile["color"],
                "recommended_action": profile["action"],
                "centroid": centroid_dict,
                "population_share": pop_share,
                "silhouette_score": round(self.silhouette, 3),
                "pca_center": {
                    "x": pca_x,
                    "y": pca_y,
                }
            }

        self.is_trained = True
        self.feature_cols = available_cols
        return {"labeled_data": df, "profiles": self.cluster_profiles, "silhouette_score": self.silhouette}

    def _map_clusters_to_archetypes(self, centers: pd.DataFrame) -> Dict[int, int]:
        """Map arbitrary K-Means ids to stable semantic archetypes using normalized signals."""
        mapping = {}
        used = set()

        # Find rush: high traffic + high NO2
        if "traffic_density_idx" in centers and "no2" in centers:
            score = centers["traffic_density_idx"] + centers["no2"] / max(centers["no2"].max(), 1)
            idx = int(score.idxmax())
            mapping[idx] = 0
            used.add(idx)

        # Find inversion: high inversion + PM25, low wind
        remaining = [i for i in centers.index if i not in used]
        if remaining and "inversion_strength" in centers:
            score = centers.loc[remaining, "inversion_strength"] + centers.loc[remaining, "pm25"] / max(centers["pm25"].max(), 1) - centers.loc[remaining, "wind_speed"] / max(centers["wind_speed"].max(), 1)
            idx = int(score.idxmax())
            mapping[idx] = 1
            used.add(idx)

        # Find ozone: high O3 + temperature
        remaining = [i for i in centers.index if i not in used]
        if remaining and "o3" in centers:
            score = centers.loc[remaining, "o3"] + centers.loc[remaining, "temperature"]
            idx = int(score.idxmax())
            mapping[idx] = 2
            used.add(idx)

        # Remaining cluster is industrial
        for idx in centers.index:
            if idx not in mapping:
                mapping[idx] = 3

        return mapping

    def predict_current(self, row: pd.DataFrame) -> Dict[str, Any]:
        """Classifies a current reading into a named pollution regime."""
        if not self.is_trained:
            raise RuntimeError("Clusterer must be fitted before predicting.")
        features = row[self.feature_cols].fillna(0.0)
        scaled = self.scaler.transform(features)
        label = int(self.model.predict(scaled)[0])
        profile = self.cluster_profiles[label]

        return {
            "cluster_id": label,
            "archetype": profile["archetype"],
            "short_name": profile["short_name"],
            "description": profile["description"],
            "icon": profile["icon"],
            "color": profile["color"],
            "recommended_action": profile["recommended_action"]
        }

    def get_profiles(self) -> List[Dict[str, Any]]:
        return list(self.cluster_profiles.values())

    def save(self, filepath: str = None):
        filepath = filepath or os.path.join(MODEL_DIR, "clusterer.joblib")
        joblib.dump(self, filepath)

    @classmethod
    def load(cls, filepath: str = None):
        filepath = filepath or os.path.join(MODEL_DIR, "clusterer.joblib")
        if os.path.exists(filepath):
            return joblib.load(filepath)
        return None
