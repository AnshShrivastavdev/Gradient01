"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring
Module: feature_engineering.py (Rolling Window Feature Extraction)
------------------------------------------------------------------
"""

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "tilt_x_deg", "tilt_y_deg", "tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp",
    "tilt_composite_deg_mean_5s", "tilt_composite_deg_std_5s", "tilt_composite_deg_roc_5s",
    "displacement_mm_mean_5s", "displacement_mm_std_5s", "displacement_mm_roc_5s",
    "strain_ue_mean_5s", "strain_ue_std_5s", "strain_ue_roc_5s",
    "vibration_amp_mean_5s", "vibration_amp_std_5s", "vibration_amp_roc_5s"
]

def extract_rolling_features(df: pd.DataFrame, window_size: int = 5) -> pd.DataFrame:
    df_sorted = df.sort_values(by=["node_id", "timestamp"]).copy()
    df_sorted["tilt_composite_deg"] = np.sqrt(df_sorted["tilt_x_deg"]**2 + df_sorted["tilt_y_deg"]**2)

    base_signals = ["tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp"]
    feature_series = [df_sorted]

    for sig in base_signals:
        roll_mean = df_sorted.groupby("node_id")[sig].rolling(window=window_size, min_periods=1).mean().reset_index(level=0, drop=True)
        roll_std = df_sorted.groupby("node_id")[sig].rolling(window=window_size, min_periods=1).std().fillna(0.0).reset_index(level=0, drop=True)
        roc = df_sorted.groupby("node_id")[sig].diff().fillna(0.0).reset_index(level=0, drop=True)

        feature_series.append(pd.Series(roll_mean, name=f"{sig}_mean_{window_size}s"))
        feature_series.append(pd.Series(roll_std, name=f"{sig}_std_{window_size}s"))
        feature_series.append(pd.Series(roc, name=f"{sig}_roc_{window_size}s"))

    result_df = pd.concat(feature_series, axis=1)
    return result_df
