"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring
Module: dataset_generator.py (Multi-Zone 1Hz Synthetic Dataset Generator)
-------------------------------------------------------------------------
"""

import os
import random
import datetime
import numpy as np
import pandas as pd

np.random.seed(42)
random.seed(42)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
OUTPUT_PATH = os.path.join(PROCESSED_DIR, "mine_subsidence_dataset.csv")
os.makedirs(PROCESSED_DIR, exist_ok=True)

TOTAL_SECONDS = 7200 # 2 hours @ 1 Hz x 3 nodes = 21,600 samples
NODES = ["NODE_A1", "NODE_B1", "NODE_C1"]

def generate_multi_zone_dataset(num_seconds=TOTAL_SECONDS):
    print(f"Generating {num_seconds * len(NODES)} multi-zone time-series records...")
    start_time = datetime.datetime(2026, 3, 1, 8, 0, 0)
    data_rows = []

    for t in range(num_seconds):
        current_time = start_time + datetime.timedelta(seconds=t)
        time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        seismic_burst = (t % 450 >= 435)

        for node_id in NODES:
            if node_id == "NODE_A1":
                zone_id = "Zone A"
                risk_level = "Normal"
                tilt_x = np.clip(np.random.normal(0.01, 0.035), -0.10, 0.10)
                tilt_y = np.clip(np.random.normal(-0.01, 0.035), -0.10, 0.10)
                disp = np.clip(np.random.normal(0.55, 0.18), 0.05, 0.98)
                strain = np.clip(np.random.normal(98.0, 18.0), 50.0, 150.0)
                vib = np.clip(np.random.exponential(0.015), 0.002, 0.075)

            elif node_id == "NODE_B1":
                if t < 1500:
                    zone_id, risk_level = "Zone A", "Normal"
                    tilt_x = np.clip(np.random.normal(0.02, 0.035), -0.10, 0.10)
                    tilt_y = np.clip(np.random.normal(0.01, 0.035), -0.10, 0.10)
                    disp = np.clip(np.random.normal(0.65, 0.15), 0.05, 0.98)
                    strain = np.clip(np.random.normal(110.0, 15.0), 50.0, 150.0)
                    vib = np.clip(np.random.exponential(0.018), 0.002, 0.078)
                elif t < 5500:
                    zone_id, risk_level = "Zone B", "Warning"
                    drift_x = (t / num_seconds) * 0.4
                    tilt_x = np.clip(np.random.normal(1.10 + drift_x, 0.25), 0.50, 2.00)
                    tilt_y = np.clip(np.random.normal(0.85 + drift_x, 0.20), 0.50, 2.00)
                    disp = np.clip(np.random.normal(8.5, 1.8), 5.0, 15.0)
                    strain = np.clip(np.random.normal(250.0, 35.0), 180.0, 350.0)
                    vib = np.clip(np.random.normal(0.42 if seismic_burst else 0.18, 0.06), 0.08, 0.65)
                else:
                    zone_id, risk_level = "Zone C", "Critical"
                    tilt_x = np.clip(np.random.normal(4.20, 0.85), 2.50, 8.00)
                    tilt_y = np.clip(np.random.normal(3.80, 0.75), 2.50, 8.00)
                    disp = np.clip(np.random.normal(32.0, 5.5), 20.0, 60.0)
                    strain = np.clip(np.random.normal(580.0, 65.0), 400.0, 900.0)
                    vib = np.clip(np.random.normal(1.85, 0.40), 0.80, 4.50)

            else: # NODE_C1
                if t < 1000:
                    zone_id, risk_level = "Zone B", "Warning"
                    tilt_x = np.clip(np.random.normal(1.30, 0.25), 0.50, 2.00)
                    tilt_y = np.clip(np.random.normal(1.10, 0.20), 0.50, 2.00)
                    disp = np.clip(np.random.normal(9.8, 1.8), 5.0, 15.0)
                    strain = np.clip(np.random.normal(290.0, 30.0), 180.0, 350.0)
                    vib = np.clip(np.random.normal(0.28, 0.08), 0.10, 0.65)
                else:
                    zone_id, risk_level = "Zone C", "Critical"
                    collapse_factor = min(1.0, (t / num_seconds) * 1.5)
                    tilt_x = np.clip(np.random.normal(4.80 + collapse_factor * 1.8, 0.85), 2.50, 8.00)
                    tilt_y = np.clip(np.random.normal(4.20 + collapse_factor * 1.6, 0.75), 2.50, 8.00)
                    disp = np.clip(np.random.normal(38.0 + collapse_factor * 14.0, 6.5), 20.0, 60.0)
                    strain = np.clip(np.random.normal(680.0 + collapse_factor * 150.0, 75.0), 400.0, 900.0)
                    vib = np.clip(np.random.normal(2.10 + collapse_factor * 0.8, 0.45), 0.80, 4.50)

            row = {
                "timestamp": time_str,
                "zone_id": zone_id,
                "node_id": node_id,
                "tilt_x_deg": round(float(tilt_x), 4),
                "tilt_y_deg": round(float(tilt_y), 4),
                "displacement_mm": round(float(disp), 3),
                "strain_ue": round(float(strain), 2),
                "vibration_amp": round(float(vib), 4),
                "risk_level": risk_level
            }
            data_rows.append(row)

    df = pd.DataFrame(data_rows)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f" Dataset saved to: {OUTPUT_PATH} ({len(df)} samples)")
    return OUTPUT_PATH

if __name__ == "__main__":
    generate_multi_zone_dataset()
