# Server Lifecycle & Startup Policy

## Persistent Background Servers
Always keep the complete stack running continuously in the background as long-running daemons (`IsDaemon: true`). **Do NOT stop, kill, or restart these servers** unless explicitly instructed by the user. If any server goes down or fails a health check, proactively revive it immediately.

## The Complete Stack Components:

1. **FastAPI Backend Server** (Port 8000)
   - **Working Directory:** `backend`
   - **Command:** `python -m uvicorn main:app --host 0.0.0.0 --port 8000`
   - **Role:** Handles real-time ESP32 gateway ingestion (USB-Serial & WiFi HTTP POST to `/api/v1/telemetry/ingest`), DSP filtering, dual ML inference, and WebSocket broadcasts to `/ws/telemetry`.

2. **3D Landing Page & Main Website** (Port 5174 / 5173)
   - **Working Directory:** Project Root (`.`)
   - **Command:** `npm run dev`
   - **Role:** Main application with interactive Three.js 3D mine strata visualization, GSAP scroll animations, and Worker/Admin portal authentication.

3. **Operations Dashboard** (Port 5173 / 5174)
   - **Working Directory:** `frontend`
   - **Command:** `npm run dev`
   - **Role:** Real-time GIS geotechnical monitoring HUD, sensor gauges, and ML forecasting curves.
