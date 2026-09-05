import React from 'react';
import { MapPin, Radio, AlertOctagon } from 'lucide-react';
import { useTelemetryContext } from '../../context/WebSocketContext';

export const MineMapView = ({ selectedNode, onSelectNode }) => {
  const { telemetry } = useTelemetryContext();

  const nodeCoordinates = {
    NODE_A1: { x: '25%', y: '45%', zone: 'Zone A', name: 'Entry Incline Gate 01' },
    NODE_B1: { x: '52%', y: '60%', zone: 'Zone B', name: 'Central Longwall Panel 04' },
    NODE_C1: { x: '78%', y: '35%', zone: 'Zone C', name: 'Extraction Void & Roof Sag 09' },
  };

  return (
    <div className="bg-[#111827] border border-[#1F2937] p-5 rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-bold text-white tracking-wide">UNDERGROUND COAL MINE 2D/3D GIS TELEMETRY MAP</h3>
          <p className="text-xs text-gray-400">Subsurface Strata Spatial Sensor Mesh</p>
        </div>
        <div className="flex items-center space-x-3 text-xs font-mono text-gray-400">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Zone A (Bedrock)</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Zone B (Active)</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Zone C (Void)</span>
        </div>
      </div>

      {/* Schematic Mine Map Canvas */}
      <div className="relative w-full h-72 bg-[#080C14] border border-[#1F2937] rounded-xl overflow-hidden flex items-center justify-center">
        {/* Mine Tunnel Grid Overlay */}
        <div
          className="absolute inset-0 opacity-15"
          style={{
            backgroundImage: 'radial-gradient(#3B82F6 1px, transparent 1px)',
            backgroundSize: '24px 24px',
          }}
        />

        {/* Longwall Conveyor & Galler Path */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none stroke-gray-700/60" strokeWidth="2" strokeDasharray="4 4">
          <path d="M 120 140 L 400 180 L 680 110" fill="none" />
          <path d="M 400 180 L 400 240" fill="none" />
        </svg>

        {/* Central Gateway Tower */}
        <div className="absolute top-4 left-4 bg-blue-950/80 border border-blue-600 px-3 py-1.5 rounded-lg flex items-center space-x-2 text-xs text-blue-200">
          <Radio className="w-4 h-4 text-blue-400 animate-pulse" />
          <span className="font-mono">CENTRAL_LORA_GATEWAY // 433 MHz</span>
        </div>

        {/* Sensor Node Markers */}
        {Object.entries(nodeCoordinates).map(([id, pos]) => {
          const nodeData = telemetry[id] || {};
          const risk = nodeData.predicted_risk || 'Normal';
          const isSelected = selectedNode === id;

          let pingColor = 'bg-green-500';
          let ringBorder = 'border-green-500 text-green-400';
          if (risk === 'Critical') {
            pingColor = 'bg-red-500';
            ringBorder = 'border-red-500 text-red-400';
          } else if (risk === 'Warning') {
            pingColor = 'bg-amber-500';
            ringBorder = 'border-amber-500 text-amber-400';
          }

          return (
            <div
              key={id}
              onClick={() => onSelectNode(id)}
              style={{ left: pos.x, top: pos.y }}
              className="absolute -translate-x-1/2 -translate-y-1/2 cursor-pointer group"
            >
              <div className="relative flex items-center justify-center">
                <span className={`absolute w-8 h-8 rounded-full ${pingColor} opacity-75 animate-ping`} />
                <div
                  className={`relative z-10 p-2 rounded-full bg-[#111827] border-2 ${ringBorder} shadow-lg ${
                    isSelected ? 'ring-4 ring-blue-500' : ''
                  }`}
                >
                  {risk === 'Critical' ? <AlertOctagon className="w-5 h-5 text-red-400" /> : <MapPin className="w-5 h-5" />}
                </div>
              </div>

              {/* Node Tag */}
              <div className="mt-1 bg-gray-900/90 border border-gray-700 px-2 py-0.5 rounded text-[10px] font-mono text-white text-center whitespace-nowrap shadow-md">
                <p className="font-bold">{id} ({pos.zone})</p>
                <p className="text-gray-400">{risk.toUpperCase()} | {nodeData.strain_ue || 0}µε</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
