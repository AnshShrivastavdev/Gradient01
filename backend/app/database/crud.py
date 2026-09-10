import datetime
from sqlalchemy.orm import Session
from app.database.db import SensorRecord

def save_telemetry(db: Session, data: dict):
    rec = SensorRecord(
        timestamp=data.get("timestamp") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        node_id=data.get("node_id", "NODE_02"),
        zone_id=data.get("zone_id", "Zone B"),
        tilt_x_deg=float(data.get("tilt_x_deg") or 0.0),
        tilt_y_deg=float(data.get("tilt_y_deg") or 0.0),
        tilt_composite_deg=float(data.get("tilt_composite_deg") or 0.0),
        displacement_mm=float(data.get("displacement_mm") or 0.0),
        strain_ue=float(data.get("strain_ue") or 0.0),
        vibration_amp=float(data.get("vibration_amp") or 0.0),
        predicted_risk=data.get("predicted_risk", "Normal"),
        confidence=float(data.get("confidence") or 100.0)
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec

def get_latest_telemetry(db: Session, limit: int = 100):
    return db.query(SensorRecord).order_by(SensorRecord.id.desc()).limit(limit).all()

def get_telemetry_by_node(db: Session, node_id: str, limit: int = 100):
    return db.query(SensorRecord).filter(SensorRecord.node_id == node_id).order_by(SensorRecord.id.desc()).limit(limit).all()
