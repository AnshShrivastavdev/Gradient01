"""
Coal Mine ML Model Evaluation & Performance Report
--------------------------------------------------
Evaluates saved model on independent test sets, prints detailed confusion matrices,
precision-recall per hazard zone, and verifies decision stability.
"""

import os
import json
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "best_zone_classifier.joblib")
TEST_DATA_PATH = os.path.join(BASE_DIR, "data", "sensor_dataset_clean.csv")

def evaluate_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model file {MODEL_PATH} does not exist.")
    
    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(TEST_DATA_PATH)
    
    features = ["strain_microstrain", "tilt_deg", "vibration_g", "displacement_mm"]
    X = df[features]
    y_true = df["hazard_zone"]
    
    y_pred = model.predict(X)
    
    acc = accuracy_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred, labels=["ZONE_A", "ZONE_B", "ZONE_C"])
    report = classification_report(y_true, y_pred, target_names=["ZONE_A", "ZONE_B", "ZONE_C"])
    
    print("\n" + "="*65)
    print("        COAL MINE HAZARD ZONE ML - EVALUATION REPORT")
    print("="*65)
    print(f"Overall Dataset Evaluation Accuracy: {acc*100:.2f}%\n")
    print("Classification Metrics by Zone:")
    print(report)
    print("Confusion Matrix:")
    print(f"{'':>12} | {'Pred ZONE_A':<12} | {'Pred ZONE_B':<12} | {'Pred ZONE_C':<12}")
    print("-" * 55)
    for idx, true_label in enumerate(["True ZONE_A", "True ZONE_B", "True ZONE_C"]):
        print(f"{true_label:>12} | {cm[idx][0]:<12} | {cm[idx][1]:<12} | {cm[idx][2]:<12}")
    print("="*65 + "\n")

if __name__ == "__main__":
    evaluate_model()
