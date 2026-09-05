from pydantic import BaseModel, Field
from typing import Optional, Dict

class RawSensorPacket(BaseModel):
    node_id: str = Field(..., example="NODE_A1")
    zone_id: Optional[str] = Field("Zone A", example="Zone A")
    timestamp: Optional[str] = None
    tilt_x_deg: float = Field(..., example=0.02)
    tilt_y_deg: float = Field(..., example=-0.01)
    displacement_mm: float = Field(..., example=0.45)
    strain_ue: float = Field(..., example=92.5)
    vibration_amp: float = Field(..., example=0.015)
    shock_count: Optional[int] = 0

class EnrichedTelemetryResponse(BaseModel):
    id: Optional[int] = None
    timestamp: str
    node_id: str
    zone_id: str
    tilt_x_deg: float
    tilt_y_deg: float
    tilt_composite_deg: float
    displacement_mm: float
    strain_ue: float
    vibration_amp: float
    predicted_risk: str # Normal, Warning, Critical
    confidence: float
    probabilities: Dict[str, float]
    hazard_status: str
    action_required: str
