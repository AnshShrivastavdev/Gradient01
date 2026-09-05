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
    # Also record displacement reading for the deep forecasting engine
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
    Feeds real-time sensor packets directly into the ML service, forecaster, and WebSocket stream.
    """
    from app.main import handle_incoming_lora_packet
    import time
    await handle_incoming_lora_packet(packet)
    return {"status": "ACK", "node_id": packet.get("node_id"), "server_timestamp": time.time()}

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
    return await reader.switch_mode(mode, port=port)

