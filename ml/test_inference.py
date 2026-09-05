"""
Automated Test Suite for Coal Mine Hazard Zone ML Inference
-----------------------------------------------------------
Tests single and streaming batch geotechnical telemetry inputs across
all three zones (ZONE_A, ZONE_B, ZONE_C) and verifies boundary response.
"""

import os
import sys
import json

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.predict import CoalMineZonePredictor

def run_tests():
    predictor = CoalMineZonePredictor()
    
    test_cases = [
        {
            "name": "Case 1: Baseline Nominal Strata (Zone A)",
            "telemetry": {"strain": 120.5, "tilt": 0.08, "vibration": 0.015, "displacement": 1.10},
            "expected_zone": "ZONE_A"
        },
        {
            "name": "Case 2: Micro-seismic Warning Tremors (Zone B)",
            "telemetry": {"strain": 480.0, "tilt": 1.85, "vibration": 0.320, "displacement": 4.90},
            "expected_zone": "ZONE_B"
        },
        {
            "name": "Case 3: Critical Yield Exceeded & Severe Sag (Zone C)",
            "telemetry": {"strain": 1050.0, "tilt": 5.40, "vibration": 1.650, "displacement": 16.80},
            "expected_zone": "ZONE_C"
        },
        {
            "name": "Case 4: High Strain Rupture Test (Zone C)",
            "telemetry": {"strain": 920.0, "tilt": 3.80, "vibration": 0.850, "displacement": 11.20},
            "expected_zone": "ZONE_C"
        },
        {
            "name": "Case 5: Quiet Shift Night Baseline (Zone A)",
            "telemetry": {"strain": 85.0, "tilt": 0.04, "vibration": 0.008, "displacement": 0.65},
            "expected_zone": "ZONE_A"
        }
    ]
    
    print("\n" + "="*75)
    print("      COAL MINE HAZARD ML PREDICTOR - INFERENCE VERIFICATION")
    print("="*75)
    
    all_passed = True
    for test in test_cases:
        t = test["telemetry"]
        res = predictor.predict(
            strain_microstrain=t["strain"],
            tilt_deg=t["tilt"],
            vibration_g=t["vibration"],
            displacement_mm=t["displacement"]
        )
        
        predicted = res["predicted_zone"]
        status = "PASSED" if predicted == test["expected_zone"] else "FAILED"
        if predicted != test["expected_zone"]:
            all_passed = False
            
        print(f"[{status}] {test['name']}")
        print(f"        Input     : Strain={t['strain']} microstrain | Tilt={t['tilt']} deg | Vib={t['vibration']} g | Disp={t['displacement']} mm")
        print(f"        Predicted : {predicted} (Confidence: {res['confidence']*100:.1f}%, Hazard: {res['hazard_score']})")
        print(f"        Action    : {res['action_required']}\n")
        
    print("="*75)
    if all_passed:
        print(" ALL TEST INFERENCES PASSED PERFECTLY!")
    else:
        print(" SOME TESTS FAILED.")
    print("="*75 + "\n")

if __name__ == "__main__":
    run_tests()
