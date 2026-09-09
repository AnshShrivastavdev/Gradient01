import React, { useState, useEffect, useRef, useMemo } from 'react';

// ============================================================================
// Web Audio API Emergency Siren Synthesizer
// Synthesizes an alternating dual-tone industrial emergency alarm (850Hz / 550Hz)
// ============================================================================
class EmergencySirenSynthesizer {
  constructor() {
    this.audioCtx = null;
    this.oscillator = null;
    this.gainNode = null;
    this.isPlaying = false;
    this.pitchInterval = null;
    this.currentFrequency = 850;
  }

  init() {
    if (!this.audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        this.audioCtx = new AudioContextClass();
      }
    }
  }

  start() {
    if (this.isPlaying) return;
    this.init();
    if (!this.audioCtx) return;

    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }

    try {
      this.oscillator = this.audioCtx.createOscillator();
      this.gainNode = this.audioCtx.createGain();

      this.oscillator.type = 'sawtooth';
      this.oscillator.frequency.setValueAtTime(850, this.audioCtx.currentTime);

      // Volume envelope
      this.gainNode.gain.setValueAtTime(0.001, this.audioCtx.currentTime);
      this.gainNode.gain.exponentialRampToValueAtTime(0.25, this.audioCtx.currentTime + 0.1);

      this.oscillator.connect(this.gainNode);
      this.gainNode.connect(this.audioCtx.destination);
      this.oscillator.start();
      this.isPlaying = true;

      // Alternating 850Hz / 550Hz frequency shift every 380ms
      this.pitchInterval = setInterval(() => {
        if (!this.oscillator || !this.audioCtx) return;
        this.currentFrequency = this.currentFrequency === 850 ? 550 : 850;
        this.oscillator.frequency.setValueAtTime(this.currentFrequency, this.audioCtx.currentTime);
      }, 380);
    } catch (e) {
      console.warn('[AUDIO] AudioContext playback issue:', e);
    }
  }

  stop() {
    if (!this.isPlaying) return;
    if (this.pitchInterval) {
      clearInterval(this.pitchInterval);
      this.pitchInterval = null;
    }
    if (this.oscillator && this.audioCtx) {
      try {
        this.gainNode.gain.setValueAtTime(this.gainNode.gain.value, this.audioCtx.currentTime);
        this.gainNode.gain.exponentialRampToValueAtTime(0.0001, this.audioCtx.currentTime + 0.08);
        setTimeout(() => {
          try {
            this.oscillator?.stop();
            this.oscillator?.disconnect();
          } catch (e) {}
          this.oscillator = null;
        }, 90);
      } catch (e) {
        this.oscillator = null;
      }
    }
    this.isPlaying = false;
  }
}

const sirenSynth = new EmergencySirenSynthesizer();

