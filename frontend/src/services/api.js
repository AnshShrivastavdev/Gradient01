import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchLatestTelemetry = async (limit = 50) => {
  const response = await apiClient.get(`/telemetry/latest?limit=${limit}`);
  return response.data;
};

export const fetchNodeTelemetry = async (nodeId, limit = 50) => {
  const response = await apiClient.get(`/telemetry/node/${nodeId}?limit=${limit}`);
  return response.data;
};

export const runInstantPrediction = async (sensorPacket) => {
  const response = await apiClient.post('/telemetry/predict', sensorPacket);
  return response.data;
};
