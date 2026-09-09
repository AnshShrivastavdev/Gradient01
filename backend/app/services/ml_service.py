"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring System
Module: ml_service.py (Dual-Engine Risk Classification & LSTM Forecasting Pipeline)
-----------------------------------------------------------------------------------
1. In-Memory Temporal Buffer: collections.deque(maxlen=60) per node_id.
2. Branch A (Risk Classification): Rolling feature extraction (mean, std, ROC)
   and XGBoost / Scikit-Learn inference producing `current_zone` and `confidence` (%).
3. Branch B (Trajectory Forecasting): PyTorch 2-Layer LSTM sequence model producing
   the 1 to 6-hour ground displacement trajectory (`forecast_curve_6h`).
4. Time-to-Collapse Calculator: Continuous linear interpolation finding the exact
   breach point across 35.0 mm threshold (`time_to_collapse_hours`, `collapse_message`).
5. Alert State: Flags `trigger_web_siren = True` on Zone C or imminent collapse (<= 2h).
6. Deterministic Safety Fallback: Zero-crash fallback rules on corrupted data or missing weights.
"""

import os
import math
import logging
from collections import defaultdict, deque
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
import joblib

from app.config import settings

logger = logging.getLogger("DualEngineMLService")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [ML_SERVICE] %(message)s")

# 18 Features aligned with trained subsidence_model.joblib
CLASSIFIER_FEATURE_COLUMNS = [
    "tilt_x_deg", "tilt_y_deg", "tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp",
    "tilt_composite_deg_mean_5s", "tilt_composite_deg_std_5s", "tilt_composite_deg_roc_5s",
    "displacement_mm_mean_5s", "displacement_mm_std_5s", "displacement_mm_roc_5s",
    "strain_ue_mean_5s", "strain_ue_std_5s", "strain_ue_roc_5s",
    "vibration_amp_mean_5s", "vibration_amp_std_5s", "vibration_amp_roc_5s"
]

LOOKBACK_STEPS = 60
FORECAST_HORIZON_HOURS = 6
DEFAULT_COLLAPSE_THRESHOLD_MM = 35.0


class DualEngineMLService:
    def __init__(self):
        # 60-step temporal sliding window buffers per node
        self.node_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=LOOKBACK_STEPS))
        
        # Classification artifacts (Branch A)
        self.classifier = None
        self.label_encoder = None

        # Forecasting artifacts (Branch B)
        self.lstm_model = None
        self.forecaster_scaler = None

        # Geotechnical limits
        self.collapse_threshold_mm = getattr(settings, "COLLAPSE_THRESHOLD_MM", DEFAULT_COLLAPSE_THRESHOLD_MM)

        self._load_classifier_artifacts()
        self._load_forecaster_artifacts()

    def _load_classifier_artifacts(self):
        """Loads Scikit-Learn/XGBoost risk classification model and label encoder."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        candidate_paths = [
            settings.ML_MODEL_PATH,
            os.path.join(base_dir, "..", "ml_engine", "artifacts", "subsidence_model.joblib"),
            os.path.join(base_dir, "..", "ml", "models", "subsidence_model.joblib")
        ]
        encoder_paths = [
            settings.ML_ENCODER_PATH,
            os.path.join(base_dir, "..", "ml_engine", "artifacts", "label_encoder.joblib"),
            os.path.join(base_dir, "..", "ml", "models", "label_encoder.joblib")
        ]

        found_model = next((p for p in candidate_paths if os.path.exists(p)), None)
        found_encoder = next((p for p in encoder_paths if os.path.exists(p)), None)

        if found_model and found_encoder:
            try:
                self.classifier = joblib.load(found_model)
                self.label_encoder = joblib.load(found_encoder)
                logger.info(f"Loaded Risk Classifier from: {found_model}")
            except Exception as ex:
                logger.warning(f"Could not load risk classifier ({ex}). Using deterministic rule fallback.")
                self.classifier = None
        else:
            logger.warning("Classifier joblib artifact not found. Will use deterministic rule fallback.")

    def _load_forecaster_artifacts(self):
        """Loads PyTorch 2-Layer LSTM displacement forecaster and MinMaxScaler."""
        try:
            import torch
            import torch.nn as nn

            class SubsidenceLSTMForecaster(nn.Module):
                def __init__(self, input_dim=1, hidden_dim=64, num_layers=2, output_dim=FORECAST_HORIZON_HOURS):
                    super().__init__()
                    self.lstm = nn.LSTM(
                        input_size=input_dim,
                        hidden_size=hidden_dim,
                        num_layers=num_layers,
                        batch_first=True
                    )
                    self.fc = nn.Linear(hidden_dim, output_dim)
                    self.relu = nn.ReLU()  # Physical constraint: non-negative forward subsidence increments

                def forward(self, x):
                    lstm_out, _ = self.lstm(x)
                    return self.relu(self.fc(lstm_out[:, -1, :]))

            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            pth_candidates = [
                getattr(settings, "FORECASTER_PTH_PATH", ""),
                os.path.join(base_dir, "..", "ml_engine", "artifacts", "displacement_forecaster.pth")
            ]
            scaler_candidates = [
                getattr(settings, "FORECASTER_SCALER_PATH", ""),
                os.path.join(base_dir, "..", "ml_engine", "artifacts", "forecaster_scaler.joblib")
            ]

            pth_file = next((p for p in pth_candidates if p and os.path.exists(p)), None)
            scaler_file = next((p for p in scaler_candidates if p and os.path.exists(p)), None)

            if pth_file and scaler_file:
                model = SubsidenceLSTMForecaster()
                model.load_state_dict(torch.load(pth_file, map_location=torch.device("cpu")))
                model.eval()
                self.lstm_model = model
                self.forecaster_scaler = joblib.load(scaler_file)
                logger.info(f"Loaded PyTorch 2-Layer LSTM Forecaster from: {pth_file}")
            else:
                logger.warning("PyTorch weights not found. Will use kinematic extrapolation fallback.")
        except Exception as ex:
            logger.warning(f"PyTorch initialization error: {ex}. Using kinematic extrapolation fallback.")
            self.lstm_model = None

    def process_telemetry(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingests a live telemetry packet, computes rolling stats, runs Branch A (risk classification)
        and Branch B (PyTorch LSTM 6-hour forecast), computes Time-to-Collapse, and sets alert siren state.
        """
        node_id = str(packet.get("node_id", "NODE_01"))

        # Defensive sanitize raw readings
        tilt_x = self._safe_float(packet.get("tilt_x_deg") or packet.get("tilt_x"), 0.0)
        tilt_y = self._safe_float(packet.get("tilt_y_deg") or packet.get("tilt_y"), 0.0)
        tilt_comp = round(math.sqrt(tilt_x**2 + tilt_y**2), 3)
        disp_mm = max(0.0, self._safe_float(packet.get("displacement_mm") or packet.get("disp_mm"), 0.5))
        strain_ue = max(0.0, self._safe_float(packet.get("strain_ue") or packet.get("strain"), 90.0))
        vib_amp = max(0.0, self._safe_float(packet.get("vibration_amp") or packet.get("vib"), 0.015))

        entry = {
            "tilt_x": tilt_x,
            "tilt_y": tilt_y,
            "tilt_composite": tilt_comp,
            "displacement": disp_mm,
            "strain": strain_ue,
            "vibration": vib_amp,
            "timestamp": packet.get("timestamp")
        }

        # Maintain in-memory sliding buffer
        buf = self.node_buffers[node_id]
        buf.append(entry)

        # -------------------------------------------------------------
        # BRANCH A: Risk Classification (Scikit-Learn / XGBoost)
        # -------------------------------------------------------------
        current_zone, confidence, probabilities, branch_a_mode = self._evaluate_risk_classification(
            tilt_x, tilt_y, tilt_comp, disp_mm, strain_ue, vib_amp, buf
        )

        # -------------------------------------------------------------
        # BRANCH B: 6-Hour Time-Series Displacement Forecasting (LSTM)
        # -------------------------------------------------------------
        forecast_curve_6h, branch_b_mode = self._evaluate_displacement_forecast(node_id, disp_mm, buf)

        # -------------------------------------------------------------
        # TIME-TO-COLLAPSE CALCULATOR (35.0 mm Threshold Crossing)
        # -------------------------------------------------------------
        time_to_collapse_hours, collapse_message = self._calculate_time_to_collapse(
            disp_mm, forecast_curve_6h
        )

        # -------------------------------------------------------------
        # ALERT STATE: Siren Triggering Logic
        # -------------------------------------------------------------
        trigger_web_siren = (
            current_zone == "Zone C"
            or (time_to_collapse_hours is not None and time_to_collapse_hours <= 2.0)
        )

        # Build output payload
        return {
            "node_id": node_id,
            "role": packet.get("role", "REFERENCE" if "1" in node_id else "MONITORING"),
            "timestamp": packet.get("timestamp"),
            "tilt_x_deg": tilt_x,
            "tilt_y_deg": tilt_y,
            "tilt_composite_deg": tilt_comp,
            "displacement_mm": disp_mm,
            "strain_ue": strain_ue,
            "vibration_amp": vib_amp,
            "ref_displacement_mm": packet.get("ref_displacement_mm"),
            "differential_displacement_mm": packet.get("differential_displacement_mm"),
            "differential_tilt_deg": packet.get("differential_tilt_deg"),
            "rssi_dbm": packet.get("rssi_dbm", -70),
            "snr_db": packet.get("snr_db", 9.5),
            "source": packet.get("source", "SERIAL_STREAM"),
            # Branch A Results
            "current_zone": current_zone,
            "confidence": confidence,
            "probabilities": probabilities,
            "classification_engine": branch_a_mode,
            # Branch B Results
            "forecast_curve_6h": forecast_curve_6h,
            "forecast_intervals": ["t+1h", "t+2h", "t+3h", "t+4h", "t+5h", "t+6h"],
            "forecasting_engine": branch_b_mode,
            "critical_threshold_mm": self.collapse_threshold_mm,
            # Time-to-Collapse Results
            "time_to_collapse_hours": time_to_collapse_hours,
            "collapse_message": collapse_message,
            # Alert Flag
            "trigger_web_siren": trigger_web_siren,
            # Historical Buffer Info
            "buffer_depth": len(buf),
            "buffer_capacity": LOOKBACK_STEPS
        }

    def _evaluate_risk_classification(
        self,
        tilt_x: float,
        tilt_y: float,
        tilt_comp: float,
        disp: float,
        strain: float,
        vib: float,
        buf: deque
    ) -> Tuple[str, float, Dict[str, float], str]:
        """
        Runs Branch A inference. Computes 5-second rolling window features and
        invokes XGBoost/RandomForest classifier. Falls back to hard geotechnical rules if needed.
        """
        # Slices up to last 5 entries for 5s rolling statistics
        recent_entries = list(buf)[-min(5, len(buf)):]

        h_tilt = [e["tilt_composite"] for e in recent_entries]
        h_disp = [e["displacement"] for e in recent_entries]
        h_strain = [e["strain"] for e in recent_entries]
        h_vib = [e["vibration"] for e in recent_entries]

        features_dict = {
            "tilt_x_deg": tilt_x,
            "tilt_y_deg": tilt_y,
            "tilt_composite_deg": tilt_comp,
            "displacement_mm": disp,
            "strain_ue": strain,
            "vibration_amp": vib,
            "tilt_composite_deg_mean_5s": float(np.mean(h_tilt)),
            "tilt_composite_deg_std_5s": float(np.std(h_tilt)) if len(h_tilt) > 1 else 0.0,
            "tilt_composite_deg_roc_5s": float(h_tilt[-1] - h_tilt[0]) if len(h_tilt) > 1 else 0.0,
            "displacement_mm_mean_5s": float(np.mean(h_disp)),
            "displacement_mm_std_5s": float(np.std(h_disp)) if len(h_disp) > 1 else 0.0,
            "displacement_mm_roc_5s": float(h_disp[-1] - h_disp[0]) if len(h_disp) > 1 else 0.0,
            "strain_ue_mean_5s": float(np.mean(h_strain)),
            "strain_ue_std_5s": float(np.std(h_strain)) if len(h_strain) > 1 else 0.0,
            "strain_ue_roc_5s": float(h_strain[-1] - h_strain[0]) if len(h_strain) > 1 else 0.0,
            "vibration_amp_mean_5s": float(np.mean(h_vib)),
            "vibration_amp_std_5s": float(np.std(h_vib)) if len(h_vib) > 1 else 0.0,
            "vibration_amp_roc_5s": float(h_vib[-1] - h_vib[0]) if len(h_vib) > 1 else 0.0,
        }

        # Try ML Model Inference
        if self.classifier is not None and self.label_encoder is not None:
            try:
                df = pd.DataFrame([features_dict], columns=CLASSIFIER_FEATURE_COLUMNS)
                pred_idx = self.classifier.predict(df)[0]
                raw_pred_label = self.label_encoder.inverse_transform([pred_idx])[0]

                # Map model classes ('Critical', 'Warning', 'Normal') to Zones
                zone_map = {
                    "Normal": "Zone A",
                    "Warning": "Zone B",
                    "Critical": "Zone C"
                }
                current_zone = zone_map.get(raw_pred_label, "Zone A")

                probabilities = {}
                confidence = 95.0
                if hasattr(self.classifier, "predict_proba"):
                    probs = self.classifier.predict_proba(df)[0]
                    for cls_name, p in zip(self.label_encoder.classes_, probs):
                        mapped_z = zone_map.get(cls_name, cls_name)
                        probabilities[mapped_z] = round(float(p) * 100, 1)
                    confidence = probabilities.get(current_zone, 95.0)

                # Hard physical safety guardrail: if sensor is in extreme zone, ML cannot under-predict
                if disp >= 20.0 or strain >= 450.0 or tilt_comp >= 3.0 or vib >= 6.0:
                    current_zone = "Zone C"
                    confidence = max(confidence, 99.0)
                elif (disp >= 5.0 or strain >= 180.0 or tilt_comp >= 0.5) and current_zone == "Zone A":
                    current_zone = "Zone B"
                    confidence = max(confidence, 90.0)

                return current_zone, round(float(confidence), 1), probabilities, "XGBOOST_MODEL"
            except Exception as ex:
                logger.error(f"Inference error in classifier: {ex}. Engaging deterministic rule fallback.")

        # Deterministic Geotechnical Safety Fallback (Rule Engine)
        if disp >= 20.0 or strain >= 450.0 or tilt_comp >= 3.0 or vib >= 6.0:
            current_zone = "Zone C"
            confidence = 99.0
            probabilities = {"Zone A": 0.5, "Zone B": 3.5, "Zone C": 96.0}
        elif disp >= 5.0 or strain >= 180.0 or tilt_comp >= 0.5 or vib >= 0.15:
            current_zone = "Zone B"
            confidence = 92.0
            probabilities = {"Zone A": 6.0, "Zone B": 92.0, "Zone C": 2.0}
        else:
            current_zone = "Zone A"
            confidence = 98.5
            probabilities = {"Zone A": 98.5, "Zone B": 1.4, "Zone C": 0.1}

        return current_zone, confidence, probabilities, "DETERMINISTIC_RULES_FALLBACK"

    def _evaluate_displacement_forecast(
        self,
        node_id: str,
        current_disp: float,
        buf: deque
    ) -> Tuple[List[float], str]:
        """
        Runs Branch B inference. Slices 60 displacement readings, runs PyTorch 2-layer LSTM,
        and computes cumulative displacement projections for 1h through 6h.
        Falls back to kinematic Taylor expansion extrapolation.
        """
        # Prepare 60-step lookback array
        raw_displacements = [e["displacement"] for e in buf]
        if len(raw_displacements) < LOOKBACK_STEPS:
            # Smooth pad backward using existing readings and initial velocity
            pad_needed = LOOKBACK_STEPS - len(raw_displacements)
            if len(raw_displacements) >= 2:
                slope = (raw_displacements[-1] - raw_displacements[0]) / len(raw_displacements)
                back_pad = [max(0.05, raw_displacements[0] - slope * (pad_needed - i)) for i in range(pad_needed)]
            else:
                back_pad = [current_disp] * pad_needed
            history_arr = np.array(back_pad + raw_displacements, dtype=np.float32)
        else:
            history_arr = np.array(raw_displacements[-LOOKBACK_STEPS:], dtype=np.float32)

        # PyTorch 2-Layer LSTM Inference
        if self.lstm_model is not None and self.forecaster_scaler is not None:
            try:
                import torch
                # Scale input sequence
                scaled_seq = self.forecaster_scaler.transform(history_arr.reshape(-1, 1)).reshape(1, LOOKBACK_STEPS, 1)
                with torch.no_grad():
                    inp_tensor = torch.tensor(scaled_seq, dtype=torch.float32)
                    increments = self.lstm_model(inp_tensor).numpy().flatten()

                # Add increments to current displacement: d(t+h) = d_now + cumsum(inc)
                projected = current_disp + np.maximum.accumulate(increments)

                # Physical minimum trend check based on recent velocity
                recent = history_arr[-10:]
                v_rate = float(np.mean(np.diff(recent))) if len(recent) > 1 else 0.0
                if v_rate > 0.08:
                    projected = np.maximum(projected, [current_disp + v_rate * 12.0 * h for h in range(1, 7)])

                curve = [round(float(v), 2) for v in projected]
                return curve, "PYTORCH_2LAYER_LSTM"
            except Exception as ex:
                logger.warning(f"LSTM forecaster inference failed ({ex}). Falling back to kinematic extrapolation.")

        # Kinematic Taylor Extrapolation Fallback
        # d(t+h) = d_0 + v_hour * h + 0.5 * a_hour * h^2
        recent = history_arr[-10:]
        v_step = float(np.mean(np.diff(recent))) if len(recent) > 1 else 0.015
        v_hour = max(0.04, v_step * 18.0)
        a_hour = (v_hour * 0.10) if v_hour > 0.4 else 0.0

        curve = []
        for h in range(1, FORECAST_HORIZON_HOURS + 1):
            projected = current_disp + (v_hour * h) + (0.5 * a_hour * (h**2))
            curve.append(round(float(projected), 2))

        return curve, "KINEMATIC_TAYLOR_FALLBACK"

    def _calculate_time_to_collapse(
        self,
        current_disp: float,
        forecast_curve_6h: List[float]
    ) -> Tuple[Optional[float], str]:
        """
        Calculates when the displacement forecast curve crosses the 35.0 mm threshold.
        Uses continuous linear interpolation between the hourly time steps.
        """
        threshold = self.collapse_threshold_mm

        # Threshold already breached in real-time
        if current_disp >= threshold:
            msg = f"CRITICAL HAZARD: Ground subsidence ({current_disp:.1f} mm) has breached the critical threshold ({threshold} mm)!"
            return 0.0, msg

        # Coordinates: [t=0, t=1, t=2, t=3, t=4, t=5, t=6]
        curve_points = [current_disp] + list(forecast_curve_6h)
        time_points = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

        for i in range(len(curve_points) - 1):
            d1, d2 = curve_points[i], curve_points[i + 1]
            t1, t2 = time_points[i], time_points[i + 1]

            if d1 < threshold <= d2:
                # Linear interpolation
                if abs(d2 - d1) > 1e-5:
                    fraction = (threshold - d1) / (d2 - d1)
                    ttf = t1 + fraction * (t2 - t1)
                    ttf_rounded = round(float(ttf), 1)
                else:
                    ttf_rounded = round(float(t2), 1)

                mins = int(round(ttf_rounded * 60))
                msg = f"CRITICAL: Ground subsidence predicted to breach {threshold} mm threshold in {ttf_rounded} hours ({mins} min)!"
                return ttf_rounded, msg

        # No breach predicted within the 6-hour horizon
        msg = f"NOMINAL: Subsidence trajectory stable. No critical breach ({threshold} mm) predicted within 6 hours."
        return None, msg

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        if val is None:
            return default
        try:
            f = float(val)
            return default if math.isnan(f) or math.isinf(f) else f
        except (ValueError, TypeError):
            return default


# Global singleton instance
ml_service = DualEngineMLService()
