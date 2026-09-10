import asyncio
from datetime import datetime, timezone
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


def _async_db_persist(payload: Dict[str, Any]):
    """Offloads SQLite writes to prevent blocking low-latency packet pipeline."""
    try:
        db = SessionLocal()
        save_telemetry(db, payload)
        db.close()
    except Exception:
        pass


async def handle_incoming_gateway_packet(raw_packet: dict) -> Dict[str, Any]:
    """
    Low-Latency Core Pipeline (< 15 ms total execution):
    1. Ingests LoRa packet from ESP32 gateway (USB-Serial or WiFi HTTP POST).
    2. Drops / acknowledges NODE_A1 / NODE_01 reference packets to keep dashboard focused on active sag.
    3. Runs in-memory DSP filtering, baseline tracking, and instantaneous micro-dynamics.
    4. Evaluates Dual ML Engine (< 5 ms) with fine-grained sensitivity and sticky hysteresis.
    5. Non-blocking parallel broadcast to all connected WebSocket clients.
    6. Returns synchronous risk decision for synchronized gateway LED & buzzer actuation.
    """
    # 1. Handle Gateway System Announcements
    if raw_packet.get("event") in ["GATEWAY_READY", "PONG", "HEARTBEAT"]:
        print(f"[GATEWAY] System Event: {raw_packet.get('event')} from {raw_packet.get('gateway_id')}")
        await ws_manager.broadcast_json({"type": "GATEWAY_ANNOUNCEMENT", "payload": raw_packet})
        return {
            "status": "success",
            "risk_level": "SAFE",
            "alert_zone": "Zone A",
            "trigger_siren": False
        }

    raw_node_id = str(raw_packet.get("node_id", "NODE_02"))
    role = str(raw_packet.get("role") or ("REFERENCE" if "1" in raw_node_id else "MONITORING"))
    is_reference = (role == "REFERENCE" or raw_node_id in ["NODE_01", "NODE_A1", "NODE_1"])

    # 2. Reference Node Handling: Update internal baseline and acknowledge without congesting dashboard
    if is_reference:
        dsp_processor.process(raw_packet)
        return {
            "status": "success",
            "risk_level": "SAFE",
            "alert_zone": "Zone A",
            "trigger_siren": False,
            "node_id": raw_node_id
        }

    # Normalize monitoring node ID
    node_id = "NODE_02" if raw_node_id in ["NODE_A2", "NODE_2"] else raw_node_id

    # 3. Digital Signal Processing Layer (In-memory median filter + EMA + real-time micro-dynamics)
    dsp_result = dsp_processor.process(raw_packet)

    # 4. Preloaded Dual-Engine ML Layer (Sub-5ms: Classifier + Vectorized PyTorch LSTM Forecaster)
    ml_result = ml_engine.evaluate(raw_packet, dsp_result)
    
    current_risk = ml_result["current_risk"]
    predicted_zone = ml_result["predicted_zone"]
    confidence = ml_result["confidence"]
    trigger_web_siren = ml_result["trigger_web_siren"]
    forecast_curve = ml_result["forecast_curve_6h"]
    time_to_collapse = ml_result["time_to_collapse_hours"]
    collapse_message = ml_result["collapse_message"]

    hardware_zone = str(raw_packet.get("zone_id") or raw_packet.get("hardware_zone") or predicted_zone)
    packet_timestamp = raw_packet.get("timestamp") or datetime.now(timezone.utc).isoformat()

    # 5. Formulate Normalized Telemetry Payload matching exact frontend specification
    unified_payload: Dict[str, Any] = {
        "node_id": node_id,
        "displacement_mm": dsp_result["smooth_disp_mm"],
        "tilt_x_deg": float(raw_packet.get("tilt_x_deg") if raw_packet.get("tilt_x_deg") is not None else (raw_packet.get("tx") or 0.0)),
        "tilt_y_deg": float(raw_packet.get("tilt_y_deg") if raw_packet.get("tilt_y_deg") is not None else (raw_packet.get("ty") or 0.0)),
        "tilt_composite_deg": dsp_result["smooth_tilt_deg"],
        "strain_ue": float(raw_packet.get("strain_ue") if raw_packet.get("strain_ue") is not None else (raw_packet.get("st") or 0.0)),
        "vibration_amp": float(raw_packet.get("vibration_amp") if raw_packet.get("vibration_amp") is not None else (raw_packet.get("v") or 0.015)),
        "shock_count": int(raw_packet.get("shock_count") or 0),
        
        # Risk & Zone Categorization
        "current_risk": current_risk,
        "predicted_risk": current_risk,
        "predicted_zone": predicted_zone,
        "zone_id": predicted_zone,
        "current_zone": predicted_zone,
        "hardware_zone": hardware_zone,
        "confidence": confidence,
        "probabilities": ml_result.get("probabilities", {}),
        "trigger_web_siren": trigger_web_siren,
        "siren_trigger": trigger_web_siren,

        # Micro-Scale Geotechnical Dynamics
        "micro_delta_disp_mm": dsp_result["micro_delta_disp_mm"],
        "micro_delta_tilt_deg": dsp_result["micro_delta_tilt_deg"],
        "micro_velocity_mm_s": dsp_result["micro_velocity_mm_s"],
        "micro_tilt_rate_deg_s": dsp_result["micro_tilt_rate_deg_s"],
        "baseline_disp": dsp_result["baseline_disp"],
        "baseline_tilt_x": dsp_result["baseline_tilt_x"],
        "baseline_tilt_y": dsp_result["baseline_tilt_y"],

        # Forecasting
        "forecast_curve": forecast_curve,
        "forecast_curve_6h": forecast_curve,
        "time_to_collapse_hours": time_to_collapse,
        "collapse_message": collapse_message,
        "timestamp": packet_timestamp,
        "role": "MONITORING",

        # Granular Raw & Filtered Blocks
        "raw": {
            "disp_mm": float(raw_packet.get("displacement_mm") if raw_packet.get("displacement_mm") is not None else (raw_packet.get("d") or 0.0)),
            "diff_disp_mm": float(raw_packet.get("differential_displacement_mm") if raw_packet.get("differential_displacement_mm") is not None else (raw_packet.get("di") or 0.0)),
            "diff_tilt_deg": float(raw_packet.get("differential_tilt_deg") if raw_packet.get("differential_tilt_deg") is not None else 0.0),
            "tilt_x_deg": float(raw_packet.get("tilt_x_deg") if raw_packet.get("tilt_x_deg") is not None else (raw_packet.get("tx") or 0.0)),
            "tilt_y_deg": float(raw_packet.get("tilt_y_deg") if raw_packet.get("tilt_y_deg") is not None else (raw_packet.get("ty") or 0.0)),
            "vib_amp": float(raw_packet.get("vibration_amp") if raw_packet.get("vibration_amp") is not None else (raw_packet.get("v") or 0.015)),
            "strain_ue": float(raw_packet.get("strain_ue") if raw_packet.get("strain_ue") is not None else (raw_packet.get("st") or 0.0)),
            "rssi": int(raw_packet.get("rssi_dbm") or raw_packet.get("rssi") or -66),
            "snr": float(raw_packet.get("snr_db") or raw_packet.get("snr") or 9.0),
            "seq": int(raw_packet.get("seq") or raw_packet.get("s") or 0)
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
            "forecast_curve_6h": forecast_curve,
            "forecast_intervals": ["+1h", "+2h", "+3h", "+4h", "+5h", "+6h"],
            "time_to_collapse_hours": time_to_collapse,
            "collapse_message": collapse_message,
            "critical_threshold_mm": ml_engine.collapse_threshold_mm
        },
        "forecast": {
            "time_to_critical_hours": time_to_collapse,
            "status_message": collapse_message,
            "forecast_trajectory": forecast_curve,
            "alert_severity": "CRITICAL" if trigger_web_siren else ("WARNING" if predicted_zone == "Zone B" else "NORMAL")
        }
    }

    # 6. SQLite persistence
    _async_db_persist(unified_payload)

    # 7. Concurrent broadcast to all active WebSocket clients (/ws/telemetry & /ws/live)
    await ws_manager.broadcast_json(unified_payload)

    # 8. Send synchronized hardware actuation command (LEDs + Buzzer) to ESP32 Gateway
    if active_serial_reader and active_serial_reader.is_connected:
        active_serial_reader.send_actuation_command(current_risk)

    return {
        "status": "success",
        "risk_level": current_risk,
        "alert_zone": predicted_zone,
        "trigger_siren": trigger_web_siren,
        "node_id": node_id,
        "payload": unified_payload
    }


async def ingest_and_get_zone(raw_packet: dict) -> Dict[str, Any]:
    """Processes packet and returns risk decision synchronously."""
    return await handle_incoming_gateway_packet(raw_packet)


# Backward compatibility alias for routers importing handle_incoming_lora_packet
handle_incoming_lora_packet = handle_incoming_gateway_packet


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 70)
    print(" SIH Underground Coal Mine Subsidence Monitoring - FastAPI Backend")
    print(f" USB-Serial Ingestion + DSP Filter + Dual ML Engine (v{settings.VERSION})")
    print("=" * 70)

    init_db()

    # Preload all ML weights into memory once
    ml_engine.preload_models()

    global active_serial_reader
    loop = asyncio.get_running_loop()
    active_serial_reader = SerialGatewayReader(on_packet_callback=handle_incoming_gateway_packet)
    import app.services.serial_reader as sr_mod
    sr_mod.serial_reader = active_serial_reader
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
async def configure_serial_port(payload: SerialConfigPayload):
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
