import React, { useState } from 'react';
import { useTelemetry } from '../context/TelemetryContext';
import { useAuth } from '../context/AuthContext';
import { sirenSynthesizer } from '../services/siren';
import { DisplacementForecastChart } from '../components/DisplacementForecastChart';
import { DynamicEarlyWarningBanner } from '../components/DynamicEarlyWarningBanner';
import { HardwareRelayAlertPanel } from '../components/HardwareRelayAlertPanel';
import { ActiveShiftMusterDesk } from '../components/ActiveShiftMusterDesk';

export const DashboardPage = () => {
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
          <button
            onClick={() => setRoleMode(isAdmin ? 'WORKER' : 'ADMIN')}
            className="px-3 py-1.5 font-bold uppercase border bg-[#0D1117] text-[#00B4D8] border-[#00B4D8] hover:bg-[#00B4D8] hover:text-black transition-colors"
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
          <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3 text-xs">
            {/* Node 1 */}
            <div className="bg-[#161B22] border border-[#30363D] p-3 space-y-1">
              <div className="text-[#8B949E] text-[10px] font-bold uppercase">NODE 01 (FIXED LEFT)</div>
              <div className="text-white font-bold">TILT X: {telemetry.node1.tiltX}°</div>
              <div className="text-white font-bold">ACCEL: {telemetry.node1.transientAccel}g</div>
            </div>

            {/* Node 2 */}
            <div className="bg-[#161B22] border border-[#30363D] p-3 space-y-1">
              <div className="text-[#00B4D8] text-[10px] font-bold uppercase">NODE 02 (CENTER MOVABLE)</div>
              <div className="text-white font-bold">TILT X: {telemetry.node2.tiltX}°</div>
              <div className="text-white font-bold">VIBE RMS: {telemetry.node2.transientRms}g</div>
            </div>

            {/* Node 3 */}
            <div className="bg-[#161B22] border border-[#30363D] p-3 space-y-1">
              <div className="text-[#8B949E] text-[10px] font-bold uppercase">NODE 03 (FIXED RIGHT)</div>
              <div className="text-white font-bold">TILT X: {telemetry.node3.tiltX}°</div>
              <div className="text-white font-bold">ACCEL: {telemetry.node3.transientAccel}g</div>
            </div>

            {/* Overhead ToF Laser */}
            <div className="bg-[#161B22] border border-[#30363D] p-3 space-y-1">
              <div className="text-[#B91C1C] text-[10px] font-bold uppercase">VL53L4CD ToF LASER</div>
              <div className="text-[#8B949E] text-[11px]">DISPLACEMENT:</div>
              <div className="text-base font-bold text-white">{telemetry.tofDistance.toFixed(2)} mm</div>
            </div>

            {/* Cantilever Strain Gauge */}
            <div className="bg-[#161B22] border border-[#30363D] p-3 space-y-1">
              <div className="text-[#B45309] text-[10px] font-bold uppercase">BX120 STRAIN GAUGE</div>
              <div className="text-[#8B949E] text-[11px]">MICROSTRAIN:</div>
              <div className={`text-base font-bold ${telemetry.strainGauge > 850 ? 'text-[#B91C1C]' : 'text-white'}`}>
                {telemetry.strainGauge.toFixed(1)} με
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
    </div>
  );
};
