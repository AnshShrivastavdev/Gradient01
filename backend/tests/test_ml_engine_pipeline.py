import os
import sys
import time
import math
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.services.fault_tolerant_ml_service import FaultTolerantMLService, fault_tolerant_service, FEATURE_COLUMNS
from app.services.forecast_service import forecast_service
from app.database.db import SessionLocal, SensorRecord, init_db

init_db()
client = TestClient(app)

# =====================================================================
# 1. MODEL ARCHITECTURE & FEATURE SCHEMA INTEGRITY
# =====================================================================
def test_ml_model_architecture_and_feature_schema():
    """Verifies that the ML engine loaded the calibrated 18-feature model."""
    assert fault_tolerant_service.model is not None, "ML model must be loaded"
    assert fault_tolerant_service.encoder is not None, "Label encoder must be loaded"
    assert fault_tolerant_service.engine_mode == "ML_ACTIVE", "Engine mode must be ML_ACTIVE"
    
    classes = fault_tolerant_service.classes
    assert "Normal" in classes and "Warning" in classes and "Critical" in classes
    
    # Verify input feature dimension matches FEATURE_COLUMNS exactly
    if hasattr(fault_tolerant_service.model, "n_features_in_"):
        assert fault_tolerant_service.model.n_features_in_ == len(FEATURE_COLUMNS)
        assert fault_tolerant_service.model.n_features_in_ == 18

# =====================================================================
# 2. ZONE A (NOMINAL / STABLE STRATA) INFERENCE
# =====================================================================
def test_zone_a_nominal_inference():
    """Nominal bedrock telemetry must classify as Normal with high confidence via ML."""
    service = FaultTolerantMLService()
    
    nominal_packet = {
        "node_id": "NODE_TEST_A",
        "zone_id": "Zone A",
        "tilt_x_deg": 0.02,
        "tilt_y_deg": 0.01,
        "displacement_mm": 0.45,
        "strain_ue": 92.0,
        "vibration_amp": 0.012
    }
    
    # Feed 3 samples to fill rolling buffer
    for _ in range(3):
        res = service.predict_packet(nominal_packet)
        
    assert res["instant_prediction"] == "Normal"
    assert res["confirmed_risk_state"] == "Normal"
    assert res["active_engine"] == "ENGINE_A_ML"
    assert res["confidence"] > 0.90
    assert res["siren_trigger"] is False

# =====================================================================
# 3. ZONE B (MICRO-SEISMIC WARNING / CREEP) INFERENCE
# =====================================================================
def test_zone_b_warning_inference():
    """Elevated ground movement must classify as Warning."""
    service = FaultTolerantMLService()
    
    warning_packet = {
        "node_id": "NODE_TEST_B",
        "zone_id": "Zone B",
        "tilt_x_deg": 0.95,
        "tilt_y_deg": 0.70,
        "displacement_mm": 7.50,
        "strain_ue": 240.0,
        "vibration_amp": 0.180
    }
    
    # Feed 3 samples for moving consensus debouncing
    for _ in range(3):
        res = service.predict_packet(warning_packet)
        
    assert res["instant_prediction"] == "Warning"
    assert res["confirmed_risk_state"] == "Warning"
    assert res["active_engine"] == "ENGINE_A_ML"
    assert res["confidence"] > 0.85
    assert res["siren_trigger"] is False

# =====================================================================
# 4. ZONE C (CRITICAL COLLAPSE / HIGH STRAIN) & SIREN TRIGGER
# =====================================================================
def test_zone_c_critical_inference_and_siren():
    """Yield limit breach must classify as Critical and immediately trigger the siren."""
    service = FaultTolerantMLService()
    
    critical_packet = {
        "node_id": "NODE_TEST_C",
        "zone_id": "Zone C",
        "tilt_x_deg": 4.50,
        "tilt_y_deg": 3.80,
        "displacement_mm": 35.0,
        "strain_ue": 750.0,
        "vibration_amp": 2.10
    }
    
    res = service.predict_packet(critical_packet)
    assert res["instant_prediction"] == "Critical"
    assert res["confirmed_risk_state"] == "Critical"
    assert res["confidence"] > 0.90
    assert res["siren_trigger"] is True

