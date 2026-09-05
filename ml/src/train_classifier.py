"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring
Module 3: Feature Engineering & Multi-Class ML Model Training (train_classifier.py)
-----------------------------------------------------------------------------------
Builds 5-second temporal rolling window features:
- Rolling Mean (mean_5s)
- Rolling Standard Deviation (std_5s)
- Rate-of-Change (roc_5s: Delta/Delta t)
for Tilt, Displacement, Micro-Strain, and Vibration across multi-node streams.

Trains and evaluates:
1. XGBoost Classifier (Extreme Gradient Boosted Decision Trees)
2. Random Forest Classifier (Bagged Ensemble)

Exports trained production model to `ml/models/subsidence_model.joblib`.
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "mine_subsidence_dataset.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

MODEL_EXPORT_PATH = os.path.join(MODELS_DIR, "subsidence_model.joblib")
ENCODER_EXPORT_PATH = os.path.join(MODELS_DIR, "label_encoder.joblib")
FEATURE_CONFIG_PATH = os.path.join(MODELS_DIR, "feature_config.json")

def engineer_rolling_features(df: pd.DataFrame, window_size: int = 5) -> pd.DataFrame:
    """
    Computes 5-second temporal rolling mean, rolling std, and rate of change (delta/delta_t)
    grouped per physical ESP32 node stream.
    """
    print(f"Engineering {window_size}-second rolling window features per node...")
    
    # Calculate resultant composite tilt: sqrt(tilt_x^2 + tilt_y^2)
    df["tilt_composite_deg"] = np.sqrt(df["tilt_x_deg"]**2 + df["tilt_y_deg"]**2)
    
    base_signals = ["tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp"]
    
    df_sorted = df.sort_values(by=["node_id", "timestamp"]).copy()
    
    feature_dfs = [df_sorted]
    
    for signal in base_signals:
        # Rolling Mean
        roll_mean = df_sorted.groupby("node_id")[signal].rolling(window=window_size, min_periods=1).mean().reset_index(level=0, drop=True)
        # Rolling Std
        roll_std = df_sorted.groupby("node_id")[signal].rolling(window=window_size, min_periods=1).std().fillna(0.0).reset_index(level=0, drop=True)
        # Rate of Change (Delta / Delta t) over window
        rate_of_change = df_sorted.groupby("node_id")[signal].diff().fillna(0.0).reset_index(level=0, drop=True)
        
        feature_dfs.append(pd.Series(roll_mean, name=f"{signal}_mean_{window_size}s"))
        feature_dfs.append(pd.Series(roll_std, name=f"{signal}_std_{window_size}s"))
        feature_dfs.append(pd.Series(rate_of_change, name=f"{signal}_roc_{window_size}s"))
        
    engineered_df = pd.concat(feature_dfs, axis=1)
    return engineered_df

