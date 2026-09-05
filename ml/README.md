# Team Gradient // SIH Underground Coal Mine Subsidence Monitoring ML Pipeline

Comprehensive end-to-end geotechnical data pipeline, Kaggle benchmark reference extractor, 1 Hz multi-node time-series generator, and XGBoost subsidence risk classifier for our **Smart India Hackathon (SIH)** project.

---

## 🛰️ Hardware & IoT Architecture

Our system deploys **ESP32** sensor nodes across subsurface sectors transmitting telemetry over **LoRa (868.1 MHz)**:

1. **Tilt (MPU6050 Accelerometer / Gyro)**: Multi-axis $X/Y$ tilt angles ($\pm 0.1^\circ$ nominal up to $8.0^\circ+$ collapse).
2. **Displacement / Roof Sag (VL53L4CD ToF Laser)**: Millimeter distance to target ($<1.0\text{mm}$ up to $60\text{mm}+$ bed separation).
3. **Micro-Strain (BX120-3AA + HX711 24-bit ADC)**: Tensile stress on rock bolts in microstrain ($50 - 150\ \mu\epsilon$ up to $>900\ \mu\epsilon$).
4. **Vibration (Piezoelectric Sensor + LM358 Op-Amp)**: Peak seismic vibration amplitude / impulse counts.

---

## 🎯 Target Output Classes & Zone Boundaries

| Zone | Risk Level | Tilt ($X/Y$) | Displacement (Sag) | Micro-Strain ($\mu\epsilon$) | Vibration Peak | Physical Strata Condition |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Zone A** | **`Normal`** | $\pm 0.10^\circ$ | $< 1.0\text{ mm}$ | $50 - 150\ \mu\epsilon$ | $< 0.08\ g$ | Baseline stable rock mass |
| **Zone B** | **`Warning`** | $0.50^\circ - 2.00^\circ$ | $5.0 - 15.0\text{ mm}$ | $180 - 350\ \mu\epsilon$ | $0.10 - 0.65\ g$ | Gradual tilt drift, progressive sag, tremor bursts |
| **Zone C** | **`Critical`** | $2.50^\circ - 8.00^\circ$ | $20.0 - 60.0\text{ mm}$ | $400 - 900\ \mu\epsilon$ | $0.80 - 4.50\ g$ | Yield limit exceeded, rapid subsidence collapse |

---

## 📁 Repository Structure (`ml/`)

```text
ml/
├── data/
│   ├── reference_stats.json            # Extracted Kaggle benchmark metrics (tunnel & building datasets)
│   ├── mine_subsidence_dataset.csv     # 1 Hz multi-node time-series dataset (21,600 samples)
│   └── sensor_dataset_clean.csv        # Static ML training matrix
├── models/
│   ├── subsidence_model.joblib         # Production XGBoost Classifier
│   ├── label_encoder.joblib            # Label encoder (Normal, Warning, Critical)
│   ├── feature_config.json             # Feature names, rolling window config & importance stats
│   └── zone_decision_rules.json        # Fast JSON decision bounds for web/edge
├── src/
│   ├── download_references.py          # KaggleHub reference dataset downloader & stats extractor
│   ├── dataset_generator.py            # 1 Hz multi-node time-series generator with noise & drift
│   ├── train_classifier.py             # Rolling feature extractor & XGBoost/Random Forest trainer
│   └── realtime_inference_demo.py      # Stateful streaming LoRa packet inference engine
├── download_references.py              # Root forwarding script
├── dataset_generator.py                # Root forwarding script
├── train_classifier.py                 # Root forwarding script
├── realtime_inference_demo.py          # Root forwarding script
├── requirements.txt                    # Python dependencies
└── README.md                           # Documentation
```

---

## 🚀 Step-by-Step Execution Guide

### 1. Install Dependencies
```bash
pip install -r ml/requirements.txt
```
*(Or manually: `pip install "kagglehub[pandas-datasets]" xgboost scikit-learn pandas numpy joblib`)*

### 2. Step 1: Download Reference Datasets
Downloads `ziya07/tunnel-risk-dataset` and `ziya07/building-structural-health-sensor-dataset` via `kagglehub` and computes reference statistics:
```bash
python ml/download_references.py
```

### 3. Step 2: Generate 1 Hz Multi-Node Time-Series Dataset
Generates `mine_subsidence_dataset.csv` across `NODE_A1`, `NODE_B1`, `NODE_C1` with realistic noise, baseline offsets, sensor drift, and seismic spikes:
```bash
python ml/dataset_generator.py
```

### 4. Step 3: Train XGBoost Subsidence Classifier
Calculates 5-second temporal rolling features (`mean_5s`, `std_5s`, `roc_5s`), trains models, prints confusion matrix, and exports `subsidence_model.joblib`:
```bash
python ml/train_classifier.py
```

### 5. Step 4: Run Real-Time LoRa Stream Inference Demo
Runs stateful real-time inference on incoming ESP32 JSON packets with rolling circular buffers:
```bash
python ml/realtime_inference_demo.py
```

---

## 💻 Programmatic Real-Time Inference Usage

```python
from ml.src.realtime_inference_demo import RealtimeSubsidencePredictor

# Initialize predictor (manages stateful 5s circular buffer per node)
predictor = RealtimeSubsidencePredictor(window_size=5)

# Example live incoming LoRa packet from ESP32
lora_packet = {
    "node_id": "NODE_B1",
    "timestamp": "2026-03-01 10:00:04",
    "tilt_x_deg": 1.20,
    "tilt_y_deg": 0.95,
    "displacement_mm": 9.80,
    "strain_ue": 280.0,
    "vibration_amp": 0.350
}

result = predictor.process_packet(lora_packet)
print("Predicted Risk:", result["predicted_risk_level"]) # "Warning"
print("Assigned Zone:", result["zone"])                  # "Zone B"
print("Confidence:", result["confidence"])               # 0.9998
print("Action Plan:", result["recommended_action"])      # "Alert underground shift supervisor..."
```
