"""
Team Gradient - SIH Underground Coal Mine Subsidence Early Warning System
Module 3: Time-Aware Cross-Validation & Hyperparameter Tuning (model_tuning.py)
------------------------------------------------------------------------------
Features:
1. Chronological TimeSeriesSplit (5 splits) across multi-node telemetry.
2. Safety Imbalance Handling - Safety class weights giving priority to Critical events.
3. Optuna Bayesian Optimization on XGBoost:
   - max_depth [3..8], learning_rate [0.01..0.15], subsample [0.7..1.0], colsample_bytree [0.6..1.0], gamma [0..2]
4. Evaluation:
   - Precision-Recall metrics, Macro F1, and normalized confusion matrix with Critical False Negative Rate (FNR).
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
import optuna
from sklearn.model_selection import TimeSeriesSplit, train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score

from signal_filtering import SensorSignalFilter
from advanced_feature_engineering import AdvancedFeatureEngineer, FEATURE_NAMES

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "mine_subsidence_dataset.csv")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

optuna.logging.set_verbosity(optuna.logging.WARNING)

def prepare_data():
    df_raw = pd.read_csv(DATA_PATH)
    # 1. Apply signal filtering
    sig_filter = SensorSignalFilter()
    df_filtered = sig_filter.process_telemetry_dataframe(df_raw)
    
    # 2. Extract multi-scale advanced features (per node)
    fe = AdvancedFeatureEngineer()
    df_features = fe.extract_features(df_filtered)
    
    # Sort strictly chronologically by timestamp so all 3 nodes appear concurrently
    df_features = df_features.sort_values(by=["timestamp", "node_id"]).reset_index(drop=True)
    
    X = df_features[FEATURE_NAMES]
    encoder = LabelEncoder()
    y = encoder.fit_transform(df_features["risk_level"])
    return X, y, encoder

def optimize_pipeline(n_trials: int = 10):
    print("=" * 75)
    print(" Team Gradient SIH // TimeSeriesSplit & Optuna Hyperparameter Optimization")
    print("=" * 75)
    
    X, y, encoder = prepare_data()
    classes = list(encoder.classes_)
    critical_class_idx = list(encoder.classes_).index("Critical")
    class_indices = list(range(len(classes)))
    
    print(f"Dataset: {len(X)} samples | Features: {X.shape[1]} | Target Classes: {classes}")
    
    # 5-Split TimeSeriesSplit across chronological flow
    tscv = TimeSeriesSplit(n_splits=5)

    # -------------------------------------------------------------
    # 1. Optuna Study for XGBoost
    # -------------------------------------------------------------
    print("\n[OPTUNA] Optimizing XGBoost with Temporal Cross-Validation...")
    
    def objective_xgb(trial):
        params = {
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "subsample": trial.suggest_float("subsample", 0.7, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "gamma": trial.suggest_float("gamma", 0.0, 2.0),
            "n_estimators": trial.suggest_int("n_estimators", 60, 120),
            "eval_metric": "mlogloss",
            "random_state": 42
        }

        f1_scores = []
        for train_idx, val_idx in tscv.split(X):
            y_tr, y_val = y[train_idx], y[val_idx]

            # Ensure multi-class stability across temporal window
            if len(np.unique(y_tr)) < len(classes) or len(np.unique(y_val)) < 2:
                continue

            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]

            weights_tr = compute_sample_weight("balanced", y_tr)
            weights_tr[y_tr == critical_class_idx] *= 2.0

            clf = XGBClassifier(**params)
            clf.fit(X_tr, y_tr, sample_weight=weights_tr)
            preds = clf.predict(X_val)
            f1_scores.append(f1_score(y_val, preds, average="macro", zero_division=0))

        return np.mean(f1_scores) if f1_scores else 0.0

    study_xgb = optuna.create_study(direction="maximize")
    study_xgb.optimize(objective_xgb, n_trials=n_trials)
    
    best_xgb_params = study_xgb.best_params
    best_xgb_score = study_xgb.best_value
    print(f" Best XGBoost Macro F1 (TimeSeries CV): {best_xgb_score * 100:.2f}%")
    print(f" Best Hyperparameters: {best_xgb_params}")

    # -------------------------------------------------------------
    # 2. Final Evaluation on Stratified Holdout
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print(" Evaluating Final Tuned Model with Safety Imbalance Weights...")
    print("=" * 70)
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    
    weights = compute_sample_weight("balanced", y_train)
    weights[y_train == critical_class_idx] *= 2.0
    
    final_model = XGBClassifier(**best_xgb_params, eval_metric="mlogloss", random_state=42)
    final_model.fit(X_train, y_train, sample_weight=weights)
    
    test_preds = final_model.predict(X_test)
    
    print("\nDetailed Classification Metrics:")
    print(classification_report(y_test, test_preds, labels=class_indices, target_names=classes, zero_division=0))
    
    cm = confusion_matrix(y_test, test_preds, labels=class_indices)
    crit_total = np.sum(cm[critical_class_idx])
    crit_fn = crit_total - cm[critical_class_idx, critical_class_idx]
    crit_fnr = (crit_fn / crit_total) * 100.0 if crit_total > 0 else 0.0
    
    print("Confusion Matrix:")
    print(f"{'':>14} | " + " | ".join([f"Pred {c:<8}" for c in classes]))
    print("-" * 55)
    for i, true_cls in enumerate(classes):
        row_str = " | ".join([f"{cm[i][j]:<13}" for j in range(len(classes))])
        print(f"True {true_cls:>9} | {row_str}")
    print("=" * 70)
    print(f" CRITICAL COLLAPSE FALSE NEGATIVE RATE (FNR): {crit_fnr:.2f}% (Safety Goal: 0.00% Zero-Miss)")
    print("=" * 70)

    # Save artifacts
    model_export_path = os.path.join(ARTIFACTS_DIR, "subsidence_model_optimized.joblib")
    encoder_export_path = os.path.join(ARTIFACTS_DIR, "label_encoder.joblib")
    joblib.dump(final_model, model_export_path)
    joblib.dump(encoder, encoder_export_path)
    
    meta = {
        "best_score": best_xgb_score,
        "best_params": best_xgb_params,
        "critical_fnr": crit_fnr,
        "features": FEATURE_NAMES,
        "classes": classes
    }
    with open(os.path.join(ARTIFACTS_DIR, "optimization_report.json"), "w") as f:
        json.dump(meta, f, indent=2)
        
    print(f"\n Exported Tuned Model Artifact: {model_export_path}")
    return model_export_path

if __name__ == "__main__":
    optimize_pipeline(n_trials=10)
