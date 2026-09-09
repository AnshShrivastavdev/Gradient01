"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring System
Module: serial_listener.py (Resilient USB-Serial Telemetry Stream Ingestion)
----------------------------------------------------------------------------
Maintains an asynchronous / threaded serial worker interfacing with the ESP32 Gateway:
1. Automated COM port discovery (CH340, CP210x, FTDI, Silicon Labs, ESP32 USB-UART bridges).
2. Non-blocking threaded read loop with threadsafe asyncio event dispatching.
3. Reconnection resilience against port locks (PlatformIO monitor conflict) & momentary disconnects.
4. Robust JSON sanitization, boundary extraction, and multi-format key normalization.
5. High-fidelity synthetic fallback mode for testbeds when physical hardware is unplugged.
"""

import os
import sys
import time
import json
import math
import random
import logging
import asyncio
import threading
from datetime import datetime, timezone
from typing import Optional, Callable, Dict, Any, List

import serial
import serial.tools.list_ports
from app.config import settings

logger = logging.getLogger("SerialListener")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [SERIAL] %(message)s")


ESP32_PORT_KEYWORDS = [
    "ch340", "ch341", "cp210", "cp2102", "cp2104", "cp2108",
    "ftdi", "usb-serial", "esp32", "silicon labs", "uart", "prolific",
    "wchusb", "qinheng"
]


class SerialListener:
    def __init__(self, on_packet_callback: Optional[Callable[[Dict[str, Any]], Any]] = None):
        """
        Initializes the serial telemetry listener.
        :param on_packet_callback: Async or sync callback invoked when a valid telemetry packet is decoded.
        """
        self.on_packet_callback = on_packet_callback
        self.running: bool = False
        self.serial_conn: Optional[serial.Serial] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        # State tracking
        self.connected_port: Optional[str] = None
        self.is_connected: bool = False
        self.packets_received: int = 0
        self.parse_errors: int = 0
        self.last_packet_time: Optional[str] = None
        self.last_error_message: Optional[str] = None
        self.gateway_info: Dict[str, Any] = {
            "gateway_id": "GATEWAY_ESP32_SURFACE",
            "baud_rate": settings.BAUD_RATE,
            "status": "INITIALIZING"
        }

    @staticmethod
    def detect_available_ports() -> List[Dict[str, Any]]:
        """
        Scans all physical and virtual COM ports on the host system.
        Marks ports that match known ESP32 USB-to-UART bridge controllers.
        """
        detected = []
        try:
            ports = serial.tools.list_ports.comports()
            for p in ports:
                desc = (p.description or "").lower()
                hwid = (p.hwid or "").lower()
                is_esp = any(k in desc or k in hwid for k in ESP32_PORT_KEYWORDS)
                detected.append({
                    "port": p.device,
                    "description": p.description,
                    "hwid": p.hwid,
                    "is_likely_esp32": is_esp
                })
        except Exception as ex:
            logger.error(f"Error enumerating COM ports: {ex}")
        return detected

    def _resolve_target_port(self) -> Optional[str]:
        """
        Determines the target COM port to connect to.
        Supports explicit config (e.g. 'COM3', '/dev/ttyUSB0') and 'AUTO' scanning.
        """
        cfg_port = settings.SERIAL_PORT.strip() if settings.SERIAL_PORT else ""

        # If explicitly disabled
        if cfg_port.upper() in ["NONE", "DISABLED", "OFF"]:
            return None

        # If user specified a concrete port, verify its presence
        available = self.detect_available_ports()
        avail_names = [p["port"] for p in available]

        if cfg_port and cfg_port.upper() != "AUTO":
            if cfg_port in avail_names:
                return cfg_port
            # If not in list, might still try if on Windows
            return cfg_port

        # Auto-detect: prioritize ports matching ESP32 keywords
        for p in available:
            if p["is_likely_esp32"]:
                return p["port"]

        # If any port exists at all, take the first one
        if available:
            return available[0]["port"]

        return None

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Starts the background reading thread."""
        if self.running:
            return

        self.running = True
        self.loop = loop or asyncio.get_event_loop()
        self.worker_thread = threading.Thread(target=self._run_thread, daemon=True, name="ESP32-SerialListener")
        self.worker_thread.start()
        logger.info(f"Background Serial Listener started. Configured Port: {settings.SERIAL_PORT} @ {settings.BAUD_RATE} baud.")

    def stop(self):
        """Stops reading and cleanly releases COM port resources."""
        self.running = False
        self._close_serial()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.5)
        self.is_connected = False
        self.connected_port = None
        self.gateway_info["status"] = "STOPPED"
        logger.info("Serial Listener stopped and port released.")

    def _close_serial(self):
        """Safely closes active serial connection."""
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
            self.serial_conn = None
        self.is_connected = False
        self.connected_port = None

    def _run_thread(self):
        """Dedicated thread loop for serial I/O."""
        reconnect_delay = 2.0

        while self.running:
            # 1. Handle Simulation Mode if explicitly enabled or port disabled
            if settings.SIMULATION_MODE or (settings.SERIAL_PORT and settings.SERIAL_PORT.upper() in ["NONE", "DISABLED"]):
                self.gateway_info["status"] = "SIMULATION_MODE"
                self._emit_synthetic_tick()
                time.sleep(1.0)
                continue

            # 2. Reconnect if port not currently open
            if not self.serial_conn or not self.serial_conn.is_open:
                target_port = self._resolve_target_port()
                if not target_port:
                    self.gateway_info["status"] = "NO_COM_PORT_DETECTED"
                    self.last_error_message = "No USB-Serial device found. Streaming live fallback telemetry..."
                    self._emit_synthetic_tick()
                    time.sleep(reconnect_delay)
                    continue

                try:
                    logger.info(f"Opening Serial port '{target_port}' @ {settings.BAUD_RATE} baud...")
                    self.serial_conn = serial.Serial(
                        port=target_port,
                        baudrate=settings.BAUD_RATE,
                        timeout=0.2,
                        write_timeout=1.0
                    )
                    self.connected_port = target_port
                    self.is_connected = True
                    self.last_error_message = None
                    self.gateway_info["status"] = f"CONNECTED_ON_{target_port}"
                    logger.info(f"Successfully locked serial channel on {target_port}.")
                except serial.SerialException as se:
                    self._close_serial()
                    err_str = str(se)
                    self.last_error_message = err_str
                    if "PermissionError" in err_str or "Access is denied" in err_str:
                        logger.warning(
                            f"Port '{target_port}' is currently locked by PlatformIO Serial Monitor (Access is denied). "
                            f"Streaming live fallback packets so UI stays responsive. (To stream real hardware, close PlatformIO monitor). Retrying in {reconnect_delay}s..."
                        )
                    else:
                        logger.warning(f"Failed to open '{target_port}': {err_str}. Retrying in {reconnect_delay}s...")
                    # Emit live tick so website does not stall on constant static telemetry
                    self._emit_synthetic_tick()
                    time.sleep(reconnect_delay)
                    continue
                except Exception as ex:
                    self._close_serial()
                    self.last_error_message = str(ex)
                    logger.error(f"Unexpected serial connection error: {ex}. Retrying in {reconnect_delay}s...")
                    self._emit_synthetic_tick()
                    time.sleep(reconnect_delay)
                    continue

            # 3. Read incoming stream lines
            try:
                raw_bytes = self.serial_conn.readline()
                if not raw_bytes:
                    continue

                line = raw_bytes.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                # Parse and validate incoming packet
                packet = self._sanitize_and_parse_line(line)
                if packet:
                    self.packets_received += 1
                    self.last_packet_time = datetime.now(timezone.utc).isoformat()
                    self._dispatch_packet(packet)

            except serial.SerialException as se:
                logger.warning(f"Hardware connection severed on {self.connected_port}: {se}. Entering auto-reconnect...")
                self._close_serial()
                self.gateway_info["status"] = "DISCONNECTED_RECONNECTING"
                time.sleep(reconnect_delay)
            except Exception as ex:
                logger.error(f"Error reading serial line: {ex}")
                time.sleep(0.1)

    def _sanitize_and_parse_line(self, raw_line: str) -> Optional[Dict[str, Any]]:
        """
        Extracts JSON substrings between '{' and '}', converts raw sensor keys,
        and standardizes the telemetry dictionary.
        """
        # Find outer braces to strip away debug prefixes e.g. [RX] or UART noise
        start_idx = raw_line.find("{")
        end_idx = raw_line.rfind("}")

        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            # Not a JSON line; could be ESP32 debug log
            if not raw_line.startswith("---") and not raw_line.startswith("=="):
                logger.debug(f"[ESP32 UART DEBUG] {raw_line}")
            return None

        json_str = raw_line[start_idx:end_idx + 1]

        try:
            doc = json.loads(json_str)
        except json.JSONDecodeError:
            self.parse_errors += 1
            logger.warning(f"Malformed JSON fragment discarded: {json_str[:80]}")
            return None

        # System announcements from gateway firmware
        if doc.get("event") in ["GATEWAY_READY", "PONG", "HEARTBEAT"]:
            self.gateway_info.update(doc)
            return {"event": doc.get("event"), "gateway_id": doc.get("gateway_id", "GATEWAY_ESP32"), "raw": doc}

        # Normalize telemetry keys to standard format
        node_id = str(doc.get("node_id") or doc.get("node") or doc.get("id") or "NODE_01").strip()
        
        # Telemetry parsing with robust key aliases
        tilt_x = self._safe_float(doc.get("tilt_x") or doc.get("tilt_x_deg") or doc.get("ax_deg"), default=0.0)
        tilt_y = self._safe_float(doc.get("tilt_y") or doc.get("tilt_y_deg") or doc.get("ay_deg"), default=0.0)
        disp_mm = self._safe_float(doc.get("disp_mm") or doc.get("displacement_mm") or doc.get("disp"), default=0.5)
        strain_ue = self._safe_float(doc.get("strain_ue") or doc.get("strain") or doc.get("str"), default=90.0)
        vib = self._safe_float(doc.get("vib") or doc.get("vibration_amp") or doc.get("vibration"), default=0.015)
        
        local_zone = str(doc.get("local_zone") or doc.get("zone_id") or doc.get("zone") or "Zone A")
        role = str(doc.get("role") or ("REFERENCE" if "1" in node_id or "A" in node_id else "MONITORING"))

        # Derived composite tilt: sqrt(tilt_x^2 + tilt_y^2)
        tilt_composite = round(math.sqrt(tilt_x ** 2 + tilt_y ** 2), 3)

        normalized_packet: Dict[str, Any] = {
            "node_id": node_id,
            "role": role,
            "local_zone": local_zone,
            "tilt_x_deg": round(tilt_x, 3),
            "tilt_y_deg": round(tilt_y, 3),
            "tilt_composite_deg": tilt_composite,
            "displacement_mm": round(disp_mm, 2),
            "strain_ue": round(strain_ue, 1),
            "vibration_amp": round(vib, 4),
            "rssi_dbm": int(doc.get("rssi_dbm") or doc.get("rssi") or -68),
            "snr_db": float(doc.get("snr_db") or doc.get("snr") or 9.5),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "HARDWARE_USB_SERIAL",
            "port": self.connected_port
        }

        # Include differential fields if present
        if "ref_displacement_mm" in doc:
            normalized_packet["ref_displacement_mm"] = self._safe_float(doc["ref_displacement_mm"])
        if "differential_displacement_mm" in doc:
            normalized_packet["differential_displacement_mm"] = self._safe_float(doc["differential_displacement_mm"])
        if "differential_tilt_deg" in doc:
            normalized_packet["differential_tilt_deg"] = self._safe_float(doc["differential_tilt_deg"])

        return normalized_packet

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        """Converts value to float safely, guarding against None, NaN, and Inf."""
        if val is None:
            return default
        try:
            f = float(val)
            return default if math.isnan(f) or math.isinf(f) else f
        except (ValueError, TypeError):
            return default

    def _dispatch_packet(self, packet: Dict[str, Any]):
        """Dispatches packet to consumer callback thread-safely."""
        if not self.on_packet_callback:
            return

        if self.loop and self.loop.is_running():
            if asyncio.iscoroutinefunction(self.on_packet_callback):
                asyncio.run_coroutine_threadsafe(self.on_packet_callback(packet), self.loop)
            else:
                self.loop.call_soon_threadsafe(self.on_packet_callback, packet)
        else:
            try:
                res = self.on_packet_callback(packet)
                if asyncio.iscoroutine(res):
                    asyncio.run(res)
            except Exception as ex:
                logger.error(f"Error in synchronous packet dispatch: {ex}")

    def _emit_synthetic_tick(self):
        """Emits synthetic 1Hz packets for testing when hardware is not plugged in."""
        now_str = datetime.now(timezone.utc).isoformat()
        self.packets_received += 1
        self.last_packet_time = now_str

        # Node 1: Stable Bedrock Reference
        jitter_1 = (random.random() - 0.5) * 0.02
        ref_packet = {
            "node_id": "NODE_01",
            "role": "REFERENCE",
            "local_zone": "Zone A",
            "tilt_x_deg": round(0.04 + jitter_1, 3),
            "tilt_y_deg": round(0.02 + jitter_1, 3),
            "tilt_composite_deg": round(math.sqrt((0.04 + jitter_1)**2 + (0.02 + jitter_1)**2), 3),
            "displacement_mm": round(0.48 + jitter_1 * 2, 2),
            "strain_ue": round(92.0 + jitter_1 * 10, 1),
            "vibration_amp": round(max(0.005, 0.012 + jitter_1 * 0.02), 4),
            "rssi_dbm": random.randint(-72, -64),
            "snr_db": round(random.uniform(9.0, 11.5), 1),
            "timestamp": now_str,
            "source": "SIMULATION_FALLBACK"
        }
        self._dispatch_packet(ref_packet)

        # Node 2: Active Subsidence Station
        jitter_2 = (random.random() - 0.5) * 0.05
        mon_disp = round(12.4 + jitter_2 * 2, 2)
        mon_packet = {
            "node_id": "NODE_02",
            "role": "MONITORING",
            "local_zone": "Zone B",
            "tilt_x_deg": round(0.85 + jitter_2, 3),
            "tilt_y_deg": round(0.62 + jitter_2, 3),
            "tilt_composite_deg": round(math.sqrt((0.85 + jitter_2)**2 + (0.62 + jitter_2)**2), 3),
            "displacement_mm": mon_disp,
            "ref_displacement_mm": 0.48,
            "differential_displacement_mm": round(mon_disp - 0.48, 2),
            "differential_tilt_deg": round(math.sqrt((0.85 - 0.04)**2 + (0.62 - 0.02)**2), 3),
            "strain_ue": round(210.0 + jitter_2 * 20, 1),
            "vibration_amp": round(max(0.010, 0.080 + jitter_2 * 0.04), 4),
            "rssi_dbm": random.randint(-82, -72),
            "snr_db": round(random.uniform(7.0, 10.0), 1),
            "timestamp": now_str,
            "source": "SIMULATION_FALLBACK"
        }
        self._dispatch_packet(mon_packet)

    def get_status(self) -> Dict[str, Any]:
        """Provides full diagnostic status of the serial interface."""
        return {
            "is_connected": self.is_connected,
            "connected_port": self.connected_port,
            "configured_port": settings.SERIAL_PORT,
            "baud_rate": settings.BAUD_RATE,
            "packets_received": self.packets_received,
            "parse_errors": self.parse_errors,
            "last_packet_time": self.last_packet_time,
            "last_error": self.last_error_message,
            "gateway_info": self.gateway_info,
            "available_system_ports": self.detect_available_ports()
        }


# Global singleton instance
serial_listener = SerialListener()
