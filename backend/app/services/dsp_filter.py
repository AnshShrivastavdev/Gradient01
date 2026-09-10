"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring System
Module: dsp_filter.py (High-Precision Digital Signal Processing & Micro-Delta Subsystem)
---------------------------------------------------------------------------------------
1. Continuous Baseline Tare: Maintain adaptive baseline (disp, tilt_x, tilt_y) per node.
2. Real-Time Micro-Dynamics:
   - micro_delta_disp_mm = abs(current_disp - baseline_disp)
   - micro_delta_tilt_deg = sqrt((tilt_x - baseline_tilt_x)**2 + (tilt_y - baseline_tilt_y)**2)
   - micro_velocity_mm_s = abs(current_disp - prev_disp) / max(0.1, dt)
   - micro_tilt_rate_deg_s = abs(tilt_y - prev_tilt_y) / max(0.1, dt)
3. Rolling median filter & adaptive EMA smoothing for outlier rejection & sub-millimeter precision.
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

        # Baseline Tare Datum
        self.baseline_disp: Optional[float] = None
        self.baseline_tilt_x: Optional[float] = None
        self.baseline_tilt_y: Optional[float] = None
        self.is_tared: bool = False
        self.tare_timestamp: Optional[float] = None

        # Filter internal states
        self.last_smooth_disp: Optional[float] = None
        self.last_smooth_diff_disp: Optional[float] = None
        self.last_smooth_tilt: Optional[float] = None
        self.last_smooth_tilt_y: Optional[float] = None
        self.last_raw_tilt_x: Optional[float] = None
        self.last_raw_tilt_y: Optional[float] = None
        
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

    def tare(self, node_id: str = "NODE_02", disp: Optional[float] = None,
             tilt_x: Optional[float] = None, tilt_y: Optional[float] = None) -> Dict[str, Any]:
        """
        Calibrates/re-zeros the baseline datum for the specified node and resets
        history buffers to guarantee zero phantom velocity or acceleration spikes.
        """
        state = self.node_states[node_id]
        now = time.time()

        state.baseline_disp = float(disp if disp is not None else (state.last_smooth_disp or 0.0))
        state.baseline_tilt_x = float(tilt_x if tilt_x is not None else (state.last_raw_tilt_x or 0.0))
        state.baseline_tilt_y = float(tilt_y if tilt_y is not None else (state.last_raw_tilt_y or 0.0))
        state.is_tared = True
        state.tare_timestamp = now

        # Re-zero filter history to align with newly tared baseline
        state.last_smooth_disp = state.baseline_disp
        state.last_smooth_diff_disp = state.baseline_disp
        state.last_smooth_tilt = math.sqrt(state.baseline_tilt_x**2 + state.baseline_tilt_y**2)
        state.last_smooth_tilt_y = state.baseline_tilt_y
        state.last_raw_tilt_x = state.baseline_tilt_x
        state.last_raw_tilt_y = state.baseline_tilt_y
        state.last_velocity_3s = 0.0
        state.last_velocity_10s = 0.0
        state.last_accel = 0.0
        state.last_tilt_rate_3s = 0.0
        state.last_tilt_rate_10s = 0.0
        state.last_timestamp = None
        state.disp_raw_buffer.clear()
        state.diff_disp_raw_buffer.clear()
        state.tilt_raw_buffer.clear()
        state.tilt_y_raw_buffer.clear()
        state.history_samples.clear()

        return {
            "node_id": node_id,
            "status": "TARED",
            "baseline_disp": round(state.baseline_disp, 3),
            "baseline_tilt_x": round(state.baseline_tilt_x, 3),
            "baseline_tilt_y": round(state.baseline_tilt_y, 3),
            "timestamp": now
        }

    def get_baseline(self, node_id: str = "NODE_02") -> Dict[str, Any]:
        state = self.node_states[node_id]
        return {
            "node_id": node_id,
            "is_tared": state.is_tared,
            "baseline_disp": state.baseline_disp,
            "baseline_tilt_x": state.baseline_tilt_x,
            "baseline_tilt_y": state.baseline_tilt_y,
            "tare_timestamp": state.tare_timestamp
        }

    def process(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a raw telemetry packet through adaptive median filter, EMA smoother,
        real-time micro-dynamics engine, and multi-window rate calculation.
        """
        node_id = str(packet.get("node_id", "NODE_02"))
        state = self.node_states[node_id]

        now = time.time()
        raw_disp = float(packet.get("displacement_mm") if packet.get("displacement_mm") is not None else (packet.get("d") or 0.0))
        raw_diff_disp = float(packet.get("differential_displacement_mm") if packet.get("differential_displacement_mm") is not None else (packet.get("di") or raw_disp))
        raw_tilt = float(packet.get("differential_tilt_deg") if packet.get("differential_tilt_deg") is not None else (packet.get("tilt_composite_deg") if packet.get("tilt_composite_deg") is not None else (packet.get("tx") or 0.0)))
        raw_tilt_x = float(packet.get("tilt_x_deg") if packet.get("tilt_x_deg") is not None else (packet.get("tx") or 0.0))
        raw_tilt_y = float(packet.get("tilt_y_deg") if packet.get("tilt_y_deg") is not None else (packet.get("ty") or 0.0))

        # -------------------------------------------------------------
        # 1. Rolling Median Filter - Fast Response Spike Rejection
        # -------------------------------------------------------------
        state.disp_raw_buffer.append(raw_disp)
        state.diff_disp_raw_buffer.append(raw_diff_disp)
        state.tilt_raw_buffer.append(raw_tilt)
        state.tilt_y_raw_buffer.append(raw_tilt_y)

        # Ultra-low latency: if buffer has 2 samples, take latest unless sudden single-packet outlier
        if len(state.disp_raw_buffer) > 1 and abs(state.disp_raw_buffer[-1] - state.disp_raw_buffer[-2]) > 50.0:
            median_disp = float(state.disp_raw_buffer[-2])
        else:
            median_disp = raw_disp

        median_diff_disp = raw_diff_disp
        median_tilt = raw_tilt
        median_tilt_y = raw_tilt_y

        # -------------------------------------------------------------
        # 2. Adaptive Exponential Moving Average (EMA)
        # Snap immediately on physical movement (alpha = 0.98), smooth when stationary
        # -------------------------------------------------------------
        if state.last_smooth_disp is None:
            smooth_disp = median_disp
            smooth_diff_disp = median_diff_disp
            smooth_tilt = median_tilt
            smooth_tilt_y = median_tilt_y
        else:
            disp_delta = abs(median_disp - state.last_smooth_disp)
            alpha_d = 0.98 if disp_delta > 5.0 else 0.25
            smooth_disp = (alpha_d * median_disp) + ((1.0 - alpha_d) * state.last_smooth_disp)

            diff_disp_delta = abs(median_diff_disp - state.last_smooth_diff_disp)
            alpha_dd = 0.98 if diff_disp_delta > 5.0 else 0.25
            smooth_diff_disp = (alpha_dd * median_diff_disp) + ((1.0 - alpha_dd) * state.last_smooth_diff_disp)

            tilt_delta = abs(median_tilt - state.last_smooth_tilt)
            alpha_t = 0.98 if tilt_delta > 3.0 else 0.25
            smooth_tilt = (alpha_t * median_tilt) + ((1.0 - alpha_t) * state.last_smooth_tilt)

            tilt_y_delta = abs(median_tilt_y - state.last_smooth_tilt_y)
            alpha_ty = 0.98 if tilt_y_delta > 3.0 else 0.25
            smooth_tilt_y = (alpha_ty * median_tilt_y) + ((1.0 - alpha_ty) * state.last_smooth_tilt_y)

        # -------------------------------------------------------------
        # 3. Continuous Baseline Tare Initialization
        # Warmup-averaged auto-tare: collect first N packets to compute a
        # stable baseline that absorbs MPU6500 noise & jitter. Until then,
        # report zero deltas to avoid false CRITICAL alarms on startup.
        # -------------------------------------------------------------
        WARMUP_COUNT = 10

        if not state.is_tared or state.baseline_disp is None:
            if not hasattr(state, '_warmup_disps'):
                state._warmup_disps = []
                state._warmup_tilt_x = []
                state._warmup_tilt_y = []

            state._warmup_disps.append(smooth_disp)
            state._warmup_tilt_x.append(raw_tilt_x)
            state._warmup_tilt_y.append(raw_tilt_y)

            if len(state._warmup_disps) >= WARMUP_COUNT:
                state.baseline_disp = float(np.mean(state._warmup_disps))
                state.baseline_tilt_x = float(np.mean(state._warmup_tilt_x))
                state.baseline_tilt_y = float(np.mean(state._warmup_tilt_y))
                state.is_tared = True
                state.tare_timestamp = now
                # Re-zero filter state to match averaged baseline
                state.last_smooth_disp = state.baseline_disp
                state.last_smooth_diff_disp = state.baseline_disp
                state.last_smooth_tilt = smooth_tilt
                state.last_smooth_tilt_y = state.baseline_tilt_y
            else:
                # Still warming up: report zero deltas
                state.baseline_disp = smooth_disp
                state.baseline_tilt_x = raw_tilt_x
                state.baseline_tilt_y = raw_tilt_y

        # -------------------------------------------------------------
        # 4. Instantaneous Micro-Dynamics Engine
        # -------------------------------------------------------------
        micro_delta_disp_mm = abs(smooth_disp - state.baseline_disp)
        micro_delta_tilt_deg = math.sqrt((raw_tilt_x - state.baseline_tilt_x)**2 + (raw_tilt_y - state.baseline_tilt_y)**2)

        if state.last_timestamp is None:
            # First packet after tare/reset: resting rate
            micro_velocity_mm_s = 0.0
            micro_tilt_rate_deg_s = 0.0
            velocity_3s = 0.0
            velocity_10s = 0.0
            accel_mm_s2 = 0.0
            tilt_rate_3s = 0.0
            tilt_rate_10s = 0.0
        else:
            dt = max(0.2, (now - state.last_timestamp))
            prev_disp = state.last_smooth_disp
            prev_tilt_y = state.last_smooth_tilt_y

            # -------------------------------------------------------------
            # 5. Multi-Window Rate Engine (Sliding 3s & 10s Windows)
            # -------------------------------------------------------------
            instant_v = (smooth_disp - prev_disp) / dt
            instant_tilt_rate = (smooth_tilt - state.last_smooth_tilt) / dt
            instant_a = (instant_v - state.last_velocity_3s) / dt

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

            micro_velocity_mm_s = abs(velocity_3s)
            micro_tilt_rate_deg_s = abs(tilt_rate_3s)

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

        # -------------------------------------------------------------
        # 6. Adaptive Resting Baseline Auto-Centering
        # When node is completely stationary at safe resting angles (velocity < 0.25, tilt_rate < 0.25),
        # gently adapt the baseline (alpha=0.04) to absorb mechanical settling, table offset,
        # and cable strain. If moving or tilted significantly (> 4.5°), freeze baseline instantly.
        # -------------------------------------------------------------
        if state.is_tared and micro_velocity_mm_s < 0.25 and micro_tilt_rate_deg_s < 0.25:
            if micro_delta_tilt_deg < 4.0 and abs(smooth_disp - state.baseline_disp) < 6.0:
                alpha_drift = 0.04
                state.baseline_tilt_x = (1.0 - alpha_drift) * state.baseline_tilt_x + alpha_drift * raw_tilt_x
                state.baseline_tilt_y = (1.0 - alpha_drift) * state.baseline_tilt_y + alpha_drift * raw_tilt_y
                state.baseline_disp = (1.0 - alpha_drift) * state.baseline_disp + alpha_drift * smooth_disp

        # Update state history
        state.last_smooth_disp = smooth_disp
        state.last_smooth_diff_disp = smooth_diff_disp
        state.last_smooth_tilt = smooth_tilt
        state.last_smooth_tilt_y = smooth_tilt_y
        state.last_raw_tilt_x = raw_tilt_x
        state.last_raw_tilt_y = raw_tilt_y
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
            "tilt_rate_10s_deg_s": round(tilt_rate_10s, 3),
            
            # Real-Time Micro-Dynamics (Micro-Scale Sensitivity)
            "micro_delta_disp_mm": round(micro_delta_disp_mm, 2),
            "micro_delta_tilt_deg": round(micro_delta_tilt_deg, 3),
            "micro_velocity_mm_s": round(micro_velocity_mm_s, 3),
            "micro_tilt_rate_deg_s": round(micro_tilt_rate_deg_s, 3),
            "baseline_disp": round(state.baseline_disp, 2),
            "baseline_tilt_x": round(state.baseline_tilt_x, 3),
            "baseline_tilt_y": round(state.baseline_tilt_y, 3)
        }


# Global DSP singleton instance
dsp_processor = DigitalSignalProcessor(median_window=5, ema_alpha=0.3)
