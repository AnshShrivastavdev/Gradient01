import datetime
from app.models.alert import AlertEvent
from app.config import settings

class AlertDispatchService:
    def __init__(self):
        self.active_alerts = []

    def evaluate_and_dispatch(self, telemetry: dict) -> list[AlertEvent]:
        new_alerts = []
        node_id = telemetry["node_id"]
        zone_id = telemetry["zone_id"]
        risk = telemetry["predicted_risk"]
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if risk == "Critical":
            alert = AlertEvent(
                timestamp=now_str,
                node_id=node_id,
                zone_id=zone_id,
                severity="CRITICAL",
                alert_type="CRITICAL_SUBSIDENCE_COLLAPSE",
                message=f"CRITICAL HAZARD in {zone_id} ({node_id})! Strain={telemetry['strain_ue']}ue, Disp={telemetry['displacement_mm']}mm. Triggering auto siren.",
                evacuation_siren_triggered=True
            )
            new_alerts.append(alert)
            self.active_alerts.append(alert)
            print(f"\n[!] [SIREN_TRIGGERED] {alert.message}\n")

        elif risk == "Warning":
            alert = AlertEvent(
                timestamp=now_str,
                node_id=node_id,
                zone_id=zone_id,
                severity="CAUTION",
                alert_type="SEISMIC_TREMOR_WARNING",
                message=f"Caution: Elevated ground movement in {zone_id} ({node_id}). Strain={telemetry['strain_ue']}ue.",
                evacuation_siren_triggered=False
            )
            new_alerts.append(alert)
            self.active_alerts.append(alert)

        return new_alerts

alert_service = AlertDispatchService()
