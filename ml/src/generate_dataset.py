"""
Coal Mine Geotechnical Sensor Dataset Generator
----------------------------------------------
Generates physically realistic sensor telemetry datasets for underground coal mine monitoring.

Monitored Geotechnical Parameters:
1. Strain Gauge (microstrain, με): Roof bolt tension & rock mass tensile stress.
2. Tilt Inclinometers (degrees, °): 3-node spatial angular deviation (Node 1, Node 2, Node 3).
3. Vibration / Accelerometer (g / m/s²): Peak transient acceleration & RMS seismic vibration.
4. Displacement / ToF Laser (mm): Vertical roof sag, bed separation, and central platform lowering.

Target Hazard Zones:
- ZONE_A: Nominal / Normal Stability (Score 0.00 - 0.35)
- ZONE_B: Caution / Micro-seismic Warning (Score 0.35 - 0.70)
- ZONE_C: Critical / Imminent Roof Fall & Evacuation (Score 0.70 - 1.00)
"""

import os
import random
import datetime
import numpy as np
import pandas as pd
import json

# Set deterministic seed for reproducibility
np.random.seed(42)
random.seed(42)

TOTAL_SAMPLES = 18000  # 6000 samples per zone for balanced distribution
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_sensor_dataset():
    print(f"Generating {TOTAL_SAMPLES} realistic geotechnical sensor samples...")
    
    samples_per_zone = TOTAL_SAMPLES // 3
    data_rows = []
    
    start_time = datetime.datetime(2026, 3, 1, 0, 0, 0)
    time_delta = datetime.timedelta(seconds=2) # 0.5 Hz logged stream
    
    for zone_idx, zone_name in enumerate(["ZONE_A", "ZONE_B", "ZONE_C"]):
        for i in range(samples_per_zone):
            current_timestamp = start_time + time_delta * (zone_idx * samples_per_zone + i)
            
            # -------------------------------------------------------------
            # Physical Sensor Simulation per Hazard Zone
            # -------------------------------------------------------------
            if zone_name == "ZONE_A":
                # ZONE A: Nominal / Baseline Subsurface Stability
                # Strain: 50 - 280 με (Far below 850 με yield limit)
                strain = np.random.normal(loc=140.0, scale=35.0)
                strain = np.clip(strain, 20.0, 320.0)
                
                # Displacement: 0.2 - 2.2 mm vertical sag
                disp = np.random.normal(loc=1.1, scale=0.35)
                disp = np.clip(disp, 0.05, 2.5)
                
                # Multi-node tilt angles (MPU-6050 nodes) in degrees
                n1_tilt_x = np.random.normal(0.02, 0.015)
                n1_tilt_y = np.random.normal(-0.01, 0.015)
                n2_tilt_x = np.random.normal(0.12, 0.04)
                n2_tilt_y = np.random.normal(0.06, 0.03)
                n3_tilt_x = np.random.normal(-0.01, 0.015)
                n3_tilt_y = np.random.normal(0.02, 0.015)
                
                # Vibration / Accelerometer in g
                transient_accel = np.random.exponential(scale=0.012)
                transient_accel = np.clip(transient_accel, 0.002, 0.075)
                rms_vibration = np.random.normal(0.035, 0.012)
                rms_vibration = np.clip(rms_vibration, 0.005, 0.078)
                
                # Risk Anomaly Score: 0.00 - 0.35
                anomaly_score = np.random.uniform(0.05, 0.33)
                node_status = "NOMINAL"
                
            elif zone_name == "ZONE_B":
                # ZONE B: Caution / Micro-seismic Activity & Roof Sag Progression
                # Strain: 320 - 740 με (Rising load on rock bolts)
                strain = np.random.normal(loc=510.0, scale=85.0)
                strain = np.clip(strain, 320.0, 750.0)
                
                # Displacement: 2.5 - 7.9 mm
                disp = np.random.normal(loc=4.8, scale=1.1)
                disp = np.clip(disp, 2.5, 7.95)
                
                # Multi-node tilt angles (Moderate angular stress)
                n1_tilt_x = np.random.normal(0.48, 0.15)
                n1_tilt_y = np.random.normal(0.35, 0.12)
                n2_tilt_x = np.random.normal(1.85, 0.35)
                n2_tilt_y = np.random.normal(1.28, 0.28)
                n3_tilt_x = np.random.normal(0.18, 0.08)
                n3_tilt_y = np.random.normal(0.12, 0.06)
                
                # Vibration / Tremors
                transient_accel = np.random.normal(0.16, 0.06)
                transient_accel = np.clip(transient_accel, 0.08, 0.58)
                rms_vibration = np.random.normal(0.36, 0.09)
                rms_vibration = np.clip(rms_vibration, 0.08, 0.59)
                
                # Risk Anomaly Score: 0.35 - 0.70
                anomaly_score = np.random.uniform(0.36, 0.69)
                node_status = "CAUTION"
                
            else: # ZONE_C
                # ZONE C: Critical Hazard / Yield Threshold Exceeded & Imminent Collapse
                # Strain: 760 - 1550+ με (Exceeds yield limit 850 με)
                strain = np.random.normal(loc=980.0, scale=150.0)
                strain = np.clip(strain, 760.0, 1650.0)
                
                # Displacement: 8.0 - 28.0 mm
                disp = np.random.normal(loc=15.2, scale=3.8)
                disp = np.clip(disp, 8.1, 32.0)
                
                # Multi-node tilt angles (Severe subsidence tilt)
                n1_tilt_x = np.random.normal(2.35, 0.65)
                n1_tilt_y = np.random.normal(2.10, 0.55)
                n2_tilt_x = np.random.normal(5.95, 1.20)
                n2_tilt_y = np.random.normal(5.10, 1.10)
                n3_tilt_x = np.random.normal(0.95, 0.30)
                n3_tilt_y = np.random.normal(0.75, 0.25)
                
                # Vibration / Rock fracture shocks
                transient_accel = np.random.normal(0.95, 0.35)
                transient_accel = np.clip(transient_accel, 0.62, 3.80)
                rms_vibration = np.random.normal(1.48, 0.42)
                rms_vibration = np.clip(rms_vibration, 0.61, 3.95)
                
                # Risk Anomaly Score: 0.70 - 1.00
                anomaly_score = np.random.uniform(0.71, 0.99)
                node_status = "CRITICAL"
                
            # Composite resultant tilt for each node: sqrt(x^2 + y^2)
            n1_tilt = float(np.sqrt(n1_tilt_x**2 + n1_tilt_y**2))
            n2_tilt = float(np.sqrt(n2_tilt_x**2 + n2_tilt_y**2))
            n3_tilt = float(np.sqrt(n3_tilt_x**2 + n3_tilt_y**2))
            
            # Overall primary structural tilt (Max across inclinometer cluster)
            primary_tilt = max(n1_tilt, n2_tilt, n3_tilt)
            
            # Max vibration component
            vibration_peak = max(transient_accel, rms_vibration)
            
            # Numeric Class ID: 0 = Zone A, 1 = Zone B, 2 = Zone C
            zone_id = 0 if zone_name == "ZONE_A" else (1 if zone_name == "ZONE_B" else 2)
            
            row = {
                "timestamp": current_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "strain_microstrain": round(float(strain), 2),
                "tilt_deg": round(float(primary_tilt), 3),
                "vibration_g": round(float(vibration_peak), 4),
                "displacement_mm": round(float(disp), 3),
                "node1_tilt_x": round(float(n1_tilt_x), 3),
                "node1_tilt_y": round(float(n1_tilt_y), 3),
                "node2_tilt_x": round(float(n2_tilt_x), 3),
                "node2_tilt_y": round(float(n2_tilt_y), 3),
                "node3_tilt_x": round(float(n3_tilt_x), 3),
                "node3_tilt_y": round(float(n3_tilt_y), 3),
                "node1_tilt_resultant": round(n1_tilt, 3),
                "node2_tilt_resultant": round(n2_tilt, 3),
                "node3_tilt_resultant": round(n3_tilt, 3),
                "transient_accel_g": round(float(transient_accel), 4),
                "rms_vibration_g": round(float(rms_vibration), 4),
                "anomaly_score": round(float(anomaly_score), 4),
                "sensor_status": node_status,
                "zone_id": zone_id,
                "hazard_zone": zone_name
            }
            data_rows.append(row)
            
    # Shuffle rows to avoid contiguous block bias
    random.shuffle(data_rows)
    
    df = pd.DataFrame(data_rows)
    
    # 1. Save Full Raw Telemetry CSV
    raw_path = os.path.join(OUTPUT_DIR, "raw_sensor_telemetry.csv")
    df.to_csv(raw_path, index=False)
    print(f" Saved full raw telemetry dataset: {raw_path} ({len(df)} records)")
    
    # 2. Save Core ML Clean Matrix (4 Core Features + Aux Features + Target)
    core_features = [
        "strain_microstrain", 
        "tilt_deg", 
        "vibration_g", 
        "displacement_mm", 
        "node1_tilt_resultant",
        "node2_tilt_resultant",
        "node3_tilt_resultant",
        "transient_accel_g",
        "rms_vibration_g",
        "anomaly_score",
        "zone_id",
        "hazard_zone"
    ]
    clean_df = df[core_features]
    clean_path = os.path.join(OUTPUT_DIR, "sensor_dataset_clean.csv")
    clean_df.to_csv(clean_path, index=False)
    print(f" Saved clean ML training dataset: {clean_path}")
    
    # 3. Save a lightweight JSON stream for live test inference simulation (100 samples)
    sample_stream = df.head(100).to_dict(orient="records")
    stream_path = os.path.join(OUTPUT_DIR, "realtime_stream_test.json")
    with open(stream_path, "w") as f:
        json.dump(sample_stream, f, indent=2)
    print(f" Saved real-time stream simulation test set: {stream_path}")
    
    print("\nDataset Summary Statistics by Zone:")
    summary = df.groupby("hazard_zone")[["strain_microstrain", "tilt_deg", "vibration_g", "displacement_mm"]].agg(["mean", "min", "max"])
    print(summary)
    return clean_path

if __name__ == "__main__":
    generate_sensor_dataset()
