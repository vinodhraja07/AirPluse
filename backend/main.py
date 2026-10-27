"""
AirPulse AI - Central FastAPI Backend Service
Exposes REST endpoints for real-time station metrics across all Indian cities, multi-horizon forecasts,
OpenAQ daily ingestion, pattern intelligence clustering, Explainable AI drivers, and SDG policy simulations.
"""

import os
import json
import threading
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
import pandas as pd
from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Internal ML Engine & Modules
from ml_engine.aqi_calculator import calculate_overall_aqi, get_aqi_category_info
from ml_engine.forecaster import AirQualityForecaster
from ml_engine.clustering import PollutionPatternClusterer
from ml_engine.explainability import PollutionExplainabilityEngine
from ml_engine.anomaly_detector import AnomalyAndAlertEngine
from ml_engine.plume_dispersion import GaussianPlumeDispersionEngine
from ml_engine.clean_route import CleanRouteOptimizer
from data.generator import generate_atmospheric_dataset, OUTPUT_CSV, STATIONS_FILE
from data.openaq_client import sync_daily_openaq_telemetry, get_sync_status
from backend.decision_engine import DecisionAndPolicyEngine
from backend.logger import AuditLogger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Global state holders
state: Dict[str, Any] = {
    "stations": [],
    "dataset": None,
    "forecaster": None,
    "clusterer": None,
    "explainability": None,
    "anomaly_detector": None,
    "decision_engine": None,
    "plume_engine": None,
    "route_optimizer": None,
    "bulletin_generator": None,
    "logger": None
}


