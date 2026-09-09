import asyncio
import json
import math
import random
import time
from typing import Optional, List, Dict
import serial
import serial.tools.list_ports
from app.config import settings

class SerialGatewayReader:
    def __init__(self, on_packet_callback=None):
        self.on_packet_callback = on_packet_callback
        self.running = False
        self.serial_conn: Optional[serial.Serial] = None
        
        # Operational State: 'HARDWARE_SERIAL' or 'SIMULATION'
        self.active_mode: str = "SIMULATION" if settings.SIMULATION_MODE else "HARDWARE_SERIAL"
        self.connected_port: Optional[str] = None
        self.hardware_packets_count: int = 0
        self.simulation_packets_count: int = 0
        self.last_packet_time: Optional[str] = None
        self.gateway_metadata: Dict = {
            "gateway_id": "GATEWAY_SURFACE_01",
            "firmware": "2.2.0-PROD",
            "freq_mhz": 433.0,
            "status": "INITIALIZING"
        }
        self.lock = asyncio.Lock()

    def list_available_com_ports(self) -> List[Dict[str, str]]:
        """Returns all USB and serial COM ports detected on host system."""
        ports = serial.tools.list_ports.comports()
        detected = []
        for p in ports:
            detected.append({
                "port": p.device,
                "description": p.description,
                "hwid": p.hwid,
                "is_likely_esp32": any(keyword in p.description.lower() for keyword in ["ch340", "cp210", "usb-serial", "esp32", "silicon labs", "ftdi"])
            })
        return detected

    async def start(self):
        self.running = True
        print("[GATEWAY_READER] Initializing Central Telemetry Gateway Reader...")
        
        # Start the background task that manages serial connection & simulation
        asyncio.create_task(self._main_supervisor_loop())

    async def stop(self):
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self.connected_port = None

    async def switch_mode(self, new_mode: str, port: Optional[str] = None) -> Dict:
        """Manually toggle between HARDWARE_SERIAL and SIMULATION mode."""
        async with self.lock:
            if new_mode == "HARDWARE_SERIAL":
                if port:
                    settings.SERIAL_PORT = port
                self.active_mode = "HARDWARE_SERIAL"
                if self.serial_conn and self.serial_conn.is_open:
                    self.serial_conn.close()
                self.serial_conn = None
            else:
                self.active_mode = "SIMULATION"
                if self.serial_conn and self.serial_conn.is_open:
                    self.serial_conn.close()
                self.serial_conn = None
                self.connected_port = None

        return self.get_status()

    def get_status(self) -> Dict:
        return {
            "active_mode": self.active_mode,
            "connected_port": self.connected_port,
            "baud_rate": settings.BAUD_RATE,
            "hardware_packets_count": self.hardware_packets_count,
            "simulation_packets_count": self.simulation_packets_count,
            "last_packet_time": self.last_packet_time,
            "gateway_metadata": self.gateway_metadata,
            "available_host_ports": self.list_available_com_ports()
        }

    async def _try_connect_serial(self, port_name: str) -> bool:
        try:
            conn = serial.Serial(port_name, settings.BAUD_RATE, timeout=0.1)
            self.serial_conn = conn
            self.connected_port = port_name
            self.gateway_metadata["status"] = f"CONNECTED_TO_{port_name}"
            print(f"[GATEWAY_READER] Successfully opened Serial Link on {port_name} @ {settings.BAUD_RATE} baud.")
            return True
        except Exception as e:
            self.connected_port = None
            return False

    async def _main_supervisor_loop(self):
        """Supervises hardware connection and seamlessly streams data."""
        while self.running:
            if self.active_mode == "HARDWARE_SERIAL":
                # Check if port is open
                if not self.serial_conn or not self.serial_conn.is_open:
                    # Attempt connection to configured port
                    connected = await self._try_connect_serial(settings.SERIAL_PORT)
                    
                    # If configured port fails, scan for likely ESP32 ports
                    if not connected:
                        ports = self.list_available_com_ports()
                        for p in ports:
                            if p["port"] != settings.SERIAL_PORT:
                                if await self._try_connect_serial(p["port"]):
                                    settings.SERIAL_PORT = p["port"]
                                    connected = True
                                    break
                    
                    if not connected:
                        # Scan quietly without generating fake/dummy telemetry
                        await asyncio.sleep(2.0)
                        continue

                # Read from active serial connection
                try:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        brace_start = line.find('{')
                        brace_end = line.rfind('}')
                        if brace_start >= 0 and brace_end > brace_start:
                            json_str = line[brace_start:brace_end+1]
                            try:
                                packet = json.loads(json_str)
                                
                                # Handle gateway system announcement packets
                                if "event" in packet:
                                    if packet["event"] in ["GATEWAY_READY", "PONG"]:
                                        self.gateway_metadata.update(packet)
                                        print(f"[GATEWAY_HARDWARE] Gateway Announcement: {packet}")
                                elif "node_id" in packet:
                                    self.hardware_packets_count += 1
                                    self.last_packet_time = time.strftime("%Y-%m-%d %H:%M:%S")
                                    if not packet.get("timestamp"):
                                        packet["timestamp"] = self.last_packet_time
                                    print(f"[SERIAL RX COM] Node: {packet.get('node_id')} | Tilt: ({packet.get('tilt_x_deg')}°, {packet.get('tilt_y_deg')}°)")
                                    if self.on_packet_callback:
                                        await self.on_packet_callback(packet)
                            except json.JSONDecodeError:
                                print(f"[GATEWAY_SERIAL] {line}")
                        else:
                            if line and not line.startswith("---"):
                                print(f"[GATEWAY_SERIAL] {line}")
                except Exception as ex:
                    print(f"[GATEWAY_READER] Serial read glitch ({ex}). Reconnecting...")
                    if self.serial_conn:
                        try:
                            self.serial_conn.close()
                        except Exception:
                            pass
                    self.serial_conn = None
                    self.connected_port = None
                    await asyncio.sleep(1.0)
            else:
                # Active mode is SIMULATION
                await self._emit_simulated_tick()
                await asyncio.sleep(1.0)

            await asyncio.sleep(0.01)

    async def _emit_simulated_tick(self):
        """Generates continuous 1Hz synthetic sensor packets for the 2-Node Topology (Node 1 Reference, Node 2 Monitoring)"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.last_packet_time = timestamp

        # Node 1: Reference Datum (Stable Bedrock)
        ref_jitter = (random.random() - 0.5) * 0.01
        ref_tilt_x = round(0.02 + ref_jitter, 3)
        ref_tilt_y = round(-0.01 + ref_jitter, 3)
        ref_disp = round(0.45 + ref_jitter * 2, 2)
        ref_strain = round(92.0 + ref_jitter * 5, 1)
        ref_vib = round(max(0.002, 0.012 + ref_jitter * 0.05), 4)

        ref_packet = {
            "node_id": "NODE_01",
            "role": "REFERENCE",
            "zone_id": "Zone A",
            "timestamp": timestamp,
            "tilt_x_deg": ref_tilt_x,
            "tilt_y_deg": ref_tilt_y,
            "displacement_mm": ref_disp,
            "strain_ue": ref_strain,
            "vibration_amp": ref_vib,
            "rssi_dbm": random.randint(-72, -65),
            "snr_db": round(random.uniform(9.0, 11.5), 1),
            "source": "SIMULATION"
        }

        self.simulation_packets_count += 1
        if self.on_packet_callback:
            await self.on_packet_callback(ref_packet)

        # Node 2: Monitoring Station (Active Subsidence Sector, Direct Shared via Gateway)
        mon_jitter = (random.random() - 0.5) * 0.04
        mon_tilt_x = round(0.95 + mon_jitter, 3)
        mon_tilt_y = round(0.70 + mon_jitter, 3)
        mon_disp = round(7.50 + mon_jitter * 2, 2)
        mon_strain = round(240.0 + mon_jitter * 15, 1)
        mon_vib = round(max(0.005, 0.180 + mon_jitter * 0.1), 4)

        diff_disp = round(mon_disp - ref_disp, 2)
        diff_tilt = round(float(np.sqrt((mon_tilt_x - ref_tilt_x)**2 + (mon_tilt_y - ref_tilt_y)**2)), 3) if 'np' in globals() else round(math.sqrt((mon_tilt_x - ref_tilt_x)**2 + (mon_tilt_y - ref_tilt_y)**2), 3)

        mon_packet = {
            "node_id": "NODE_02",
            "role": "MONITORING",
            "zone_id": "Zone B",
            "timestamp": timestamp,
            "tilt_x_deg": mon_tilt_x,
            "tilt_y_deg": mon_tilt_y,
            "displacement_mm": mon_disp,
            "ref_displacement_mm": ref_disp,
            "differential_displacement_mm": diff_disp,
            "differential_tilt_deg": diff_tilt,
            "strain_ue": mon_strain,
            "vibration_amp": mon_vib,
            "rssi_dbm": random.randint(-82, -70),
            "snr_db": round(random.uniform(7.5, 10.5), 1),
            "source": "SIMULATION"
        }

        self.simulation_packets_count += 1
        if self.on_packet_callback:
            await self.on_packet_callback(mon_packet)

_global_gateway_reader: Optional[SerialGatewayReader] = None

def set_global_gateway_reader(reader: SerialGatewayReader):
    global _global_gateway_reader
    _global_gateway_reader = reader

def get_global_gateway_reader() -> SerialGatewayReader:
    global _global_gateway_reader
    if _global_gateway_reader is None:
        _global_gateway_reader = SerialGatewayReader()
    return _global_gateway_reader

