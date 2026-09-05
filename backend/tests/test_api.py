import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"

def test_instant_prediction_zone_a():
    payload = {
        "node_id": "NODE_A1",
        "zone_id": "Zone A",
        "tilt_x_deg": 0.02,
        "tilt_y_deg": -0.01,
        "displacement_mm": 0.45,
        "strain_ue": 92.5,
        "vibration_amp": 0.015
    }
    response = client.post("/api/v1/telemetry/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_risk"] == "Normal"

def test_instant_prediction_zone_c():
    payload = {
        "node_id": "NODE_C1",
        "zone_id": "Zone C",
        "tilt_x_deg": 4.5,
        "tilt_y_deg": 3.8,
        "displacement_mm": 35.0,
        "strain_ue": 780.0,
        "vibration_amp": 2.1
    }
    response = client.post("/api/v1/telemetry/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_risk"] == "Critical"

def test_ingest_wifi_telemetry_gateway():
    """Validates HTTP POST ingestion emitted by ESP32 Gateway over WiFi."""
    gateway_payload = {
        "seq": 1042,
        "node_id": "NODE_B1",
        "zone_id": "Zone B",
        "timestamp_ms": 128450,
        "tilt_x_deg": 1.25,
        "tilt_y_deg": 0.85,
        "displacement_mm": 8.40,
        "strain_ue": 290.0,
        "vibration_amp": 0.32,
        "shock_count": 2,
        "dropped_packets": 0,
        "rssi_dbm": -68,
        "snr_db": "8.5",
        "freq_err_hz": 120,
        "gateway_id": "GATEWAY_SURFACE_01",
        "gateway_uptime_ms": 320000
    }
    response = client.post("/api/v1/telemetry/ingest", json=gateway_payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "ACK"
    assert res_data["node_id"] == "NODE_B1"
    assert "server_timestamp" in res_data

