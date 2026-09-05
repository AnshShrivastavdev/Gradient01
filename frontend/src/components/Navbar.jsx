import React from 'react';
import { Radio, Activity, ShieldAlert } from 'lucide-react';
import { useTelemetryContext } from '../context/WebSocketContext';

export const Navbar = () => {
  const { isConnected, telemetry } = useTelemetryContext();
  const hasCritical = Object.values(telemetry).some((n) => n.predicted_risk === 'Critical');

  return (
    <header className="bg-[#0B0F19] border-b border-[#1F2937] px-6 py-4 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center space-x-3">
        <div className="p-2 bg-blue-600/20 border border-blue-500 rounded-lg">
          <Activity className="w-6 h-6 text-blue-400 animate-pulse" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-white tracking-wider flex items-center gap-2">
            TEAM GRADIENT // MINE SUBSIDENCE MONITORING
            <span className="text-xs bg-blue-900/60 text-blue-300 px-2 py-0.5 rounded border border-blue-700">SIH 2026</span>
          </h1>
          <p className="text-xs text-gray-400">ESP32 LoRa 433MHz Telemetry & Real-Time ML Hazard Risk Engine</p>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {hasCritical && (
          <div className="flex items-center space-x-2 px-3 py-1.5 bg-red-950/80 border border-red-600 rounded-full animate-bounce">
            <ShieldAlert className="w-4 h-4 text-red-400" />
            <span className="text-xs font-bold text-red-300">EVACUATION SIREN ACTIVE</span>
          </div>
        )}

        <div className="flex items-center space-x-2 bg-[#111827] px-3 py-1.5 rounded-full border border-[#1F2937]">
          <span className={`w-2.5 h-2.5 rounded-full ${isConnected ? 'bg-green-500 animate-ping' : 'bg-amber-500'}`} />
          <span className="text-xs font-mono text-gray-300">
            {isConnected ? 'LORA_GATEWAY_ONLINE' : 'SIMULATION_STREAM'}
          </span>
        </div>
      </div>
    </header>
  );
};
