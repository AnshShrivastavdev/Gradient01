from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
from app.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SensorRecord(Base):
    __tablename__ = "sensor_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String, default=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    node_id = Column(String, index=True)
    zone_id = Column(String, index=True)
    tilt_x_deg = Column(Float)
    tilt_y_deg = Column(Float)
    tilt_composite_deg = Column(Float)
    displacement_mm = Column(Float)
    strain_ue = Column(Float)
    vibration_amp = Column(Float)
    predicted_risk = Column(String, index=True)
    confidence = Column(Float)

def init_db():
    Base.metadata.create_all(bind=engine)
