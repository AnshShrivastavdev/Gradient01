"""
Coal Mine Sensor Zone Classification - Model Training Pipeline
--------------------------------------------------------------
Trains machine learning models to classify real-time coal mine geotechnical
sensor streams (Strain, Tilt, Vibration, Displacement) into hazard zones:
- ZONE_A: Stable / Nominal
- ZONE_B: Caution / Seismic Warning
- ZONE_C: Critical / Imminent Roof Fall Hazard

Saves model weights, metadata, and JSON decision rules in ml/models/.
"""

import os
import json
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "sensor_dataset_clean.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# Feature and Target Configuration
FEATURE_COLUMNS = [
    "strain_microstrain",
    "tilt_deg",
    "vibration_g",
    "displacement_mm"
]

TARGET_COLUMN = "hazard_zone" # ZONE_A, ZONE_B, ZONE_C

def train_and_evaluate():
    print(f"Loading geotechnical dataset from: {DATA_PATH}")
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}. Run generate_dataset.py first.")
        
    df = pd.read_csv(DATA_PATH)
    print(f"Total dataset size: {len(df)} samples across classes: {df[TARGET_COLUMN].value_counts().to_dict()}")
    
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    
    # Train / Test Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"Training set: {len(X_train)} samples | Test set: {len(X_test)} samples")
    
    # Feature Scaling
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Candidate Classifiers
    models = {
        "Random_Forest": RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42),
        "Gradient_Boosting": GradientBoostingClassifier(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42),
        "Decision_Tree": DecisionTreeClassifier(max_depth=6, random_state=42),
        "Logistic_Regression": LogisticRegression(max_iter=1000, random_state=42)
    }
    
    results = {}
    best_name = None
    best_f1 = -1
    best_model = None
    
    print("\n" + "="*70)
    print(f"{'Model':<25} | {'Train Acc':<10} | {'Test Acc':<10} | {'Macro F1':<10}")
    print("="*70)
    
    for name, model in models.items():
        if name == "Logistic_Regression":
            model.fit(X_train_scaled, y_train)
            train_preds = model.predict(X_train_scaled)
            test_preds = model.predict(X_test_scaled)
        else:
            model.fit(X_train, y_train)
            train_preds = model.predict(X_train)
            test_preds = model.predict(X_test)
            
        train_acc = accuracy_score(y_train, train_preds)
        test_acc = accuracy_score(y_test, test_preds)
        macro_f1 = f1_score(y_test, test_preds, average='macro')
        
        results[name] = {
            "train_acc": round(float(train_acc), 4),
            "test_acc": round(float(test_acc), 4),
            "macro_f1": round(float(macro_f1), 4),
            "model": model
        }
        
        print(f"{name:<25} | {train_acc*100:>8.2f}% | {test_acc*100:>8.2f}% | {macro_f1:>10.4f}")
        
        if macro_f1 > best_f1:
            best_f1 = macro_f1
            best_name = name
            best_model = model
            
    print("="*70)
    print(f"\n Best Performing Model: {best_name} (Test Accuracy: {results[best_name]['test_acc']*100:.2f}%, F1: {best_f1:.4f})")
    
    # Detailed Classification Report & Confusion Matrix for Best Model
    if best_name == "Logistic_Regression":
        final_test_preds = best_model.predict(X_test_scaled)
    else:
        final_test_preds = best_model.predict(X_test)
        
    print("\nDetailed Classification Report:")
    labels = ["ZONE_A", "ZONE_B", "ZONE_C"]
    print(classification_report(y_test, final_test_preds, target_names=labels))
    
    cm = confusion_matrix(y_test, final_test_preds, labels=labels)
    cm_dict = {
        "labels": labels,
        "matrix": cm.tolist()
    }
    
    # Feature Importances (if tree-based)
    importances = {}
    if hasattr(best_model, "feature_importances_"):
        for feat, imp in zip(FEATURE_COLUMNS, best_model.feature_importances_):
            importances[feat] = round(float(imp), 4)
            print(f"Feature Importance -> {feat:<20}: {imp*100:.2f}%")
            
    # Save Model Artifacts
    model_save_path = os.path.join(MODELS_DIR, "best_zone_classifier.joblib")
    joblib.dump(best_model, model_save_path)
    print(f"\n Saved trained model: {model_save_path}")
    
    scaler_save_path = os.path.join(MODELS_DIR, "scaler.joblib")
    joblib.dump(scaler, scaler_save_path)
    print(f" Saved feature scaler: {scaler_save_path}")
    
    # Save Model Metadata JSON
    metadata = {
        "model_type": best_name,
        "features": FEATURE_COLUMNS,
        "classes": labels,
        "test_accuracy": results[best_name]["test_acc"],
        "macro_f1": results[best_name]["macro_f1"],
        "confusion_matrix": cm_dict,
        "feature_importances": importances,
        "zone_thresholds_reference": {
            "ZONE_A": {"strain_max": 300, "tilt_max": 0.50, "vibration_max": 0.08, "disp_max": 2.50, "status": "NOMINAL"},
            "ZONE_B": {"strain_range": [300, 750], "tilt_range": [0.50, 3.00], "vibration_range": [0.08, 0.60], "disp_range": [2.50, 8.00], "status": "CAUTION"},
            "ZONE_C": {"strain_min": 750, "tilt_min": 3.00, "vibration_min": 0.60, "disp_min": 8.00, "status": "CRITICAL"}
        }
    }
    
    metadata_path = os.path.join(MODELS_DIR, "model_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f" Saved model metadata: {metadata_path}")
    
    # Save Decision Rules in JSON (for fast standalone / client-side / edge inference)
    rules_path = os.path.join(MODELS_DIR, "zone_decision_rules.json")
    with open(rules_path, "w") as f:
        json.dump({
            "name": "Geotechnical Risk Scoring Engine",
            "version": "1.0",
            "weights": {
                "strain": 0.35,
                "tilt": 0.25,
                "vibration": 0.20,
                "displacement": 0.20
            },
            "critical_limits": {
                "strain_yield_limit_microstrain": 850.0,
                "tilt_critical_deg": 3.0,
                "vibration_critical_g": 0.60,
                "displacement_critical_mm": 8.0
            },
            "zones": {
                "ZONE_A": {"label": "Nominal Baseline", "color": "#15803D", "score_max": 0.35},
                "ZONE_B": {"label": "Seismic Caution", "color": "#B45309", "score_max": 0.70},
                "ZONE_C": {"label": "Critical Evacuation", "color": "#B91C1C", "score_min": 0.70}
            }
        }, f, indent=2)
    print(f" Saved edge decision rules: {rules_path}")
    
    print("\n Training pipeline completed successfully!")

if __name__ == "__main__":
    train_and_evaluate()
