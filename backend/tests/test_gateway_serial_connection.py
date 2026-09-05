import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
from fastapi.testclient import TestClient
from app.main import app
from app.services.serial_reader import SerialGatewayReader, get_global_gateway_reader

client = TestClient(app)

def test_gateway_status_endpoint():
    response = client.get("/api/v1/telemetry/gateway-status")
    assert response.status_code == 200
    data = response.json()
    assert "active_mode" in data
    assert "baud_rate" in data
    assert "available_host_ports" in data
    assert "gateway_metadata" in data
    assert data["baud_rate"] == 115200

def test_gateway_ports_endpoint():
    response = client.get("/api/v1/telemetry/gateway-ports")
    assert response.status_code == 200
    data = response.json()
    assert "ports" in data
    assert isinstance(data["ports"], list)

def test_gateway_switch_mode():
    # Switch to SIMULATION
    res1 = client.post("/api/v1/telemetry/gateway-switch-mode?mode=SIMULATION")
    assert res1.status_code == 200
    assert res1.json()["active_mode"] == "SIMULATION"

    # Switch to HARDWARE_SERIAL
    res2 = client.post("/api/v1/telemetry/gateway-switch-mode?mode=HARDWARE_SERIAL")
    assert res2.status_code == 200
    assert res2.json()["active_mode"] == "HARDWARE_SERIAL"

    # Revert back to SIMULATION for continuous testing
    res3 = client.post("/api/v1/telemetry/gateway-switch-mode?mode=SIMULATION")
    assert res3.status_code == 200
    assert res3.json()["active_mode"] == "SIMULATION"

@pytest.mark.asyncio
async def test_serial_reader_hardware_packet_processing():
    received_packets = []

    async def mock_callback(packet):
        received_packets.append(packet)

    reader = SerialGatewayReader(on_packet_callback=mock_callback)
    
    # Simulate single-line JSON packet emitted by ESP32 Gateway
    raw_packet_line = json.dumps({
        "node_id": "NODE_C1",
        "zone_id": "Zone C",
        "tilt_x_deg": 4.52,
        "tilt_y_deg": 3.81,
        "displacement_mm": 34.20,
        "strain_ue": 652.0,
        "vibration_amp": 1.84,
        "rssi_dbm": -71,
        "snr_db": 9.8,
        "seq": 2045,
        "gateway_id": "GATEWAY_SURFACE_01"
    })

    packet = json.loads(raw_packet_line)
    await reader.on_packet_callback(packet)

    assert len(received_packets) == 1
    assert received_packets[0]["node_id"] == "NODE_C1"
    assert received_packets[0]["displacement_mm"] == 34.20
    assert received_packets[0]["gateway_id"] == "GATEWAY_SURFACE_01"
