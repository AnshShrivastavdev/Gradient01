import React from 'react';
import { ShieldCheck, AlertTriangle, AlertOctagon, Radio, Anchor, Activity } from 'lucide-react';
import { useTelemetryContext } from '../context/WebSocketContext';

export const ZoneStatusGrid = ({ selectedNode, onSelectNode }) => {
  const { telemetry, isConnected } = useTelemetryContext();

  const node1Data = telemetry.NODE_01 || telemetry.NODE_A1 || {};
  const node2Data = telemetry.NODE_02 || telemetry.NODE_B1 || {};

  // Differential displacement calculations
  const rawNode1Disp = node1Data.displacement_mm ?? 0.45;
  const rawNode2Disp = node2Data.displacement_mm ?? 7.50;
  const differentialDisp = (node2Data.differential_displacement_mm !== undefined && node2Data.differential_displacement_mm !== null)
    ? node2Data.differential_displacement_mm
    : (rawNode2Disp - rawNode1Disp);

  const stations = [
    {
      id: 'NODE_01',
      alias: 'NODE_A1',
      nodeNumber: 'NODE 01',
      role: 'REFERENCE DATUM',
      roleType: 'reference',
      title: 'Station 01 // Fixed Bedrock Datum',
      subtitle: 'Zero-Drift Baseline Reference Platform',
      data: node1Data,
      icon: <Anchor className="w-5 h-5 text-cyan-400" />,
      tagColor: 'bg-cyan-950/80 text-cyan-300 border-cyan-700',
    },
    {
      id: 'NODE_02',
      alias: 'NODE_B1',
      nodeNumber: 'NODE 02',
      role: 'ACTIVE MONITORING',
      roleType: 'monitoring',
      title: 'Station 02 // Strata Subsidence Panel',
      subtitle: 'Underground Active Roof Sag (Direct via Gateway)',
      data: node2Data,
      icon: <Activity className="w-5 h-5 text-amber-400" />,
      tagColor: 'bg-amber-950/80 text-amber-300 border-amber-700',
    },
    {
      id: 'GATEWAY_LINK',
      alias: 'GATEWAY_SURFACE_01',
      nodeNumber: 'GATEWAY 01',
      role: 'CENTRAL LORAWAN / WIFI',
      roleType: 'gateway',
      title: 'Gateway // Surface Ingestion Link',
      subtitle: 'Differential Strata Ingestion & WiFi Telemetry Relay',
      data: {
        predicted_risk: node2Data.predicted_risk || 'Normal',
        tilt_x_deg: node2Data.differential_tilt_deg || (node2Data.tilt_x_deg - node1Data.tilt_x_deg || 0).toFixed(2),
        displacement_mm: Number(differentialDisp).toFixed(2),
        strain_ue: node2Data.strain_ue || 0,
        vibration_amp: node2Data.vibration_amp || 0,
        rssi_dbm: node2Data.rssi_dbm || -78,
      },
      icon: <Radio className="w-5 h-5 text-indigo-400" />,
      tagColor: 'bg-indigo-950/80 text-indigo-300 border-indigo-700',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {stations.map((st) => {
        const risk = st.data.predicted_risk || 'Normal';
        const isSelected = selectedNode === st.id || selectedNode === st.alias;

        let borderCol = 'border-green-800/60 bg-green-950/20';
        let badgeCol = 'bg-green-800/60 text-green-300 border-green-600';
        let statusIcon = <ShieldCheck className="w-4 h-4 text-green-400" />;

        if (st.roleType === 'reference') {
          borderCol = 'border-cyan-800/50 bg-cyan-950/15';
        } else if (risk === 'Critical') {
          borderCol = 'border-red-600 bg-red-950/30 animate-pulse';
          badgeCol = 'bg-red-800 text-white border-red-500';
          statusIcon = <AlertOctagon className="w-4 h-4 text-red-400" />;
        } else if (risk === 'Warning') {
          borderCol = 'border-amber-600/70 bg-amber-950/25';
          badgeCol = 'bg-amber-800 text-amber-200 border-amber-500';
          statusIcon = <AlertTriangle className="w-4 h-4 text-amber-400" />;
        }

        return (
          <div
            key={st.id}
            onClick={() => onSelectNode(st.id)}
            className={`p-4 rounded-xl border transition-all cursor-pointer ${borderCol} ${
              isSelected ? 'ring-2 ring-blue-500 shadow-lg shadow-blue-900/30' : 'hover:border-gray-500'
            }`}
          >
            {/* Station Header */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                {st.icon}
                <div>
                  <span className="text-xs font-mono font-bold text-gray-300 uppercase block">{st.nodeNumber}</span>
                  <span className="text-sm font-bold text-white leading-tight">{st.title}</span>
                </div>
              </div>
              <div className="flex flex-col items-end space-y-1">
                <span className={`text-[9px] px-2 py-0.5 rounded-full border font-mono font-bold ${st.tagColor}`}>
                  {st.role}
                </span>
                <span className={`text-[9px] px-2 py-0.5 rounded-full border font-mono font-bold flex items-center gap-1 ${badgeCol}`}>
                  {statusIcon}
                  {risk.toUpperCase()}
                </span>
              </div>
            </div>

            <p className="text-xs text-gray-400 mb-3">{st.subtitle}</p>

            {/* Quick Metrics Grid */}
            <div className="grid grid-cols-4 gap-2 text-center bg-[#0B0F19]/90 p-2 rounded-lg border border-[#1F2937]">
              <div>
                <p className="text-[10px] text-gray-500 font-mono">
                  {st.roleType === 'gateway' ? 'Δ TILT' : 'TILT'}
                </p>
                <p className="text-xs font-mono font-bold text-gray-200">{st.data.tilt_x_deg || 0}°</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500 font-mono">
                  {st.roleType === 'gateway' ? 'Δ SAG' : 'DISP'}
                </p>
                <p className="text-xs font-mono font-bold text-gray-200">{st.data.displacement_mm || 0}mm</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500 font-mono">STRAIN</p>
                <p className="text-xs font-mono font-bold text-gray-200">{st.data.strain_ue || 0}µε</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-500 font-mono">
                  {st.roleType === 'gateway' ? 'RSSI' : 'VIB'}
                </p>
                <p className="text-xs font-mono font-bold text-gray-200">
                  {st.roleType === 'gateway' ? `${st.data.rssi_dbm || -75}dBm` : `${st.data.vibration_amp || 0}g`}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
