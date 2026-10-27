"""
AirPulse AI - Municipal Action & Forecast Audit Logger
Maintains a tamper-evident operational log of forecasts, alerts, and simulated policy triggers.
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_trail.db")


class AuditLogger:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    station_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    aqi REAL NOT NULL,
                    category TEXT NOT NULL,
                    details TEXT NOT NULL
                )
            """)
            conn.commit()

    def log_event(
        self,
        station_id: str,
        event_type: str,
        aqi: float,
        category: str,
        details: Dict[str, Any]
    ):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs (timestamp, station_id, event_type, aqi, category, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                station_id,
                event_type,
                aqi,
                category,
                json.dumps(details)
            ))
            conn.commit()

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, timestamp, station_id, event_type, aqi, category, details
                FROM audit_logs
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "station_id": r[2],
                "event_type": r[3],
                "aqi": r[4],
                "category": r[5],
                "details": json.loads(r[6])
            }
            for r in rows
        ]
