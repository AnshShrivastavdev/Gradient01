import React, { useState, useEffect, useRef, useMemo } from 'react';

// ============================================================================
// Web Audio API Dual-Tone Emergency Siren Synthesizer Fallback
// Alternates 850Hz / 550Hz square-sawtooth alarm if siren.mp3 is unavailable
// ============================================================================
class EmergencySirenSynthesizer {
  constructor() {
    this.audioCtx = null;
    this.oscillator = null;
    this.gainNode = null;
    this.isPlaying = false;
    this.intervalId = null;
    this.freq = 850;
  }

  init() {
    if (!this.audioCtx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.audioCtx = new AudioCtx();
    }
  }

  start() {
    if (this.isPlaying) return;
    this.init();
    if (!this.audioCtx) return;
    if (this.audioCtx.state === 'suspended') this.audioCtx.resume();

    try {
      this.oscillator = this.audioCtx.createOscillator();
      this.gainNode = this.audioCtx.createGain();
      this.oscillator.type = 'sawtooth';
      this.oscillator.frequency.setValueAtTime(850, this.audioCtx.currentTime);

      this.gainNode.gain.setValueAtTime(0.001, this.audioCtx.currentTime);
      this.gainNode.gain.exponentialRampToValueAtTime(0.25, this.audioCtx.currentTime + 0.1);

      this.oscillator.connect(this.gainNode);
      this.gainNode.connect(this.audioCtx.destination);
      this.oscillator.start();
      this.isPlaying = true;

      this.intervalId = setInterval(() => {
        if (!this.oscillator || !this.audioCtx) return;
        this.freq = this.freq === 850 ? 550 : 850;
        this.oscillator.frequency.setValueAtTime(this.freq, this.audioCtx.currentTime);
      }, 380);
    } catch (e) {
      console.warn('[AUDIO] Synthesizer issue:', e);
    }
  }

