import React, { createContext, useContext, useEffect, useState } from 'react';

const WebSocketContext = createContext(null);

export const WebSocketProvider = ({ children }) => {
  const [telemetry, setTelemetry] = useState({
    NODE_01: {
      node_id: 'NODE_01',
      role: 'REFERENCE',
      zone_id: 'Zone A',
      tilt_x_deg: 0.0,
      tilt_y_deg: 0.0,
      displacement_mm: 0.0,
      strain_ue: 0.0,
      vibration_amp: 0.0,
      predicted_risk: 'Normal',
      confidence: 1.0,
      is_reference: true,
      description: 'Fixed Bedrock Reference Datum (Awaiting live telemetry)'
    },
    NODE_02: {
      node_id: 'NODE_02',
      role: 'MONITORING',
      zone_id: 'Zone B',
      tilt_x_deg: 0.0,
      tilt_y_deg: 0.0,
      displacement_mm: 0.0,
      ref_displacement_mm: 0.0,
      differential_displacement_mm: 0.0,
      differential_tilt_deg: 0.0,
      strain_ue: 0.0,
      vibration_amp: 0.0,
      predicted_risk: 'Normal',
      confidence: 1.0,
      is_reference: false,
      description: 'Active Subsidence Sector (Awaiting live telemetry)'
    },
    // Backwards-compatible aliases
    NODE_A1: { node_id: 'NODE_A1', role: 'REFERENCE', zone_id: 'Zone A', tilt_x_deg: 0.0, tilt_y_deg: 0.0, displacement_mm: 0.0, strain_ue: 0.0, vibration_amp: 0.0, predicted_risk: 'Normal', confidence: 1.0 },
    NODE_B1: { node_id: 'NODE_B1', role: 'MONITORING', zone_id: 'Zone B', tilt_x_deg: 0.0, tilt_y_deg: 0.0, displacement_mm: 0.0, strain_ue: 0.0, vibration_amp: 0.0, predicted_risk: 'Normal', confidence: 1.0 },
  });

  const [activeAlerts, setActiveAlerts] = useState([]);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/ws/telemetry';
    let ws;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setIsConnected(true);
        console.log('[WS_CONNECTED] Telemetry link online');
      };

      ws.onmessage = (event) => {
        try {
          const packet = JSON.parse(event.data);
          if (packet.node_id) {
            setTelemetry((prev) => ({
              ...prev,
              [packet.node_id]: packet,
            }));
          }
          if (packet.alerts && packet.alerts.length > 0) {
            setActiveAlerts((prev) => [...packet.alerts, ...prev].slice(0, 10));
          }
        } catch (err) {
          console.error('[WS PARSE ERR]', err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
      };
    } catch (err) {
      console.log('[WS UNAVAILABLE] Using local state simulation');
    }

    return () => {
      if (ws) ws.close();
    };
  }, []);

  return (
    <WebSocketContext.Provider value={{ telemetry, activeAlerts, isConnected }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useTelemetryContext = () => useContext(WebSocketContext);
