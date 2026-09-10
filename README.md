<p align="center">
  <h1 align="center">⛏️ Underground Coal Mine Subsidence Monitoring System</h1>
  <p align="center">
    <strong>Team Gradient</strong> · Smart India Hackathon (SIH) 2026
  </p>
  <p align="center">
    <em>An enterprise end-to-end IoT + Machine Learning + Real-Time GIS platform for monitoring rock mass strata movement, detecting progressive roof sag, and triggering automated evacuation sirens during imminent subsidence collapse.</em>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/ESP32-LoRa_433MHz-blue?style=flat-square&logo=espressif" alt="ESP32 LoRa"/>
    <img src="https://img.shields.io/badge/FastAPI-v2.0-009688?style=flat-square&logo=fastapi" alt="FastAPI"/>
    <img src="https://img.shields.io/badge/React_18-Vite_5-61DAFB?style=flat-square&logo=react" alt="React"/>
    <img src="https://img.shields.io/badge/XGBoost-LSTM-orange?style=flat-square&logo=python" alt="ML"/>
    <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker" alt="Docker"/>
    <img src="https://img.shields.io/badge/Firebase-Auth-FFCA28?style=flat-square&logo=firebase" alt="Firebase"/>
    <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License"/>
  </p>
</p>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Sensor Hardware & IoT](#sensor-hardware--iot)
- [Zone Classification & Thresholds](#zone-classification--thresholds)
- [ML Pipeline](#ml-pipeline)
- [Backend API](#backend-api)
- [Frontend Dashboard](#frontend-dashboard)
- [Getting Started](#getting-started)
- [Docker Deployment](#docker-deployment)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Team](#team)
- [License](#license)

---

## Overview

India's underground coal mines face catastrophic subsidence events caused by progressive roof sag, pillar failure, and bed separation. This system provides **real-time, continuous monitoring** of geotechnical parameters across underground mine panels using a network of ESP32 sensor nodes communicating over **LoRa (433 MHz)**, processed by a **dual-engine ML pipeline** (XGBoost classifier + LSTM 6-hour displacement forecaster), and visualized through a **live GIS dashboard** with automated siren triggers.

The platform ingests 1 Hz telemetry from underground sensor nodes, applies **digital signal processing** (median filter + EMA smoothing), performs **real-time ML inference** with hysteresis-based zone classification, and broadcasts unified telemetry over WebSockets to a React dashboard featuring 3D mine visualization, displacement forecasting charts, and multi-zone alert management.

---

## Key Features

| Category | Feature |
|:---|:---|
| **IoT / Hardware** | Dual-node ESP32 topology (Reference + Monitoring) over LoRa SX1278 at 433 MHz |
| **Sensors** | MPU6500 tilt/accelerometer, VL53L4CD ToF laser displacement, HX711 strain gauge, piezoelectric vibration |
| **Signal Processing** | Median filter → EMA smoothing → multi-window velocity/acceleration rate engine (1s, 3s, 10s) |
| **ML Classification** | XGBoost subsidence risk classifier with 5-second rolling temporal features |
| **ML Forecasting** | LSTM-based 6-hour displacement trajectory forecaster with time-to-collapse estimation |
| **Backend** | FastAPI with async serial ingestion, WebSocket broadcasting, REST telemetry API, SQLite persistence |
| **Frontend (Dashboard)** | React + Vite real-time GIS dashboard with zone status grid, sensor gauges, time-series charts |
| **Frontend (Landing)** | 3D Three.js landing page with GSAP animations, Firebase authentication, role-based access |
| **Alerting** | Automated web siren trigger, dynamic early warning banners, hardware relay alert panel |
| **Deployment** | Docker Compose (backend + frontend), PlatformIO firmware builds |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        UNDERGROUND MINE PANEL                               │
│                                                                             │
│  ┌──────────────────┐     LoRa 433 MHz      ┌──────────────────────┐       │
│  │  NODE_01 (Ref)   │ ─────────────────────▶ │  GATEWAY NODE        │       │
│  │  ESP32 + MPU6500 │                        │  ESP32 (LoRa Rx)     │       │
│  └──────────────────┘                        │  JSON → USB/UART     │       │
│                                              │  JSON → WiFi HTTP    │       │
│  ┌──────────────────┐     LoRa 433 MHz      └─────────┬────────────┘       │
│  │  NODE_02 (Mon)   │ ─────────────────────▶           │                    │
│  │  ESP32 + MPU6500 │                                  │                    │
│  │  + VL53L4CD ToF  │                                  │                    │
│  │  + HX711 Strain  │                                  │                    │
│  │  + Piezo Vib     │                                  │                    │
│  └──────────────────┘                                  │                    │
└────────────────────────────────────────────────────────│────────────────────┘
                                                         │ USB Serial / WiFi
                                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND SERVER (FastAPI)                          │
│                                                                             │
│  ┌────────────────┐   ┌──────────────────┐   ┌───────────────────────┐     │
│  │ Serial Reader  │──▶│  DSP Filter      │──▶│  Dual ML Engine       │     │
│  │ (UART/COM)     │   │  Median + EMA    │   │  Branch A: XGBoost    │     │
│  │                │   │  Rate Engine     │   │  Branch B: LSTM 6h    │     │
│  └────────────────┘   └──────────────────┘   │  + TTF Calculator     │     │
│                                               └───────────┬───────────┘     │
│                                                           │                 │
│  ┌────────────────┐   ┌──────────────────┐               │                 │
│  │ SQLite DB      │◀──│  Telemetry CRUD  │◀──────────────┘                 │
│  │ (Persistence)  │   └──────────────────┘               │                 │
│  └────────────────┘                                      │                 │
│                                                           ▼                 │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │            WebSocket Broadcast (/ws/telemetry & /ws/live)     │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                              │                │                             │
│  REST API (/api/v1/*)        │                │      Health (/health)       │
└──────────────────────────────│────────────────│─────────────────────────────┘
                               ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND APPLICATIONS                               │
│                                                                             │
│  ┌──────────────────────────────┐  ┌───────────────────────────────────┐   │
│  │  Landing Page (src/)         │  │  Operations Dashboard (frontend/) │   │
│  │  • 3D Three.js Mine Viz     │  │  • Real-Time ML Forecasting HUD  │   │
│  │  • Firebase Auth            │  │  • Zone Status Grid              │   │
│  │  • Role-based Login         │  │  • Sensor Metric Gauges          │   │
│  │  • Admin Console            │  │  • Time-Series Charts            │   │
│  │  • Worker HUD               │  │  • Vibration FFT Spectral        │   │
│  │  • GSAP Animations          │  │  • GIS Mine Map View             │   │
│  └──────────────────────────────┘  │  • Displacement Forecast Chart  │   │
│                                     │  • Early Warning Banners        │   │
│                                     │  • Hardware Relay Alert Panel   │   │
│                                     │  • Active Shift Muster Desk    │   │
│                                     └───────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technologies |
|:---|:---|
| **Firmware** | C/C++ · Arduino Framework · PlatformIO · ESP32 DevKit V1 |
| **Communication** | LoRa SX1278 (433 MHz) · UART Serial (115200 baud) · WiFi HTTP |
| **Sensors** | MPU6500 (Tilt) · VL53L4CD (ToF Displacement) · HX711 + BX120-3AA (Strain) · Piezo + LM358 (Vibration) |
| **Backend** | Python 3.10+ · FastAPI · Uvicorn · Pydantic · SQLAlchemy · WebSockets · PySerial |
| **ML / AI** | XGBoost · scikit-learn · PyTorch (LSTM Forecaster) · NumPy · Pandas · SciPy · KaggleHub |
| **Frontend** | React 18 · Vite 5 · Tailwind CSS 3 · Three.js · React Three Fiber · GSAP · Lucide Icons · Axios |
| **Auth** | Firebase Authentication |
| **Database** | SQLite (development) · PostgreSQL / InfluxDB (production-ready) |
| **DevOps** | Docker · Docker Compose |

---

## Project Structure

```text
coal-mine-subsidence-monitoring/
├── README.md                            # This file
├── docker-compose.yml                   # Multi-container deployment
├── .gitignore
├── package.json                         # Root Vite + React (Landing Page)
├── vite.config.js
├── tailwind.config.js
├── index.html                           # Landing page entry
│
├── src/                                 # Landing Page & Auth UI (React + Three.js)
│   ├── App.jsx                          # Root app with auth flow & tab routing
│   ├── main.jsx
│   ├── index.css
│   ├── pages/
│   │   ├── LandingPage.jsx              # 3D hero with Three.js mine visualization
│   │   ├── AuthPage.jsx                 # Firebase authentication page
│   │   ├── DashboardPage.jsx            # Main operational dashboard wrapper
│   │   ├── AdminConsole.jsx             # Admin panel for system configuration
│   │   └── WorkerHUD.jsx               # Simplified worker heads-up display
│   ├── components/
│   │   ├── Navbar.jsx
│   │   ├── Footer.jsx
│   │   ├── AuthModal.jsx                # Login/signup modal (Firebase)
│   │   ├── DashboardView.jsx            # Real-time ML forecasting HUD
│   │   ├── DisplacementForecastChart.jsx # 6-hour LSTM trajectory chart
│   │   ├── DynamicEarlyWarningBanner.jsx # Animated alert banners
│   │   ├── HardwareRelayAlertPanel.jsx  # Hardware siren/relay controls
│   │   ├── ActiveShiftMusterDesk.jsx    # Shift roster & personnel tracking
│   │   └── 3d/                          # Three.js 3D components
│   ├── context/
│   │   ├── AuthContext.jsx              # Firebase auth state management
│   │   └── TelemetryContext.jsx         # WebSocket telemetry state
│   └── services/
│       ├── firebase.js                  # Firebase SDK configuration
│       ├── mlPredictor.js               # Client-side ML prediction helpers
│       └── siren.js                     # Web Audio API siren controller
│
├── firmware/                            # ESP32 Embedded C/C++ (PlatformIO)
│   ├── sensor_node/                     # Dual-build: Node 1 (Ref) & Node 2 (Mon)
│   │   ├── platformio.ini               # PlatformIO build configurations
│   │   ├── include/
│   │   │   └── config.h                 # LoRa freq, node IDs, sensor pinouts
│   │   └── src/
│   │       ├── node1_reference.cpp      # Reference datum node (MPU6500 only)
│   │       ├── node2_monitoring.cpp     # Full monitoring node (all sensors)
│   │       ├── mpu6500_handler.cpp      # Tilt & accelerometer driver
│   │       ├── vl53l4cd_handler.cpp     # ToF laser displacement driver
│   │       ├── strain_hx711_handler.cpp # HX711 micro-strain bridge driver
│   │       └── piezo_handler.cpp        # Piezo vibration spike detector
│   └── gateway_node/                    # Central LoRa gateway (Rx → Serial/MQTT)
│       ├── platformio.ini
│       └── src/
│           └── main.cpp                 # LoRa packet aggregation & JSON forwarding
│
├── ml_engine/                           # ML Training, Feature Engineering & Artifacts
│   ├── requirements.txt
│   ├── artifacts/                       # Production-ready model artifacts
│   │   ├── subsidence_model.joblib      # Trained XGBoost classifier
│   │   ├── subsidence_model_optimized.joblib
│   │   ├── subsidence_pipeline_package.joblib
│   │   ├── label_encoder.joblib         # Zone label encoder
│   │   ├── feature_config.json          # Feature names & importance
│   │   ├── displacement_forecaster.pth  # PyTorch LSTM forecaster weights
│   │   ├── displacement_forecaster.onnx # ONNX export for edge deployment
│   │   ├── forecaster_scaler.joblib     # Feature scaler for LSTM
│   │   ├── forecaster_metadata.json     # Forecaster hyperparameters
│   │   ├── optimization_report.json     # Model tuning results
│   │   └── tuning_report.json
│   ├── data/                            # Training datasets
│   └── src/
│       ├── fetch_references.py          # KaggleHub benchmark data downloader
│       ├── dataset_generator.py         # 1 Hz multi-node synthetic data generator
│       ├── feature_engineering.py       # Rolling window feature extraction
│       ├── advanced_feature_engineering.py
│       ├── train.py                     # XGBoost / Random Forest trainer
│       ├── train_displacement_forecaster.py  # LSTM forecaster trainer
│       ├── evaluate.py                  # Metrics & confusion matrix
│       ├── model_tuning.py              # Hyperparameter optimization
│       ├── filter_and_tune.py           # Signal filter calibration
│       ├── signal_filtering.py          # DSP filter prototyping
│       └── threshold_calibration_and_export.py  # Zone boundary tuning
│
├── ml/                                  # Standalone ML pipeline (alternative entry)
│   ├── README.md                        # Detailed ML documentation
│   ├── requirements.txt
│   ├── src/                             # Mirror scripts with root forwarding
│   ├── models/                          # Trained model exports
│   └── data/                            # Datasets & reference stats
│
├── backend/                             # FastAPI Real-Time Telemetry Server
│   ├── requirements.txt
│   ├── main.py                          # Uvicorn entry point
│   ├── .env                             # Environment configuration
│   ├── app/
│   │   ├── main.py                      # FastAPI app, lifespan, core pipeline
│   │   ├── config.py                    # Settings (serial port, DB, ML paths, thresholds)
│   │   ├── models/                      # Pydantic schemas & DB models
│   │   ├── services/
│   │   │   ├── serial_reader.py         # ESP32 UART serial JSON ingestion
│   │   │   ├── dsp_filter.py            # Median + EMA + rate engine (1s/3s/10s)
│   │   │   ├── ml_engine.py             # Dual-engine: XGBoost + LSTM + hysteresis
│   │   │   ├── ml_service.py            # ML model loading & inference service
│   │   │   ├── forecast_service.py      # LSTM displacement forecasting
│   │   │   ├── alert_service.py         # SMS/email/buzzer alert triggers
│   │   │   ├── serial_listener.py       # Alternative serial listener
│   │   │   └── fault_tolerant_ml_service.py  # Graceful degradation ML wrapper
│   │   ├── routers/
│   │   │   ├── telemetry.py             # REST endpoints for historical data
│   │   │   └── websocket.py             # Live WebSocket stream manager
│   │   └── database/
│   │       ├── db.py                    # SQLite / PostgreSQL connection
│   │       └── crud.py                  # Telemetry read/write queries
│   └── tests/
│       └── test_api.py                  # API integration tests
│
└── frontend/                            # Operations Dashboard (React + Vite)
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── App.jsx                      # Dashboard app with tab navigation
        ├── main.jsx
        ├── DashboardView.jsx            # ML Forecasting HUD (primary view)
        ├── components/
        │   ├── Navbar.jsx
        │   ├── AlertBanner.jsx          # Dynamic zone alert banners
        │   ├── ZoneStatusGrid.jsx       # Zone A/B/C status cards
        │   ├── SensorMetricCard.jsx     # Real-time sensor gauges
        │   ├── DashboardView.jsx        # Detailed forecasting dashboard
        │   ├── Charts/
        │   │   ├── TimeSeriesChart.jsx   # Real-time line charts
        │   │   └── VibrationFFTChart.jsx # Seismic spectral density
        │   └── GISMap/
        │       └── MineMapView.jsx      # 2D/3D mine spatial map
        ├── context/
        │   └── WebSocketContext.jsx      # Real-time sensor state
        ├── hooks/
        │   └── useLiveTelemetry.js       # Custom telemetry hook
        └── services/
            └── api.js                    # Axios REST client
```

---

## Sensor Hardware & IoT

### Two-Node Topology

| Node | ID | Role | Hardware | Purpose |
|:---|:---|:---|:---|:---|
| **Node 1** | `NODE_01` | `REFERENCE` | ESP32 + MPU6500 + LoRa SX1278 | Fixed bedrock reference datum for differential false-alarm rejection |
| **Node 2** | `NODE_02` | `MONITORING` | ESP32 + MPU6500 + VL53L4CD + HX711 + Piezo + LoRa SX1278 | Full real-time underground roof sag & strain monitoring |

### Sensor Specifications

| Sensor | IC / Module | Measurement | Range | Interface |
|:---|:---|:---|:---|:---|
| **Tilt / Accelerometer** | MPU6500 | X/Y axis tilt (°) | ±0.1° to 8.0°+ | I2C (SDA: 21, SCL: 22) |
| **Displacement / Roof Sag** | VL53L4CD (ToF Laser) | Distance to target (mm) | <1.0 mm to 60+ mm | I2C (XSHUT: 27) |
| **Micro-Strain** | BX120-3AA + HX711 24-bit ADC | Tensile stress (µε) | 50 to 900+ µε | GPIO (DOUT: 16, SCK: 17) |
| **Vibration** | Piezo + LM358 Op-Amp | Peak amplitude (g) | <0.08g to 4.5+ g | ADC (Analog: 34, INT: 35) |

### LoRa Configuration

| Parameter | Value |
|:---|:---|
| Frequency Band | 433 MHz ISM |
| Spreading Factor | 7 |
| Sync Word | `0x12` |
| TX Power | 20 dBm |
| Baud Rate (Serial) | 115200 |

---

## Zone Classification & Thresholds

The system classifies mine conditions into three risk zones using geotechnical threshold boundaries:

| Zone | Risk Level | Tilt (X/Y) | Displacement (Sag) | Micro-Strain (µε) | Vibration Peak | Physical Condition |
|:---|:---|:---|:---|:---|:---|:---|
| 🟢 **Zone A** | **Normal** | ±0.10° | <1.0 mm | 50–150 µε | <0.08 g | Baseline stable rock mass |
| 🟡 **Zone B** | **Warning** | 0.50°–2.00° | 5.0–15.0 mm | 180–350 µε | 0.10–0.65 g | Gradual tilt drift, progressive sag, tremor bursts |
| 🔴 **Zone C** | **Critical** | 2.50°–8.00° | 20.0–60.0 mm | 400–900 µε | 0.80–4.50 g | Yield limit exceeded, rapid subsidence collapse |

### Critical Alert Thresholds (Backend)

```
CRITICAL_STRAIN_UE  = 750.0 µε
CRITICAL_DISP_MM    = 20.0 mm
CRITICAL_TILT_DEG   = 2.5°
CRITICAL_VIB_AMP    = 0.80 g
COLLAPSE_THRESHOLD  = 400.0 mm
```

---

## ML Pipeline

### Branch A — XGBoost Subsidence Risk Classifier

- **Input**: 1 Hz telemetry (tilt, displacement, strain, vibration)
- **Feature Engineering**: 5-second rolling window → `mean_5s`, `std_5s`, `roc_5s` for each sensor channel
- **Output**: Zone classification (A/B/C) with confidence score
- **Artifacts**: `subsidence_model.joblib`, `label_encoder.joblib`, `feature_config.json`

### Branch B — LSTM 6-Hour Displacement Forecaster

- **Input**: Historical displacement time-series
- **Architecture**: PyTorch LSTM network
- **Output**: 6-hour displacement trajectory curve + time-to-collapse estimation
- **Artifacts**: `displacement_forecaster.pth` / `.onnx`, `forecaster_scaler.joblib`

### Training Pipeline

```bash
# 1. Install ML dependencies
pip install -r ml_engine/requirements.txt

# 2. Fetch Kaggle reference benchmark data
python ml_engine/src/fetch_references.py

# 3. Generate 1 Hz multi-node time-series dataset (21,600 samples)
python ml_engine/src/dataset_generator.py

# 4. Train XGBoost classifier with temporal features
python ml_engine/src/train.py

# 5. Train LSTM displacement forecaster
python ml_engine/src/train_displacement_forecaster.py

# 6. Evaluate model performance
python ml_engine/src/evaluate.py
```

### Programmatic Inference

```python
from ml.src.realtime_inference_demo import RealtimeSubsidencePredictor

predictor = RealtimeSubsidencePredictor(window_size=5)

packet = {
    "node_id": "NODE_B1",
    "timestamp": "2026-03-01 10:00:04",
    "tilt_x_deg": 1.20,
    "tilt_y_deg": 0.95,
    "displacement_mm": 9.80,
    "strain_ue": 280.0,
    "vibration_amp": 0.350
}

result = predictor.process_packet(packet)
print(result["predicted_risk_level"])  # "Warning"
print(result["zone"])                  # "Zone B"
print(result["confidence"])            # 0.9998
```

---

## Backend API

The FastAPI backend provides real-time telemetry ingestion, ML inference, and WebSocket broadcasting.

### Core Pipeline Flow

```
ESP32 Gateway → Serial Reader → DSP Filter → Dual ML Engine → WebSocket Broadcast
                                    ↓                               ↓
                              Rate Engine              SQLite Persistence
                           (1s, 3s, 10s)
```

### Key Services

| Service | File | Description |
|:---|:---|:---|
| Serial Reader | `serial_reader.py` | Async UART/USB JSON packet ingestion from ESP32 gateway |
| DSP Filter | `dsp_filter.py` | Median filter + EMA smoothing + multi-window rate engine |
| ML Engine | `ml_engine.py` | Dual-engine: XGBoost classifier + LSTM forecaster + hysteresis |
| Alert Service | `alert_service.py` | SMS / email / hardware buzzer trigger on danger states |
| Forecast Service | `forecast_service.py` | 6-hour displacement trajectory prediction |

---

## Frontend Dashboard

The system includes **two frontend applications**:

### 1. Landing Page (`src/`)
- **3D Mine Visualization** — Three.js + React Three Fiber
- **GSAP Animations** — Smooth scroll-driven transitions
- **Firebase Auth** — Role-based login (Worker / Admin)
- **Admin Console** — System configuration & management
- **Worker HUD** — Simplified heads-up display for underground personnel

### 2. Operations Dashboard (`frontend/`)
- **Real-Time ML Forecasting HUD** — Live predictions with confidence scores
- **Zone Status Grid** — Zone A/B/C cards with live sensor data
- **Sensor Metric Gauges** — Tilt, displacement, strain, vibration readouts
- **Time-Series Charts** — Historical trend visualization
- **Vibration FFT** — Seismic spectral density analysis
- **GIS Mine Map** — 2D/3D spatial sensor node map
- **Displacement Forecast Chart** — 6-hour LSTM trajectory visualization
- **Early Warning Banners** — Animated alert banners
- **Hardware Relay Panel** — Physical siren & relay control interface
- **Active Shift Muster Desk** — Personnel tracking & evacuation roster

---

## Getting Started

### Prerequisites

- **Python** 3.10+
- **Node.js** 18+ & npm
- **PlatformIO** CLI (for firmware flashing)
- **Docker** & Docker Compose (optional, for containerized deployment)

### 1. Clone the Repository

```bash
git clone https://github.com/team-gradient/coal-mine-subsidence-monitoring.git
cd coal-mine-subsidence-monitoring
```

### 2. Train ML Models (`ml_engine/`)

```bash
pip install -r ml_engine/requirements.txt
python ml_engine/src/fetch_references.py
python ml_engine/src/dataset_generator.py
python ml_engine/src/train.py
python ml_engine/src/train_displacement_forecaster.py
```

### 3. Start the Backend (`backend/`)

```bash
pip install -r backend/requirements.txt

# Start with simulation mode (no physical hardware required)
SIMULATION_MODE=true python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

### 4. Start the Operations Dashboard (`frontend/`)

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at `http://localhost:5173`.

### 5. Start the Landing Page (Root `src/`)

```bash
# From project root
npm install
npm run dev
```

Landing page available at `http://localhost:5174` (or next available port).

### 6. Flash Firmware (`firmware/`)

```bash
# Flash Node 1 (Reference Datum)
cd firmware/sensor_node
pio run -e node1_reference -t upload

# Flash Node 2 (Monitoring Node)
pio run -e node2_monitoring -t upload

# Flash Gateway Node
cd ../gateway_node
pio run -t upload
```

---

## Docker Deployment

Launch the full backend + frontend stack with Docker Compose:

```bash
docker-compose up --build
```

| Service | Container | Port | URL |
|:---|:---|:---|:---|
| Backend (FastAPI) | `mine_subsidence_backend` | `8000` | `http://localhost:8000` |
| Frontend (React) | `mine_subsidence_frontend` | `3000` | `http://localhost:3000` |

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|:---|:---|:---|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `SERIAL_PORT` | `COM5` | USB serial port for ESP32 gateway |
| `BAUD_RATE` | `115200` | Serial baud rate |
| `SIMULATION_MODE` | `false` | Enable simulated telemetry (no hardware) |
| `DB_URL` | `sqlite:///./subsidence.db` | Database connection string |
| `ML_MODEL_PATH` | `ml_engine/artifacts/subsidence_model.joblib` | XGBoost model path |
| `ML_ENCODER_PATH` | `ml_engine/artifacts/label_encoder.joblib` | Label encoder path |
| `FORECASTER_PTH_PATH` | `ml_engine/artifacts/displacement_forecaster.pth` | LSTM model path |
| `COLLAPSE_THRESHOLD_MM` | `400.0` | Displacement collapse threshold (mm) |

### Frontend (`docker-compose.yml`)

| Variable | Default | Description |
|:---|:---|:---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API base URL |
| `VITE_WS_BASE_URL` | `ws://localhost:8000/ws/telemetry` | WebSocket endpoint |

---

## API Reference

### REST Endpoints

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/` | Health check |
| `GET` | `/health` | System status with serial & WebSocket diagnostics |
| `GET` | `/api/v1/serial/status` | Hardware COM port diagnostics |
| `POST` | `/api/v1/serial/configure` | Dynamically switch COM port or baud rate |
| `GET` | `/api/v1/telemetry/*` | Historical telemetry queries |

### WebSocket Endpoints

| Endpoint | Description |
|:---|:---|
| `ws://localhost:8000/ws/telemetry` | Primary live telemetry stream |
| `ws://localhost:8000/ws/live` | Alternative live data stream |

### Unified Telemetry Payload Schema

```json
{
  "node_id": "NODE_02",
  "hardware_zone": "Zone B",
  "predicted_zone": "Zone B",
  "confidence": 0.9998,
  "raw": {
    "disp_mm": 9.80,
    "diff_disp_mm": 8.50,
    "tilt_x_deg": 1.20,
    "tilt_y_deg": 0.95,
    "vib_amp": 0.35,
    "strain_ue": 280.0,
    "rssi": -66,
    "snr": 9.0
  },
  "filtered": {
    "smooth_disp_mm": 9.65,
    "disp_velocity_mm_s": 0.12,
    "disp_velocity_3s_mm_s": 0.10,
    "disp_velocity_10s_mm_s": 0.08,
    "smooth_tilt_deg": 1.18,
    "tilt_rate_deg_s": 0.02
  },
  "forecasting": {
    "forecast_curve_6h": [9.8, 10.2, 10.9, 11.5, 12.1, 12.8],
    "forecast_intervals": ["+1h", "+2h", "+3h", "+4h", "+5h", "+6h"],
    "time_to_collapse_hours": 48.5,
    "collapse_message": "No imminent collapse detected",
    "critical_threshold_mm": 400.0
  },
  "trigger_web_siren": false,
  "timestamp": "2026-03-01T10:00:04Z"
}
```

---

## Testing

### Backend Tests

```bash
cd backend
pip install pytest httpx
pytest tests/ -v
```

### ML Model Tests

```bash
cd ml
python test_inference.py
```

---

## Team

**Team Gradient** — Smart India Hackathon (SIH) 2026

---

## License

This project is developed for the **Smart India Hackathon 2026**. All rights reserved by Team Gradient.
