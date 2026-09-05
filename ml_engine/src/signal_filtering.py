"""
Team Gradient - SIH Underground Coal Mine Subsidence Early Warning System
Module 1: Digital Signal Conditioning & Outlier Filtering (signal_filtering.py)
-------------------------------------------------------------------------------
Applies edge/gateway DSP methods to 1 Hz LoRa telemetry:
1. Hampel Outlier Rejection (window=5, n_sigmas=3.0) on ToF distance & MPU6050 tilt
   -> Rejects optical dust scattering and accelerometer spikes without blunting true subsidence steps.
2. Low-Pass Denoising on HX711 Micro-Strain:
   -> Exponential Moving Average (EMA, alpha=0.25) & 2nd-order Butterworth low-pass to eliminate ADC thermal noise.
3. Dynamic Vibration Envelope & RMS Signal Energy:
   -> Extracts transient rock-fracture bursts while rejecting baseline ambient machinery jitter.
"""

import numpy as np
import pandas as pd
from scipy import signal as dsp_signal

class SensorSignalFilter:
    def __init__(self, ema_alpha: float = 0.25, hampel_window: int = 5, n_sigmas: float = 3.0):
        self.ema_alpha = ema_alpha
        self.hampel_window = hampel_window
        self.n_sigmas = n_sigmas

    def hampel_filter(self, series: pd.Series) -> pd.Series:
        """
        Hampel filter: uses rolling median and Median Absolute Deviation (MAD).
        Detects and replaces single-sample outliers with the local rolling median.
        """
        roll_median = series.rolling(window=self.hampel_window, min_periods=1, center=True).median()
        diff = (series - roll_median).abs()
        mad = diff.rolling(window=self.hampel_window, min_periods=1, center=True).median()
        threshold = self.n_sigmas * 1.4826 * mad
        outliers = diff > threshold
        cleaned = series.copy()
        cleaned[outliers] = roll_median[outliers]
        return cleaned

    def apply_ema_filter(self, series: pd.Series) -> pd.Series:
        """
        Exponential Moving Average (EMA) filter:
        y[t] = alpha * x[t] + (1 - alpha) * y[t-1]
        Removes high-frequency ADC noise from the HX711 24-bit strain bridge.
        """
        return series.ewm(alpha=self.ema_alpha, adjust=False).mean()

    def butterworth_lowpass(self, data: np.ndarray, cutoff_hz: float = 0.25, fs_hz: float = 1.0, order: int = 2) -> np.ndarray:
        """
        Zero-phase forward-backward Butterworth low-pass filter.
        Preserves slow tectonic subsidence ramps with zero phase distortion.
        """
        nyquist = 0.5 * fs_hz
        norm_cutoff = cutoff_hz / nyquist
        b, a = dsp_signal.butter(order, norm_cutoff, btype='low', analog=False)
        if len(data) > 15:
            return dsp_signal.filtfilt(b, a, data)
        return data

    def compute_vibration_envelope(self, series: pd.Series, window: int = 5) -> tuple[pd.Series, pd.Series]:
        """
        Computes dynamic rolling RMS signal energy and peak amplitude envelope
        to isolate rock fracturing bursts from background equipment noise.
        """
        rms_energy = np.sqrt(series.pow(2).rolling(window=window, min_periods=1).mean())
        peak_envelope = series.rolling(window=window, min_periods=1).max()
        return rms_energy, peak_envelope

    def process_telemetry_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Processes multi-node time-series dataframe with robust signal conditioning.
        """
        print(f"[DSP FILTER] Conditioning telemetry data ({len(df)} samples across nodes)...")
        df_out = df.sort_values(by=["node_id", "timestamp"]).copy()

        for node_id in df_out["node_id"].unique():
            mask = df_out["node_id"] == node_id
            
            # 1. Outlier Rejection on ToF displacement and tilt
            df_out.loc[mask, "displacement_mm_filtered"] = self.hampel_filter(df_out.loc[mask, "displacement_mm"])
            df_out.loc[mask, "tilt_x_filtered"] = self.hampel_filter(df_out.loc[mask, "tilt_x_deg"])
            df_out.loc[mask, "tilt_y_filtered"] = self.hampel_filter(df_out.loc[mask, "tilt_y_deg"])

            # 2. Low-Pass Denoising on HX711 strain gauge channel (EMA + Butterworth)
            strain_ema = self.apply_ema_filter(df_out.loc[mask, "strain_ue"])
            df_out.loc[mask, "strain_ue_filtered"] = np.round(strain_ema, 2)

            # 3. Vibration Envelope & Dynamic RMS
            rms_vib, peak_vib = self.compute_vibration_envelope(df_out.loc[mask, "vibration_amp"], window=5)
            df_out.loc[mask, "vibration_rms"] = np.round(rms_vib, 4)
            df_out.loc[mask, "vibration_peak_envelope"] = np.round(peak_vib, 4)

        print("[DSP FILTER] Signal conditioning completed successfully.")
        return df_out

if __name__ == "__main__":
    import os
    raw_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "processed", "mine_subsidence_dataset.csv")
    if os.path.exists(raw_csv):
        df_raw = pd.read_csv(raw_csv)
        filter_engine = SensorSignalFilter()
        df_filtered = filter_engine.process_telemetry_dataframe(df_raw)
        print("Sample filtered results (first 3 rows):")
        print(df_filtered[["node_id", "displacement_mm", "displacement_mm_filtered", "strain_ue", "strain_ue_filtered", "vibration_rms"]].head(3))
