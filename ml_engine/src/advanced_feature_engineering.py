"""
Team Gradient - SIH Underground Coal Mine Subsidence Early Warning System
Module 2: Advanced Geotechnical Multi-Scale Feature Engineering
(advanced_feature_engineering.py)
--------------------------------------------------------------------------
Extracts domain-specific geomechanical features across small (3s), medium (10s),
and large (30s) rolling temporal horizons per physical ESP32 node:

1. Total Tilt Vector Angle: theta = sqrt(tilt_x^2 + tilt_y^2)
2. Ground Deformation Velocity & Acceleration:
   - 1st Derivative (Velocity): v_disp = Delta d / Delta t (mm/s)
   - 2nd Derivative (Acceleration): a_disp = Delta^2 d / Delta t^2 (mm/s^2)
3. Strain Rate:
   - dot_epsilon = Delta epsilon / Delta t (ue/s) capturing accelerating yield
4. Vibration Volatility & Energy:
   - Dynamic rolling standard deviation, peak envelope, and RMS energy
5. Multi-Sensor Cross-Channel Interaction:
   - Rockburst / Subsidence Hazard Index: (Deformation Velocity * Strain Rate)
"""

import numpy as np
import pandas as pd

class AdvancedFeatureEngineer:
    def __init__(self, windows=(3, 10, 30)):
        self.windows = windows

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        print(f"[FEATURE ENGINE] Extracting multi-scale temporal features across windows {self.windows}s...")
        df_out = df.sort_values(by=["node_id", "timestamp"]).copy()

        # 1. Total Resultant Inclinometer Tilt: theta = sqrt(tilt_x^2 + tilt_y^2)
        tilt_x = df_out.get("tilt_x_filtered", df_out["tilt_x_deg"])
        tilt_y = df_out.get("tilt_y_filtered", df_out["tilt_y_deg"])
        df_out["tilt_total_deg"] = np.round(np.sqrt(tilt_x**2 + tilt_y**2), 4)

        disp = df_out.get("displacement_mm_filtered", df_out["displacement_mm"])
        strain = df_out.get("strain_ue_filtered", df_out["strain_ue"])
        vib = df_out.get("vibration_amp", df_out["vibration_amp"])

        # 2. 1st and 2nd Order Derivatives (Velocity & Acceleration) per Node
        # Deformation Velocity: Delta d / Delta t
        df_out["disp_velocity_mms"] = df_out.groupby("node_id")[disp.name].diff().fillna(0.0)
        # Deformation Acceleration: Delta^2 d / Delta t^2
        df_out["disp_accel_mms2"] = df_out.groupby("node_id")["disp_velocity_mms"].diff().fillna(0.0)

        # Strain Rate: Delta epsilon / Delta t
        df_out["strain_rate_ues"] = df_out.groupby("node_id")[strain.name].diff().fillna(0.0)

        # Tilt Rate: Delta theta / Delta t
        df_out["tilt_rate_degs"] = df_out.groupby("node_id")["tilt_total_deg"].diff().fillna(0.0)

        # 3. Cross-Channel Interaction: (Deformation Velocity * Strain Rate)
        # Physical meaning: High velocity combined with high strain rate flags imminent rock burst / shear collapse
        df_out["rockburst_hazard_index"] = np.round(
            df_out["disp_velocity_mms"].abs() * df_out["strain_rate_ues"].abs(), 4
        )

        # 4. Multi-Scale Temporal Windows (Small: 3s, Medium: 10s, Large: 30s)
        for w in self.windows:
            # Displacement rolling statistics
            df_out[f"disp_mean_{w}s"] = df_out.groupby("node_id")[disp.name].rolling(w, min_periods=1).mean().reset_index(drop=True)
            df_out[f"disp_std_{w}s"] = df_out.groupby("node_id")[disp.name].rolling(w, min_periods=1).std().fillna(0.0).reset_index(drop=True)
            df_out[f"disp_max_{w}s"] = df_out.groupby("node_id")[disp.name].rolling(w, min_periods=1).max().reset_index(drop=True)

            # Strain rolling statistics
            df_out[f"strain_mean_{w}s"] = df_out.groupby("node_id")[strain.name].rolling(w, min_periods=1).mean().reset_index(drop=True)
            df_out[f"strain_std_{w}s"] = df_out.groupby("node_id")[strain.name].rolling(w, min_periods=1).std().fillna(0.0).reset_index(drop=True)

            # Tilt rolling statistics
            df_out[f"tilt_mean_{w}s"] = df_out.groupby("node_id")["tilt_total_deg"].rolling(w, min_periods=1).mean().reset_index(drop=True)
            df_out[f"tilt_std_{w}s"] = df_out.groupby("node_id")["tilt_total_deg"].rolling(w, min_periods=1).std().fillna(0.0).reset_index(drop=True)

            # Vibration volatility (RMS energy & peak shock)
            df_out[f"vib_rms_{w}s"] = np.sqrt(df_out.groupby("node_id")[vib.name].rolling(w, min_periods=1).apply(lambda x: np.mean(x**2), raw=True).reset_index(drop=True))
            df_out[f"vib_max_{w}s"] = df_out.groupby("node_id")[vib.name].rolling(w, min_periods=1).max().reset_index(drop=True)
            df_out[f"vib_std_{w}s"] = df_out.groupby("node_id")[vib.name].rolling(w, min_periods=1).std().fillna(0.0).reset_index(drop=True)

        print(f"[FEATURE ENGINE] Engineered {len(df_out.columns)} total columns.")
        return df_out

FEATURE_NAMES = [
    "tilt_x_deg", "tilt_y_deg", "tilt_total_deg", "tilt_rate_degs",
    "displacement_mm", "disp_velocity_mms", "disp_accel_mms2",
    "strain_ue", "strain_rate_ues",
    "vibration_amp", "rockburst_hazard_index",
    # Multi-scale rolling features
    "disp_mean_3s", "disp_std_3s", "disp_max_3s",
    "disp_mean_10s", "disp_std_10s", "disp_max_10s",
    "disp_mean_30s", "disp_std_30s", "disp_max_30s",
    "strain_mean_3s", "strain_std_3s",
    "strain_mean_10s", "strain_std_10s",
    "strain_mean_30s", "strain_std_30s",
    "tilt_mean_3s", "tilt_std_3s",
    "tilt_mean_10s", "tilt_std_10s",
    "tilt_mean_30s", "tilt_std_30s",
    "vib_rms_3s", "vib_max_3s", "vib_std_3s",
    "vib_rms_10s", "vib_max_10s", "vib_std_10s",
    "vib_rms_30s", "vib_max_30s", "vib_std_30s"
]

if __name__ == "__main__":
    import os
    raw_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "processed", "mine_subsidence_dataset.csv")
    if os.path.exists(raw_path):
        df = pd.read_csv(raw_path)
        fe = AdvancedFeatureEngineer()
        featured = fe.extract_features(df)
        print("Feature columns sample:")
        print(featured[FEATURE_NAMES[:8]].head(3))
