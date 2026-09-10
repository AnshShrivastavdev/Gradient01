from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.db import SessionLocal
from app.database.crud import get_latest_telemetry, get_telemetry_by_node
from app.services.fault_tolerant_ml_service import fault_tolerant_service
from app.services.forecast_service import forecast_service
from app.models.sensor_data import RawSensorPacket

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/latest")
def fetch_latest(limit: int = 50, db: Session = Depends(get_db)):
    return get_latest_telemetry(db, limit=limit)

@router.get("/node/{node_id}")
def fetch_by_node(node_id: str, limit: int = 50, db: Session = Depends(get_db)):
    return get_telemetry_by_node(db, node_id, limit=limit)

@router.post("/predict")
def predict_instant(packet: RawSensorPacket):
    """Executes robust fault-tolerant inference with dual-engine fallback."""
    result = fault_tolerant_service.predict_packet(packet.model_dump())
    forecast_service.record_reading(result["node_id"], result["telemetry"]["displacement_mm"])

    return {
        "node_id": result["node_id"],
        "predicted_risk": result["instant_prediction"],
        "confirmed_risk_state": result["confirmed_risk_state"],
        "confidence": result["confidence"],
        "probabilities": result["probabilities"],
        "active_engine": result["active_engine"],
        "safety_override": result["safety_override"],
        "siren_trigger": result["siren_trigger"]
    }

@router.post("/ingest")
async def ingest_wifi_telemetry(packet: dict):
    """
    Direct HTTP POST ingestion endpoint for ESP32 Gateway transmitting over WiFi.
    Feeds real-time sensor packets directly into in-memory DSP, micro-dynamics, ML engine,
    and concurrent WebSocket broadcaster (< 15 ms total response time).
    Returns synchronized hardware risk level (SAFE, WARNING, CRITICAL) to actuate LEDs and buzzer.
    """
    from app.main import ingest_and_get_zone

    result = await ingest_and_get_zone(packet)
    risk_level = result.get("risk_level") or ("CRITICAL" if result.get("alert_zone") == "Zone C" else "WARNING" if result.get("alert_zone") == "Zone B" else "SAFE")

    return {
        "status": "success",
        "ack": True,
        "risk_level": risk_level,
        "node_id": result.get("node_id") or packet.get("node_id", "NODE_02"),
        "alert_zone": result.get("alert_zone", "Zone A"),
        "trigger_siren": result.get("trigger_siren", False),
        "server_timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.post("/tare")
def tare_baseline(node_id: str = "NODE_02", disp: Optional[float] = None,
                  tilt_x: Optional[float] = None, tilt_y: Optional[float] = None):
    """
    Resets/re-zeros the baseline datum for high-precision micro-scale tracking.
    """
    from app.services.dsp_filter import dsp_processor
    from app.services.ml_engine import ml_engine
    result = dsp_processor.tare(node_id=node_id, disp=disp, tilt_x=tilt_x, tilt_y=tilt_y)
    ml_engine.reset_node(node_id=node_id)
    return result

@router.get("/tare/{node_id}")
def get_tare_status(node_id: str = "NODE_02"):
    """
    Returns the active baseline datum calibration for the requested node.
    """
    from app.services.dsp_filter import dsp_processor
    return dsp_processor.get_baseline(node_id=node_id)

@router.get("/forecast/{node_id}")
def get_node_forecast(node_id: str, threshold: float = Query(35.0, description="Critical threshold in mm")):
    """
    Returns multi-step 6-hour displacement forecast trajectory and Time-to-Failure (TTF).
    """
    forecast_service.critical_threshold_mm = threshold
    return forecast_service.predict_future_trajectory(node_id)

@router.get("/diagnostics")
def get_service_diagnostics():
    """Health check endpoint returning memory footprint, buffer states, and operational mode."""
    return fault_tolerant_service.get_diagnostics()

@router.get("/gateway-status")
def get_gateway_status():
    """Returns the live connection state of the hardware ESP32 LoRa central gateway."""
    from app.services.serial_reader import get_global_gateway_reader
    reader = get_global_gateway_reader()
    if not reader:
        raise HTTPException(status_code=503, detail="Gateway reader service not initialized")
    return reader.get_status()

@router.get("/gateway-ports")
def get_detected_com_ports():
    """Lists all available USB serial ports on host for ESP32 connection."""
    from app.services.serial_reader import get_global_gateway_reader
    reader = get_global_gateway_reader()
    if not reader:
        raise HTTPException(status_code=503, detail="Gateway reader service not initialized")
    return {"ports": reader.list_available_com_ports()}

@router.post("/gateway-switch-mode")
async def switch_gateway_mode(mode: str = Query(..., description="'HARDWARE_SERIAL' or 'SIMULATION'"),
                              port: Optional[str] = Query(None, description="Optional COM port name")):
    """Switches telemetry stream between physical ESP32 LoRa hardware and simulation."""
    from app.services.serial_reader import get_global_gateway_reader
    reader = get_global_gateway_reader()
    if not reader:
        raise HTTPException(status_code=503, detail="Gateway reader service not initialized")
    if mode == "HARDWARE_SERIAL":
        reader.set_mode(False, port)
    else:
        reader.set_mode(True, port)
    return {
        "status": "SUCCESS",
        "active_mode": mode,
        "current_mode": mode,
        "port": reader.connected_port
    }
