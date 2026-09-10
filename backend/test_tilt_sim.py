from app.services.dsp_filter import DigitalSignalProcessor
from app.services.ml_engine import SubsidenceMLEngine
import time

dsp = DigitalSignalProcessor()
ml = SubsidenceMLEngine()

# 12 warmup packets at rest
for i in range(12):
    pkt = {'node_id': 'NODE_02', 'displacement_mm': 6.0, 'tilt_x_deg': 1.9, 'tilt_y_deg': -6.5, 'vibration_amp': 1.5, 'strain_ue': 0.0}
    dsp_res = dsp.process(pkt)
    ml_res = ml.evaluate(pkt, dsp_res)

print("Baseline tared. At rest zone:", ml_res['predicted_zone'])

print("\n--- Deflecting: tilt_y = -1.5 (5 deg deflection) ---")
for i in range(15):
    pkt = {'node_id': 'NODE_02', 'displacement_mm': 6.0, 'tilt_x_deg': 1.9, 'tilt_y_deg': -1.5, 'vibration_amp': 1.5, 'strain_ue': 0.0}
    dsp_res = dsp.process(pkt)
    ml_res = ml.evaluate(pkt, dsp_res)
    print(f"Pkt {i:02d}: delta_tilt={dsp_res['micro_delta_tilt_deg']:.2f} | tilt_rate={dsp_res['micro_tilt_rate_deg_s']:.2f} | zone={ml_res['predicted_zone']} | siren={ml_res['trigger_web_siren']}")
    time.sleep(0.1)
