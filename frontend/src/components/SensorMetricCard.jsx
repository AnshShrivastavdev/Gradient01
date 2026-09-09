import React from 'react';
import { Compass, MoveVertical, Gauge, Zap, Anchor, Activity, Radio } from 'lucide-react';

export const SensorMetricCard = ({ data = {} }) => {
  const isReference = data.role === 'REFERENCE' || data.node_id === 'NODE_01' || data.node_id === 'NODE_A1';
  const tilt = Math.sqrt(Math.pow(data.tilt_x_deg || 0, 2) + Math.pow(data.tilt_y_deg || 0, 2)).toFixed(2);
  const disp = (data.displacement_mm || 0).toFixed(2);
  const diffDisp = data.differential_displacement_mm !== undefined && data.differential_displacement_mm !== null
    ? `${data.differential_displacement_mm > 0 ? '+' : ''}${data.differential_displacement_mm} mm`
    : null;
  const strain = (data.strain_ue || 0).toFixed(1);
  const vib = (data.vibration_amp || 0).toFixed(4);

  const metrics = [
    {
      title: isReference ? 'Reference Inclinometer' : 'Tilt Inclinometer',
      sensor: 'MPU6500 (Pitch/Roll)',
      value: `${tilt}°`,
      subvalue: `X: ${data.tilt_x_deg || 0}° | Y: ${data.tilt_y_deg || 0}°`,
      icon: <Compass className="w-5 h-5 text-indigo-400" />,
      threshold: isReference ? 'Zero Baseline: <0.05°' : 'Max Nominal: 0.10° | Yield: >2.5°',
      barPercent: Math.min(100, (tilt / 5.0) * 100),
      color: tilt > 2.5 ? 'bg-red-500' : tilt > 0.5 ? 'bg-amber-500' : 'bg-indigo-500',
    },
    {
      title: isReference ? 'Bedrock Baseline Datum' : 'Roof Displacement',
      sensor: 'VL53L4CD ToF Laser',
      value: `${disp} mm`,
      subvalue: isReference
        ? 'Fixed Stable Bedrock Height'
        : (diffDisp ? `Δ Rel to Node 1: ${diffDisp}` : 'Vertical Subsidence Sag'),
      icon: <MoveVertical className="w-5 h-5 text-cyan-400" />,
      threshold: isReference ? 'Stable Anchor (<0.5mm)' : 'Max Nominal: 1.0mm | Yield: >20mm',
      barPercent: Math.min(100, (disp / 40.0) * 100),
      color: disp > 20 ? 'bg-red-500' : disp > 5.0 ? 'bg-amber-500' : 'bg-cyan-500',
    },
    {
      title: isReference ? 'Anchor Micro-Strain' : 'Micro-Strain Gauge',
      sensor: 'BX120-3AA + HX711',
      value: `${strain} µε`,
      subvalue: isReference ? 'Pillar Base Rest Load' : 'Roof Bolt Tensile Yield',
      icon: <Gauge className="w-5 h-5 text-emerald-400" />,
      threshold: isReference ? 'Nominal Baseline (<100µε)' : 'Max Nominal: 150µε | Yield: >400µε',
      barPercent: Math.min(100, (strain / 800.0) * 100),
      color: strain > 400 ? 'bg-red-500' : strain > 180 ? 'bg-amber-500' : 'bg-emerald-500',
    },
    {
      title: isReference ? 'Ambient Seismic Floor' : 'Seismic Vibration',
      sensor: 'Piezo + LM358 Circuit',
      value: `${vib} g`,
      subvalue: isReference ? 'Mine Background Noise' : 'Transient Shocks & Bursts',
      icon: <Zap className="w-5 h-5 text-amber-400" />,
      threshold: isReference ? 'Quiet Floor (<0.02g)' : 'Max Nominal: 0.08g | Yield: >0.80g',
      barPercent: Math.min(100, (vib / 3.0) * 100),
      color: vib > 0.8 ? 'bg-red-500' : vib > 0.1 ? 'bg-amber-500' : 'bg-amber-500',
    },
  ];

  return (
    <div className="space-y-3">
      {/* Node Role Status Strip */}
      <div className="flex flex-wrap items-center justify-between px-3 py-2 bg-[#111827] border border-[#1F2937] rounded-lg text-xs font-mono">
        <div className="flex items-center space-x-2">
          {isReference ? (
            <Anchor className="w-4 h-4 text-cyan-400" />
          ) : (
            <Activity className="w-4 h-4 text-amber-400" />
          )}
          <span className="font-bold text-white">
            SELECTED: {data.node_id || 'NODE_02'}
          </span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
            isReference
              ? 'bg-cyan-950 text-cyan-300 border-cyan-700'
              : 'bg-amber-950 text-amber-300 border-amber-700'
          }`}>
            {isReference ? 'NODE 1: REFERENCE DATUM' : 'NODE 2: ACTIVE MONITORING (VIA GATEWAY)'}
          </span>
        </div>

        <div className="flex items-center space-x-4 text-gray-400 text-[11px]">
          {data.ref_displacement_mm !== undefined && (
            <span>Ref Datum (Node 1): <strong className="text-cyan-300">{data.ref_displacement_mm} mm</strong></span>
          )}
          {data.differential_displacement_mm !== undefined && (
            <span>Differential Sag (Δ): <strong className="text-amber-300">+{data.differential_displacement_mm} mm</strong></span>
          )}
          <span className="flex items-center gap-1">
            <Radio className="w-3.5 h-3.5 text-blue-400" />
            LoRa: {data.rssi_dbm || -75} dBm
          </span>
        </div>
      </div>

      {/* 4 Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((m, idx) => (
          <div key={idx} className="bg-[#111827] border border-[#1F2937] p-4 rounded-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{m.title}</span>
                <div className="p-1.5 bg-[#0B0F19] rounded-lg border border-[#1F2937]">{m.icon}</div>
              </div>
              <p className="text-2xl font-bold font-mono text-white mb-1">{m.value}</p>
              <p className="text-xs text-gray-400 mb-3">{m.subvalue}</p>
            </div>

            <div>
              <div className="w-full bg-[#0B0F19] h-2 rounded-full overflow-hidden mb-2 border border-[#1F2937]">
                <div className={`h-full transition-all duration-300 ${m.color}`} style={{ width: `${m.barPercent}%` }} />
              </div>
              <div className="flex items-center justify-between text-[10px] text-gray-500 font-mono">
                <span>{m.sensor}</span>
                <span>{m.threshold}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
