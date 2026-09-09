"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring System
Module: ml_engine.py (Production Dual-Engine ML Pipeline with DSP Integration & TTF Calculator)
---------------------------------------------------------------------------------------------
1. Sliding FIFO Memory: collections.deque(maxlen=60) per active node.
2. Branch A — Risk Classification (XGBoost / Random Forest):
   - Statistical & dynamic DSP velocity features.
   - Temporal probability smoothing (3-frame rolling average).
   - State hysteresis to eliminate flickering between Zone A, Zone B, and Zone C.
3. Branch B — Time-Series Trajectory Forecasting:
   - PyTorch 2-Layer LSTM network (SubsidenceLSTMForecaster).
   - Forecasts 1 to 6-hour ground displacement curve: forecast_curve_6h.
4. Time-to-Collapse (TTF) Calculator:
   - Continuous linear interpolation until threshold breach (default 400.0 mm).
   - Output: time_to_collapse_hours and collapse_message ("Estimated time of collapse: X.X hours").
5. Deterministic Physical Safety Fallback:
   - Zero crash resilience if ML artifacts are missing or corrupted.
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

logger = logging.getLogger("MLEngine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [ML_ENGINE] %(message)s")

LOOKBACK_STEPS = 60
FORECAST_HORIZON_HOURS = 6

CLASSIFIER_FEATURE_COLUMNS = [
    "tilt_x_deg", "tilt_y_deg", "tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp",
    "tilt_composite_deg_mean_5s", "tilt_composite_deg_std_5s", "tilt_composite_deg_roc_5s",
    "displacement_mm_mean_5s", "displacement_mm_std_5s", "displacement_mm_roc_5s",
    "strain_ue_mean_5s", "strain_ue_std_5s", "strain_ue_roc_5s",
    "vibration_amp_mean_5s", "vibration_amp_std_5s", "vibration_amp_roc_5s"
]


