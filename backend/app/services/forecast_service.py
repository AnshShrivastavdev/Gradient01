"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring System
Module: forecast_service.py (Real-Time Subsidence Forecasting & TTF Service)
----------------------------------------------------------------------------
Maintains a 60-step temporal sliding buffer of ground displacement per node,
generates a 6-hour multi-step subsidence trajectory, and computes fractional
Time-to-Failure (TTF) until critical threshold breach via linear interpolation.
"""

import os
import json
import collections
import numpy as np
import joblib
from typing import Dict, Any, Optional, List

LOOKBACK_STEPS = 60
FORECAST_HORIZON_HOURS = 6
DEFAULT_CRITICAL_THRESHOLD_MM = 35.0

class SubsidenceForecastService:
    def __init__(self, critical_threshold_mm: float = DEFAULT_CRITICAL_THRESHOLD_MM):
        self.critical_threshold_mm = critical_threshold_mm
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self.pth_path = os.path.join(self.base_dir, "..", "ml_engine", "artifacts", "displacement_forecaster.pth")
        self.scaler_path = os.path.join(self.base_dir, "..", "ml_engine", "artifacts", "forecaster_scaler.joblib")
        
        # FIFO circular buffer of past 60 displacement readings per node
        self.node_displacement_buffers: Dict[str, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=LOOKBACK_STEPS)
        )
        
        self.torch_model = None
        self.scaler = None
        self._initialize_forecaster()

    def _initialize_forecaster(self):
        try:
            import torch
            import torch.nn as nn
            
            class SubsidenceLSTMForecaster(nn.Module):
                def __init__(self, input_dim=1, hidden_dim=64, num_layers=2, output_dim=FORECAST_HORIZON_HOURS):
                    super().__init__()
                    self.lstm = nn.LSTM(input_size=input_dim, hidden_size=hidden_dim, num_layers=num_layers, batch_first=True)
                    self.fc = nn.Linear(hidden_dim, output_dim)
                    self.relu = nn.ReLU()

                def forward(self, x):
                    lstm_out, _ = self.lstm(x)
                    return self.relu(self.fc(lstm_out[:, -1, :]))

            if os.path.exists(self.pth_path) and os.path.exists(self.scaler_path):
                self.torch_model = SubsidenceLSTMForecaster()
                self.torch_model.load_state_dict(torch.load(self.pth_path, map_location=torch.device('cpu')))
                self.torch_model.eval()
                self.scaler = joblib.load(self.scaler_path)
                print(f"[FORECAST_SERVICE] Deep LSTM Model loaded from {self.pth_path}")
            else:
                print(f"[FORECAST_SERVICE NOTE] Model weights not found at {self.pth_path}. Using kinematic fallback.")
        except Exception as ex:
            print(f"[FORECAST_SERVICE NOTE] Torch initialization notice ({ex}). Using kinematic fallback.")
            self.torch_model = None

    def record_reading(self, node_id: str, displacement_mm: float):
        """Appends a new displacement observation to node's lookback sequence."""
        self.node_displacement_buffers[node_id].append(float(displacement_mm))

    def calculate_time_to_failure(self, forecast_trajectory: List[float], current_disp: float) -> Optional[float]:
        """
        Calculates exact fractional Time-to-Failure (TTF) in hours using linear
        interpolation across the 6-hour forecast trajectory.
        Returns:
            fractional hours (e.g. 4.2) or None if critical threshold is not breached.
        """
        threshold = self.critical_threshold_mm
        
        # Already breached
        if current_disp >= threshold:
            return 0.0
            
        # Trajectory represents [t+1h, t+2h, t+3h, t+4h, t+5h, t+6h]
        points = [current_disp] + list(forecast_trajectory)
        times = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

        for i in range(len(points) - 1):
            d_start, d_end = points[i], points[i+1]
            t_start, t_end = times[i], times[i+1]

            if d_start < threshold <= d_end:
                if d_end - d_start > 1e-6:
                    fraction = (threshold - d_start) / (d_end - d_start)
                    ttf_hours = t_start + fraction * (t_end - t_start)
                    return round(float(ttf_hours), 1)
                return round(float(t_end), 1)

        # No breach predicted within 6-hour horizon
        return None

    def predict_future_trajectory(self, node_id: str) -> Dict[str, Any]:
        """
        Generates 6-step multi-hour forecast and TTF alert payload.
        """
        buf = self.node_displacement_buffers[node_id]
        if len(buf) == 0:
            current_disp = 0.50
            history_arr = np.full((LOOKBACK_STEPS,), current_disp, dtype=np.float32)
        else:
            current_disp = buf[-1]
            raw_list = list(buf)
            # Reconstruct sequence with recent velocity slope if warming up
            if len(raw_list) < LOOKBACK_STEPS:
                pad_len = LOOKBACK_STEPS - len(raw_list)
                # Compute slope
                if len(raw_list) >= 2:
                    slope = (raw_list[-1] - raw_list[0]) / len(raw_list)
                    # Back-extrapolate
                    back_pad = [max(0.05, raw_list[0] - slope * (pad_len - i)) for i in range(pad_len)]
                else:
                    back_pad = [raw_list[0]] * pad_len
                history_arr = np.array(back_pad + raw_list, dtype=np.float32)
            else:
                history_arr = np.array(raw_list[-LOOKBACK_STEPS:], dtype=np.float32)

        # -------------------------------------------------------------
        # 1. Model Inference (LSTM or Kinematic Gradient Extrapolator)
        # -------------------------------------------------------------
        forecast_values = []
        if self.torch_model and self.scaler:
            try:
                import torch
                scaled_in = self.scaler.transform(history_arr.reshape(-1, 1)).reshape(1, LOOKBACK_STEPS, 1)
                with torch.no_grad():
                    tensor_in = torch.tensor(scaled_in, dtype=torch.float32)
                    # Predicts forward increments [delta_1h, delta_2h, ..., delta_6h] >= 0
                    increments = self.torch_model(tensor_in).numpy().flatten()
                
                # Cumulative absolute trajectory: y[t+h] = current_disp + increment
                projected = current_disp + np.maximum.accumulate(increments)
                # Physical smoothing against minimum trend
                recent = history_arr[-10:]
                v_rate = float(np.mean(np.diff(recent))) if len(recent) > 1 else 0.0
                if v_rate > 0.1: # Rapid active subsidence
                    projected = np.maximum(projected, [current_disp + v_rate * 15 * h for h in range(1, 7)])

                forecast_values = [round(float(v), 2) for v in projected]
            except Exception as e:
                forecast_values = []

        if not forecast_values:
            # Kinematic Taylor Extrapolator Fallback
            recent = history_arr[-10:]
            v_step = float(np.mean(np.diff(recent))) if len(recent) > 1 else 0.02
            v_hour = max(0.05, v_step * 20.0)
            a_hour = (v_hour * 0.12) if v_hour > 0.5 else 0.0

            for h in range(1, FORECAST_HORIZON_HOURS + 1):
                projected = current_disp + (v_hour * h) + (0.5 * a_hour * (h**2))
                forecast_values.append(round(float(projected), 2))

        # -------------------------------------------------------------
        # 2. Time-to-Failure (TTF) Calculation
        # -------------------------------------------------------------
        ttf_hours = self.calculate_time_to_failure(forecast_values, current_disp)

        if ttf_hours is not None:
            status_msg = f"Estimated time to critical subsidence threshold: {ttf_hours} hours"
            alert_severity = "CRITICAL" if ttf_hours <= 2.0 else "WARNING"
        else:
            status_msg = f"Trajectory stable. No critical breach ({self.critical_threshold_mm} mm) predicted within 6 hours."
            alert_severity = "NORMAL"

        return {
            "node_id": node_id,
            "current_displacement_mm": round(float(current_disp), 2),
            "critical_threshold_mm": self.critical_threshold_mm,
            "forecast_horizon_hours": FORECAST_HORIZON_HOURS,
            "time_to_critical_hours": ttf_hours,
            "status_message": status_msg,
            "alert_severity": alert_severity,
            "forecast_trajectory": forecast_values,
            "hourly_intervals": [f"t+{h}h" for h in range(1, FORECAST_HORIZON_HOURS + 1)],
            "buffer_fill_pct": round(min(1.0, len(buf) / LOOKBACK_STEPS) * 100, 1)
        }

# Global Singleton Instance
forecast_service = SubsidenceForecastService(critical_threshold_mm=35.0)
