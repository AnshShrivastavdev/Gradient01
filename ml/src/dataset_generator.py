"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring
Module 2: 1Hz Multi-Node Time-Series Dataset Generator (dataset_generator.py)
-----------------------------------------------------------------------------
Generates realistic multi-node geotechnical time-series sensor telemetry
sampled at 1 Hz across three ESP32 + LoRa nodes:
- NODE_A1 (Zone A Sector / Baseline Entry Gate)
- NODE_B1 (Zone B Sector / Longwall Panel)
- NODE_C1 (Zone C Sector / Extraction Void)

Hardware Monitored:
1. MPU6500 Accelerometer: tilt_x_deg, tilt_y_deg
2. VL53L4CD ToF Laser: displacement_mm
3. BX120-3AA + HX711: strain_ue (microstrain)
4. Piezo + LM358: vibration_amp (peak amplitude)

Output Classes:
- Normal (Zone A): tilt +-0.1 deg, disp < 1.0mm, strain 50-150 ue
- Warning (Zone B): tilt 0.5 - 2.0 deg, disp drop 5-15mm, strain 180-350 ue, transient vibration bursts
- Critical (Zone C): tilt 2.5 - 8.0 deg, disp drop 20-60mm, strain 400-900 ue, sustained rupture shocks

Required Schema:
`timestamp, zone_id, node_id, tilt_x_deg, tilt_y_deg, displacement_mm, strain_ue, vibration_amp, risk_level`
"""

import os
import random
import datetime
import numpy as np
import pandas as pd

np.random.seed(42)
random.seed(42)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "mine_subsidence_dataset.csv")
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

TOTAL_SECONDS = 7200  # 2 hours of continuous 1 Hz multi-node streaming (7200 timesteps x 3 nodes = 21,600 samples)
NODES = [
    {"node_id": "NODE_A1", "default_zone": "Zone A"},
    {"node_id": "NODE_B1", "default_zone": "Zone B"},
    {"node_id": "NODE_C1", "default_zone": "Zone C"},
]

def generate_timeseries_dataset(num_seconds=TOTAL_SECONDS):
    print(f"Generating 1 Hz multi-node geotechnical time-series dataset ({num_seconds} seconds across 3 nodes)...")
    
    start_time = datetime.datetime(2026, 3, 1, 8, 0, 0)
    data_rows = []
    
    # State tracking per node for realistic continuous drift, noise, and cumulative deformation
    node_states = {
        "NODE_A1": {"tilt_x": 0.01, "tilt_y": -0.01, "disp": 0.45, "strain": 85.0, "drift_rate": 0.00002},
        "NODE_B1": {"tilt_x": 0.85, "tilt_y": 0.65, "disp": 7.20, "strain": 240.0, "drift_rate": 0.0004},
        "NODE_C1": {"tilt_x": 3.80, "tilt_y": 3.20, "disp": 28.50, "strain": 580.0, "drift_rate": 0.0020},
    }
    
    # Create phases so nodes can experience realistic operational transitions and seismic events
    for t in range(num_seconds):
        current_time = start_time + datetime.timedelta(seconds=t)
        time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Periodic micro-seismic shock trigger (every ~300-600s)
        seismic_burst = (t % 450 >= 435) # 15-second vibration shock window
        
        for node in NODES:
            node_id = node["node_id"]
            state = node_states[node_id]
            
            # Allow scenario transition:
            # During first 30%: nominal/normal baseline
            # During middle 35%: developing warning / subsidence progression
            # During last 35%: critical subsidence collapse
            # Or steady allocation based on sector position
            
            # Dynamic zone assignment per time segment and node location
            if node_id == "NODE_A1":
                # Primarily Zone A with occasional small tremors
                if seismic_burst and t > 5000:
                    zone_id = "Zone B"
                    risk_level = "Warning"
                else:
                    zone_id = "Zone A"
                    risk_level = "Normal"
            elif node_id == "NODE_B1":
                if t < 1500:
                    zone_id = "Zone A"
                    risk_level = "Normal"
                elif t < 5500:
                    zone_id = "Zone B"
                    risk_level = "Warning"
                else:
                    zone_id = "Zone C"
                    risk_level = "Critical"
            else: # NODE_C1 (High extraction void)
                if t < 1000:
                    zone_id = "Zone B"
                    risk_level = "Warning"
                else:
                    zone_id = "Zone C"
                    risk_level = "Critical"
                    
            # ---------------------------------------------------------
            # Physics-based Telemetry Generation with Noise & Drift
            # ---------------------------------------------------------
            if risk_level == "Normal":
                # Zone A: Normal / Stable
                # tilt +-0.1 deg, disp < 1.0mm, strain 50-150 ue, vibration < 0.08
                noise_tilt = np.random.normal(0, 0.02)
                tilt_x = np.clip(np.random.normal(0.01, 0.035) + noise_tilt, -0.10, 0.10)
                tilt_y = np.clip(np.random.normal(-0.01, 0.035) + noise_tilt, -0.10, 0.10)
                
                disp = np.clip(np.random.normal(0.55, 0.18), 0.05, 0.98)
                strain = np.clip(np.random.normal(98.0, 18.0), 50.0, 150.0)
                
                # Vibration baseline
                vib = np.clip(np.random.exponential(0.015), 0.002, 0.075)
                
                # Rare spike injection (sensor glint / electric noise)
                if np.random.random() < 0.003:
                    vib += 0.025
                    
            elif risk_level == "Warning":
                # Zone B: Warning / Seismic Caution
                # gradual tilt drift 0.5-2.0 deg, disp drop 5-15mm, strain 180-350 ue, transient vibration bursts
                drift_x = (t / num_seconds) * 0.4
                tilt_x = np.clip(np.random.normal(1.10 + drift_x, 0.28), 0.50, 2.00)
                tilt_y = np.clip(np.random.normal(0.85 + drift_x, 0.22), 0.50, 2.00)
                
                disp_drift = (t / num_seconds) * 3.5
                disp = np.clip(np.random.normal(8.5 + disp_drift, 1.8), 5.0, 15.0)
                
                strain_drift = (t / num_seconds) * 45.0
                strain = np.clip(np.random.normal(250.0 + strain_drift, 35.0), 180.0, 350.0)
                
                # Vibration with intermittent bursts
                if seismic_burst:
                    vib = np.clip(np.random.normal(0.42, 0.08), 0.25, 0.65)
                else:
                    vib = np.clip(np.random.normal(0.18, 0.05), 0.08, 0.38)
                    
            else: # Critical
                # Zone C: Critical / Subsidence Collapse
                # tilt 2.5-8.0 deg, disp drop 20-60mm, strain 400-900 ue, sustained rupture shocks
                collapse_factor = min(1.0, (t / num_seconds) * 1.5)
                tilt_x = np.clip(np.random.normal(4.20 + collapse_factor * 2.2, 0.85), 2.50, 8.00)
                tilt_y = np.clip(np.random.normal(3.80 + collapse_factor * 1.9, 0.75), 2.50, 8.00)
                
                disp = np.clip(np.random.normal(34.0 + collapse_factor * 16.0, 6.5), 20.0, 60.0)
                strain = np.clip(np.random.normal(610.0 + collapse_factor * 180.0, 75.0), 400.0, 900.0)
                
                # Sustained rupture shocks
                vib = np.clip(np.random.normal(1.95 + collapse_factor * 0.8, 0.45), 0.80, 4.50)
                
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
    print(f" Saved 1 Hz time-series dataset to: {OUTPUT_PATH}")
    print(f" Total Records: {len(df)} | Class Breakdown:\n{df['risk_level'].value_counts()}")
    print("\nSample Rows:")
    print(df.head(6))
    return OUTPUT_PATH

if __name__ == "__main__":
    generate_timeseries_dataset()
