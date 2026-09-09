import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.ml_service import ml_service
from app.services.serial_listener import serial_listener

# 1. Test parsing realistic ESP32 Gateway Serial line with prefix noise
raw_line = '[RX] PACKET #12 RECEIVED: {"node_id":"NODE_01","tilt_x":0.05,"tilt_y":0.02,"disp_mm":12.4,"strain_ue":110.0,"vib":0.08,"local_zone":"Zone A"}'
parsed = serial_listener._sanitize_and_parse_line(raw_line)
assert parsed is not None, "Sanitization failed!"
print("Parsed Packet:", parsed["node_id"], parsed["tilt_composite_deg"], parsed["displacement_mm"])

# 2. Test ML Service dual-engine inference
res = ml_service.process_telemetry(parsed)
assert res["current_zone"] in ["Zone A", "Zone B", "Zone C"]
assert len(res["forecast_curve_6h"]) == 6

print("\n--- ML Pipeline Verification ---")
print("Current Zone:     ", res["current_zone"])
print("Confidence:       ", res["confidence"], "%")
print("6h Forecast Curve:", res["forecast_curve_6h"])
print("Time to Collapse: ", res["time_to_collapse_hours"])
print("Collapse Message: ", res["collapse_message"])
print("Web Siren Trigger:", res["trigger_web_siren"])
print("Engines Active:   ", res["classification_engine"], "+", res["forecasting_engine"])

# 3. Test High Hazard Scenario (Should trigger Siren)
hazard_packet = {
    "node_id": "NODE_02",
    "tilt_x": 2.4,
    "tilt_y": 1.9,
    "disp_mm": 34.2,
    "strain_ue": 490.0,
    "vib": 0.25,
    "local_zone": "Zone C"
}
hazard_res = ml_service.process_telemetry(hazard_packet)
print("\n--- Hazard Scenario Verification ---")
print("Current Zone:     ", hazard_res["current_zone"])
print("Web Siren Trigger:", hazard_res["trigger_web_siren"])
assert hazard_res["trigger_web_siren"] is True, "Siren should be armed on critical hazard!"

print("\nSUCCESS: All pipeline integration checks passed flawlessly!")
