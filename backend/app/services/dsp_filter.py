"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring System
Module: dsp_filter.py (Digital Signal Processing & Continuous Smoothing Subsystem)
-----------------------------------------------------------------------------------
Solves discrete/stepped jumps when physically moving the hardware node:
1. Adaptive Rolling Median Filter (window=5) on displacement to reject laser multipath spikes.
2. Exponential Moving Average (EMA, alpha=0.3) for smooth, continuous sub-millimeter tracking.
3. Low-Pass Filter on differential tilt and Y-axis angles.
4. Dynamic Rate Engine: Real-time velocity (Δd/Δt in mm/s), acceleration (d²d/dt² in mm/s²),
   and angular tilt rate (deg/s) over sliding 3s and 10s windows.
"""

import time
import math
import collections
from typing import Dict, Any, Optional, Tuple, List
import numpy as np


class NodeDSPState:
    def __init__(self, median_window: int = 5, ema_alpha: float = 0.3):
        self.median_window = median_window
        self.ema_alpha = ema_alpha

        # Raw history buffers for median filtering (spike & laser multipath outlier rejection)
        self.disp_raw_buffer = collections.deque(maxlen=median_window)
        self.diff_disp_raw_buffer = collections.deque(maxlen=median_window)
        self.tilt_raw_buffer = collections.deque(maxlen=median_window)
        self.tilt_y_raw_buffer = collections.deque(maxlen=median_window)

        # Filtered history with timestamps: (epoch_sec, smooth_disp, smooth_tilt, smooth_tilt_y)
        self.history_samples = collections.deque(maxlen=60)

        # Filter internal states
        self.last_smooth_disp: Optional[float] = None
        self.last_smooth_diff_disp: Optional[float] = None
        self.last_smooth_tilt: Optional[float] = None
        self.last_smooth_tilt_y: Optional[float] = None
        
        self.last_velocity_3s: float = 0.0
        self.last_velocity_10s: float = 0.0
        self.last_accel: float = 0.0
        self.last_tilt_rate_3s: float = 0.0
        self.last_tilt_rate_10s: float = 0.0
        self.last_timestamp: Optional[float] = None


class DigitalSignalProcessor:
    def __init__(self, median_window: int = 5, ema_alpha: float = 0.3):
        self.median_window = median_window
        self.ema_alpha = ema_alpha
        self.node_states: Dict[str, NodeDSPState] = collections.defaultdict(
            lambda: NodeDSPState(median_window=self.median_window, ema_alpha=self.ema_alpha)
        )

    def process(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a raw telemetry packet through adaptive median filter, EMA smoother,
        and the dynamic rate calculation engine across sliding 3s and 10s windows.
        """
        node_id = str(packet.get("node_id", "NODE_02"))
        state = self.node_states[node_id]

        now = time.time()
        raw_disp = float(packet.get("displacement_mm") or 382.0)
        raw_diff_disp = float(packet.get("differential_displacement_mm") or raw_disp)
        raw_tilt = float(packet.get("differential_tilt_deg") or packet.get("tilt_composite_deg") or 0.0)
        raw_tilt_y = float(packet.get("tilt_y_deg") or 0.0)

        # -------------------------------------------------------------
        # 1. Rolling Median Filter (Window = 2) - Fast Response Spike Rejection
        # -------------------------------------------------------------
        state.disp_raw_buffer.append(raw_disp)
        state.diff_disp_raw_buffer.append(raw_diff_disp)
        state.tilt_raw_buffer.append(raw_tilt)
        state.tilt_y_raw_buffer.append(raw_tilt_y)

        # Ultra-low latency: if buffer has 2 samples, take latest unless sudden single-packet outlier
        if len(state.disp_raw_buffer) > 1 and abs(state.disp_raw_buffer[-1] - state.disp_raw_buffer[-2]) > 100.0:
            median_disp = float(state.disp_raw_buffer[-2])
        else:
            median_disp = raw_disp

        median_diff_disp = raw_diff_disp
        median_tilt = raw_tilt
        median_tilt_y = raw_tilt_y

        # -------------------------------------------------------------
        # 2. Adaptive Exponential Moving Average (EMA)
        # When physical motion is detected (|delta| > 1.0), snap immediately (alpha = 0.95)
        # When stationary, gently smooth (|delta| <= 1.0, alpha = 0.50)
        # -------------------------------------------------------------
        if state.last_smooth_disp is None:
            smooth_disp = median_disp
            smooth_diff_disp = median_diff_disp
            smooth_tilt = median_tilt
            smooth_tilt_y = median_tilt_y
        else:
            # Adaptive alpha for displacement
            disp_delta = abs(median_disp - state.last_smooth_disp)
            alpha_d = 0.95 if disp_delta > 1.5 else 0.50
            smooth_disp = (alpha_d * median_disp) + ((1.0 - alpha_d) * state.last_smooth_disp)

            diff_disp_delta = abs(median_diff_disp - state.last_smooth_diff_disp)
            alpha_dd = 0.95 if diff_disp_delta > 1.5 else 0.50
            smooth_diff_disp = (alpha_dd * median_diff_disp) + ((1.0 - alpha_dd) * state.last_smooth_diff_disp)

            # Adaptive alpha for tilt (instant response when tilting sensor in hand)
            tilt_delta = abs(median_tilt - state.last_smooth_tilt)
            alpha_t = 0.95 if tilt_delta > 0.8 else 0.50
            smooth_tilt = (alpha_t * median_tilt) + ((1.0 - alpha_t) * state.last_smooth_tilt)

            tilt_y_delta = abs(median_tilt_y - state.last_smooth_tilt_y)
            alpha_ty = 0.95 if tilt_y_delta > 0.8 else 0.50
            smooth_tilt_y = (alpha_ty * median_tilt_y) + ((1.0 - alpha_ty) * state.last_smooth_tilt_y)

        # -------------------------------------------------------------
        # 3. Dynamic Rate Engine (Sliding 3s and 10s Windows)
        # -------------------------------------------------------------
        velocity_3s = 0.0
        velocity_10s = 0.0
        accel_mm_s2 = 0.0
        tilt_rate_3s = 0.0
        tilt_rate_10s = 0.0

        if state.last_timestamp is not None:
            dt = max(0.05, now - state.last_timestamp)

            # Instantaneous rate
            instant_v = (smooth_disp - state.last_smooth_disp) / dt
            instant_tilt_rate = (smooth_tilt - state.last_smooth_tilt) / dt
            instant_a = (instant_v - state.last_velocity_3s) / dt

            # Multi-sample sliding 3s window regression
            samples_3s = [s for s in state.history_samples if (now - s[0]) <= 3.5]
            if len(samples_3s) >= 3:
                times_3s = [s[0] - samples_3s[0][0] for s in samples_3s]
                disps_3s = [s[1] for s in samples_3s]
                tilts_3s = [s[2] for s in samples_3s]
                slope_v, _ = np.polyfit(times_3s, disps_3s, 1)
                slope_t, _ = np.polyfit(times_3s, tilts_3s, 1)
                velocity_3s = float(slope_v)
                tilt_rate_3s = float(slope_t)
            else:
                velocity_3s = instant_v
                tilt_rate_3s = instant_tilt_rate

            # Multi-sample sliding 10s window regression
            samples_10s = [s for s in state.history_samples if (now - s[0]) <= 10.5]
            if len(samples_10s) >= 5:
                times_10s = [s[0] - samples_10s[0][0] for s in samples_10s]
                disps_10s = [s[1] for s in samples_10s]
                tilts_10s = [s[2] for s in samples_10s]
                slope_v10, _ = np.polyfit(times_10s, disps_10s, 1)
                slope_t10, _ = np.polyfit(times_10s, tilts_10s, 1)
                velocity_10s = float(slope_v10)
                tilt_rate_10s = float(slope_t10)
            else:
                velocity_10s = velocity_3s
                tilt_rate_10s = tilt_rate_3s

            accel_mm_s2 = instant_a

        # Update state history
        state.last_smooth_disp = smooth_disp
        state.last_smooth_diff_disp = smooth_diff_disp
        state.last_smooth_tilt = smooth_tilt
        state.last_smooth_tilt_y = smooth_tilt_y
        state.last_velocity_3s = velocity_3s
        state.last_velocity_10s = velocity_10s
        state.last_accel = accel_mm_s2
        state.last_tilt_rate_3s = tilt_rate_3s
        state.last_tilt_rate_10s = tilt_rate_10s
        state.last_timestamp = now
        state.history_samples.append((now, smooth_disp, smooth_tilt, smooth_tilt_y))

        return {
            "smooth_disp_mm": round(smooth_disp, 2),
            "smooth_diff_disp_mm": round(smooth_diff_disp, 2),
            "disp_velocity_mm_s": round(velocity_3s, 3),
            "disp_velocity_3s_mm_s": round(velocity_3s, 3),
            "disp_velocity_10s_mm_s": round(velocity_10s, 3),
            "disp_accel_mm_s2": round(accel_mm_s2, 4),
            "smooth_tilt_deg": round(smooth_tilt, 3),
            "smooth_tilt_y_deg": round(smooth_tilt_y, 3),
            "tilt_rate_deg_s": round(tilt_rate_3s, 3),
            "tilt_rate_3s_deg_s": round(tilt_rate_3s, 3),
            "tilt_rate_10s_deg_s": round(tilt_rate_10s, 3)
        }


# Global DSP singleton instance
dsp_processor = DigitalSignalProcessor(median_window=5, ema_alpha=0.3)
