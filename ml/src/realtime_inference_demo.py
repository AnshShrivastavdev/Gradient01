"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring
Module 4: Real-Time ESP32 LoRa Packet Inference Demo (realtime_inference_demo.py)
---------------------------------------------------------------------------------
Lightweight, sub-millisecond edge/gateway inference engine for ESP32 multi-node
LoRa packets.

Features:
- Ring buffer state management per physical node (5-second temporal window)
- Real-time rolling feature extraction (mean, std, rate of change delta/delta_t)
- Multi-class prediction via trained XGBoost subsidence classifier
- Actionable geotechnical alert dispatch (Normal, Warning, Critical Evacuation)
"""

import os
import sys
import time
import json
import collections
import numpy as np
import pandas as pd
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "subsidence_model.joblib")
ENCODER_PATH = os.path.join(BASE_DIR, "models", "label_encoder.joblib")
CONFIG_PATH = os.path.join(BASE_DIR, "models", "feature_config.json")

ZONE_METADATA = {
    "Normal": {
        "zone": "Zone A",
        "badge": "[ZONE A: NOMINAL]",
        "color": "#15803D",
        "description": "Baseline subsurface strata stable. Zero critical shear detected.",
        "action": "Maintain routine 1Hz continuous telemetry logging."
    },
    "Warning": {
        "zone": "Zone B",
        "badge": "[ZONE B: CAUTION]",
        "color": "#B45309",
        "description": "Progressive roof sag and micro-seismic tremor bursts detected.",
        "action": "Alert underground shift supervisor. Dispatch geotechnical inspection team."
    },
    "Critical": {
        "zone": "Zone C",
        "badge": "[ZONE C: CRITICAL EVACUATION]",
        "color": "#B91C1C",
        "description": "CRITICAL SUBSIDENCE COLLAPSE IMMINENT. YIELD LIMIT BREACHED.",
        "action": "AUTOMATICALLY TRIGGER EVACUATION SIRENS & LORA BEACONS. EVACUATE SECTOR NOW."
    }
}

class RealtimeSubsidencePredictor:
    def __init__(self, window_size: int = 5):
        if not os.path.exists(MODEL_PATH) or not os.path.exists(ENCODER_PATH):
            raise FileNotFoundError("Model artifacts missing. Run train_classifier.py first.")
            
        self.model = joblib.load(MODEL_PATH)
        self.encoder = joblib.load(ENCODER_PATH)
        
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            self.config = json.load(f)
            
        self.feature_columns = self.config["feature_columns"]
        self.window_size = window_size
        
        # Ring buffer per node for stateful rolling feature calculations
        # Structure: node_id -> deque of dicts holding raw signals
        self.node_buffers = collections.defaultdict(lambda: collections.deque(maxlen=self.window_size))

    def process_packet(self, packet: dict) -> dict:
        """
        Processes a single incoming LoRa JSON packet from an ESP32 node.
        
        Expected Packet Schema:
        {
            "node_id": "NODE_A1" | "NODE_B1" | "NODE_C1",
            "timestamp": "2026-03-01 08:00:00",
            "tilt_x_deg": float,
            "tilt_y_deg": float,
            "displacement_mm": float,
            "strain_ue": float,
            "vibration_amp": float
        }
        """
        node_id = packet.get("node_id", "NODE_UNKNOWN")
        tilt_x = float(packet.get("tilt_x_deg", 0.0))
        tilt_y = float(packet.get("tilt_y_deg", 0.0))
        tilt_comp = float(np.sqrt(tilt_x**2 + tilt_y**2))
        disp = float(packet.get("displacement_mm", 0.0))
        strain = float(packet.get("strain_ue", 0.0))
        vib = float(packet.get("vibration_amp", 0.0))
        
        current_entry = {
            "tilt_x": tilt_x,
            "tilt_y": tilt_y,
            "tilt_comp": tilt_comp,
            "disp": disp,
            "strain": strain,
            "vib": vib
        }
        
        # Append to node's rolling memory
        buffer = self.node_buffers[node_id]
        buffer.append(current_entry)
        
        # Compute rolling window statistics
        hist_tilt_comp = [e["tilt_comp"] for e in buffer]
        hist_disp = [e["disp"] for e in buffer]
        hist_strain = [e["strain"] for e in buffer]
        hist_vib = [e["vib"] for e in buffer]
        
        # Rolling means
        tilt_comp_mean = float(np.mean(hist_tilt_comp))
        disp_mean = float(np.mean(hist_disp))
        strain_mean = float(np.mean(hist_strain))
        vib_mean = float(np.mean(hist_vib))
        
        # Rolling stds (ddof=0 for small window stability)
        tilt_comp_std = float(np.std(hist_tilt_comp))
        disp_std = float(np.std(hist_disp))
        strain_std = float(np.std(hist_strain))
        vib_std = float(np.std(hist_vib))
        
        # Rate of change: delta over window
        tilt_comp_roc = float(hist_tilt_comp[-1] - hist_tilt_comp[0]) if len(buffer) > 1 else 0.0
        disp_roc = float(hist_disp[-1] - hist_disp[0]) if len(buffer) > 1 else 0.0
        strain_roc = float(hist_strain[-1] - hist_strain[0]) if len(buffer) > 1 else 0.0
        vib_roc = float(hist_vib[-1] - hist_vib[0]) if len(buffer) > 1 else 0.0
        
        # Build feature vector matching model schema
        features_dict = {
            "tilt_x_deg": tilt_x,
            "tilt_y_deg": tilt_y,
            "tilt_composite_deg": tilt_comp,
            "displacement_mm": disp,
            "strain_ue": strain,
            "vibration_amp": vib,
            "tilt_composite_deg_mean_5s": tilt_comp_mean,
            "tilt_composite_deg_std_5s": tilt_comp_std,
            "tilt_composite_deg_roc_5s": tilt_comp_roc,
            "displacement_mm_mean_5s": disp_mean,
            "displacement_mm_std_5s": disp_std,
            "displacement_mm_roc_5s": disp_roc,
            "strain_ue_mean_5s": strain_mean,
            "strain_ue_std_5s": strain_std,
            "strain_ue_roc_5s": strain_roc,
            "vibration_amp_mean_5s": vib_mean,
            "vibration_amp_std_5s": vib_std,
            "vibration_amp_roc_5s": vib_roc
        }
        
        X_df = pd.DataFrame([features_dict], columns=self.feature_columns)
        
        # Model inference
        pred_idx = self.model.predict(X_df)[0]
        predicted_risk = self.encoder.inverse_transform([pred_idx])[0]
        
        # Probabilities
        probabilities = {}
        confidence = 1.0
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(X_df)[0]
            for cls_name, prob in zip(self.encoder.classes_, probs):
                probabilities[cls_name] = round(float(prob), 4)
            confidence = probabilities.get(predicted_risk, 1.0)
            
        meta = ZONE_METADATA.get(predicted_risk, {})
        
        return {
            "node_id": node_id,
            "timestamp": packet.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S")),
            "predicted_risk_level": predicted_risk,
            "zone": meta.get("zone", "Zone A"),
            "confidence": round(float(confidence), 4),
            "probabilities": probabilities,
            "status_badge": meta.get("badge", ""),
            "description": meta.get("description", ""),
            "recommended_action": meta.get("action", ""),
            "extracted_features": {
                "tilt_composite_deg": round(tilt_comp, 3),
                "displacement_mm_mean_5s": round(disp_mean, 2),
                "displacement_roc_5s": round(disp_roc, 3),
                "strain_ue_mean_5s": round(strain_mean, 1),
                "vibration_amp_mean_5s": round(vib_mean, 3)
            }
        }

def run_realtime_stream_simulation():
    print("=" * 80)
    print("  TEAM GRADIENT // SIH UNDERGROUND COAL MINE REAL-TIME INFERENCE DEMO")
    print("=" * 80)
    
    predictor = RealtimeSubsidencePredictor(window_size=5)
    
    # Simulated incoming LoRa packets from all three field nodes
    test_stream = [
        # NODE_A1: Stable entry gate
        {"node_id": "NODE_A1", "timestamp": "2026-03-01 10:00:01", "tilt_x_deg": 0.02, "tilt_y_deg": -0.01, "displacement_mm": 0.45, "strain_ue": 92.5, "vibration_amp": 0.012},
        {"node_id": "NODE_A1", "timestamp": "2026-03-01 10:00:02", "tilt_x_deg": 0.01, "tilt_y_deg": 0.01, "displacement_mm": 0.48, "strain_ue": 94.0, "vibration_amp": 0.015},
        
        # NODE_B1: Progressive sag & warning tremors
        {"node_id": "NODE_B1", "timestamp": "2026-03-01 10:00:03", "tilt_x_deg": 0.85, "tilt_y_deg": 0.70, "displacement_mm": 7.40, "strain_ue": 235.0, "vibration_amp": 0.180},
        {"node_id": "NODE_B1", "timestamp": "2026-03-01 10:00:04", "tilt_x_deg": 1.20, "tilt_y_deg": 0.95, "displacement_mm": 9.80, "strain_ue": 280.0, "vibration_amp": 0.350},
        
        # NODE_C1: Critical collapse / extraction void rupture
        {"node_id": "NODE_C1", "timestamp": "2026-03-01 10:00:05", "tilt_x_deg": 4.10, "tilt_y_deg": 3.65, "displacement_mm": 32.50, "strain_ue": 640.0, "vibration_amp": 1.850},
        {"node_id": "NODE_C1", "timestamp": "2026-03-01 10:00:06", "tilt_x_deg": 5.80, "tilt_y_deg": 4.90, "displacement_mm": 44.20, "strain_ue": 790.0, "vibration_amp": 2.650},
    ]
    
    for i, packet in enumerate(test_stream, 1):
        result = predictor.process_packet(packet)
        print(f"\n[Packet #{i:02d} Received from LoRa Gateway]")
        print(f"  * Node ID     : {result['node_id']} | Time: {result['timestamp']}")
        print(f"  * Sensor Raw  : Tilt=({packet['tilt_x_deg']}°, {packet['tilt_y_deg']}°) | Disp={packet['displacement_mm']}mm | Strain={packet['strain_ue']}ue | Vib={packet['vibration_amp']}")
        print(f"  * ML Result   : {result['status_badge']} -> Risk: {result['predicted_risk_level']} (Confidence: {result['confidence']*100:.1f}%)")
        print(f"  * Probabilities: {result['probabilities']}")
        print(f"  * Action Plan : {result['recommended_action']}")
        time.sleep(0.05)
        
    print("\n" + "=" * 80)
    print(" Real-Time LoRa Stream Inference Demo Completed Successfully!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_realtime_stream_simulation()