export default function DashboardView() {
  // WebSocket State
  const [isConnected, setIsConnected] = useState(false);
  const [connectionLatency, setConnectionLatency] = useState(12);
  const [packetCounter, setPacketCounter] = useState(0);
  const [selectedNode, setSelectedNode] = useState('NODE_02');

  // Mute toggle for web siren
  const [isMuted, setIsMuted] = useState(false);
  const [sirenActive, setSirenActive] = useState(false);
  const [lastAlertNotificationTime, setLastAlertNotificationTime] = useState(0);

  // Live Telemetry Cache (by node_id)
  const [nodesData, setNodesData] = useState({
    NODE_01: {
      node_id: 'NODE_01',
      role: 'REFERENCE',
      current_zone: 'Zone A',
      confidence: 99.1,
      tilt_x_deg: 0.04,
      tilt_y_deg: 0.02,
      tilt_composite_deg: 0.045,
      displacement_mm: 0.48,
      strain_ue: 92.5,
      vibration_amp: 0.012,
      rssi_dbm: -67,
      snr_db: 10.2,
      source: 'INITIALIZING',
      timestamp: new Date().toISOString(),
      forecast_curve_6h: [0.50, 0.52, 0.55, 0.58, 0.60, 0.63],
      time_to_collapse_hours: null,
      collapse_message: 'Nominal reference bedrock stratum. Trajectory completely stable.',
      trigger_web_siren: false,
      classification_engine: 'XGBOOST_MODEL',
      forecasting_engine: 'PYTORCH_2LAYER_LSTM'
    },
    NODE_02: {
      node_id: 'NODE_02',
      role: 'MONITORING',
      current_zone: 'Zone B',
      confidence: 94.2,
      tilt_x_deg: 0.88,
      tilt_y_deg: 0.64,
      tilt_composite_deg: 1.088,
      displacement_mm: 12.4,
      ref_displacement_mm: 0.48,
      differential_displacement_mm: 11.92,
      differential_tilt_deg: 1.05,
      strain_ue: 215.0,
      vibration_amp: 0.082,
      rssi_dbm: -74,
      snr_db: 8.8,
      source: 'INITIALIZING',
      timestamp: new Date().toISOString(),
      forecast_curve_6h: [14.1, 16.5, 19.8, 23.4, 28.1, 33.5],
      time_to_collapse_hours: 6.4,
      collapse_message: 'Elevated rate of strata subsidence. Approach to 35mm threshold under monitoring.',
      trigger_web_siren: false,
      classification_engine: 'XGBOOST_MODEL',
      forecasting_engine: 'PYTORCH_2LAYER_LSTM'
    }
  });

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  // Request browser notification permissions on mount
  useEffect(() => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      if (Notification.permission === 'default') {
        Notification.requestPermission();
      }
    }
  }, []);

  // Establish & Maintain Resilient WebSocket Link to FastAPI
  useEffect(() => {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/telemetry';

    function connect() {
      try {
        console.log(`[WS] Connecting to telemetry stream: ${wsUrl}`);
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          console.log('[WS] Connected to FastAPI Telemetry Broadcaster');
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.type === 'GATEWAY_ANNOUNCEMENT') {
              console.log('[WS] Gateway Announcement:', data.payload);
              return;
            }

            if (data.node_id) {
              setPacketCounter((prev) => prev + 1);
              setNodesData((prev) => ({
                ...prev,
                [data.node_id]: {
                  ...prev[data.node_id],
                  ...data
                }
              }));

              // Check web siren trigger condition
              if (data.trigger_web_siren === true) {
                setSirenActive(true);

                // Fire desktop notification (debounced 10s)
                const now = Date.now();
                if (now - lastAlertNotificationTime > 10000) {
                  setLastAlertNotificationTime(now);
                  if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
                    new Notification('CRITICAL COAL MINE SUBSIDENCE ALERT', {
                      body: `Station ${data.node_id} reported ${data.current_zone || 'CRITICAL'}! Collapse estimated: ${data.time_to_collapse_hours ? data.time_to_collapse_hours + 'h' : 'IMMINENT'}. Evacuate hazardous sector!`,
                      icon: '/favicon.ico',
                      tag: 'subsidence-critical-alarm'
                    });
                  }
                }
              } else if (data.node_id === selectedNode && !data.trigger_web_siren) {
                // If current selected node has returned to nominal, stop siren
                setSirenActive(false);
              }
            }
          } catch (err) {
            console.error('[WS PARSE ERROR]', err);
          }
        };

        ws.onerror = (err) => {
          console.warn('[WS ERROR] Connection failed. Retrying in 2.5s...', err);
        };

        ws.onclose = () => {
          setIsConnected(false);
          console.log('[WS CLOSED] Telemetry link offline. Reconnecting in 2.5s...');
          reconnectTimeoutRef.current = setTimeout(connect, 2500);
        };
      } catch (err) {
        console.error('[WS EXCEPTION]', err);
        reconnectTimeoutRef.current = setTimeout(connect, 2500);
      }
    }

    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
      sirenSynth.stop();
    };
  }, [lastAlertNotificationTime, selectedNode]);

  // Manage Web Audio Siren Loop State
  useEffect(() => {
    if (sirenActive && !isMuted) {
      sirenSynth.start();
    } else {
      sirenSynth.stop();
    }
  }, [sirenActive, isMuted]);

  // Active Station Telemetry
  const currentData = nodesData[selectedNode] || nodesData['NODE_02'];

  // Zone Visual Styling Configuration
  const zoneConfig = useMemo(() => {
    const zone = currentData.current_zone || 'Zone A';
    switch (zone) {
      case 'Zone C':
        return {
          bannerBg: 'bg-red-950/70 border-red-500 shadow-[0_0_35px_rgba(239,68,68,0.35)]',
          badgeBg: 'bg-red-600 text-white animate-pulse',
          badgeText: 'ZONE C // CRITICAL SUBSIDENCE BREACH HAZARD',
          textColor: 'text-red-400',
          accentBorder: 'border-red-500/60',
          gaugeColor: '#EF4444',
          statusTitle: 'EMERGENCY EVACUATION RECOMMENDED',
          iconColor: 'text-red-500'
        };
      case 'Zone B':
        return {
          bannerBg: 'bg-amber-950/50 border-amber-500/80 shadow-[0_0_25px_rgba(245,158,11,0.2)]',
          badgeBg: 'bg-amber-500 text-black font-bold',
          badgeText: 'ZONE B // ELEVATED SUBSIDENCE ALERT',
          textColor: 'text-amber-400',
          accentBorder: 'border-amber-500/50',
          gaugeColor: '#F59E0B',
          statusTitle: 'GROUND ACCELERATION ACTIVE — MONITOR TRAJECTORY',
          iconColor: 'text-amber-400'
        };
      case 'Zone A':
      default:
        return {
          bannerBg: 'bg-emerald-950/40 border-emerald-500/60 shadow-[0_0_20px_rgba(16,185,129,0.15)]',
          badgeBg: 'bg-emerald-600/90 text-white',
          badgeText: 'ZONE A // STRATUM STABLE & NOMINAL',
          textColor: 'text-emerald-400',
          accentBorder: 'border-emerald-500/40',
          gaugeColor: '#10B981',
          statusTitle: 'NORMAL BEDROCK STRUCTURAL INTEGRITY',
          iconColor: 'text-emerald-400'
        };
    }
  }, [currentData.current_zone]);

  // 6-Hour Forecast Chart Points & Scales
  const forecastPoints = useMemo(() => {
    const trajectory = currentData.forecast_curve_6h || [12.4, 13.0, 13.8, 14.7, 15.8, 17.0];
    const currentDisp = currentData.displacement_mm || 12.4;
    return [currentDisp, ...trajectory];
  }, [currentData.forecast_curve_6h, currentData.displacement_mm]);

  // Helper to toggle siren test
  const handleToggleSirenTest = () => {
    setSirenActive((prev) => !prev);
  };

  return (
    <div className="min-h-screen bg-[#06090F] text-gray-100 font-sans p-4 sm:p-6 lg:p-8 space-y-6">
      {/* ==================================================================== */}
      {/* 1. TOP HEADER & METADATA BAR */}
      {/* ==================================================================== */}
      <header className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-gray-800">
        <div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-emerald-500 animate-ping"></span>
            <h1 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
              MINE SUBSIDENCE FORECASTING & EARLY WARNING SYSTEM
            </h1>
            <span className="text-xs px-2.5 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800 font-mono">
              SIH 2026 // PROD
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1 font-mono">
            USB-Serial Gateway Stream (115200 Baud) → FastAPI Dual ML Engine → PyTorch 2-Layer LSTM Forecaster
          </p>
        </div>

        {/* Live Stream Status & Mute Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* WebSocket Status Indicator */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono ${
            isConnected
              ? 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300'
              : 'bg-red-950/60 border-red-500/50 text-red-300'
          }`}>
            <span className={`h-2 w-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
            <span>{isConnected ? 'LIVE WS CONNECTED' : 'WS RECONNECTING...'}</span>
            <span className="text-gray-500">|</span>
            <span className="text-gray-400">Rx: {packetCounter} pkts</span>
          </div>

          {/* Node Station Selector */}
          <div className="flex items-center bg-[#0F1420] border border-gray-700 rounded-lg p-1 text-xs font-mono">
            <button
              onClick={() => setSelectedNode('NODE_01')}
              className={`px-3 py-1 rounded transition-all ${
                selectedNode === 'NODE_01'
                  ? 'bg-blue-600 text-white font-bold shadow'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              NODE_01 (REF)
            </button>
            <button
              onClick={() => setSelectedNode('NODE_02')}
              className={`px-3 py-1 rounded transition-all ${
                selectedNode === 'NODE_02'
                  ? 'bg-blue-600 text-white font-bold shadow'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              NODE_02 (MONITOR)
            </button>
          </div>

          {/* Audio Siren Mute / Test Toggle */}
          <button
            onClick={() => setIsMuted((prev) => !prev)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono transition-all ${
              isMuted
                ? 'bg-gray-800 border-gray-600 text-gray-400 hover:bg-gray-700'
                : sirenActive
                ? 'bg-red-600 text-white font-bold animate-pulse border-red-400'
                : 'bg-blue-950/60 border-blue-600/50 text-blue-300 hover:bg-blue-900/50'
            }`}
            title="Toggle siren sound output"
          >
            <span>{isMuted ? '🔇 SIREN MUTED' : sirenActive ? '🚨 SIREN SOUNDING' : '🔊 SIREN ARMED'}</span>
          </button>

          <button
            onClick={handleToggleSirenTest}
            className="px-2.5 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-mono border border-gray-700"
          >
            {sirenActive ? 'STOP SIREN' : 'TEST SIREN'}
          </button>
        </div>
      </header>

      {/* ==================================================================== */}
      {/* 2. DYNAMIC RISK ZONE BANNER & COLLAPSE COUNTDOWN */}
      {/* ==================================================================== */}
      <section className={`p-5 rounded-xl border transition-all duration-500 ${zoneConfig.bannerBg}`}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 rounded text-xs font-black tracking-wider uppercase ${zoneConfig.badgeBg}`}>
                {zoneConfig.badgeText}
              </span>
              <span className="text-xs font-mono text-gray-300">
                Confidence: <strong className="text-white">{currentData.confidence}%</strong>
              </span>
              <span className="text-xs font-mono text-gray-400">
                Engine: <span className="text-blue-300">{currentData.classification_engine || 'XGBOOST'}</span>
              </span>
            </div>
            <h2 className="text-lg font-bold text-white tracking-wide">
              {zoneConfig.statusTitle}
            </h2>
            <p className="text-xs text-gray-300 font-mono">
              {currentData.collapse_message}
            </p>
          </div>

          {/* Time-to-Collapse (TTF) Countdown Gauge */}
          <div className="flex items-center gap-4 bg-black/40 border border-white/10 p-3.5 rounded-lg">
            <div className="text-right">
              <div className="text-[10px] uppercase font-mono tracking-widest text-gray-400">
                ESTIMATED TIME-TO-COLLAPSE (TTF)
              </div>
              <div className="text-xs font-mono text-gray-300">
                Threshold Limit: <span className="text-red-400 font-bold">35.0 mm</span>
              </div>
            </div>
            <div className={`text-2xl sm:text-3xl font-mono font-black px-3 py-1 rounded border ${
              currentData.time_to_collapse_hours !== null && currentData.time_to_collapse_hours <= 2.0
                ? 'bg-red-600 text-white border-red-400 animate-pulse'
                : currentData.time_to_collapse_hours !== null
                ? 'bg-amber-600 text-white border-amber-400'
                : 'bg-emerald-950 text-emerald-400 border-emerald-600'
            }`}>
              {currentData.time_to_collapse_hours !== null
                ? `${currentData.time_to_collapse_hours.toFixed(1)} HRS`
                : 'STABLE (>6h)'}
            </div>
          </div>
        </div>
      </section>

      {/* ==================================================================== */}
      {/* 3. REAL-TIME SENSOR METRIC CARDS */}
      {/* ==================================================================== */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Tilt Composite & Angles */}
        <div className="bg-[#0B0F19] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors shadow-lg">
          <div className="flex items-center justify-between text-xs font-mono text-gray-400 mb-2">
            <span>INCLINOMETER / TILT</span>
            <span className="text-blue-400">MPU6500</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-mono font-black text-white">
              {currentData.tilt_composite_deg?.toFixed(2) ?? '0.00'}°
            </span>
            <span className="text-xs text-gray-400 font-mono">Composite</span>
          </div>
          <div className="mt-3 pt-3 border-t border-gray-800/80 grid grid-cols-2 gap-2 text-xs font-mono">
            <div>
              <span className="text-gray-500">Tilt X:</span>{' '}
              <span className="text-gray-200">{currentData.tilt_x_deg?.toFixed(2) ?? 0}°</span>
            </div>
            <div>
              <span className="text-gray-500">Tilt Y:</span>{' '}
              <span className="text-gray-200">{currentData.tilt_y_deg?.toFixed(2) ?? 0}°</span>
            </div>
            {currentData.differential_tilt_deg !== undefined && (
              <div className="col-span-2 text-[11px] text-amber-400">
                Δ Tilt vs Ref: +{currentData.differential_tilt_deg?.toFixed(3)}°
              </div>
            )}
          </div>
        </div>

        {/* Metric 2: Vertical Displacement */}
        <div className="bg-[#0B0F19] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors shadow-lg">
          <div className="flex items-center justify-between text-xs font-mono text-gray-400 mb-2">
            <span>GROUND DISPLACEMENT</span>
            <span className="text-red-400">CRITICAL: 35 mm</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className={`text-3xl font-mono font-black ${
              (currentData.displacement_mm || 0) >= 35
                ? 'text-red-500 animate-pulse'
                : (currentData.displacement_mm || 0) >= 20
                ? 'text-amber-400'
                : 'text-white'
            }`}>
              {currentData.displacement_mm?.toFixed(2) ?? '0.00'}
            </span>
            <span className="text-xs text-gray-400 font-mono">mm</span>
          </div>
          {/* Progress to 35mm threshold */}
          <div className="mt-3 w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                (currentData.displacement_mm || 0) >= 35 ? 'bg-red-500' : (currentData.displacement_mm || 0) >= 20 ? 'bg-amber-500' : 'bg-blue-500'
              }`}
              style={{ width: `${Math.min(100, ((currentData.displacement_mm || 0) / 35) * 100)}%` }}
            />
          </div>
          <div className="mt-2 flex justify-between text-[11px] font-mono text-gray-500">
            <span>0 mm</span>
            <span className="text-gray-400">
              {currentData.differential_displacement_mm !== undefined
                ? `Diff Sag: ${currentData.differential_displacement_mm} mm`
                : 'Datum Baseline'}
            </span>
            <span>35 mm</span>
          </div>
        </div>

        {/* Metric 3: Strain Gauge */}
        <div className="bg-[#0B0F19] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors shadow-lg">
          <div className="flex items-center justify-between text-xs font-mono text-gray-400 mb-2">
            <span>FIBER/STRATA STRAIN</span>
            <span className="text-yellow-400">LIMIT: 450 με</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-mono font-black text-white">
              {currentData.strain_ue?.toFixed(1) ?? '0.0'}
            </span>
            <span className="text-xs text-gray-400 font-mono">με</span>
          </div>
          <div className="mt-3 pt-3 border-t border-gray-800/80 flex items-center justify-between text-xs font-mono">
            <span className="text-gray-500">State:</span>
            <span className={`px-2 py-0.5 rounded text-[11px] ${
              (currentData.strain_ue || 0) > 450
                ? 'bg-red-950 text-red-400 border border-red-800'
                : (currentData.strain_ue || 0) > 180
                ? 'bg-amber-950 text-amber-400 border border-amber-800'
                : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
            }`}>
              {(currentData.strain_ue || 0) > 450 ? 'PLASTIC RUPTURE' : (currentData.strain_ue || 0) > 180 ? 'HIGH ELASTIC SAG' : 'NOMINAL BED'}
            </span>
          </div>
        </div>

        {/* Metric 4: Micro-Seismic Vibration */}
        <div className="bg-[#0B0F19] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors shadow-lg">
          <div className="flex items-center justify-between text-xs font-mono text-gray-400 mb-2">
            <span>VIBRATION AMPLITUDE</span>
            <span className="text-cyan-400">SEISMIC RMS</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-mono font-black text-white">
              {currentData.vibration_amp?.toFixed(4) ?? '0.0000'}
            </span>
            <span className="text-xs text-gray-400 font-mono">g-amp</span>
          </div>
          <div className="mt-3 pt-3 border-t border-gray-800/80 flex items-center justify-between text-xs font-mono text-gray-400">
            <span>LoRa RSSI:</span>
            <span className="text-white">{currentData.rssi_dbm || -70} dBm ({currentData.snr_db || 9} dB)</span>
          </div>
        </div>
      </section>

      {/* ==================================================================== */}
      {/* 4. PYTORCH 2-LAYER LSTM 6-HOUR TRAJECTORY VISUALIZATION */}
      {/* ==================================================================== */}
      <section className="bg-[#0B0F19] border border-gray-800 rounded-xl p-5 sm:p-6 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse"></span>
              6-HOUR GROUND DISPLACEMENT TRAJECTORY FORECAST
            </h3>
            <p className="text-xs font-mono text-gray-400">
              Evaluated with PyTorch 2-Layer LSTM sequence backbone over 60-step rolling window. Critical collapse cutoff at 35.0 mm.
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs font-mono">
            <div className="flex items-center gap-1.5 text-blue-400">
              <span className="h-2 w-4 bg-blue-500 rounded-sm"></span>
              <span>LSTM Prediction Curve</span>
            </div>
            <div className="flex items-center gap-1.5 text-red-400">
              <span className="h-0.5 w-4 border-b-2 border-dashed border-red-500"></span>
              <span>Collapse Cutoff (35mm)</span>
            </div>
          </div>
        </div>

        {/* SVG Forecast Trajectory Graph */}
        <div className="relative w-full h-72 sm:h-80 bg-[#080C14] border border-gray-800/80 rounded-lg p-3 sm:p-4 overflow-hidden">
          <svg className="w-full h-full" viewBox="0 0 700 240" preserveAspectRatio="none">
            <defs>
              <linearGradient id="forecastAreaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.45" />
                <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.0" />
              </linearGradient>
              <linearGradient id="dangerZoneGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#EF4444" stopOpacity="0.15" />
                <stop offset="100%" stopColor="#EF4444" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Background Grid Lines & Y-Axis Markers */}
            {[0, 10, 20, 30, 35, 40].map((val) => {
              const y = 220 - (val / 45) * 200;
              const isThreshold = val === 35;
              return (
                <g key={val}>
                  <line
                    x1="45"
                    y1={y}
                    x2="680"
                    y2={y}
                    stroke={isThreshold ? '#EF4444' : '#1F2937'}
                    strokeDasharray={isThreshold ? '4,4' : '2,2'}
                    strokeWidth={isThreshold ? 1.5 : 1}
                  />
                  <text
                    x="35"
                    y={y + 4}
                    fill={isThreshold ? '#EF4444' : '#6B7280'}
                    fontSize="10"
                    textAnchor="end"
                    fontFamily="monospace"
                  >
                    {val}mm
                  </text>
                </g>
              );
            })}

            {/* X-Axis Hourly Ticks */}
            {['Now', 't+1h', 't+2h', 't+3h', 't+4h', 't+5h', 't+6h'].map((label, idx) => {
              const x = 55 + idx * 100;
              return (
                <g key={label}>
                  <line x1={x} y1="20" x2={x} y2="220" stroke="#161E2E" strokeWidth="1" />
                  <text
                    x={x}
                    y="235"
                    fill="#9CA3AF"
                    fontSize="11"
                    textAnchor="middle"
                    fontFamily="monospace"
                  >
                    {label}
                  </text>
                </g>
              );
            })}

            {/* Threshold Label Callout */}
            <rect x="580" y="55" width="95" height="18" fill="#7F1D1D" rx="3" />
            <text x="627" y="67" fill="#FCA5A5" fontSize="9" textAnchor="middle" fontFamily="monospace" fontWeight="bold">
              35mm FAILURE
            </text>

            {/* Calculate Polyline Points */}
            {(() => {
              const coords = forecastPoints.map((val, idx) => {
                const x = 55 + idx * 100;
                const y = Math.max(15, 220 - (val / 45) * 200);
                return { x, y, val };
              });

              const pathD = coords.reduce((acc, pt, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${pt.x},${pt.y}`, '');
              const areaD = `${pathD} L ${coords[coords.length - 1].x},220 L ${coords[0].x},220 Z`;

              return (
                <>
                  {/* Area fill under curve */}
                  <path d={areaD} fill="url(#forecastAreaGrad)" />

                  {/* Forecast Line */}
                  <path
                    d={pathD}
                    fill="none"
                    stroke="#3B82F6"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />

                  {/* Individual Data Points with Value Callouts */}
                  {coords.map((pt, i) => {
                    const isExceeded = pt.val >= 35.0;
                    return (
                      <g key={i}>
                        <circle
                          cx={pt.x}
                          cy={pt.y}
                          r={i === 0 ? 6 : 5}
                          fill={isExceeded ? '#EF4444' : i === 0 ? '#10B981' : '#3B82F6'}
                          stroke="#0B0F19"
                          strokeWidth="2"
                        />
                        <text
                          x={pt.x}
                          y={pt.y - 10}
                          fill={isExceeded ? '#F87171' : '#E5E7EB'}
                          fontSize="10"
                          fontWeight="bold"
                          textAnchor="middle"
                          fontFamily="monospace"
                        >
                          {pt.val.toFixed(1)}
                        </text>
                      </g>
                    );
                  })}
                </>
              );
            })()}
          </svg>
        </div>

        {/* Bottom Forecast Summary Pills */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 pt-2">
          {['Now (Observed)', 'Hour 1', 'Hour 2', 'Hour 3', 'Hour 4', 'Hour 5', 'Hour 6'].map((lbl, idx) => {
            const val = forecastPoints[idx] ?? 0;
            const breached = val >= 35.0;
            return (
              <div
                key={lbl}
                className={`p-2 rounded border text-center font-mono ${
                  breached
                    ? 'bg-red-950/60 border-red-500 text-red-300'
                    : 'bg-[#080C14] border-gray-800 text-gray-300'
                }`}
              >
                <div className="text-[10px] text-gray-400">{lbl}</div>
                <div className={`text-sm font-black ${breached ? 'text-red-400' : 'text-white'}`}>
                  {val.toFixed(1)} mm
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ==================================================================== */}
      {/* 5. HARDWARE BRIDGE & ML DIAGNOSTICS */}
      {/* ==================================================================== */}
      <footer className="bg-[#0B0F19] border border-gray-800 rounded-xl p-4 text-xs font-mono text-gray-400 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span>
            Node: <strong className="text-white">{currentData.node_id}</strong> ({currentData.role})
          </span>
          <span>
            Port: <span className="text-blue-400">{currentData.port || 'COM3 / /dev/ttyUSB0'}</span>
          </span>
          <span>
            Baud: <span className="text-gray-200">115200</span>
          </span>
          <span>
            Deep Forecaster: <span className="text-emerald-400">{currentData.forecasting_engine || 'LSTM_PYTORCH'}</span>
          </span>
        </div>
        <div className="text-gray-500">
          Last Synced: {new Date(currentData.timestamp || Date.now()).toLocaleTimeString()}
        </div>
      </footer>
    </div>
  );
}
