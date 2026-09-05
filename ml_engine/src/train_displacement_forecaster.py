"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring System
Module: train_displacement_forecaster.py (Multi-Step Subsidence Forecasting Engine)
-----------------------------------------------------------------------------------
Builds, trains, and exports a deep sequence model (LSTM) for multi-step ground
displacement forecasting (1 to 6 hours ahead) and Time-to-Failure (TTF) prediction:

Architecture:
- Input Shape: (Batch, Lookback=60, Features=1)
- Deep Recurrent Backbone: 2-Layer LSTM (hidden_dim=64, batch_first=True)
- Linear Head: Linear(64, Output_Horizon=6)
- Target: Future displacement increments / absolute trajectories
- Loss: Huber Loss (Smooth L1) for outlier robustness

Exports:
1. PyTorch weights: `ml_engine/artifacts/displacement_forecaster.pth`
2. ONNX graph: `ml_engine/artifacts/displacement_forecaster.onnx`
3. Scaler & metadata: `ml_engine/artifacts/forecaster_scaler.joblib`, `forecaster_metadata.json`
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import json
import math
import numpy as np
import pandas as pd
import joblib

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

MODEL_PTH_PATH = os.path.join(ARTIFACTS_DIR, "displacement_forecaster.pth")
MODEL_ONNX_PATH = os.path.join(ARTIFACTS_DIR, "displacement_forecaster.onnx")
SCALER_PATH = os.path.join(ARTIFACTS_DIR, "forecaster_scaler.joblib")
META_PATH = os.path.join(ARTIFACTS_DIR, "forecaster_metadata.json")

LOOKBACK_STEPS = 60 # Past 60 observations
FORECAST_STEPS = 6  # Next 1 to 6 hours ahead

# =====================================================================
# 1. GEOMECHANICAL SUBSIDENCE TIME-SERIES GENERATOR
# =====================================================================
def generate_subsidence_trajectories(num_curves=250, length_steps=300):
    """
    Generates realistic geomechanical displacement trajectories based on
    Voight's rock failure curve: Primary (Creep), Secondary (Linear steady),
    and Tertiary (Accelerating Runaway to Collapse).
    """
    print(f"Generating {num_curves} synthetic geomechanical subsidence profiles...")
    trajectories = []
    
    for i in range(num_curves):
        t = np.linspace(0, 100, length_steps)
        curve_type = np.random.choice(["steady", "progressive", "critical_collapse"], p=[0.30, 0.40, 0.30])
        
        if curve_type == "steady":
            d = 0.5 + 0.015 * t + np.random.normal(0, 0.05, length_steps)
        elif curve_type == "progressive":
            d = 1.0 + 0.15 * t + 0.001 * (t**2) + np.random.normal(0, 0.12, length_steps)
        else:
            t_inflect = np.random.uniform(45, 70)
            steepness = np.random.uniform(0.14, 0.24)
            max_disp = np.random.uniform(45, 75)
            d = max_disp / (1 + np.exp(-steepness * (t - t_inflect))) + np.random.normal(0, 0.20, length_steps)
            
        d = np.clip(d, 0.0, 100.0)
        trajectories.append(d)
        
    return trajectories

def create_sliding_windows(trajectories, lookback=LOOKBACK_STEPS, horizon=FORECAST_STEPS):
    """Slices sequential trajectories into relative (X, y) sliding window pairs."""
    X_list, y_list = [], []
    for traj in trajectories:
        for i in range(len(traj) - lookback - horizon):
            window = traj[i : i + lookback]
            future = traj[i + lookback : i + lookback + horizon]
            # Predict relative forward cumulative increments from last observed step:
            # y_relative = future - window[-1] >= 0
            y_diff = future - window[-1]
            X_list.append(window)
            y_list.append(y_diff)
            
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    return X, y

# =====================================================================
# 2. PYTORCH LSTM ARCHITECTURE
# =====================================================================
def get_pytorch_model():
    import torch
    import torch.nn as nn

    class SubsidenceLSTMForecaster(nn.Module):
        def __init__(self, input_dim=1, hidden_dim=64, num_layers=2, output_dim=FORECAST_STEPS):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.num_layers = num_layers
            self.lstm = nn.LSTM(
                input_size=input_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=0.1 if num_layers > 1 else 0.0
            )
            self.fc = nn.Linear(hidden_dim, output_dim)
            self.relu = nn.ReLU() # Physical constraint: displacement increments are non-negative

        def forward(self, x):
            # x shape: (batch, seq_len, 1)
            lstm_out, _ = self.lstm(x)
            last_step = lstm_out[:, -1, :]
            out = self.relu(self.fc(last_step))
            return out

    return SubsidenceLSTMForecaster

