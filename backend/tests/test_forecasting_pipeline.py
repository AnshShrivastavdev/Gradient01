import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.forecast_service import SubsidenceForecastService

# =====================================================================
# 1. TEST TIME-TO-FAILURE (TTF) LINEAR INTERPOLATION LOGIC
# =====================================================================
def test_ttf_calculation_precision():
    service = SubsidenceForecastService(critical_threshold_mm=35.0)
    
    # Trajectory crossing 35.0 mm between t+4h (33.1mm) and t+5h (39.8mm)
    # Expected interpolation:
    # fraction = (35.0 - 33.1) / (39.8 - 33.1) = 1.9 / 6.7 ≈ 0.2835
    # ttf = 4.0 + 0.2835 * 1.0 = 4.28 -> round(4.3) or ~4.2 depending on points
    current_disp = 12.4
    trajectory = [18.2, 24.5, 29.8, 33.1, 39.8, 45.2]
    
    ttf = service.calculate_time_to_failure(trajectory, current_disp)
    assert ttf is not None
    assert 4.0 <= ttf <= 4.5

def test_steady_trajectory_returns_none_ttf():
    service = SubsidenceForecastService(critical_threshold_mm=35.0)
    
    # Steady bedrock: stays far below 35.0 mm threshold across all 6 hours
    current_disp = 0.50
    trajectory = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    
    ttf = service.calculate_time_to_failure(trajectory, current_disp)
    assert ttf is None # No failure predicted

def test_already_breached_threshold_returns_zero_hours():
    service = SubsidenceForecastService(critical_threshold_mm=35.0)
    
    current_disp = 38.5 # Already above 35.0 mm!
    trajectory = [42.0, 46.0, 50.0, 55.0, 60.0, 65.0]
    
    ttf = service.calculate_time_to_failure(trajectory, current_disp)
    assert ttf == 0.0

# =====================================================================
# 2. TEST END-TO-END PREDICTION PAYLOAD & BUFFER ACCUMULATION
# =====================================================================
def test_steady_node_prediction_payload():
    service = SubsidenceForecastService(critical_threshold_mm=35.0)
    node_id = "NODE_A1"
    
    # Feed 60 steady samples
    for _ in range(60):
        service.record_reading(node_id, 0.45)
        
    payload = service.predict_future_trajectory(node_id)
    assert payload["node_id"] == "NODE_A1"
    assert payload["time_to_critical_hours"] is None
    assert "Trajectory stable" in payload["status_message"]
    assert len(payload["forecast_trajectory"]) == 6
    assert payload["buffer_fill_pct"] == 100.0

def test_accelerating_collapse_prediction_payload():
    service = SubsidenceForecastService(critical_threshold_mm=35.0)
    node_id = "NODE_C1"
    
    # Feed accelerating subsidence curve
    for d in [5.0, 8.0, 12.0, 16.0, 21.0, 26.0, 31.0]:
        service.record_reading(node_id, d)
        
    payload = service.predict_future_trajectory(node_id)
    assert payload["node_id"] == "NODE_C1"
    assert payload["time_to_critical_hours"] is not None
    assert payload["time_to_critical_hours"] > 0.0
    assert "Estimated time to critical subsidence threshold" in payload["status_message"]
    assert len(payload["forecast_trajectory"]) == 6
    assert payload["alert_severity"] in ["WARNING", "CRITICAL"]