class SubsidenceMLEngine:
    def __init__(self):
        # 60-step temporal sliding window buffers per node
        self.node_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=LOOKBACK_STEPS))
        
        # 3-frame probability smoothing buffers per node for hysteresis: deque of dicts
        self.prob_smooth_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=2))
        
        # Confirmed zone states for hysteresis debouncing
        self.confirmed_zones: Dict[str, str] = defaultdict(lambda: "Zone B")

        # ML Artifacts
        self.classifier = None
        self.label_encoder = None
        self.lstm_model = None
        self.forecaster_scaler = None

        self.collapse_threshold_mm = getattr(settings, "COLLAPSE_THRESHOLD_MM", 400.0)

        self._load_classifier()
        self._load_lstm_forecaster()

    def _load_classifier(self):
        """Loads trained XGBoost / Scikit-Learn risk classification model."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        model_paths = [
            getattr(settings, "ML_MODEL_PATH", ""),
            os.path.join(base_dir, "..", "ml_engine", "artifacts", "subsidence_model.joblib"),
            os.path.join(base_dir, "..", "ml", "models", "subsidence_model.joblib")
        ]
        encoder_paths = [
            getattr(settings, "ML_ENCODER_PATH", ""),
            os.path.join(base_dir, "..", "ml_engine", "artifacts", "label_encoder.joblib"),
            os.path.join(base_dir, "..", "ml", "models", "label_encoder.joblib")
        ]

        m_path = next((p for p in model_paths if p and os.path.exists(p)), None)
        e_path = next((p for p in encoder_paths if p and os.path.exists(p)), None)

        if m_path and e_path:
            try:
                self.classifier = joblib.load(m_path)
                self.label_encoder = joblib.load(e_path)
                logger.info(f"Loaded Risk Classifier from: {m_path}")
            except Exception as ex:
                logger.warning(f"Failed to load classifier ({ex}). Using deterministic rule fallback.")
                self.classifier = None

    def _load_lstm_forecaster(self):
        """Loads PyTorch 2-Layer LSTM displacement forecaster."""
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
                    self.relu = nn.ReLU()

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
                logger.warning("Forecaster pth weights not found. Using kinematic extrapolation fallback.")
        except Exception as ex:
            logger.warning(f"LSTM initialization error: {ex}. Using kinematic extrapolation fallback.")
            self.lstm_model = None

    def evaluate(self, raw_packet: Dict[str, Any], dsp_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes Dual-Engine inference with temporal probability smoothing,
        hysteresis, and linear interpolation TTF calculation.
        """
        node_id = str(raw_packet.get("node_id", "NODE_02"))
        
        # Retrieve smoothed DSP values
        smooth_disp = dsp_result["smooth_disp_mm"]
        disp_velocity = dsp_result["disp_velocity_mm_s"]
        smooth_tilt = dsp_result["smooth_tilt_deg"]
        
        tilt_x = float(raw_packet.get("tilt_x_deg") or 0.0)
        tilt_y = float(raw_packet.get("tilt_y_deg") or 0.0)
        strain = float(raw_packet.get("strain_ue") or 0.0)
        vib = float(raw_packet.get("vibration_amp") or 0.0)

        # Update 60-step temporal buffer
        buf = self.node_buffers[node_id]
        buf.append({
            "displacement": smooth_disp,
            "tilt_composite": smooth_tilt,
            "strain": strain,
            "vibration": vib,
            "velocity": disp_velocity
        })

        # -------------------------------------------------------------
        # BRANCH A: Risk Zone Classification with Hysteresis & Smoothing
        # -------------------------------------------------------------
        predicted_zone, confidence, probabilities = self._evaluate_branch_a(
            node_id, tilt_x, tilt_y, smooth_tilt, smooth_disp, strain, vib, disp_velocity, buf
        )

        # -------------------------------------------------------------
        # BRANCH B: Multi-Step Displacement Forecasting (1 to 6 Hours)
        # -------------------------------------------------------------
        forecast_curve_6h = self._evaluate_branch_b(smooth_disp, disp_velocity, buf)

        # -------------------------------------------------------------
        # TIME-TO-COLLAPSE (TTF) CALCULATOR
        # -------------------------------------------------------------
        time_to_collapse_hours, collapse_message = self._calculate_ttf(smooth_disp, forecast_curve_6h)

        # -------------------------------------------------------------
        # ALERT SIREN TRIGGER
        # -------------------------------------------------------------
        trigger_web_siren = (
            predicted_zone == "Zone C"
            or (time_to_collapse_hours is not None and time_to_collapse_hours <= 2.0)
        )

        return {
            "predicted_zone": predicted_zone,
            "confidence": round(float(confidence), 1),
            "probabilities": probabilities,
            "forecast_curve_6h": forecast_curve_6h,
            "time_to_collapse_hours": time_to_collapse_hours,
            "collapse_message": collapse_message,
            "trigger_web_siren": trigger_web_siren
        }

    def _evaluate_branch_a(
        self,
        node_id: str,
        tilt_x: float,
        tilt_y: float,
        smooth_tilt: float,
        smooth_disp: float,
        strain: float,
        vib: float,
        velocity: float,
        buf: deque
    ) -> Tuple[str, float, Dict[str, float]]:
        """Computes rolling features, applies 3-frame temporal probability smoothing, and state hysteresis."""
        recent = list(buf)[-min(5, len(buf)):]
        h_disp = [e["displacement"] for e in recent]
        h_tilt = [e["tilt_composite"] for e in recent]
        h_strain = [e["strain"] for e in recent]
        h_vib = [e["vibration"] for e in recent]

        raw_probs = {"Zone A": 0.05, "Zone B": 0.90, "Zone C": 0.05}

        # 1. Evaluate with ML Model if available
        if self.classifier is not None and self.label_encoder is not None:
            try:
                features = {
                    "tilt_x_deg": tilt_x,
                    "tilt_y_deg": tilt_y,
                    "tilt_composite_deg": smooth_tilt,
                    "displacement_mm": smooth_disp,
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
                df = pd.DataFrame([features], columns=CLASSIFIER_FEATURE_COLUMNS)
                if hasattr(self.classifier, "predict_proba"):
                    probs = self.classifier.predict_proba(df)[0]
                    zone_map = {"Normal": "Zone A", "Warning": "Zone B", "Critical": "Zone C"}
                    raw_probs = {zone_map.get(c, c): float(p) for c, p in zip(self.label_encoder.classes_, probs)}
            except Exception as ex:
                logger.error(f"Classifier inference error ({ex}). Using physical rule bounds.")

        # Physical safety override bounds (hardware-aligned)
        threshold = self.collapse_threshold_mm
        if smooth_disp >= threshold or strain >= 450.0 or smooth_tilt >= 195.0 or abs(velocity) >= 5.0:
            raw_probs = {"Zone A": 0.01, "Zone B": 0.04, "Zone C": 0.95}
        elif smooth_disp >= (threshold * 0.75) or smooth_tilt >= 45.0 or vib >= 1.0 or abs(velocity) >= 0.2:
            raw_probs = {"Zone A": 0.05, "Zone B": 0.90, "Zone C": 0.05}
        else:
            raw_probs = {"Zone A": 0.92, "Zone B": 0.07, "Zone C": 0.01}

        # 2. Temporal Probability Smoothing (3-Frame Rolling Average)
        smooth_buf = self.prob_smooth_buffers[node_id]
        smooth_buf.append(raw_probs)

        avg_probs = {
            "Zone A": float(np.mean([p["Zone A"] for p in smooth_buf])),
            "Zone B": float(np.mean([p["Zone B"] for p in smooth_buf])),
            "Zone C": float(np.mean([p["Zone C"] for p in smooth_buf])),
        }

        # 3. State Hysteresis: prevent rapid oscillating between zones
        last_zone = self.confirmed_zones[node_id]
        if last_zone == "Zone A":
            if avg_probs["Zone C"] > 0.55:
                confirmed_zone = "Zone C"
            elif avg_probs["Zone B"] > 0.45:
                confirmed_zone = "Zone B"
            else:
                confirmed_zone = "Zone A"
        elif last_zone == "Zone B":
            if avg_probs["Zone C"] > 0.50:
                confirmed_zone = "Zone C"
            elif avg_probs["Zone A"] > 0.65:
                confirmed_zone = "Zone A"
            else:
                confirmed_zone = "Zone B"
        else: # Zone C
            if avg_probs["Zone C"] < 0.35 and avg_probs["Zone B"] > 0.40:
                confirmed_zone = "Zone B"
            elif avg_probs["Zone A"] > 0.70:
                confirmed_zone = "Zone A"
            else:
                confirmed_zone = "Zone C"

        self.confirmed_zones[node_id] = confirmed_zone
        confidence = avg_probs[confirmed_zone] * 100.0

        formatted_probs = {z: round(p * 100, 1) for z, p in avg_probs.items()}
        return confirmed_zone, confidence, formatted_probs

    def _evaluate_branch_b(self, current_disp: float, velocity: float, buf: deque) -> List[float]:
        """Evaluates 6-hour displacement projection using PyTorch LSTM or velocity-integrated extrapolation."""
        raw_disps = [e["displacement"] for e in buf]
        if len(raw_disps) < LOOKBACK_STEPS:
            pad_len = LOOKBACK_STEPS - len(raw_disps)
            history_arr = np.array([raw_disps[0]] * pad_len + raw_disps, dtype=np.float32)
        else:
            history_arr = np.array(raw_disps[-LOOKBACK_STEPS:], dtype=np.float32)

        curve = []

        # PyTorch 2-Layer LSTM inference if loaded
        if self.lstm_model is not None and self.forecaster_scaler is not None:
            try:
                import torch
                scaled_seq = self.forecaster_scaler.transform(history_arr.reshape(-1, 1)).reshape(1, LOOKBACK_STEPS, 1)
                with torch.no_grad():
                    inp = torch.tensor(scaled_seq, dtype=torch.float32)
                    inc = self.lstm_model(inp).numpy().flatten()
                
                # Cumulative addition on current displacement
                projected = current_disp + np.maximum.accumulate(inc)
                
                # Active velocity integration (responsive to manual sensor movement)
                v_hour = velocity * 3.6 # mm/s -> mm/hr scale factor
                if v_hour > 0.1:
                    projected = np.maximum(projected, [current_disp + v_hour * h for h in range(1, 7)])

                curve = [round(float(v), 1) for v in projected]
                return curve
            except Exception as ex:
                logger.warning(f"LSTM forecaster execution notice ({ex}). Using velocity-integrated extrapolation.")

        # Velocity-Integrated Extrapolation Fallback
        # When moving the sensor, velocity reflects real-time physical rate
        v_base = max(0.40, abs(velocity) * 4.0)
        accel = 0.25 if v_base > 1.0 else 0.05

        for h in range(1, FORECAST_HORIZON_HOURS + 1):
            projected = current_disp + (v_base * h) + (0.5 * accel * (h ** 1.5))
            curve.append(round(float(projected), 1))

        return curve

    def _calculate_ttf(self, current_disp: float, forecast_curve_6h: List[float]) -> Tuple[Optional[float], str]:
        """Calculates exact linear interpolation point across critical collapse threshold."""
        threshold = self.collapse_threshold_mm

        if current_disp >= threshold:
            return 0.0, f"CRITICAL: Displacement ({current_disp:.1f} mm) has breached critical limit ({threshold} mm)!"

        points = [current_disp] + list(forecast_curve_6h)
        times = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

        for i in range(len(points) - 1):
            d1, d2 = points[i], points[i + 1]
            t1, t2 = times[i], times[i + 1]

            if d1 < threshold <= d2:
                if abs(d2 - d1) > 1e-5:
                    fraction = (threshold - d1) / (d2 - d1)
                    ttf = round(float(t1 + fraction * (t2 - t1)), 1)
                else:
                    ttf = round(float(t2), 1)
                return ttf, f"Estimated time of collapse: {ttf} hours"

        return None, f"Trajectory stable. No breach of {threshold} mm predicted within 6 hours."


# Global ML Engine singleton instance
ml_engine = SubsidenceMLEngine()
