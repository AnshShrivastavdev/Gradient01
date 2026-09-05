import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.db import init_db, SessionLocal
from app.database.crud import save_telemetry
from app.services.serial_reader import SerialGatewayReader
from app.services.fault_tolerant_ml_service import fault_tolerant_service
from app.services.forecast_service import forecast_service
from app.services.alert_service import alert_service
from app.routers import telemetry, websocket
from app.routers.websocket import ws_manager

gateway_reader = None

async def handle_incoming_lora_packet(packet: dict):
    # 1. Run fault-tolerant dual-engine inference with automatic sanitization
    ft_result = fault_tolerant_service.predict_packet(packet)
    clean_tel = ft_result["telemetry"]
    node_id = ft_result["node_id"]

    # 2. Update multi-step displacement lookback buffer & generate 6-hour forecast
    forecast_service.record_reading(node_id, clean_tel["displacement_mm"])
    forecast_payload = forecast_service.predict_future_trajectory(node_id)

    # 3. Enrich telemetry object with live forecast & Time-to-Failure (TTF)
    enriched = {
        "timestamp": clean_tel["timestamp"],
        "node_id": node_id,
        "zone_id": ft_result["zone_id"],
        "tilt_x_deg": clean_tel["tilt_x_deg"],
        "tilt_y_deg": clean_tel["tilt_y_deg"],
        "tilt_composite_deg": clean_tel["tilt_composite_deg"],
        "displacement_mm": clean_tel["displacement_mm"],
        "strain_ue": clean_tel["strain_ue"],
        "vibration_amp": clean_tel["vibration_amp"],
        "predicted_risk": ft_result["confirmed_risk_state"],
        "instant_prediction": ft_result["instant_prediction"],
        "confidence": ft_result["confidence"],
        "probabilities": ft_result["probabilities"],
        "active_engine": ft_result["active_engine"],
        "safety_override": ft_result["safety_override"],
        "siren_trigger": ft_result["siren_trigger"],
        "rssi_dbm": clean_tel["rssi_dbm"],
        "snr_db": clean_tel["snr_db"],
        # Deep Learning Forecast & TTF Early Warning
        "forecast": {
            "time_to_critical_hours": forecast_payload["time_to_critical_hours"],
            "status_message": forecast_payload["status_message"],
            "forecast_trajectory": forecast_payload["forecast_trajectory"],
            "hourly_intervals": forecast_payload["hourly_intervals"],
            "alert_severity": forecast_payload["alert_severity"]
        }
    }

    # 4. Check for threshold breach / auto-siren
    alerts = alert_service.evaluate_and_dispatch(enriched)
    enriched["alerts"] = [a.model_dump() for a in alerts]

    # 5. Save to Database
    try:
        db = SessionLocal()
        save_telemetry(db, enriched)
        db.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")

    # 6. Broadcast to connected Frontend WebSocket clients
    await ws_manager.broadcast_json(enriched)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print(" SIH Underground Coal Mine Monitoring - FastAPI Service Starting")
    print("=" * 60)
    init_db()

    global gateway_reader
    gateway_reader = SerialGatewayReader(on_packet_callback=handle_incoming_lora_packet)
    from app.services.serial_reader import set_global_gateway_reader
    set_global_gateway_reader(gateway_reader)
    await gateway_reader.start()

    yield

    print("[SHUTDOWN] Stopping telemetry ingestion...")
    if gateway_reader:
        await gateway_reader.stop()

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

app.include_router(telemetry.router, prefix=settings.API_V1_STR)
app.include_router(websocket.router)

@app.get("/")
def health_check():
    diag = fault_tolerant_service.get_diagnostics()
    return {
        "status": "ONLINE",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "mode": "SIMULATION" if settings.SIMULATION_MODE else "HARDWARE_UART",
        "ml_engine_mode": diag["service_mode"],
        "total_packets": diag["total_processed_packets"],
        "memory_usage_kb": diag["memory_usage_kb"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