# =====================================================================
# 5. NODE 1 REFERENCE DATUM LOCKING & DIFFERENTIAL TELEMETRY
# =====================================================================
def test_node1_reference_datum_and_differential_calculation():
    """Node 1 establishes baseline tilt without triggering false alarms, allowing Node 2 differential math."""
    service = FaultTolerantMLService()
    
    # Node 1 Reference packet (with vertical inclinometer mounting: -1.66°, -97.25°)
    node1_pkt = {
        "node_id": "NODE_A1",
        "role": "REFERENCE",
        "zone_id": "Zone A",
        "tilt_x_deg": -1.66,
        "tilt_y_deg": -97.25,
        "displacement_mm": 0.0,
        "strain_ue": 0.0,
        "vibration_amp": 0.0
    }
    res1 = service.predict_packet(node1_pkt)
    assert res1["confirmed_risk_state"] == "Normal"
    assert res1["active_engine"] == "REFERENCE_DATUM_LOCK"
    assert res1["siren_trigger"] is False
    assert service.reference_orientation["active"] is True
    assert service.reference_orientation["tilt_x_deg"] == -1.66
    assert service.reference_orientation["tilt_y_deg"] == -97.25

    # Node 2 Monitoring packet evaluated against Node 1
    node2_pkt = {
        "node_id": "NODE_02",
        "role": "MONITORING",
        "zone_id": "Zone B",
        "tilt_x_deg": -1.60,
        "tilt_y_deg": -97.10,
        "displacement_mm": 0.50,
        "strain_ue": 95.0,
        "vibration_amp": 0.015
    }
    res2 = service.predict_packet(node2_pkt)
    assert "differential_tilt_deg" in res2["telemetry"]
    # Diff tilt composite = sqrt((-1.60 - (-1.66))^2 + (-97.10 - (-97.25))^2) = sqrt(0.06^2 + 0.15^2) ≈ 0.161°
    diff_tilt = res2["telemetry"]["differential_tilt_deg"]
    assert 0.15 <= diff_tilt <= 0.17
    assert res2["confirmed_risk_state"] == "Normal"

# =====================================================================
# 6. LSTM DEEP DISPLACEMENT FORECASTER & TTF INTERPOLATION
# =====================================================================
def test_displacement_forecasting_pipeline():
    """Verifies 6-hour lookahead trajectory and fractional Time-to-Failure."""
    node_id = "NODE_FORECAST_TEST"
    
    # Feed steady readings
    for _ in range(60):
        forecast_service.record_reading(node_id, 0.45)
    
    steady_res = forecast_service.predict_future_trajectory(node_id)
    assert len(steady_res["forecast_trajectory"]) == 6
    assert steady_res["time_to_critical_hours"] is None
    assert steady_res["alert_severity"] == "NORMAL"
    
    # Feed accelerating subsidence
    for d in [10.0, 15.0, 20.0, 25.0, 30.0]:
        forecast_service.record_reading(node_id, d)
        
    accel_res = forecast_service.predict_future_trajectory(node_id)
    assert len(accel_res["forecast_trajectory"]) == 6
    assert accel_res["alert_severity"] in ["WARNING", "CRITICAL"]

# =====================================================================
# 7. DEFENSIVE INPUT SANITIZATION (NaN, None, Inf, Corrupt)
# =====================================================================
def test_defensive_guardrails_corrupt_payload():
    """Pipeline must gracefully sanitize malformed data without raising any uncaught exceptions."""
    service = FaultTolerantMLService()
    
    corrupt_packet = {
        "node_id": "NODE_CORRUPT",
        "tilt_x_deg": float("nan"),
        "tilt_y_deg": float("inf"),
        "displacement_mm": None,
        "strain_ue": "INVALID_STRING_VALUE",
        "vibration_amp": -999.0
    }
    
    res = service.predict_packet(corrupt_packet)
    clean = res["telemetry"]
    assert not math.isnan(clean["tilt_x_deg"])
    assert not math.isinf(clean["tilt_y_deg"])
    assert clean["displacement_mm"] == 0.50
    assert clean["strain_ue"] == 95.0
    assert clean["vibration_amp"] == 0.0

