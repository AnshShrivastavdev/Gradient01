"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring
Module: train.py (XGBoost & Random Forest Classifier Training)
--------------------------------------------------------------
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

from feature_engineering import extract_rolling_features, FEATURE_COLUMNS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "mine_subsidence_dataset.csv")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

MODEL_PATH = os.path.join(ARTIFACTS_DIR, "subsidence_model.joblib")
ENCODER_PATH = os.path.join(ARTIFACTS_DIR, "label_encoder.joblib")
CONFIG_PATH = os.path.join(ARTIFACTS_DIR, "feature_config.json")

def train_models():
    print("Loading processed dataset...")
    df = pd.read_csv(DATA_PATH)
    featured_df = extract_rolling_features(df, window_size=5)

    X = featured_df[FEATURE_COLUMNS]
    y_raw = featured_df["risk_level"]

    encoder = LabelEncoder()
    y = encoder.fit_transform(y_raw)
    classes = list(encoder.classes_)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)

    model = XGBClassifier(
        n_estimators=120,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        eval_metric="mlogloss"
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    f1 = f1_score(y_test, preds, average="macro")

    print(f"XGBoost Test Accuracy: {acc*100:.2f}% | Macro F1: {f1:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, preds, target_names=classes))

    joblib.dump(model, MODEL_PATH)
    joblib.dump(encoder, ENCODER_PATH)

    config = {
        "model_type": "XGBoost",
        "classes": classes,
        "features": FEATURE_COLUMNS,
        "window_size": 5,
        "test_accuracy": round(float(acc), 4),
        "macro_f1": round(float(f1), 4)
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print(f" Model artifacts saved to: {ARTIFACTS_DIR}")
    return MODEL_PATH

if __name__ == "__main__":
    train_models()
