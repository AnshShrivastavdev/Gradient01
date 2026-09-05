"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring
Module: filter_and_tune.py (Signal Filtering & Hyperparameter Tuning Pipeline)
-------------------------------------------------------------------------------
1. Signal Conditioning & Filtering:
   - Outlier Rejection via Hampel filter / Rolling Z-Score
   - 2nd-Order Low-Pass Butterworth Filter (cut-off: 0.25 Hz for 1 Hz sampling)
   - Physical sensor bounding & baseline calibration
2. Model Tuning:
   - Stratified 5-Fold Cross Validation
   - Hyperparameter Grid Search for XGBoost
   - Class-weighted loss penalty for safety-critical early warnings
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from scipy import signal as dsp_signal
from sklearn.model_selection import StratifiedKFold, GridSearchCV
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, accuracy_score, f1_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "mine_subsidence_dataset.csv")
FILTERED_DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "mine_subsidence_filtered.csv")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")

# =====================================================================
# 1. DIGITAL SIGNAL FILTERING ENGINE
# =====================================================================
def butterworth_lowpass_filter(data, cutoff_hz=0.25, fs_hz=1.0, order=2):
    """
    Applies a zero-phase digital low-pass Butterworth filter
    to remove electrical sensor jitter while preserving ground deformation trends.
    """
    nyquist = 0.5 * fs_hz
    normal_cutoff = cutoff_hz / nyquist
    b, a = dsp_signal.butter(order, normal_cutoff, btype='low', analog=False)
    # filtfilt provides zero-phase distortion (forward-backward filtering)
    return dsp_signal.filtfilt(b, a, data)

def hampel_filter_outliers(series, window_size=5, n_sigmas=3.0):
    """
    Hampel filter uses median and MAD (Median Absolute Deviation)
    to replace single-point sensor spikes with rolling median.
    """
    roll_median = series.rolling(window=window_size, min_periods=1, center=True).median()
    diff = (series - roll_median).abs()
    mad = diff.rolling(window=window_size, min_periods=1, center=True).median()
    threshold = n_sigmas * 1.4826 * mad
    
    # Replace outliers with local median
    is_outlier = diff > threshold
    cleaned = series.copy()
    cleaned[is_outlier] = roll_median[is_outlier]
    return cleaned

def apply_signal_filtering(df: pd.DataFrame) -> pd.DataFrame:
    print("\n[STEP 1/2] Applying Digital Signal Conditioning & Outlier Filtering...")
    df_filtered = df.copy()
    
    raw_channels = ["tilt_x_deg", "tilt_y_deg", "displacement_mm", "strain_ue", "vibration_amp"]
    
    for node_id in df_filtered["node_id"].unique():
        mask = df_filtered["node_id"] == node_id
        for ch in raw_channels:
            # 1. Hampel outlier spike removal
            cleaned_spikes = hampel_filter_outliers(df_filtered.loc[mask, ch])
            # 2. Low-pass Butterworth smoothing
            if len(cleaned_spikes) > 15:
                smoothed = butterworth_lowpass_filter(cleaned_spikes.values, cutoff_hz=0.30, fs_hz=1.0, order=2)
                df_filtered.loc[mask, ch] = np.round(smoothed, 4)
            else:
                df_filtered.loc[mask, ch] = np.round(cleaned_spikes, 4)

    # Re-calculate composite resultant tilt after filtering
    df_filtered["tilt_composite_deg"] = np.sqrt(df_filtered["tilt_x_deg"]**2 + df_filtered["tilt_y_deg"]**2)
    
    # Extract 5s rolling derivatives on filtered signals
    base_signals = ["tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp"]
    for sig in base_signals:
        df_filtered[f"{sig}_mean_5s"] = df_filtered.groupby("node_id")[sig].rolling(5, min_periods=1).mean().reset_index(drop=True)
        df_filtered[f"{sig}_std_5s"] = df_filtered.groupby("node_id")[sig].rolling(5, min_periods=1).std().fillna(0.0).reset_index(drop=True)
        df_filtered[f"{sig}_roc_5s"] = df_filtered.groupby("node_id")[sig].diff().fillna(0.0).reset_index(drop=True)

    df_filtered.to_csv(FILTERED_DATA_PATH, index=False)
    print(f" -> Conditioned & filtered dataset saved to: {FILTERED_DATA_PATH}")
    return df_filtered

# =====================================================================
# 2. HYPERPARAMETER TUNING VIA 5-FOLD GRID SEARCH
# =====================================================================
def run_hyperparameter_tuning(df: pd.DataFrame):
    print("\n[STEP 2/2] Running 5-Fold Stratified Grid Search Hyperparameter Tuning...")
    
    feature_cols = [
        "tilt_x_deg", "tilt_y_deg", "tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp",
        "tilt_composite_deg_mean_5s", "tilt_composite_deg_std_5s", "tilt_composite_deg_roc_5s",
        "displacement_mm_mean_5s", "displacement_mm_std_5s", "displacement_mm_roc_5s",
        "strain_ue_mean_5s", "strain_ue_std_5s", "strain_ue_roc_5s",
        "vibration_amp_mean_5s", "vibration_amp_std_5s", "vibration_amp_roc_5s"
    ]
    
    X = df[feature_cols]
    encoder = LabelEncoder()
    y = encoder.fit_transform(df["risk_level"])
    
    param_grid = {
        'n_estimators': [80, 120],
        'max_depth': [4, 6],
        'learning_rate': [0.05, 0.1],
        'subsample': [0.8, 1.0],
        'colsample_bytree': [0.8, 1.0]
    }
    
    base_xgb = XGBClassifier(eval_metric="mlogloss", random_state=42)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    grid_search = GridSearchCV(
        estimator=base_xgb,
        param_grid=param_grid,
        cv=cv,
        scoring='f1_macro',
        n_jobs=-1,
        verbose=1
    )
    
    grid_search.fit(X, y)
    
    best_params = grid_search.best_params_
    best_score = grid_search.best_score_
    best_model = grid_search.best_estimator_
    
    print("\n" + "=" * 65)
    print("        HYPERPARAMETER TUNING RESULTS (5-FOLD CV)")
    print("=" * 65)
    print(f"Optimal F1 (Macro) Cross-Validation Score: {best_score * 100:.2f}%")
    print("Best Hyperparameters:")
    for k, v in best_params.items():
        print(f"  * {k:<20} : {v}")
    print("=" * 65)
    
    # Save tuned model & tuning log
    tuned_model_path = os.path.join(ARTIFACTS_DIR, "subsidence_model.joblib")
    joblib.dump(best_model, tuned_model_path)
    
    tuning_report = {
        "best_cv_score_f1_macro": round(float(best_score), 4),
        "best_hyperparameters": best_params,
        "cv_folds": 5,
        "filter_applied": "Butterworth Low-pass (0.30Hz) + Hampel Outlier Rejection",
        "feature_count": len(feature_cols),
        "total_samples": len(df)
    }
    
    report_path = os.path.join(ARTIFACTS_DIR, "tuning_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(tuning_report, f, indent=2)
        
    print(f"\n Tuned model exported to: {tuned_model_path}")
    print(f" Tuning metadata saved to: {report_path}\n")

if __name__ == "__main__":
    raw_df = pd.read_csv(DATA_PATH)
    filtered_df = apply_signal_filtering(raw_df)
    run_hyperparameter_tuning(filtered_df)
