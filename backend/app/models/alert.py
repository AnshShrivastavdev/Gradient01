from pydantic import BaseModel
from typing import Optional

class AlertEvent(BaseModel):
    id: Optional[int] = None
    timestamp: str
    node_id: str
    zone_id: str
    severity: str # CAUTION | CRITICAL
    alert_type: str # ROOF_SAG_EXCEEDED | STRAIN_YIELD_LIMIT | HIGH_TILT | SEISMIC_SHOCK
    message: str
    is_active: bool = True
    evacuation_siren_triggered: bool = False
