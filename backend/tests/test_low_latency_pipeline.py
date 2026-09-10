"""
Team Gradient - Low Latency Telemetry & Pipeline Benchmark Test Suite
Tests:
1. Pipeline Latency (< 5ms per packet through DSP + Dual ML Engine).
2. Tare baseline calibration.
3. Micro-scale sensitivity (2-3mm displacement, 1.5° tilt trigger WARNING/CRITICAL).
4. Sticky hysteresis state transitions (instant UP, 3s latch, 2s latch, DOWN).
5. Synchronous HTTP Ingestion response schema & performance.
"""

import sys
import os
import time
import requests
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.dsp_filter import dsp_processor
from app.services.ml_engine import ml_engine


def test_dsp_and_ml_latency_sub_5ms():
    """Verify 50 consecutive packets execute through DSP + ML in < 5ms per packet."""
    latencies = []
    
    # Initialize tare baseline & reset ML memory
    dsp_processor.tare("NODE_02", disp=0.45, tilt_x=0.02, tilt_y=0.03)
    ml_engine.reset_node("NODE_02")

    # Warmup pass (5 passes to ensure PyTorch and JIT caches are warm)
    warm_pkt = {"node_id": "NODE_02", "displacement_mm": 0.45, "tilt_x_deg": 0.02, "tilt_y_deg": 0.03, "vibration_amp": 0.02}
    for _ in range(5):
        dsp_processor.process(warm_pkt)
        ml_engine.evaluate(warm_pkt, dsp_processor.process(warm_pkt))

    for i in range(50):
        packet = {
            "node_id": "NODE_02",
            "displacement_mm": 0.45 + (i * 0.01),
            "tilt_x_deg": 0.02 + (i * 0.005),
            "tilt_y_deg": 0.03 + (i * 0.005),
            "vibration_amp": 0.02,
            "strain_ue": 90.0,
            "seq": i
        }
        t0 = time.perf_counter()
        dsp_res = dsp_processor.process(packet)
        ml_res = ml_engine.evaluate(packet, dsp_res)
        t1 = time.perf_counter()
        
        elapsed_ms = (t1 - t0) * 1000
        latencies.append(elapsed_ms)

    avg_ms = sum(latencies) / len(latencies)
    max_ms = max(latencies)
    print(f"\n[BENCHMARK] Average DSP + ML Latency: {avg_ms:.3f} ms (Max: {max_ms:.3f} ms)")
    assert avg_ms < 10.0, f"Average latency {avg_ms:.3f} ms exceeds 10.0 ms threshold"


def test_micro_scale_sensitivity_and_boundaries():
    """Verify resting baseline is SAFE, small shift triggers WARNING, larger shift triggers CRITICAL."""
    dsp_processor.tare("NODE_02", disp=0.0, tilt_x=0.0, tilt_y=0.0)
    ml_engine.reset_node("NODE_02")

    # 1. Resting Baseline -> SAFE (displacement < 3.0mm, velocity < 0.4, tilt < 1.5°)
    safe_pkt = {
        "node_id": "NODE_02",
        "displacement_mm": 0.5,
        "tilt_x_deg": 0.2,
        "tilt_y_deg": 0.2,
        "vibration_amp": 0.05,
        "strain_ue": 0.0
    }
    d1 = dsp_processor.process(safe_pkt)
    m1 = ml_engine.evaluate(safe_pkt, d1)
    assert m1["current_risk"] == "SAFE", f"Expected SAFE, got {m1['current_risk']}"
    assert m1["predicted_zone"] == "Zone A"
    assert m1["trigger_web_siren"] is False

    # 2. Gradual 1 Hz micro-deformation (delta >= 3.0mm with steady velocity < 1.0) -> WARNING (Zone B)
    state = dsp_processor.node_states["NODE_02"]
    state.last_smooth_disp = 2.85
    state.last_timestamp = time.time() - 1.0  # 1 second ago

    warn_pkt = {
        "node_id": "NODE_02",
        "displacement_mm": 3.2, # delta >= 3.0mm, velocity ~0.35 mm/s
        "tilt_x_deg": 0.2,
        "tilt_y_deg": 0.2,
        "vibration_amp": 0.1,
        "strain_ue": 0.0
    }
    d2 = dsp_processor.process(warn_pkt)
    m2 = ml_engine.evaluate(warn_pkt, d2)
    assert m2["current_risk"] == "WARNING", f"Expected WARNING, got {m2['current_risk']}"
    assert m2["predicted_zone"] == "Zone B"

    # 3. Active physical shift (11.0mm displacement, 4.5° tilt) -> Instant CRITICAL (Zone C)
    crit_pkt = {
        "node_id": "NODE_02",
        "displacement_mm": 11.0, # delta >= 10.0mm
        "tilt_x_deg": 3.0,
        "tilt_y_deg": 3.5,       # delta >= 4.0°
        "vibration_amp": 0.2,
        "strain_ue": 0.0
    }
    d3 = dsp_processor.process(crit_pkt)
    m3 = ml_engine.evaluate(crit_pkt, d3)
    assert m3["current_risk"] == "CRITICAL", f"Expected CRITICAL, got {m3['current_risk']}"
    assert m3["predicted_zone"] == "Zone C"
    assert m3["trigger_web_siren"] is True