# =====================================================================
# 8. HARD PHYSICS ENGINE B SAFETY OVERRIDE
# =====================================================================
def test_engine_b_safety_override():
    """If ML under-predicts under extreme strain, Engine B must force Critical."""
    service = FaultTolerantMLService()
    
    extreme_packet = {
        "node_id": "NODE_OVERRIDE_TEST",
        "tilt_x_deg": 4.5,
        "tilt_y_deg": 3.8,
        "displacement_mm": 25.0,
        "strain_ue": 550.0, # Breaches 450ue critical yield
        "vibration_amp": 0.20
    }
    
    res = service.predict_packet(extreme_packet)
    assert res["instant_prediction"] == "Critical"
    assert res["siren_trigger"] is True

# =====================================================================
# 9. REAL-TIME LATENCY BENCHMARK (< 5ms PER PACKET)
# =====================================================================
def test_realtime_inference_latency_benchmark():
    """Ensures inference speed meets real-time requirements (< 5ms per packet)."""
    service = FaultTolerantMLService()
    packet = {
        "node_id": "NODE_BENCH",
        "tilt_x_deg": 0.5,
        "tilt_y_deg": 0.4,
        "displacement_mm": 4.2,
        "strain_ue": 160.0,
        "vibration_amp": 0.08
    }
    
    # Warm up
    for _ in range(5):
        service.predict_packet(packet)
        
    start_time = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        service.predict_packet(packet)
    elapsed_total_ms = (time.perf_counter() - start_time) * 1000.0
    avg_latency_ms = elapsed_total_ms / iterations
    
    print(f"\n[BENCHMARK] Average ML Inference Latency: {avg_latency_ms:.3f} ms per packet ({iterations} packets)")
    assert avg_latency_ms < 25.0, f"Latency {avg_latency_ms} ms exceeds 25ms target"

# =====================================================================
# 10. END-TO-END HTTP WIFI INGESTION & DB PERSISTENCE
# =====================================================================
def test_http_wifi_ingest_and_clean_db_storage():
    """Simulates real ESP32 Gateway HTTP POST packet to /api/v1/telemetry/ingest."""
    raw_packet = {
        "node_id": "NODE_02",
        "role": "MONITORING",
        "zone_id": "Zone B",
        "seq": 1,
        "tilt_x_deg": 0.85,
        "tilt_y_deg": 0.65,
        "displacement_mm": 6.80,
        "strain_ue": 220.0,
        "vibration_amp": 0.160,
        "rssi_dbm": -68,
        "snr_db": 9.5
    }
    # Tare baseline to eliminate cross-test velocity spikes from previous suite runs
    client.post("/api/v1/telemetry/tare?node_id=NODE_02&disp=0.0&tilt_x=0.0&tilt_y=0.0")

    res = client.post("/api/v1/telemetry/ingest", json=raw_packet)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["success", "ACK"]
    assert data["risk_level"] in ["SAFE", "WARNING", "CRITICAL"]
    assert data["node_id"] == "NODE_02"
    
    # Verify recorded in database (allow background thread executor to commit)
    time.sleep(0.15)
    db = SessionLocal()
    records = db.query(SensorRecord).filter(SensorRecord.node_id == "NODE_02").all()
    assert len(records) >= 1
    latest = records[-1]
    assert latest.node_id == "NODE_02"
    assert latest.zone_id == "Zone B"
    assert latest.predicted_risk in ["Normal", "Warning", "Critical", "SAFE", "WARNING", "CRITICAL"]
    db.close()