  stop() {
    if (!this.isPlaying) return;
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    if (this.oscillator && this.audioCtx) {
      try {
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

const synthSiren = new EmergencySirenSynthesizer();

export default function DashboardView() {
  const [isConnected, setIsConnected] = useState(false);
  const [packetCount, setPacketCount] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [sirenActive, setSirenActive] = useState(false);
  const [lastNotificationTime, setLastNotificationTime] = useState(0);

  // Unified Telemetry State aligned with DSP & ML Engine
  const [telemetry, setTelemetry] = useState({
    node_id: 'NODE_02',
    hardware_zone: 'Zone B',
    predicted_zone: 'Zone B',
    confidence: 96.4,
    raw: {
      disp_mm: 382.0,
      diff_disp_mm: 382.0,
      diff_tilt_deg: 187.805,
      tilt_x_deg: -0.183,
      tilt_y_deg: 90.549,
      vib_amp: 1.8656,
      strain_ue: 0.0,
      rssi: -66,
      snr: 9.0,
      seq: 587
    },
    filtered: {
      smooth_disp_mm: 382.0,
      disp_velocity_mm_s: 0.0,
      disp_accel_mm_s2: 0.0,
      smooth_tilt_deg: 187.8,
      tilt_rate_deg_s: 0.0
    },
    forecasting: {
      forecast_curve_6h: [383.5, 385.8, 388.5, 392.0, 396.2, 401.0],
      forecast_intervals: ['+1h', '+2h', '+3h', '+4h', '+5h', '+6h'],
      time_to_collapse_hours: 5.8,
      collapse_message: 'Estimated time of collapse: 5.8 hours',
      critical_threshold_mm: 400.0
    },
    trigger_web_siren: false,
    timestamp: new Date().toISOString()
  });

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const audioRef = useRef(null);

  // Request browser desktop notification permissions on mount
  useEffect(() => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      if (Notification.permission === 'default') {
        Notification.requestPermission();
      }
    }
  }, []);

  // Establish & Maintain WebSocket link to FastAPI at ws://localhost:8000/ws/telemetry
  useEffect(() => {
    const wsUrl = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_WS_URL) || 'ws://localhost:8000/ws/telemetry';

    function connect() {
      try {
        console.log(`[WS] Connecting to: ${wsUrl}`);
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          console.log('[WS] Connected to telemetry broadcaster');
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'GATEWAY_ANNOUNCEMENT') return;

            if (data.node_id) {
              setPacketCount((c) => c + 1);
              setTelemetry((prev) => ({
                ...prev,
                ...data,
                raw: { ...prev.raw, ...(data.raw || {}) },
                filtered: { ...prev.filtered, ...(data.filtered || {}) },
                forecasting: { ...prev.forecasting, ...(data.forecasting || {}) }
              }));

              // Check web siren trigger
              if (data.trigger_web_siren === true) {
                setSirenActive(true);

                // Debounced desktop notification (every 10s)
                const now = Date.now();
                if (now - lastNotificationTime > 10000) {
                  setLastNotificationTime(now);
                  if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
                    new Notification('CRITICAL SUBSIDENCE HAZARD', {
                      body: `Station ${data.node_id} reached ${data.predicted_zone || 'CRITICAL'}! ${data.forecasting?.collapse_message || 'Evacuate sector immediately!'}`,
                      icon: '/favicon.ico',
                      tag: 'subsidence-emergency'
                    });
                  }
                }
              } else {
                setSirenActive(false);
              }
            }
          } catch (err) {
            console.error('[WS PARSE ERR]', err);
          }
        };

        ws.onerror = () => {
          if (ws) ws.close();
        };

        ws.onclose = () => {
          setIsConnected(false);
          reconnectTimeoutRef.current = setTimeout(connect, 2000);
        };
      } catch (err) {
        reconnectTimeoutRef.current = setTimeout(connect, 2000);
      }
    }

    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
      synthSiren.stop();
      if (audioRef.current) audioRef.current.pause();
    };
  }, [lastNotificationTime]);

  // Handle siren audio playback (siren.mp3 with fallback to Web Audio synthesizer)
  useEffect(() => {
    if (sirenActive && !isMuted) {
      // Try HTML5 Audio element first
      if (!audioRef.current) {
        audioRef.current = new Audio('/sounds/siren.mp3');
        audioRef.current.loop = true;
      }
      audioRef.current.play().catch(() => {
        // Fallback to pure Web Audio API synthesizer
        synthSiren.start();
      });
    } else {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      synthSiren.stop();
    }
  }, [sirenActive, isMuted]);

  // Zone UI styling
  const zoneConfig = useMemo(() => {
    const zone = telemetry.predicted_zone || telemetry.hardware_zone || 'Zone B';
    switch (zone) {
      case 'Zone C':
        return {
          bannerBg: 'bg-red-950/70 border-red-500 shadow-[0_0_35px_rgba(239,68,68,0.35)]',
          badgeBg: 'bg-red-600 text-white animate-pulse',
          badgeText: 'ZONE C // CRITICAL SUBSIDENCE BREACH HAZARD',
          statusTitle: 'EMERGENCY EVACUATION DIRECTIVE ACTIVE',
          accentBorder: 'border-red-500/60',
          textColor: 'text-red-400'
        };
      case 'Zone B':
        return {
          bannerBg: 'bg-amber-950/50 border-amber-500/80 shadow-[0_0_25px_rgba(245,158,11,0.2)]',
          badgeBg: 'bg-amber-500 text-black font-bold',
          badgeText: 'ZONE B // ELEVATED SUBSIDENCE CAUTION',
          statusTitle: 'ACTIVE STRATA ACCELERATION — DYNAMIC DSP FILTERING ACTIVE',
          accentBorder: 'border-amber-500/50',
          textColor: 'text-amber-400'
        };
      case 'Zone A':
      default:
        return {
          bannerBg: 'bg-emerald-950/40 border-emerald-500/60 shadow-[0_0_20px_rgba(16,185,129,0.15)]',
          badgeBg: 'bg-emerald-600/90 text-white font-bold',
          badgeText: 'ZONE A // STRATUM STABLE & NOMINAL',
          statusTitle: 'NORMAL STRUCTURAL BEDROCK INTEGRITY',
          accentBorder: 'border-emerald-500/40',
          textColor: 'text-emerald-400'
        };
    }
  }, [telemetry.predicted_zone, telemetry.hardware_zone]);

  // Forecast points: Current smoothed + 6 hourly points
  const forecastPoints = useMemo(() => {
    const current = telemetry.filtered?.smooth_disp_mm ?? 382.0;
    const curve = telemetry.forecasting?.forecast_curve_6h || [383.5, 385.8, 388.5, 392.0, 396.2, 401.0];
    return [current, ...curve];
  }, [telemetry.filtered?.smooth_disp_mm, telemetry.forecasting?.forecast_curve_6h]);

  const threshold = telemetry.forecasting?.critical_threshold_mm || 400.0;

  return (
    <div className="min-h-screen bg-[#06090F] text-gray-100 font-mono p-4 sm:p-6 lg:p-8 space-y-6">
      {/* 1. HEADER & COM LINK MONITOR */}
      <header className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-gray-800">
        <div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-emerald-500 animate-ping"></span>
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight">
              UNDERGROUND MINE SUBSIDENCE MONITORING & EARLY WARNING
            </h1>
            <span className="text-[10px] px-2 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800">
              TEAM GRADIENT // SIH 2026
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            LoRa SX1278 (433MHz) → ESP32 Gateway → DSP Noise Filter → Dual ML Engine & LSTM TTF Forecaster
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs">
          {/* Live WS Status */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${
            isConnected ? 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300' : 'bg-red-950/60 border-red-500/50 text-red-300'
          }`}>
            <span className={`h-2 w-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
            <span>{isConnected ? 'LIVE WS CONNECTED' : 'WS RECONNECTING...'}</span>
            <span className="text-gray-500">|</span>
            <span className="text-gray-400">Rx: {packetCount} pkts</span>
          </div>

          {/* Active Node Indicator */}
          <div className="bg-[#0F1420] border border-gray-700 px-3 py-1.5 rounded-lg text-blue-400 font-bold">
            NODE_02 (SINGLE-NODE ACTIVE)
          </div>

          {/* Siren Control Button */}
          <button
            onClick={() => setIsMuted((m) => !m)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all ${
              isMuted
                ? 'bg-gray-800 border-gray-600 text-gray-400'
                : sirenActive
                ? 'bg-red-600 text-white font-bold animate-pulse border-red-400'
                : 'bg-blue-950/60 border-blue-600/50 text-blue-300'
            }`}
          >
            {isMuted ? '🔇 SIREN MUTED' : sirenActive ? '🚨 SIREN SOUNDING' : '🔊 SIREN ARMED'}
          </button>

          <button
            onClick={() => setSirenActive((s) => !s)}
            className="px-2.5 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700"
          >
            {sirenActive ? 'STOP TEST' : 'TEST SIREN'}
          </button>
        </div>
      </header>

      {/* 2. DYNAMIC ZONE STATUS BANNER & COLLAPSE COUNTDOWN */}
      <section className={`p-5 rounded-xl border transition-all duration-500 ${zoneConfig.bannerBg}`}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-3">
              <span className={`px-3 py-1 rounded text-xs font-black tracking-wider uppercase ${zoneConfig.badgeBg}`}>
                {zoneConfig.badgeText}
              </span>
              <span className="text-xs text-gray-300">
                Hardware LED: <strong className="text-white">{telemetry.hardware_zone}</strong>
              </span>
              <span className="text-xs text-gray-300">
                ML Confidence: <strong className="text-white">{telemetry.confidence}%</strong>
              </span>
            </div>
            <h2 className="text-lg font-bold text-white tracking-wide">
              {zoneConfig.statusTitle}
            </h2>
            <p className="text-xs text-gray-300 font-mono">
              {telemetry.forecasting?.collapse_message}
            </p>
          </div>

          {/* Time-to-Collapse (TTF) Countdown Badge */}
          <div className="flex items-center gap-4 bg-black/50 border border-white/10 p-3.5 rounded-lg">
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-widest text-gray-400">
                TIME-TO-COLLAPSE (TTF)
              </div>
              <div className="text-xs text-gray-300">
                Limit Threshold: <span className="text-red-400 font-bold">{threshold} mm</span>
              </div>
            </div>
            <div className={`text-2xl sm:text-3xl font-black px-3.5 py-1 rounded border ${
              telemetry.forecasting?.time_to_collapse_hours !== null && telemetry.forecasting?.time_to_collapse_hours <= 2.0
                ? 'bg-red-600 text-white border-red-400 animate-pulse'
                : telemetry.forecasting?.time_to_collapse_hours !== null
                ? 'bg-amber-600 text-white border-amber-400'
                : 'bg-emerald-950 text-emerald-400 border-emerald-600'
            }`}>
              {telemetry.forecasting?.time_to_collapse_hours !== null
                ? `${telemetry.forecasting.time_to_collapse_hours} HRS`
                : 'STABLE (>6h)'}
            </div>
          </div>
        </div>
      </section>

      {/* 3. REAL-TIME SMOOTHED SENSOR GAUGES (DSP + RATE ENGINE) */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Displacement (Median Filtered + EMA Smoothed) */}
        <div className="bg-[#0B0F19] border border-gray-800 rounded-xl p-5 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>LASER DISPLACEMENT (VL53L4CD)</span>
            <span className="text-cyan-400 text-[10px]">DSP SMOOTHED</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-white">
              {telemetry.filtered?.smooth_disp_mm?.toFixed(1) ?? '382.0'}
            </span>
            <span className="text-xs text-gray-400">mm</span>
            <span className="ml-auto text-xs px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
              v: {telemetry.filtered?.disp_velocity_mm_s?.toFixed(2) ?? '0.00'} mm/s
            </span>
          </div>
          {/* Progress to Threshold */}
          <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                (telemetry.filtered?.smooth_disp_mm || 0) >= threshold ? 'bg-red-500' : 'bg-blue-500'
              }`}
              style={{ width: `${Math.min(100, ((telemetry.filtered?.smooth_disp_mm || 0) / threshold) * 100)}%` }}
            />
          </div>
          <div className="pt-2 border-t border-gray-800/80 flex justify-between text-[11px] text-gray-500">
            <span>Raw: {telemetry.raw?.disp_mm?.toFixed(1)} mm</span>
            <span>Limit: {threshold} mm</span>
          </div>
        </div>

        {/* Card 2: Strata Tilt & Angular Rate */}
        <div className="bg-[#0B0F19] border border-gray-800 rounded-xl p-5 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>INCLINOMETER / TILT (MPU6050)</span>
            <span className="text-indigo-400 text-[10px]">BUTTERWORTH LPF</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-white">
              {telemetry.filtered?.smooth_tilt_deg?.toFixed(1) ?? '187.8'}°
            </span>
            <span className="text-xs text-gray-400">Diff Tilt</span>
            <span className="ml-auto text-xs text-gray-400">
              ω: {telemetry.filtered?.tilt_rate_deg_s?.toFixed(2) ?? '0.00'}°/s
            </span>
          </div>
          <div className="pt-2 border-t border-gray-800/80 grid grid-cols-2 gap-1 text-[11px] text-gray-400">
            <div>Tilt X: <strong className="text-white">{telemetry.raw?.tilt_x_deg?.toFixed(2)}°</strong></div>
            <div>Tilt Y: <strong className="text-white">{telemetry.raw?.tilt_y_deg?.toFixed(2)}°</strong></div>
          </div>
        </div>

        {/* Card 3: Vibration Amplitude & Microstrain */}
        <div className="bg-[#0B0F19] border border-gray-800 rounded-xl p-5 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>VIBRATION & STRAIN</span>
            <span className="text-yellow-400 text-[10px]">SEISMIC RMS</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-white">
              {telemetry.raw?.vib_amp?.toFixed(3) ?? '1.865'}
            </span>
            <span className="text-xs text-gray-400">g-amp</span>
          </div>
          <div className="pt-2 border-t border-gray-800/80 flex justify-between text-[11px] text-gray-400">
            <span>Microstrain: <strong className="text-white">{telemetry.raw?.strain_ue?.toFixed(1)} με</strong></span>
            <span className="text-amber-400 font-bold">
              {(telemetry.raw?.vib_amp || 0) > 2.5 ? 'SEISMIC SHOCK' : 'ACTIVE'}
            </span>
          </div>
        </div>

        {/* Card 4: LoRa RF Link Quality */}
        <div className="bg-[#0B0F19] border border-gray-800 rounded-xl p-5 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>LORA SX1278 (433MHz)</span>
            <span className="text-emerald-400 text-[10px]">RF TELEMETRY</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-white">
              {telemetry.raw?.rssi ?? -66}
            </span>
            <span className="text-xs text-gray-400">dBm</span>
            <span className="ml-auto text-xs text-emerald-400 font-bold">
              SNR: {telemetry.raw?.snr ?? 9.0} dB
            </span>
          </div>
          <div className="pt-2 border-t border-gray-800/80 flex justify-between text-[11px] text-gray-400">
            <span>Gateway: <strong className="text-white">SURFACE_01</strong></span>
            <span>Packet Seq: #{telemetry.raw?.seq || 0}</span>
          </div>
        </div>
      </section>

      {/* 4. PYTORCH 2-LAYER LSTM 6-HOUR TRAJECTORY CHART */}
      <section className="bg-[#0B0F19] border border-gray-800 rounded-xl p-5 sm:p-6 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse"></span>
              6-HOUR GROUND DISPLACEMENT TRAJECTORY FORECAST
            </h3>
            <p className="text-xs text-gray-400">
              Evaluated with PyTorch 2-Layer LSTM sequence backbone over 60-step lookback window. Critical collapse cutoff at {threshold} mm.
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1.5 text-blue-400">
              <span className="h-2 w-4 bg-blue-500 rounded-sm"></span>
              <span>LSTM Forecast Trajectory</span>
            </div>
            <div className="flex items-center gap-1.5 text-red-400">
              <span className="h-0.5 w-4 border-b-2 border-dashed border-red-500"></span>
              <span>Collapse Cutoff ({threshold}mm)</span>
            </div>
          </div>
        </div>

        {/* Scaled SVG Graph */}
        <div className="relative w-full h-72 sm:h-80 bg-[#080C14] border border-gray-800/80 rounded-lg p-3 sm:p-4 overflow-hidden">
          <svg className="w-full h-full" viewBox="0 0 700 240" preserveAspectRatio="none">
            <defs>
              <linearGradient id="forecastAreaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.45" />
                <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Grid & Y-Axis lines scaled around 370mm - 410mm */}
            {[370, 380, 390, 400, 410].map((val) => {
              const y = 220 - ((val - 365) / 50) * 190;
              const isThreshold = val === threshold;
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
                    x="40"
                    y={y + 4}
                    fill={isThreshold ? '#EF4444' : '#6B7280'}
                    fontSize="10"
                    textAnchor="end"
                  >
                    {val}mm
                  </text>
                </g>
              );
            })}

            {/* X-Axis Ticks */}
            {['Now', '+1h', '+2h', '+3h', '+4h', '+5h', '+6h'].map((label, idx) => {
              const x = 60 + idx * 100;
              return (
                <g key={label}>
                  <line x1={x} y1="20" x2={x} y2="220" stroke="#161E2E" strokeWidth="1" />
                  <text x={x} y="235" fill="#9CA3AF" fontSize="11" textAnchor="middle">
                    {label}
                  </text>
                </g>
              );
            })}

            {/* Threshold Label */}
            <rect x="580" y="30" width="100" height="18" fill="#7F1D1D" rx="3" />
            <text x="630" y="42" fill="#FCA5A5" fontSize="9" textAnchor="middle" fontWeight="bold">
              {threshold}mm FAILURE
            </text>

            {/* Curve plotting */}
            {(() => {
              const coords = forecastPoints.map((val, idx) => {
                const x = 60 + idx * 100;
                const y = Math.max(20, Math.min(220, 220 - ((val - 365) / 50) * 190));
                return { x, y, val };
              });

              const pathD = coords.reduce((acc, pt, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${pt.x},${pt.y}`, '');
              const areaD = `${pathD} L ${coords[coords.length - 1].x},220 L ${coords[0].x},220 Z`;

              return (
                <>
                  <path d={areaD} fill="url(#forecastAreaGrad)" />
                  <path d={pathD} fill="none" stroke="#3B82F6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                  {coords.map((pt, i) => {
                    const isBreach = pt.val >= threshold;
                    return (
                      <g key={i}>
                        <circle
                          cx={pt.x}
                          cy={pt.y}
                          r={i === 0 ? 6 : 5}
                          fill={isBreach ? '#EF4444' : i === 0 ? '#10B981' : '#3B82F6'}
                          stroke="#0B0F19"
                          strokeWidth="2"
                        />
                        <text
                          x={pt.x}
                          y={pt.y - 10}
                          fill={isBreach ? '#F87171' : '#E5E7EB'}
                          fontSize="10"
                          fontWeight="bold"
                          textAnchor="middle"
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

        {/* 7 Hourly Interval Summary Pills */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 pt-2">
          {['Now (Observed)', 'Hour 1', 'Hour 2', 'Hour 3', 'Hour 4', 'Hour 5', 'Hour 6'].map((lbl, idx) => {
            const val = forecastPoints[idx] ?? 0;
            const isBreach = val >= threshold;
            return (
              <div
                key={lbl}
                className={`p-2 rounded border text-center ${
                  isBreach
                    ? 'bg-red-950/60 border-red-500 text-red-300'
                    : 'bg-[#080C14] border-gray-800 text-gray-300'
                }`}
              >
                <div className="text-[10px] text-gray-400">{lbl}</div>
                <div className={`text-sm font-black ${isBreach ? 'text-red-400' : 'text-white'}`}>
                  {val.toFixed(1)} mm
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 5. FOOTER DIAGNOSTICS */}
      <footer className="bg-[#0B0F19] border border-gray-800 rounded-xl p-4 text-xs text-gray-400 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span>Active Station: <strong className="text-white">NODE_02 (MONITORING)</strong></span>
          <span>Baud: <strong className="text-white">115200</strong></span>
          <span>DSP Filter: <strong className="text-emerald-400">MEDIAN(5) + EMA(0.3)</strong></span>
          <span>Dual ML: <strong className="text-blue-400">XGBoost + PyTorch LSTM</strong></span>
        </div>
        <div>
          Last Ingested: {new Date(telemetry.timestamp || Date.now()).toLocaleTimeString()}
        </div>
      </footer>
    </div>
  );
}