def train_subsidence_classifier():
    print("=" * 75)
    print(" Team Gradient SIH // Training Geotechnical Subsidence ML Classifier")
    print("=" * 75)
    
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Dataset missing at {DATA_PATH}. Run dataset_generator.py first.")
        
    raw_df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(raw_df)} time-series samples.")
    
    # Feature Engineering
    featured_df = engineer_rolling_features(raw_df, window_size=5)
    
    # Define feature set
    feature_cols = [
        # Instantaneous readings
        "tilt_x_deg", "tilt_y_deg", "tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp",
        # Rolling statistics (5s window)
        "tilt_composite_deg_mean_5s", "tilt_composite_deg_std_5s", "tilt_composite_deg_roc_5s",
        "displacement_mm_mean_5s", "displacement_mm_std_5s", "displacement_mm_roc_5s",
        "strain_ue_mean_5s", "strain_ue_std_5s", "strain_ue_roc_5s",
        "vibration_amp_mean_5s", "vibration_amp_std_5s", "vibration_amp_roc_5s"
    ]
    
    X = featured_df[feature_cols]
    y_raw = featured_df["risk_level"] # Normal, Warning, Critical
    
    # Encode target labels
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(y_raw)
    class_names = list(label_encoder.classes_)
    print(f"Classes: {class_names} -> Mappings: {dict(zip(class_names, label_encoder.transform(class_names)))}")
    
    # Stratified Train-Test Split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"Training set: {len(X_train)} samples | Test set: {len(X_test)} samples")
    
    # -------------------------------------------------------------
    # Model Benchmarking: XGBoost vs Random Forest
    # -------------------------------------------------------------
    models = {
        "XGBoost_Classifier": XGBClassifier(
            n_estimators=120,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            eval_metric="mlogloss"
        ),
        "Random_Forest": RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            random_state=42
        )
    }
    
    best_model_name = None
    best_model = None
    best_f1 = -1
    
    print("\n" + "-" * 70)
    print(f"{'Algorithm':<25} | {'Train Acc':<10} | {'Test Acc':<10} | {'Macro F1':<10}")
    print("-" * 70)
    
    for name, model in models.items():
        model.fit(X_train, y_train)
        train_preds = model.predict(X_train)
        test_preds = model.predict(X_test)
        
        train_acc = accuracy_score(y_train, train_preds)
        test_acc = accuracy_score(y_test, test_preds)
        macro_f1 = f1_score(y_test, test_preds, average="macro")
        
        print(f"{name:<25} | {train_acc*100:>8.2f}% | {test_acc*100:>8.2f}% | {macro_f1:>10.4f}")
        
        if macro_f1 > best_f1:
            best_f1 = macro_f1
            best_model_name = name
            best_model = model
            
    print("-" * 70)
    print(f"\n Selected Production Model: {best_model_name} (F1 Score: {best_f1:.4f})")
    
    # Detailed Evaluation Report
    final_preds = best_model.predict(X_test)
    print("\n" + "=" * 70)
    print(" Detailed Classification Metrics (Independent Test Set):")
    print("=" * 70)
    print(classification_report(y_test, final_preds, target_names=class_names))
    
    cm = confusion_matrix(y_test, final_preds)
    print("Confusion Matrix:")
    print(f"{'':>14} | " + " | ".join([f"Pred {c:<8}" for c in class_names]))
    print("-" * 55)
    for i, true_cls in enumerate(class_names):
        row_str = " | ".join([f"{cm[i][j]:<13}" for j in range(len(class_names))])
        print(f"True {true_cls:>9} | {row_str}")
    print("=" * 70)
    
    # Feature Importances
    importances = {}
    if hasattr(best_model, "feature_importances_"):
        print("\nTop Geotechnical Feature Importances:")
        sorted_idx = np.argsort(best_model.feature_importances_)[::-1]
        for idx in sorted_idx[:10]:
            feat = feature_cols[idx]
            imp = float(best_model.feature_importances_[idx])
            importances[feat] = round(imp, 4)
            print(f"  * {feat:<30} : {imp*100:>6.2f}%")
            
    # Export Model & Artifacts
    joblib.dump(best_model, MODEL_EXPORT_PATH)
    joblib.dump(label_encoder, ENCODER_EXPORT_PATH)
    
    config = {
        "model_name": best_model_name,
        "classes": class_names,
        "feature_columns": feature_cols,
        "base_signals": ["tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp"],
        "window_size": 5,
        "test_accuracy": round(float(accuracy_score(y_test, final_preds)), 4),
        "macro_f1": round(float(best_f1), 4),
        "top_features": importances,
        "hardware_mapping": {
            "MPU6050": ["tilt_x_deg", "tilt_y_deg"],
            "VL53L4CD": ["displacement_mm"],
            "HX711_BX120": ["strain_ue"],
            "PIEZO_LM358": ["vibration_amp"]
        }
    }
    
    with open(FEATURE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        
    print(f"\n Exported Model Artifacts:")
    print(f"  -> Model: {MODEL_EXPORT_PATH}")
    print(f"  -> Encoder: {ENCODER_EXPORT_PATH}")
    print(f"  -> Config: {FEATURE_CONFIG_PATH}")
    print(" Training Pipeline Execution Complete!\n")

if __name__ == "__main__":
    train_subsidence_classifier()
