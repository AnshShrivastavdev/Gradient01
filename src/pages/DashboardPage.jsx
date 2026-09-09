import React, { useState } from 'react';
import { useTelemetry } from '../context/TelemetryContext';
import { useAuth } from '../context/AuthContext';
import { sirenSynthesizer } from '../services/siren';
import { DisplacementForecastChart } from '../components/DisplacementForecastChart';
import { DynamicEarlyWarningBanner } from '../components/DynamicEarlyWarningBanner';
import { HardwareRelayAlertPanel } from '../components/HardwareRelayAlertPanel';
import { ActiveShiftMusterDesk } from '../components/ActiveShiftMusterDesk';
import DashboardView from '../components/DashboardView';

export const DashboardPage = ({ onBackToStory }) => {
  const {
    telemetry,
    historicalPoints,
    activeForecastNode,
    setActiveForecastNode,
    isLoading,
    overrideState,
    triggerDrillOverride,
    toggleSkeletonLoading,
  } = useTelemetry();

  const { currentUser, registerLedger, approveWorker, rejectWorker, logout } = useAuth();

  // View toggle: 'SCADA' (Differential matrix) or 'DSP_ML' (Dedicated DSP & ML Live Telemetry)
  const [viewMode, setViewMode] = useState('DSP_ML');

  // Role toggle: Defaults to ADMIN so geotechnical SCADA forecasting is visible immediately
  const [roleMode, setRoleMode] = useState(currentUser?.role || 'ADMIN');
  const isAdmin = roleMode === 'ADMIN';
  const isWorker = roleMode === 'WORKER';

  const isCritical = telemetry.currentZone === 'ZONE_C';
  const isCaution = telemetry.currentZone === 'ZONE_B';

  const handleSirenToggle = () => {
    if (sirenSynthesizer.isPlaying) {
      sirenSynthesizer.stop();
    } else {
      sirenSynthesizer.start();
    }
  };

  return (
    <div className="min-h-[calc(100vh-140px)] bg-[#0D1117] text-[#E6EDF3] font-mono p-4 md:p-8 space-y-6 select-none max-w-7xl mx-auto">
      {/* 1. TOP MINIMAL DASHBOARD HEADER BAR */}
      <div className="bg-[#161B22] border-2 border-[#30363D] p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="text-[10px] bg-[#00B4D8] text-black font-bold px-2 py-0.5 uppercase">
              {isAdmin ? 'SAFETY INCHARGE ADMIN' : 'UNDERGROUND WORKER'}
            </span>
            <span className="text-xs text-[#8B949E]">
              {currentUser?.empId || 'EMP-8842'} | {currentUser?.name || 'Rajesh Kumar'}
            </span>
          </div>
          <h2 className="text-lg md:text-xl font-display font-extrabold text-white uppercase">
            COAL MINE MONITORING SYSTEM DASHBOARD
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {onBackToStory && (
            <button
              onClick={onBackToStory}
              className="px-3 py-1.5 font-bold uppercase border bg-emerald-950/70 text-emerald-300 border-emerald-500 hover:bg-emerald-600 hover:text-white transition-colors flex items-center gap-1"
            >
              <span>🎬</span> [ 3D STORYTELLING ]
            </button>
          )}

          <button
            onClick={() => setViewMode((v) => (v === 'SCADA' ? 'DSP_ML' : 'SCADA'))}
            className={`px-3 py-1.5 font-bold uppercase border transition-colors ${
              viewMode === 'DSP_ML'
                ? 'bg-[#00B4D8] text-black border-[#00B4D8]'
                : 'bg-[#0D1117] text-[#00B4D8] border-[#00B4D8] hover:bg-[#00B4D8] hover:text-black'
            }`}
          >
            {viewMode === 'DSP_ML' ? '[ SWITCH: SCADA OVERVIEW ]' : '[ SWITCH: DSP & ML TELEMETRY ]'}
          </button>

          <button
            onClick={() => setRoleMode(isAdmin ? 'WORKER' : 'ADMIN')}
            className="px-3 py-1.5 font-bold uppercase border bg-[#0D1117] text-[#8B949E] border-[#30363D] hover:text-white transition-colors"
          >
            {isAdmin ? '[ VIEW: WORKER HUD ]' : '[ VIEW: ADMIN SCADA ]'}
          </button>

          {isAdmin && (
            <button
              onClick={toggleSkeletonLoading}
              className={`px-3 py-1.5 font-bold uppercase border ${
                isLoading
                  ? 'bg-[#B45309] text-white border-white'
                  : 'bg-[#0D1117] text-[#8B949E] border-[#30363D] hover:text-white'
              }`}
            >
              {isLoading ? '[ HYDRATION: ON ]' : '[ HYDRATION: OFF ]'}
            </button>
          )}

          <button
            onClick={logout}
            className="px-3 py-1.5 bg-[#B91C1C] text-white font-bold uppercase border border-red-500 hover:bg-red-800"
          >
            [ LOG OUT ]
          </button>
        </div>
      </div>

      {viewMode === 'DSP_ML' ? (
        <div className="border-2 border-[#30363D] rounded-xl overflow-hidden shadow-2xl">
          <DashboardView />
        </div>
      ) : (
        <>
          {/* 2. MINIMAL CENTRAL HAZARD BEACON */}
          <div
            className={`p-5 border-2 flex flex-col md:flex-row items-center justify-between gap-4 transition-colors duration-300 ${
              isCritical
                ? 'bg-[#B91C1C] border-white text-white siren-active'
                : isCaution
                ? 'bg-[#B45309] border-white text-white'
                : 'bg-[#15803D] border-white text-white'
            }`}
          >
        <div className="space-y-1 text-center md:text-left">
          <div className="text-[10px] font-bold uppercase tracking-widest opacity-90">
            REAL-TIME COAL MINE HAZARD BEACON
          </div>
          <h3 className="text-xl md:text-2xl font-display font-extrabold uppercase">
            {telemetry.currentZone === 'ZONE_A' && 'ZONE A // NORMAL MONITORING'}
            {telemetry.currentZone === 'ZONE_B' && 'ZONE B // SEISMIC CAUTION'}
            {telemetry.currentZone === 'ZONE_C' && 'ZONE C // CRITICAL EVACUATION'}
          </h3>
          <p className="text-xs font-bold font-mono max-w-xl">
            "{telemetry.zoneMessage}"
          </p>
        </div>

        <button
          onClick={handleSirenToggle}
          className={`px-4 py-2 text-xs font-bold uppercase border whitespace-nowrap ${
            sirenSynthesizer.isPlaying
              ? 'bg-black text-white border-white animate-pulse'
              : 'bg-white text-black border-black hover:bg-gray-200'
          }`}
        >
          {sirenSynthesizer.isPlaying ? '[ SIREN: ACTIVE (STOP) ]' : '[ TEST ALARM SIREN ]'}
        </button>
      </div>

      {/* 3. MINIMAL LIVE TELEMETRY MATRIX */}
      <div className="space-y-3">
        <div className="flex justify-between items-center text-xs">
          <span className="font-bold text-white uppercase">[ LIVE TELEMETRY MATRIX ]</span>
          <span className="text-[#8B949E]">SAMPLING: 50 Hz | LATENCY: {telemetry.latencyMs}ms</span>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="scada-skeleton-loader h-28 border border-[#30363D] p-3 space-y-2">
                <div className="h-4 bg-[#30363D] w-3/4"></div>
                <div className="h-6 bg-[#30363D] w-full"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
            {/* Card 1: Node 1 Reference Datum */}
            <div className="bg-[#161B22] border-2 border-cyan-500/40 p-3 space-y-1.5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-cyan-400 text-[10px] font-bold uppercase tracking-wider">NODE 01 (REF DATUM)</span>
                <span className="text-[9px] bg-cyan-950 text-cyan-300 px-1.5 py-0.5 rounded border border-cyan-800">BEDROCK BASE</span>
              </div>
              <div className="text-white font-bold">SAG: <span className="text-cyan-300 text-sm font-extrabold">{telemetry.node1?.displacement?.toFixed(2) ?? '0.48'} mm</span></div>
              <div className="text-xs text-gray-300">TILT: <span className="text-white font-bold">{telemetry.node1?.tiltComposite?.toFixed(2) ?? '0.04'}°</span> (X:{telemetry.node1?.tiltX}° Y:{telemetry.node1?.tiltY}°)</div>
              <div className="text-xs text-gray-400">STRAIN: <span className="text-white font-bold">{telemetry.node1?.strain?.toFixed(1) ?? '92.0'} με</span></div>
              <div className="text-[10px] text-gray-500">ACCEL: {telemetry.node1?.transientAccel ?? '0.012'}g</div>
            </div>

            {/* Card 2: Node 2 Active Monitoring Station */}
            <div className="bg-[#161B22] border-2 border-[#00B4D8] p-3 space-y-1.5 shadow-sm shadow-blue-500/20">
              <div className="flex items-center justify-between">
                <span className="text-[#00B4D8] text-[10px] font-bold uppercase tracking-wider">NODE 02 (MONITORING)</span>
                <span className="text-[9px] bg-blue-950 text-blue-300 px-1.5 py-0.5 rounded border border-blue-800">ACTIVE SECTOR</span>
              </div>
              <div className="text-white font-bold">SAG: <span className="text-[#F59E0B] text-sm font-extrabold">{telemetry.node2?.displacement?.toFixed(2) ?? '12.40'} mm</span></div>
              <div className="text-xs text-gray-300">TILT: <span className="text-white font-bold">{telemetry.node2?.tiltComposite?.toFixed(2) ?? '1.05'}°</span> (X:{telemetry.node2?.tiltX}° Y:{telemetry.node2?.tiltY}°)</div>
              <div className="text-xs text-gray-400">STRAIN: <span className="text-white font-bold">{telemetry.node2?.strain?.toFixed(1) ?? '210.0'} με</span></div>
              <div className="text-[10px] text-gray-500">VIBE RMS: {telemetry.node2?.transientRms ?? '0.080'}g</div>
            </div>

            {/* Card 3: Differential Sag = Node 2 - Node 1 */}
            <div className="bg-[#0D1526] border-2 border-amber-500/80 p-3 space-y-1 shadow-md">
              <div className="text-amber-400 text-[10px] font-bold uppercase tracking-wider">
                Δ SAG [NODE 2 - NODE 1]
              </div>
              <div className="text-[11px] text-gray-300 font-mono">
                {telemetry.node2?.displacement?.toFixed(2) ?? '12.40'} - {telemetry.node1?.displacement?.toFixed(2) ?? '0.48'}
              </div>
              <div className="text-lg font-extrabold text-[#F59E0B]">
                = {telemetry.differential?.displacementMm?.toFixed(2) ?? '11.92'} mm
              </div>
              <div className="text-[10px] text-gray-400">
                True Strata Sag vs Bedrock
              </div>
            </div>

            {/* Card 4: Differential Tilt = Node 2 - Node 1 */}
            <div className="bg-[#0D1526] border-2 border-indigo-500/80 p-3 space-y-1 shadow-md">
              <div className="text-indigo-400 text-[10px] font-bold uppercase tracking-wider">
                Δ TILT [NODE 2 - NODE 1]
              </div>
              <div className="text-[11px] text-gray-300 font-mono">
                {telemetry.node2?.tiltComposite?.toFixed(2) ?? '1.05'}° - {telemetry.node1?.tiltComposite?.toFixed(2) ?? '0.04'}°
              </div>
              <div className="text-lg font-extrabold text-cyan-300">
                = +{telemetry.differential?.tiltDeg?.toFixed(3) ?? '1.014'}°
              </div>
              <div className="text-[10px] text-gray-400">
                Angular Strata Deflection
              </div>
            </div>

            {/* Card 5: Differential Strain = Node 2 - Node 1 */}
            <div className="bg-[#0D1526] border-2 border-emerald-500/80 p-3 space-y-1 shadow-md">
              <div className="text-emerald-400 text-[10px] font-bold uppercase tracking-wider">
                Δ STRAIN [NODE 2 - NODE 1]
              </div>
              <div className="text-[11px] text-gray-300 font-mono">
                {telemetry.node2?.strain?.toFixed(1) ?? '210.0'} - {telemetry.node1?.strain?.toFixed(1) ?? '92.0'}
              </div>
              <div className="text-lg font-extrabold text-white">
                = +{telemetry.differential?.strainUe?.toFixed(1) ?? '118.0'} με
              </div>
              <div className="text-[10px] text-gray-400">
                Induced Mechanical Stress
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 4. ISOLATION FOREST AI ANOMALY BAR */}
      <div className="bg-[#161B22] border-2 border-[#30363D] p-4 space-y-2">
        <div className="flex justify-between items-center text-xs">
          <span className="font-bold text-white uppercase">ISOLATION FOREST ANOMALY SCORE</span>
          <span className="text-white font-bold">{telemetry.anomalyScore.toFixed(2)} / 1.00</span>
        </div>
        <div className="w-full h-4 bg-[#0D1117] border border-[#30363D] overflow-hidden">
          <div
            className="h-full transition-all duration-300"
            style={{
              width: `${telemetry.anomalyScore * 100}%`,
              backgroundColor:
                telemetry.anomalyScore < 0.35
                  ? '#15803D'
                  : telemetry.anomalyScore < 0.70
                  ? '#B45309'
                  : '#B91C1C',
            }}
          ></div>
        </div>
      </div>

      {/* 5. ROLE-SPECIFIC CONTROLS */}
      {isAdmin ? (
        <div className="space-y-6">
          {/* Dynamic Early-Warning Banner (Admin Only) */}
          <DynamicEarlyWarningBanner
            timeToCriticalHours={telemetry.forecast?.timeToCriticalHours}
            statusMessage={telemetry.forecast?.statusMessage}
            activeNodeId={activeForecastNode}
            criticalThreshold={telemetry.forecast?.criticalThreshold || 35.0}
            onTriggerRelaySiren={handleSirenToggle}
          />

          {/* Interactive Multi-Step Displacement Forecast Chart (Admin Only) */}
          <DisplacementForecastChart
            historicalPoints={historicalPoints}
            forecastTrajectory={telemetry.forecast?.forecastTrajectory}
            timeToCriticalHours={telemetry.forecast?.timeToCriticalHours}
            criticalThreshold={telemetry.forecast?.criticalThreshold || 35.0}
            activeNodeId={activeForecastNode}
            onNodeChange={setActiveForecastNode}
          />

          {/* Automatic Hardware Siren & Cellular Dispatch Relay Panel (Admin Only) */}
          <HardwareRelayAlertPanel
            isCriticalActive={isCritical}
            timeToCriticalHours={telemetry.forecast?.timeToCriticalHours}
            activeNodeId={activeForecastNode}
          />

          {/* Manual Drill Controls */}
          <div className="bg-[#161B22] border-2 border-[#30363D] p-4 space-y-3">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-white uppercase">[ MANUAL SAFETY DRILL OVERRIDE ]</span>
              <span className="text-[#8B949E]">MODE: <strong className="text-white">{overrideState}</strong></span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <button
                onClick={() => triggerDrillOverride('TEST_ZONE_A')}
                className={`py-2 px-2 font-bold border ${
                  overrideState === 'TEST_ZONE_A' ? 'bg-[#15803D] text-white border-white' : 'bg-[#0D1117] text-[#15803D] border-[#15803D]'
                }`}
              >
                [ TEST ZONE A ]
              </button>
              <button
                onClick={() => triggerDrillOverride('TEST_ZONE_B')}
                className={`py-2 px-2 font-bold border ${
                  overrideState === 'TEST_ZONE_B' ? 'bg-[#B45309] text-white border-white' : 'bg-[#0D1117] text-[#B45309] border-[#B45309]'
                }`}
              >
                [ TEST ZONE B ]
              </button>
              <button
                onClick={() => triggerDrillOverride('TEST_ZONE_C')}
                className={`py-2 px-2 font-bold border ${
                  overrideState === 'TEST_ZONE_C' ? 'bg-[#B91C1C] text-white border-white' : 'bg-[#0D1117] text-[#B91C1C] border-[#B91C1C]'
                }`}
              >
                [ TEST ZONE C ]
              </button>
              <button
                onClick={() => triggerDrillOverride('AUTO')}
                className={`py-2 px-2 font-bold border ${
                  overrideState === 'AUTO' ? 'bg-[#30363D] text-white border-white' : 'bg-[#0D1117] text-[#8B949E] border-[#30363D]'
                }`}
              >
                [ RESET AUTO ]
              </button>
            </div>
          </div>

          {/* Live Digital Shift Muster & Personnel Safety Tracking Desk */}
          <ActiveShiftMusterDesk />
        </div>
      ) : (
        /* Worker View Action Strip (Digital Mobile Verified) */
        <div className="bg-[#161B22] border-2 border-[#15803D] p-5 space-y-4 text-xs">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-[#30363D] pb-2">
            <span className="font-bold text-white uppercase">WORKER SAFELINK MOBILE EMERGENCY DISPATCH</span>
            <span className="bg-[#15803D] text-white px-2 py-0.5 font-bold">
              DIGITAL TAG: {currentUser?.empId || 'EMP-8842'} | MOBILE: {currentUser?.mobile || '+91 98765 43210'}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <a
              href="tel:108"
              className="w-full block text-center py-3.5 bg-[#B91C1C] text-white font-display font-extrabold text-xs sm:text-sm uppercase border-2 border-white hover:bg-red-800 transition-colors"
            >
              [ 🚨 CALL SURFACE MINE RESCUE (108) ]
            </a>
            <a
              href="tel:112"
              className="w-full block text-center py-3.5 bg-[#B45309] text-white font-display font-extrabold text-xs sm:text-sm uppercase border-2 border-white hover:bg-amber-800 transition-colors"
            >
              [ 📞 NATIONAL EMERGENCY DISPATCH (112) ]
            </a>
          </div>
        </div>
      )}
    </>
  )}
</div>
);
};
