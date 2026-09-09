import { useTelemetryContext } from '../context/WebSocketContext';

export const useLiveTelemetry = (nodeId = 'NODE_02') => {
  const { telemetry, isConnected, activeAlerts } = useTelemetryContext();

  // Support both NODE_01/NODE_02 and backwards-compatible NODE_A1/NODE_B1
  let currentData = telemetry[nodeId];
  if (!currentData) {
    if (nodeId === 'NODE_01' || nodeId === 'NODE_A1') {
      currentData = telemetry.NODE_01 || telemetry.NODE_A1;
    } else {
      currentData = telemetry.NODE_02 || telemetry.NODE_B1 || telemetry.NODE_01;
    }
  }

  return {
    data: currentData || {},
    isConnected,
    activeAlerts,
    allNodes: telemetry,
  };
};
