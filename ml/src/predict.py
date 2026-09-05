"""
Real-time Coal Mine Hazard Zone Inference Engine
------------------------------------------------
Accepts live geotechnical sensor telemetry (Strain, Tilt, Vibration, Displacement)
and outputs predicted Hazard Zone (ZONE_A, ZONE_B, ZONE_C) with probabilities,
critical alerts, and recommended safety actions.
"""

import os
import sys
import argparse
import json
import joblib
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "best_zone_classifier.joblib")
METADATA_PATH = os.path.join(BASE_DIR, "models", "model_metadata.json")

FEATURE_COLUMNS = [
    "strain_microstrain",
    "tilt_deg",
    "vibration_g",
    "displacement_mm"
]

ZONE_DETAILS = {
    "ZONE_A": {
        "title": "ZONE A // NORMAL MONITORING",
        "description": "Subsurface stable. Zero critical turbulence detected.",
        "action": "Maintain standard 50Hz continuous logging.",
        "status": "NOMINAL",
        "badge_color": "#15803D"
    },
    "ZONE_B": {
        "title": "ZONE B // SEISMIC CAUTION",
        "description": "Mild ground tremors and progressive roof sag detected.",
        "action": "Alert underground safety officers. Prepare for potential sector evacuation.",
        "status": "CAUTION",
        "badge_color": "#B45309"
    },
    "ZONE_C": {
        "title": "ZONE C // CRITICAL EVACUATION",
        "description": "Severe geotechnical movement and roof bolt yield threshold exceeded.",
        "action": "SOUND EVACUATION SIRENS IMMEDIATELY. EVACUATE LONGWALL SECTOR NOW.",
        "status": "CRITICAL",
        "badge_color": "#B91C1C"
    }
}

class CoalMineZonePredictor:
    def __init__(self, model_path=MODEL_PATH):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}. Train the model first via ml/src/train_model.py.")
        self.model = joblib.load(model_path)
        
        if os.path.exists(METADATA_PATH):
            with open(METADATA_PATH, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
        else:
            self.metadata = None

    def predict(self, strain_microstrain: float, tilt_deg: float, vibration_g: float, displacement_mm: float):
        """
        Runs ML model inference on single sensor telemetry reading.
        """
        features_df = pd.DataFrame([{
            "strain_microstrain": float(strain_microstrain),
            "tilt_deg": float(tilt_deg),
            "vibration_g": float(vibration_g),
            "displacement_mm": float(displacement_mm)
        }], columns=FEATURE_COLUMNS)
        
        prediction = self.model.predict(features_df)[0]
        
        # Get probability distribution if supported
        probabilities = {}
        confidence = 1.0
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(features_df)[0]
            for cls_name, prob in zip(self.model.classes_, probs):
                probabilities[cls_name] = round(float(prob), 4)
            confidence = probabilities.get(prediction, 1.0)
            
        # Calculate composite normalized hazard score (0.0 to 1.0)
        strain_norm = min(1.0, max(0.0, strain_microstrain / 1000.0))
        tilt_norm = min(1.0, max(0.0, tilt_deg / 5.0))
        vib_norm = min(1.0, max(0.0, vibration_g / 1.5))
        disp_norm = min(1.0, max(0.0, displacement_mm / 15.0))
        composite_hazard_score = round(float(0.35 * strain_norm + 0.25 * tilt_norm + 0.20 * vib_norm + 0.20 * disp_norm), 4)
        
        info = ZONE_DETAILS.get(prediction, {})
        
        return {
            "predicted_zone": prediction,
            "confidence": round(float(confidence), 4),
            "hazard_score": composite_hazard_score,
            "class_probabilities": probabilities,
            "status": info.get("status", "UNKNOWN"),
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "action_required": info.get("action", ""),
            "badge_color": info.get("badge_color", "#71717A"),
            "input_telemetry": {
                "strain_microstrain": strain_microstrain,
                "tilt_deg": tilt_deg,
                "vibration_g": vibration_g,
                "displacement_mm": displacement_mm
            }
        }

def main():
    parser = argparse.ArgumentParser(description="Predict Coal Mine Hazard Zone from Live Sensor Data")
    parser.add_argument("--strain", type=float, default=142.5, help="Strain gauge reading (microstrain)")
    parser.add_argument("--tilt", type=float, default=0.14, help="Inclinometer tilt angle (degrees)")
    parser.add_argument("--vibration", type=float, default=0.045, help="Peak vibration / acceleration (g)")
    parser.add_argument("--displacement", type=float, default=1.24, help="Vertical roof displacement / sag (mm)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    
    args = parser.parse_args()
    
    predictor = CoalMineZonePredictor()
    result = predictor.predict(
        strain_microstrain=args.strain,
        tilt_deg=args.tilt,
        vibration_g=args.vibration,
        displacement_mm=args.displacement
    )
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n" + "="*60)
        print("  COAL MINE TELEMETRY - ML HAZARD ZONE CLASSIFICATION")
        print("="*60)
        print(f" Input Sensors : Strain={args.strain} microstrain | Tilt={args.tilt} deg | Vib={args.vibration} g | Disp={args.displacement} mm")
        print(f" Predicted Zone: {result['predicted_zone']} ({result['status']})")
        print(f" Confidence    : {result['confidence'] * 100:.1f}%")
        print(f" Hazard Score  : {result['hazard_score']}")
        print(f" Zone Title    : {result['title']}")
        print(f" Status Notice : {result['description']}")
        print(f" Action Req'd  : {result['action_required']}")
        print("="*60 + "\n")

if __name__ == "__main__":
    main()
