import React, { useState } from 'react';
import { useTelemetry } from '../context/TelemetryContext';
import { useAuth } from '../context/AuthContext';
import { sirenSynthesizer } from '../services/siren';

export const WorkerHUD = ({ setActiveTab }) => {
  const { telemetry } = useTelemetry();
  const { currentUser, logout } = useAuth();

  const [sirenMuted, setSirenMuted] = useState(false);

  // Fallback worker profile if not logged in
  const workerProfile = currentUser || {
    empId: 'EMP-8842',
    name: 'Rajesh Kumar',
    sector: 'Zone B Longwall Panel',
    registerRef: 'BOOK-04-P112',
  };

  const handleSirenToggle = () => {
    if (sirenSynthesizer.isPlaying) {
      sirenSynthesizer.stop();
      setSirenMuted(true);
    } else {
      sirenSynthesizer.start();
      setSirenMuted(false);
    }
  };

  const isCritical = telemetry.currentZone === 'ZONE_C';
  const isCaution = telemetry.currentZone === 'ZONE_B';

  return (
    <div
      className={`min-h-[calc(100vh-140px)] font-mono p-4 md:p-8 flex flex-col justify-between max-w-md mx-auto select-none transition-colors duration-300 ${
        isCritical
          ? 'bg-[#0D1117] siren-active border-4 border-[#B91C1C]'
          : 'bg-[#0D1117] border-2 border-[#30363D]'
      }`}
    >
      {/* Top Header Strip */}
      <div className="bg-[#161B22] border border-[#30363D] p-3 flex justify-between items-center text-xs">
        <div>
          <span className="text-[#8B949E] block">SAFELINK HUD // UNDERGROUND</span>
          <span className="text-white font-bold">{workerProfile.sector}</span>
        </div>
        <div className="text-right">
          <span className="text-[#8B949E] block">STATUS</span>
          <span
            className={`font-bold uppercase ${
              isCritical
                ? 'text-[#B91C1C] animate-ping'
                : isCaution
                ? 'text-[#B45309]'
                : 'text-[#15803D]'
            }`}
          >
            {telemetry.currentZone.replace('_', ' ')}
          </span>
        </div>
      </div>

      {/* CENTRAL HAZARD BEACON */}
      <div className="my-6 space-y-4 text-center">
        <div
          className={`p-6 border-4 flex flex-col items-center justify-center space-y-4 ${
            isCritical
              ? 'bg-[#B91C1C] border-white text-white'
              : isCaution
              ? 'bg-[#B45309] border-white text-white'
              : 'bg-[#15803D] border-white text-white'
          }`}
        >
          <div className="text-xs font-bold uppercase tracking-widest border-b border-white/40 pb-1">
            HAZARD LEVEL BEACON
          </div>
          <h2 className="text-2xl md:text-3xl font-display font-extrabold tracking-tight uppercase">
            {telemetry.currentZone === 'ZONE_A' && 'ZONE A // NORMAL MONITORING'}
            {telemetry.currentZone === 'ZONE_B' && 'ZONE B // SEISMIC CAUTION'}
            {telemetry.currentZone === 'ZONE_C' && 'ZONE C // CRITICAL ALERT'}
          </h2>
          <p className="text-xs md:text-sm font-mono font-bold leading-relaxed max-w-xs">
            "{telemetry.zoneMessage}"
          </p>
        </div>

        {/* SIREN AUDIO CONTROL DECK */}
        <div className="flex items-center justify-between bg-[#161B22] border border-[#30363D] p-3 text-xs">
          <span className="text-[#8B949E]">WEB AUDIO SIREN (800Hz/500Hz):</span>
          <button
            onClick={handleSirenToggle}
            className={`px-3 py-1.5 font-bold uppercase border ${
              sirenSynthesizer.isPlaying
                ? 'bg-[#B91C1C] text-white border-white animate-pulse'
                : 'bg-[#30363D] text-[#E6EDF3] border-[#374151]'
            }`}
          >
            {sirenSynthesizer.isPlaying ? '[ SIREN: ACTIVE (MUTE) ]' : '[ SIREN: READY (TEST) ]'}
          </button>
        </div>
      </div>

      {/* WORKER CREDENTIAL STRIP */}
      <div className="bg-[#161B22] border border-[#30363D] p-4 space-y-2 text-xs">
        <div className="text-[#8B949E] font-bold uppercase border-b border-[#30363D] pb-1">
          WORKER IDENTITY & MUSTER VERIFICATION
        </div>
        <div className="grid grid-cols-2 gap-2 text-[#E6EDF3]">
          <div>
            <span className="text-[#8B949E] block">WORKER NAME:</span>
            <span className="font-bold">{workerProfile.name}</span>
          </div>
          <div>
            <span className="text-[#8B949E] block">EMPLOYEE ID:</span>
            <span className="font-bold">{workerProfile.empId}</span>
          </div>
        </div>
        <div className="pt-2 border-t border-[#30363D] flex justify-between items-center text-[11px]">
          <span className="text-[#8B949E]">PHYSICAL MUSTER TAG:</span>
          <span className="bg-[#15803D] text-white px-2 py-0.5 font-bold">
            VERIFIED: {workerProfile.registerRef || 'BOOK 04, PG 112'}
          </span>
        </div>
      </div>

      {/* EMERGENCY ACTION DECK */}
      <div className="mt-6 space-y-3">
        <a
          href="tel:108"
          className="w-full block text-center py-4 bg-[#B91C1C] text-white font-display font-extrabold text-sm uppercase border-2 border-white hover:bg-red-800 transition-colors"
        >
          [ CALL AMBULANCE / SURFACE EMS (108) ]
        </a>

        <button
          onClick={() => {
            logout();
            setActiveTab('auth');
          }}
          className="w-full py-3 bg-[#30363D] text-white font-bold text-xs uppercase border border-[#374151] hover:bg-gray-700 transition-colors"
        >
          [ LOGOUT FROM HUD ]
        </button>
      </div>
    </div>
  );
};
