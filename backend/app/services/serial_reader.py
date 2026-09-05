import asyncio
import json
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
                        # Fall back temporarily to simulation while waiting for USB plug-in
                        print(f"[GATEWAY_READER] No hardware ESP32 detected on serial ports. Emulating telemetry while scanning...")
                        await self._emit_simulated_tick()
                        await asyncio.sleep(1.0)
                        continue

                # Read from active serial connection
                try:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        if line.startswith('{') and line.endswith('}'):
                            packet = json.loads(line)
                            
                            # Handle gateway system announcement packets
                            if "event" in packet:
                                if packet["event"] in ["GATEWAY_READY", "PONG"]:
                                    self.gateway_metadata.update(packet)
                                    print(f"[GATEWAY_HARDWARE] Gateway Announcement: {packet}")
                            elif "node_id" in packet:
                                self.hardware_packets_count += 1
                                self.last_packet_time = time.strftime("%Y-%m-%d %H:%M:%S")
                                packet["timestamp"] = self.last_packet_time
                                if self.on_packet_callback:
                                    await self.on_packet_callback(packet)
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
        """Generates continuous 1Hz synthetic sensor packets across nodes"""
        nodes = [
            {"id": "NODE_A1", "zone": "Zone A", "tilt_base": 0.02, "disp_base": 0.45, "strain_base": 92.0, "vib_base": 0.015},
            {"id": "NODE_B1", "zone": "Zone B", "tilt_base": 0.95, "disp_base": 7.50, "strain_base": 240.0, "vib_base": 0.190},
            {"id": "NODE_C1", "zone": "Zone C", "tilt_base": 4.50, "disp_base": 34.00, "strain_base": 650.0, "vib_base": 1.950},
        ]

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.last_packet_time = timestamp

        for n in nodes:
            jitter = (random.random() - 0.5) * 0.04
            tilt_x = round(n["tilt_base"] + jitter, 3)
            tilt_y = round(n["tilt_base"] * 0.8 + jitter, 3)
            disp = round(n["disp_base"] + jitter * 2, 2)
            strain = round(n["strain_base"] + jitter * 15, 1)
            vib = round(max(0.002, n["vib_base"] + jitter * 0.1), 4)

            packet = {
                "node_id": n["id"],
                "zone_id": n["zone"],
                "timestamp": timestamp,
                "tilt_x_deg": tilt_x,
                "tilt_y_deg": tilt_y,
                "displacement_mm": disp,
                "strain_ue": strain,
                "vibration_amp": vib,
                "rssi_dbm": random.randint(-85, -60),
                "snr_db": round(random.uniform(7.0, 11.5), 1),
                "source": "SIMULATION"
            }

            self.simulation_packets_count += 1
            if self.on_packet_callback:
                await self.on_packet_callback(packet)

_global_gateway_reader: Optional[SerialGatewayReader] = None

def set_global_gateway_reader(reader: SerialGatewayReader):
    global _global_gateway_reader
    _global_gateway_reader = reader

def get_global_gateway_reader() -> SerialGatewayReader:
    global _global_gateway_reader
    if _global_gateway_reader is None:
        _global_gateway_reader = SerialGatewayReader()
    return _global_gateway_reader

