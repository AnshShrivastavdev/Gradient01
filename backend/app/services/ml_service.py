import os
import joblib
import collections
import numpy as np
import pandas as pd
from app.config import settings

FEATURE_COLUMNS = [
    "tilt_x_deg", "tilt_y_deg", "tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp",
    "tilt_composite_deg_mean_5s", "tilt_composite_deg_std_5s", "tilt_composite_deg_roc_5s",
    "displacement_mm_mean_5s", "displacement_mm_std_5s", "displacement_mm_roc_5s",
    "strain_ue_mean_5s", "strain_ue_std_5s", "strain_ue_roc_5s",
    "vibration_amp_mean_5s", "vibration_amp_std_5s", "vibration_amp_roc_5s"
]

class MLInferenceService:
    def __init__(self):
        self.model = None
        self.encoder = None
        self.window_size = 5
        self.node_buffers = collections.defaultdict(lambda: collections.deque(maxlen=self.window_size))
        self.load_artifacts()

    def load_artifacts(self):
        model_path = os.path.abspath(settings.ML_MODEL_PATH)
        encoder_path = os.path.abspath(settings.ML_ENCODER_PATH)

        if os.path.exists(model_path) and os.path.exists(encoder_path):
            self.model = joblib.load(model_path)
            self.encoder = joblib.load(encoder_path)
            print(f"[ML_SERVICE] Loaded trained model from {model_path}")
        else:
            print(f"[ML_SERVICE WARN] Model files not found at {model_path}. Using fallback heuristic rules.")

    def predict_packet(self, packet_dict: dict) -> dict:
        node_id = packet_dict.get("node_id", "NODE_DEFAULT")
        tilt_x = float(packet_dict.get("tilt_x_deg", 0.0))
        tilt_y = float(packet_dict.get("tilt_y_deg", 0.0))
        tilt_comp = float(np.sqrt(tilt_x**2 + tilt_y**2))
        disp = float(packet_dict.get("displacement_mm", 0.0))
        strain = float(packet_dict.get("strain_ue", 0.0))
        vib = float(packet_dict.get("vibration_amp", 0.0))

        entry = {
            "tilt_x": tilt_x, "tilt_y": tilt_y, "tilt_comp": tilt_comp,
            "disp": disp, "strain": strain, "vib": vib
        }
        buffer = self.node_buffers[node_id]
        buffer.append(entry)

        # 5s rolling statistics
        h_tilt = [e["tilt_comp"] for e in buffer]
        h_disp = [e["disp"] for e in buffer]
        h_strain = [e["strain"] for e in buffer]
        h_vib = [e["vib"] for e in buffer]

        features_dict = {
            "tilt_x_deg": tilt_x, "tilt_y_deg": tilt_y, "tilt_composite_deg": tilt_comp,
            "displacement_mm": disp, "strain_ue": strain, "vibration_amp": vib,
            "tilt_composite_deg_mean_5s": float(np.mean(h_tilt)),
            "tilt_composite_deg_std_5s": float(np.std(h_tilt)),
            "tilt_composite_deg_roc_5s": float(h_tilt[-1] - h_tilt[0]) if len(buffer) > 1 else 0.0,
            "displacement_mm_mean_5s": float(np.mean(h_disp)),
            "displacement_mm_std_5s": float(np.std(h_disp)),
            "displacement_mm_roc_5s": float(h_disp[-1] - h_disp[0]) if len(buffer) > 1 else 0.0,
            "strain_ue_mean_5s": float(np.mean(h_strain)),
            "strain_ue_std_5s": float(np.std(h_strain)),
            "strain_ue_roc_5s": float(h_strain[-1] - h_strain[0]) if len(buffer) > 1 else 0.0,
            "vibration_amp_mean_5s": float(np.mean(h_vib)),
            "vibration_amp_std_5s": float(np.std(h_vib)),
            "vibration_amp_roc_5s": float(h_vib[-1] - h_vib[0]) if len(buffer) > 1 else 0.0,
        }

        if self.model and self.encoder:
            df = pd.DataFrame([features_dict], columns=FEATURE_COLUMNS)
            pred_idx = self.model.predict(df)[0]
            predicted_risk = self.encoder.inverse_transform([pred_idx])[0]
            
            probs = {}
            confidence = 1.0
            if hasattr(self.model, "predict_proba"):
                raw_probs = self.model.predict_proba(df)[0]
                for c_name, p in zip(self.encoder.classes_, raw_probs):
                    probs[c_name] = round(float(p), 4)
                confidence = probs.get(predicted_risk, 1.0)
        else:
            # Fallback rules
            if strain >= settings.CRITICAL_STRAIN_UE or disp >= settings.CRITICAL_DISP_MM:
                predicted_risk = "Critical"
            elif strain >= 180 or disp >= 5.0 or tilt_comp >= 0.5:
                predicted_risk = "Warning"
            else:
                predicted_risk = "Normal"
            confidence = 0.95
            probs = {predicted_risk: 0.95}

        return {
            "predicted_risk": predicted_risk,
            "confidence": confidence,
            "probabilities": probs,
            "tilt_composite_deg": round(tilt_comp, 3),
            "features": features_dict
        }

ml_service = MLInferenceService()