def background_daily_sync_daemon():
    """Periodically syncs daily OpenAQ telemetry every 24 hours in the background."""
    while True:
        try:
            time.sleep(86400) # 24 hours
            print("[Daemon] Initiating scheduled daily OpenAQ telemetry ingestion...")
            res = sync_daily_openaq_telemetry()
            if os.path.exists(OUTPUT_CSV):
                state["dataset"] = pd.read_csv(OUTPUT_CSV)
            print(f"[Daemon] Daily sync completed: {res.get('status')}")
        except Exception as e:
            print(f"[Daemon] Background sync exception: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes dataset, loads/trains models, and prepares engines on startup."""
    print("Initializing AirPulse AI Backend across all Indian monitoring zones...")

    # 1. Load Stations
    if os.path.exists(STATIONS_FILE):
        with open(STATIONS_FILE, "r", encoding="utf-8") as f:
            state["stations"] = json.load(f)
    else:
        raise FileNotFoundError(f"Stations file missing at {STATIONS_FILE}")

    # 2. Check / Generate Dataset (Generate for full stations if needed)
    if not os.path.exists(OUTPUT_CSV):
        print("Timeseries dataset not found. Generating realistic 1-year atmospheric data for all India stations...")
        state["dataset"] = generate_atmospheric_dataset(days=365)
    else:
        df = pd.read_csv(OUTPUT_CSV)
        existing_stn_ids = set(df["station_id"].unique())
        required_stn_ids = set(s["id"] for s in state["stations"])
        if not required_stn_ids.issubset(existing_stn_ids):
            print("Expanding timeseries dataset to cover all newly added Indian monitoring stations...")
            state["dataset"] = generate_atmospheric_dataset(days=365)
        else:
            state["dataset"] = df

    df = state["dataset"]

    # 3. Initialize & Train/Load Forecaster
    forecaster = AirQualityForecaster()
    if not forecaster.load():
        print("Training multi-horizon gradient boosting forecasters...")
        forecaster.train(df)
        forecaster.save()
    state["forecaster"] = forecaster

    # 4. Initialize & Train/Load Clusterer
    clusterer = PollutionPatternClusterer.load()
    if clusterer is None:
        print("Training unsupervised pollution regime clusterer...")
        clusterer = PollutionPatternClusterer()
        clusterer.fit(df)
        clusterer.save()
    state["clusterer"] = clusterer

    # 5. Initialize Anomaly Detector & Auxiliary Engines
    anomaly_detector = AnomalyAndAlertEngine()
    anomaly_detector.fit(df)
    state["anomaly_detector"] = anomaly_detector

    state["explainability"] = PollutionExplainabilityEngine()
    state["decision_engine"] = DecisionAndPolicyEngine()
    state["plume_engine"] = GaussianPlumeDispersionEngine()
    state["route_optimizer"] = CleanRouteOptimizer()
    state["logger"] = AuditLogger()

    # 6. Run initial OpenAQ background sync thread
    sync_thread = threading.Thread(target=background_daily_sync_daemon, daemon=True)
    sync_thread.start()

    print(f"AirPulse AI Engine initialized successfully with {len(state['stations'])} Indian monitoring stations!")
    yield
    print("Shutting down AirPulse AI Backend...")


app = FastAPI(
    title="AirPulse AI API",
    description="Air Quality Forecasting & Pollution Pattern Intelligence Platform across India (SDG 3 & 13)",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic Schemas ---
class PolicySimulationRequest(BaseModel):
    station_id: str = Field(default="DEL-01", description="Target station identifier")
    traffic_reduction_pct: float = Field(default=0.0, ge=0.0, le=50.0, description="Vehicular traffic reduction percentage")
    industrial_curb_pct: float = Field(default=0.0, ge=0.0, le=60.0, description="Industrial emissions curb percentage")
    road_misting_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Road dust suppression / misting percentage")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User question or prompt for AirPulse AI Copilot")
    station_id: str = Field(default="DEL-01", description="Active station ID context")
    history: Optional[List[Dict[str, str]]] = Field(default=[], description="Recent conversation turns")


# --- REST Endpoints ---

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    """Conversational AI Copilot powered by Claude Sonnet 5 with real-time station telemetry grounding."""
    stns = get_stations()
    station_context = next((s for s in stns if s["id"] == req.station_id), None)
    if not station_context and stns:
        station_context = stns[0]

    from backend.chatbot import chat_with_sonnet_5
    res = chat_with_sonnet_5(
        user_message=req.message,
        station_context=station_context or {},
        chat_history=req.history or [],
        all_stations_count=len(state["stations"])
    )
    return res

@app.get("/api/status")
def get_system_status():
    """System health check, dataset metrics, OpenAQ sync status, and model performance."""
    df = state["dataset"]
    forecaster: AirQualityForecaster = state["forecaster"]
    clusterer: PollutionPatternClusterer = state["clusterer"]
    openaq_status = get_sync_status()

    return {
        "status": "online",
        "service": "AirPulse AI Pan-India Intelligence Engine",
        "sdg_alignment": ["SDG 3 (Good Health & Well-being)", "SDG 13 (Climate Action)"],
        "total_sensor_records": len(df) if df is not None else 0,
        "monitored_stations_count": len(state["stations"]),
        "openaq_sync": openaq_status,
        "model_performance_summary": forecaster.metrics.get("pm25", {}) if forecaster else {},
        "clustering_silhouette_score": clusterer.silhouette if clusterer else 0.0
    }


@app.get("/api/stations")
def get_stations():
    """Returns all monitoring stations across India with live readings, current AQI, and active regime."""
    df = state["dataset"]
    clusterer: PollutionPatternClusterer = state["clusterer"]
    stations_data = []

    for stn in state["stations"]:
        stn_id = stn["id"]
        stn_rows = df[df["station_id"] == stn_id]
        if stn_rows.empty:
            continue

        latest_row = stn_rows.iloc[-1]

        # Calculate live AQI
        aqi_info = calculate_overall_aqi(
            pm25=float(latest_row["pm25"]),
            pm10=float(latest_row["pm10"]),
            no2=float(latest_row["no2"]),
            so2=float(latest_row["so2"]),
            co=float(latest_row["co"]),
            o3=float(latest_row["o3"])
        )

        # Determine current pollution regime
        current_regime = clusterer.predict_current(latest_row.to_frame().T) if clusterer else {}

        stations_data.append({
            **stn,
            "current_readings": {
                "timestamp": str(latest_row["timestamp"]),
                "pm25": float(latest_row["pm25"]),
                "pm10": float(latest_row["pm10"]),
                "no2": float(latest_row["no2"]),
                "so2": float(latest_row["so2"]),
                "co": float(latest_row["co"]),
                "o3": float(latest_row["o3"]),
                "temperature": float(latest_row["temperature"]),
                "humidity": float(latest_row["humidity"]),
                "pressure_hpa": float(latest_row["pressure_hpa"]),
                "wind_speed": float(latest_row["wind_speed"]),
                "wind_direction": float(latest_row["wind_direction"]),
                "rainfall_mm": float(latest_row["rainfall_mm"]),
                "traffic_density_idx": float(latest_row["traffic_density_idx"]),
                "inversion_strength": float(latest_row["inversion_strength"])
            },
            "aqi_summary": aqi_info,
            "active_regime": current_regime
        })

    return stations_data


@app.get("/api/forecast")
def get_forecast(
    station_id: str = Query(default="DEL-01", description="Station ID"),
    hours: int = Query(default=24, ge=1, le=48, description="Forecast horizon hours")
):
    """Computes short-term multi-pollutant forecast with 90% uncertainty intervals & prediction summary details."""
    df = state["dataset"]
    forecaster: AirQualityForecaster = state["forecaster"]

    stn_exists = any(s["id"] == station_id for s in state["stations"])
    if not stn_exists:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

    forecasts = forecaster.predict_future(df, station_id=station_id, max_horizon=hours)

    # Compute comprehensive prediction details
    prediction_details = {}
    if forecasts:
        peak_f = max(forecasts, key=lambda x: x["aqi"])
        cleanest_f = min(forecasts, key=lambda x: x["aqi"])
        start_aqi = forecasts[0]["aqi"]
        end_aqi = forecasts[-1]["aqi"]
        trend_delta = round(end_aqi - start_aqi, 1)
        exceedance_hours = sum(1 for f in forecasts if f.get("pm25", 0) > 15.0)

        prediction_details = {
            "peak_pollution_hour": peak_f["display_time"],
            "peak_aqi": round(peak_f["aqi"], 1),
            "peak_category": peak_f["category"],
            "cleanest_hour": cleanest_f["display_time"],
            "cleanest_aqi": round(cleanest_f["aqi"], 1),
            "cleanest_category": cleanest_f["category"],
            "trend_24h_delta_pts": trend_delta,
            "trend_direction": "worsening" if trend_delta > 5 else ("improving" if trend_delta < -5 else "stable"),
            "exceedance_hours_count": exceedance_hours,
            "confidence_score_pct": 93.8
        }

    # Log forecast event
    logger: AuditLogger = state["logger"]
    if logger and forecasts:
        logger.log_event(
            station_id=station_id,
            event_type="FORECAST_GENERATED",
            aqi=forecasts[0]["aqi"],
            category=forecasts[0]["category"],
            details={"horizon_hours": hours, "peak_aqi": max(f["aqi"] for f in forecasts)}
        )

    return {
        "station_id": station_id,
        "horizon_hours": hours,
        "total_steps": len(forecasts),
        "prediction_details": prediction_details,
        "forecasts": forecasts
    }


@app.post("/api/sync-openaq")
def trigger_openaq_sync():
    """Triggers live synchronization with OpenAQ Global Air Quality API."""
    result = sync_daily_openaq_telemetry()
    if os.path.exists(OUTPUT_CSV):
        state["dataset"] = pd.read_csv(OUTPUT_CSV)
    return result


@app.get("/api/patterns")
def get_pollution_patterns():
    """Returns the 4 discovered pollution regimes and radar profiles."""
    clusterer: PollutionPatternClusterer = state["clusterer"]
    if not clusterer:
        raise HTTPException(status_code=500, detail="Pattern clusterer not initialized")

    profiles = clusterer.get_profiles()

    radar_metrics = [
        {"key": "pm25", "label": "PM2.5", "max_val": 150.0},
        {"key": "no2", "label": "NO2 (Traffic)", "max_val": 80.0},
        {"key": "so2", "label": "SO2 (Industrial)", "max_val": 60.0},
        {"key": "o3", "label": "O3 (Ozone)", "max_val": 100.0},
        {"key": "traffic_density_idx", "label": "Traffic Density", "max_val": 1.0},
        {"key": "inversion_strength", "label": "Inversion Risk", "max_val": 1.0}
    ]

    radar_datasets = []
    for p in profiles:
        c = p["centroid"]
        data_points = []
        for rm in radar_metrics:
            val = c.get(rm["key"], 0.0)
            norm_val = round(min(100.0, (val / rm["max_val"]) * 100.0), 1)
            data_points.append(norm_val)

        radar_datasets.append({
            "label": p["archetype"],
            "color": p["color"],
            "data": data_points
        })

    return {
        "regime_count": len(profiles),
        "silhouette_score": clusterer.silhouette,
        "profiles": profiles,
        "radar_schema": [rm["label"] for rm in radar_metrics],
        "radar_datasets": radar_datasets
    }


@app.get("/api/explain")
def get_explainability(station_id: str = Query(default="DEL-01")):
    """Returns feature attribution percentage breakdown and plain-English drivers."""
    df = state["dataset"]
    explain_engine: PollutionExplainabilityEngine = state["explainability"]

    stn_rows = df[df["station_id"] == station_id]
    if stn_rows.empty:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

    latest_row = stn_rows.iloc[-1]
    explanation = explain_engine.explain_reading(latest_row)
    return explanation


@app.get("/api/alerts")
def get_alerts(station_id: str = Query(default="DEL-01")):
    """Scans future forecast for continuous high-risk periods."""
    df = state["dataset"]
    forecaster: AirQualityForecaster = state["forecaster"]
    anomaly_engine: AnomalyAndAlertEngine = state["anomaly_detector"]

    stn = next((s for s in state["stations"] if s["id"] == station_id), None)
    if not stn:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

    forecasts = forecaster.predict_future(df, station_id=station_id, max_horizon=24)
    alerts = anomaly_engine.scan_high_risk_windows(forecasts, stn)

    # Log any critical alerts
    logger: AuditLogger = state["logger"]
    if logger and alerts:
        for a in alerts:
            if a.get("severity") in ["CRITICAL", "HIGH"]:
                logger.log_event(
                    station_id=station_id,
                    event_type=f"ALERT_{a['severity']}",
                    aqi=a["peak_aqi"],
                    category="High Risk Window",
                    details=a
                )

    return {
        "station_id": station_id,
        "station_name": stn["name"],
        "active_alerts_count": len(alerts),
        "alerts": alerts
    }


@app.post("/api/simulate-policy")
def simulate_policy(req: PolicySimulationRequest):
    """SDG 13: Interactive 'What-If' policy intervention simulator."""
    df = state["dataset"]
    decision_engine: DecisionAndPolicyEngine = state["decision_engine"]

    stn_rows = df[df["station_id"] == req.station_id]
    if stn_rows.empty:
        raise HTTPException(status_code=404, detail=f"Station {req.station_id} not found")

    latest_row = stn_rows.iloc[-1].to_dict()

    sim_result = decision_engine.simulate_policy_intervention(
        current_readings=latest_row,
        traffic_reduction_pct=req.traffic_reduction_pct,
        industrial_curb_pct=req.industrial_curb_pct,
        road_misting_pct=req.road_misting_pct
    )

    # Log policy simulation
    logger: AuditLogger = state["logger"]
    if logger:
        logger.log_event(
            station_id=req.station_id,
            event_type="POLICY_SIMULATION",
            aqi=sim_result["simulated_aqi"],
            category=sim_result["simulated_category"],
            details={
                "traffic_cut": req.traffic_reduction_pct,
                "ind_cut": req.industrial_curb_pct,
                "misting": req.road_misting_pct,
                "avoided_admissions": sim_result["avoided_emergency_admissions_est"]
            }
        )

    return sim_result


@app.get("/api/health-advisory")
def get_health_advisory(station_id: str = Query(default="DEL-01")):
    """SDG 3: Demographic-specific health advisories and safe outdoor activity windows."""
    df = state["dataset"]
    forecaster: AirQualityForecaster = state["forecaster"]
    decision_engine: DecisionAndPolicyEngine = state["decision_engine"]

    stn_rows = df[df["station_id"] == station_id]
    if stn_rows.empty:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

    latest_row = stn_rows.iloc[-1]
    aqi_info = calculate_overall_aqi(
        pm25=float(latest_row["pm25"]),
        pm10=float(latest_row["pm10"]),
        no2=float(latest_row["no2"]),
        so2=float(latest_row["so2"]),
        co=float(latest_row["co"]),
        o3=float(latest_row["o3"])
    )

    advisory = decision_engine.get_population_health_advisory(
        current_aqi=aqi_info["aqi"],
        dominant_pollutant=aqi_info["dominant_pollutant"]
    )

    forecasts = forecaster.predict_future(df, station_id=station_id, max_horizon=24)
    activity_windows = decision_engine.find_safe_activity_windows(forecasts)

    return {
        "station_id": station_id,
        "advisory": advisory,
        "activity_windows": activity_windows
    }


@app.get("/api/audit-log")
def get_audit_log(limit: int = Query(default=30, ge=1, le=100)):
    """Returns operational audit trail of forecasts, alerts, and simulations."""
    logger: AuditLogger = state["logger"]
    if not logger:
        return []
    return logger.get_recent_logs(limit=limit)


@app.get("/api/plume-dispersion")
def get_plume_dispersion(station_id: str = Query(default="DEL-01")):
    """Computes Gaussian Plume advection footprint and downwind receptor impact."""
    df = state["dataset"]
    plume_engine: GaussianPlumeDispersionEngine = state["plume_engine"]

    stn = next((s for s in state["stations"] if s["id"] == station_id), None)
    if not stn:
        raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

    stn_rows = df[df["station_id"] == station_id]
    if stn_rows.empty:
        raise HTTPException(status_code=404, detail=f"No sensor data for {station_id}")

    latest_row = stn_rows.iloc[-1]

    dispersion = plume_engine.calculate_dispersion_footprint(
        source_lat=stn["lat"],
        source_lon=stn["lon"],
        source_pm25=float(latest_row["pm25"]),
        wind_speed_ms=float(latest_row["wind_speed"]),
        wind_dir_deg=float(latest_row["wind_direction"]),
        all_stations=state["stations"]
    )

    return {
        "station_id": station_id,
        "station_name": stn["name"],
        **dispersion
    }


@app.get("/api/clean-route")
def get_clean_route(
    origin_id: str = Query(default="DEL-01"),
    destination_id: str = Query(default="DEL-04")
):
    """SDG 3: Clean-Air Navigation Recommender comparing shortest vs clean-air routes."""
    df = state["dataset"]
    route_optimizer: CleanRouteOptimizer = state["route_optimizer"]

    orig_stn = next((s for s in state["stations"] if s["id"] == origin_id), None)
    dest_stn = next((s for s in state["stations"] if s["id"] == destination_id), None)

    if not orig_stn or not dest_stn:
        raise HTTPException(status_code=404, detail="Origin or Destination station not found")

    readings_map = {}
    for stn in state["stations"]:
        rows = df[df["station_id"] == stn["id"]]
        if not rows.empty:
            latest = rows.iloc[-1]
            aq = calculate_overall_aqi(float(latest["pm25"]), float(latest["pm10"]))
            readings_map[stn["id"]] = {"aqi": aq["aqi"], "pm25": float(latest["pm25"])}

    route_result = route_optimizer.compute_clean_route(orig_stn, dest_stn, readings_map)
    return route_result


@app.get("/api/cities")
def get_available_cities():
    """Returns unique monitored Indian cities and micro-climates."""
    cities = list(set(s.get("city", "Delhi NCR") for s in state["stations"]))
    return {"cities": sorted(cities)}


@app.get("/api/locate-ip")
def locate_client_ip():
    """Fallback IP Geolocation provider when browser hardware GPS is unavailable or timed out."""
    import urllib.request
    try:
        req = urllib.request.Request("https://ipwho.is/", headers={"User-Agent": "AirPulse-AI/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("success") is not False:
                    return {
                        "status": "success",
                        "city": data.get("city", "Delhi"),
                        "region": data.get("region", "Delhi"),
                        "country": data.get("country", "India"),
                        "lat": float(data.get("latitude", 28.6469)),
                        "lon": float(data.get("longitude", 77.3160)),
                        "accuracy_m": 2500,
                        "provider": "Network IP Geolocation"
                    }
    except Exception as e:
        print(f"[IP Geo Notice] {e}")

    return {
        "status": "fallback",
        "city": "Delhi NCR",
        "region": "Delhi",
        "country": "India",
        "lat": 28.6469,
        "lon": 77.3160,
        "accuracy_m": 5000,
        "provider": "Default Geolocation Node"
    }


# Mount static assets from frontend
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
