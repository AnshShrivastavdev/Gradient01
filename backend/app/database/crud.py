from sqlalchemy.orm import Session
from app.database.db import SensorRecord

def save_telemetry(db: Session, data: dict):
    rec = SensorRecord(
        timestamp=data["timestamp"],
        node_id=data["node_id"],
        zone_id=data["zone_id"],
        tilt_x_deg=data["tilt_x_deg"],
        tilt_y_deg=data["tilt_y_deg"],
        tilt_composite_deg=data["tilt_composite_deg"],
        displacement_mm=data["displacement_mm"],
        strain_ue=data["strain_ue"],
        vibration_amp=data["vibration_amp"],
        predicted_risk=data["predicted_risk"],
        confidence=data["confidence"]
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec

def get_latest_telemetry(db: Session, limit: int = 100):
    return db.query(SensorRecord).order_by(SensorRecord.id.desc()).limit(limit).all()

def get_telemetry_by_node(db: Session, node_id: str, limit: int = 100):
    return db.query(SensorRecord).filter(SensorRecord.node_id == node_id).order_by(SensorRecord.id.desc()).limit(limit).all()
