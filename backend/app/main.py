import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.database.db import init_db, SessionLocal
from app.database.crud import save_telemetry
from app.services.serial_reader import SerialGatewayReader, serial_reader
from app.services.dsp_filter import dsp_processor
from app.services.ml_engine import ml_engine
from app.routers import telemetry, websocket
from app.routers.websocket import ws_manager

active_serial_reader: Optional[SerialGatewayReader] = None


async def handle_incoming_gateway_packet(raw_packet: dict):
    """
    Core Pipeline: Ingests raw serial packet from ESP32 gateway,
    executes DSP filtering and rate estimation, runs Dual-Engine ML evaluation
    with hysteresis, and broadcasts unified telemetry schema over WebSockets.
    """
    # 1. Handle Gateway System Announcements
    if raw_packet.get("event") in ["GATEWAY_READY", "PONG", "HEARTBEAT"]:
        print(f"[GATEWAY] System Event: {raw_packet.get('event')} from {raw_packet.get('gateway_id')}")
        await ws_manager.broadcast_json({"type": "GATEWAY_ANNOUNCEMENT", "payload": raw_packet})
        return

    # 2. Digital Signal Processing Layer (Median Filter + EMA + Dynamic Rate Engine)
    dsp_result = dsp_processor.process(raw_packet)

    # 3. Dual-Engine ML Layer (Branch A Classifier + Branch B 6h LSTM Forecaster + TTF Calculator)
    ml_result = ml_engine.evaluate(raw_packet, dsp_result)

    node_id = str(raw_packet.get("node_id", "NODE_02"))
    hardware_zone = str(raw_packet.get("zone_id") or raw_packet.get("hardware_zone") or "Zone B")
    predicted_zone = ml_result["predicted_zone"]
    confidence = ml_result["confidence"]

    # 4. Formulate Unified Telemetry Payload matching exact engineering specification
    unified_payload: Dict[str, Any] = {
        "node_id": node_id,
        "hardware_zone": hardware_zone,
        "predicted_zone": predicted_zone,
        "confidence": confidence,
        "raw": {
            "disp_mm": float(raw_packet.get("displacement_mm") or 0.0),
            "diff_disp_mm": float(raw_packet.get("differential_displacement_mm") or 0.0),
            "diff_tilt_deg": float(raw_packet.get("differential_tilt_deg") or 0.0),
            "tilt_x_deg": float(raw_packet.get("tilt_x_deg") or 0.0),
            "tilt_y_deg": float(raw_packet.get("tilt_y_deg") or 0.0),
            "vib_amp": float(raw_packet.get("vibration_amp") or 0.0),
            "strain_ue": float(raw_packet.get("strain_ue") or 0.0),
            "rssi": int(raw_packet.get("rssi_dbm") or -66),
            "snr": float(raw_packet.get("snr_db") or 9.0),
            "seq": int(raw_packet.get("seq") or 0)
        },
        "filtered": {
            "smooth_disp_mm": dsp_result["smooth_disp_mm"],
            "smooth_diff_disp_mm": dsp_result["smooth_diff_disp_mm"],
            "disp_velocity_mm_s": dsp_result["disp_velocity_mm_s"],
            "disp_velocity_3s_mm_s": dsp_result.get("disp_velocity_3s_mm_s", dsp_result["disp_velocity_mm_s"]),
            "disp_velocity_10s_mm_s": dsp_result.get("disp_velocity_10s_mm_s", dsp_result["disp_velocity_mm_s"]),
            "disp_accel_mm_s2": dsp_result["disp_accel_mm_s2"],
            "smooth_tilt_deg": dsp_result["smooth_tilt_deg"],
            "smooth_tilt_y_deg": dsp_result.get("smooth_tilt_y_deg", dsp_result["smooth_tilt_deg"]),
            "tilt_rate_deg_s": dsp_result["tilt_rate_deg_s"],
            "tilt_rate_3s_deg_s": dsp_result.get("tilt_rate_3s_deg_s", dsp_result["tilt_rate_deg_s"]),
            "tilt_rate_10s_deg_s": dsp_result.get("tilt_rate_10s_deg_s", dsp_result["tilt_rate_deg_s"])
        },
        "forecasting": {
            "forecast_curve_6h": ml_result["forecast_curve_6h"],
            "forecast_intervals": ["+1h", "+2h", "+3h", "+4h", "+5h", "+6h"],
            "time_to_collapse_hours": ml_result["time_to_collapse_hours"],
            "collapse_message": ml_result["collapse_message"],
            "critical_threshold_mm": ml_engine.collapse_threshold_mm
        },
        "trigger_web_siren": ml_result["trigger_web_siren"],
        "timestamp": raw_packet.get("timestamp"),
        
        # Backwards-compatibility schema for multi-view dashboard components
        "role": raw_packet.get("role", "MONITORING"),
        "zone_id": predicted_zone,
        "current_zone": predicted_zone,
        "predicted_risk": "Critical" if predicted_zone == "Zone C" else "Warning" if predicted_zone == "Zone B" else "Normal",
        "tilt_x_deg": float(raw_packet.get("tilt_x_deg") or 0.0),
        "tilt_y_deg": float(raw_packet.get("tilt_y_deg") or 0.0),
        "tilt_composite_deg": dsp_result["smooth_tilt_deg"],
        "displacement_mm": dsp_result["smooth_disp_mm"],
        "strain_ue": float(raw_packet.get("strain_ue") or 0.0),
        "vibration_amp": float(raw_packet.get("vibration_amp") or 0.0),
        "ref_displacement_mm": float(raw_packet.get("ref_displacement_mm") or 0.0),
        "differential_displacement_mm": dsp_result["smooth_disp_mm"],
        "differential_tilt_deg": dsp_result["smooth_tilt_deg"],
        "forecast_curve_6h": ml_result["forecast_curve_6h"],
        "time_to_collapse_hours": ml_result["time_to_collapse_hours"],
        "collapse_message": ml_result["collapse_message"],
        "siren_trigger": ml_result["trigger_web_siren"],
        "forecast": {
            "time_to_critical_hours": ml_result["time_to_collapse_hours"],
            "status_message": ml_result["collapse_message"],
            "forecast_trajectory": ml_result["forecast_curve_6h"],
            "alert_severity": "CRITICAL" if ml_result["trigger_web_siren"] else "WARNING" if predicted_zone == "Zone B" else "NORMAL"
        }
    }

    # 5. Persist to Database asynchronously
    try:
        db = SessionLocal()
        save_telemetry(db, unified_payload)
        db.close()
    except Exception:
        pass

    # 6. Dispatch to all active WebSockets (/ws/telemetry & /ws/live)
    await ws_manager.broadcast_json(unified_payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 70)
    print(" SIH Underground Coal Mine Subsidence Monitoring - FastAPI Backend")
    print(f" USB-Serial Ingestion + DSP Filter + Dual ML Engine (v{settings.VERSION})")
    print("=" * 70)

    init_db()

    global active_serial_reader
    loop = asyncio.get_running_loop()
    active_serial_reader = SerialGatewayReader(on_packet_callback=handle_incoming_gateway_packet)
    active_serial_reader.start(loop=loop)

    yield

    print("\n[SHUTDOWN] Releasing serial resources and terminating background worker...")
    if active_serial_reader:
        active_serial_reader.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(telemetry.router, prefix=settings.API_V1_STR)