# =====================================================================
# 3. TRAINING & ONNX EXPORT PIPELINE
# =====================================================================
def train_and_export():
    import torch
    import torch.nn as nn
    from torch.utils.data import TensorDataset, DataLoader
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.model_selection import train_test_split

    print("=" * 70)
    print(" Team Gradient SIH // Training Deep Subsidence LSTM Forecaster")
    print("=" * 70)

    trajectories = generate_subsidence_trajectories(num_curves=220, length_steps=300)
    X_raw, y_diff_raw = create_sliding_windows(trajectories)
    print(f"Total windowed training pairs: {len(X_raw):,} sequences")

    scaler = MinMaxScaler(feature_range=(0.0, 1.0))
    scaler.fit(X_raw.reshape(-1, 1))

    X_scaled = scaler.transform(X_raw.reshape(-1, 1)).reshape(X_raw.shape)
    # Target is forward increment in mm
    y_target = y_diff_raw

    X_scaled = np.expand_dims(X_scaled, axis=-1)

    X_train, X_val, y_train, y_val = train_test_split(X_scaled, y_target, test_size=0.15, random_state=42)

    train_dataset = TensorDataset(torch.tensor(X_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.float32))
    val_dataset = TensorDataset(torch.tensor(X_val, dtype=torch.float32), torch.tensor(y_val, dtype=torch.float32))

    train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=256, shuffle=False)

    ModelClass = get_pytorch_model()
    model = ModelClass(input_dim=1, hidden_dim=64, num_layers=2, output_dim=FORECAST_STEPS)

    criterion = nn.HuberLoss(delta=1.0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.005, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=2)

    epochs = 8
    print(f"\nTraining SubsidenceLSTMForecaster for {epochs} epochs...")
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for bx, by in train_loader:
            optimizer.zero_grad()
            preds = model(bx)
            loss = criterion(preds, by)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(bx)
        train_loss /= len(train_dataset)

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for bx, by in val_loader:
                preds = model(bx)
                loss = criterion(preds, by)
                val_loss += loss.item() * len(bx)
        val_loss /= len(val_dataset)
        scheduler.step(val_loss)

        print(f"Epoch {epoch:02d}/{epochs:02d} | Train Huber Loss: {train_loss:.5f} | Val Huber Loss: {val_loss:.5f}")

    # Export PyTorch weights
    torch.save(model.state_dict(), MODEL_PTH_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"\n Saved PyTorch model weights: {MODEL_PTH_PATH}")
    print(f" Saved MinMaxScaler artifact: {SCALER_PATH}")

    # Export to ONNX
    model.eval()
    dummy_input = torch.randn(1, LOOKBACK_STEPS, 1, dtype=torch.float32)
    try:
        torch.onnx.export(
            model,
            dummy_input,
            MODEL_ONNX_PATH,
            export_params=True,
            opset_version=18,
            do_constant_folding=True,
            input_names=['displacement_history_60'],
            output_names=['forecast_increments_6'],
            dynamic_axes={'displacement_history_60': {0: 'batch_size'}, 'forecast_increments_6': {0: 'batch_size'}}
        )
        print(f" Successfully exported ONNX model: {MODEL_ONNX_PATH}")
        onnx_exported = True
    except Exception as ex:
        print(f"[!] ONNX export error ({ex})")
        onnx_exported = False

    meta = {
        "architecture": "SubsidenceLSTMForecaster",
        "input_shape": [LOOKBACK_STEPS, 1],
        "output_horizon_hours": FORECAST_STEPS,
        "prediction_mode": "relative_cumulative_increments",
        "val_huber_loss": round(float(val_loss), 5),
        "onnx_exported": onnx_exported,
        "critical_threshold_default_mm": 35.0
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    print(f" Saved model metadata: {META_PATH}")
    print(" Displacement Forecasting Engine Training Complete!\n")

if __name__ == "__main__":
    train_and_export()
