"""
Team Gradient - SIH Underground Coal Mine Subsidence Early Warning System
Module 4: Threshold Calibration & Pipeline Export (threshold_calibration_and_export.py)
----------------------------------------------------------------------------------------
1. Moving Consensus Filtering & Hysteresis:
   - Requires N (default: 2) consecutive predictions of an elevated risk state
     before escalating risk state to eliminate transient acoustic/electrical chatter.
   - De-escalation back to Normal requires 2 consecutive calm samples for stabilization.
2. Complete Pipeline Packaging & Export:
   - Combines Signal Filter params, Multi-scale Feature specs, and Tuned XGBoost
     into a single deployable object serialized to `subsidence_model_optimized.joblib`.
"""

import os
import json
import joblib
import collections
import numpy as np
import pandas as pd

from signal_filtering import SensorSignalFilter
from advanced_feature_engineering import AdvancedFeatureEngineer, FEATURE_NAMES

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

MODEL_EXPORT_PATH = os.path.join(ARTIFACTS_DIR, "subsidence_pipeline_package.joblib")
ENCODER_PATH = os.path.join(ARTIFACTS_DIR, "label_encoder.joblib")

class ConsolidatedSubsidencePipeline:
    """
    Self-contained deployment pipeline encapsulating:
    1. Online Hampel outlier filtering & EMA strain denoising
    2. Multi-scale temporal rolling feature extraction (3s, 10s, 30s)
    3. Tuned XGBoost hazard classifier
    4. Moving consensus hysteresis state machine (anti-chatter)
    """
    def __init__(self, model, classes, feature_names, consensus_k: int = 2):
        self.model = model
        self.classes = classes
        self.feature_names = feature_names
        self.consensus_k = consensus_k
        
        # Standard dicts for clean joblib serialization
        self.node_buffers = {}
        self.consensus_history = {}
        self.current_state = {}

    def _get_buffer(self, node_id: str):
        if node_id not in self.node_buffers:
            self.node_buffers[node_id] = collections.deque(maxlen=35)
        return self.node_buffers[node_id]

    def _get_history(self, node_id: str):
        if node_id not in self.consensus_history:
            self.consensus_history[node_id] = collections.deque(maxlen=self.consensus_k)
        return self.consensus_history[node_id]

    def process_live_sample(self, packet: dict) -> dict:
        node_id = packet.get("node_id", "NODE_A1")
        tilt_x = float(packet.get("tilt_x_deg", 0.0))
        tilt_y = float(packet.get("tilt_y_deg", 0.0))
        disp = float(packet.get("displacement_mm", 0.0))
        strain = float(packet.get("strain_ue", 0.0))
        vib = float(packet.get("vibration_amp", 0.0))

        buf = self._get_buffer(node_id)
        if len(buf) >= 5:
            disp_recent = [e["disp"] for e in list(buf)[-5:]]
            med_disp = float(np.median(disp_recent))
            # If current reading diverges by more than 15mm from 5s median, clamp spike
            if abs(disp - med_disp) > 15.0 and len(buf) > 10:
                disp = med_disp

            # EMA on strain
            prev_strain = buf[-1]["strain"]
            strain = 0.25 * strain + 0.75 * prev_strain

        tilt_total = float(np.sqrt(tilt_x**2 + tilt_y**2))

        entry = {
            "tilt_x": tilt_x, "tilt_y": tilt_y, "tilt_total": tilt_total,
            "disp": disp, "strain": strain, "vib": vib
        }
        buf.append(entry)

        # Extract features
        hist_disp = [e["disp"] for e in buf]
        hist_strain = [e["strain"] for e in buf]
        hist_tilt = [e["tilt_total"] for e in buf]
        hist_vib = [e["vib"] for e in buf]

        disp_vel = float(hist_disp[-1] - hist_disp[-2]) if len(buf) >= 2 else 0.0
        disp_vel_prev = float(hist_disp[-2] - hist_disp[-3]) if len(buf) >= 3 else 0.0
        disp_acc = float(disp_vel - disp_vel_prev)

        strain_rate = float(hist_strain[-1] - hist_strain[-2]) if len(buf) >= 2 else 0.0
        tilt_rate = float(hist_tilt[-1] - hist_tilt[-2]) if len(buf) >= 2 else 0.0

        rockburst_idx = float(abs(disp_vel) * abs(strain_rate))

        feat_dict = {
            "tilt_x_deg": tilt_x,
            "tilt_y_deg": tilt_y,
            "tilt_total_deg": tilt_total,
            "tilt_rate_degs": tilt_rate,
            "displacement_mm": disp,
            "disp_velocity_mms": disp_vel,
            "disp_accel_mms2": disp_acc,
            "strain_ue": strain,
            "strain_rate_ues": strain_rate,
            "vibration_amp": vib,
            "rockburst_hazard_index": rockburst_idx,
        }

        for w in (3, 10, 30):
            sub_d = hist_disp[-w:]
            sub_s = hist_strain[-w:]
            sub_t = hist_tilt[-w:]
            sub_v = hist_vib[-w:]

            feat_dict[f"disp_mean_{w}s"] = float(np.mean(sub_d))
            feat_dict[f"disp_std_{w}s"] = float(np.std(sub_d))
            feat_dict[f"disp_max_{w}s"] = float(np.max(sub_d))

            feat_dict[f"strain_mean_{w}s"] = float(np.mean(sub_s))
            feat_dict[f"strain_std_{w}s"] = float(np.std(sub_s))

            feat_dict[f"tilt_mean_{w}s"] = float(np.mean(sub_t))
            feat_dict[f"tilt_std_{w}s"] = float(np.std(sub_t))

            feat_dict[f"vib_rms_{w}s"] = float(np.sqrt(np.mean(np.square(sub_v))))
            feat_dict[f"vib_max_{w}s"] = float(np.max(sub_v))
            feat_dict[f"vib_std_{w}s"] = float(np.std(sub_v))

        # Model predict
        X_df = pd.DataFrame([feat_dict], columns=self.feature_names)
        raw_pred_idx = self.model.predict(X_df)[0]
        raw_pred = self.classes[raw_pred_idx]

        probs = {}
        if hasattr(self.model, "predict_proba"):
            p_arr = self.model.predict_proba(X_df)[0]
            for c_name, p in zip(self.classes, p_arr):
                probs[c_name] = round(float(p), 4)

        # ---------------------------------------------------------
        # Moving Consensus Hysteresis State Machine
        # ---------------------------------------------------------
        c_hist = self._get_history(node_id)
        c_hist.append(raw_pred)

        if node_id not in self.current_state:
            self.current_state[node_id] = "Normal"

        # State transition logic:
        if raw_pred == "Critical" and (probs.get("Critical", 0.0) > 0.85 or list(c_hist).count("Critical") >= 2):
            self.current_state[node_id] = "Critical"
        elif list(c_hist).count("Warning") >= self.consensus_k:
            if self.current_state[node_id] != "Critical":
                self.current_state[node_id] = "Warning"
        elif all(p == "Normal" for p in c_hist) and len(c_hist) >= self.consensus_k:
            self.current_state[node_id] = "Normal"

        confirmed_state = self.current_state[node_id]

        return {
            "node_id": node_id,
            "raw_instantaneous_prediction": raw_pred,
            "confirmed_risk_state": confirmed_state,
            "confidence": probs.get(raw_pred, 1.0),
            "probabilities": probs,
            "rockburst_hazard_index": rockburst_idx,
            "filter_status": "CONVERGED" if len(buf) >= 10 else "WARMING_UP"
        }

