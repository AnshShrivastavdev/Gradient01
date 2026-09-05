import { useTelemetryContext } from '../context/WebSocketContext';

export const useLiveTelemetry = (nodeId = 'NODE_A1') => {
  const { telemetry, isConnected, activeAlerts } = useTelemetryContext();
  const currentData = telemetry[nodeId] || telemetry.NODE_A1;

  return {
    data: currentData,
    isConnected,
    activeAlerts,
    allNodes: telemetry,
  };
};