app.include_router(websocket.router)


@app.get("/")
@app.get("/health")
def health_check():
    status = active_serial_reader.get_status() if active_serial_reader else {}
    return {
        "status": "ONLINE",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "serial_connection": status.get("is_connected", False),
        "connected_port": status.get("connected_port"),
        "packets_ingested": status.get("packets_received", 0),
        "websocket_subscribers": len(ws_manager.active_connections)
    }


@app.get("/api/v1/serial/status")
def get_serial_status():
    """Returns hardware COM port diagnostics."""
    if not active_serial_reader:
        return {"error": "Serial reader service not initialized"}
    return active_serial_reader.get_status()


class SerialConfigPayload(BaseModel):
    port: str
    baud_rate: Optional[int] = None
    simulation_mode: Optional[bool] = None


@app.post("/api/v1/serial/configure")
def configure_serial_port(payload: SerialConfigPayload):
    """Dynamically switch COM port or baud rate without server restart."""
    global active_serial_reader
    if not active_serial_reader:
        return {"error": "Serial reader service not initialized"}

    settings.SERIAL_PORT = payload.port
    if payload.baud_rate:
        settings.BAUD_RATE = payload.baud_rate
    if payload.simulation_mode is not None:
        settings.SIMULATION_MODE = payload.simulation_mode

    active_serial_reader.stop()
    loop = asyncio.get_running_loop()
    active_serial_reader = SerialGatewayReader(on_packet_callback=handle_incoming_gateway_packet)
    active_serial_reader.start(loop=loop)

    return {
        "message": f"Serial port updated to '{payload.port}'",
        "status": active_serial_reader.get_status()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
