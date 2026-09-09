import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { sirenSynthesizer } from '../services/siren';

const TelemetryContext = createContext(null);

export const TelemetryProvider = ({ children }) => {
  // Live Hydration / Skeleton loading state toggle
  const [isLoading, setIsLoading] = useState(false);

  // Manual Drill / Hazard State Override: 'ZONE_A' | 'ZONE_B' | 'ZONE_C' | 'AUTO'
  const [overrideState, setOverrideState] = useState('AUTO');

  // Active node for forecasting inspection
  const [activeForecastNode, setActiveForecastNode] = useState('NODE_C1');

  // Historical displacement buffer (past 5-6 points)
  const [historicalPoints, setHistoricalPoints] = useState([
    { label: '-30m', timeVal: -0.5, value: 8.2, isFuture: false },
    { label: '-20m', timeVal: -0.33, value: 9.1, isFuture: false },
    { label: '-10m', timeVal: -0.16, value: 10.3, isFuture: false },
    { label: '-5m', timeVal: -0.08, value: 11.2, isFuture: false },
    { label: 'Now', timeVal: 0.0, value: 12.4, isFuture: false },
  ]);

  // Baseline Telemetry Values
  const [telemetry, setTelemetry] = useState({
    node1: { tiltX: 0.02, tiltY: -0.01, transientAccel: 0.012, status: 'NOMINAL' },
    node2: { tiltX: 0.14, tiltY: 0.08, transientRms: 0.045, status: 'NOMINAL' },
    node3: { tiltX: -0.01, tiltY: 0.03, transientAccel: 0.009, status: 'NOMINAL' },
    tofDistance: 12.40, // mm vertical displacement
    strainGauge: 142.5, // microstrain (με) (Threshold: 850 με)
    anomalyScore: 0.18, // 0.00 - 1.00
    currentZone: 'ZONE_A', // ZONE_A | ZONE_B | ZONE_C
    zoneMessage: 'SUBSURFACE STABLE. ZERO CRITICAL TURBULENCE DETECTED.',
    lastUpdated: new Date().toISOString(),
    samplingRate: '50 Hz',
    loraFrequency: '868.10 MHz',
    latencyMs: 24,
    // Deep LSTM Multi-Step Forecasting Engine
    forecast: {
      timeToCriticalHours: null,
      statusMessage: 'Ground displacement trajectory stable. No critical breach forecasted within 6 hours.',
      forecastTrajectory: [12.8, 13.2, 13.7, 14.1, 14.6, 15.0],
      criticalThreshold: 35.0,
      activeEngine: 'LSTM_ONNX_V2',
    },
  });

  const wsRef = useRef(null);

  // Connect to FastAPI live WebSocket stream if backend is available
  useEffect(() => {
    let socket;
    try {
      socket = new WebSocket('ws://localhost:8000/ws/live');
      wsRef.current = socket;

      socket.onmessage = (event) => {
        try {
          const packet = JSON.parse(event.data);
          if (overrideState === 'AUTO' && packet) {
            setTelemetry((prev) => {
              const isRef = packet.role === 'REFERENCE' || packet.node_id === 'NODE_A1' || packet.node_id === 'NODE_01';

              if (isRef) {
                // Update Node 1 Reference Datum orientation without altering mine risk level
                return {
                  ...prev,
                  node1: {
                    tiltX: packet.tilt_x_deg ?? prev.node1.tiltX,
                    tiltY: packet.tilt_y_deg ?? prev.node1.tiltY,
                    transientAccel: packet.vibration_amp ?? prev.node1.transientAccel,
                    status: 'REFERENCE DATUM',
                  },
                };
              }

              // Node 2 is the main monitoring node driving risk assessment & alerts
              const activeZone =
                packet.predicted_risk === 'Critical'
                  ? 'ZONE_C'
                  : packet.predicted_risk === 'Warning'
                  ? 'ZONE_B'
                  : 'ZONE_A';

              const forecastData = packet.forecast || prev.forecast;

              return {
                ...prev,
                node2: {
                  tiltX: packet.tilt_x_deg ?? prev.node2.tiltX,
                  tiltY: packet.tilt_y_deg ?? prev.node2.tiltY,
                  transientRms: packet.vibration_amp ?? prev.node2.transientRms,
                  differentialTilt: packet.differential_tilt_deg,
                  status: activeZone === 'ZONE_C' ? 'CRITICAL SAG' : activeZone === 'ZONE_B' ? 'ELEVATED TILT' : 'NOMINAL',
                },
                tofDistance: packet.displacement_mm ?? prev.tofDistance,
                strainGauge: packet.strain_ue ?? prev.strainGauge,
                currentZone: activeZone,
                zoneMessage:
                  activeZone === 'ZONE_C'
                    ? 'CRITICAL GROUND MOVEMENT DETECTED ON NODE 2. EVACUATE SECTOR IMMEDIATELY.'
                    : activeZone === 'ZONE_B'
                    ? 'ELEVATED STRATA SAG & TILT DETECTED ON NODE 2. CAUTION ADVISED.'
                    : 'SUBSURFACE STABLE. ZERO CRITICAL TURBULENCE DETECTED.',
                forecast: {
                  ...prev.forecast,
                  timeToCriticalHours: forecastData.time_to_critical_hours,
                  statusMessage: forecastData.status_message,
                  forecastTrajectory: forecastData.forecast_trajectory || prev.forecast.forecastTrajectory,
                },
              };
            });
          }
        } catch (e) {
          // ignore non-json
        }
      };

      socket.onerror = () => {
        // Fallback to internal simulation
      };
    } catch (e) {
      // ignore
    }

    return () => {
      if (socket) socket.close();
    };
  }, [overrideState]);

  // Dynamic 50Hz telemetry simulation loop with small natural sensor noise
  useEffect(() => {
    const interval = setInterval(() => {
      setTelemetry((prev) => {
        const noise = (Math.random() - 0.5) * 0.02;

        let activeZone = prev.currentZone;
        let score = prev.anomalyScore;
        let n1 = { ...prev.node1 };
        let n2 = { ...prev.node2 };
        let n3 = { ...prev.node3 };
        let tof = prev.tofDistance;
        let strain = prev.strainGauge;

        // Forecaster payload
        let ttf = null;
        let msg = 'Ground displacement trajectory stable. No critical breach forecasted within 6 hours.';
        let trajectory = [12.8, 13.2, 13.7, 14.1, 14.6, 15.0];

        if (overrideState === 'TEST_ZONE_A') {
          activeZone = 'ZONE_A';
          score = 0.15 + (Math.random() - 0.5) * 0.04;
          n1 = { tiltX: 0.02 + noise, tiltY: -0.01 + noise, transientAccel: 0.011, status: 'NOMINAL' };
          n2 = { tiltX: 0.12 + noise, tiltY: 0.07 + noise, transientRms: 0.042, status: 'NOMINAL' };
          n3 = { tiltX: -0.01 + noise, tiltY: 0.02 + noise, transientAccel: 0.008, status: 'NOMINAL' };
          tof = 1.15 + noise;
          strain = 135.0 + noise * 10;
          ttf = null;
          msg = 'Ground displacement trajectory stable. No critical breach forecasted within 6 hours.';
          trajectory = [1.2, 1.4, 1.6, 1.8, 2.0, 2.2];
        } else if (overrideState === 'TEST_ZONE_B') {
          activeZone = 'ZONE_B';
          score = 0.52 + (Math.random() - 0.5) * 0.06;
          n1 = { tiltX: 0.45 + noise, tiltY: 0.32 + noise, transientAccel: 0.142, status: 'CAUTION' };
          n2 = { tiltX: 1.84 + noise, tiltY: 1.25 + noise, transientRms: 0.385, status: 'WARNING' };
          n3 = { tiltX: 0.12 + noise, tiltY: 0.09 + noise, transientAccel: 0.038, status: 'NOMINAL' };
          tof = 4.85 + noise * 2;
          strain = 495.2 + noise * 30;
          ttf = 5.8;
          msg = 'Estimated time to critical subsidence threshold: 5.8 hours';
          trajectory = [6.2, 9.8, 15.4, 22.0, 29.8, 36.5];
        } else if (overrideState === 'TEST_ZONE_C') {
          activeZone = 'ZONE_C';
          score = 0.89 + (Math.random() - 0.5) * 0.05;
          n1 = { tiltX: 2.15 + noise, tiltY: 1.94 + noise, transientAccel: 0.812, status: 'CRITICAL' };
          n2 = { tiltX: 5.72 + noise, tiltY: 4.88 + noise, transientRms: 1.450, status: 'CRITICAL' };
          n3 = { tiltX: 0.85 + noise, tiltY: 0.64 + noise, transientAccel: 0.310, status: 'CAUTION' };
          tof = 14.60 + noise * 5;
          strain = 940.8 + noise * 40; // Exceeds 850 yield threshold
          ttf = 4.2;
          msg = 'Estimated time to critical subsidence threshold: 4.2 hours';
          trajectory = [18.2, 23.5, 29.1, 33.8, 39.8, 46.5];
        } else {
          // AUTO mode natural drift
          n1.tiltX = Number((n1.tiltX + noise * 0.1).toFixed(2));
          n2.tiltX = Number((n2.tiltX + noise * 0.2).toFixed(2));
          n3.tiltX = Number((n3.tiltX + noise * 0.1).toFixed(2));
          tof = Number((tof + noise * 0.05).toFixed(2));
          strain = Number((strain + noise * 2).toFixed(1));

          if (score < 0.35) {
            activeZone = 'ZONE_A';
            ttf = null;
            msg = 'Ground displacement trajectory stable. No critical breach forecasted within 6 hours.';
            trajectory = [tof + 0.2, tof + 0.4, tof + 0.6, tof + 0.9, tof + 1.1, tof + 1.3];
          } else if (score < 0.70) {
            activeZone = 'ZONE_B';
            ttf = 5.6;
            msg = 'Estimated time to critical subsidence threshold: 5.6 hours';
            trajectory = [tof + 2.0, tof + 5.5, tof + 10.2, tof + 16.8, tof + 24.5, tof + 34.0];
          } else {
            activeZone = 'ZONE_C';
            ttf = 4.2;
            msg = 'Estimated time to critical subsidence threshold: 4.2 hours';
            trajectory = [18.2, 23.5, 29.1, 33.8, 39.8, 46.5];
          }
        }

        let zoneMsg = '';
        if (activeZone === 'ZONE_A') zoneMsg = 'SUBSURFACE STABLE. ZERO CRITICAL TURBULENCE DETECTED.';
        else if (activeZone === 'ZONE_B') zoneMsg = 'MILD GROUND TREMORS DETECTED. PREPARE FOR POSSIBLE EVACUATION.';
        else zoneMsg = 'CRITICAL GROUND MOVEMENT. EVACUATE CAVE IMMEDIATELY.';

        return {
          ...prev,
          node1: n1,
          node2: n2,
          node3: n3,
          tofDistance: Math.max(0.1, tof),
          strainGauge: Math.max(10, strain),
          anomalyScore: Math.min(1.0, Math.max(0.0, Number(score.toFixed(2)))),
          currentZone: activeZone,
          zoneMessage: zoneMsg,
          lastUpdated: new Date().toISOString(),
          latencyMs: 22 + Math.floor(Math.random() * 8),
          forecast: {
            ...prev.forecast,
            timeToCriticalHours: ttf,
            statusMessage: msg,
            forecastTrajectory: trajectory,
          },
        };
      });
    }, 300);

    return () => clearInterval(interval);
  }, [overrideState]);

  // Update historical points whenever tofDistance drifts
  useEffect(() => {
    setHistoricalPoints((prev) => {
      const updated = [...prev];
      updated[updated.length - 1] = {
        label: 'Now',
        timeVal: 0.0,
        value: Number(telemetry.tofDistance.toFixed(2)),
        isFuture: false,
      };
      return updated;
    });
  }, [telemetry.tofDistance]);

  // Handle siren auto-trigger on ZONE_C or when TTF <= 4.5 hours
  useEffect(() => {
    const isCritical =
      telemetry.currentZone === 'ZONE_C' ||
      (telemetry.forecast.timeToCriticalHours !== null && telemetry.forecast.timeToCriticalHours <= 4.5);

    if (isCritical) {
      sirenSynthesizer.start();
    } else {
      sirenSynthesizer.stop();
    }
  }, [telemetry.currentZone, telemetry.forecast.timeToCriticalHours]);

  const triggerDrillOverride = useCallback((mode) => {
    setOverrideState(mode);
  }, []);

  const toggleSkeletonLoading = useCallback(() => {
    setIsLoading((prev) => !prev);
  }, []);

  return (
    <TelemetryContext.Provider
      value={{
        telemetry,
        historicalPoints,
        activeForecastNode,
        setActiveForecastNode,
        isLoading,
        overrideState,
        triggerDrillOverride,
        toggleSkeletonLoading,
      }}
    >
      {children}
    </TelemetryContext.Provider>
  );
};

export const useTelemetry = () => {
  const ctx = useContext(TelemetryContext);
  if (!ctx) throw new Error('useTelemetry must be used within TelemetryProvider');
  return ctx;
};

