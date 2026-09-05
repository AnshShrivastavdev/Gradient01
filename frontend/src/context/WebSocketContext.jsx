import React, { createContext, useContext, useEffect, useState } from 'react';

const WebSocketContext = createContext(null);

export const WebSocketProvider = ({ children }) => {
  const [telemetry, setTelemetry] = useState({
    NODE_A1: { node_id: 'NODE_A1', zone_id: 'Zone A', tilt_x_deg: 0.02, tilt_y_deg: -0.01, displacement_mm: 0.45, strain_ue: 92.5, vibration_amp: 0.012, predicted_risk: 'Normal', confidence: 0.99 },
    NODE_B1: { node_id: 'NODE_B1', zone_id: 'Zone B', tilt_x_deg: 0.95, tilt_y_deg: 0.70, displacement_mm: 7.50, strain_ue: 240.0, vibration_amp: 0.180, predicted_risk: 'Warning', confidence: 0.98 },
    NODE_C1: { node_id: 'NODE_C1', zone_id: 'Zone C', tilt_x_deg: 4.50, tilt_y_deg: 3.80, displacement_mm: 34.00, strain_ue: 650.0, vibration_amp: 1.950, predicted_risk: 'Critical', confidence: 0.99 },
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
