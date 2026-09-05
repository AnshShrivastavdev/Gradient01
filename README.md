# Team Gradient // SIH Underground Coal Mine Subsidence Monitoring System

An enterprise end-to-end IoT, Machine Learning, and Real-Time GIS system designed for the **Smart India Hackathon (SIH)** to monitor rock mass strata movement, detect progressive roof sag, and trigger automated evacuation sirens during imminent subsidence collapse.

---

## 🏗️ System Architecture & Directory Structure

```text
mine-subsidence-system/
├── README.md
├── docker-compose.yml
├── .gitignore
│
├── firmware/                              # Embedded C/C++ (PlatformIO / Arduino)
│   ├── sensor_node/                       # ESP32 Remote Sensor Node (LoRa Tx)
│   │   ├── platformio.ini
│   │   ├── include/
│   │   │   ├── config.h                   # LoRa frequency (433MHz), node ID, pinouts
│   │   │   └── sensors.h
│   │   └── src/
│   │       ├── main.cpp                   # Sampling loop & packet transmission
│   │       ├── mpu6050_handler.cpp        # Tilt & accelerometer reading
│   │       ├── vl53l4cd_handler.cpp       # ToF distance/displacement reading
│   │       ├── strain_hx711_handler.cpp   # Micro-strain bridge reading
│   │       └── piezo_handler.cpp          # Vibration spike detection
│   │
│   └── gateway_node/                      # ESP32 Central Gateway Node (LoRa Rx -> Serial/MQTT)
│       ├── platformio.ini
│       └── src/
│           └── main.cpp                   # Receives LoRa packets & forwards JSON via UART/USB & WiFi HTTP
│
├── ml_engine/                             # ML Training, Feature Extraction & Artifacts
│   ├── requirements.txt                   # scikit-learn, xgboost, joblib, pandas, kagglehub
│   ├── artifacts/
│   │   ├── subsidence_model.joblib        # Serialized trained XGBoost model
│   │   ├── label_encoder.joblib           # Target label encoder
│   │   └── feature_config.json            # Model features and metadata
│   ├── data/
│   │   ├── raw/                           # Raw samples from Kagglehub reference datasets
│   │   └── processed/
│   │       └── mine_subsidence_dataset.csv
│   └── src/
│       ├── fetch_references.py            # Kagglehub automated dataset extraction
│       ├── dataset_generator.py           # Multi-zone synthetic dataset generator
│       ├── feature_engineering.py         # Rolling window (mean, std, delta) logic
│       ├── train.py                       # Random Forest / XGBoost training script
│       └── evaluate.py                    # Model validation metrics & confusion matrix
│
├── backend/                               # Real-Time API & Sensor Ingestion Service
│   ├── requirements.txt                   # FastAPI, uvicorn, pyserial, websockets, joblib
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                        # FastAPI entry point & lifespan manager
│   │   ├── config.py                      # DB connection strings, serial COM ports, alert thresholds
│   │   ├── models/                        # Pydantic schemas & DB models
│   │   │   ├── sensor_data.py
│   │   │   └── alert.py
│   │   ├── services/
│   │   │   ├── serial_reader.py           # Reads live JSON packets from ESP32 gateway over UART
│   │   │   ├── ml_service.py              # Loads .joblib model & runs live inference
│   │   │   └── alert_service.py           # Triggers SMS/email/buzzer on Danger/Warning states
│   │   ├── routers/
│   │   │   ├── telemetry.py               # REST endpoints for historical node observations
│   │   │   └── websocket.py               # Live WebSocket stream to frontend UI
│   │   └── database/
│   │       ├── db.py                      # SQLite / PostgreSQL / InfluxDB connection
│   │       └── crud.py                    # Read/write queries for sensor logs
│   └── tests/
│       └── test_api.py
│
└── frontend/                              # Real-time GIS & Dashboard UI (React + Tailwind / Vite)
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── App.jsx
        ├── main.jsx
        ├── context/
        │   └── WebSocketContext.jsx       # Real-time sensor state management
        ├── hooks/
        │   └── useLiveTelemetry.js        # Custom hook for incoming sensor telemetry
        ├── components/
        │   ├── Navbar.jsx
        │   ├── AlertBanner.jsx            # Dynamic alert banner (Zone B Caution / Zone C Danger)
        │   ├── ZoneStatusGrid.jsx         # Cards showing status of Zone A, B, C
        │   ├── SensorMetricCard.jsx       # Real-time Tilt, Displacement, Strain, Vibration gauges
        │   ├── Charts/
        │   │   ├── TimeSeriesChart.jsx    # Real-time line charts (Chart.js / Recharts)
        │   │   └── VibrationFFTChart.jsx  # Seismic spectral density visualization
        │   └── GISMap/
        │       └── MineMapView.jsx        # 2D/3D spatial map of coalfield & sensor nodes
        └── services/
            └── api.js                     # Axios instance for backend REST queries
```

---

## ⚡ Quickstart

### 1. Run Machine Learning Pipeline (`ml_engine/`)
```bash
# Install dependencies
pip install -r ml_engine/requirements.txt

# Fetch Kaggle benchmark data
python ml_engine/src/fetch_references.py

# Generate 1 Hz time-series dataset (21,600 samples)
python ml_engine/src/dataset_generator.py

# Train XGBoost model with 5s rolling window features
python ml_engine/src/train.py
```

### 2. Run FastAPI Backend (`backend/`)
```bash
# Install dependencies
pip install -r backend/requirements.txt

# Start backend server with live simulation stream / serial ingestion
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

### 3. Run React Frontend (`frontend/`)
```bash
npm run dev
```

---

## 🐳 Docker Deployment
To launch both the FastAPI backend and React frontend with Docker Compose:
```bash
docker-compose up --build
```
