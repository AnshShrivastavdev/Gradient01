import React from 'react';
import { ShieldCheck, AlertTriangle, AlertOctagon } from 'lucide-react';
import { useTelemetryContext } from '../context/WebSocketContext';

export const ZoneStatusGrid = ({ selectedNode, onSelectNode }) => {
  const { telemetry } = useTelemetryContext();

  const zones = [
    {
      id: 'NODE_A1',
      title: 'Zone A // Entry Gate Sector',
      subtitle: 'Fixed Reference Bedrock',
      data: telemetry.NODE_A1 || {},
    },
    {
      id: 'NODE_B1',
      title: 'Zone B // Longwall Panel',
      subtitle: 'Central Stepper Chamber',
      data: telemetry.NODE_B1 || {},
    },
    {
      id: 'NODE_C1',
      title: 'Zone C // Extraction Void',
      subtitle: 'High Shear Overburden',
      data: telemetry.NODE_C1 || {},
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {zones.map((zone) => {
        const risk = zone.data.predicted_risk || 'Normal';
        const isSelected = selectedNode === zone.id;

        let borderCol = 'border-green-800 bg-green-950/20';
        let badgeCol = 'bg-green-800/60 text-green-300 border-green-600';
        let icon = <ShieldCheck className="w-5 h-5 text-green-400" />;

        if (risk === 'Critical') {
          borderCol = 'border-red-600 bg-red-950/30 animate-pulse';
          badgeCol = 'bg-red-800 text-white border-red-500';
          icon = <AlertOctagon className="w-5 h-5 text-red-400" />;
        } else if (risk === 'Warning') {
          borderCol = 'border-amber-600 bg-amber-950/30';
          badgeCol = 'bg-amber-800 text-amber-200 border-amber-500';
          icon = <AlertTriangle className="w-5 h-5 text-amber-400" />;
        }

        return (
          <div
            key={zone.id}
            onClick={() => onSelectNode(zone.id)}
            className={`p-4 rounded-xl border transition-all cursor-pointer ${borderCol} ${
              isSelected ? 'ring-2 ring-blue-500 shadow-lg shadow-blue-900/20' : 'hover:border-gray-500'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                {icon}
                <span className="text-sm font-bold text-white">{zone.title}</span>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full border font-mono font-bold ${badgeCol}`}>
                {risk.toUpperCase()}
              </span>
            </div>

            <p className="text-xs text-gray-400 mb-3">{zone.subtitle} ({zone.id})</p>

            <div className="grid grid-cols-4 gap-2 text-center bg-[#0B0F19]/80 p-2 rounded-lg border border-[#1F2937]">
              <div>
                <p className="text-[10px] text-gray-500">TILT</p>
                <p className="text-xs font-mono font-bold text-gray-200">{zone.data.tilt_x_deg || 0}°</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500">DISP</p>
                <p className="text-xs font-mono font-bold text-gray-200">{zone.data.displacement_mm || 0}mm</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500">STRAIN</p>
                <p className="text-xs font-mono font-bold text-gray-200">{zone.data.strain_ue || 0}µε</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500">VIB</p>
                <p className="text-xs font-mono font-bold text-gray-200">{zone.data.vibration_amp || 0}g</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
