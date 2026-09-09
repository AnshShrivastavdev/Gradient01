from pydantic import BaseModel, Field
from typing import Optional, Dict

class RawSensorPacket(BaseModel):
    node_id: str = Field(..., example="NODE_02")
    role: Optional[str] = Field("MONITORING", example="MONITORING")
    zone_id: Optional[str] = Field("Zone B", example="Zone B")
    timestamp: Optional[str] = None
    tilt_x_deg: float = Field(..., example=0.95)
    tilt_y_deg: float = Field(..., example=0.70)
    displacement_mm: float = Field(..., example=7.50)
    strain_ue: float = Field(..., example=240.0)
    vibration_amp: float = Field(..., example=0.180)
    shock_count: Optional[int] = 0
    ref_displacement_mm: Optional[float] = None
    differential_displacement_mm: Optional[float] = None
    differential_tilt_deg: Optional[float] = None

class EnrichedTelemetryResponse(BaseModel):
    id: Optional[int] = None
    timestamp: str
    node_id: str
    role: Optional[str] = "MONITORING"
    zone_id: str
    tilt_x_deg: float
    tilt_y_deg: float
    tilt_composite_deg: float
    displacement_mm: float
    ref_displacement_mm: Optional[float] = None
    differential_displacement_mm: Optional[float] = None
    differential_tilt_deg: Optional[float] = None
    strain_ue: float
    vibration_amp: float
    predicted_risk: str # Normal, Warning, Critical
    confidence: float
    probabilities: Dict[str, float]
    hazard_status: str
    action_required: str