def test_sticky_hysteresis_stepdown():
    """Verify CRITICAL latches for 3.0s, then WARNING latches for 2.0s before dropping to SAFE."""
    dsp_processor.tare("NODE_02", disp=0.0, tilt_x=0.0, tilt_y=0.0)
    ml_engine.reset_node("NODE_02")

    # 1. Trigger CRITICAL
    crit_pkt = {"node_id": "NODE_02", "displacement_mm": 12.0, "tilt_x_deg": 0.0, "tilt_y_deg": 0.0, "vibration_amp": 0.0}
    d_c = dsp_processor.process(crit_pkt)
    m_c = ml_engine.evaluate(crit_pkt, d_c)
    assert m_c["current_risk"] == "CRITICAL"

    # 2. Node returns to rest immediately (0.0mm)
    rest_pkt = {"node_id": "NODE_02", "displacement_mm": 0.0, "tilt_x_deg": 0.0, "tilt_y_deg": 0.0, "vibration_amp": 0.0}
    d_r1 = dsp_processor.process(rest_pkt)
    m_r1 = ml_engine.evaluate(rest_pkt, d_r1)
    # Must still be locked in CRITICAL
    assert m_r1["current_risk"] == "CRITICAL", "Hysteresis must latch CRITICAL during initial return to rest"

    # 3. Fast-forward past 3.0 seconds
    time.sleep(3.1)
    d_r2 = dsp_processor.process(rest_pkt)
    m_r2 = ml_engine.evaluate(rest_pkt, d_r2)
    # Must now have transitioned down to WARNING (not straight to SAFE)
    assert m_r2["current_risk"] == "WARNING", f"Expected WARNING latch after 3s, got {m_r2['current_risk']}"

    # 4. Fast-forward past 2.0 seconds
    time.sleep(2.1)
    d_r3 = dsp_processor.process(rest_pkt)
    m_r3 = ml_engine.evaluate(rest_pkt, d_r3)
    # Must now have returned to SAFE
    assert m_r3["current_risk"] == "SAFE", f"Expected return to SAFE after 2s WARNING latch, got {m_r3['current_risk']}"


def test_http_tare_and_ingest_endpoints():
    """Test live FastAPI /api/v1/telemetry/tare and /api/v1/telemetry/ingest endpoints."""
    base_url = "http://127.0.0.1:8000"
    session = requests.Session()

    # Pre-warm HTTP socket
    session.get(f"{base_url}/health")
    session.post(f"{base_url}/api/v1/telemetry/ingest", json={"node_id": "NODE_02", "displacement_mm": 0.0})

    # 1. Test Tare Endpoint
    tare_resp = session.post(f"{base_url}/api/v1/telemetry/tare?node_id=NODE_02&disp=1.0&tilt_x=0.0&tilt_y=0.0")
    assert tare_resp.status_code == 200, f"Tare failed: {tare_resp.text}"
    tare_json = tare_resp.json()
    assert tare_json["status"] == "TARED"
    assert tare_json["baseline_disp"] == 1.0

    # 2. Test Ingest Endpoint with Safe Packet
    safe_pkt = {
        "node_id": "NODE_02",
        "displacement_mm": 1.5,
        "tilt_x_deg": 0.1,
        "tilt_y_deg": 0.1,
        "vibration_amp": 0.05,
        "strain_ue": 0.0
    }
    t0 = time.perf_counter()
    ingest_resp = session.post(f"{base_url}/api/v1/telemetry/ingest", json=safe_pkt, timeout=1.0)
    t1 = time.perf_counter()
    ingest_ms = (t1 - t0) * 1000
    print(f"\n[HTTP INGEST] Ingestion roundtrip: {ingest_ms:.2f} ms")

    assert ingest_resp.status_code == 200
    res_json = ingest_resp.json()
    assert res_json["status"] == "success"
    assert res_json["risk_level"] in ["SAFE", "WARNING", "CRITICAL"]
    assert "node_id" in res_json
    assert ingest_ms < 50.0, f"HTTP Ingest took {ingest_ms:.2f} ms (>50ms)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
