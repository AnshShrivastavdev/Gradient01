import React, { useState } from 'react';

/**
 * HardwareRelayAlertPanel
 * -------------------------------------------------------------
 * Displays real-time industrial SCADA hardware relay statuses
 * (Siren, Strobe, LoRa Broadcast) and GSM Emergency SMS dispatch logs.
 */
export const HardwareRelayAlertPanel = ({
  isCriticalActive = false,
  timeToCriticalHours = null,
  activeNodeId = 'NODE_C1',
}) => {
  const [manualSirenOverride, setManualSirenOverride] = useState(false);
  const [smsLogs, setSmsLogs] = useState([
    {
      id: 1,
      time: '10:42:15 AM',
      recipient: 'DGMS Safety Directorate (+91-9876543210)',
      status: 'SENT',
      message: 'Zone C1 Telemetry Nominal baseline (12.4mm). Routine telemetry heartbeat.',
    },
  ]);

  const isRelaySirenActive = isCriticalActive || manualSirenOverride || (timeToCriticalHours !== null && timeToCriticalHours <= 5.0);
  const isStrobeActive = isRelaySirenActive;

  const handleTestSmsBroadcast = () => {
    const newLog = {
      id: Date.now(),
      time: new Date().toLocaleTimeString(),
      recipient: 'Mines Rescue Station & DGMS (+91-9876543210)',
      status: 'DELIVERED (ACK 200)',
      message: `[CRITICAL ALERT] Accelerated subsidence at ${activeNodeId}. Estimated failure in ${timeToCriticalHours || '4.2'} hrs. Evacuate sector.`,
    };
    setSmsLogs((prev) => [newLog, ...prev.slice(0, 4)]);
  };

  return (
    <div className="bg-[#161B22] border-2 border-[#30363D] p-4 sm:p-5 space-y-4 font-mono text-[#E6EDF3]">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-[#30363D] pb-3">
        <div className="space-y-0.5">
          <div className="text-[10px] bg-[#30363D] text-[#8B949E] px-2 py-0.5 inline-block font-bold uppercase">
            INDUSTRIAL I/O & RELAY MATRIX
          </div>
          <h4 className="text-sm sm:text-base font-bold text-white uppercase">
            AUTOMATIC HARDWARE SIRENS & EMERGENCY BROADCAST DISPATCH
          </h4>
        </div>

        <button
          onClick={handleTestSmsBroadcast}
          className="px-3 py-1.5 bg-[#0D1117] text-[#00B4D8] font-bold text-xs uppercase border border-[#00B4D8] hover:bg-[#00B4D8] hover:text-black transition-colors"
        >
          [ TRANSMIT EMERGENCY SMS DISPATCH ]
        </button>
      </div>

      {/* 3 Hardware Relays */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
        {/* Relay 1: Physical Siren */}
        <div
          className={`border p-3 space-y-2 transition-colors ${
            isRelaySirenActive
              ? 'bg-[#2A1215] border-[#EF4444]'
              : 'bg-[#0D1117] border-[#30363D]'
          }`}
        >
          <div className="flex justify-between items-center">
            <span className="text-[#8B949E] text-[10px] font-bold">RELAY #1 (GPIO 26)</span>
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isRelaySirenActive ? 'bg-[#EF4444] animate-ping' : 'bg-[#30363D]'
              }`}
            ></span>
          </div>
          <div className="font-bold text-white text-sm">110dB INDUSTRIAL SIREN</div>
          <div className="flex justify-between items-center text-[11px] pt-1 border-t border-[#30363D]">
            <span className="text-[#8B949E]">STATE:</span>
            <span
              className={`font-bold ${
                isRelaySirenActive ? 'text-[#EF4444]' : 'text-[#8B949E]'
              }`}
            >
              {isRelaySirenActive ? '[ ENERGIZED (ACTIVE) ]' : '[ STANDBY (OPEN) ]'}
            </span>
          </div>
        </div>

        {/* Relay 2: Optical Strobe */}
        <div
          className={`border p-3 space-y-2 transition-colors ${
            isStrobeActive
              ? 'bg-[#2A1D0E] border-[#F59E0B]'
              : 'bg-[#0D1117] border-[#30363D]'
          }`}
        >
          <div className="flex justify-between items-center">
            <span className="text-[#8B949E] text-[10px] font-bold">RELAY #2 (GPIO 27)</span>
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isStrobeActive ? 'bg-[#F59E0B] animate-pulse' : 'bg-[#30363D]'
              }`}
            ></span>
          </div>
          <div className="font-bold text-white text-sm">ROTATING OPTICAL STROBE</div>
          <div className="flex justify-between items-center text-[11px] pt-1 border-t border-[#30363D]">
            <span className="text-[#8B949E]">STATE:</span>
            <span
              className={`font-bold ${
                isStrobeActive ? 'text-[#F59E0B]' : 'text-[#8B949E]'
              }`}
            >
              {isStrobeActive ? '[ FLASHING (3.0 Hz) ]' : '[ STANDBY (OFF) ]'}
            </span>
          </div>
        </div>

        {/* Relay 3: LoRa RF Emergency Broadcast */}
        <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-[#8B949E] text-[10px] font-bold">RF MODEM (SX1276)</span>
            <span className="w-2.5 h-2.5 rounded-full bg-[#10B981]"></span>
          </div>
          <div className="font-bold text-white text-sm">LoRa EMERGENCY BROADCAST</div>
          <div className="flex justify-between items-center text-[11px] pt-1 border-t border-[#30363D]">
            <span className="text-[#8B949E]">CH: 868.10 MHz</span>
            <span className="text-[#10B981] font-bold">[ SYNCED / READY ]</span>
          </div>
        </div>
      </div>

      {/* SMS & Cellular Dispatch Activity Table */}
      <div className="space-y-2 pt-1">
        <div className="text-[11px] font-bold text-[#8B949E] uppercase">
          [ CELLULAR GSM SMS ALERT TRANSMISSION LOG ]
        </div>
        <div className="bg-[#0D1117] border border-[#30363D] divide-y divide-[#30363D] text-xs">
          {smsLogs.map((log) => (
            <div key={log.id} className="p-2.5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
              <div className="space-y-0.5">
                <div className="flex items-center space-x-2">
                  <span className="text-[#00B4D8] font-bold text-[11px]">{log.time}</span>
                  <span className="text-white font-bold">{log.recipient}</span>
                </div>
                <div className="text-[#8B949E] text-[11px]">{log.message}</div>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 bg-[#15803D] text-white whitespace-nowrap">
                {log.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
