"""
AirPulse AI - 1-Click Platform Launcher
Orchestrates environment verification, synthetic data generation, ML training,
FastAPI server execution, and dashboard browser opening.
"""

import os
import sys
import webbrowser
import time
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_CSV = os.path.join(BASE_DIR, "data", "aqi_timeseries.csv")


def main():
    print("=" * 70)
    print("🌍 AIRPULSE AI — AIR QUALITY INTELLIGENCE PLATFORM (SDG 3 & 13)")
    print("=" * 70)

    # 1. Check / Generate Dataset
    if not os.path.exists(DATA_CSV):
        print("\n[Step 1/3] Generating synthetic 1-year atmospheric multi-station dataset...")
        from data.generator import generate_atmospheric_dataset
        generate_atmospheric_dataset(days=365)
        print("✓ Dataset generated successfully.")
    else:
        print("\n[Step 1/3] Found existing dataset at:", DATA_CSV)

    # 2. Pre-flight Model Check
    print("\n[Step 2/3] Checking ML models & pattern intelligence...")
    from ml_engine.forecaster import AirQualityForecaster
    from ml_engine.clustering import PollutionPatternClusterer
    import pandas as pd

    forecaster = AirQualityForecaster()
    if not forecaster.load():
        print("Training multi-horizon forecast models...")
        df = pd.read_csv(DATA_CSV)
        forecaster.train(df)
        forecaster.save()

    clusterer = PollutionPatternClusterer.load()
    if clusterer is None:
        print("Training pollution regime clusterer...")
        df = pd.read_csv(DATA_CSV)
        clusterer = PollutionPatternClusterer()
        clusterer.fit(df)
        clusterer.save()

    print("✓ Machine learning models ready.")

    # 3. Launch Server on standard port
    import socket
    def find_free_port(preferred_port=8080):
        for p in [preferred_port, 8000, 8888, 5000, 8008]:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', p)) != 0:
                    return p
        return preferred_port

    env_port = int(os.environ.get("PORT", 8080))
    port = find_free_port(env_port)
    host = "127.0.0.1"
    url = f"http://{host}:{port}"
    print(f"\n[Step 3/3] Starting FastAPI Server on {url}...")
    print("Opening web dashboard in your browser...")

    # Open browser slightly after server startup
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(url)

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    from backend.main import app
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
