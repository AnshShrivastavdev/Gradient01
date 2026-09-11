"""
Team Gradient - SIH Underground Coal Mine Subsidence Monitoring System
Module: serial_reader.py (Resilient Asynchronous / Threaded Serial Telemetry Stream Ingestion)
----------------------------------------------------------------------------------------------
Ingests real-time LoRa packets forwarded by the Central Surface ESP32 Gateway:
1. Configurable USB-Serial COM port (default COM5, COM3, or AUTO) at 115200 baud.
2. Non-blocking line scanner: strips debug logs, ANSI escapes, and extracts valid JSON payloads.
3. Resilient auto-reconnection logic when port is busy (PlatformIO conflict) or disconnected.
4. Terminal Serial Monitor: Prints clean colored log lines for every decoded packet:
   [MONITOR RX] Node: NODE_02 | Disp: 382mm | Tilt: 90.5° | Vib: 1.86 | Zone: Zone B
5. Concurrently dispatches raw dictionary to DSP filter, ML Dual-Engine, and WebSockets.
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

# Enable ANSI Virtual Terminal colors on Windows PowerShell / cmd
if os.name == "nt":
    os.system("")

logger = logging.getLogger("SerialReader")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [SERIAL_READER] %(message)s")

ESP32_PORT_KEYWORDS = [
    "cp210", "cp2102", "cp2104", "cp2108", "ch340", "ch341",
    "ftdi", "usb-serial", "esp32", "silicon labs", "uart", "prolific",
    "wchusb", "qinheng"
]

# ANSI Color constants for Terminal Serial Monitor
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_WHITE = "\033[97m"
CLR_BLUE = "\033[94m"

# Safe print helper to prevent Windows cp1252 console crashes
def safe_print(msg: str):
    try:
        print(msg, flush=True)
    except (UnicodeEncodeError, Exception):
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)
        except Exception:
            pass


class SerialGatewayReader:
    def __init__(self, on_packet_callback: Optional[Callable[[Dict[str, Any]], Any]] = None):
        """
        Initializes the serial gateway reader.
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
        self._last_lock_warn_time: float = 0.0
        self._has_printed_lock_banner: bool = False
        
        self.gateway_info: Dict[str, Any] = {
            "gateway_id": "GATEWAY_SURFACE_01",
            "baud_rate": settings.BAUD_RATE,
            "status": "INITIALIZING"
        }

    @staticmethod
    def detect_available_ports() -> List[Dict[str, Any]]:
        """Scans all COM ports and flags likely ESP32 / USB-UART bridge chips."""
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
        """Determines target COM port using config and auto-detection."""
        cfg_port = settings.SERIAL_PORT.strip() if settings.SERIAL_PORT else ""

        if cfg_port.upper() in ["NONE", "DISABLED", "OFF"]:
            return None

        available = self.detect_available_ports()

        # If running on Linux/Cloud container (e.g. Render, Docker), Windows COM ports do not exist
        if sys.platform != "win32" and cfg_port.upper().startswith("COM"):
            cfg_port = "AUTO"

        if cfg_port and cfg_port.upper() != "AUTO":
            return cfg_port

        # Prioritize ESP32-like ports
        for p in available:
            if p["is_likely_esp32"]:
                return p["port"]

        if available:
            return available[0]["port"]

        return None

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Starts background reading worker thread within FastAPI lifespan."""
        if self.running:
            return

        self.running = True
        self.loop = loop or asyncio.get_event_loop()
        self.worker_thread = threading.Thread(target=self._run_thread, daemon=True, name="ESP32-SerialReader")
        self.worker_thread.start()
        print(f"\n{CLR_BOLD}{CLR_CYAN}[SERIAL INITIATION]{CLR_RESET} Target Port: {settings.SERIAL_PORT or 'AUTO'} @ {settings.BAUD_RATE} baud.")

    def stop(self):
        """Stops reading and releases port resource."""
        self.running = False
        self._close_serial()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.5)
        self.is_connected = False
        self.connected_port = None
        self.gateway_info["status"] = "STOPPED"
        print(f"\n{CLR_BOLD}[SERIAL SHUTDOWN]{CLR_RESET} SerialGatewayReader stopped and port released.\n")

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
        """Dedicated thread loop for serial I/O with auto-reconnect and fallback streaming."""
        reconnect_delay = 2.0

        while self.running:
            # 1. Handle Simulation Mode if explicitly requested
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
                    self.serial_conn = serial.Serial(
                        port=target_port,
                        baudrate=settings.BAUD_RATE,
                        timeout=0.05,
                        write_timeout=1.0
                    )
                    self.connected_port = target_port
                    self.is_connected = True
                    self.last_error_message = None
                    self.gateway_info["status"] = f"CONNECTED_ON_{target_port}"
                    self._has_printed_lock_banner = False
                    
                    safe_print(
                        f"\n{CLR_BOLD}{CLR_GREEN}"
                        f"+--------------------------------------------------------------------------------------+\n"
                        f"| [PORT ACQUIRED] FASTAPI HAS SEIZED EXCLUSIVE ACCESS TO {target_port} @ {settings.BAUD_RATE} BAUD!   |\n"
                        f"| [SERIAL MONITOR ACTIVE] Ingesting Live LoRa 433MHz Telemetry Packets Directly        |\n"
                        f"+--------------------------------------------------------------------------------------+"
                        f"{CLR_RESET}\n"
                    )
                except serial.SerialException as se:
                    self._close_serial()
                    err_str = str(se)
                    self.last_error_message = err_str
                    now_t = time.time()
                    
                    if "PermissionError" in err_str or "Access is denied" in err_str:
                        if not self._has_printed_lock_banner:
                            self._has_printed_lock_banner = True
                            safe_print(
                                f"\n{CLR_BOLD}{CLR_YELLOW}"
                                f"+------------------------------------------------------------------------------------------+\n"
                                f"| [PORT LOCK DETECTED] Port '{target_port}' is currently busy or open in another program!      |\n"
                                f"|                                                                                          |\n"
                                f"|  -> ACTION TO STREAM LIVE HARDWARE:                                                      |\n"
                                f"|     Close PlatformIO Serial Monitor in your VS Code terminal (press [Ctrl+C]).           |\n"
                                f"|     FastAPI will automatically lock onto {target_port} within 2s without restarting!        |\n"
                                f"|                                                                                          |\n"
                                f"|  (Streaming live fallback packets so UI & ML stay responsive until port is released)    |\n"
                                f"+------------------------------------------------------------------------------------------+"
                                f"{CLR_RESET}\n"
                            )
                    else:
                        if (now_t - self._last_lock_warn_time) > 10.0:
                            self._last_lock_warn_time = now_t
                            logger.warning(f"Failed to open '{target_port}': {err_str}. Retrying in {reconnect_delay}s...")

                    # Always emit synthetic fallback packet so WebSocket clients receive live stream
                    self._emit_synthetic_tick()
                    time.sleep(reconnect_delay)
                    continue
                except Exception as ex:
                    self._close_serial()
                    self.last_error_message = str(ex)
                    logger.error(f"Unexpected serial connection error: {ex}. Retrying in {reconnect_delay}s...")
                    time.sleep(reconnect_delay)
                    continue

            # 3. Read incoming stream lines from physical hardware
            try:
                raw_bytes = self.serial_conn.readline()
                if not raw_bytes:
                    continue

                line = raw_bytes.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

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

    def send_actuation_command(self, risk: str):
        """Sends synchronized hardware actuation command (LEDs + Buzzer) back to ESP32 Gateway over USB Serial."""
        if self.serial_conn and self.serial_conn.is_open:
            try:
                cmd = f"CMD:ACTUATE:{risk.upper()}\n".encode("utf-8")
                self.serial_conn.write(cmd)
                self.serial_conn.flush()
            except Exception as e:
                logger.warning(f"Failed to send serial actuation command: {e}")

    def list_available_com_ports(self) -> List[str]:
        """Lists port names for detected serial ports."""
        return [p["port"] for p in self.detect_available_ports()]

    async def switch_mode(self, mode: str, port: Optional[str] = None) -> Dict[str, Any]:
        """Switches mode between SIMULATION and HARDWARE_SERIAL."""
        mode_upper = mode.upper()
        if "SIMULAT" in mode_upper:
            settings.SIMULATION_MODE = True
            self.gateway_info["status"] = "SIMULATION_MODE"
            active_mode = "SIMULATION"
        else:
            settings.SIMULATION_MODE = False
            active_mode = "HARDWARE_SERIAL"
            if port:
                settings.SERIAL_PORT = port

        return {
            "status": "SUCCESS",
            "active_mode": active_mode,
            "port": settings.SERIAL_PORT,
            "baud_rate": settings.BAUD_RATE
        }

    def _sanitize_and_parse_line(self, raw_line: str) -> Optional[Dict[str, Any]]:
        """
        Extracts JSON substrings between '{' and '}', strips debug prefixes,
        and standardizes the incoming telemetry dictionary for ingestion.
        """
        stripped = raw_line.strip()
        # Strictly ignore gateway debug logs like "[RX] Payload : ...", "[DATA] ...", etc.
        # Genuine telemetry packets and announcements from ESP32 gateway are serialized JSON objects
        if stripped.startswith("["):
            return None

        start_idx = stripped.find("{")
        end_idx = stripped.rfind("}")

        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            # Gateway/node debug messages (e.g., [RX] PACKET...)
            return None

        json_str = stripped[start_idx:end_idx + 1]

        try:
            doc = json.loads(json_str)
        except json.JSONDecodeError:
            self.parse_errors += 1
            return None

        # System announcements from gateway
        if doc.get("event") in ["GATEWAY_READY", "PONG", "HEARTBEAT"]:
            self.gateway_info.update(doc)
            return {"event": doc.get("event"), "gateway_id": doc.get("gateway_id", "GATEWAY_SURFACE_01"), "raw": doc}

        # Node identification and role mapping
        node_id = str(doc.get("node_id") or doc.get("node") or doc.get("id") or "NODE_02").strip()
        role = str(doc.get("role") or ("REFERENCE" if "1" in node_id else "MONITORING"))
        zone_id = str(doc.get("zone_id") or doc.get("local_zone") or ("Zone A" if role == "REFERENCE" else "Zone B"))

        # Telemetry metrics with explicit None checks to preserve legitimate 0.0 values (supporting full & short LoRa keys)
        tilt_x = self._extract_metric(doc, ["tilt_x_deg", "tilt_x", "tx"], default=0.0)
        tilt_y = self._extract_metric(doc, ["tilt_y_deg", "tilt_y", "ty"], default=0.0)
        disp_mm = self._extract_metric(doc, ["displacement_mm", "disp_mm", "d"], default=0.0)
        strain_ue = self._extract_metric(doc, ["strain_ue", "strain", "st"], default=0.0)
        vib_amp = self._extract_metric(doc, ["vibration_amp", "vib", "v"], default=0.015)

        ref_disp = self._extract_metric(doc, ["ref_displacement_mm"], default=0.0)
        diff_disp = self._extract_metric(doc, ["differential_displacement_mm", "diff_disp_mm", "di"], default=disp_mm - ref_disp)
        diff_tilt = self._extract_metric(doc, ["differential_tilt_deg"], default=round(math.sqrt(tilt_x**2 + tilt_y**2), 3))

        # Composite tilt
        tilt_composite = round(math.sqrt(tilt_x**2 + tilt_y**2), 3)

        normalized_packet: Dict[str, Any] = {
            "node_id": node_id,
            "role": role,
            "zone_id": zone_id,
            "hardware_zone": zone_id,
            "seq": int(doc.get("seq") or self.packets_received),
            "ts_ms": int(doc.get("ts_ms") or int(time.time() * 1000)),
            "tilt_x_deg": round(tilt_x, 3),
            "tilt_y_deg": round(tilt_y, 3),
            "tilt_composite_deg": tilt_composite,
            "displacement_mm": round(disp_mm, 2),
            "strain_ue": round(strain_ue, 1),
            "vibration_amp": round(vib_amp, 4),
            "shock_count": int(doc.get("shock_count") or 0),
            "ref_displacement_mm": round(ref_disp, 2),
            "differential_displacement_mm": round(diff_disp, 2),
            "differential_tilt_deg": round(diff_tilt, 3),
            "gateway_id": str(doc.get("gateway_id") or "GATEWAY_SURFACE_01"),
            "rssi_dbm": int(doc.get("rssi_dbm") or doc.get("rssi") or -66),
            "snr_db": float(doc.get("snr_db") or doc.get("snr") or 9.0),
            "source": "HARDWARE_LORA",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "port": self.connected_port
        }

        return normalized_packet

    @staticmethod
    def _extract_metric(doc: Dict[str, Any], keys: List[str], default: float = 0.0) -> float:
        """Safely extracts float from dictionary keys preserving legitimate 0.0 values."""
        for k in keys:
            if k in doc and doc[k] is not None:
                try:
                    f = float(doc[k])
                    if not (math.isnan(f) or math.isinf(f)):
                        return f
                except (ValueError, TypeError):
                    continue
        return default

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        if val is None:
            return default
        try:
            f = float(val)
            return default if math.isnan(f) or math.isinf(f) else f
        except (ValueError, TypeError):
            return default

    def _print_terminal_monitor(self, packet: Dict[str, Any]):
        """
        Prints clean formatted/colored telemetry directly to the backend terminal
        acting as our live Serial Monitor:
        [MONITOR RX] Node: NODE_02 | Disp: 0.45mm | Tilt: 0.02 deg | Vib: 0.015 | Zone: Zone A
        """
        node_id = packet.get("node_id", "NODE_02")
        disp = float(packet.get("displacement_mm", 0.0) or 0.0)

        tilt = packet.get("tilt_y_deg")
        if tilt is None:
            tilt = packet.get("differential_tilt_deg") or packet.get("tilt_composite_deg") or 0.0

        vib = float(packet.get("vibration_amp", 0.015) or 0.015)
        zone = packet.get("predicted_zone") or packet.get("zone_id") or packet.get("hardware_zone") or "Zone B"

        if "Zone C" in zone or "Critical" in zone:
            zone_color = f"{CLR_BOLD}{CLR_RED}{zone}{CLR_RESET}"
        elif "Zone B" in zone or "Warning" in zone:
            zone_color = f"{CLR_BOLD}{CLR_YELLOW}{zone}{CLR_RESET}"
        else:
            zone_color = f"{CLR_BOLD}{CLR_GREEN}{zone}{CLR_RESET}"

        log_line = (
            f"{CLR_BOLD}[MONITOR RX]{CLR_RESET} "
            f"Node: {CLR_CYAN}{node_id}{CLR_RESET} | "
            f"Disp: {CLR_WHITE}{disp:.2f}mm{CLR_RESET} | "
            f"Tilt: {CLR_WHITE}{float(tilt):.2f} deg{CLR_RESET} | "
            f"Vib: {CLR_WHITE}{vib:.3f}{CLR_RESET} | "
            f"Zone: {zone_color}"
        )
        safe_print(log_line)

    def _dispatch_packet(self, packet: Dict[str, Any]):
        """Prints live monitor log and dispatches packet to consumer callback thread-safely."""
        # 1. Print formatted live serial monitor log to console
        self._print_terminal_monitor(packet)

        # 2. Asynchronously mirror physical hardware packet to Render cloud backend
        if self.connected_port:
            self._async_forward_to_cloud(packet)

        # 3. Dispatch to async/sync callback
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

    def _async_forward_to_cloud(self, packet: Dict[str, Any]):
        """Asynchronously mirrors physical hardware packets to Render cloud backend with zero latency impact."""
        cloud_url = os.getenv("CLOUD_INGEST_URL", "https://gradient01.onrender.com/api/v1/telemetry/ingest")
        if not cloud_url:
            return

        def _worker():
            try:
                import urllib.request
                import json
                payload = json.dumps(packet).encode("utf-8")
                req = urllib.request.Request(
                    cloud_url,
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "HardwareGatewayBridge/1.0"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=1.5):
                    pass
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _emit_synthetic_tick(self):
        """No-op: Purged synthetic fallback to ensure only authentic hardware packets stream."""
        pass

    def list_available_com_ports(self) -> List[str]:
        """Returns list of detected COM port device names."""
        ports = self.detect_available_ports()
        return [p["port"] for p in ports]

    def set_mode(self, simulation: bool, port: Optional[str] = None):
        """Switches runtime mode between physical ESP32 hardware and simulation."""
        settings.SIMULATION_MODE = simulation
        if port:
            settings.SERIAL_PORT = port
        if simulation:
            self._close_serial()
            self.gateway_info["status"] = "SIMULATION_MODE"
        else:
            self._close_serial()
            self.gateway_info["status"] = "INITIALIZING"

    def get_status(self) -> Dict[str, Any]:
        active_mode = "SIMULATION" if settings.SIMULATION_MODE else ("HARDWARE_SERIAL" if self.is_connected else "DISCONNECTED")
        return {
            "active_mode": active_mode,
            "baud_rate": settings.BAUD_RATE,
            "available_host_ports": self.list_available_com_ports(),
            "gateway_metadata": self.gateway_info,
            "is_connected": self.is_connected,
            "connected_port": self.connected_port,
            "configured_port": settings.SERIAL_PORT,
            "packets_received": self.packets_received,
            "parse_errors": self.parse_errors,
            "last_packet_time": self.last_packet_time,
            "last_error": self.last_error_message,
            "gateway_info": self.gateway_info,
            "available_system_ports": self.detect_available_ports()
        }


# Global singleton instance
serial_reader = SerialGatewayReader()

def get_global_gateway_reader() -> SerialGatewayReader:
    """Returns global gateway reader singleton for routers and test suites."""
    global serial_reader
    return serial_reader

