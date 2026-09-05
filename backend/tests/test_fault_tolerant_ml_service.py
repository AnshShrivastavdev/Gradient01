import os
import sys
import math
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.services.fault_tolerant_ml_service import FaultTolerantMLService, fault_tolerant_service

client = TestClient(app)

# =====================================================================
# 1. INPUT SANITIZATION & SCHEMA DEFENSE TESTS
# =====================================================================
def test_input_sanitization_nans_and_corrupt_data():
    service = FaultTolerantMLService()
    
    # Send packet loaded with NaN, Inf, None, and corrupted types
    corrupt_packet = {
        "node_id": "NODE_A1",
        "zone_id": "Zone A",
        "tilt_x_deg": float("nan"),
        "tilt_y_deg": float("inf"),
        "displacement_mm": None,
        "strain_ue": "CORRUPTED_STRING_VALUE",
        "vibration_amp": -999.0 # Extreme out-of-bounds
    }
    
    # Must NOT raise any exceptions!
    res = service.predict_packet(corrupt_packet)
    assert res is not None
    assert res["node_id"] == "NODE_A1"
    
    clean = res["telemetry"]
    # Check default fallbacks
    assert not math.isnan(clean["tilt_x_deg"])
    assert clean["tilt_x_deg"] == 0.0 # Nominal default
    assert not math.isinf(clean["tilt_y_deg"])
    assert clean["tilt_y_deg"] == 0.0 # Nominal default
    assert clean["displacement_mm"] == 0.50 # Nominal default
    assert clean["strain_ue"] == 95.0 # Nominal default
    assert clean["vibration_amp"] == 0.0 # Clipped to min bound

# =====================================================================
# 2. BOUNDED MEMORY MANAGEMENT TESTS
# =====================================================================
def test_bounded_circular_memory_leak_prevention():
    service = FaultTolerantMLService()
    
    # Pump 50 packets for NODE_A1
    for i in range(50):
        packet = {
            "node_id": "NODE_A1",
            "tilt_x_deg": 0.01,
            "tilt_y_deg": 0.01,
            "displacement_mm": 0.5,
            "strain_ue": 90.0,
            "vibration_amp": 0.01
        }
        service.predict_packet(packet)
        
    buffer = service.node_buffers["NODE_A1"]
    # Strictly bounded by maxlen=10 (zero memory leak)
    assert len(buffer) == 10
    assert buffer.maxlen == 10

# =====================================================================
# 3. PACKET DROP & TIME GAP IMPUTATION
# =====================================================================
def test_packet_drop_gap_imputation():
    service = FaultTolerantMLService()
    node = "NODE_TEST_GAP"
    
    # Packet 1 at t=0
    pkt1 = {"node_id": node, "tilt_x_deg": 0.02, "displacement_mm": 0.5, "strain_ue": 90.0, "vibration_amp": 0.01}
    service.last_packet_epochs[node] = 1000.0
    service._handle_packet_gaps(node, current_epoch=1004.0, entry=pkt1) # 4s gap!
    
    # Imputation should pad dropped packets into the buffer
    assert service.dropped_packets_imputed >= 2

# =====================================================================
# 4. REDUNDANT DUAL-ENGINE & FAIL-SAFE OVERRIDE TESTS
# =====================================================================
def test_engine_b_safety_override_on_underprediction():
    service = FaultTolerantMLService()
    
    # Dangerous physical reading: Strain 850ue (Yield threshold breached)
    danger_packet = {
        "node_id": "NODE_C1",
        "zone_id": "Zone C",
        "tilt_x_deg": 4.5,
        "tilt_y_deg": 3.8,
        "displacement_mm": 35.0,
        "strain_ue": 850.0,
        "vibration_amp": 2.5
    }
    
    res = service.predict_packet(danger_packet)
    assert res["instant_prediction"] == "Critical"
    assert res["confidence"] >= 0.90

def test_engine_b_fallback_when_model_missing():
    # Force model path to non-existent file
    service = FaultTolerantMLService(model_path="NON_EXISTENT_MODEL_FILE.joblib")
    assert service.engine_mode == "RULE_FALLBACK"
    
    # Should operate normally via Engine B with zero crashes
    pkt = {
        "node_id": "NODE_A1",
        "tilt_x_deg": 0.02,
        "displacement_mm": 0.5,
        "strain_ue": 90.0,
        "vibration_amp": 0.01
    }
    res = service.predict_packet(pkt)
    assert res["instant_prediction"] == "Normal"
    assert res["active_engine"] == "ENGINE_B_FALLBACK"

# =====================================================================
# 5. ALERT DEBOUNCING & MOVING CONSENSUS TESTS
# =====================================================================
def test_alert_debouncing_prevents_chatter():
    service = FaultTolerantMLService()
    node = "NODE_DEBOUNCE"
    
    # Tick 1: Normal steady state
    res1 = service.predict_packet({"node_id": node, "tilt_x_deg": 0.01, "displacement_mm": 0.5, "strain_ue": 90.0, "vibration_amp": 0.01})
    assert res1["confirmed_risk_state"] == "Normal"
    
    # Tick 2: Single transient Warning reading (e.g. slight jitter)
    res2 = service.predict_packet({"node_id": node, "tilt_x_deg": 0.8, "displacement_mm": 6.0, "strain_ue": 220.0, "vibration_amp": 0.20})
    # State should remain debounced at Normal (anti-chatter active)
    assert res2["confirmed_risk_state"] == "Normal"
    
    # Tick 3: Second consecutive Warning reading -> State escalated!
    res3 = service.predict_packet({"node_id": node, "tilt_x_deg": 0.8, "displacement_mm": 6.0, "strain_ue": 220.0, "vibration_amp": 0.20})
    assert res3["confirmed_risk_state"] == "Warning"

# =====================================================================
# 6. DIAGNOSTICS & HEALTH CHECK API TEST
# =====================================================================
def test_diagnostics_api_endpoint():
    response = client.get("/api/v1/telemetry/diagnostics")
    assert response.status_code == 200
    diag = response.json()
    assert diag["status"] == "HEALTHY"
    assert "memory_usage_kb" in diag
    assert "total_processed_packets" in diag
    assert "active_nodes" in diag