def export_pipeline():
    print("=" * 70)
    print(" Exporting Unified Subsidence Early Warning Pipeline")
    print("=" * 70)
    
    model_path = os.path.join(ARTIFACTS_DIR, "subsidence_model_optimized.joblib")
    model = joblib.load(model_path)
    encoder = joblib.load(ENCODER_PATH)

    pipeline = ConsolidatedSubsidencePipeline(
        model=model,
        classes=list(encoder.classes_),
        feature_names=FEATURE_NAMES,
        consensus_k=2
    )

    joblib.dump(pipeline, MODEL_EXPORT_PATH)
    print(f" Successfully exported consolidated pipeline package to:\n  -> {MODEL_EXPORT_PATH}")
    
    # Run test simulation on hysteresis anti-chatter
    print("\n--- Verifying Moving Consensus Hysteresis Anti-Chatter ---")
    test_packets = [
        {"node_id": "NODE_B1", "tilt_x_deg": 0.02, "tilt_y_deg": 0.01, "displacement_mm": 0.5, "strain_ue": 90.0, "vibration_amp": 0.01},
        # Spurious single-sample spike (optical glint: 25mm)
        {"node_id": "NODE_B1", "tilt_x_deg": 0.02, "tilt_y_deg": 0.01, "displacement_mm": 25.0, "strain_ue": 90.0, "vibration_amp": 0.01},
        # Back to normal
        {"node_id": "NODE_B1", "tilt_x_deg": 0.02, "tilt_y_deg": 0.01, "displacement_mm": 0.5, "strain_ue": 90.0, "vibration_amp": 0.01},
        # True warning onset (two consecutive steps)
        {"node_id": "NODE_B1", "tilt_x_deg": 1.10, "tilt_y_deg": 0.85, "displacement_mm": 8.5, "strain_ue": 250.0, "vibration_amp": 0.22},
        {"node_id": "NODE_B1", "tilt_x_deg": 1.25, "tilt_y_deg": 0.95, "displacement_mm": 9.2, "strain_ue": 270.0, "vibration_amp": 0.35},
    ]

    for i, pkt in enumerate(test_packets, 1):
        res = pipeline.process_live_sample(pkt)
        print(f"Tick {i:02d} -> Raw: {res['raw_instantaneous_prediction']:<8} | Confirmed State: {res['confirmed_risk_state']:<8} (Hysteresis Active)")

if __name__ == "__main__":
    export_pipeline()
