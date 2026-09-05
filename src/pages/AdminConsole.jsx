import React from 'react';
import { useTelemetry } from '../context/TelemetryContext';
import { useAuth } from '../context/AuthContext';
import { sirenSynthesizer } from '../services/siren';
import { DisplacementForecastChart } from '../components/DisplacementForecastChart';
import { DynamicEarlyWarningBanner } from '../components/DynamicEarlyWarningBanner';
import { HardwareRelayAlertPanel } from '../components/HardwareRelayAlertPanel';
import { ActiveShiftMusterDesk } from '../components/ActiveShiftMusterDesk';

export const AdminConsole = () => {
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

  const { registerLedger, approveWorker, rejectWorker } = useAuth();


  return (
    <div className="min-h-[calc(100vh-140px)] bg-[#0D1117] text-[#E6EDF3] font-mono p-4 md:p-8 space-y-6">
      {/* SCADA Console Title Bar */}
      <div className="bg-[#161B22] border-2 border-[#30363D] p-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="space-y-1">
          <div className="inline-block bg-[#B45309] text-white px-2.5 py-0.5 text-xs font-bold uppercase">
            SAFETY INCHARGE COMMAND DESK
          </div>
          <h2 className="text-xl md:text-2xl font-display font-extrabold text-white uppercase">
            SCADA GEOTECHNICAL MONITORING OPERATIONS
          </h2>
          <p className="text-xs text-[#8B949E]">
            Muster Verification & Real-Time Telemetry Correlation Matrix
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs">
          {/* Skeleton Loader Simulation Toggle */}
          <button
            onClick={toggleSkeletonLoading}
            className={`px-3 py-1.5 font-bold uppercase border ${
              isLoading
                ? 'bg-[#B45309] text-white border-white'
                : 'bg-[#0D1117] text-[#8B949E] border-[#30363D] hover:text-white'
            }`}
          >
            {isLoading ? '[ SKELETON LOADERS: ON ]' : '[ SIMULATE HYDRATION ]'}
          </button>
        </div>
      </div>

      {/* 1. MANUAL DRILL OVERRIDE SUITE */}
      <div className="bg-[#161B22] border-2 border-[#30363D] p-4 space-y-3">
        <div className="flex justify-between items-center border-b border-[#30363D] pb-2 text-xs">
          <span className="font-bold text-white uppercase">[ EMERGENCY SAFETY DRILL OVERRIDE ]</span>
          <span className="text-[#8B949E]">CURRENT STATE: <strong className="text-white">{overrideState}</strong></span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 text-xs">
          <button
            onClick={() => triggerDrillOverride('TEST_ZONE_A')}
            className={`py-2 px-3 font-bold border transition-colors ${
              overrideState === 'TEST_ZONE_A'
                ? 'bg-[#15803D] text-white border-white'
                : 'bg-[#0D1117] text-[#15803D] border-[#15803D] hover:bg-[#15803D] hover:text-white'
            }`}
          >
            [ TEST ZONE A: NOMINAL ]
          </button>

          <button
            onClick={() => triggerDrillOverride('TEST_ZONE_B')}
            className={`py-2 px-3 font-bold border transition-colors ${
              overrideState === 'TEST_ZONE_B'
                ? 'bg-[#B45309] text-white border-white'
                : 'bg-[#0D1117] text-[#B45309] border-[#B45309] hover:bg-[#B45309] hover:text-white'
            }`}
          >
            [ TEST ZONE B: CAUTION ]
          </button>

          <button
            onClick={() => triggerDrillOverride('TEST_ZONE_C')}
            className={`py-2 px-3 font-bold border transition-colors ${
              overrideState === 'TEST_ZONE_C'
                ? 'bg-[#B91C1C] text-white border-white animate-pulse'
                : 'bg-[#0D1117] text-[#B91C1C] border-[#B91C1C] hover:bg-[#B91C1C] hover:text-white'
            }`}
          >
            [ TEST ZONE C: CRITICAL ]
          </button>

          <button
            onClick={() => triggerDrillOverride('AUTO')}
            className={`py-2 px-3 font-bold border transition-colors ${
              overrideState === 'AUTO'
                ? 'bg-[#30363D] text-white border-white'
                : 'bg-[#0D1117] text-[#8B949E] border-[#30363D] hover:text-white'
            }`}
          >
            [ RESET TO LIVE SENSOR AUTO ]
          </button>
        </div>
      </div>

      {/* 2. DYNAMIC EARLY-WARNING BANNER */}
      <DynamicEarlyWarningBanner
        timeToCriticalHours={telemetry.forecast?.timeToCriticalHours}
        statusMessage={telemetry.forecast?.statusMessage}
        activeNodeId={activeForecastNode}
        criticalThreshold={telemetry.forecast?.criticalThreshold || 35.0}
        onTriggerRelaySiren={() => sirenSynthesizer.toggle()}
      />

      {/* 3. INTERACTIVE DISPLACEMENT SUBSIDENCE FORECAST PLOT */}
      <DisplacementForecastChart
        historicalPoints={historicalPoints}
        forecastTrajectory={telemetry.forecast?.forecastTrajectory}
        timeToCriticalHours={telemetry.forecast?.timeToCriticalHours}
        criticalThreshold={telemetry.forecast?.criticalThreshold || 35.0}
        activeNodeId={activeForecastNode}
        onNodeChange={setActiveForecastNode}
      />

      {/* 4. HARDWARE RELAYS & CELLULAR SMS DISPATCH */}
      <HardwareRelayAlertPanel
        isCriticalActive={telemetry.currentZone === 'ZONE_C'}
        timeToCriticalHours={telemetry.forecast?.timeToCriticalHours}
        activeNodeId={activeForecastNode}
      />

      {/* 5. ISOLATION FOREST AI ANOMALY BAR */}
      <div className="bg-[#161B22] border-2 border-[#30363D] p-5 space-y-3">
        <div className="flex justify-between items-center text-xs">
          <span className="font-bold text-white uppercase">UNSUPERVISED ISOLATION FOREST ANOMALY INFERENCE ENGINE</span>
          <span className="text-xs bg-[#0D1117] border border-[#30363D] px-2 py-0.5 text-white">
            RISK INDEX: <strong className="text-[#15803D]">{telemetry.anomalyScore.toFixed(2)}</strong> / 1.00
          </span>
        </div>

        {/* Continuous Score Gauge */}
        <div className="w-full h-5 bg-[#0D1117] border border-[#30363D] relative overflow-hidden">
          <div
            className="h-full transition-all duration-200"
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

        <div className="grid grid-cols-3 text-[11px] font-mono text-center pt-1 border-t border-[#30363D]">
          <div className={telemetry.anomalyScore < 0.35 ? 'text-[#15803D] font-bold' : 'text-[#8B949E]'}>
            ZONE A (0.00-0.35): STABLE BASELINE
          </div>
          <div className={telemetry.anomalyScore >= 0.35 && telemetry.anomalyScore < 0.70 ? 'text-[#B45309] font-bold' : 'text-[#8B949E]'}>
            ZONE B (0.35-0.70): TREMOR WARNING
          </div>
          <div className={telemetry.anomalyScore >= 0.70 ? 'text-[#B91C1C] font-bold' : 'text-[#8B949E]'}>
            ZONE C (&gt;0.70): EVACUATION ALERT
          </div>
        </div>
      </div>

      {/* 3. LIVE TELEMETRY MATRIX (With Skeleton Hydration Support) */}
      <div className="bg-[#161B22] border-2 border-[#30363D] p-5 space-y-4">
        <div className="flex justify-between items-center border-b border-[#30363D] pb-2 text-xs">
          <span className="font-bold text-white uppercase">[ LIVE MULTI-SENSOR TELEMETRY MATRIX ]</span>
          <span className="text-[#8B949E]">50Hz STREAMING | LoRa RF 868.10 MHz</span>
        </div>

        {isLoading ? (
          /* Skeleton Loading Hydration Display */
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="scada-skeleton-loader h-36 border border-[#30363D] p-4 space-y-3">
                <div className="h-4 bg-[#30363D] w-3/4"></div>
                <div className="h-3 bg-[#30363D] w-1/2"></div>
                <div className="h-6 bg-[#30363D] w-full"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 text-xs">
            {/* Node 1 */}
            <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-2">
              <div className="text-white font-bold border-b border-[#30363D] pb-1 uppercase">
                NODE 01 (FIXED LEFT)
              </div>
              <div className="text-[#8B949E]">TILT X: <strong className="text-white">{telemetry.node1.tiltX}°</strong></div>
              <div className="text-[#8B949E]">TILT Y: <strong className="text-white">{telemetry.node1.tiltY}°</strong></div>
              <div className="text-[#8B949E]">ACCEL: <strong className="text-white">{telemetry.node1.transientAccel}g</strong></div>
            </div>

            {/* Node 2 */}
            <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-2">
              <div className="text-white font-bold border-b border-[#30363D] pb-1 uppercase">
                NODE 02 (CENTER MOVABLE)
              </div>
              <div className="text-[#8B949E]">TILT X: <strong className="text-white">{telemetry.node2.tiltX}°</strong></div>
              <div className="text-[#8B949E]">TILT Y: <strong className="text-white">{telemetry.node2.tiltY}°</strong></div>
              <div className="text-[#8B949E]">VIBE RMS: <strong className="text-white">{telemetry.node2.transientRms}g</strong></div>
            </div>

            {/* Node 3 */}
            <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-2">
              <div className="text-white font-bold border-b border-[#30363D] pb-1 uppercase">
                NODE 03 (FIXED RIGHT)
              </div>
              <div className="text-[#8B949E]">TILT X: <strong className="text-white">{telemetry.node3.tiltX}°</strong></div>
              <div className="text-[#8B949E]">TILT Y: <strong className="text-white">{telemetry.node3.tiltY}°</strong></div>
              <div className="text-[#8B949E]">ACCEL: <strong className="text-white">{telemetry.node3.transientAccel}g</strong></div>
            </div>

            {/* Overhead ToF Laser */}
            <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-2">
              <div className="text-white font-bold border-b border-[#30363D] pb-1 uppercase">
                VL53L4CD ToF LASER
              </div>
              <div className="text-[#8B949E]">DISPLACEMENT DELTA:</div>
              <div className="text-lg font-bold text-white">{telemetry.tofDistance.toFixed(2)} mm</div>
              <div className="text-[10px] text-[#8B949E]">NON-CONTACT DISPLACEMENT</div>
            </div>

            {/* Cantilever Strain Gauge */}
            <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-2">
              <div className="text-white font-bold border-b border-[#30363D] pb-1 uppercase">
                BX120 STRAIN GAUGE
              </div>
              <div className="text-[#8B949E]">MICROSTRAIN (με):</div>
              <div
                className={`text-lg font-bold ${
                  telemetry.strainGauge > 850 ? 'text-[#B91C1C]' : 'text-[#15803D]'
                }`}
              >
                {telemetry.strainGauge.toFixed(1)} με
              </div>
              <div className="text-[10px] text-[#8B949E]">YIELD THRESHOLD: 850 με</div>
            </div>
          </div>
        )}
      </div>

      {/* 4. ACTIVE UNDERGROUND WORKER MUSTER & SAFETY VERIFICATION DESK */}
      <ActiveShiftMusterDesk />
    </div>
  );
};
