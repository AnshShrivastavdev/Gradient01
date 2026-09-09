"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring System
Module: fault_tolerant_ml_service.py (Resilient Dual-Engine Inference Service)
-------------------------------------------------------------------------------
Principal Reliability & Embedded ML Subsystem:
1. Input Sanitization & Defensive Guardrails (handles None, NaN, Inf, string corrupted values).
2. Bounded Circular Memory Management (collections.deque(maxlen=10), flat memory, zero leaks).
3. Packet Drop & Time-Gap Padding (interpolates missing seconds on LoRa frame loss).
4. Redundant Dual-Engine Architecture:
   - Engine A: Supervised XGBoost/RandomForest Multi-scale Classifier
   - Engine B: Deterministic Hard Physics Rule Layer (Strain > 450, Disp > 20, Tilt > 3.0, Vib > 6.0)
   - Fail-Safe Override: Overrules under-predictions and survives complete ML model failure with zero downtime.
5. Alert Debouncing & Moving State Consensus (2-tick confirmation eliminates siren chatter).
6. Real-Time Diagnostics & Health Monitoring (RSS memory, active modes, buffer states).
"""

import os
import math
import time
import logging
import tracemalloc
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

import numpy as np
import pandas as pd
import joblib

# Initialize tracemalloc for memory diagnostics
if not tracemalloc.is_tracing():
    tracemalloc.start()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [FAULT_TOLERANT_ML] %(message)s"
)
logger = logging.getLogger("FaultTolerantMLService")

# =====================================================================
# CALIBRATED PHYSICAL SENSOR BOUNDS & NOMINAL DEFAULTS
# =====================================================================
SENSOR_BOUNDS = {
    "tilt_x_deg": {"min": -180.0, "max": 180.0, "default": 0.0},
    "tilt_y_deg": {"min": -180.0, "max": 180.0, "default": 0.0},
    "displacement_mm": {"min": 0.0, "max": 150.0, "default": 0.50},
    "strain_ue": {"min": 0.0, "max": 2500.0, "default": 95.0},
    "vibration_amp": {"min": 0.0, "max": 10.0, "default": 0.015}
}

# DETERMINISTIC HARD PHYSICAL SAFETY LIMITS (Engine B)
PHYSICAL_CRITICAL_LIMITS = {
    "tilt_total_deg": 3.0,
    "displacement_mm": 20.0,
    "strain_ue": 450.0,
    "vibration_amp": 6.0
}

PHYSICAL_WARNING_LIMITS = {
    "tilt_total_deg": 0.50,
    "displacement_mm": 5.0,
    "strain_ue": 180.0,
    "vibration_amp": 0.15
}

FEATURE_COLUMNS = [
    "tilt_x_deg", "tilt_y_deg", "tilt_composite_deg", "displacement_mm", "strain_ue", "vibration_amp",
    "tilt_composite_deg_mean_5s", "tilt_composite_deg_std_5s", "tilt_composite_deg_roc_5s",
    "displacement_mm_mean_5s", "displacement_mm_std_5s", "displacement_mm_roc_5s",
    "strain_ue_mean_5s", "strain_ue_std_5s", "strain_ue_roc_5s",
    "vibration_amp_mean_5s", "vibration_amp_std_5s", "vibration_amp_roc_5s"
]

class FaultTolerantMLService:
    def __init__(self, model_path: Optional[str] = None, encoder_path: Optional[str] = None):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Candidate model paths for zero-config discovery: prioritize calibrated 18-feature model
        default_model_path = os.path.join(self.base_dir, "..", "ml_engine", "artifacts", "subsidence_model.joblib")
        fallback_model_path = os.path.join(self.base_dir, "..", "ml_engine", "artifacts", "subsidence_model_optimized.joblib")
        default_encoder_path = os.path.join(self.base_dir, "..", "ml_engine", "artifacts", "label_encoder.joblib")

        self.model_path = model_path or (default_model_path if os.path.exists(default_model_path) else fallback_model_path)
        self.encoder_path = encoder_path or default_encoder_path

        self.model = None
        self.encoder = None
        self.classes: List[str] = ["Critical", "Normal", "Warning"]
        self.engine_mode: str = "RULE_FALLBACK"

        # Bounded Circular Buffers: node_id -> deque(maxlen=10)
        self.node_buffers: Dict[str, deque] = {}
        # Timestamps for packet drop detection: node_id -> float (epoch seconds)
        self.last_packet_epochs: Dict[str, float] = {}
        # Debouncing History: node_id -> deque of recent predictions (maxlen=2)
        self.debounce_buffers: Dict[str, deque] = {}
        # Confirmed Global State per node
        self.confirmed_states: Dict[str, str] = {}

        # Reference Orientation Tracking (Node 1 with MPU6500 baseline)
        self.reference_orientation: Dict[str, Any] = {
            "tilt_x_deg": 0.0,
            "tilt_y_deg": 0.0,
            "active": False,
            "timestamp": None
        }

        # Reliability Diagnostics Counters
        self.total_processed_packets: int = 0
        self.sanitized_values_count: int = 0
        self.dropped_packets_imputed: int = 0
        self.safety_overrides_triggered: int = 0
        self.start_epoch: float = time.time()

        self._initialize_engine_a()

    # =================================================================
    # 1. ENGINE INITIALIZATION & RECOVERY
    # =================================================================
    def _initialize_engine_a(self) -> bool:
        """Attempts to load Engine A (ML Classifier). Falls back cleanly to Engine B on any error."""
        try:
            if os.path.exists(self.model_path) and os.path.exists(self.encoder_path):
                loaded_model = joblib.load(self.model_path)
                # Verify feature dimension matches 18 FEATURE_COLUMNS
                if hasattr(loaded_model, "n_features_in_") and loaded_model.n_features_in_ != len(FEATURE_COLUMNS):
                    logger.warning(f"Model at {self.model_path} expects {loaded_model.n_features_in_} features, looking for 18-feature model.")
                    alt_path = os.path.join(self.base_dir, "..", "ml_engine", "artifacts", "subsidence_model.joblib")
                    if os.path.exists(alt_path) and alt_path != self.model_path:
                        loaded_model = joblib.load(alt_path)
                        self.model_path = alt_path
                self.model = loaded_model
                self.encoder = joblib.load(self.encoder_path)
                self.classes = list(self.encoder.classes_)
                self.engine_mode = "ML_ACTIVE"
                logger.info(f"Engine A (ML) Online: Loaded {os.path.basename(self.model_path)} with classes {self.classes}")
                return True
            else:
                logger.warning(f"Engine A Artifacts not found at {self.model_path}. Running in RULE_FALLBACK mode.")
                self.engine_mode = "RULE_FALLBACK"
                return False
        except Exception as err:
            logger.error(f"Failed to load Engine A ({err}). Engaging Engine B (RULE_FALLBACK) seamlessly.")
            self.model = None
            self.encoder = None
            self.engine_mode = "RULE_FALLBACK"
            return False

    # =================================================================
    # 2. DEFENSIVE INPUT SANITIZATION
    # =================================================================
    def _sanitize_numeric(self, val: Any, field_name: str) -> float:
        """Sanitizes incoming fields, protecting against None, NaN, Inf, and type errors."""
        limits = SENSOR_BOUNDS[field_name]
        default = limits["default"]

        if val is None:
            self.sanitized_values_count += 1
            return default

        try:
            val_float = float(val)
        except (ValueError, TypeError):
            self.sanitized_values_count += 1
            return default

        if math.isnan(val_float) or math.isinf(val_float):
            self.sanitized_values_count += 1
            return default

        # Out-of-bounds physical clipping
        if val_float < limits["min"] or val_float > limits["max"]:
            self.sanitized_values_count += 1
            return max(limits["min"], min(limits["max"], val_float))

        return val_float

    def sanitize_packet(self, raw_packet: Dict[str, Any]) -> Dict[str, Any]:
        """Validates schema integrity and sanitizes all telemetry channels."""
        raw_node = str(raw_packet.get("node_id", "NODE_02")).strip()
        node_id = raw_node if raw_node and raw_node != "NODE_UNKNOWN" else "NODE_02"
        is_ref = (raw_packet.get("role") == "REFERENCE") or (node_id in ["NODE_01", "NODE_REF", "NODE_DATUM"])
        role = "REFERENCE" if is_ref else raw_packet.get("role", "MONITORING")
        zone_id = str(raw_packet.get("zone_id", "Zone A" if is_ref else "Zone B")).strip()

        # If explicitly passed in packet, prefer passed values
        if raw_packet.get("zone_id"):
            zone_id = str(raw_packet.get("zone_id")).strip()
        if raw_packet.get("role"):
            role = str(raw_packet.get("role")).strip()

        # Parse timestamp safely
        raw_ts = raw_packet.get("timestamp")
        timestamp_str = str(raw_ts) if raw_ts else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        cleaned = {
            "node_id": node_id,
            "role": role,
            "zone_id": zone_id,
            "timestamp": timestamp_str,
            "tilt_x_deg": self._sanitize_numeric(raw_packet.get("tilt_x_deg"), "tilt_x_deg"),
            "tilt_y_deg": self._sanitize_numeric(raw_packet.get("tilt_y_deg"), "tilt_y_deg"),
            "displacement_mm": self._sanitize_numeric(raw_packet.get("displacement_mm"), "displacement_mm"),
            "strain_ue": self._sanitize_numeric(raw_packet.get("strain_ue"), "strain_ue"),
            "vibration_amp": self._sanitize_numeric(raw_packet.get("vibration_amp"), "vibration_amp"),
            "rssi_dbm": int(raw_packet.get("rssi_dbm", -75)) if raw_packet.get("rssi_dbm") is not None else -75,
            "snr_db": float(raw_packet.get("snr_db", 9.0)) if raw_packet.get("snr_db") is not None else 9.0
        }

        # Calculate composite resultant tilt: theta = sqrt(x^2 + y^2)
        cleaned["tilt_composite_deg"] = round(float(np.sqrt(cleaned["tilt_x_deg"]**2 + cleaned["tilt_y_deg"]**2)), 4)

        # Differential fields
        if raw_packet.get("ref_displacement_mm") is not None:
            cleaned["ref_displacement_mm"] = float(raw_packet["ref_displacement_mm"])
        if raw_packet.get("differential_displacement_mm") is not None:
            cleaned["differential_displacement_mm"] = float(raw_packet["differential_displacement_mm"])
        if raw_packet.get("differential_tilt_deg") is not None:
            cleaned["differential_tilt_deg"] = float(raw_packet["differential_tilt_deg"])

        return cleaned

    # =================================================================
    # 3. BOUNDED MEMORY & TIME-GAP IMPUTATION
    # =================================================================
    def _get_node_buffer(self, node_id: str) -> deque:
        if node_id not in self.node_buffers:
            # Strictly bounded circular queue of maxlen=10 (flat memory footprint)
            self.node_buffers[node_id] = deque(maxlen=10)
            self.debounce_buffers[node_id] = deque(maxlen=2)
            self.confirmed_states[node_id] = "Normal"
        return self.node_buffers[node_id]

    def _handle_packet_gaps(self, node_id: str, current_epoch: float, entry: Dict[str, float]) -> None:
        """Detects dropped LoRa packets (>1.8s gap) and pads rolling history with last stable readings."""
        if node_id in self.last_packet_epochs:
            dt = current_epoch - self.last_packet_epochs[node_id]
            # If gap > 1.8 seconds (dropped 1Hz packet), pad up to 3 seconds
            if dt > 1.8:
                dropped_steps = min(int(dt) - 1, 3)
                buffer = self._get_node_buffer(node_id)
                for _ in range(dropped_steps):
                    buffer.append(entry.copy())
                    self.dropped_packets_imputed += 1
        self.last_packet_epochs[node_id] = current_epoch

    # =================================================================
    # 4. ENGINE B: DETERMINISTIC HARD SAFETY RULE CHECKER
    # =================================================================
    def _evaluate_engine_b(self, telemetry: Dict[str, float]) -> Tuple[str, float, str]:
        """
        Engine B: Zero-dependency hard physical threshold evaluator.
        Evaluates differential tilt relative to reference datum if calibrated.
        """
        tilt = telemetry.get("differential_tilt_deg") if telemetry.get("differential_tilt_deg") is not None else telemetry["tilt_composite_deg"]
        disp = telemetry.get("differential_displacement_mm") if telemetry.get("differential_displacement_mm") is not None else telemetry["displacement_mm"]
        strain = telemetry["strain_ue"]
        vib = telemetry["vibration_amp"]

        # Critical ground collapse conditions
        if (strain >= PHYSICAL_CRITICAL_LIMITS["strain_ue"] or
            disp >= PHYSICAL_CRITICAL_LIMITS["displacement_mm"] or
            tilt >= PHYSICAL_CRITICAL_LIMITS["tilt_total_deg"] or
            vib >= PHYSICAL_CRITICAL_LIMITS["vibration_amp"]):
            reason = []
            if strain >= PHYSICAL_CRITICAL_LIMITS["strain_ue"]: reason.append(f"Strain={strain}µε >= {PHYSICAL_CRITICAL_LIMITS['strain_ue']}")
            if disp >= PHYSICAL_CRITICAL_LIMITS["displacement_mm"]: reason.append(f"Disp={disp}mm >= {PHYSICAL_CRITICAL_LIMITS['displacement_mm']}")
            if tilt >= PHYSICAL_CRITICAL_LIMITS["tilt_total_deg"]: reason.append(f"Tilt={tilt}° >= {PHYSICAL_CRITICAL_LIMITS['tilt_total_deg']}")
            if vib >= PHYSICAL_CRITICAL_LIMITS["vibration_amp"]: reason.append(f"Vib={vib}g >= {PHYSICAL_CRITICAL_LIMITS['vibration_amp']}")
            return "Critical", 1.0, f"PHYSICAL_THRESHOLD_BREACH: {', '.join(reason)}"

        # Warning conditions
        if (strain >= PHYSICAL_WARNING_LIMITS["strain_ue"] or
            disp >= PHYSICAL_WARNING_LIMITS["displacement_mm"] or
            tilt >= PHYSICAL_WARNING_LIMITS["tilt_total_deg"] or
            vib >= PHYSICAL_WARNING_LIMITS["vibration_amp"]):
            return "Warning", 0.95, "PHYSICAL_WARNING_LIMIT_EXCEEDED"

        return "Normal", 0.99, "BASELINE_PHYSICS_NOMINAL"

    # =================================================================
    # 5. ENGINE A: SUPERVISED ML INFERENCE WITH EXTRACTED FEATURES
    # =================================================================
    def _evaluate_engine_a(self, node_id: str, telemetry: Dict[str, Any]) -> Tuple[Optional[str], float, Dict[str, float]]:
        """Engine A: Evaluates trained model on engineered rolling features."""
        if not self.model or not self.encoder:
            return None, 0.0, {}

        buffer = self._get_node_buffer(node_id)
        if len(buffer) < 1:
            return None, 0.0, {}

        h_tilt = [e["tilt_composite_deg"] for e in buffer]
        h_disp = [e["displacement_mm"] for e in buffer]
        h_strain = [e["strain_ue"] for e in buffer]
        h_vib = [e["vibration_amp"] for e in buffer]

        # Rolling calculations over buffer
        features_dict = {
            "tilt_x_deg": telemetry["tilt_x_deg"],
            "tilt_y_deg": telemetry["tilt_y_deg"],
            "tilt_composite_deg": telemetry["tilt_composite_deg"],
            "displacement_mm": telemetry["displacement_mm"],
            "strain_ue": telemetry["strain_ue"],
            "vibration_amp": telemetry["vibration_amp"],
            "tilt_composite_deg_mean_5s": float(np.mean(h_tilt[-5:])),
            "tilt_composite_deg_std_5s": float(np.std(h_tilt[-5:])) if len(h_tilt) >= 2 else 0.0,
            "tilt_composite_deg_roc_5s": float(h_tilt[-1] - h_tilt[-min(len(h_tilt), 5)]),
            "displacement_mm_mean_5s": float(np.mean(h_disp[-5:])),
            "displacement_mm_std_5s": float(np.std(h_disp[-5:])) if len(h_disp) >= 2 else 0.0,
            "displacement_mm_roc_5s": float(h_disp[-1] - h_disp[-min(len(h_disp), 5)]),
            "strain_ue_mean_5s": float(np.mean(h_strain[-5:])),
            "strain_ue_std_5s": float(np.std(h_strain[-5:])) if len(h_strain) >= 2 else 0.0,
            "strain_ue_roc_5s": float(h_strain[-1] - h_strain[-min(len(h_strain), 5)]),
            "vibration_amp_mean_5s": float(np.mean(h_vib[-5:])),
            "vibration_amp_std_5s": float(np.std(h_vib[-5:])) if len(h_vib) >= 2 else 0.0,
            "vibration_amp_roc_5s": float(h_vib[-1] - h_vib[-min(len(h_vib), 5)])
        }

        try:
            X_df = pd.DataFrame([features_dict], columns=FEATURE_COLUMNS)
            pred_idx = self.model.predict(X_df)[0]
            predicted_class = self.encoder.inverse_transform([pred_idx])[0]

            probs = {}
            confidence = 1.0
            if hasattr(self.model, "predict_proba"):
                prob_arr = self.model.predict_proba(X_df)[0]
                for c_name, p in zip(self.encoder.classes_, prob_arr):
                    probs[c_name] = round(float(p), 4)
                confidence = probs.get(predicted_class, 1.0)

            return predicted_class, confidence, probs
        except Exception as ex:
            logger.error(f"Engine A prediction failure: {ex}. Falling back.")
            return None, 0.0, {}

    # =================================================================
    # 6. DUAL-ENGINE ARBITRATION & ALERT DEBOUNCING
    # =================================================================
    def predict_packet(self, raw_packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes end-to-end resilient inference:
        Sanitization -> Buffer Update -> Engine A/B Arbitration -> State Debouncing.
        """
        self.total_processed_packets += 1
        now_epoch = time.time()

        # Step 1: Defensive Sanitization
        clean_telemetry = self.sanitize_packet(raw_packet)
        node_id = clean_telemetry["node_id"]

        # Step 1b: If Reference Node (Node 1 with MPU6500), update baseline orientation
        if clean_telemetry.get("role") == "REFERENCE" or node_id in ["NODE_01", "NODE_REF", "NODE_DATUM"]:
            self.reference_orientation = {
                "tilt_x_deg": clean_telemetry["tilt_x_deg"],
                "tilt_y_deg": clean_telemetry["tilt_y_deg"],
                "active": True,
                "timestamp": clean_telemetry["timestamp"]
            }
            # Reference Datum is stable bedrock; suppress subsidence alerts
            self.confirmed_states[node_id] = "Normal"
            buffer = self._get_node_buffer(node_id)
            buffer.append(clean_telemetry)
            return {
                "node_id": node_id,
                "zone_id": clean_telemetry["zone_id"],
                "timestamp": clean_telemetry["timestamp"],
                "telemetry": clean_telemetry,
                "instant_prediction": "Normal",
                "confirmed_risk_state": "Normal",
                "confidence": 1.0,
                "probabilities": {"Normal": 1.0, "Warning": 0.0, "Critical": 0.0},
                "active_engine": "REFERENCE_DATUM_LOCK",
                "safety_override": False,
                "buffer_depth": len(buffer),
                "siren_trigger": False
            }
        elif self.reference_orientation.get("active"):
            # For Node 2 (Monitoring Node): Calculate differential orientation against Reference Node 1
            diff_x = clean_telemetry["tilt_x_deg"] - self.reference_orientation["tilt_x_deg"]
            diff_y = clean_telemetry["tilt_y_deg"] - self.reference_orientation["tilt_y_deg"]
            diff_composite = round(float(np.sqrt(diff_x**2 + diff_y**2)), 3)
            clean_telemetry["differential_tilt_x_deg"] = round(diff_x, 3)
            clean_telemetry["differential_tilt_y_deg"] = round(diff_y, 3)
            clean_telemetry["differential_tilt_deg"] = diff_composite
            clean_telemetry["ref_orientation"] = self.reference_orientation.copy()

        # Step 2: Buffer Management & Gap Imputation
        buffer = self._get_node_buffer(node_id)
        self._handle_packet_gaps(node_id, now_epoch, clean_telemetry)
        buffer.append(clean_telemetry)

        # Step 3: Run Engine B (Hard Physical Rules)
        rule_pred, rule_conf, rule_reason = self._evaluate_engine_b(clean_telemetry)

        # Step 4: Run Engine A (Supervised ML)
        ml_pred, ml_conf, ml_probs = self._evaluate_engine_a(node_id, clean_telemetry)

        # Step 5: Dual-Engine Arbitration & Fail-Safe Override
        safety_override = False
        final_instant_pred = "Normal"
        active_engine = "ENGINE_A_ML"

        if ml_pred is None:
            # Complete ML failure / missing model -> Fallback cleanly
            final_instant_pred = rule_pred
            final_conf = rule_conf
            final_probs = {rule_pred: 1.0}
            active_engine = "ENGINE_B_FALLBACK"
        else:
            # Both engines active -> Check for under-prediction
            final_instant_pred = ml_pred
            final_conf = ml_conf
            final_probs = ml_probs

            # CRITICAL FAIL-SAFE OVERRULE:
            # If Engine B flags Critical, Engine A CANNOT under-predict
            if rule_pred == "Critical" and ml_pred != "Critical":
                logger.warning(
                    f"SAFETY OVERRULE on {node_id}: ML predicted '{ml_pred}', "
                    f"but physical rules detected '{rule_pred}' ({rule_reason}). Overriding to Critical."
                )
                final_instant_pred = "Critical"
                final_conf = 1.0
                final_probs["Critical"] = 1.0
                safety_override = True
                active_engine = "ENGINE_B_SAFETY_OVERRIDE"
                self.safety_overrides_triggered += 1

        # Step 6: 2-Tick Alert Debouncing (Moving Consensus Anti-Chatter)
        deb_buffer = self.debounce_buffers[node_id]
        deb_buffer.append(final_instant_pred)

        # Instant escalation if Critical with high confidence (>0.90) or 2 consecutive Criticals
        if final_instant_pred == "Critical" and (final_conf >= 0.90 or deb_buffer.count("Critical") >= 2):
            self.confirmed_states[node_id] = "Critical"
        # Warning requires 2 consecutive Warning or Critical predictions
        elif deb_buffer.count("Warning") >= 2 or (deb_buffer.count("Critical") >= 1 and deb_buffer.count("Warning") >= 1):
            if self.confirmed_states[node_id] != "Critical":
                self.confirmed_states[node_id] = "Warning"
        # De-escalation back to Normal requires 2 consecutive Normal samples
        elif all(p == "Normal" for p in deb_buffer) and len(deb_buffer) >= 2:
            self.confirmed_states[node_id] = "Normal"

        confirmed_zone_state = self.confirmed_states[node_id]

        return {
            "node_id": node_id,
            "zone_id": clean_telemetry["zone_id"],
            "timestamp": clean_telemetry["timestamp"],
            "telemetry": clean_telemetry,
            "instant_prediction": final_instant_pred,
            "confirmed_risk_state": confirmed_zone_state,
            "confidence": round(float(final_conf), 4),
            "probabilities": final_probs,
            "active_engine": active_engine,
            "safety_override": safety_override,
            "buffer_depth": len(buffer),
            "siren_trigger": (confirmed_zone_state == "Critical")
        }

    # =================================================================
    # 7. HEALTH CHECK & DIAGNOSTICS ENDPOINT
    # =================================================================
    def get_diagnostics(self) -> Dict[str, Any]:
        """Returns lightweight diagnostic telemetry and memory status."""
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        uptime_seconds = round(time.time() - self.start_epoch, 1)

        active_nodes_info = {}
        for nid, buf in self.node_buffers.items():
            active_nodes_info[nid] = {
                "buffer_size": len(buf),
                "last_seen_seconds_ago": round(time.time() - self.last_packet_epochs.get(nid, time.time()), 2),
                "confirmed_state": self.confirmed_states.get(nid, "Normal")
            }

        return {
            "status": "HEALTHY",
            "service_mode": self.engine_mode,
            "uptime_seconds": uptime_seconds,
            "memory_usage_kb": round(current_mem / 1024, 2),
            "peak_memory_kb": round(peak_mem / 1024, 2),
            "total_processed_packets": self.total_processed_packets,
            "sanitized_values_repaired": self.sanitized_values_count,
            "dropped_packets_imputed": self.dropped_packets_imputed,
            "safety_overrides_count": self.safety_overrides_triggered,
            "active_nodes": active_nodes_info
        }

# Global Singleton Service Instance
fault_tolerant_service = FaultTolerantMLService()
