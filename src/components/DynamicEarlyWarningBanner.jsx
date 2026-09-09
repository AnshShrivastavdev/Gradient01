import React, { useEffect, useState } from 'react';
import { sirenSynthesizer } from '../services/siren';

/**
 * DynamicEarlyWarningBanner
 * -------------------------------------------------------------
 * Displays real-time geomechanical failure warnings, exact Time-to-Failure (TTF),
 * audio speech synthesis alert buttons, and emergency evacuation directives.
 */
export const DynamicEarlyWarningBanner = ({
  timeToCriticalHours = 4.2,
  statusMessage = 'Estimated time to critical subsidence threshold: 4.2 hours',
  activeNodeId = 'NODE_02',
  criticalThreshold = 35.0,
  onTriggerRelaySiren,
}) => {
  const isCriticalBreachImminent = timeToCriticalHours !== null && timeToCriticalHours > 0;
  const [speechMuted, setSpeechMuted] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(
    timeToCriticalHours ? Math.round(timeToCriticalHours * 3600) : 0
  );

  // Update countdown when timeToCriticalHours changes
  useEffect(() => {
    if (timeToCriticalHours) {
      setSecondsRemaining(Math.round(timeToCriticalHours * 3600));
    }
  }, [timeToCriticalHours]);

  // Countdown timer tick
  useEffect(() => {
    if (!isCriticalBreachImminent) return;
    const interval = setInterval(() => {
      setSecondsRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [isCriticalBreachImminent]);

  const formatCountdown = (totalSecs) => {
    const hrs = Math.floor(totalSecs / 3600);
    const mins = Math.floor((totalSecs % 3600) / 60);
    const secs = totalSecs % 60;
    return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const handleSpeechAlert = () => {
    if (!speechMuted && isCriticalBreachImminent) {
      sirenSynthesizer.speak(
        `Critical Geotechnical Alert. ${statusMessage}. Evacuation protocol recommended immediately.`
      );
    }
  };

  return (
    <div
      className={`border-2 p-4 sm:p-5 transition-all duration-300 font-mono ${
        isCriticalBreachImminent
          ? 'bg-[#1C1418] border-[#EF4444] shadow-[0_0_20px_rgba(239,68,68,0.25)]'
          : 'bg-[#0F1C18] border-[#10B981]'
      }`}
    >
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
        {/* Left: Indicator & Status Text */}
        <div className="space-y-2 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                isCriticalBreachImminent
                  ? 'bg-[#B91C1C] text-white animate-pulse'
                  : 'bg-[#15803D] text-white'
              }`}
            >
              {isCriticalBreachImminent ? '⚠️ DYNAMIC EARLY-WARNING' : '✅ BASELINE NORMAL'}
            </span>

            <span className="text-xs text-[#8B949E]">
              MONITORING TARGET: <strong className="text-white">{activeNodeId}</strong>
            </span>

            {isCriticalBreachImminent && (
              <span className="text-[10px] bg-[#B45309] text-white px-2 py-0.5 font-bold uppercase">
                CRITICAL THRESHOLD: {criticalThreshold.toFixed(1)} mm
              </span>
            )}
          </div>

          <h3
            className={`text-lg sm:text-xl font-display font-extrabold uppercase tracking-tight ${
              isCriticalBreachImminent ? 'text-[#EF4444]' : 'text-[#10B981]'
            }`}
          >
            {isCriticalBreachImminent
              ? statusMessage
              : 'Ground displacement trajectory stable. No critical breach forecasted within 6 hours.'}
          </h3>

          <p className="text-xs text-[#8B949E] leading-relaxed">
            {isCriticalBreachImminent
              ? `Deep LSTM continuous trajectory predicts structural inflection to collapse. Shift safety officers must review retreat coordinates and ensure Section ${activeNodeId} miners are accounted for.`
              : 'Normal background micro-creep rates observed. Continuous 50Hz sensor stream and rolling 60-sample lookback buffer active.'}
          </p>
        </div>

        {/* Right: Countdown & Control Actions */}
        <div className="flex flex-col sm:flex-row lg:flex-col items-start lg:items-end justify-between gap-3 w-full lg:w-auto pt-2 lg:pt-0 border-t lg:border-t-0 border-[#30363D]">
          {isCriticalBreachImminent && (
            <div className="bg-[#0D1117] border border-[#B91C1C] px-3 py-1.5 text-center w-full sm:w-auto">
              <div className="text-[9px] text-[#EF4444] uppercase font-bold tracking-widest">
                T-MINUS TO CRITICAL COLLAPSE
              </div>
              <div className="text-xl sm:text-2xl font-extrabold text-white font-mono tracking-wider">
                {formatCountdown(secondsRemaining)}
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 text-xs w-full sm:w-auto">
            {isCriticalBreachImminent && (
              <button
                onClick={handleSpeechAlert}
                className="px-3 py-1.5 bg-[#B45309] text-white font-bold uppercase border border-amber-400 hover:bg-amber-700 flex items-center space-x-1"
                title="Play Audio Voice Warning"
              >
                <span>🔊</span>
                <span>[ VOICE ALERT ]</span>
              </button>
            )}

            {isCriticalBreachImminent && (
              <button
                onClick={onTriggerRelaySiren}
                className="px-3 py-1.5 bg-[#B91C1C] text-white font-bold uppercase border border-red-400 hover:bg-red-800 animate-pulse flex items-center space-x-1"
              >
                <span>🚨</span>
                <span>[ TRIGGER HARDWARE RELAY ]</span>
              </button>
            )}

            <button
              onClick={() => setSpeechMuted(!speechMuted)}
              className="px-3 py-1.5 bg-[#0D1117] text-[#8B949E] border border-[#30363D] hover:text-white"
            >
              {speechMuted ? '[ AUDIO: MUTED ]' : '[ AUDIO: ARMED ]'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
