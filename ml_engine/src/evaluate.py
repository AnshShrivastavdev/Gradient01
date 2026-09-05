"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring
Module: evaluate.py (Validation Metrics & Confusion Matrix)
----------------------------------------------------------
"""

import os
import joblib
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

from feature_engineering import extract_rolling_features, FEATURE_COLUMNS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "mine_subsidence_dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "artifacts", "subsidence_model.joblib")
ENCODER_PATH = os.path.join(BASE_DIR, "artifacts", "label_encoder.joblib")

def evaluate():
    model = joblib.load(MODEL_PATH)
    encoder = joblib.load(ENCODER_PATH)

    df = pd.read_csv(DATA_PATH)
    featured_df = extract_rolling_features(df, window_size=5)

    X = featured_df[FEATURE_COLUMNS]
    y_true = encoder.transform(featured_df["risk_level"])

    preds = model.predict(X)
    acc = accuracy_score(y_true, preds)
    classes = list(encoder.classes_)

    print("=" * 60)
    print("      ML ENGINE - FULL DATASET VALIDATION REPORT")
    print("=" * 60)
    print(f"Overall Accuracy: {acc*100:.2f}%\n")
    print(classification_report(y_true, preds, target_names=classes))
    print("Confusion Matrix:")
    print(confusion_matrix(y_true, preds))
    print("=" * 60)

if __name__ == "__main__":
    evaluate()
